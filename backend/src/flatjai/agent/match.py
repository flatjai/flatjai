"""Stage 5, Match (code only): hard constraints, duplicates, and relaxations with real numbers.

Hard constraints are checked in code, never by the model, so "fits your budget" is always true.
A fact the listing does not state is "unknown" (ok=None): shown to the student, not a rejection.
Commute joins the checks in M3.
"""

import re
from datetime import timedelta

from ..schemas import Listing, Profile
from ..tools.cost import UTILITIES_HKD_MONTH, Cost
from ..tools.preview import ListingPreview
from .plan import candidate_areas
from .state import Check, Match

MOVE_IN_SLACK = timedelta(days=14)  # a home free two weeks after the wanted date still counts


def people(profile: Profile) -> int:
    return (profile.flatmates or 0) + 1


def your_share(cost: Cost, listing: Listing, profile: Profile) -> int:
    """Monthly cost for the student: a whole flat is split between the people sharing it."""
    if listing.room_only:
        return cost.monthly_hkd
    return round(cost.monthly_hkd / people(profile))


def hard_checks(listing: Listing, cost: Cost, profile: Profile) -> list[Check]:
    checks: list[Check] = []
    if profile.budget_hkd_month is not None and profile.budget_is_total:
        # household budget: compare the whole flat's cost
        ok = cost.monthly_hkd <= profile.budget_hkd_month
        detail = f"HK${cost.monthly_hkd:,}/month all in, total budget HK${profile.budget_hkd_month:,}"
        checks.append(Check(name="budget", ok=ok, detail=detail, value=cost.monthly_hkd))
    elif profile.budget_hkd_month is not None:
        share = your_share(cost, listing, profile)
        split = (
            f" (HK${cost.monthly_hkd:,} split {people(profile)} ways)" if share != cost.monthly_hkd else ""
        )
        ok = share <= profile.budget_hkd_month
        detail = f"HK${share:,}/month all in{split}, budget HK${profile.budget_hkd_month:,}"
        checks.append(Check(name="budget", ok=ok, detail=detail, value=share))
    if profile.room_only is True:
        checks.append(
            Check(
                name="room",
                ok=listing.room_only,
                detail="room" if listing.room_only else "whole flat, not a room",
            )
        )
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


def same_home(a: Listing, b: Listing) -> bool:
    """Design rule: same estate, area within 3%, rent within 5% (one flat listed by several agents)."""
    if _norm_name(a.estate or a.title) != _norm_name(b.estate or b.title):
        return False
    if (
        a.saleable_sqft
        and b.saleable_sqft
        and abs(a.saleable_sqft - b.saleable_sqft) > 0.03 * a.saleable_sqft
    ):
        return False
    return abs(a.rent_hkd_month - b.rent_hkd_month) <= 0.05 * a.rent_hkd_month


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
            out.append(f"Raising the budget to HK${_round_up(target):,} a month adds {adds} home(s).")
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
    """From list-page rents (unverified, so "about"): the monthly figure the budget is compared with,
    rent plus estimated utilities, split between flatmates unless the budget is a total."""
    split = 1 if profile.budget_is_total else people(profile)
    needed = sorted(round((rent + UTILITIES_HKD_MONTH) / split) for rent in card_rents)
    budget = profile.budget_hkd_month or 0
    reachable = [n for n in needed if n <= 1.5 * budget]
    if not reachable:
        return [f"The homes found are listed from about HK${_round_up(needed[0]):,} a month for you."]
    target = reachable[min(2, len(reachable) - 1)]
    adds = sum(n <= target for n in needed)
    return [f"Raising the budget to about HK${_round_up(target):,} a month adds about {adds} home(s)."]


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

