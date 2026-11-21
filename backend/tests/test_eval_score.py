"""The evaluation scorer (eval/score.py) checks homes with its own code; these pin its rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))

from score import ablation_mismatches, check_home, duplicate_homes, number_on_page, score_case  # noqa: E402


def test_numbers_are_found_as_written_on_the_page():
    page = "Rent HK$9,000 /month · 實用 420 呎 · 月租 1.5萬"
    assert number_on_page(9000, page) and number_on_page(420, page) and number_on_page(15000, page)
    assert not number_on_page(900, page)  # part of 9,000 is not 900
    assert not number_on_page(8000, page)


def test_limits_are_ok_violated_or_unknown():
    truth = {"budget": 9000, "room": "room", "commute_max": 40}
    assert check_home({"rent_hkd_month": 8500, "room_only": True, "commute_min": 22}, truth) == {
        "budget": True,
        "room": True,
        "commute": True,
    }
    got = check_home({"rent_hkd_month": 9500, "room_only": None, "commute_min": None}, truth)
    assert got == {"budget": False, "room": None, "commute": None}
    assert check_home({"rent_hkd_month": 1, "room_only": False}, {"budget": 9, "room": "room"})["room"]
    assert not check_home({"rent_hkd_month": 1, "room_only": True}, {"budget": 9, "room": "flat"})["room"]


def home(**kw):
    base = {
        "source_url": "https://x.hk/a",
        "rent_hkd_month": 8000,
        "saleable_sqft": None,
        "gross_sqft": None,
        "room_only": True,
        "commute_min": 20,
        "monthly_hkd": 8600,
        "move_in_hkd": 24000,
    }
    return {**base, **kw}


def row(homes, summary="", asked=None, relaxations=()):
    turn = {
        "asked": asked,
        "profile": None,
        "homes": homes,
        "summary": summary,
        "relaxations": list(relaxations),
        "usage": None,
        "error": None,
    }
    return {
        "case": "std-hkust-own-room-9k",
        "category": "standard",
        "system": "x",
        "repeat": 0,
        "wall_s": 1.0,
        "turns": [turn],
    }


def test_a_listing_missing_from_the_snapshot_is_invented_and_its_rent_unsupported():
    s = score_case(row([home()]), pages={})
    assert s["invented_listings"] == 1 and s["facts"] == 1 and s["supported"] == 0


def test_summary_figures_must_come_from_the_cards_or_the_budget():
    pages = {"https://x.hk/a": "Rent $8,000"}
    ok = score_case(row([home()], "HK$8,000 a month, HK$1,000 under your HK$9,000 budget, 20 min"), pages)
    assert ok["summary_figures"] == 4 and ok["summary_supported"] == 4
    bad = score_case(row([home()], "only HK$7,200 a month"), pages)
    assert bad["summary_supported"] == 0


def test_commute_limit_is_judged_on_the_router_minutes():
    truth = {"budget": 9000, "commute_max": 30}
    # model_facts ablation: the model claimed 15 min, the router found 45
    assert (
        check_home({"rent_hkd_month": 8000, "commute_min": 15, "tool_commute_min": 45}, truth)["commute"]
        is False
    )
    assert check_home({"rent_hkd_month": 8000, "commute_min": 25}, truth)["commute"] is True


def test_duplicates_are_the_same_page_or_same_rent_and_building():
    a = {"source_url": "u1", "title": "Tseung Kwan O · East Point City", "rent_hkd_month": 4800}
    b = {"source_url": "u2", "title": "Hang Hau · East Point City Tower 3", "rent_hkd_month": 4800}
    c = {"source_url": "u3", "title": "Hang Hau · Park Central", "rent_hkd_month": 4800}
    d = {"source_url": "u4", "title": "Hung Hom · Mangrove", "rent_hkd_month": 17500, "saleable_sqft": 250}
    e = {"source_url": "u5", "title": "Hung Hom · BAKERVIEW", "rent_hkd_month": 17500, "saleable_sqft": 335}
    assert duplicate_homes([a, b]) == 1
    assert duplicate_homes([a, c]) == 0  # same rent, another building
    assert duplicate_homes([d, e]) == 0  # same district and rent is not the same home
    assert duplicate_homes([a, {**a}]) == 1  # the same page twice


def test_rows_labelled_with_an_ablation_must_have_run_with_it():
    rows = [
        {"system": "flatjai", "case": "a"},
        {"system": "b1", "case": "a"},
        {"system": "flatjai-no_reflect", "case": "a", "ablate": ["no_reflect"]},
        {"system": "flatjai-no_dedup", "case": "b"},  # recorded before runs stored their ablation
        {"system": "flatjai-model_facts", "case": "c", "ablate": []},  # the cached-settings bug
    ]
    assert ablation_mismatches(rows) == ["flatjai-model_facts/c", "flatjai-no_dedup/b"]
