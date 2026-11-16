"""What to ask the agent: questions come from what the listing leaves open, never from guesses."""

from datetime import date

from flatjai.agent.ask import ask_for, questions_for
from flatjai.agent.state import Check
from flatjai.schemas import Listing, Profile

URL = "https://en.uhomes.com/hk/hongkong/detail-apartments-1579208"


def listing(**kw) -> Listing:
    base = {"source_url": URL, "portal": "uhomes", "title": "Hang Hau Metro City", "rent_hkd_month": 7700}
    return Listing(**(base | kw))


def test_unknowns_become_questions():
    p = Profile(campus="HKUST", move_in=date(2027, 1, 1), lease_months=12, soft_preferences=["quiet"])
    checks = [
        Check(name="move_in", ok=None, detail="availability not stated"),
        Check(name="commute", ok=True, detail="~17 min"),
    ]
    qs = questions_for(listing(room_only=True), checks, p)
    assert "Is it available from 1 January 2027?" in qs
    assert "Is the bathroom private or shared?" in qs
    assert "What is the minimum lease? I'm hoping for 12 months." in qs
    assert "Is it quiet?" in qs
    assert not any("get to HKUST" in q for q in qs)  # the commute is known


def test_known_facts_are_not_asked():
    p = Profile(campus="HKUST")
    known = listing(room_only=True, bathroom="shared", lease_months=12)
    qs = questions_for(known, [Check(name="commute", ok=True, detail="~17 min")], p)
    assert not any("bathroom" in q or "lease" in q for q in qs)


def test_message_names_the_home_and_numbers_the_questions():
    ask = ask_for(listing(room_only=True), [], Profile(campus="HKUST"))
    assert ask.message.startswith("Hi, I saw Hang Hau Metro City on uhomes at HK$7,700 a month")
    assert "1. " in ask.message and ask.message.endswith("Thank you!")
