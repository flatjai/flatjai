"""Fetch tool: url -> Page (page_hash, cleaned text, fetched_at).

Polite by construction:
- robots.txt is read once per domain and obeyed (an unreadable or blocked robots.txt counts as "no").
- At most one request per `min_interval_s` per domain (robots crawl-delay wins if longer).
- The user agent names the project.
- Bot challenges (HTTP 403/429/503, challenge pages) raise FetchBlocked; we never retry around them.
Raw bytes go to the blob store under their SHA-256, which is the page_hash.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import BaseModel

from ..storage.blobs import BlobStore
from ..tracing import span
from .clean import html_to_text, page_links, page_title

BLOCK_STATUSES = {401, 403, 429, 503}
CHALLENGE_MARKERS = ("challenge page", "just a moment...", "attention required", "cf-chl")


class Page(BaseModel):
    url: str
    final_url: str
    page_hash: str
    title: str
    text: str
    fetched_at: datetime
    http_status: int
    links: list[str] = []


class FetchError(Exception):
    """The page could not be fetched (network, HTTP error, not HTML)."""


class FetchBlocked(FetchError):
    """robots.txt disallows the URL, or the site answered with a bot challenge."""


@dataclass
class _Domain:
    lock: asyncio.Lock
    robots: RobotFileParser | None = None
    last_request: float | None = None  # monotonic time of the previous request


class Fetcher:
    def __init__(
        self,
        http: httpx.AsyncClient,
        blobs: BlobStore,
        user_agent: str,
        min_interval_s: float = 2.0,
        max_chars: int | None = None,
        clock=time.monotonic,
        sleep=asyncio.sleep,
    ) -> None:
        self.http, self.blobs, self.user_agent = http, blobs, user_agent
        self.min_interval_s, self.max_chars = min_interval_s, max_chars
        self._clock, self._sleep = clock, sleep
        self._domains: dict[str, _Domain] = {}

    async def fetch(self, url: str) -> Page:
        async with span("fetch", "tool", url=url) as sp:
            page = await self._fetch(url)
            sp.attrs |= {"status": page.http_status, "page_hash": page.page_hash, "chars": len(page.text)}
            return page

    async def _fetch(self, url: str) -> Page:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        dom = self._domains.setdefault(origin, _Domain(lock=asyncio.Lock()))
        async with dom.lock:  # serialises requests to one domain; other domains run in parallel
            if dom.robots is None:
                dom.robots = await self._load_robots(origin, dom)
            if not dom.robots.can_fetch(self.user_agent, url):
                raise FetchBlocked(f"robots.txt disallows {url}")
            resp = await self._polite_get(url, dom)

        if resp.status_code in BLOCK_STATUSES or _looks_like_challenge(resp.text):
            raise FetchBlocked(f"{url} answered with a bot challenge (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            raise FetchError(f"{url}: HTTP {resp.status_code}")
        if "html" not in resp.headers.get("content-type", "html"):
            raise FetchError(f"{url}: not an HTML page ({resp.headers.get('content-type')})")

        page_hash = self.blobs.put(resp.content)
        return Page(
            url=url,
            final_url=str(resp.url),
            page_hash=page_hash,
            title=page_title(resp.text),
            text=html_to_text(resp.text, self.max_chars),
            fetched_at=datetime.now(UTC),
            http_status=resp.status_code,
            links=page_links(resp.text, str(resp.url)),
        )

    async def _polite_get(self, url: str, dom: _Domain) -> httpx.Response:
        if dom.last_request is not None:
            wait = dom.last_request + self._delay(dom) - self._clock()
            if wait > 0:
                await self._sleep(wait)
        try:
            return await self.http.get(url, headers={"User-Agent": self.user_agent}, follow_redirects=True)
        except httpx.HTTPError as e:
            raise FetchError(f"{url}: {type(e).__name__}: {e}") from e
        finally:
            dom.last_request = self._clock()

    def _delay(self, dom: _Domain) -> float:
        crawl_delay = dom.robots.crawl_delay(self.user_agent) if dom.robots else None
        return max(self.min_interval_s, float(crawl_delay or 0))

    async def _load_robots(self, origin: str, dom: _Domain) -> RobotFileParser:
        rp = RobotFileParser()
        try:
            resp = await self._polite_get(f"{origin}/robots.txt", dom)
        except FetchError:
            rp.parse(["User-agent: *", "Disallow: /"])  # cannot read the rules: stay out
            return rp
        if resp.status_code == 404:
            rp.parse([])  # no robots.txt: everything allowed
        elif resp.status_code >= 400 or "text/plain" not in resp.headers.get("content-type", ""):
            rp.parse(["User-agent: *", "Disallow: /"])  # challenge or error page: stay out
        else:
            rp.parse(resp.text.splitlines())
        return rp


def _looks_like_challenge(html: str) -> bool:
    head = html[:4000].lower()
    return any(m in head for m in CHALLENGE_MARKERS)
