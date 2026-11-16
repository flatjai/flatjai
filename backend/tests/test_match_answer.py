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


def test_budget_is_a_rent_budget():
    c = checks(Profile(budget_hkd_month=12000))["budget"]
    assert c.ok is True and c.value == 12000  # rent 12,000; utilities are not counted against it
    assert checks(Profile(budget_hkd_month=11999))["budget"].ok is False


def test_whole_flat_rent_is_split_between_flatmates():
    c = checks(Profile(budget_hkd_month=7000, flatmates=1))["budget"]
    assert c.ok is True and c.value == 6000 and "split 2 ways" in c.detail


def test_total_budget_is_compared_with_the_whole_rent():
    c = checks(Profile(budget_hkd_month=11000, flatmates=1, budget_is_total=True))["budget"]
    assert c.ok is False and c.value == 12000


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
        "Raising the rent budget to HK$11,000 a month adds 1 home(s).",
        "Raising the rent budget to HK$15,000 a month adds 3 home(s).",
    ]  # 15,000 is exactly 1.5x the budget: the furthest suggestion still offered


def test_no_rooms_found_suggests_sharing_a_flat():
    p = Profile(room_only=True)
    out = relaxations([match(1, p)], p)
    assert "No rooms" in out[0] and "HK$12,600" in out[0]  # the cheapest flat's all-in cost


FACTS = {
    "id": 7,
    "title": "Test Court",
    "district": "Hang Hau",
    "rent_hkd": 12000,
    "monthly_all_in_hkd": 12600,
    "rent_for_you_hkd": 6000,
    "move_in_cost_hkd": 42000,
    "saleable_sqft": 400,
    "gross_sqft": None,
    "bedrooms": 2,
    "furnished": None,
    "available_from": None,
    "commute_min_estimate": 22,
}
PROFILE = Profile(budget_hkd_month=7000, flatmates=1)


def test_claims_with_real_numbers_are_supported():
    allowed = allowed_numbers(FACTS, PROFILE)
    assert supported("HK$6,000 rent a month for you, HK$1,000 under budget", allowed)
    assert supported("HK$12,600 a month all in, about 22 minutes to campus", allowed)
    assert supported("400 ft² saleable, 2 bedrooms", allowed)
    assert supported("Quiet estate with a gym", allowed)


def test_invented_numbers_are_caught():
    allowed = allowed_numbers(FACTS, PROFILE)
    assert not supported("Only 5 minutes from the MTR at HK$5,900", allowed)
    assert not supported("Rent is HK$11,000", allowed)
    assert not supported("HK$6,300 a month for you", allowed)  # an all-in share is not a fact
    assert not supported("12.5% cheaper than average", allowed)
    assert not supported("Only 5 minutes from the MTR", allowed)
    assert not supported("3 km to campus", allowed)


def test_code_reasons_are_always_supported():
    assert all(supported(r, allowed_numbers(FACTS, PROFILE)) for r in code_reasons(FACTS, PROFILE))


def test_total_budget_reasons_are_supported():
    p = Profile(budget_hkd_month=13000, flatmates=1, budget_is_total=True)
    f = FACTS | {"rent_for_you_hkd": 12000}
    reasons = code_reasons(f, p)
    assert reasons[0] == "HK$12,000 rent a month in total, HK$1,000 under budget"
    assert reasons[1] == "about 22 minutes to campus"
    FACTS_TOTAL = f
    assert all(supported(r, allowed_numbers(FACTS_TOTAL, p)) for r in reasons)


def test_area_check_until_real_commutes():
    p = Profile(campus="HKUST", max_commute_min=40)
    assert checks(p, district="Hang Hau")["area"].ok is True
    assert checks(p, district="Tuen Mun")["area"].ok is False
    assert checks(p)["area"].ok is None  # district not stated
    assert "area" not in checks(Profile(campus="HKUST"), district="Tuen Mun")  # no commute limit given


def test_total_budget_compares_the_whole_rent_never_a_share():
    from flatjai.agent.answer import facts

    p = Profile(budget_hkd_month=30000, flatmates=1, budget_is_total=True)
    m = match(1, p, rent_hkd_month=19000)
    f = facts(m, p)
    assert f["rent_for_you_hkd"] == 19000 and f["monthly_all_in_hkd"] == 19600  # the whole rent, no share
    assert not supported("Monthly share is HK$9,800, under your budget of HK$30,000", allowed_numbers(f, p))


def test_budget_claims_must_compare_the_rent():
    from flatjai.agent.answer import fair_claim

    p = Profile(budget_hkd_month=15000, flatmates=1)
    f = FACTS | {"rent_hkd": 19000, "rent_for_you_hkd": 9500, "monthly_all_in_hkd": 19600}
    assert not fair_claim("Monthly all-in cost is HK$19,600, under your budget of HK$15,000", f, p)
    assert fair_claim("HK$9,500 rent a month for you, HK$5,500 under your budget", f, p)
    assert fair_claim("About HK$19,600 a month all in", f, p)  # no budget claim: other checks apply

    assert not fair_claim("Rent_for_you_hkd is HK$9,500, within your HK$15,000 budget", f, p)


def test_preference_claims_must_match_what_the_student_named():
    from flatjai.agent.answer import fair_claim

    p = Profile(budget_hkd_month=15000, districts=["Diamond Hill", "Choi Hung"], soft_preferences=["quiet"])
    tko = FACTS | {"district": "Tseung Kwan O"}
    assert not fair_claim("It's in Tseung Kwan O, which is one of your preferred districts.", tko, p)
    assert fair_claim(
        "It's in Diamond Hill, one of your preferred areas.", FACTS | {"district": "Diamond Hill"}, p
    )
    assert fair_claim("A quiet estate, as you preferred.", tko, p)
