"""List-page pre-filter: listings that surely cannot fit are skipped before any fetch or model call."""

from datetime import UTC, datetime

from conftest import LIST_URL, LISTING_HTML

from flatjai.agent.match import quick_reject
from flatjai.schemas import Profile
from flatjai.tools.clean import html_to_text, link_texts, page_links
from flatjai.tools.fetch import Page
from flatjai.tools.preview import ListingPreview, preview_from_card

CARD = (
    "Centaline Property AI Deco & Talk Key bookmark LUNG POON COURT・Lung Bik House (Block F) Middle Floor・"
    "FLAT 12・1 Room Diamond Hill Diamond Hill 39 years · West · 74% Efficiency(%) 3 mins 3 mins S.A. S.A. "
    "340 ft² 340ft² @ $45 /ft² (Prem. paid) GFA GFA 462ft² 462ft² @ $33 /ft² (Prem. paid) Rent $ 15,500"
)


def test_card_facts_are_read():
    p = preview_from_card(CARD)
    assert p == ListingPreview(rent_hkd=15500, district="Diamond Hill", saleable_sqft=340, bedrooms=1)


def test_card_without_facts_gives_nothing():
    assert preview_from_card("Other estate") is None


def test_rent_over_budget_is_rejected_but_unknowns_never():
    p = Profile(budget_hkd_month=12000)
    assert quick_reject(ListingPreview(rent_hkd=15500), p) == "over budget"
    assert (
        quick_reject(ListingPreview(rent_hkd=11900), p) is None
    )  # utilities may still push it over: read it
    assert quick_reject(ListingPreview(), p) is None
    assert quick_reject(None, p) is None


def test_shared_and_total_budgets():
    assert quick_reject(ListingPreview(rent_hkd=15500), Profile(budget_hkd_month=9000, flatmates=1)) is None
    total = Profile(budget_hkd_month=15000, flatmates=1, budget_is_total=True)
    assert quick_reject(ListingPreview(rent_hkd=15500), total) == "over budget"


def test_far_district_rejected_only_with_a_commute_limit():
    far = ListingPreview(district="Tuen Mun")
    assert quick_reject(far, Profile(campus="HKUST", max_commute_min=40)) == "too far"
    assert quick_reject(far, Profile(campus="HKUST")) is None
    assert (
        quick_reject(ListingPreview(district="Lohas Park"), Profile(campus="HKUST", max_commute_min=40))
        is None
    )


LIST_WITH_CARDS = """<html><body>
<a href="/findproperty/en/detail/Cheap-Court_AAA111?theme=rent">CHEAP COURT 1 Room Hang Hau Hang Hau Rent $ 9,000</a>
<a href="/findproperty/en/detail/Dear-Court_BBB222?theme=rent">DEAR COURT 2 Rooms Hang Hau Hang Hau Rent $ 48,000</a>
<a href="/findproperty/en/detail/Far-Court_CCC333?theme=rent">FAR COURT 1 Room Tuen Mun Tuen Mun Rent $ 8,000</a>
<a href="/findproperty/en/detail/Mystery-Court_DDD444?theme=rent">MYSTERY COURT</a>
</body></html>"""


class CardFetcher:
    def __init__(self):
        self.urls = []

    async def fetch(self, url):
        self.urls.append(url)
        html = LISTING_HTML if "/detail/" in url else LIST_WITH_CARDS
        return Page(
            url=url,
            final_url=url,
            page_hash=url[-12:],
            title="t",
            text=html_to_text(html),
            fetched_at=datetime.now(UTC),
            http_status=200,
            links=page_links(html, url),
            link_text=link_texts(html, url),
        )


async def test_search_stage_skips_surely_failing_listings_before_reading(store):
    from test_loop import FakeSearcher, run

    fetcher = CardFetcher()
    replies = {"Profile": {"budget_hkd_month": 15000, "campus": "HKUST", "max_commute_min": 40}}
    events, state, _, _ = await run(
        store,
        replies,
        searcher=FakeSearcher([{"url": LIST_URL}]),
        fetcher=fetcher,
        brief="flat near HKUST, 15k, 40 min",
    )
    read = [u for u in fetcher.urls if "/detail/" in u]
    assert not any("Dear-Court" in u or "Far-Court" in u for u in read)  # never fetched
    assert read[0].endswith("Cheap-Court_AAA111?theme=rent")  # promising card read first
    assert state.prefiltered == 2
    assert state.skipped == {"over budget (list page)": 1, "too far (list page)": 1}


def test_suggestions_come_from_card_rents_when_everything_was_skipped():
    from flatjai.agent.match import relaxations

    p = Profile(budget_hkd_month=9000)
    assert relaxations([], p, [12000, 12500, 13000, 30000]) == [
        "Raising the rent budget to about HK$13,000 a month adds about 3 home(s)."  # 30,000 is past 1.5x
    ]
    assert relaxations([], p, [40000]) == [
        "The homes found are listed from about HK$40,000 rent a month for you."
    ]


async def test_answer_explains_when_every_home_was_skipped_early(store):
    from test_loop import FakeSearcher, run

    replies = {"Profile": {"budget_hkd_month": 5000, "campus": "HKUST", "max_commute_min": 40}}
    events, state, _, _ = await run(
        store,
        replies,
        searcher=FakeSearcher([{"url": LIST_URL}]),
        fetcher=CardFetcher(),
        brief="flat near HKUST, 5k, 40 min",
    )
    done = events[-1].data
    assert state.read_urls == [
        "https://hk.centanet.com/findproperty/en/detail/Mystery-Court_DDD444?theme=rent"
    ]
    assert done["relaxations"] and "about" in done["relaxations"][0]


def test_labelled_rent_on_a_listing_page_is_read_without_the_model():
    from flatjai.tools.preview import preview_from_page

    text = "Sell\n$4.8M\nMonthly：$14,623\nRent\n$13,500\nS.A.\n301\nft²"
    assert preview_from_page(text).rent_hkd == 13500  # the rent, not the mortgage figure
    assert preview_from_page("Monthly：$14,623") is None


async def test_over_budget_page_is_skipped_before_extraction(store):
    from conftest import LISTING_URL
    from test_loop import FakeFetcher, FakeSearcher, run

    replies = {"Profile": {"budget_hkd_month": 9000, "campus": "HKUST"}}
    _, state, fake, _ = await run(
        store,
        replies,
        searcher=FakeSearcher([{"url": LISTING_URL}]),
        fetcher=FakeFetcher(),
        brief="flat near HKUST, 9k",
    )
    names = [r["response_format"]["json_schema"]["name"] for r in fake.requests]
    assert "ListingDraft" not in names  # rent $12,800 on the page is over 9k: no model call
    assert state.skipped == {"over budget (listed rent)": 1}
