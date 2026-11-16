import asyncio

import pytest

from flatjai.agent.events import EventBus


async def collect(bus: EventBus, after: int = 0) -> list[int]:
    return [e.seq async for e in bus.subscribe(after=after)]


async def test_live_subscriber_gets_every_event_in_order():
    bus = EventBus()
    task = asyncio.create_task(collect(bus))
    await bus.emit("state", stage="understand")
    await bus.emit("progress", pages=1)
    await bus.emit("done", summary="ok")
    assert await asyncio.wait_for(task, 1) == [1, 2, 3]


async def test_reconnect_resumes_after_last_event_id():
    bus = EventBus()
    for i in range(3):
        await bus.emit("progress", pages=i)
    await bus.emit("done", summary="ok")
    assert await collect(bus, after=2) == [3, 4]


async def test_reconnect_after_everything_was_seen_ends_immediately():
    bus = EventBus()
    await bus.emit("done", summary="ok")
    assert await asyncio.wait_for(collect(bus, after=1), 1) == []


async def test_heartbeat_when_quiet():
    bus = EventBus()
    it = bus.subscribe(heartbeat_s=0.01)
    assert await asyncio.wait_for(anext(it), 1) is None
    await bus.emit("done", summary="ok")
    assert (await anext(it)).type == "done"


async def test_no_events_after_done():
    bus = EventBus()
    await bus.emit("error", message="x")
    with pytest.raises(RuntimeError):
        await bus.emit("progress")


async def test_events_carry_seconds_since_start():
    bus = EventBus(clock=lambda: 12.34)
    assert (await bus.emit("progress")).data == {"t": 12.3}
