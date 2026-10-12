"""Google-Search-grounded supplier shortlisting for the products in a job.

For every line item (product) a live, grounding-enabled Gemini query returns
REAL companies that supply it — with their website, any contact / email that
is visible in the search snippets, and the search-result URL each entry came
from. Results are stored on the job's data payload and persisted with its
history record, so they survive restarts and appear in the audit trail.

The model is told never to invent companies, websites or emails. Any contact
detail that comes from a snippet is unverified by design and is flagged in
the UI as "verify before use".
"""
import csv
import io
import json
import os
import random
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

from server import netfix  # noqa: F401  (IPv4-first DNS for outbound HTTPS)
from server.history import history_store
from server.jobs import job_manager
from server.websearch import WebSearchUnavailable, search_many

TARGET_SUPPLIERS = 10
MAX_FOLLOW_UP_PASSES = 2
SUPPLIER_MODES = ("all", "per_item")

# Last-known Google-Search-grounding quota state, exposed at GET /api/quota so
# the header can show it next to the pipeline label.
_GROUNDING_STATE: Dict = {"state": "unknown", "model": None, "ts": None, "detail": None}
_GROUNDING_STATE_LOCK = threading.Lock()
_QUOTA_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "quota_state.json"


def _load_grounding_state() -> None:
    """Restore the last-known quota state so it survives server restarts."""
    try:
        data = json.loads(_QUOTA_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(data, dict) and data.get("state") in ("ok", "exhausted"):
        with _GROUNDING_STATE_LOCK:
            _GROUNDING_STATE.update(
                {k: data.get(k) for k in ("state", "model", "ts", "detail")}
            )


def _note_grounding(ok: bool, model: Optional[str] = None, detail: Optional[str] = None) -> None:
    with _GROUNDING_STATE_LOCK:
        _GROUNDING_STATE.update(
            state="ok" if ok else "exhausted",
            model=model,
            ts=datetime.now().isoformat(timespec="seconds"),
            detail=detail,
        )
        payload = dict(_GROUNDING_STATE)
    try:
        _QUOTA_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _QUOTA_STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def quota_status() -> Dict:
    """Current grounding-quota state plus the official usage page link."""
    with _GROUNDING_STATE_LOCK:
        return {**dict(_GROUNDING_STATE), "link": "https://ai.dev/rate-limit"}


_load_grounding_state()

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class QuotaExhaustedError(RuntimeError):
    """Google-Search-grounding daily quota is exhausted; use the web fallback."""


class Supplier(BaseModel):
    """One real supplier as returned by the grounded model."""
    company_name: str = ""
    website: str = ""
    contact: str = ""
    email: str = ""
    source: str = ""


class SupplierList(BaseModel):
    """Structured response schema for a grounded search result."""
    suppliers: List[Supplier] = []


SEARCH_INSTRUCTION = (
    "You are a sourcing analyst using live Google Search to build a supplier "
    "shortlist. For the product below, find at least {target} REAL, distinct "
    "companies that manufacture, distribute or supply it. Base EVERY entry on "
    "actual search results. Never invent a company, website, phone number or "
    "email. For each supplier return:\n"
    "  - company_name: the official company name\n"
    "  - website: the company's official website URL\n"
    "  - contact: a named contact person/department, or a phone number, only "
    "    if it is visible in the search results\n"
    "  - email: a contact email address ONLY if one appears in the search "
    "    results; otherwise leave it empty\n"
    "  - source: the search-result URL the entry came from\n"
    "If you cannot genuinely find {target} suppliers, return as many real ones "
    "as you did find. Do not list directories, comparison portals or job "
    "boards as suppliers.\n"
    "Product: {name}\n"
    "Context / description: {description}"
)

FOLLOW_UP_INSTRUCTION = (
    "You are still using live Google Search. I already have these suppliers: "
    "{names}. Find {needed} ADDITIONAL real, distinct companies that supply "
    "this product but are NOT in that list. Base every entry on actual search "
    "results; never invent data.\n"
    "Product: {name}\n"
    "Context / description: {description}"
)

SHARED_INSTRUCTION = (
    "You are a sourcing analyst using live Google Search. Find ONE shared "
    "supplier shortlist of at least {target} REAL, distinct companies that can "
    "supply the products listed below. This SAME list will be reused for ALL of "
    "the products, so prefer manufacturers, distributors or wholesalers that "
    "can supply the range. Base EVERY entry on actual search results. Never "
    "invent a company, website, phone number or email. For each supplier "
    "return:\n"
    "  - company_name: the official company name\n"
    "  - website: the company's official website URL\n"
    "  - contact: a named contact person/department, or a phone number, only "
    "    if it is visible in the search results\n"
    "  - email: a contact email ONLY if one appears in the search results; "
    "    otherwise leave it empty\n"
    "  - source: the search-result URL the entry came from\n"
    "If you cannot genuinely find {target} suppliers, return as many real ones "
    "as you did find. Do not list directories, comparison portals or job boards "
    "as suppliers.\n"
    "Products that must all be covered by this one list:\n{products}"
)

SHARED_WEB_CAST_INSTRUCTION = (
    "You are a sourcing analyst. Below are REAL web search results for a group "
    "of products. Build ONE shared supplier shortlist of at least {target} "
    "REAL, distinct companies that can supply these products. This SAME list "
    "will be reused for all of them, so prefer manufacturers, distributors or "
    "wholesalers that can cover the range. Base EVERY entry only on the "
    "provided results; never invent a company, website, phone number or email. "
    "Each supplier needs company_name, website, contact, email (only if present "
    "in the snippets) and source (the result URL it came from). If fewer than "
    "{target} real suppliers appear, return as many as you genuinely found. Do "
    "not list directories, comparison portals or job boards.\n\n"
    "Products: {products}\n\n"
    "Search results:\n{results}"
)

WEB_CAST_INSTRUCTION = (
    "You are a sourcing analyst. Below are REAL web search results for the "
    "product. Build a supplier shortlist of at least {target} REAL, distinct "
    "companies that manufacture, distribute or supply it. Base EVERY entry only "
    "on the provided results. Never invent a company, website, phone number or "
    "email. For each supplier return:\n"
    "  - company_name: the official company name\n"
    "  - website: the company's official website (use the matching result URL "
    "    when you can)\n"
    "  - contact: a named contact person/department, or a phone number, only "
    "    if it appears in the search results\n"
    "  - email: a contact email ONLY if one appears in the search results; "
    "    otherwise leave it empty\n"
    "  - source: the result URL the entry came from\n"
    "If fewer than {target} real suppliers appear in the results, return as "
    "many as you genuinely found. Do not list directories, comparison portals "
    "or job boards as suppliers.\n\n"
    "Product: {name}\n"
    "Description: {description}\n\n"
    "Search results:\n{results}"
)


class SupplierFinder:
    """Calls Gemini with Google-Search grounding and parses a structured list."""

    DEFAULT_MODEL = "gemini-3.8-flash"
    FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"]

    def __init__(self, model: str = None, api_key: str = None):
        if genai is None:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai"
            )
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.models = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]
        self.timeout_ms = int(os.environ.get("GEMINI_TIMEOUT_MS", "30000"))
        self._client = None

    def _get_client(self):
        if self._client is None:
            key = self.api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not set. Get a key from "
                    "https://aistudio.google.com/apikey and set it as an "
                    "environment variable."
                )
            # An explicit timeout stops an overloaded model from hanging the run
            # forever; a slow/queued call then fails fast and we move on.
            self._client = genai.Client(
                api_key=key, http_options=types.HttpOptions(timeout=self.timeout_ms)
            )
        return self._client

    def _call(self, instruction: str) -> List[Supplier]:
        """One grounded request, trying each model and retrying transient errors."""
        client = self._get_client()
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_schema=SupplierList,
            temperature=0.1,
        )
        last_err = None
        saw_quota = False
        for model in self.models:
            for attempt in range(3):
                try:
                    resp = client.models.generate_content(
                        model=model, contents=instruction, config=config
                    )
                    _note_grounding(True, model)
                    return SupplierList.model_validate_json(resp.text).suppliers
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    # Daily quota is gone; record it and move to the next model
                    # without burning backoff sleeps.
                    daily_quota = "PerDay" in msg or "current quota" in msg or "quota" in msg.lower()
                    if daily_quota:
                        saw_quota = True
                        _note_grounding(False, model, msg.splitlines()[0][:200])
                    # Grounding/search unsupported for this model -> try the next one.
                    unsupported = any(
                        key in msg
                        for key in (
                            "search tool", "grounding", "not supported",
                            "not allowed", "unsupported", "disabled", "not enabled",
                        )
                    )
                    if unsupported or daily_quota:
                        break
                    if attempt < 2:
                        time.sleep(2 ** attempt + random.uniform(0, 1))
        if saw_quota:
            raise QuotaExhaustedError(
                f"Google-Search grounding quota exhausted (429) on: {', '.join(self.models)}"
            )
        raise RuntimeError(f"Supplier search failed on all models: {last_err}")

    def _cast_suppliers(self, text: str) -> List[Supplier]:
        """Plain (non-grounded) Gemini call that parses web-search text into a list.

        One attempt per model so an overloaded model can't stall the whole run:
        the client timeout turns a hang into a fast failure and we try the next.
        """
        client = self._get_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SupplierList,
            temperature=0.1,
        )
        last_err = None
        for model in self.models:
            try:
                resp = client.models.generate_content(
                    model=model, contents=text, config=config
                )
                return SupplierList.model_validate_json(resp.text).suppliers
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Supplier list parsing failed on all models: {last_err}")

    @staticmethod
    def _dedupe(suppliers: List[Supplier]) -> List[Supplier]:
        seen, out = set(), []
        for s in suppliers:
            domain = (s.website or "").strip().lower().rstrip("/")
            name = " ".join(s.company_name.lower().split()) if s.company_name else ""
            key = domain or name or s.email.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(s)
        return out

    def find_for_item(self, item: Dict):
        """Return ``(shortlist_dicts, backend)`` for one line item (10+, deduped).

        ``backend`` is ``"search_grounding"`` when Gemini's Google-Search grounding
        worked, or ``"web_search"`` when the daily grounding quota was exhausted
        and the normal (quota-free) web-search fallback was used instead.
        """
        name = (
            (item.get("item_name") or item.get("description") or item.get("item_number") or "product")
        ).strip()
        description = (item.get("description") or "").strip()[:800]
        try:
            suppliers = self._call(
                SEARCH_INSTRUCTION.format(target=TARGET_SUPPLIERS, name=name, description=description)
            )
            backend = "search_grounding"

            # Extra passes only when the first result is under the target count.
            for _ in range(MAX_FOLLOW_UP_PASSES):
                suppliers = self._dedupe(suppliers)
                have = len([s for s in suppliers if s.company_name or s.website])
                if have >= TARGET_SUPPLIERS:
                    break
                known = " | ".join((s.company_name or s.website or "") for s in suppliers[:40]) or "none"
                extra = self._call(
                    FOLLOW_UP_INSTRUCTION.format(
                        names=known, needed=TARGET_SUPPLIERS - have, name=name, description=description
                    )
                )
                suppliers = self._dedupe(suppliers + extra)
        except QuotaExhaustedError:
            suppliers, backend = self._find_via_web(name, description)
        return self._to_dicts(suppliers), backend

    @staticmethod
    def _web_queries(name: str, description: str) -> List[str]:
        """Query variants used by the quota-free web-search fallback."""
        queries = [
            f"{name} supplier",
            f"{name} manufacturer",
            f"{name} distributor contact",
            name,
        ]
        if description:
            queries.append(f"{name} {description[:80]} supplier")
        return queries

    def _find_via_web(self, name: str, description: str):
        """Quota-free fallback: normal web search + plain Gemini parsing."""
        try:
            results = search_many(self._web_queries(name, description), per_query=8, max_total=40)
        except WebSearchUnavailable as e:
            raise RuntimeError(
                "Google-Search grounding quota is exhausted and no normal web-search "
                f"fallback is available: {e}"
            ) from e
        if not results:
            raise RuntimeError(
                "Google-Search grounding quota is exhausted and the normal web-search "
                "fallback returned no results for this product."
            )
        blob = "\n".join(
            f"- {r['title']}\n  url: {r['url']}\n  snippet: {r['snippet']}"
            for r in results
        )
        suppliers = self._cast_suppliers(
            WEB_CAST_INSTRUCTION.format(
                target=TARGET_SUPPLIERS, name=name, description=description, results=blob
            )
        )
        return self._dedupe(suppliers), "web_search"

    @staticmethod
    def _to_dicts(suppliers: List[Supplier]) -> List[Dict]:
        return [
            {
                "company_name": s.company_name.strip(),
                "website": s.website.strip(),
                "contact": s.contact.strip(),
                "email": s.email.strip(),
                "source": s.source.strip(),
            }
            for s in suppliers[:20]
            if s.company_name or s.website
        ]

    # ------------------------------------------------------------- shared list
    @staticmethod
    def _item_name(item: Dict) -> str:
        return (
            (item.get("item_name") or item.get("description") or item.get("item_number") or "product")
        ).strip()

    def find_for_all(self, items: List[Dict]):
        """Return ``(shortlist_dicts, backend)``: ONE shared list for every item.

        A single grounded search builds one supplier shortlist from all the
        products together; that SAME list is then used for every line item. On a
        grounding-quota ``429`` it falls back to the quota-free web search.
        """
        names = [self._item_name(it) for it in items if self._item_name(it)]
        listing = "\n".join(f"- {n}" for n in names) or "- the products in this tender"
        try:
            suppliers = self._call(
                SHARED_INSTRUCTION.format(target=TARGET_SUPPLIERS, products=listing)
            )
            backend = "search_grounding"
            for _ in range(MAX_FOLLOW_UP_PASSES):
                suppliers = self._dedupe(suppliers)
                have = len([s for s in suppliers if s.company_name or s.website])
                if have >= TARGET_SUPPLIERS:
                    break
                known = " | ".join((s.company_name or s.website or "") for s in suppliers[:40]) or "none"
                extra = self._call(
                    SHARED_INSTRUCTION.format(target=TARGET_SUPPLIERS, products=listing)
                    + f"\nDo not repeat these already known suppliers: {known}"
                )
                suppliers = self._dedupe(suppliers + extra)
        except QuotaExhaustedError:
            suppliers, backend = self._find_shared_via_web(names)
        return self._to_dicts(self._dedupe(suppliers)), backend

    def _find_shared_via_web(self, names: List[str]):
        """Quota-free fallback: union web results across every product, then one parse.

        Searching each product and pooling the candidates gives a shared list
        broad enough to cover all of them, parsed into a single list.
        """
        names = names[:10] or ["industrial supplier"]
        queries = []
        for n in names:
            queries += self._web_queries(n, "")
        try:
            results = search_many(queries, per_query=6, max_total=60)
        except WebSearchUnavailable as e:
            raise RuntimeError(
                "Google-Search grounding quota is exhausted and no normal web-search "
                f"fallback is available: {e}"
            ) from e
        if not results:
            raise RuntimeError(
                "Google-Search grounding quota is exhausted and the normal web-search "
                "fallback returned no results for these products."
            )
        blob = "\n".join(
            f"- {r['title']}\n  url: {r['url']}\n  snippet: {r['snippet']}"
            for r in results
        )
        suppliers = self._cast_suppliers(
            SHARED_WEB_CAST_INSTRUCTION.format(
                target=TARGET_SUPPLIERS, products="; ".join(names), results=blob
            )
        )
        return self._dedupe(suppliers), "web_search"


class SupplierManager:
    """Runs supplier discovery for a finished job in the background, persisting progress."""

    def __init__(self, finder: Optional[SupplierFinder] = None):
        self.finder = finder or SupplierFinder()
        self._lock = threading.Lock()
        self._active: Dict[str, bool] = {}

    def start(self, job_id: str, mode: str = "all") -> Optional[str]:
        """Begin background shortlisting; returns None on success or an error message.

        ``mode`` is ``"all"`` (one batched search covering every product at once)
        or ``"per_item"`` (a separate search per product).
        """
        if mode not in SUPPLIER_MODES:
            mode = "all"
        job = job_manager.get(job_id)
        if job is None:
            return "Job not found."
        if job.status != "done" or not job.data:
            return "The run must be finished before searching suppliers."
        items = job.data.get("line_items") or []
        if not items:
            return "This run has no line items to source."
        with self._lock:
            if self._active.get(job_id):
                return "Supplier search is already running."
            self._active[job_id] = True

        self._seed(job, items)
        job.data["supplier_mode"] = mode
        threading.Thread(target=self._run, args=(job_id, mode), daemon=True).start()
        return None

    @staticmethod
    def _apply(entry: Dict, found: List[Dict], backend: str) -> None:
        """Write one product's results and status onto its state entry."""
        entry["backend"] = backend or entry.get("backend") or "search_grounding"
        entry["suppliers"] = found
        entry["status"] = "done"
        used = "web search" if entry["backend"] == "web_search" else "Google grounding"
        entry["message"] = f"{len(found)} supplier(s) shortlisted via {used}"

    def _seed(self, job, items: List[Dict]) -> List[Dict]:
        """Initialise one per-product row, keeping results that are already done."""
        existing = (job.data or {}).get("suppliers") or []
        state: List[Dict] = []
        for idx, it in enumerate(items):
            prev = existing[idx] if idx < len(existing) else None
            if prev and prev.get("status") == "done":
                state.append(prev)
            else:
                state.append(
                    {
                        "item_no": it.get("item_no"),
                        "item_name": it.get("item_name") or it.get("description") or f"Item {idx + 1}",
                        "status": "pending",
                        "message": "Queued for search",
                        "backend": (prev or {}).get("backend"),
                        "suppliers": [s for s in ((prev or {}).get("suppliers") or []) if s],
                    }
                )
        job.data["suppliers"] = state
        self._persist(job)
        return state

    def _run(self, job_id: str, mode: str = "all"):
        try:
            job = job_manager.get(job_id)
            if job is None:
                return
            state = job.data.get("suppliers") or []
            items = (job.data or {}).get("line_items") or []
            if mode == "per_item":
                self._run_per_item(job, state, items)
            else:
                self._run_all(job, state, items)
            job_manager._audit(job, "supplier_search_completed", "Supplier shortlisting finished")
            self._persist(job)
        finally:
            with self._lock:
                self._active.pop(job_id, None)

    def _run_per_item(self, job, state: List[Dict], items: List[Dict]):
        """One search per product, run sequentially."""
        pending = sum(1 for s in state if s["status"] != "done")
        job_manager._audit(
            job, "supplier_search_started", f"Searching suppliers for {pending} product(s), one by one"
        )
        for idx, entry in enumerate(state):
            if entry["status"] == "done":
                continue
            entry["status"] = "searching"
            entry["message"] = "Searching Google…"
            self._persist(job)
            try:
                found = self.finder.find_for_item(items[idx] if idx < len(items) else {})
                if isinstance(found, tuple):
                    found, backend = found
                else:
                    backend = None
                self._apply(entry, found, backend)
                self._persist(job)
                job_manager._audit(
                    job, "suppliers_shortlisted",
                    f"{len(found)} supplier(s) for '{entry.get('item_name')}'",
                )
            except Exception as e:
                entry["status"] = "error"
                entry["message"] = str(e)[:200]
                self._persist(job)
                traceback.print_exc()

    def _run_all(self, job, state: List[Dict], items: List[Dict]):
        """One shared supplier list found once and applied to every product."""
        targets = [(i, e) for i, e in enumerate(state) if e["status"] != "done"]
        if not targets:
            return
        job_manager._audit(
            job, "supplier_search_started",
            f"Building one shared supplier list for {len(targets)} product(s)",
        )
        for _, entry in targets:
            entry["status"] = "searching"
            entry["message"] = "Building one shared supplier list…"
        self._persist(job)
        # Only the products still to do are sent, but the shared list is applied
        # to each of them (and the search subject covers all line items).
        try:
            result = self.finder.find_for_all(items)
            if isinstance(result, tuple):
                found, backend = result
            else:
                found, backend = result, None
            for _, entry in targets:
                self._apply(entry, found, backend)
                job_manager._audit(
                    job, "suppliers_shortlisted",
                    f"{len(found)} shared supplier(s) applied to '{entry.get('item_name')}'",
                )
        except Exception as e:
            for _, entry in targets:
                entry["status"] = "error"
                entry["message"] = str(e)[:200]
            traceback.print_exc()
        self._persist(job)

    def _persist(self, job):
        try:
            history_store.save(job)
        except Exception:
            pass

    def build_csv(self, job_id: str) -> Optional[str]:
        """Return a CSV of all shortlisted suppliers, or None when there are none."""
        job = job_manager.get(job_id)
        if job is None:
            return None
        rows = (job.data or {}).get("suppliers") or []
        if not rows:
            return None
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["item_no", "item_name", "company_name", "website", "email", "contact", "source"])
        for row in rows:
            for s in row.get("suppliers") or []:
                writer.writerow(
                    [
                        row.get("item_no") or "",
                        row.get("item_name") or "",
                        s.get("company_name") or "",
                        s.get("website") or "",
                        s.get("email") or "",
                        s.get("contact") or "",
                        s.get("source") or "",
                    ]
                )
        return out.getvalue()


supplier_finder = SupplierManager()