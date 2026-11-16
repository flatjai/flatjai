"""Student-housing sites (uhomes, Amber): URLs, card and page rents, room fields, sold-out pages."""

import pytest
from conftest import make_model

from flatjai.agent.verify import Unsupported, verify_listing
from flatjai.schemas import Listing, Profile
from flatjai.tools.portals import portal_for
from flatjai.tools.preview import preview_from_card, preview_from_page

UHOMES = "https://en.uhomes.com/hk/hongkong/detail-apartments-1579208"
AMBER = "https://amberstudent.com/places/hkust-mansion-student-apartment-hongkong-2605047097905"


def test_listing_and_list_urls_are_recognised():
    assert portal_for(UHOMES).is_listing(UHOMES) and portal_for(UHOMES).rooms
    assert portal_for(AMBER).is_listing(AMBER)
    assert not portal_for(AMBER).is_listing(AMBER.replace("/places/", "/fr/places/"))  # same home in French
    assert portal_for("https://en.uhomes.com/hk/hongkong").is_list("https://en.uhomes.com/hk/hongkong")
    assert portal_for("https://www.expat.com/x").allowed is False


def test_room_site_cards_and_pages():
    card = "Qingyangju Phase 1 392-394, Pai Tau Estate, Sha Tin, Hong Kong(China) 4.70 mi walk ... From HK$6,800 /month"
    p = preview_from_card(card)
    assert p.district == "Sha Tin" and p.rent_hkd == 6800
    page = "Luxury room From: HK$8,580/month ... Deluxe Single Room From: HK$7,380/month ... Ensuite HK$11,580/month"
    assert preview_from_page(page).rent_hkd == 7380  # the cheapest room, so it is never skipped wrongly


def room(**kw) -> Listing:
    base = {"source_url": UHOMES, "portal": "uhomes", "title": "Hang Hau Apartment", "rent_hkd_month": 7300}
    return Listing(**(base | kw))


PAGE = "Hang Hau Apartment\nPrivate Room\nShared Bathroom\nDuration (1): 12 month\nHK$7,300\n/month\nMonthly：$14,623"


def test_a_monthly_room_price_is_a_rent_but_a_mortgage_is_not():
    ok = room(evidence={"rent_hkd_month": "HK$7,300 /month"})
    assert verify_listing(ok, PAGE).listing.rent_hkd_month == 7300
    with pytest.raises(Unsupported):
        verify_listing(room(rent_hkd_month=14623, evidence={"rent_hkd_month": "Monthly：$14,623"}), PAGE)


def test_room_fields_need_their_evidence():
    v = verify_listing(
        room(
            room_only=True,
            bathroom="shared",
            lease_months=12,
            evidence={
                "rent_hkd_month": "HK$7,300 /month",
                "room_only": "Private Room",
                "bathroom": "Shared Bathroom",
                "lease_months": "Duration (1): 12 month",
            },
        ),
        PAGE,
    )
    assert v.dropped == [] and v.listing.bathroom == "shared" and v.listing.lease_months == 12
    v2 = verify_listing(
        room(lease_months=6, evidence={"rent_hkd_month": "HK$7,300 /month", "lease_months": "6 months"}), PAGE
    )
    assert v2.listing.lease_months is None and v2.dropped == ["lease_months"]


async def test_sold_out_page_is_skipped():
    from datetime import UTC, datetime

    from flatjai.tools.extract import SoldOut, extract_listing
    from flatjai.tools.fetch import Page

    draft = {"is_rental_listing": True, "title": "HKUST Mansion", "rent_hkd_month": 7380, "sold_out": True}
    mc, _ = make_model({"ListingDraft": draft})
    page = Page(
        url=AMBER,
        final_url=AMBER,
        page_hash="h",
        title="t",
        text="Sold out HK$7,380/month",
        fetched_at=datetime.now(UTC),
        http_status=200,
    )
    with pytest.raises(SoldOut):
        await extract_listing(mc, page, "amber")


async def test_room_sites_are_read_first_for_a_room_brief(store):
    from conftest import LIST_URL
    from test_loop import FakeFetcher, FakeSearcher, run

    fetcher = FakeFetcher()
    replies = {"Profile": {"budget_hkd_month": 9000, "campus": "HKUST", "room_only": True}}
    await run(
        store,
        replies,
        searcher=FakeSearcher([{"url": LIST_URL}]),
        fetcher=fetcher,
        brief="own room near HKUST, 9k",
    )
    browsed = [
        u
        for u in fetcher.urls
        if u
        in (
            "https://en.uhomes.com/hk/hongkong",
            "https://amberstudent.com/places/search/hong-kong-china-2602036575849",
        )
    ]
    assert browsed and fetcher.urls.index(browsed[0]) < fetcher.urls.index(LIST_URL)
    assert Profile(room_only=True).room_only


async def test_rent_the_model_left_out_is_read_from_the_page():
    from datetime import UTC, datetime

    from flatjai.tools.extract import extract_listing
    from flatjai.tools.fetch import Page

    draft = {
        "is_rental_listing": True,
        "title": "Hang Hau Apartment",
        "rent_hkd_month": None,
        "room_only": True,
        "evidence": {"room_only": "Private Room"},
    }
    mc, _ = make_model({"ListingDraft": draft})
    text = "Rooms\n4B\nHK$8,200\n/month\n2A\nHK$7,700\n/month\nPrivate Room"
    page = Page(
        url=UHOMES,
        final_url=UHOMES,
        page_hash="h",
        title="t",
        text=text,
        fetched_at=datetime.now(UTC),
        http_status=200,
    )
    listing = await extract_listing(mc, page, "uhomes")
    assert listing.rent_hkd_month == 7700 and listing.evidence["rent_hkd_month"] == "HK$7,700 /month"
    assert verify_listing(listing, text).listing.rent_hkd_month == 7700


def test_an_unstated_room_type_on_a_student_site_is_unknown():
    from flatjai.agent.match import hard_checks
    from flatjai.tools.cost import cost

    p = Profile(room_only=True)
    on_uhomes = room()
    assert {c.name: c.ok for c in hard_checks(on_uhomes, cost(on_uhomes), p)}["room"] is None
    centaline = room(source_url="https://hk.centanet.com/findproperty/en/detail/X_ABC123", portal="centaline")
    assert {c.name: c.ok for c in hard_checks(centaline, cost(centaline), p)}["room"] is False


def test_worldwide_sites_keep_hong_kong_results_only():
    from flatjai.tools.search import portal_results

    raw = [
        {
            "url": "https://amberstudent.com/places/the-rook-orlando-2608063813595",
            "title": "The Rook, Orlando",
        },
        {
            "url": "https://amberstudent.com/places/dwell-prince-edward-2605288317489",
            "title": "Dwell Prince Edward, Hong Kong",
        },
        {"url": "https://amberstudent.com/places/dwell-mong-kok-2605288317490"},  # from a list page: kept
    ]
    assert [r.url.rsplit("/", 1)[1] for r in portal_results(raw)] == [
        "dwell-prince-edward-2605288317489",
        "dwell-mong-kok-2605288317490",
    ]


def test_site_boilerplate_is_cleaned_from_titles_and_geocode_names():
    from flatjai.agent.read import geocode_name
    from flatjai.tools.extract import tidy_title

    assert tidy_title("Hang Hau Metro City · Hong Kong(China) Student Accommodation") == "Hang Hau Metro City"
    assert (
        tidy_title("Dwell Ho Man Tin, Hong Kong · Student Housing · Amber") == "Dwell Ho Man Tin, Hong Kong"
    )
    named = room(title="Hang Hau · RESIDENCE OASIS・Tower 2", district="Hang Hau")
    assert geocode_name(named) == "RESIDENCE OASIS"
    assert geocode_name(room(title="Hang Hau Metro City", district="Hang Hau")) == "Hang Hau Metro City"
