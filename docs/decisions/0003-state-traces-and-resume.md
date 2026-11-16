# 0003 Runs, events and traces live in Postgres; runs resume after a crash

Date: 2026-11-16 · Status: accepted

## Decision
- Tables per design section 7 (`storage/models.py`, Alembic migrations in `backend/migrations/`):
  sessions, messages, runs, events, pages, listings, shortlist_items, spans, cache.
- The agent loop is a state machine (`agent/loop.py`). After every stage it saves `RunState` (JSON)
  and the finished spans. Every SSE event is written before subscribers see it.
- On startup, runs still marked `running` resume from their saved stage with their event history,
  so sequence numbers continue and a connected browser just sees more events. A shutdown leaves
  runs `running` on purpose.
- The tracer (`tracing.py`) keeps the current span in a context variable: the model client and the
  tools open spans without being handed a tracer, and asyncio tasks inherit their parent span.
- Extractions are unique per (page hash, extractor version, model): the table is the extraction
  cache, and bumping `EXTRACTOR_VERSION` invalidates exactly the stale rows.
- Unit tests use a SQLite file per test (not in-memory: one shared connection interleaves the
  transactions of concurrent runs and lost a message in a test).

## Consequences
The run inspector (`/runs/{id}`) is just a view of `spans`. A resumed run gets a fresh time budget.
