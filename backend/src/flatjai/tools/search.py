"""Search tool: query (+ portal) -> [SearchResult] via a self-hosted SearXNG (free, no API key).

Results are filtered to pages on portals we are allowed to read, and classified:
- kind="listing": one home (read it with fetch + extract)
- kind="list":    a portal page listing many homes in an area or estate (expand it into listings)
Anything else (news, estate guides, blocked sites) is dropped before a fetch is spent on it.
"""

import re
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel

from ..tracing import span
from .portals import Portal, portal_for
from .preview import ListingPreview, preview_from_card

_HONG_KONG = re.compile(r"hong[\s-]?kong|hongkong|香港|kowloon|new territories")


class SearchResult(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    portal: str
    kind: Literal["listing", "list"]
    preview: ListingPreview | None = None  # what the list page said about it (unverified)


class SearchError(Exception):
    pass


class Searcher:
    def __init__(self, http: httpx.AsyncClient, searxng_url: str) -> None:
        self.http, self.base = http, searxng_url.rstrip("/")

    async def search(self, query: str, portal: Portal | None = None, lang: str = "en") -> list[SearchResult]:
        q = f"{query} site:{portal.domains[0]}" if portal else query
        async with span("search", "tool", query=q) as sp:
            results = await self._search(q, lang)
            sp.attrs |= {"results": len(results), "urls": [r.url for r in results[:10]]}
            return results

    async def _search(self, q: str, lang: str) -> list[SearchResult]:
        try:
            resp = await self.http.get(
                f"{self.base}/search", params={"q": q, "format": "json", "language": lang}, timeout=8.0
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SearchError(f"SearXNG at {self.base} failed: {type(e).__name__}: {e}") from e
        return portal_results(resp.json().get("results", []))


def portal_results(raw: list[dict]) -> list[SearchResult]:
    """Keep listing and list pages on allowed portals, in rank order, without duplicates."""
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in raw:
        url = r.get("url", "").split("#")[0]
        p = portal_for(url)
        if not p or not p.allowed or url in seen:
            continue
        kind = "listing" if p.is_listing(url) else "list" if p.is_list(url) else None
        if kind is None:
            continue
        said = f"{url} {r.get('title', '')} {r.get('content', '')}".lower()
        if p.worldwide and (r.get("title") or r.get("content")) and not _HONG_KONG.search(said):
            continue  # a web result from a worldwide site about another city (Orlando, Boston: seen live)
        seen.add(url)
        out.append(
            SearchResult(
                url=url, title=r.get("title", ""), snippet=r.get("content", ""), portal=p.name, kind=kind
            )
        )
    return out


class _PageSource(Protocol):
    async def fetch(self, url: str): ...


async def expand_list(fetcher: _PageSource, url: str) -> list[SearchResult]:
    """Fetch a portal list page and return the single-listing links on it."""
    page = await fetcher.fetch(url)
    texts = getattr(page, "link_text", {}) or {}
    # a link's card text is its title: on a worldwide site the Hong Kong filter then applies to it too
    raw = [{"url": u, "title": texts.get(u, "")} for u in page.links]
    results = [r for r in portal_results(raw) if r.kind == "listing"]
    for r in results:
        if card := texts.get(r.url):
            r.preview = preview_from_card(card)
    return results
