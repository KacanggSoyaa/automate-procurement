"""Normal web search as a quota-free fallback for supplier discovery.

Used when Gemini's Google-Search grounding daily quota is exhausted, so the
pipeline can keep finding suppliers. Two engines, preferred in order:

1. Google Programmable Search Engine (official, real Google results) when
   GOOGLE_CSE_KEY and GOOGLE_CSE_ID are both set in the environment.
   Free tier = 100 queries/day, entirely separate from the Gemini quota.
2. DuckDuckGo via the ``ddgs`` package - no API key, no daily quota.

Both return a normalized list of ``{title, url, snippet}`` dicts.
"""
import os
import urllib.parse
import urllib.request

from server import netfix  # noqa: F401  (IPv4-first DNS for outbound HTTPS)

try:
    from ddgs import DDGS
except Exception:  # pragma: no cover - ddgs is an optional dependency
    DDGS = None


class WebSearchUnavailable(Exception):
    """Raised when neither fallback engine can be used right now."""


def _google_cse(query: str, n: int) -> list:
    """Official Google search via the Programmable Search JSON API."""
    key = os.environ.get("GOOGLE_CSE_KEY")
    cx = os.environ.get("GOOGLE_CSE_ID")
    if not key or not cx:
        raise WebSearchUnavailable(
            "Google Custom Search not configured: set GOOGLE_CSE_KEY and GOOGLE_CSE_ID"
        )
    n = min(n, 10)
    url = (
        "https://www.googleapis.com/customsearch/v1?key="
        + urllib.parse.quote(key, safe="")
        + "&cx=" + urllib.parse.quote(cx, safe="")
        + "&q=" + urllib.parse.quote(query)
        + "&num=" + str(n)
    )
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = __import__("json").loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise WebSearchUnavailable(f"Google Custom Search request failed: {e}") from e
    return [
        {
            "title": (it.get("title") or "").strip(),
            "url": (it.get("link") or "").strip(),
            "snippet": (it.get("snippet") or "").strip(),
        }
        for it in data.get("items") or []
    ]


def _duckduckgo(query: str, n: int) -> list:
    """DuckDuckGo text search via ddgs (no API key needed)."""
    if DDGS is None:
        raise WebSearchUnavailable(
            "DuckDuckGo fallback needs the 'ddgs' package. Run: pip install ddgs"
        )
    try:
        with DDGS(timeout=20) as ddgs:
            results = list(ddgs.text(query, max_results=n, safesearch="moderate"))
    except Exception as e:
        raise WebSearchUnavailable(f"DuckDuckGo search failed: {e}") from e
    out = []
    for it in results or []:
        title = (it.get("title") or "").strip()
        url = (it.get("href") or it.get("url") or "").strip()
        if not title or not url:
            continue
        out.append(
            {
                "title": title,
                "url": url,
                "snippet": (it.get("body") or "").strip(),
            }
        )
    return out


def search(query: str, n: int = 10) -> list:
    """One query over the best available engine."""
    try:
        return _google_cse(query, n)
    except WebSearchUnavailable:
        pass
    return _duckduckgo(query, n)


def search_many(queries: list, per_query: int = 8, max_total: int = 40) -> list:
    """Run several queries, dedupe by URL, stop once max_total results are in."""
    seen, out = set(), []
    for q in queries:
        try:
            results = search(q, n=per_query)
        except WebSearchUnavailable:
            continue
        for r in results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                out.append(r)
                if len(out) >= max_total:
                    return out
    return out


def engine_available() -> str:
    """Human label of the engine that will be used (for diagnostics only)."""
    if os.environ.get("GOOGLE_CSE_KEY") and os.environ.get("GOOGLE_CSE_ID"):
        return "Google Custom Search"
    if DDGS is None:
        return "none (install ddgs)"
    return "DuckDuckGo"