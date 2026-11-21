"""Stage 6, Reflect: enough good homes, or search more?

Code forces the obvious cases (enough homes fit; rounds, time or model calls used up). Otherwise
the model decides between reading more of the homes already found, re-planning with advice (e.g.
"everything in Hang Hau is over budget, try cheaper areas further out"), or answering now.
Every grounding check on facts already happened in code (verify.py, match.py); claims in the final
explanation are checked in the Answer stage.
"""

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from ..schemas import Profile
from ..tracing import span
from .context import RunContext
from .state import RunState, Stage

MIN_ROUND_SECONDS = 25.0  # a new plan -> search -> read round needs at least this long
MIN_CALLS_FOR_ROUND = 5


class ReflectDecision(BaseModel):
    action: Literal["read_more", "replan", "answer"]
    reason: str = Field(description="One sentence to the student, saying 'you', about what happens next")
    advice: str = Field("", description="For replan: what the next search should change")


SYSTEM = """You review a home search for a student in Hong Kong and decide the next step:
- "read_more": unread homes from the current searches remain and they look promising
- "replan": the current areas are not working (e.g. most homes there are over budget); give advice
  for the next search, such as cheaper areas further from campus or a different home type
- "answer": stop and present what was found
Reply with JSON only."""


def outcome_summary(state: RunState) -> str:
    fails = Counter(
        c.name for m in state.matches if m.duplicate_of is None for c in m.checks if c.ok is False
    )
    shares = [c.value for m in state.matches for c in m.checks if c.name == "budget" and c.value]
    parts = [f"read {len(state.read_urls)} pages, {len(state.fits())} homes fit"]
    if fails:
        parts.append("rejected: " + ", ".join(f"{n} {k}" for k, n in fails.most_common()))
    if shares:
        parts.append(f"student's monthly share ranged HK${min(shares):,} to HK${max(shares):,}")
    if state.skipped:
        parts.append("skipped pages: " + ", ".join(f"{n} {k}" for k, n in state.skipped.items()))
    return "; ".join(parts)


def forced_decision(ctx: RunContext, state: RunState) -> str | None:
    calls_left = ctx.tools.model.calls_left
    if len(state.fits()) >= ctx.budget.enough:
        return "enough homes fit"
    if state.round >= ctx.budget.max_rounds and not state.candidates:
        return "all search rounds used"
    if ctx.work_time_left() < MIN_ROUND_SECONDS:
        return "time budget nearly used"
    if calls_left is not None and calls_left < MIN_CALLS_FOR_ROUND:
        return "model call budget nearly used"
    if state.fetches >= ctx.budget.max_fetches:
        return "fetch budget used"
    return None


async def reflect_stage(ctx: RunContext, state: RunState) -> Stage:
    summary = outcome_summary(state)
    async with span("decide", "stage", summary=summary) as sp:
        if "no_reflect" in ctx.budget.ablate:
            sp.attrs |= {"decision": "answer", "forced": "ablation no_reflect"}
            return "answer"
        if reason := forced_decision(ctx, state):
            sp.attrs |= {"decision": "answer", "forced": reason}
            return "answer"
        profile = Profile.model_validate(state.profile)
        user = (
            f"Profile: {profile.model_dump_json()}\nSearches tried: {'; '.join(state.queries_tried)}\n"
            f"Outcome: {summary}\nUnread homes from these searches: {len(state.candidates)}\n"
            f"Search rounds used: {state.round} of {ctx.budget.max_rounds}"
        )
        d = await ctx.tools.model.typed_call("reflect", SYSTEM, user, ReflectDecision)
        action = d.action
        if action == "read_more" and not state.candidates:
            action = "replan"
        if action == "replan" and state.round >= ctx.budget.max_rounds:
            action = "read_more" if state.candidates else "answer"
        sp.attrs |= {"decision": action, "model_said": d.action, "reason": d.reason}
    await ctx.bus.emit("progress", **state.counters(), note=d.reason)
    if action == "replan":
        state.advice = d.advice or d.reason
        return "plan"
    return "read" if action == "read_more" else "answer"
