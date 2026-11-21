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


async def test_conversations_group_a_brief_with_its_replies(client):
    first = await start(client, brief="flat near campus")
    await client.get(f"/runs/{first['run_id']}/events")
    second = await start(client, brief="HKUST, 15k", session_id=first["session_id"])
    await client.get(f"/runs/{second['run_id']}/events")
    other = await start(client, brief="studio near HKU")
    await client.get(f"/runs/{other['run_id']}/events")
    for r in (first, second, other):
        await finished(r["run_id"])
    convos = (await client.get("/sessions")).json()
    assert [c["session_id"] for c in convos] == [other["session_id"], first["session_id"]]  # newest first
    assert [r["brief"] for r in convos[1]["runs"]] == ["flat near campus", "HKUST, 15k"]  # in order
    assert convos[1]["runs"][0]["homes"] >= 1


async def test_one_conversation_with_its_events_in_one_request(client):
    """Reopening a chat is one request: every turn in order, each with the events to rebuild it."""
    first = await start(client, brief="flat near campus")
    await client.get(f"/runs/{first['run_id']}/events")
    second = await start(client, brief="HKUST, 15k", session_id=first["session_id"])
    await client.get(f"/runs/{second['run_id']}/events")
    for r in (first, second):
        await finished(r["run_id"])

    chat = (await client.get(f"/sessions/{first['session_id']}")).json()
    assert chat["session_id"] == first["session_id"]
    assert [t["id"] for t in chat["runs"]] == [first["run_id"], second["run_id"]]
    streamed = parse_sse((await client.get(f"/runs/{second['run_id']}/events")).text)
    stored = chat["runs"][1]["events"]
    # the same history the stream replays
    assert [e["type"] for e in stored] == [e["event"] for e in streamed]
    assert [e["seq"] for e in stored] == sorted(e["seq"] for e in stored)
    assert stored[-1]["type"] == "done" and chat["runs"][1]["homes"] >= 1

    bare = (await client.get(f"/sessions/{first['session_id']}?events=false")).json()
    assert all("events" not in t for t in bare["runs"])
    assert (await client.get("/sessions/nope")).status_code == 404


async def _running_run(store, run_id="r1", **values):
    if await store.get_session("s") is None:
        await store.create_session("s")
    await store.create_run(
        id=run_id,
        session_id="s",
        brief="15k near HKUST",
        status="running",
        stage="understand",
        state={},
        model_profile="fake",
        model="fake",
        **values,
    )


async def test_a_run_another_process_is_executing_is_not_taken_over(store):
    """A dev server starting beside an evaluation used to resume the evaluation's live run, and two
    processes then wrote the same run's events (duplicate run_id, seq)."""
    from flatjai.storage.models import utcnow

    await _running_run(store, owner="eval-process", heartbeat_at=utcnow())
    runs = manager(store)
    assert await runs.resume_unfinished() == []
    assert (await store.get_run("r1")).owner == "eval-process"


async def test_a_run_whose_owner_went_quiet_is_resumed_and_claimed(store):
    from datetime import timedelta

    from flatjai.storage.models import utcnow

    await _running_run(store, owner="crashed", heartbeat_at=utcnow() - timedelta(minutes=5))
    runs = manager(store)
    assert await runs.resume_unfinished() == ["r1"]
    await asyncio.wait_for(asyncio.shield(runs.tasks["r1"]), 5)
    run = await store.get_run("r1")
    assert run.owner == runs.owner and run.status == "done"


async def test_only_one_of_two_processes_claims_a_run(store):
    from datetime import timedelta

    from flatjai.storage.models import utcnow

    await _running_run(store)  # no heartbeat: released by a clean stop
    stale_before = utcnow() - timedelta(seconds=45)
    got = await asyncio.gather(
        store.claim_run("r1", "a", stale_before), store.claim_run("r1", "b", stale_before)
    )
    assert sorted(got) == [False, True]


async def test_a_clean_stop_releases_the_run_for_the_next_process(store):
    from flatjai.storage.models import utcnow

    await _running_run(store, owner="old-server", heartbeat_at=utcnow())
    await store.release_run("r1", "someone-else")  # only the owner may release it
    assert (await store.get_run("r1")).heartbeat_at is not None
    await store.release_run("r1", "old-server")
    assert await manager(store).resume_unfinished() == ["r1"]


async def test_new_runs_carry_their_owner_and_a_heartbeat(store):
    runs = manager(store)
    run, _ = await runs.start("Studio near HKU, 15k")
    stored = await store.get_run(run.id)
    assert stored.owner == runs.owner and stored.heartbeat_at is not None
    await runs.shutdown()
