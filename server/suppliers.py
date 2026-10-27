"""Live web-search-grounded supplier shortlisting for the products in a job.

For every line item (product) a live, search-enabled AI query (Google Gemini
grounding, OpenAI web search or Anthropic web search — whichever provider the
user selected) returns REAL companies that supply it — with their website,
any contact / email that is visible in the search snippets, and the
search-result URL each entry came from. Results are stored on the job's data
payload and persisted with its history record, so they survive restarts and
appear in the audit trail.

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
from server.ai_providers import (
    ProviderClient,
    UnsupportedSearchError,
    extract_json,
    get_spec,
    is_quota_error,
    is_unsupported_search,
    resolve_model,
)
from server.history import history_store
from server.jobs import job_manager
from server.websearch import WebSearchUnavailable, search_many

TARGET_SUPPLIERS = 5
MAX_FOLLOW_UP_PASSES = 1
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


class QuotaExhaustedError(RuntimeError):
    """The provider's live-search quota is exhausted; use the web fallback."""


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
    "You are a sourcing analyst using live web search to build a supplier "
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
    "You are still using live web search. I already have these suppliers: "
    "{names}. Find {needed} ADDITIONAL real, distinct companies that supply "
    "this product but are NOT in that list. Base every entry on actual search "
    "results; never invent data.\n"
    "Product: {name}\n"
    "Context / description: {description}"
)

SHARED_INSTRUCTION = (
    "You are a sourcing analyst using live web search. Find ONE shared "
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
    """Runs live search-enabled supplier queries on the chosen AI provider.

    The provider's own web-search tool is used (Gemini Google-Search grounding,
    OpenAI web search, Anthropic web search). When the live search quota is
    exhausted or the provider has no search tool, callers fall back to the
    quota-free DuckDuckGo search + plain model parsing.
    """

    DEFAULT_MODEL = get_spec("gemini").default_model
    FALLBACK_MODELS = list(get_spec("gemini").fallback_models)

    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        spec = get_spec(provider)
        self.provider = spec.id
        self.label = spec.label
        self.api_key = api_key
        self.model = resolve_model(spec.id, model)
        self.models = [self.model] + [m for m in spec.fallback_models if m != self.model]
        self.timeout_ms = int(
            os.environ.get(f"{spec.env_prefix}_TIMEOUT_MS", str(spec.search_timeout_ms))
        )
        self._client: Optional[ProviderClient] = None

    def _get_client(self) -> ProviderClient:
        if self._client is None:
            self._client = ProviderClient(
                self.provider, api_key=self.api_key, model=self.model,
                timeout_ms=self.timeout_ms,
            )
        return self._client

    def _call(self, instruction: str) -> List[Supplier]:
        """One live-search request, trying each model and retrying transient errors.

        Daily-quota errors skip straight to the next model without backoff;
        once every model is exhausted the caller falls back to normal web search.
        """
        client = self._get_client()
        last_err = None
        saw_quota = False
        saw_unsupported = False
        for model in self.models:
            for attempt in range(3):
                try:
                    text = client.search_json(
                        instruction, schema=SupplierList, temperature=0.1, model=model
                    )
                    _note_grounding(True, model)
                    return extract_json(text, SupplierList).suppliers
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    if isinstance(e, UnsupportedSearchError) or is_unsupported_search(msg):
                        saw_unsupported = True
                        break
                    if is_quota_error(msg):
                        saw_quota = True
                        _note_grounding(False, model, msg.splitlines()[0][:200])
                        break
                    if attempt < 2:
                        time.sleep(2 ** attempt + random.uniform(0, 1))
        if saw_quota:
            raise QuotaExhaustedError(
                f"Live-search quota exhausted on {self.label}: {', '.join(self.models)}"
            )
        if saw_unsupported:
            raise UnsupportedSearchError(
                f"{self.label} live web search is not available on: {', '.join(self.models)}"
            )
        raise RuntimeError(f"Supplier search failed on all models: {last_err}")

    def _cast_suppliers(self, text: str) -> List[Supplier]:
        """Plain (non-searched) call that parses web-search text into a list.

        One attempt per model so an overloaded model can't stall the whole run:
        the client timeout turns a hang into a fast failure and we try the next.
        """
        client = self._get_client()
        last_err = None
        for model in self.models:
            try:
                out = client.generate_json(
                    [text], schema=SupplierList, system=None, temperature=0.1, model=model
                )
                return extract_json(out, SupplierList).suppliers
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

        ``backend`` is ``"search_grounding"`` when the provider's live web
        search worked, or ``"web_search"`` when the live-search quota was
        exhausted (or unsupported) and the normal (quota-free) web-search
        fallback was used instead.
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
                if have >= 3:
                    break
                known = " | ".join((s.company_name or s.website or "") for s in suppliers[:40]) or "none"
                extra = self._call(
                    FOLLOW_UP_INSTRUCTION.format(
                        names=known, needed=TARGET_SUPPLIERS - have, name=name, description=description
                    )
                )
                suppliers = self._dedupe(suppliers + extra)
        except (QuotaExhaustedError, UnsupportedSearchError):
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
        """Quota-free fallback: normal web search + plain model parsing."""
        try:
            results = search_many(self._web_queries(name, description), per_query=8, max_total=40)
        except WebSearchUnavailable as e:
            raise RuntimeError(
                "Live AI search is unavailable and no normal web-search "
                f"fallback is available: {e}"
            ) from e
        if not results:
            raise RuntimeError(
                "Live AI search is unavailable and the normal web-search "
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

        A single live search builds one supplier shortlist from all the
        products together; that SAME list is then used for every line item.
        On a live-search quota error (or missing search tool) it falls back to
        the quota-free web search.
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
                if have >= 3:
                    break
                known = " | ".join((s.company_name or s.website or "") for s in suppliers[:40]) or "none"
                extra = self._call(
                    SHARED_INSTRUCTION.format(target=TARGET_SUPPLIERS, products=listing)
                    + f"\nDo not repeat these already known suppliers: {known}"
                )
                suppliers = self._dedupe(suppliers + extra)
        except (QuotaExhaustedError, UnsupportedSearchError):
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
                "Live AI search is unavailable and no normal web-search "
                f"fallback is available: {e}"
            ) from e
        if not results:
            raise RuntimeError(
                "Live AI search is unavailable and the normal web-search "
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

    def start(self, job_id: str, mode: str = "all", api_key: Optional[str] = None,
              provider: Optional[str] = None, model: Optional[str] = None) -> Optional[str]:
        """Begin background shortlisting; returns None on success or an error message.

        ``mode`` is ``"all"`` (one batched search covering every product at once)
        or ``"per_item"`` (a separate search per product). ``provider``/``model``
        pick the AI provider used for the live search — the user's chosen one,
        or Gemini when the supplier-search setting is pinned to Gemini.
        ``api_key`` is the caller's own key for that provider when they have
        set one, else the server env key.
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
        try:
            finder = SupplierFinder(provider=provider, model=model, api_key=api_key)
        except Exception as e:
            return str(e)
        with self._lock:
            if self._active.get(job_id):
                return "Supplier search is already running."
            self._active[job_id] = True

        self._seed(job, items)
        job.data["supplier_mode"] = mode
        threading.Thread(target=self._run, args=(job_id, mode, finder), daemon=True).start()
        return None

    @staticmethod
    def _apply(entry: Dict, found: List[Dict], backend: str) -> None:
        """Write one product's results and status onto its state entry."""
        entry["backend"] = backend or entry.get("backend") or "search_grounding"
        entry["suppliers"] = found
        entry["status"] = "done"
        used = "web search" if entry["backend"] == "web_search" else "live AI search"
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

    def _run(self, job_id: str, mode: str = "all", finder: Optional["SupplierFinder"] = None):
        finder = finder or self.finder
        try:
            job = job_manager.get(job_id)
            if job is None:
                return
            state = job.data.get("suppliers") or []
            items = (job.data or {}).get("line_items") or []
            if mode == "per_item":
                self._run_per_item(job, state, items, finder)
            else:
                self._run_all(job, state, items, finder)
            job_manager._audit(job, "supplier_search_completed", "Supplier shortlisting finished")
            self._persist(job)
        finally:
            with self._lock:
                self._active.pop(job_id, None)

    def _run_per_item(self, job, state: List[Dict], items: List[Dict],
                      finder: Optional["SupplierFinder"] = None):
        """One search per product, run sequentially."""
        finder = finder or self.finder
        pending = sum(1 for s in state if s["status"] != "done")
        job_manager._audit(
            job, "supplier_search_started", f"Searching suppliers for {pending} product(s), one by one"
        )
        for idx, entry in enumerate(state):
            if entry["status"] == "done":
                continue
            entry["status"] = "searching"
            entry["message"] = "Searching the web…"
            self._persist(job)
            try:
                found = finder.find_for_item(items[idx] if idx < len(items) else {})
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

    def _run_all(self, job, state: List[Dict], items: List[Dict],
                 finder: Optional["SupplierFinder"] = None):
        """One shared supplier list found once and applied to every product."""
        finder = finder or self.finder
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
            result = finder.find_for_all(items)
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