"""The full agent loop with fake search, fetch and model, and a real (SQLite) store: stage order,
cards, clarify, sessions, re-plan, budgets, resume and tracing."""

import asyncio
from datetime import UTC, datetime

from conftest import ALL_REPLIES, DRAFT_JSON, LIST_HTML, LIST_URL, LISTING_HTML, LISTING_URL, make_model

from flatjai.agent.context import RunContext, Toolbox
from flatjai.agent.events import EventBus
from flatjai.agent.loop import run_agent
from flatjai.agent.state import Budget, RunState
from flatjai.tools.clean import html_to_text, page_links
from flatjai.tools.fetch import FetchBlocked, Page
from flatjai.tools.search import SearchError, portal_results
from flatjai.tracing import Tracer

OTHER_URL = "https://hk.centanet.com/findproperty/en/detail/Other-Estate_DEF456?theme=rent"


class FakeSearcher:
    def __init__(self, raw=None, fail=False):
        self.raw, self.fail, self.queries = raw or [{"url": LIST_URL}], fail, []

    async def search(self, query, portal=None, lang="en"):
        self.queries.append(query)
        if self.fail:
            raise SearchError("down")
        return portal_results(self.raw)


class FakeFetcher:
    def __init__(self, blocked=(), delay=0.0):
        self.blocked, self.delay, self.urls = set(blocked), delay, []

    async def fetch(self, url):
        self.urls.append(url)
        await asyncio.sleep(self.delay)
        if url in self.blocked:
            raise FetchBlocked(url)
        html = LISTING_HTML if "/detail/" in url else LIST_HTML
        return Page(
            url=url,
            final_url=url,
            page_hash=url[-12:],
            title="t",
            text=html_to_text(html),
            fetched_at=datetime.now(UTC),
            http_status=200,
            links=page_links(html, url),
        )


async def run(
    store,
    replies=None,
    searcher=None,
    fetcher=None,
    budget=None,
    brief="2 bed near HKUST, 15k a month",
    session_id="s1",
    state=None,
):
    if await store.get_session(session_id) is None:
        await store.create_session(session_id)
    run_id = f"r{len(await store.list_runs()) + 1}"
    await store.create_run(
        id=run_id,
        session_id=session_id,
        brief=brief,
        status="running",
        stage="understand",
        state={},
        model_profile="fake",
        model="fake",
    )
    mc, fake = make_model(ALL_REPLIES | (replies or {}))
    budget = budget or Budget()
    mc.call_limit = budget.max_model_calls
    ctx = RunContext(
        run_id=run_id,
        session_id=session_id,
        brief=brief,
        tools=Toolbox(mc, searcher or FakeSearcher(), fetcher or FakeFetcher()),
        store=store,
        bus=EventBus(),
        tracer=Tracer(run_id),
        budget=budget,
    )
    final = await run_agent(ctx, state or RunState())
    return ctx.bus.history, final, fake, run_id


def stages(events):
    """Stages in order; a stage that speaks twice in a row (start, then details) counts once."""
    out = []
    for e in events:
        if e.type == "state" and (not out or out[-1] != e.data["stage"]):
            out.append(e.data["stage"])
    return out


async def test_full_loop_streams_cards_and_ranked_answer(store):
    events, state, _, run_id = await run(store)
    assert stages(events) == ["understand", "plan", "search", "read", "match", "reflect", "answer"]
    cards = [e.data for e in events if e.type == "card"]
    assert {c["listing"]["source_url"] for c in cards} == {LISTING_URL, OTHER_URL}
    assert cards[0]["checks"][0]["name"] == "budget" and cards[0]["checks"][0]["ok"] is True
    done = events[-1]
    assert done.type == "done" and len(done.data["shortlist"]) == 1  # both pages hold the same flat
    assert done.data["shortlist"][0]["reasons"][0].startswith("HK$12,800 rent a month, HK$2,200 under budget")
    assert state.stage == "finished"
    saved = await store.get_run(run_id)
    assert saved.stage == "finished" and saved.state["round"] == 1


async def test_duplicate_listing_is_marked(store):
    _, state, _, _ = await run(store)
    assert sum(m.duplicate_of is not None for m in state.matches) == 1


async def test_every_stage_model_and_tool_call_is_traced(store):
    _, _, _, run_id = await run(store)
    spans = await store.spans(run_id)
    kinds = {(s.kind, s.name) for s in spans}
    assert (
        ("stage", "read") in kinds and ("model", "extract_listing") in kinds and ("model", "explain") in kinds
    )
    by_id = {s.id: s for s in spans}
    extract = next(s for s in spans if s.name == "extract_listing")
    assert by_id[extract.parent_id].name == "read"  # tasks inherit the stage span
    assert extract.tokens_in == 100 and "Page text" in extract.attrs["input"]


async def test_second_run_uses_the_extraction_cache(store):
    await run(store)
    _, _, fake, _ = await run(store, session_id="s2")
    names = [r["response_format"]["json_schema"]["name"] for r in fake.requests]
    assert "ListingDraft" not in names


async def test_missing_budget_asks_once_then_continues_in_the_session(store):
    replies = {
        "Profile": {"campus": "HKUST"},
        "ClarifyDecision": {
            "ask": True,
            "question": "What is your monthly budget?",
            "suggestions": ["HK$8,000", "HK$12,000"],
        },
    }
    events, state, _, run_id = await run(store, replies, brief="2 bed near HKUST")
    assert events[-1].type == "clarify" and events[-1].data["missing"] == ["budget_hkd_month", "move_in"]
    assert stages(events) == ["understand"]
    assert (await store.get_session("s1")).asked == ["budget_hkd_month", "move_in"]

    # the answer arrives as a new run in the same session; the earlier campus is kept
    replies2 = {
        "Profile": {"budget_hkd_month": 15000},
        "ClarifyDecision": {"ask": True, "question": "again?"},
    }
    events2, state2, _, _ = await run(store, replies2, brief="15k")
    assert state2.profile["campus"] == "HKUST" and state2.profile["budget_hkd_month"] == 15000
    assert events2[-1].type == "done"  # move_in is still missing, but we never ask twice


async def test_model_decides_not_to_ask(store):
    events, _, fake, _ = await run(store, {"Profile": {"budget_hkd_month": 15000, "campus": "HKUST"}})
    names = [r["response_format"]["json_schema"]["name"] for r in fake.requests]
    assert "ClarifyDecision" in names and events[-1].type == "done"


async def test_replan_when_nothing_fits(store):
    replies = {
        "Profile": {"budget_hkd_month": 10000, "campus": "HKUST", "move_in": "2027-01-01"},
        "SearchPlan": [
            {"queries": [{"area": "Hang Hau", "text": "Hang Hau flat"}]},
            {"queries": [{"area": "Po Lam", "text": "Po Lam flat"}]},
        ],
        "ReflectDecision": [
            {"action": "replan", "reason": "all over budget", "advice": "cheaper areas"},
            {"action": "answer", "reason": "stop"},
        ],
    }
    searcher = FakeSearcher()
    events, state, fake, _ = await run(
        store, replies, searcher=searcher, budget=Budget(max_rounds=2), brief="flat near HKUST, 10k max"
    )
    assert list(dict.fromkeys(searcher.queries)) == ["Hang Hau flat", "Po Lam flat"]  # once per portal
    plan_prompt = [r for r in fake.requests if r["response_format"]["json_schema"]["name"] == "SearchPlan"][1]
    assert "cheaper areas" in plan_prompt["messages"][1]["content"]
    assert "Hang Hau flat" in plan_prompt["messages"][1]["content"]  # told what was tried
    done = events[-1].data
    assert done["shortlist"] == [] and "None of the" in done["summary"]
    assert done["relaxations"][0].startswith("Raising the rent budget to about HK$12,800")


async def test_enough_homes_skips_the_reflect_call(store):
    _, _, fake, _ = await run(store, budget=Budget(enough=1))
    names = [r["response_format"]["json_schema"]["name"] for r in fake.requests]
    assert "ReflectDecision" not in names


async def test_search_down_falls_back_to_portal_list(store):
    fetcher = FakeFetcher()
    events, state, _, _ = await run(store, searcher=FakeSearcher(fail=True), fetcher=fetcher)
    assert fetcher.urls[0] == "https://hk.centanet.com/findproperty/en/list/rent"
    assert any("own rental list" in n for n in state.notes)


async def test_blocked_page_is_skipped(store):
    _, state, _, _ = await run(store, fetcher=FakeFetcher(blocked={LISTING_URL}))
    assert state.skipped == {"blocked": 1} and len(state.fits()) == 1


async def test_time_budget_still_ends_with_an_answer(store):
    events, state, _, _ = await run(
        store, fetcher=FakeFetcher(delay=5), budget=Budget(max_seconds=0.6, answer_reserve_s=0.3)
    )
    assert events[-1].type == "done" and any("time budget" in n for n in state.notes)


async def test_model_call_budget_ends_with_an_answer(store):
    events, state, _, _ = await run(store, budget=Budget(max_model_calls=3))
    assert events[-1].type == "done" and any("model calls" in n for n in state.notes)


async def test_resume_from_saved_read_stage(store):
    """A run that crashed after Search continues with Read; earlier stages are not repeated."""
    saved = RunState(
        stage="read",
        round=1,
        profile={"budget_hkd_month": 15000, "campus": "HKUST"},
        queries_tried=["Hang Hau flat"],
        candidates=portal_results([{"url": LISTING_URL}]),
    )
    events, state, fake, _ = await run(store, state=saved)
    assert stages(events) == ["read", "match", "reflect", "answer"]
    assert "Profile" not in [r["response_format"]["json_schema"]["name"] for r in fake.requests]
    assert events[-1].data["shortlist"][0]["listing_id"] == state.fits()[0].listing_id
    assert DRAFT_JSON["rent_hkd_month"] == 12800


async def test_every_page_read_is_reported_with_its_outcome(store):
    events, _, _, _ = await run(store, fetcher=FakeFetcher(blocked={LISTING_URL}))
    obs = [e.data for e in events if e.type == "observation"]
    assert {o["outcome"] for o in obs} == {"skipped", "fit"}
    assert next(o for o in obs if o["outcome"] == "skipped")["reason"] == "blocked"
    flights = [e.data["in_flight"] for e in events if e.type == "progress" and "in_flight" in e.data]
    assert flights[0] == 2 and flights[-1] == 0


async def test_replan_never_leaves_the_areas_within_reach(store):
    replies = {
        "Profile": {"budget_hkd_month": 15000, "campus": "HKUST", "max_commute_min": 40},
        "SearchPlan": {"queries": [{"area": "Mong Kok", "text": "Mong Kok flat"}]},
    }
    searcher = FakeSearcher()
    await run(store, replies, searcher=searcher, brief="flat near HKUST, 15k, 40 min")
    assert searcher.queries and all("Mong Kok" not in q for q in searcher.queries)
