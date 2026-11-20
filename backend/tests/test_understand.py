from flatjai.agent.understand import ground_profile, merge, numbers_in
from flatjai.schemas import Profile


def test_numbers_the_student_wrote():
    assert {9000} <= numbers_in("max 9k a month")
    assert {9000} <= numbers_in("HK$9,000")
    assert {15000} <= numbers_in("1.5萬以內")
    assert {8000} <= numbers_in("每月八千以內")


def test_invented_budget_is_cleared():
    assert ground_profile(Profile(budget_hkd_month=3000), "cheap room please").budget_hkd_month is None
    assert ground_profile(Profile(budget_hkd_month=9000), "own room, 9k max").budget_hkd_month == 9000


def test_commute_limit_written_by_the_student_is_kept():
    brief = "2-bedroom flat, 30k total, under 40 min to HKUST"
    assert ground_profile(Profile(), brief).max_commute_min == 40
    assert ground_profile(Profile(max_commute_min=30), brief).max_commute_min is None  # not what they wrote
    assert ground_profile(Profile(max_commute_min=30), "no time given").max_commute_min == 30


def test_follow_up_keeps_earlier_fields():
    before = Profile(budget_hkd_month=9000, campus="HKUST", soft_preferences=["quiet"])
    after = merge(before, Profile(budget_hkd_month=8000))
    assert after.budget_hkd_month == 8000 and after.campus == "HKUST" and after.soft_preferences == ["quiet"]


def test_budget_the_model_dropped_is_filled_from_the_text():
    p = ground_profile(Profile(campus="HKUST"), "HKUST, 30k in total, under 40 minutes")
    assert p.budget_hkd_month == 30000 and p.budget_is_total and p.max_commute_min == 40
    assert ground_profile(Profile(), "between 8k and 10k").budget_hkd_month is None  # ambiguous: leave it


def test_a_studio_is_a_whole_small_flat_not_a_room():
    p = ground_profile(Profile(room_only=True), "Studio near HKU, up to 15k")
    assert p.room_only is False and p.bedrooms == 0
    assert ground_profile(Profile(room_only=True), "own room near HKU").room_only is True


def test_placeholder_answers_are_not_offered():
    from flatjai.agent.understand import tidy_suggestions

    assert tidy_suggestions(["HKUST", "HKU", "PolyU", "None"]) == ["HKUST", "HKU", "PolyU"]
    assert tidy_suggestions(["N/A", "Other", "HKUST, HK$9,000"]) == ["HKUST, HK$9,000"]


def test_a_campus_the_student_named_is_never_lost():
    """Seen live: "near Hang Hau, HKUST" came back with no campus, so FlatJai asked which one."""
    brief = "2-bedroom flat to share with a friend, 30k total, near Hang Hau, HKUST, move in February"
    assert ground_profile(Profile(), brief).campus == "HKUST"
    assert (
        ground_profile(Profile(), "a 2bhk near hong kong university of science & technology").campus
        == "HKUST"
    )
    assert ground_profile(Profile(), "room near The Chinese University of Hong Kong").campus == "CUHK"
    assert ground_profile(Profile(), "studio near the University of Hong Kong").campus == "HKU"
    assert (
        ground_profile(Profile(), "between HKU and CityU").campus is None
    )  # two named: leave it to the model
    assert ground_profile(Profile(campus="PolyU"), "cheaper please").campus == "PolyU"  # never cleared


def test_campuses_written_next_to_chinese_are_found_and_win_over_the_model():
    # seen live: "CUHK附近" gave districts ["CUHK"] and no campus; 港大 was read as HKUST
    p = ground_profile(
        Profile(districts=["CUHK"], budget_hkd_month=6500), "CUHK附近 own room, 每月6500以下, 40 min 內"
    )
    assert p.campus == "CUHK" and p.districts == []
    p = ground_profile(
        Profile(campus="HKUST", budget_hkd_month=15000), "想租港大附近嘅開放式單位, budget 15k"
    )
    assert p.campus == "HKU"
    # "ust" inside a word is not HKUST
    assert ground_profile(Profile(), "just a room in Sha Tin").campus is None


def test_a_flat_brief_is_a_whole_flat_even_if_the_model_says_room():
    # seen live: "1-bedroom flat for one" parsed as room_only true on one run of three
    p = ground_profile(
        Profile(room_only=True, bedrooms=1), "1-bedroom flat for one, PolyU, up to 18k a month"
    )
    assert p.room_only is False
    p = ground_profile(Profile(room_only=True), "Own room in a shared flat near HKU, 8k")
    assert p.room_only is True  # a room in a flat is still a room
