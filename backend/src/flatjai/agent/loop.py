"""The agent loop: a state machine over seven named stages.

    understand -> plan -> search -> read -> match -> reflect -> answer
                   ^                  ^                 |
                   |                  +-- read_more ----+
                   +------------------ replan ----------+
    understand -> (clarify) -> finished, when the model decides to ask the student first

Each stage is a function (ctx, state) -> next stage. After every stage the state is saved and the
finished spans are written, so a run can resume from the last stage after a crash. When time or
model calls run out, the loop jumps to Answer, which always produces an answer.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from ..model_client import BudgetExhausted
from ..schemas import Profile
from ..tracing import activate, span
from .answer import answer_stage
from .context import RunContext
from .gather import search_stage
from .match import mark_duplicates, relaxations
from .plan import fallback_queries, new_queries, plan_search, within_reach
from .read import read_stage
from .reflect import reflect_stage
from .state import RunState, Stage
from .understand import decide_clarify, parse_brief, tidy_suggestions

log = logging.getLogger(__name__)
BLOCKING = ("budget_hkd_month", "campus")


async def understand_stage(ctx: RunContext, state: RunState) -> Stage:
    session = await ctx.store.get_session(ctx.session_id)
    previous = Profile.model_validate(session.profile) if session and session.profile else None
    profile = await parse_brief(ctx.tools.model, ctx.brief, previous=previous)
    state.profile = profile.model_dump(mode="json")
    missing = profile.missing()
    await ctx.store.update_session(ctx.session_id, profile=state.profile)
    await ctx.bus.emit("state", stage="understand", profile=state.profile, missing=missing)

    not_asked = [f for f in missing if f not in (session.asked if session else [])]
    # Only a missing budget or campus is worth stopping for. Move-in alone never is: listings rarely
    # state availability, so the search would come out the same (seen live: Qwen stopped three
    # complete briefs to ask "When do you need to move in?"). It is still asked with a real gap.
    if any(f in BLOCKING for f in not_asked):
        decision = await decide_clarify(ctx.tools.model, ctx.brief, profile, not_asked)
        if decision.ask and decision.question.strip():
            await ctx.store.update_session(
                ctx.session_id, asked=[*(session.asked if session else []), *not_asked]
            )
            await ctx.store.add_message(ctx.session_id, "assistant", decision.question)
            await ctx.bus.emit(
                "clarify",
                question=decision.question,
                suggestions=tidy_suggestions(decision.suggestions)[:4],
                missing=not_asked,
            )
            return "finished"
    return "plan"


async def plan_stage(ctx: RunContext, state: RunState) -> Stage:
    profile = Profile.model_validate(state.profile)
    state.round += 1
    try:
        plan = await plan_search(ctx.tools.model, profile, state.queries_tried, state.advice)
        queries = new_queries(within_reach([q.text for q in plan.queries], profile), state.queries_tried)
        rationale = plan.rationale
    except ValueError:  # invalid plan after the repair retry: deterministic fallback
        queries, rationale = [], ""
    if not queries:
        queries = fallback_queries(profile, state.queries_tried)
        rationale = rationale or "Searching the areas closest to campus."
    state.planned, state.advice = queries, None
    await ctx.bus.emit("state", stage="plan", round=state.round, queries=queries, rationale=rationale)
    return "search" if queries else "answer"


async def match_stage(ctx: RunContext, state: RunState) -> Stage:
    duplicates = mark_duplicates(state.matches)
    profile = Profile.model_validate(state.profile)
    state.relaxations = (
        relaxations(state.matches, profile, state.card_rents) if len(state.fits()) < ctx.budget.enough else []
    )
    await ctx.bus.emit("progress", **state.counters(), duplicates=duplicates)
    return "reflect"


StageFn = Callable[[RunContext, RunState], Awaitable[Stage]]
STAGES: dict[str, StageFn] = {
    "understand": understand_stage,
    "plan": plan_stage,
    "search": search_stage,
    "read": read_stage,
    "match": match_stage,
    "reflect": reflect_stage,
    "answer": answer_stage,
}


async def run_agent(ctx: RunContext, state: RunState) -> RunState:
    """Run stages until finished. Returns the final state (also saved after every stage)."""
    activate(ctx.tracer)
    while state.stage != "finished":
        name = state.stage
        await ctx.bus.emit("state", stage=name)  # stages may emit again with details
        try:
            async with span(name, "stage", round=state.round):
                if name == "answer":
                    state.stage = await STAGES[name](ctx, state)
                else:
                    async with asyncio.timeout(max(ctx.work_time_left(), 0.01)):
                        state.stage = await STAGES[name](ctx, state)
        except TimeoutError:
            state.notes.append(f"Stopped searching at the {ctx.budget.max_seconds:.0f} s time budget.")
            state.stage = "answer" if name != "answer" else "finished"
        except BudgetExhausted:
            state.notes.append(f"Used the budget of {ctx.budget.max_model_calls} model calls.")
            state.stage = "answer" if name != "answer" else "finished"
        await ctx.store.save_run(ctx.run_id, stage=state.stage, state=state.model_dump(mode="json"))
        await ctx.store.add_spans(ctx.tracer.drain())
    return state
