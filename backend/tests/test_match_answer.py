"""Match (hard checks, duplicates, relaxations) and the Answer stage's claim checking: pure code."""

from datetime import date

from flatjai.agent.answer import allowed_numbers, code_reasons, supported
from flatjai.agent.match import hard_checks, mark_duplicates, relaxations, same_home
from flatjai.agent.state import Match
from flatjai.schemas import Listing, Profile
from flatjai.tools.cost import cost

URL = "https://hk.centanet.com/findproperty/en/detail/X_ABC123"


def listing(**kw) -> Listing:
    base = {"source_url": URL, "portal": "centaline", "title": "Test Court", "rent_hkd_month": 12000}
    return Listing(**(base | kw))


def checks(profile: Profile, **kw):
    li = listing(**kw)
    return {c.name: c for c in hard_checks(li, cost(li), profile)}


def test_budget_uses_all_in_monthly_cost():
    c = checks(Profile(budget_hkd_month=12500))["budget"]
    assert c.ok is False and c.value == 12600  # rent 12,000 + utilities 600


def test_whole_flat_is_split_between_flatmates():
    c = checks(Profile(budget_hkd_month=7000, flatmates=1))["budget"]
    assert c.ok is True and c.value == 6300 and "split 2 ways" in c.detail


def test_total_budget_is_compared_with_the_whole_flat():
    c = checks(Profile(budget_hkd_month=12000, flatmates=1, budget_is_total=True))["budget"]
    assert c.ok is False and c.value == 12600


def test_room_wanted_rejects_whole_flat():
    assert checks(Profile(room_only=True))["room"].ok is False
    assert checks(Profile(room_only=True), room_only=True)["room"].ok is True


def test_unstated_facts_are_unknown_not_rejections():
    c = checks(Profile(bedrooms=2, move_in=date(2027, 1, 1)))
    assert c["bedrooms"].ok is None and c["move_in"].ok is None


def test_move_in_allows_two_weeks_slack():
    p = Profile(move_in=date(2027, 1, 1))
    assert checks(p, available_from=date(2027, 1, 10))["move_in"].ok is True
    assert checks(p, available_from=date(2027, 2, 1))["move_in"].ok is False


def match(i: int, profile: Profile, **kw) -> Match:
    li = listing(**kw)
    c = cost(li)
    return Match(
        listing_id=i,
        listing=li.model_dump(mode="json"),
        cost=c.model_dump(),
        checks=hard_checks(li, c, profile),
        fetched_at="2026-11-16T00:00:00+00:00",
    )


def test_same_flat_from_two_agents_is_one_home():
    assert same_home(listing(saleable_sqft=400), listing(saleable_sqft=410, rent_hkd_month=12300))
    assert not same_home(listing(saleable_sqft=400), listing(saleable_sqft=500))
    p = Profile()
    ms = [match(1, p, saleable_sqft=400), match(2, p, saleable_sqft=405), match(3, p, title="Other")]
    assert mark_duplicates(ms) == 1 and ms[1].duplicate_of == 1 and not ms[1].fits


def test_relaxation_numbers_are_computed():
    p = Profile(budget_hkd_month=10000)
    ms = [
        match(1, p, rent_hkd_month=11000),
        match(2, p, rent_hkd_month=12000, title="B"),
        match(3, p, rent_hkd_month=15000, title="C"),
    ]
    assert relaxations(ms, p) == [
        "Raising the budget to HK$11,600 a month adds 1 home(s).",
        "Raising the budget to HK$12,600 a month adds 2 home(s).",
    ]  # HK$15,600 is more than 1.5x the budget: not suggested


def test_no_rooms_found_suggests_sharing_a_flat():
    p = Profile(room_only=True)
    out = relaxations([match(1, p)], p)
    assert "No rooms" in out[0] and "HK$12,600" in out[0]


FACTS = {
    "id": 7,
    "title": "Test Court",
    "district": "Hang Hau",
    "rent_hkd": 12000,
    "monthly_all_in_hkd": 12600,
    "your_monthly_share_hkd": 6300,
    "move_in_cost_hkd": 42000,
    "saleable_sqft": 400,
    "gross_sqft": None,
    "bedrooms": 2,
    "furnished": None,
    "available_from": None,
}
PROFILE = Profile(budget_hkd_month=7000, flatmates=1)


def test_claims_with_real_numbers_are_supported():
    allowed = allowed_numbers(FACTS, PROFILE)
    assert supported("HK$6,300 a month for you, HK$700 under budget", allowed)
    assert supported("400 ft² saleable, 2 bedrooms", allowed)
    assert supported("Quiet estate with a gym", allowed)


def test_invented_numbers_are_caught():
    allowed = allowed_numbers(FACTS, PROFILE)
    assert not supported("Only 5 minutes from the MTR at HK$5,900", allowed)
    assert not supported("Rent is HK$11,000", allowed)
    assert not supported("12.5% cheaper than average", allowed)
    assert not supported("Only 5 minutes from the MTR", allowed)
    assert not supported("3 km to campus", allowed)


def test_code_reasons_are_always_supported():
    assert all(supported(r, allowed_numbers(FACTS, PROFILE)) for r in code_reasons(FACTS, PROFILE))


def test_total_budget_reasons_are_supported():
    p = Profile(budget_hkd_month=13000, flatmates=1, budget_is_total=True)
    reasons = code_reasons(FACTS, p)
    assert reasons[0] == "HK$12,600 a month all in, HK$400 under your total budget"
    assert all(supported(r, allowed_numbers(FACTS, p)) for r in reasons)


def test_area_check_until_real_commutes():
    p = Profile(campus="HKUST", max_commute_min=40)
    assert checks(p, district="Hang Hau")["area"].ok is True
    assert checks(p, district="Tuen Mun")["area"].ok is False
    assert checks(p)["area"].ok is None  # district not stated
    assert "area" not in checks(Profile(campus="HKUST"), district="Tuen Mun")  # no commute limit given
