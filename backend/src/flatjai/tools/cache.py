"""Cache wrappers around tools. Every hit or miss is recorded on the tool span.

Page cache: a URL fetched within `max_age` (24 h) is served from Postgres + the blob store, with no
network request. That keeps portal load low and makes repeated runs (and development) fast.

Search cache: results for the same query + site are reused for 6 h. Free search engines throttle
repeated queries (Brave "too many requests", DuckDuckGo CAPTCHA), so when a live search fails or
comes back empty, an older cached answer is served instead ("stale"): portal area pages rarely move.

Offline (FJ_OFFLINE=1, the frozen snapshot used by the evaluation): nothing touches the network.
A page is served from the cache whatever its age, and a page never seen raises FetchError. A search
is served from the cache whatever its age; a query never seen gets the cached results of the most
similar query for the same site (most shared words), since the model words its queries a little
differently each run. No similar query: no results.
"""

from datetime import UTC, datetime, timedelta

from ..storage.blobs import BlobStore
from ..storage.store import Store
from ..tracing import span
from .clean import link_texts, page_links
from .fetch import Fetcher, FetchError, Page
from .portals import Portal
from .preview import ListingPreview
from .search import Searcher, SearchError, SearchResult, portal_results

PAGE_MAX_AGE = timedelta(hours=24)
FOREVER = timedelta(days=36500)
SEARCH_MAX_AGE = timedelta(hours=6)


class CachedFetcher:
    def __init__(
        self,
        fetcher: Fetcher | None,
        store: Store,
        blobs: BlobStore,
        max_age: timedelta = PAGE_MAX_AGE,
        offline: bool = False,
    ):
        self.fetcher, self.store, self.blobs = fetcher, store, blobs
        self.offline, self.max_age = offline, FOREVER if offline else max_age

    async def fetch(self, url: str) -> Page:
        row = await self.store.fresh_page(url, self.max_age, datetime.now(UTC))
        if row is not None and self.blobs.has(row.page_hash):
            async with span("fetch", "tool", url=url, cache="hit", page_hash=row.page_hash):
                html = self.blobs.get(row.page_hash).decode("utf-8", errors="replace")
                return Page(
                    url=url,
                    final_url=row.final_url,
                    page_hash=row.page_hash,
                    title=row.title,
                    text=row.text,
                    fetched_at=row.fetched_at,
                    http_status=row.http_status,
                    links=page_links(html, row.final_url),
                    link_text=link_texts(html, row.final_url),
                )
        if self.offline or self.fetcher is None:
            async with span("fetch", "tool", url=url, cache="miss-offline"):
                raise FetchError(f"{url}: not in the snapshot (offline)")
        page = await self.fetcher.fetch(url)
        await self.store.put_page(
            page_hash=page.page_hash,
            url=url,
            final_url=page.final_url,
            title=page.title,
            text=page.text,
            http_status=page.http_status,
            fetched_at=page.fetched_at,
        )
        return page


class CachedSearcher:
    def __init__(
        self,
        searcher: Searcher | None,
        store: Store,
        max_age: timedelta = SEARCH_MAX_AGE,
        offline: bool = False,
    ):
        self.searcher, self.store = searcher, store
        self.offline, self.max_age = offline, FOREVER if offline else max_age

    async def search(self, query: str, portal: Portal | None = None, lang: str = "en") -> list[SearchResult]:
        key = f"{lang}|{portal.name if portal else '*'}|{' '.join(query.lower().split())}"
        row = await self.store.cache_get("search", key)
        if row is not None and _age(row.stored_at) <= self.max_age:
            async with span("search", "tool", query=query, cache="hit", results=len(row.value)):
                return _refiltered(row.value)
        if self.offline or self.searcher is None:
            return await self._nearest(key)
        try:
            results = await self.searcher.search(query, portal=portal, lang=lang)
        except SearchError:
            if row is None:
                raise
            results = []
        if results:
            await self.store.cache_put("search", key, [r.model_dump() for r in results])
            return results
        if row is not None and row.value:
            async with span("search", "tool", query=query, cache="stale", results=len(row.value)):
                return _refiltered(row.value)
        return results

    async def _nearest(self, key: str) -> list[SearchResult]:
        prefix, _, query = key.rpartition("|")
        words = set(query.split())
        best, best_score = None, 0.0
        for row in await self.store.cache_rows("search", prefix + "|"):
            other = set(row.key.rpartition("|")[2].split())
            score = len(words & other) / max(len(words | other), 1)
            if row.value and score > best_score:
                best, best_score = row, score
        async with span(
            "search",
            "tool",
            query=query,
            cache="nearest" if best else "miss-offline",
            nearest=best.key if best else None,
            similarity=round(best_score, 2),
        ):
            return _refiltered(best.value) if best is not None and best_score >= 0.3 else []


def _refiltered(cached: list[dict]) -> list[SearchResult]:
    """Cached results pass today's filters: results stored before a rule existed (Amber listings in
    Orlando, before the Hong Kong filter) must not come back from the cache (seen live)."""
    raw = [{"url": r["url"], "title": r.get("title", ""), "content": r.get("snippet", "")} for r in cached]
    previews = {r["url"]: r.get("preview") for r in cached}
    kept = portal_results(raw)
    for r in kept:
        if previews.get(r.url):
            r.preview = ListingPreview.model_validate(previews[r.url])
    return kept


def _age(stored_at: datetime) -> timedelta:
    if stored_at.tzinfo is None:  # SQLite returns naive datetimes; values are stored in UTC
        stored_at = stored_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - stored_at
