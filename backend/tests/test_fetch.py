"""Fetch tool against a fake web (httpx.MockTransport) and a fake clock: no network, no waiting."""

import hashlib

import httpx
import pytest
from conftest import LISTING_HTML, LISTING_URL

from flatjai.storage.blobs import BlobStore
from flatjai.tools.fetch import FetchBlocked, Fetcher, FetchError

ROBOTS_OK = "User-agent: *\nDisallow: /private\n"


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.now += s


def site(pages: dict[str, tuple[int, str, str]]):
    """pages: path -> (status, content type, body). Unknown paths answer 404."""
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.url.path)
        assert request.headers["user-agent"].startswith("FlatJai/")
        status, ctype, body = pages.get(request.url.path, (404, "text/html", "not found"))
        return httpx.Response(status, headers={"content-type": ctype}, text=body)

    return handler, hits


def fetcher(tmp_path, handler, clock=None):
    clock = clock or FakeClock()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    f = Fetcher(http, BlobStore(tmp_path), "FlatJai/test", min_interval_s=2.0, clock=clock, sleep=clock.sleep)
    return f, clock


PATH = "/findproperty/en/detail/Test-Court-Block-1_ABC123"


async def test_fetch_cleans_text_and_stores_raw_page_by_hash(tmp_path):
    handler, _ = site({"/robots.txt": (200, "text/plain", ROBOTS_OK), PATH: (200, "text/html", LISTING_HTML)})
    f, _ = fetcher(tmp_path, handler)
    page = await f.fetch(LISTING_URL)
    assert page.page_hash == hashlib.sha256(LISTING_HTML.encode()).hexdigest()
    assert BlobStore(tmp_path).get(page.page_hash) == LISTING_HTML.encode()
    assert "$12,800" in page.text and "<span>" not in page.text


async def test_second_request_to_same_domain_waits_two_seconds(tmp_path):
    handler, hits = site(
        {"/robots.txt": (200, "text/plain", ROBOTS_OK), PATH: (200, "text/html", LISTING_HTML)}
    )
    f, clock = fetcher(tmp_path, handler)
    await f.fetch(LISTING_URL)
    await f.fetch(LISTING_URL)
    assert hits == ["/robots.txt", PATH, PATH]  # robots.txt read once per domain
    assert clock.slept == [2.0, 2.0]  # after robots.txt, after the first page


async def test_robots_crawl_delay_wins_when_longer(tmp_path):
    handler, _ = site(
        {
            "/robots.txt": (200, "text/plain", "User-agent: *\nCrawl-delay: 5\n"),
            PATH: (200, "text/html", "<p>x</p>"),
        }
    )
    f, clock = fetcher(tmp_path, handler)
    await f.fetch(LISTING_URL)
    assert clock.slept == [5.0]


async def test_robots_disallow_is_obeyed(tmp_path):
    handler, hits = site({"/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /findproperty/\n")})
    f, _ = fetcher(tmp_path, handler)
    with pytest.raises(FetchBlocked, match="robots"):
        await f.fetch(LISTING_URL)
    assert hits == ["/robots.txt"]


async def test_unreadable_robots_means_stay_out(tmp_path):
    handler, hits = site({"/robots.txt": (403, "text/html", "challenge")})
    f, _ = fetcher(tmp_path, handler)
    with pytest.raises(FetchBlocked):
        await f.fetch(LISTING_URL)
    assert hits == ["/robots.txt"]


async def test_missing_robots_allows_everything(tmp_path):
    handler, _ = site({PATH: (200, "text/html", LISTING_HTML)})
    f, _ = fetcher(tmp_path, handler)
    assert (await f.fetch(LISTING_URL)).http_status == 200


@pytest.mark.parametrize(
    "status,body",
    [(403, "denied"), (200, "<html><title>28hse challenge page</title></html>")],
)
async def test_bot_challenges_are_blocked_not_retried(tmp_path, status, body):
    handler, hits = site({"/robots.txt": (200, "text/plain", ROBOTS_OK), PATH: (status, "text/html", body)})
    f, _ = fetcher(tmp_path, handler)
    with pytest.raises(FetchBlocked):
        await f.fetch(LISTING_URL)
    assert hits.count(PATH) == 1


async def test_gone_listing_is_a_fetch_error(tmp_path):
    handler, _ = site({"/robots.txt": (200, "text/plain", ROBOTS_OK)})
    f, _ = fetcher(tmp_path, handler)
    with pytest.raises(FetchError, match="404"):
        await f.fetch(LISTING_URL)
