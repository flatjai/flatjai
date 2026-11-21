"""Request API.

POST /runs                 brief (+ client_key, + session_id to continue) -> run; agent runs in background
GET  /runs                 recent runs (run inspector index)
GET  /runs/{id}            one run: status, stage, brief, session
GET  /runs/{id}/events     server-sent events; resumes after Last-Event-ID (or ?after=N)
GET  /runs/{id}/trace      spans with timings, tokens, inputs/outputs (run inspector)
POST /parse                brief -> Profile (synchronous, for the brief form)
GET  /health               active model profile

Shared across runs: one HTTP client, one Fetcher (so the per-domain rate limit holds across all
users), one model connection with the server's concurrency limit, one database engine.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent.ablations import parse_ablations
from .agent.context import Toolbox
from .agent.events import Event
from .agent.runs import RunManager
from .agent.state import Budget
from .agent.understand import parse_brief
from .config import active_profile, settings
from .model_client import ModelClient
from .schemas import Profile
from .storage.blobs import BlobStore
from .storage.store import Store, make_engine
from .tools.cache import CachedFetcher, CachedSearcher
from .tools.fetch import Fetcher
from .tools.geocode import Geocoder
from .tools.otp import TransitRouter
from .tools.search import Searcher

HEARTBEAT_S = 15.0


def build_run_manager(
    http: httpx.AsyncClient, model: ModelClient, store: Store, ablate: frozenset[str] | None = None
) -> RunManager:
    """`ablate` (E2) defaults to FJ_ABLATE; the evaluation passes its own, since settings() is cached
    at import (a variable set afterwards in-process would be ignored)."""
    s = settings()
    blobs = BlobStore(s.data_dir / "blobs")
    fetcher = CachedFetcher(
        Fetcher(
            http,
            blobs,
            user_agent=s.user_agent,
            min_interval_s=s.min_fetch_interval_s,
            max_chars=s.page_text_max_chars,
        ),
        store,
        blobs,
        offline=s.fj_offline,
    )
    searcher = CachedSearcher(Searcher(http, s.searxng_url), store, offline=s.fj_offline)
    geocoder = Geocoder(http, store)
    router = TransitRouter(http, s.otp_url, store) if s.otp_url else None

    def make_tools(budget: Budget) -> Toolbox:
        return Toolbox(
            model=model.for_run(call_limit=budget.max_model_calls),
            searcher=searcher,
            fetcher=fetcher,
            geocoder=geocoder,
            router=router,
        )

    budget = Budget(
        max_seconds=s.run_max_seconds, ablate=parse_ablations(s.fj_ablate) if ablate is None else ablate
    )
    return RunManager(store, make_tools, budget)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if hasattr(app.state, "runs"):  # tests inject their own store and RunManager
        yield
        return
    engine = make_engine(settings().database_url)
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
        app.state.model = ModelClient(active_profile())
        app.state.store = Store(engine)
        app.state.runs = build_run_manager(http, app.state.model, app.state.store)
        await app.state.runs.resume_unfinished()
        sweep = asyncio.create_task(app.state.runs.sweep())
        yield
        sweep.cancel()
        await app.state.runs.shutdown()
    await engine.dispose()


app = FastAPI(title="FlatJai", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class BriefIn(BaseModel):
    brief: str = Field(min_length=1, max_length=2000)


class RunIn(BriefIn):
    client_key: str | None = Field(None, max_length=100, description="Same key twice -> same run")
    session_id: str | None = Field(None, max_length=32, description="Continue this conversation")


class RunOut(BaseModel):
    run_id: str
    session_id: str
    events_url: str


class RunInfo(BaseModel):
    id: str
    session_id: str
    brief: str
    status: str
    stage: str
    model_profile: str
    model: str
    started_at: datetime
    ended_at: datetime | None


@app.get("/health")
async def health() -> dict:
    p = active_profile()
    return {"status": "ok", "model_profile": p.name, "model": p.model, "base_url": p.base_url}


@app.post("/parse", response_model=Profile)
async def parse(body: BriefIn, request: Request) -> Profile:
    return await parse_brief(request.app.state.model.for_run(), body.brief)


@app.post("/runs", response_model=RunOut, status_code=201)
async def create_run(body: RunIn, request: Request, response: Response) -> RunOut:
    run, created = await request.app.state.runs.start(body.brief, body.client_key, body.session_id)
    if not created:
        response.status_code = 200
    return RunOut(run_id=run.id, session_id=run.session_id, events_url=f"/runs/{run.id}/events")


@app.get("/runs", response_model=list[RunInfo])
async def list_runs(request: Request, limit: int = 30) -> list:
    return await request.app.state.store.list_runs(min(limit, 200))


class TurnInfo(BaseModel):
    id: str
    brief: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    model: str
    homes: int


class Conversation(BaseModel):
    session_id: str
    started_at: datetime
    last_at: datetime
    runs: list[TurnInfo]


@app.get("/sessions", response_model=list[Conversation])
async def list_conversations(request: Request, limit: int = 30) -> list:
    """Conversations for the run inspector: a brief, the replies that continued it, and their runs."""
    return await request.app.state.store.conversations(min(limit, 100))


@app.get("/sessions/{session_id}")
async def get_conversation(session_id: str, request: Request, events: bool = True) -> dict:
    """One chat in one request: its turns in order, each with the stored events that rebuild it
    (the same history /runs/{id}/events replays). A turn still running streams the rest from its seq."""
    chat = await request.app.state.store.conversation(session_id, with_events=events)
    if chat is None:
        raise HTTPException(404, f"no session {session_id}")
    return jsonable_encoder(chat)


@app.get("/runs/{run_id}", response_model=RunInfo)
async def get_run(run_id: str, request: Request):
    run = await request.app.state.store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"no run {run_id}")
    return run


@app.get("/runs/{run_id}/trace")
async def run_trace(run_id: str, request: Request) -> dict:
    store: Store = request.app.state.store
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"no run {run_id}")
    spans = await store.spans(run_id)
    return {
        "run": RunInfo.model_validate(run, from_attributes=True).model_dump(mode="json"),
        "totals": await store.run_totals(run_id),
        "spans": [
            {
                "id": s.id,
                "parent_id": s.parent_id,
                "name": s.name,
                "kind": s.kind,
                "started_at": s.started_at.isoformat(),
                "ms": s.ms,
                "tokens_in": s.tokens_in,
                "tokens_out": s.tokens_out,
                "error": s.error,
                "attrs": s.attrs,
            }
            for s in spans
        ],
    }


@app.get("/runs/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    after: int = 0,
    last_event_id: int | None = Header(None),
) -> StreamingResponse:
    bus = await request.app.state.runs.bus(run_id)
    if bus is None:
        raise HTTPException(404, f"no run {run_id}")
    start = last_event_id if last_event_id is not None else after

    async def stream() -> AsyncIterator[str]:
        yield "retry: 2000\n\n"
        async for event in bus.subscribe(after=start, heartbeat_s=HEARTBEAT_S):
            if await request.is_disconnected():
                return
            yield ": ping\n\n" if event is None else sse(event)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


def sse(event: Event) -> str:
    return f"id: {event.seq}\nevent: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
