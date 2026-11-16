"""Typed run events and a per-run bus that the SSE endpoint reads.

Every event gets a sequence number. The bus keeps the full history, so a client that reconnects
with Last-Event-ID receives exactly the events it missed, then live ones. With a sink, each event is
also written to Postgres before subscribers see it, so a finished or resumed run replays from there.
A run ends with exactly one terminal event: done, error, or clarify (waiting for the student).
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel

EventType = Literal["state", "progress", "observation", "clarify", "card", "token", "done", "error"]
TERMINAL: set[str] = {"done", "error", "clarify"}


class Event(BaseModel):
    seq: int
    type: EventType
    data: dict[str, Any]


class EventBus:
    def __init__(
        self,
        history: list[Event] | None = None,
        sink: Callable[[Event], Awaitable[None]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.history: list[Event] = list(history or [])
        self.sink = sink
        self.clock = clock  # seconds since the run started; stamped on every event as "t"
        self._changed = asyncio.Condition()

    @property
    def closed(self) -> bool:
        return bool(self.history) and self.history[-1].type in TERMINAL

    async def emit(self, type: EventType, **data: Any) -> Event:
        if self.closed:
            raise RuntimeError("run already finished")
        async with self._changed:  # numbering, persisting and appending happen as one step
            if self.clock is not None:
                data = {**data, "t": round(self.clock(), 1)}
            event = Event(seq=len(self.history) + 1, type=type, data=data)
            if self.sink is not None:
                await self.sink(event)
            self.history.append(event)
            self._changed.notify_all()
        return event

    async def subscribe(
        self, after: int = 0, heartbeat_s: float | None = None
    ) -> AsyncIterator[Event | None]:
        """Yield events with seq > after, waiting for new ones until the run finishes.

        With heartbeat_s, yields None after that many quiet seconds so the caller can keep an
        idle connection alive (the timeout is caught here, so the generator itself survives it).
        """
        sent = after
        while not (self.closed and sent >= len(self.history)):
            async with self._changed:
                try:
                    async with asyncio.timeout(heartbeat_s):
                        await self._changed.wait_for(lambda s=sent: len(self.history) > s)
                except TimeoutError:
                    batch = None
                else:
                    batch = self.history[sent:]
            if batch is None:
                yield None
                continue
            for event in batch:
                yield event
                sent = event.seq
