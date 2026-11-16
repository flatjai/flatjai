"""Stage 3, Search: planned queries -> candidate listing URLs.

Each query is searched per readable portal; the best list page per query is opened for its listing
links (live listings, unlike indexed ones that are often already let); results from different
queries are interleaved so early cards come from different areas. URLs already read or queued are
skipped. If web search finds nothing at all, the portal's own rental list is read instead.
"""

import asyncio
import logging
from itertools import zip_longest

from ..schemas import Profile
from ..tools.fetch import FetchError
from ..tools.portals import readable_listing_portals
from ..tools.search import SearchError, SearchResult, expand_list
from .context import RunContext
from .match import promise, quick_reject
from .state import RunState, Stage

log = logging.getLogger(__name__)
LIST_PAGES_PER_QUERY = 1


async def search_stage(ctx: RunContext, state: RunState) -> Stage:
    known = set(state.read_urls) | {c.url for c in state.candidates}
    per_query: list[list[SearchResult]] = []
    profile = Profile.model_validate(state.profile)
    portals = readable_listing_portals()
    if profile.room_only:  # a student who wants a room: student-housing sites first
        portals.sort(key=lambda p: not p.rooms)
    for portal in portals:
        if portal.rooms and portal.browse_url and state.round == 1:
            # student-housing sites list their homes on one page: read it every first round
            per_query.append(await _expand(ctx, state, portal.browse_url))
        hits = await asyncio.gather(*(_search(ctx, state, q, portal) for q in state.planned))
        state.queries += len(state.planned)
        for results in hits:
            listings: list[SearchResult] = []
            for page in [r for r in results if r.kind == "list"][:LIST_PAGES_PER_QUERY]:
                listings += await _expand(ctx, state, page.url)
            listings += [r for r in results if r.kind == "listing"]
            per_query.append(listings)
        if not any(per_query) and portal.browse_url and not portal.rooms and state.round == 1:
            per_query.append(await _expand(ctx, state, portal.browse_url))
            state.notes.append(f"Web search found nothing, so FlatJai read {portal.name}'s own rental list.")

    new: dict[str, SearchResult] = {}
    for row in zip_longest(*per_query):
        for r in row:
            if r is not None and r.url not in known:
                new.setdefault(r.url, r)
    # list-page pre-filter: skip what surely cannot fit before spending a fetch and a model call on it
    keep: list[SearchResult] = []
    for r in new.values():
        if reason := quick_reject(r.preview, profile):
            state.skip(f"{reason} (list page)")
            state.prefiltered += 1
            if reason == "over budget" and r.preview and r.preview.rent_hkd:
                state.card_rents.append(r.preview.rent_hkd)
        else:
            keep.append(r)
    keep.sort(key=lambda r: promise(r.preview, profile))  # stable: area interleaving is kept within groups
    state.candidates += keep
    state.found += len(new)
    state.queries_tried += state.planned
    await ctx.bus.emit("progress", **state.counters(), new_candidates=len(new))
    return "read" if state.candidates else "reflect"


async def _search(ctx: RunContext, state: RunState, query: str, portal) -> list[SearchResult]:
    try:
        return await ctx.tools.searcher.search(query, portal=portal)
    except SearchError as e:
        log.warning("search failed: %s", e)
        state.skip("search error")
        return []


async def _expand(ctx: RunContext, state: RunState, url: str) -> list[SearchResult]:
    if state.fetches >= ctx.budget.max_fetches:
        return []
    state.fetches += 1
    try:
        return await expand_list(ctx.tools.fetcher, url)
    except FetchError as e:
        log.warning("list page %s failed: %s", url, e)
        state.skip("list page error")
        return []
