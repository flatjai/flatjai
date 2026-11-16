"""Stage 7, Answer: rank the homes that fit and explain why, with every claim checked.

The model orders the shortlist and writes short reasons (typed call `explain`), using the student's
soft preferences. Code then checks the claims: a reason or summary that contains a number which is
not one of that home's facts (or the student's own figures) is dropped. If the call fails or runs
out of time, a code ranking (cheapest share first) with code-written reasons is used instead, so a
run always ends with an answer. When nothing fits, the answer says so and lists the computed
relaxations; it never invents a home.
"""

import asyncio
import re

from pydantic import BaseModel, Field

from ..model_client import BudgetExhausted
from ..schemas import Listing, Profile
from ..tracing import span
from .context import RunContext
from .match import rent_for_you
from .state import Match, RunState, Stage

_FIELD_NAME = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b", re.I)
_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|min|minute|km|m\b|metre|meter|hour|hr|分鐘|公里)?", re.I)
SMALL_COUNTS = set(range(0, 11))  # "2 bedrooms", "3 homes": fine without a matching fact


class Pick(BaseModel):
    id: int = Field(description="The home's id from the list")
    reasons: list[str] = Field(
        max_length=3,
        description="1 to 3 short reasons this home suits the student, using only the facts given",
    )


class Shortlist(BaseModel):
    picks: list[Pick] = Field(max_length=5, description="Best first, at most 5")
    summary: str = Field(description="Two sentences for the student about the shortlist")


SYSTEM = """You present a shortlist of Hong Kong homes to a student, speaking to them as "you".
All homes given already meet their hard limits. Order them best first for this student, weighing
their soft preferences and value for money, and give 1-3 short reasons for each.
Only state facts that appear in the home's data. Write money as HK$ with commas, e.g. HK$9,600.
The student's budget is a monthly RENT budget: compare it only with rent_for_you_hkd ("your rent" or
"your share of the rent"), never with the all-in cost. Never write the data's field names. Call a district "preferred" only if
the student named it.
If a preference cannot be checked from the data (e.g. "quiet"), do not claim it.
The summary is two short sentences to the student. Reply with JSON only."""


def facts(m: Match, profile: Profile) -> dict:
    listing = Listing.model_validate(m.listing)
    return {
        "id": m.listing_id,
        "title": listing.title,
        "district": listing.district,
        "rent_hkd": listing.rent_hkd_month,
        "monthly_all_in_hkd": m.cost["monthly_hkd"],
        # the rent the student's budget is compared with: their share of a shared flat's rent, or the
        # whole rent for a total budget (so a share is never set against a total budget)
        "rent_for_you_hkd": rent_for_you(listing, profile),
        "move_in_cost_hkd": m.cost["move_in_hkd"],
        "saleable_sqft": listing.saleable_sqft,
        "gross_sqft": listing.gross_sqft,
        "bedrooms": listing.bedrooms,
        "furnished": listing.furnished,
        "available_from": listing.available_from.isoformat() if listing.available_from else None,
        "commute_min_estimate": m.commute["minutes"] if m.commute else None,
        "unknown_checks": sum(c.ok is None for c in m.checks),
    }


def allowed_numbers(f: dict, profile: Profile, extra: set[int] = frozenset()) -> set[int]:
    nums = {v for v in f.values() if isinstance(v, int) and not isinstance(v, bool)}
    for v in (profile.budget_hkd_month, profile.max_commute_min, profile.bedrooms):
        if v:
            nums.add(v)
    if profile.budget_hkd_month:
        nums.add(profile.budget_hkd_month - budgeted(f, profile))  # "HK$600 under budget"
    for d in (f.get("available_from"), profile.move_in.isoformat() if profile.move_in else None):
        if d:
            y, mth, day = (int(x) for x in d.split("-"))
            nums |= {y, mth, day}
    return nums | set(extra)


def supported(text: str, allowed: set[int]) -> bool:
    """Every number in the text must be a known fact. Small bare counts are allowed, but not
    small measurements: "5 minutes from the MTR" is a claim that needs a fact behind it."""
    for raw, unit in _NUMBER.findall(text):
        value = float(raw.replace(",", ""))
        if value != int(value):
            return False
        if int(value) in allowed or (int(value) in SMALL_COUNTS and not unit):
            continue
        return False
    return True


def budgeted(f: dict, profile: Profile) -> int:
    """The figure the budget is compared with: the rent for the student (their share, or the whole
    rent for a total budget). The budget is a rent budget; all-in cost is shown, not compared."""
    return f["rent_for_you_hkd"]


def fair_claim(text: str, f: dict, profile: Profile) -> bool:
    """Claims that can be true number by number and still false as a whole. No field names; a "your
    preferred district" claim only for a district the student named; and a reason that talks about
    the budget may only use the rent it is compared with, the budget and their difference. Every number can be real and the claim still false: "all-in HK$19,600 is
    under your HK$15,000 budget" (seen live)."""
    if _FIELD_NAME.search(text):
        return False  # the model echoed a field name ("Rent_for_you_hkd is HK$9,000")
    if re.search(r"prefer|you asked|you wanted|your choice", text, re.I) and not _named_by_student(
        text, f, profile
    ):
        return False  # "in Tseung Kwan O, one of your preferred districts" when the student named others (seen live)
    if not profile.budget_hkd_month or "budget" not in text.lower():
        return True
    budget, rent = profile.budget_hkd_month, f["rent_for_you_hkd"]
    allowed = {budget, rent, budget - rent} | SMALL_COUNTS
    money = {int(float(raw.replace(",", ""))) for raw, _unit in _NUMBER.findall(text)}
    return money <= allowed and rent <= budget


def _named_by_student(text: str, f: dict, profile: Profile) -> bool:
    """A claim that a home matches the student's stated preference holds only if the home's district
    is one the student named, or the preference it cites is in their soft preferences."""
    district = (f.get("district") or "").lower()
    named = [d.lower() for d in profile.districts]
    if district and any(d in district or district in d for d in named):
        return True
    return any(p.lower() in text.lower() for p in profile.soft_preferences)


def code_reasons(f: dict, profile: Profile) -> list[str]:
    reasons = []
    rent = f["rent_for_you_hkd"]
    who = " in total" if profile.budget_is_total else " for you" if rent != f["rent_hkd"] else ""
    if profile.budget_hkd_month:
        reasons.append(f"HK${rent:,} rent a month{who}, HK${profile.budget_hkd_month - rent:,} under budget")
    else:
        reasons.append(f"HK${rent:,} rent a month{who}")
    if f["commute_min_estimate"]:
        reasons.append(f"about {f['commute_min_estimate']} minutes to campus")
    if f["saleable_sqft"]:
        reasons.append(f"{f['saleable_sqft']:,} ft² saleable")
    if f["district"]:
        reasons.append(f"in {f['district']}")
    return reasons


async def answer_stage(ctx: RunContext, state: RunState) -> Stage:
    if state.profile is None:
        await _finish(ctx, state, "FlatJai could not read the brief this time. Please try again.", [])
        return "finished"
    profile = Profile.model_validate(state.profile)
    fits = state.fits()
    if not fits:
        await _finish(ctx, state, no_fit_summary(state), [])
        return "finished"

    table = {m.listing_id: facts(m, profile) for m in fits}
    picks, summary = await _ranked(ctx, profile, table)
    shortlist = [{"listing_id": i, "rank": n, "reasons": r} for n, (i, r) in enumerate(picks, start=1)]
    await ctx.store.put_shortlist(ctx.run_id, picks)
    await _finish(ctx, state, summary, shortlist)
    return "finished"


async def _ranked(
    ctx: RunContext, profile: Profile, table: dict[int, dict]
) -> tuple[list[tuple[int, list[str]]], str]:
    size = ctx.budget.shortlist_size
    by_value = sorted(table, key=lambda i: budgeted(table[i], profile))
    fallback = [(i, code_reasons(table[i], profile)) for i in by_value[:size]]
    cheapest = table[by_value[0]]
    fallback_summary = (
        f"{len(table)} home(s) meet your limits. The best value is {cheapest['title']} at "
        f"HK${budgeted(cheapest, profile):,} rent a month {'in total' if profile.budget_is_total else 'for you'}."
    )
    async with span("explain+check", "stage", homes=len(table)) as sp:
        try:
            async with asyncio.timeout(ctx.answer_time_left()):
                user = f"Student: {profile.model_dump_json()}\nHomes:\n" + "\n".join(
                    str(f) for f in table.values()
                )
                out = await ctx.tools.model.typed_call("explain", SYSTEM, user, Shortlist)
        except (TimeoutError, BudgetExhausted, ValueError) as e:
            sp.attrs["fallback"] = type(e).__name__
            return fallback, fallback_summary

        picks: list[tuple[int, list[str]]] = []
        dropped = 0
        for p in out.picks:
            if p.id not in table or any(p.id == i for i, _ in picks):
                dropped += 1
                continue
            ok = [
                r
                for r in p.reasons
                if supported(r, allowed_numbers(table[p.id], profile)) and fair_claim(r, table[p.id], profile)
            ]
            dropped += len(p.reasons) - len(ok)
            picks.append((p.id, ok or code_reasons(table[p.id], profile)))
        # homes the model left out still appear, after its picks, ordered by value
        picks += [(i, code_reasons(table[i], profile)) for i in by_value if i not in {p for p, _ in picks}]
        # homes whose hard limits are all confirmed come before homes with an unknown ("?") limit;
        # the model's order is kept within each group (a far home with an unknown commute ranked #1: seen live)
        picks.sort(key=lambda pick: table[pick[0]]["unknown_checks"])
        everything = set().union(*(allowed_numbers(f, profile, {len(table)}) for f in table.values()))
        summary_ok = supported(out.summary, everything)
        sp.attrs |= {"unsupported_claims": dropped + (not summary_ok), "summary_ok": summary_ok}
        return picks[:size], out.summary if summary_ok and out.summary.strip() else fallback_summary


def no_fit_summary(state: RunState) -> str:
    read, found = len(state.read_urls), len(state.read_urls) + len(state.candidates)
    stopped = any("budget" in n for n in state.notes)
    early = state.prefiltered
    if read == 0 and early:
        return (
            f"FlatJai found {found + early} homes, but going by their listed rents and areas, none fits "
            "your budget and commute. Here is what would change that."
        )
    if read == 0:
        if stopped:
            return f"FlatJai ran out of its budget before reading any of the {found} homes found. Try again."
        return "FlatJai could not find listings for this brief on the sites it can read."
    if stopped:
        return (
            f"FlatJai stopped after reading {read} of the {found} homes found, and none of those meets "
            "all your hard limits yet. Running the search again continues faster, as pages already read are cached."
        )
    if early:
        return (
            f"None of the {found + early} homes FlatJai found meets all your limits: {early} were ruled out "
            f"by their listed rent or area, and the {read} it read in full did not fit either."
        )
    return f"None of the {read} homes FlatJai read meets all your hard limits."


async def _finish(ctx: RunContext, state: RunState, summary: str, shortlist: list[dict]) -> None:
    calls = ctx.tools.model.calls
    await ctx.bus.emit(
        "done",
        summary=summary,
        shortlist=shortlist,
        relaxations=state.relaxations,
        notes=state.notes,
        counters=state.counters(),
        usage={
            "seconds": round(ctx.elapsed(), 1),
            "model_calls": len(calls),
            "tokens_in": sum(c.tokens_in for c in calls),
            "tokens_out": sum(c.tokens_out for c in calls),
            "fetches": state.fetches,
            "rounds": state.round,
        },
    )
    await ctx.store.add_message(ctx.session_id, "assistant", summary)
