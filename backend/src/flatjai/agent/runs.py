"""Run manager: creates runs in a session, executes them in the background, resumes interrupted ones.

- Idempotency: a client key seen before returns the existing run (double-click, retried POST).
- Sessions: a run may continue a session (an answer to our question, or a refinement); the
  session keeps the profile so far.
- Resume: a run whose process stopped (crash, restart) is still "running" in the database. On
  startup (and on a periodic sweep) it continues from the last saved stage with its event history
  restored, so a connected client just sees more events.
- Ownership: each manager has an owner id and refreshes a heartbeat on its runs. A resume claims a
  run only when its heartbeat is missing (a clean stop released it) or stale (a crash), so a dev
  server starting beside an evaluation never takes over a run the evaluation is still executing.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import timedelta

from ..storage import models as m
from ..storage.store import Store
from ..tracing import Tracer
from .context import RunContext, Toolbox
from .events import Event, EventBus
from .loop import run_agent
from .state import Budget, RunState

log = logging.getLogger(__name__)

HEARTBEAT_S = 10.0  # how often a manager marks its runs alive
STALE_S = 45.0  # a heartbeat older than this means the owner stopped
SWEEP_S = 30.0  # how often the server looks for runs to resume


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class RunManager:
    def __init__(
        self, store: Store, make_tools: Callable[[Budget], Toolbox], budget: Budget | None = None
    ) -> None:
        self.store, self.make_tools, self.budget = store, make_tools, budget or Budget()
        self.owner = new_id()
        self.live: dict[str, EventBus] = {}
        self.tasks: dict[str, asyncio.Task] = {}

    async def start(
        self, brief: str, client_key: str | None = None, session_id: str | None = None
    ) -> tuple[m.Run, bool]:
        """-> (run, created). A known client key returns the existing run instead of a new one."""
        if client_key and (existing := await self.store.run_by_key(client_key)):
            return existing, False
        if session_id is None or await self.store.get_session(session_id) is None:
            session_id = (await self.store.create_session(new_id())).id
        await self.store.add_message(session_id, "user", brief)
        tools = self.make_tools(self.budget)
        run = await self.store.create_run(
            id=new_id(),
            session_id=session_id,
            client_key=client_key,
            brief=brief,
            status="running",
            stage="understand",
            state=RunState().model_dump(mode="json"),
            model_profile=tools.model.profile.name,
            model=tools.model.profile.model,
            owner=self.owner,
            heartbeat_at=m.utcnow(),
        )
        self._launch(run, RunState(), [], tools)
        return run, True

    async def resume_unfinished(self) -> list[str]:
        resumed = []
        stale_before = m.utcnow() - timedelta(seconds=STALE_S)
        for run in await self.store.unfinished_runs():
            if run.id in self.tasks or not await self.store.claim_run(run.id, self.owner, stale_before):
                continue  # ours already, or another process is still executing it
            history = [Event(seq=e.seq, type=e.type, data=e.data) for e in await self.store.events(run.id)]
            state = RunState.model_validate(run.state)
            state.notes.append("This search was interrupted and resumed.")
            self._launch(run, state, history, self.make_tools(self.budget))
            resumed.append(run.id)
        return resumed

    async def sweep(self, every_s: float = SWEEP_S) -> None:
        """Resume runs whose owner crashed after this process started (the server runs this)."""
        while True:
            await asyncio.sleep(every_s)
            try:
                await self.resume_unfinished()
            except Exception:  # noqa: BLE001 - a failed sweep must not stop the next one
                log.exception("resume sweep failed")

    async def bus(self, run_id: str) -> EventBus | None:
        """The live bus of a running run, or a closed bus replaying a finished run from the database."""
        if run_id in self.live:
            return self.live[run_id]
        if await self.store.get_run(run_id) is None:
            return None
        history = [Event(seq=e.seq, type=e.type, data=e.data) for e in await self.store.events(run_id)]
        return EventBus(history=history)

    def _launch(self, run: m.Run, state: RunState, history: list[Event], tools: Toolbox) -> None:
        async def sink(event: Event) -> None:
            await self.store.add_event(run.id, event.seq, event.type, event.data)

        started = time.monotonic()
        bus = EventBus(history=history, sink=sink, clock=lambda: time.monotonic() - started)
        ctx = RunContext(
            run_id=run.id,
            session_id=run.session_id,
            brief=run.brief,
            tools=tools,
            store=self.store,
            bus=bus,
            tracer=Tracer(run.id),
            budget=self.budget,
        )
        self.live[run.id] = bus
        self.tasks[run.id] = asyncio.create_task(self._execute(ctx, state), name=f"run-{run.id}")

    async def _beat(self, run_id: str) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_S)
            try:
                await self.store.heartbeat(run_id, self.owner)
            except Exception:  # noqa: BLE001 - a missed beat only risks a later takeover
                log.exception("heartbeat for run %s failed", run_id)

    async def _execute(self, ctx: RunContext, state: RunState) -> None:
        beat = asyncio.create_task(self._beat(ctx.run_id))
        try:
            await run_agent(ctx, state)
            last = ctx.bus.history[-1].type if ctx.bus.history else None
            status = "needs_input" if last == "clarify" else "done"
            await self.store.save_run(ctx.run_id, status=status, ended_at=m.utcnow())
        except asyncio.CancelledError:
            # shutdown: the run stays "running"; released, so the next start resumes it at once
            try:
                await self.store.release_run(ctx.run_id, self.owner)
            except Exception:  # noqa: BLE001 - unreleased, it is resumed once its heartbeat is stale
                log.exception("could not release run %s", ctx.run_id)
            raise
        except Exception as e:  # noqa: BLE001 - any crash becomes a readable error event
            log.exception("run %s failed", ctx.run_id)
            await self.store.add_spans(ctx.tracer.drain())
            if not ctx.bus.closed:
                await ctx.bus.emit("error", message=readable(e), retry=True)
            await self.store.save_run(ctx.run_id, status="error", ended_at=m.utcnow())
        finally:
            beat.cancel()
            self.live.pop(ctx.run_id, None)
            self.tasks.pop(ctx.run_id, None)

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def readable(e: Exception) -> str:
    name = type(e).__name__
    if name in {"APIConnectionError", "APITimeoutError"}:
        return "The language model server is not reachable. Is Ollama (or the TACC service) running?"
    return f"Something went wrong ({name}: {e})."
