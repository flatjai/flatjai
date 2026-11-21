"""E2 ablations (agent/ablations.py): each switch removes exactly one agent part."""

import pytest
from test_loop import FakeSearcher, run

from flatjai.agent.ablations import parse_ablations
from flatjai.agent.state import Budget


def schema_names(fake):
    return [r["response_format"]["json_schema"]["name"] for r in fake.requests]


def test_parse_ablations_rejects_unknown_names():
    assert parse_ablations("") == frozenset()
    assert parse_ablations(" no_reflect, no_dedup ") == {"no_reflect", "no_dedup"}
    with pytest.raises(ValueError, match="no_such"):
        parse_ablations("no_such")


async def test_no_reflect_answers_after_one_pass(store):
    replies = {
        "Profile": {"budget_hkd_month": 10000, "campus": "HKUST", "move_in": "2027-01-01"},
        "ReflectDecision": {"action": "replan", "reason": "all over budget", "advice": "cheaper areas"},
    }
    searcher = FakeSearcher()
    _, state, fake, _ = await run(
        store, replies, searcher=searcher, budget=Budget(max_rounds=3, ablate=frozenset({"no_reflect"}))
    )
    assert state.round == 1 and "ReflectDecision" not in schema_names(fake)


async def test_no_dedup_keeps_both_copies_of_a_home(store):
    _, state, _, _ = await run(store, budget=Budget(ablate=frozenset({"no_dedup"})))
    assert len(state.matches) == 2 and all(m.duplicate_of is None for m in state.matches)


async def test_model_facts_replace_the_tools_and_keep_the_tool_figures(store):
    replies = {"ModelFacts": {"monthly_hkd": 9999, "move_in_hkd": 11111, "commute_min": 7}}
    events, state, fake, _ = await run(store, replies, budget=Budget(ablate=frozenset({"model_facts"})))
    m = state.matches[0]
    assert m.cost["monthly_hkd"] == 9999 and m.cost["move_in_hkd"] == 11111
    assert m.cost["tool_monthly_hkd"] == 12800 + 600  # the cost tool: rent + utilities estimate
    assert m.cost["tool_move_in_hkd"] == 12800 * 3 + 6400  # deposit 2 + first month + half commission
    assert m.commute["method"] == "model" and m.commute["minutes"] == 7
    assert "ModelFacts" in schema_names(fake)


async def test_run_manager_takes_the_ablations_given_over_the_cached_settings(store):
    # eval/run_suite.py once set FJ_ABLATE after `import flatjai.api` had cached settings(), so every
    # "ablation" ran the full agent; it now passes them in
    import httpx

    from flatjai.api import build_run_manager
    from flatjai.config import active_profile
    from flatjai.model_client import ModelClient

    async with httpx.AsyncClient() as http:
        given = build_run_manager(http, ModelClient(active_profile()), store, ablate=frozenset({"no_dedup"}))
        default = build_run_manager(http, ModelClient(active_profile()), store)
    assert given.budget.ablate == {"no_dedup"} and default.budget.ablate == frozenset()
