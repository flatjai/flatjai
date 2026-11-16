# FlatJai (揾樓仔)

An agentic home-search assistant for students in Hong Kong. A student writes a plain-language brief
("HK$9,000 a month, own room, under 40 minutes to HKUST, from January"). FlatJai returns a shortlist
showing the real monthly and move-in cost, the commute to campus, the source of each home and why it fits.

Course project for CSIT6000V (HKUST, Fall 2026). Runs on a local model in development and on Qwen3.8-27B (vLLM) on TACC.

## Status
M2: the full agent loop runs on live listings. Understand (asks one question if budget or campus is
missing) -> Plan -> Search -> Read -> Match -> Reflect (re-plan or read more) -> Answer, streamed to
the UI over server-sent events. Every figure is checked against its page and every hard limit in
code; the answer's claims are checked against the facts. Runs, events and traces are stored in
Postgres, interrupted runs resume, and every run can be inspected at `/runs`.
Commute is an offline estimate (MTR or bus, decision 0005), shown as "~N min". Not yet: OpenTripPlanner; frozen snapshot, record/replay, query suite and CI (M4).

## Run it
Needs [uv](https://docs.astral.sh/uv/), Docker, Node + pnpm and [Ollama](https://ollama.com)
(`brew install ollama && brew services start ollama && ollama pull qwen3:8b`).

```bash
cp .env.example .env    # on a laptop model, set RUN_MAX_SECONDS=240
make up                 # Postgres + SearXNG
make model              # qwen3:8b with a 16K context (Ollama defaults to 4K)
make test               # 96 tests, no model, network or Postgres needed
make check-model        # the model returns a valid Profile
make eval-understand    # 6 briefs -> expected profiles on the active model
make dev                # migrates, then API on http://localhost:8000/docs
make web                # UI on http://localhost:3000, run inspector on /runs
```

API: `POST /runs {brief, client_key, session_id?}` -> run and session ids; `GET /runs/{id}/events`
streams `state`, `progress`, `card` and one of `done`/`clarify`/`error` (resumes with `Last-Event-ID`);
`GET /runs/{id}/trace` returns the spans. A reply or refinement is a new run in the same session.

Switch to TACC: write `SERVICE_BASE_URL` into `deploy/tacc/server-url.txt`, set `FJ_MODEL=tacc`.

## Layout
| Path | What |
|---|---|
| `backend/` | FastAPI app, agent loop, model client, tools |
| `web/` | Next.js UI: brief, live progress, verified cards |
| `data/` | listing snapshots and labels |
| `eval/` | test briefs, baselines, scoring |
| `deploy/tacc/` | TACC job config |
| `deploy/searxng/` | SearXNG settings (JSON API on) |
| `docs/` | decisions (`decisions/`) and `BUILD_LOG.md` |

## Backend modules
| Module | Role |
|---|---|
| `model_client.py` | One OpenAI-compatible client: JSON-schema typed calls, one repair retry, max_tokens, call budget, spans (5) |
| `agent/loop.py`, `agent/state.py` | The seven-stage state machine, budgets, saved state (4) |
| `agent/understand.py` | Brief -> Profile, numbers grounded in the brief; whether to ask (4) |
| `agent/plan.py`, `agent/gather.py`, `agent/read.py` | Plan queries, search and expand list pages, fetch + extract + verify (4, 6) |
| `agent/match.py`, `agent/reflect.py`, `agent/answer.py` | Hard checks, duplicates, relaxations; read more / re-plan / answer; ranked, checked answer (4) |
| `agent/verify.py` | Every extracted fact must match a span on the fetched page (1, 10) |
| `agent/events.py`, `agent/runs.py` | Numbered, persisted events; runs, sessions, idempotency, resume (9, 10) |
| `tools/search.py`, `tools/fetch.py`, `tools/extract.py`, `tools/cost.py` | Tools with typed contracts (6) |
| `tools/cache.py`, `storage/` | Page, search and extraction caches; Postgres store; blob store (7, 8) |
| `agent/ask.py` | What to ask the agent: the listing's open questions as a copyable message (decision 0006) |
| `tools/preview.py` | Rent and district from list-page cards and listing pages: skip what surely cannot fit before the model (decision 0005) |
| `tools/geocode.py`, `tools/transit.py` | Place a home (Address Lookup Service) and estimate its commute by MTR or bus (6, decision 0005) |
| `data/mtr.json`, `scripts/build_mtr.py` | MTR stations and lines from MTR Open Data and Wikipedia, built once |
| `tracing.py` | Spans for stages, model and tool calls -> run inspector (13) |

Decisions are in `docs/decisions/`.
