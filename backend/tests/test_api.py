"""Request API over ASGI with the real RunManager, fake tools and a SQLite store."""

import asyncio

import httpx
import pytest
from conftest import ALL_REPLIES, make_model
from test_loop import FakeFetcher, FakeSearcher

from flatjai.agent.context import Toolbox
from flatjai.agent.runs import RunManager
from flatjai.api import app


def manager(store, replies=None) -> RunManager:
    def make_tools(budget):
        mc, _ = make_model(ALL_REPLIES | (replies or {}))
        return Toolbox(mc, FakeSearcher(), FakeFetcher())

    return RunManager(store, make_tools)


@pytest.fixture
async def api(store):
    async def open_client(replies=None):
        app.state.store, app.state.runs = store, manager(store, replies)
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")

    yield open_client
    await app.state.runs.shutdown()
    del app.state.store, app.state.runs


@pytest.fixture
async def client(api):
    async with await api() as c:
        yield c


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = [line for line in block.split("\n") if ": " in line and not line.startswith(":")]
        fields = dict(line.split(": ", 1) for line in lines)
        if "event" in fields:
            events.append(fields)
    return events


async def finished(run_id: str) -> None:
    if task := app.state.runs.tasks.get(run_id):
        await asyncio.wait_for(asyncio.shield(task), 5)


async def start(client, **body) -> dict:
    r = await client.post("/runs", json={"brief": "2 bed near HKUST"} | body)
    return r.json()


async def test_run_streams_events_then_replays_from_the_database(client):
    r = await client.post("/runs", json={"brief": "2 bed near HKUST", "client_key": "k1"})
    assert r.status_code == 201
    run_id, session_id = r.json()["run_id"], r.json()["session_id"]
    live = parse_sse((await client.get(f"/runs/{run_id}/events")).text)
    assert live[0]["event"] == "state" and live[-1]["event"] == "done"
    await finished(run_id)
    assert run_id not in app.state.runs.live  # finished: now served from the database
    replay = parse_sse((await client.get(f"/runs/{run_id}/events")).text)
    assert [e["id"] for e in replay] == [e["id"] for e in live]
    info = (await client.get(f"/runs/{run_id}")).json()
    assert info["status"] == "done" and info["session_id"] == session_id


async def test_same_client_key_returns_the_same_run(client):
    a = await client.post("/runs", json={"brief": "abc", "client_key": "same"})
    b = await client.post("/runs", json={"brief": "abc", "client_key": "same"})
    assert a.status_code == 201 and b.status_code == 200 and a.json()["run_id"] == b.json()["run_id"]


async def test_resume_with_last_event_id(client):
    run_id = (await start(client))["run_id"]
    everything = parse_sse((await client.get(f"/runs/{run_id}/events")).text)
    rest = parse_sse((await client.get(f"/runs/{run_id}/events", headers={"Last-Event-ID": "3"})).text)
    assert [e["id"] for e in rest] == [e["id"] for e in everything[3:]]


async def test_follow_up_continues_the_session(client):
    first = await start(client)
    await client.get(f"/runs/{first['run_id']}/events")
    second = await start(client, brief="cheaper", session_id=first["session_id"])
    assert second["session_id"] == first["session_id"]
    messages = await app.state.store.messages(first["session_id"])
    assert [m.role for m in messages][:3] == ["user", "assistant", "user"]


async def test_trace_endpoint(client):
    run_id = (await start(client))["run_id"]
    await client.get(f"/runs/{run_id}/events")
    await finished(run_id)
    trace = (await client.get(f"/runs/{run_id}/trace")).json()
    assert trace["run"]["id"] == run_id
    assert {"stage", "model"} <= {s["kind"] for s in trace["spans"]}
    assert trace["totals"]["model"]["count"] >= 3
    assert (await client.get("/runs")).json()[0]["id"] == run_id


async def test_crash_becomes_readable_error_event(api):
    async with await api({"Profile": "not json at all"}) as c:
        run_id = (await start(c))["run_id"]
        events = parse_sse((await c.get(f"/runs/{run_id}/events")).text)
        await finished(run_id)
        assert events[-1]["event"] == "error" and "retry" in events[-1]["data"]
        assert (await c.get(f"/runs/{run_id}")).json()["status"] == "error"


async def test_unknown_run_is_404_and_brief_is_validated(client):
    assert (await client.get("/runs/nope/events")).status_code == 404
    assert (await client.post("/runs", json={"brief": ""})).status_code == 422


async def test_interrupted_run_resumes_on_startup(store):
    """A run left 'running' by a crash continues from its saved stage, keeping its events."""
    from flatjai.agent.state import RunState
    from flatjai.tools.search import portal_results

    await store.create_session("s")
    saved = RunState(
        stage="read",
        round=1,
        profile={"budget_hkd_month": 15000, "campus": "HKUST"},
        queries_tried=["Hang Hau flat"],
        found=1,
        candidates=portal_results(
            [{"url": "https://hk.centanet.com/findproperty/en/detail/Test-Court-Block-1_ABC123"}]
        ),
    )
    await store.create_run(
        id="r1",
        session_id="s",
        brief="15k near HKUST",
        status="running",
        stage="read",
        state=saved.model_dump(mode="json"),
        model_profile="fake",
        model="fake",
    )
    for seq, stage in enumerate(["understand", "plan", "search"], start=1):
        await store.add_event("r1", seq, "state", {"stage": stage})

    runs = manager(store)
    assert await runs.resume_unfinished() == ["r1"]
    await asyncio.wait_for(asyncio.shield(runs.tasks["r1"]), 5)
    events = await store.events("r1")
    assert [e.seq for e in events] == list(range(1, len(events) + 1))  # numbering continues
    assert events[3].data["stage"] == "read" and events[-1].type == "done"
    assert any("resumed" in n for n in events[-1].data["notes"])
    assert (await store.get_run("r1")).status == "done"
