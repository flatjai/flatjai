"""The evaluation scorer (eval/score.py) checks homes with its own code; these pin its rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))

from score import check_home, number_on_page, score_case  # noqa: E402


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
