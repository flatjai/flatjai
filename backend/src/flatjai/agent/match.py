"""Stage 5, Match (code only): hard constraints, duplicates, and relaxations with real numbers.

Hard constraints are checked in code, never by the model, so "fits your budget" is always true.
A fact the listing does not state is "unknown" (ok=None): shown to the student, not a rejection.
Commute joins the checks in M3.
"""

import json
import re
from datetime import timedelta
from pathlib import Path

from ..schemas import Listing, Profile
from ..tools.cost import Cost
from ..tools.portals import portal_for
from ..tools.preview import ListingPreview
from .plan import candidate_areas
from .state import Check, Match

MOVE_IN_SLACK = timedelta(days=14)  # a home free two weeks after the wanted date still counts


def people(profile: Profile) -> int:
    return (profile.flatmates or 0) + 1


def rent_for_you(listing: Listing, profile: Profile) -> int:
    """The rent the student's budget is compared with. A student's amount is a monthly RENT budget:
    a whole flat's rent is split between the people sharing it, unless the budget is a total.
    Utilities and fees are shown as the all-in cost, never counted against the budget."""
    if listing.room_only or profile.budget_is_total:
        return listing.rent_hkd_month
    return round(listing.rent_hkd_month / people(profile))


def hard_checks(listing: Listing, cost: Cost, profile: Profile) -> list[Check]:
    checks: list[Check] = []
    if profile.budget_hkd_month is not None:
        rent = rent_for_you(listing, profile)
        split = (
            f" (HK${listing.rent_hkd_month:,} split {people(profile)} ways)"
            if rent != listing.rent_hkd_month
            else ""
        )
        kind = "total rent budget" if profile.budget_is_total else "rent budget"
        ok = rent <= profile.budget_hkd_month
        detail = f"rent HK${rent:,}/month{split}, {kind} HK${profile.budget_hkd_month:,}"
        checks.append(Check(name="budget", ok=ok, detail=detail, value=rent))
    if profile.room_only is True:
        if listing.room_only:
            checks.append(Check(name="room", ok=True, detail="room"))
        elif _rooms_site(listing):  # a student-housing site that did not say: unknown, not a whole flat
            checks.append(Check(name="room", ok=None, detail="room or whole flat not stated"))
        else:
            checks.append(Check(name="room", ok=False, detail="whole flat, not a room"))
    elif (
        listing.room_only
        and (profile.room_only is False or profile.bedrooms)
        and not (profile.bedrooms == 0 and _says_studio(listing))
    ):
        # a whole flat was asked for ("2-bedroom flat to share"): a single room cannot be it (seen live)
        checks.append(Check(name="room", ok=False, detail="a room, not a whole flat"))
    if profile.bedrooms:
        if listing.bedrooms is None:
            checks.append(Check(name="bedrooms", ok=None, detail="bedrooms not stated"))
        else:
            ok = listing.bedrooms >= profile.bedrooms
            checks.append(
                Check(
                    name="bedrooms", ok=ok, detail=f"{listing.bedrooms} bedroom(s), need {profile.bedrooms}"
                )
            )
    if area := area_check(listing, profile):
        checks.append(area)
    if profile.move_in:
        if listing.available_from is None:
            checks.append(Check(name="move_in", ok=None, detail="availability not stated"))
        else:
            ok = listing.available_from <= profile.move_in + MOVE_IN_SLACK
            checks.append(
                Check(name="move_in", ok=ok, detail=f"available from {listing.available_from:%d %b %Y}")
            )
    return checks


def area_check(listing: Listing, profile: Profile) -> Check | None:
    """Interim commute check until M3 routes real journeys: with a commute limit, a home in a known
    district outside the areas within reach of the campus fails. Missing one home is better than
    showing one 90 minutes away. Unknown district -> unknown."""
    areas = candidate_areas(profile)
    if not profile.max_commute_min or not areas:
        return None
    where = " ".join(filter(None, [listing.district, listing.title, listing.address])).lower()
    near = next((a for a in areas if a.lower() in where), None)
    if near:
        return Check(
            name="area", ok=True, detail=f"in {near}, within reach of {profile.campus or 'your areas'}"
        )
    if not listing.district:
        return Check(name="area", ok=None, detail="district not stated; commute not checked")
    target = profile.campus or ", ".join(profile.districts)
    return Check(
        name="area", ok=False, detail=f"{listing.district} is not among the areas within reach of {target}"
    )


def _norm_name(text: str | None) -> str:
    return re.sub(r"[^a-z0-9一-鿿]", "", (text or "").lower())


# Place words that sites put around an estate's name in different ways: "Tseung Kwan O · East Point
# City" on one site, "Hang Hau East Point City" on another (seen live). Station names (MTR Open Data)
# and the 18 districts, longest first so "Tseung Kwan O" goes before "Kwan".
_DISTRICTS = [
    "Central and Western",
    "Wan Chai",
    "Eastern",
    "Southern",
    "Yau Tsim Mong",
    "Sham Shui Po",
    "Kowloon City",
    "Wong Tai Sin",
    "Kwun Tong",
    "Kwai Tsing",
    "Tsuen Wan",
    "Tuen Mun",
    "Yuen Long",
    "North",
    "Tai Po",
    "Sha Tin",
    "Sai Kung",
    "Islands",
    "Hong Kong",
    "HongKong",
    "Kowloon",
    "China",
    "Clear Water Bay",
    "Sai Ying Pun",
    "Mid-Levels",
    "Po Lam",
    "Kennedy Town",
    "Pok Fu Lam",
]
_PLACE_WORDS = sorted(
    {
        _norm_name(n)
        for n in [
            *_DISTRICTS,
            *(
                s["name"]
                for s in json.loads((Path(__file__).resolve().parents[1] / "data" / "mtr.json").read_text())[
                    "stations"
                ].values()
            ),
        ]
    },
    key=len,
    reverse=True,
)


def estate_core(text: str | None) -> str:
    """The estate's own name: place words removed. Empty when nothing but places is left."""
    core = _norm_name(text)
    for word in _PLACE_WORDS:
        if word:
            core = core.replace(word, "")
    return core


def same_home(a: Listing, b: Listing) -> bool:
    """Design rule: same estate, area within 3%, rent within 5% (one flat listed by several agents).
    The estate is compared without place words, so two sites naming it differently still match;
    a name that is only places ("Hang Hau") is compared in full."""
    name_a, name_b = a.estate or a.title, b.estate or b.title
    core_a, core_b = estate_core(name_a), estate_core(name_b)
    if len(core_a) >= 4 and len(core_b) >= 4:
        if core_a != core_b:
            return False
    elif _norm_name(name_a) != _norm_name(name_b):
        return False
    if (
        a.saleable_sqft
        and b.saleable_sqft
        and abs(a.saleable_sqft - b.saleable_sqft) > 0.03 * a.saleable_sqft
    ):
        return False
    return abs(a.rent_hkd_month - b.rent_hkd_month) <= 0.05 * a.rent_hkd_month


def _says_studio(listing: Listing) -> bool:
    """A self-contained studio offered in a student residence suits a student who asked for a studio."""
    text = " ".join([listing.title, *listing.evidence.values()]).lower()
    return "studio" in text or "開放式" in text


def _rooms_site(listing: Listing) -> bool:
    portal = portal_for(str(listing.source_url))
    return bool(portal and portal.rooms)


def mark_duplicates(matches: list[Match]) -> int:
    """Mark later copies of the same home; returns how many were marked."""
    kept: list[Match] = []
    marked = 0
    for m in matches:
        if m.duplicate_of is not None:
            continue
        listing = Listing.model_validate(m.listing)
        if original := next((k for k in kept if same_home(Listing.model_validate(k.listing), listing)), None):
            m.duplicate_of = original.listing_id
            marked += 1
        else:
            kept.append(m)
    return marked


def relaxations(matches: list[Match], profile: Profile, card_rents: list[int] | None = None) -> list[str]:
    """Concrete, computed suggestions when too few homes fit: 'raising the budget to X adds N homes'.
    Read listings give exact figures; list-page rents of skipped listings give an "about" figure."""
    out: list[str] = []
    if profile.budget_hkd_month is not None:
        needed = sorted(
            c.value
            for m in matches
            if m.duplicate_of is None
            for c in m.checks
            if c.name == "budget" and c.ok is False and all(o.ok is not False for o in m.checks if o is not c)
        )
        needed = [n for n in needed if n <= 1.5 * profile.budget_hkd_month]  # useful suggestions only
        for target in sorted({needed[0], needed[min(2, len(needed) - 1)]} if needed else set()):
            adds = sum(n <= target for n in needed)
            out.append(f"Raising the rent budget to HK${_round_up(target):,} a month adds {adds} home(s).")
    if not out and card_rents and profile.budget_hkd_month:
        out += _card_relaxations(card_rents, profile)
    if profile.room_only:
        flats = [m for m in matches if not m.listing.get("room_only") and m.duplicate_of is None]
        if flats and not any(m.fits for m in matches):
            cheapest = min(m.cost["monthly_hkd"] for m in flats)
            out.append(
                f"No rooms were found on the sites FlatJai can read; the cheapest whole flat seen costs "
                f"HK${cheapest:,} a month, which could work split with flatmates."
            )
    return out


def _card_relaxations(card_rents: list[int], profile: Profile) -> list[str]:
    """From list-page rents (unverified, so "about"): the rent the budget is compared with, split
    between flatmates unless the budget is a total."""
    split = 1 if profile.budget_is_total else people(profile)
    needed = sorted(round(rent / split) for rent in card_rents)
    budget = profile.budget_hkd_month or 0
    reachable = [n for n in needed if n <= 1.5 * budget]
    if not reachable:
        return [f"The homes found are listed from about HK${_round_up(needed[0]):,} rent a month for you."]
    target = reachable[min(2, len(reachable) - 1)]
    adds = sum(n <= target for n in needed)
    return [f"Raising the rent budget to about HK${_round_up(target):,} a month adds about {adds} home(s)."]


def _round_up(n: int, step: int = 100) -> int:
    return -(-n // step) * step


def quick_reject(preview: ListingPreview | None, profile: Profile) -> str | None:
    """Skip a listing from its list-page card alone, only when it surely fails: the rent by itself
    is over the budget (rent is a floor on the monthly cost), or the card names a district out of
    reach under a commute limit. Unknowns never reject. Returns the reason, or None to read it."""
    if preview is None:
        return None
    if preview.rent_hkd and profile.budget_hkd_month:
        rent_for_you = preview.rent_hkd if profile.budget_is_total else preview.rent_hkd / people(profile)
        if rent_for_you > profile.budget_hkd_month:
            return "over budget"
    areas = candidate_areas(profile)
    if preview.district and profile.max_commute_min and areas:
        if not any(
            a.lower() in preview.district.lower() or preview.district.lower() in a.lower() for a in areas
        ):
            return "too far"
    return None


def promise(preview: ListingPreview | None, profile: Profile) -> int:
    """Read order: listings whose card shows a rent within budget first, unknown ones after."""
    if preview and preview.rent_hkd and profile.budget_hkd_month:
        return 0
    return 1


def with_commute(
    checks: list[Check], minutes: int, summary: str, profile: Profile, precision: str
) -> list[Check]:
    """The commute estimate replaces the interim area check. With a limit it is a hard check;
    an area-level location (the district, not the building) is marked as such in the detail."""
    rest = [c for c in checks if c.name != "area"]
    where = "" if precision == "building" else " (from the district; building not found)"
    detail = f"~{minutes} min to {profile.campus}: {summary}{where}"
    ok = None if profile.max_commute_min is None else minutes <= profile.max_commute_min
    if profile.max_commute_min is not None:
        detail += f", limit {profile.max_commute_min} min"
    return [*rest, Check(name="commute", ok=ok, detail=detail, value=minutes)]
