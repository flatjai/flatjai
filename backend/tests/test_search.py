import httpx
import pytest
from conftest import LIST_HTML, LIST_URL, LISTING_URL

from flatjai.tools.portals import portal_for
from flatjai.tools.search import Searcher, SearchError, expand_list, portal_results

RAW = [
    {"url": LIST_URL, "title": "Hang Hau rentals"},
    {"url": LISTING_URL, "title": "Test Court", "content": "Rent $12,800"},
    {"url": LISTING_URL + "#photos", "title": "duplicate"},
    {"url": "https://www.28hse.com/en/rent/residential/property-1", "title": "blocked portal"},
    {"url": "https://hk.centanet.com/estate/en/Some-Estate/2-XYZ", "title": "estate guide"},
    {"url": "https://news.example.com/hang-hau", "title": "news"},
]


def test_keeps_listing_and_list_pages_on_allowed_portals_only():
    results = portal_results(RAW)
    assert [(r.kind, r.url) for r in results] == [("list", LIST_URL), ("listing", LISTING_URL)]
    assert results[1].portal == "centaline" and results[1].snippet == "Rent $12,800"


def test_blocked_portals_are_known_but_not_allowed():
    assert portal_for("https://www.28hse.com/x").allowed is False
    assert portal_for("https://unknown.example.com/") is None


async def test_searcher_restricts_to_portal_and_asks_for_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"results": RAW})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        results = await Searcher(http, "http://searx").search("Hang Hau flat", portal=portal_for(LISTING_URL))
    assert seen["q"] == "Hang Hau flat site:hk.centanet.com" and seen["format"] == "json"
    assert len(results) == 2


async def test_searcher_errors_are_typed():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(502))) as http:
        with pytest.raises(SearchError):
            await Searcher(http, "http://searx").search("x")


class _Page:
    links = [
        "https://hk.centanet.com/findproperty/en/detail/Test-Court-Block-1_ABC123?theme=rent",
        "https://hk.centanet.com/estate/en/Some-Estate/2-XYZ",
    ]


class _Fetcher:
    async def fetch(self, url):
        assert url == LIST_URL
        return _Page()


async def test_expand_list_keeps_listing_links():
    results = await expand_list(_Fetcher(), LIST_URL)
    assert [r.url for r in results] == [_Page.links[0]] and results[0].kind == "listing"
    assert "detail" in LIST_HTML  # fixture sanity
