# FlatJai (揾樓仔)

An agentic home-search assistant for students in Hong Kong. A student writes a plain-language brief
("HK$9,000 a month, own room, under 40 minutes to HKUST, from January"). FlatJai returns a shortlist
showing the real monthly and move-in cost, the commute to campus, the source of each home and why it fits.

Course project for CSIT6000V (HKUST, Fall 2026). Runs on a local model in development and on Qwen3.8-27B (vLLM) on TACC.

## Status
M0: backend skeleton. Model client with local/tacc profiles, typed `parse_brief` call, cost tool, Postgres in Compose. No UI, search or commute yet.

## Run it
Needs [uv](https://docs.astral.sh/uv/), Docker, and a local OpenAI-compatible model server
(Ollama: `ollama pull qwen3:8b`, or LM Studio; set `base_url` in `backend/models.yaml`).

```bash
cp .env.example .env
make up            # Postgres
make test          # unit tests, no model needed
make check-model   # M0 check: the model returns a valid Profile
make dev           # API on http://localhost:8000/docs
```

Switch to TACC: write `SERVICE_BASE_URL` into `deploy/tacc/server-url.txt`, set `FJ_MODEL=tacc`.

## Layout
| Path | What |
|---|---|
| `backend/` | FastAPI app, agent loop, model client, tools |
| `web/` | UI (not yet) |
| `data/` | listing snapshots and labels |
| `eval/` | test briefs, baselines, scoring |
| `deploy/tacc/` | TACC job config |
| `docs/` | decisions (`decisions/`) and `BUILD_LOG.md` |
