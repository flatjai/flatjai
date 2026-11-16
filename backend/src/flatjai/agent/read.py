"""Stage 4, Read: candidate URLs -> verified listings, checked against the hard constraints.

Per candidate: fetch (cached 24 h) -> extraction (cached per page hash + extractor version + model)
-> grounding check -> cost -> hard checks. Candidates are read concurrently (the fetcher paces each
domain, the model client caps concurrency) and a card is streamed as soon as a home fits. Reading
stops early once the shortlist is full; unread candidates go back in the queue.
"""

import asyncio
import logging

import openai

from ..schemas import Listing, Profile
from ..tools.cost import cost
from ..tools.extract import EXTRACTOR_VERSION, NotAListing, extract_listing
from ..tools.fetch import FetchBlocked, FetchError, Page
from ..tools.portals import portal_for
from ..tools.preview import preview_from_page
from ..tools.search import SearchResult
from ..tools.transit import CAMPUSES, Commute, commute
from ..tracing import span
from .context import RunContext
from .match import hard_checks, quick_reject, with_commute
from .plan import campus_key
from .state import Match, RunState, Stage
from .verify import Unsupported, verify_listing

log = logging.getLogger(__name__)


async def read_stage(ctx: RunContext, state: RunState) -> Stage:
    profile = Profile.model_validate(state.profile)
    room = min(ctx.budget.reads_per_round, ctx.budget.max_fetches - state.fetches)
    batch, state.candidates = state.candidates[:room], state.candidates[room:]
    state.fetches += len(batch)
    by_url = {r.url: r for r in batch}
    tasks = {asyncio.create_task(_tagged(ctx, r, profile)): r for r in batch}
    await ctx.bus.emit("progress", **state.counters(), in_flight=len(tasks))
    try:
        for next_done in asyncio.as_completed(tasks):
            url, match, reason = await next_done
            state.read_urls.append(url)
            preview = by_url[url].preview
            if reason.startswith("over budget") and preview and preview.rent_hkd:
                state.card_rents.append(preview.rent_hkd)
            if match is None:
                state.skip(reason)
            else:
                state.matches.append(match)
            await ctx.bus.emit("observation", **observation(url, match, reason))
            if match is not None and match.fits:
                await ctx.bus.emit("card", **card(match))
            in_flight = sum(not t.done() for t in tasks)
            await ctx.bus.emit("progress", **state.counters(), in_flight=in_flight)
            if len(state.fits()) >= ctx.budget.shortlist_size:
                break
    finally:
        unread = [r for t, r in tasks.items() if not t.done() or t.cancelled()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        done_urls = set(state.read_urls)
        state.candidates = [r for r in unread if r.url not in done_urls] + state.candidates
        state.fetches -= len([r for r in unread if r.url not in done_urls])
    return "match"


async def _tagged(ctx: RunContext, result: SearchResult, profile: Profile) -> tuple[str, Match | None, str]:
    match, reason = await read_one(ctx, result, profile)
    return result.url, match, reason


async def read_one(ctx: RunContext, result: SearchResult, profile: Profile) -> tuple[Match | None, str]:
    """-> (match, "ok") or (None, short skip reason)."""
    try:
        page = await ctx.tools.fetcher.fetch(result.url)
    except FetchBlocked as e:
        log.info("skip: %s", e)
        return None, "blocked"
    except FetchError as e:
        log.info("skip: %s", e)
        return None, "gone or unreachable"

    # a labelled rent already over budget: skip the model call (about 25 s on a laptop)
    if page_preview := preview_from_page(page.text):
        result.preview = page_preview  # kept so the rent can feed budget suggestions
    if reason := quick_reject(page_preview, profile):
        return None, f"{reason} (listed rent)"

    model = ctx.tools.model.profile.model
    row = await ctx.store.extraction(page.page_hash, EXTRACTOR_VERSION, model)
    if row is None:
        try:
            listing, dropped, outcome = await _extract(ctx, page, result)
        except openai.APIError as e:  # model server trouble: skip, and do not cache the outcome
            log.warning("model error on %s: %s", page.url, e)
            return None, "model error"
        row = await ctx.store.put_extraction(
            page_hash=page.page_hash,
            extractor_version=EXTRACTOR_VERSION,
            model=model,
            data=listing.model_dump(mode="json") if listing else None,
            outcome=outcome,
            dropped=dropped,
        )
    if row.outcome != "ok" or row.data is None:
        return None, row.outcome

    listing = Listing.model_validate(row.data)
    c = cost(listing)
    checks = hard_checks(listing, c, profile)
    trip = await _commute(ctx, listing, profile)
    if trip is not None:
        journey, precision = trip
        checks = with_commute(checks, journey.minutes, journey.summary(), profile, precision)
    match = Match(
        listing_id=row.id,
        listing=row.data,
        cost=c.model_dump(mode="json"),
        checks=checks,
        fetched_at=page.fetched_at.isoformat(),
        dropped=row.dropped,
        commute=journey.model_dump() | {"precision": precision} if trip else None,
    )
    return match, "ok"


async def _commute(ctx: RunContext, listing: Listing, profile: Profile) -> tuple[Commute, str] | None:
    """Locate the home (cached) and estimate the commute to the student's campus."""
    key = campus_key(profile.campus)
    if ctx.tools.geocoder is None or key not in CAMPUSES:
        return None
    place = await ctx.tools.geocoder.locate(geocode_name(listing), listing.district)
    if place is None:
        return None
    async with span("commute", "tool", campus=key, home=[place.lat, place.lon]) as sp:
        journey = commute((place.lat, place.lon), key)
        sp.attrs["minutes"] = journey.minutes if journey else None
    return (journey, place.precision) if journey else None


def geocode_name(listing: Listing) -> str | None:
    """The estate or building to look up: 'Hang Hau · RESIDENCE OASIS・Tower 2' -> 'RESIDENCE OASIS'."""
    if listing.estate:
        return listing.estate
    title = listing.title.split("·")[-1]
    return title.split("・")[0].strip() or None


async def _extract(
    ctx: RunContext, page: Page, result: SearchResult
) -> tuple[Listing | None, list[str], str]:
    portal = portal_for(page.final_url) or portal_for(result.url)
    try:
        listing = await extract_listing(ctx.tools.model, page, portal.name if portal else result.portal)
        verified = verify_listing(listing, page.text)
    except NotAListing:
        return None, [], "not a listing"
    except Unsupported:
        return None, [], "unsupported rent"
    except ValueError:  # still invalid after the repair retry
        return None, [], "extraction failed"
    return verified.listing, verified.dropped, "ok"


def observation(url: str, match: Match | None, reason: str) -> dict:
    """What one page turned out to be, for the live reading feed: fit, rejected (and why) or skipped."""
    if match is None:
        return {"url": url, "title": None, "outcome": "skipped", "reason": reason}
    failed = next((c for c in match.checks if c.ok is False), None)
    return {
        "url": url,
        "title": match.listing.get("title"),
        "district": match.listing.get("district"),
        "rent_hkd": match.listing.get("rent_hkd_month"),
        "outcome": "fit" if match.fits else "rejected",
        "failed": failed.name if failed else ("duplicate" if match.duplicate_of else None),
        "reason": failed.detail if failed else None,
    }


def card(m: Match) -> dict:
    return {
        "listing_id": m.listing_id,
        "listing": m.listing,
        "cost": m.cost,
        "checks": [c.model_dump() for c in m.checks],
        "fetched_at": m.fetched_at,
        "unverified_fields": m.dropped,
        "commute": m.commute,
    }
