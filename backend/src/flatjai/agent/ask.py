"""What to ask the agent: for a home that fits, the questions its listing leaves open, and a message.

Every "?" check and every unstated detail that matters to this student becomes one question. The
questions come from code, from facts known to be missing, so the message never asserts anything the
listing did not say. FlatJai never sends it: the student copies it to WhatsApp or email.
"""

from pydantic import BaseModel

from ..schemas import Listing, Profile
from .state import Check

PORTAL_NAMES = {"centaline": "Centaline", "uhomes": "uhomes", "amber": "Amber Student"}


class Ask(BaseModel):
    questions: list[str]
    message: str


def questions_for(listing: Listing, checks: list[Check], profile: Profile) -> list[str]:
    unknown = {c.name for c in checks if c.ok is None}
    asks: list[str] = []
    if "move_in" in unknown and profile.move_in:
        asks.append(f"Is it available from {profile.move_in:%-d %B %Y}?")
    if "room" in unknown:
        asks.append("Is this a private room, or the whole flat?")
    if listing.room_only and listing.bathroom is None:
        asks.append("Is the bathroom private or shared?")
    if listing.room_only:
        asks.append("How many people share the flat?")
    if "bedrooms" in unknown:
        asks.append("How many bedrooms does it have?")
    if listing.lease_months is None:
        want = f" I'm hoping for {profile.lease_months} months." if profile.lease_months else ""
        asks.append(f"What is the minimum lease?{want}")
    if not listing.room_only and listing.mgmt_fee_included is None:
        asks.append("Is the management fee included in the rent?")
    if listing.portal == "centaline" and listing.agent_fee == "unknown":
        asks.append("What is the agent commission?")
    if "commute" in unknown or not any(c.name == "commute" for c in checks):
        if profile.campus:
            asks.append(f"How do residents usually get to {profile.campus}, and how long does it take?")
    for wish in profile.soft_preferences:
        asks.append(f"Is it {wish}?" if " " not in wish else f"Can you tell me about: {wish}?")
    return asks


def ask_for(listing: Listing, checks: list[Check], profile: Profile) -> Ask:
    questions = questions_for(listing, checks, profile)
    where = PORTAL_NAMES.get(listing.portal, listing.portal)
    lines = [
        f"Hi, I saw {listing.title} on {where} at HK${listing.rent_hkd_month:,} a month ({listing.source_url}).",
        "Could you tell me:" if questions else "Is it still available?",
        *(f"{i}. {q}" for i, q in enumerate(questions, start=1)),
        "Thank you!",
    ]
    return Ask(questions=questions, message="\n".join(lines))
