# FlatJai (揾樓仔)

**An AI agent that finds a home in Hong Kong for a student, and never makes up a number.**

A student writes what they need in plain words: *"Own room, max HK$9,000 a month, under 40 minutes
to HKUST, from January."* FlatJai searches the listing sites, reads each listing, and returns a
short list of real homes. Each one shows its true monthly and move-in cost, the commute to campus
on an actual bus and MTR route, where the listing came from, and why it fits.

<table>
  <tr>
    <td width="50%"><img src="docs/images/live-progress.png" alt="FlatJai working through a brief: understood, planned, searched, read 22 listings, 4 homes fit"></td>
    <td width="50%"><img src="docs/images/commute-map.png" alt="A shortlisted room: HK$5,100 a month, 38 minutes to HKUST, its route on a map, every limit checked"></td>
  </tr>
  <tr>
    <td>Every step is streamed live while it reads the market.</td>
    <td>A result: rent, real cost to move in, the route to campus, and which of your limits it meets.</td>
  </tr>
</table>

Built for CSIT6000V (Advanced AI Computing and Systems, HKUST, Fall 2026). It runs on a laptop
with Qwen3 8B, and on Qwen3.8-27B on TACC GPUs.

This README has two parts, as the artifact guidelines ask:
**[Getting Started Instructions](#getting-started-instructions)** (set up and check that the system
works, about 30 minutes plus downloads) and **[Detailed Instructions](#detailed-instructions)**
(rerun the evaluation and compare with the reported results).

## What the artifact claims

The model makes the decisions (what the student means, where to look, what to read next, how to
explain the choice). **The facts come from tools, and code checks them:**

- every rent, size and address must be quoted from the listing page it came from;
- the monthly and move-in costs are computed by code (deposit, first month, agent fee);
- commutes are real journeys from OpenTripPlanner over Hong Kong's bus, minibus and MTR data;
- "fits your budget" and "under 40 minutes" are decided by code, never by the model;
- any sentence in the explanation whose number is not one of that home's facts is removed.

On a frozen snapshot of the market (20 briefs in 7 categories, scored by independent code), the
artifact supports these claims:

| | Claim | Evidence |
|---|---|---|
| **C1** | FlatJai shows no invented facts (0%) and keeps every shown home within the student's limits (100%), while the model alone invents 85% of its facts and one search plus an answer invents 44%. | E1, Table 1 |
| **C2** | The tools carry the honesty: letting the model state costs and commutes puts 24% of shown homes over a limit and understates every move-in cost. Reflection and de-duplication add smaller gains. | E2, Table 2 |
| **C3** | C1 and C2 hold on a larger model: Qwen 27B on TACC also shows 0% invented facts and 100% within limits. | E3, Table 3 |
| **C4** | A brief takes a median of 26 s on a laptop (8B) and 19 s on TACC (27B), under the 90 s target. | Tables 1 and 3 |

| | Invented facts | Homes within the student's limits | Brief handled well |
|---|---|---|---|
| The model alone (B0) | 85% | 100% (of 35 homes, mostly invented) | 12% |
| One search, then answer (B1) | 44% | 71% | 15% |
| **FlatJai, Qwen 8B** | **0%** | **100%** | **100%** |
| **FlatJai, Qwen 27B** | **0%** | **100%** | **100%** |

## How it works

```mermaid
flowchart TB
    student([Student]) -->|brief| web[Web UI<br/>Next.js]
    web -->|POST /runs| api[API<br/>FastAPI]
    api -.->|live events, SSE| web
    api --> agent[Agent loop<br/>7 stages]
    agent -->|typed JSON calls| model[(Qwen 8B on Ollama<br/>or Qwen 27B on vLLM)]
    agent --> tools
    agent --> pg[(Postgres<br/>runs, traces, cache)]
    subgraph tools [Tools]
        direction LR
        searxng[SearXNG<br/>search]
        sites[Listing sites<br/>robots.txt respected]
        geo[HK address<br/>lookup]
        otp[OpenTripPlanner<br/>bus, minibus, MTR]
    end
    grafana[Grafana<br/>metrics] --> pg
```

Each brief runs through seven stages. The run is saved after every stage, so it can resume after
a crash, and the browser can reconnect without losing anything.

```mermaid
stateDiagram-v2
    [*] --> Understand
    Understand --> Plan
    Understand --> [*]: budget or campus missing, ask once
    Plan --> Search
    Search --> Read
    Read --> Match
    Match --> Reflect
    Reflect --> Read: read more
    Reflect --> Plan: search elsewhere
    Reflect --> Answer: enough homes
    Answer --> [*]
```

| Stage | What happens |
|---|---|
| Understand | The brief becomes a typed profile. If the budget or campus is missing, the agent asks one question. |
| Plan | The model picks areas and search terms within reach of the campus. |
| Search | SearXNG finds listing pages on sites FlatJai is allowed to read. |
| Read | Each page is fetched politely, the listing extracted with a quote for every field, the quotes checked against the page, the cost computed and the commute routed. |
| Match | Code checks every hard limit and removes duplicates listed on several sites. |
| Reflect | Enough good homes? If not, read more or search somewhere else. |
| Answer | The model ranks and explains; code removes any claim it cannot back. |

The full design (data flow, storage, resume, tracing, code map) is in
[docs/architecture.md](docs/architecture.md).

---

# Getting Started Instructions

Goal: set FlatJai up from a fresh clone and run one brief end to end on the frozen snapshot, in
about 30 minutes of hands-on time. Most of the wait is downloading the model (~5 GB) and Docker
images. Nothing here contacts a listing site.

## Prerequisites

| | Minimum | Notes |
|---|---|---|
| OS | macOS, Linux, or Windows 11 with WSL2 | On Windows everything runs inside WSL2 (Ubuntu) |
| Memory | 16 GB RAM | The 8B model uses ~6 GB; Docker needs ~6 GB with the route planner |
| Disk | ~15 GB free | Model 5 GB, Docker images, the Hong Kong map and transit data |
| GPU | not needed | Apple Silicon and NVIDIA GPUs make the model faster |
| Network | needed for setup only | The evaluation itself runs offline on the snapshot |

Software: [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/),
[Node.js](https://nodejs.org) 20.9 or newer, zstd, git and [Ollama](https://ollama.com).

<details open>
<summary><b>macOS</b> (with Homebrew)</summary>

```bash
brew install --cask docker        # then open Docker Desktop once
brew install uv node zstd git ollama
```
</details>

<details>
<summary><b>Linux</b> (Ubuntu or Debian)</summary>

```bash
# Docker Engine: https://docs.docker.com/engine/install/ubuntu/ , then let your user run it:
sudo usermod -aG docker $USER && newgrp docker
sudo apt update && sudo apt install -y zstd git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://ollama.com/install.sh | sh
# Node 20.9 or newer: https://nodejs.org/en/download
```
</details>

<details>
<summary><b>Windows</b> (WSL2)</summary>

1. In PowerShell as administrator: `wsl --install -d Ubuntu`, then restart.
2. Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) and turn on
   *Settings > Resources > WSL integration* for Ubuntu.
3. Open the Ubuntu terminal and follow the **Linux** steps above, skipping Docker Engine.
4. Clone the repository inside WSL (for example in `~/flatjai`), not under `/mnt/c`: it is much faster.
</details>

## Setup (one command)

```bash
git clone https://github.com/BhanuRana/flatjai.git
cd flatjai
./setup.sh
```

`setup.sh` checks every tool and tells you how to install anything missing. It then:

1. creates `.env`;
2. installs the Python and web dependencies;
3. starts Postgres, SearXNG, OpenTripPlanner and Grafana in Docker;
4. loads the frozen market snapshot (`data/snapshot-2026-11-20.tar.zst`, 460 listing pages);
5. builds the Hong Kong transit graph (~2 min);
6. downloads the model (~5 GB), checks that it returns valid structured output, and runs the tests.

It is safe to run again, and it never overwrites your database. It ends with
`FlatJai is set up.` and the test line `194 passed`.

| Short on memory or disk? | |
|---|---|
| `./setup.sh --no-otp` | Skip the route planner (saves ~4 GB of Docker memory). Commutes use an MTR-based estimate, so commute minutes differ from the reported runs. |
| `./setup.sh --no-model` | Skip the local model, then point FlatJai at another server (see [Models](#models)). |

## A small end-to-end example

**Step 1. Tests** (no model, network or database needed, ~20 s):

```bash
make test
```

Expected: the last line reads `194 passed`.

**Step 2. One brief through the whole agent, on the snapshot** (~1 minute). The brief is the first
case in the suite: *"Own room, max HK$9,000 a month, under 40 min to HKUST, from January, quiet"*.

```bash
make up                                   # Postgres, SearXNG, OTP and Grafana (setup.sh left them running)
cd backend
FJ_OFFLINE=1 uv run python ../eval/run_suite.py --system flatjai --cases std-hkust-own-room-9k --tag smoke
```

Expected output (times vary with the machine):

```
flatjai on local (flatjai-qwen3-8b), offline=True, 1 cases x 1 -> eval/results/<stamp>-flatjai-smoke.jsonl
  [0] std-hkust-own-room-9k          37.4s  homes=4
wrote .../eval/results/<stamp>-flatjai-smoke.jsonl
```

The agent understood the brief, planned, searched the snapshot, read the listings, checked every
limit and answered with 3 to 5 homes (4 in the reported runs, with commutes of 35 to 38 minutes).

**Step 3. Score it with the independent checker** (~10 s):

```bash
uv run python ../eval/score.py ../eval/results/*-flatjai-smoke.jsonl --out /tmp/flatjai-smoke.md
```

Expected: the report printed to the terminal shows, for `flatjai`, **Constraint satisfaction
100%**, **Invented facts 0%**, **Invented listings 0%**, **Correct ask/no-ask 100%** and **Outcome
ok 100%**. If you see these, the system works end to end. (`--out` keeps the shipped
`eval/results/report.md` untouched.)

**Step 4 (optional). The app in a browser:**

```bash
cd .. && ./run.sh local --offline         # services, API and web in one terminal; Ctrl-C stops
```

Open http://localhost:3000 and tap one of the example briefs. Expected: the stages tick by live
(Understood, Planned, Searched, Read N listings), and within about a minute a shortlist of cards
appears, each with rent, move-in cost, commute and the limits it meets. **Inspect** on the answer
shows every stage, model call and tool call of the run.

---

# Detailed Instructions

## Experiments and where their results are

| Experiment | Supports | What it runs | Command | Time (laptop, 8B) | Output | In the report |
|---|---|---|---|---|---|---|
| **E1** systems | C1, C4 | B0, B1 and FlatJai over the 20 briefs | `make eval` (`REPEAT=3` as reported) | ~15 min per repeat | `eval/results/report.md` | Table 1, Figure 1 |
| **E2** ablations | C2 | FlatJai with one part off: `no_reflect`, `no_dedup`, `model_facts` | `make ablate` | ~30 min | `eval/results/report.md` (E1 and E2 in one table) | Table 2, Figure 1 |
| **E3** 27B on TACC | C3, C4 | FlatJai, B1, B0 and `model_facts` on Qwen3.8-27B | `./run.sh tacc` | ~15 min plus queueing | `eval/results/report-tacc.md` | Table 3 |
| Understand stage | (seed check) | briefs to expected profile fields | `make eval-understand` | ~2 min | terminal | – |

Table 1 is the E1 table in [docs/evaluation.md](docs/evaluation.md), Table 2 the E2
table ("E2 results"), Table 3 the E3 table, and Figure 1 is `docs/images/quality.png` (within
limits, invented facts and outcome for every system and ablation, on 8B and 27B). The full tables
with 95% bootstrap intervals and per-category breakdowns are in `eval/results/report.md` and
`eval/results/report-tacc.md`. Failures found during development, each with its fix and a
before/after measurement, are in [docs/failure-analysis.md](docs/failure-analysis.md).

## Test cases

`eval/suite.yaml` holds 20 reviewed briefs in 7 categories: standard requests (6), missing
information (3), impossible requests (3), Chinese and mixed-language briefs (3), ambiguous
locations (2), an adversarial brief (1) and multi-turn refinements (2). Each case lists the turns
the student types, the student's hard limits as we read them (`truth`) and what a good answer does
(`expect`). Cases 21 to 50 are drafts (`status: draft`), not yet reviewed or in the snapshot;
`make eval` skips them.

## Data

`data/snapshot-2026-11-20.tar.zst` (9 MB) is a frozen copy of the market: every listing page,
search result, extraction, geocode and OpenTripPlanner journey FlatJai cached during one live pass.
`make snapshot-import` loads it into Postgres (`setup.sh` does this once). With `FJ_OFFLINE=1`
FlatJai reads only this cache: no listing site is contacted, and every run sees the same market.
The raw run files behind every reported number are in `eval/results/*.jsonl`.

## Configuration

| Setting | Where | Reported runs | Meaning |
|---|---|---|---|
| `FJ_MODEL` | `.env` | `local` (E1, E2), `tacc` (E3) | Model profile from `backend/models.yaml` |
| `FJ_OFFLINE` | set by `make eval` / `make ablate` | `1` | Snapshot only |
| `RUN_MAX_SECONDS` | `.env` | 240 on the laptop, 90 on TACC | Time budget per brief |
| `OTP_URL` | `.env` | `http://localhost:8080` | Real journeys; unset means the MTR estimate |
| `SYSTEMS` | `make` variable | `b0 b1 flatjai` | Which systems `make eval` runs |
| `REPEAT` | `make` variable | 3 for E1, 1 for E2 and E3 | Repeats of the suite |
| `ABLATIONS` | `make` variable | `no_reflect no_dedup model_facts` | Which parts `make ablate` switches off |

Model profiles: `local` is Qwen3 8B (16K context, thinking off) on Ollama, built by `make model`;
`tacc` is Qwen3.8-27B (AWQ INT4) on vLLM. All systems use the same profile, so each comparison is
about the system, not the model.

## Reproduce the results, step by step

**1. Rescore the shipped runs** (~1 minute; checks the scorer and the snapshot, no model needed):

```bash
cd backend
uv run python ../eval/score.py \
  ../eval/results/20261120-1544-b0-offline.jsonl ../eval/results/20261120-1550-b1-offline.jsonl \
  ../eval/results/20261120-1637-flatjai-offline.jsonl \
  ../eval/results/20261121-0900-flatjai-no_reflect-offline.jsonl \
  ../eval/results/20261121-1022-flatjai-no_dedup-offline.jsonl \
  ../eval/results/20261121-1033-flatjai-model_facts-offline.jsonl --out /tmp/report-e1-e2.md
uv run python ../eval/score.py ../eval/results/2026*-tacc.jsonl --out /tmp/report-tacc.md
```

Expected: the same numbers as `eval/results/report.md` and `eval/results/report-tacc.md`.

**2. Rerun E1 on your machine** (fresh model calls on the snapshot):

```bash
cd ..
make eval REPEAT=3          # or REPEAT=1 for a quicker run; writes eval/results/report.md
```

**3. Rerun E2:**

```bash
make ablate                 # the three ablations, then one report with E1
make ablate ABLATIONS=model_facts      # one ablation only
```

**4. Rerun E3 on Qwen 27B** (needs a TACC account and the course's model-serving kit; one-time
setup in [docs/tacc.md](docs/tacc.md)):

```bash
./run.sh tacc               # bundles FlatJai and the snapshot, starts the vLLM service, runs the
                            # suite inside TACC, downloads and scores the results, cancels the service
```

The 27B service is reachable only from inside the cluster, so the suite goes to TACC as a batch
job. Without TACC access, step 1 rescores the shipped E3 runs.

**5. Look at the runs** (optional): `make obs` loads the TACC runs and the scored suite into
Grafana at http://localhost:3001, next to your own runs.

## What the scorer checks

All checks are code in `eval/score.py`, independent of the agent's own checks, and pinned by
`backend/tests/test_eval_score.py`:

| Metric | Definition |
|---|---|
| Constraint satisfaction | Shown homes with no limit broken / shown homes. An unknown fact (no bedroom count) is counted separately. |
| All limits confirmed | Shown homes with every limit known and met / shown homes. |
| Invented facts | Shown rents and sizes not on the home's page in the snapshot, plus summary figures that match no card, budget or relaxation / all such figures. |
| Invented listings | Shown homes whose page is not in the snapshot / shown homes. |
| Correct ask/no-ask | The first turn asks a question exactly when the brief is missing something essential. |
| Outcome ok | Enough homes; for an impossible brief, no home that breaks a limit and concrete relaxations. |

## Expected variation

- **The model is not deterministic.** A rerun on the snapshot gives the same market, but the model
  may plan or rank differently. What should hold on every run: invented facts 0%, invented
  listings 0%, constraint satisfaction 100% for FlatJai, and B0 and B1 far worse. Outcome ok,
  "all limits confirmed" (52% reported, interval 40 to 64%) and homes per brief move by a few points.
- **Speed depends on the machine.** The reported 26 s per brief is a 16 GB Apple Silicon laptop
  with cached extractions; slower machines may hit `RUN_MAX_SECONDS` on a few briefs (raise it in
  `.env`). Close other heavy apps, and restart Ollama if tokens per second drop.
- **Without OpenTripPlanner** (`--no-otp`) commutes come from the MTR estimate, so commute minutes
  and a few commute-limit decisions differ.
- **27B results** depend on the shared TACC service and its queue; times include its load.

## Known limitations

- 20 reviewed briefs, so the intervals are wide (see `eval/results/report.md`). 30 more are drafted.
- Commutes are checked against OpenTripPlanner on open data (MTR times fitted to the timetable in
  `scripts/build_mtr_gtfs.py`), not against journeys timed by hand.
- B0 and B1 commutes are the model's own claims and are scored as claimed.
- "All limits confirmed" is about 50% because many pages do not say whether a home is a room or
  how many bedrooms a flat has; FlatJai shows these as "?" and suggests asking.
- Precision@5 against hand labels and an LLM-judged explanation score are not built.
- A live run (not offline) reads today's listing sites, so its results differ from the snapshot.
  Live mode fetches at most one page every 2 s per site and respects robots.txt.
- Nothing in the artifact is destructive: it writes only to its own Docker volume, `.env`,
  `data/blobs` and `eval/results/`.

---

# Using FlatJai

## Start it

```bash
./run.sh local              # the app on this machine (Ctrl-C stops it)
./run.sh local --offline    # the same, answering from the frozen snapshot only
./run.sh local --tacc      # the app here, with Qwen 27B on TACC through an SSH tunnel
./run.sh tacc               # the evaluation suite on Qwen 27B inside TACC
```

`./run.sh local` starts the Docker services, the API and the web app in one terminal (`make local`
does the same). To run the API and the web app in separate terminals instead, use `make dev` and
`make web`.

| Open | What |
|---|---|
| http://localhost:3000 | FlatJai: write a brief, or tap one of the examples |
| http://localhost:3001 | Metrics dashboard (Grafana, no login) |
| http://localhost:8000/docs | API reference |

Stop the Docker services with `make down`; your data stays in the Docker volume.

## Models

The model is chosen by `FJ_MODEL` in `.env`, from the profiles in `backend/models.yaml`:

| Profile | Model | Where |
|---|---|---|
| `local` (default) | Qwen3 8B, 16K context | Ollama on your machine (`make model` builds it) |
| `tacc` | Qwen3.8-27B, AWQ INT4 | vLLM on TACC GPUs, run as a batch job: [docs/tacc.md](docs/tacc.md) |

Any OpenAI-compatible server works (LM Studio, vLLM, llama.cpp server): add a profile with its
`base_url` and `model`, and set `FJ_MODEL` to its name. `make check-model` confirms the model returns
valid structured output.

## See what the agent did

Every stage, model call and tool call is recorded. Open **Inspect** on any answer to see one run:

![Run inspector: each stage, model call and tool call on a timeline, with timings and tokens](docs/images/run-inspector.png)

The **Metrics** dashboard (Grafana, http://localhost:3001) covers every run, with Qwen 8B and 27B
side by side: outcomes, time per brief and per stage, model and tool latency, cache hits, and the
scored evaluation.

![Grafana dashboard: runs, outcomes, time per brief, model calls and cache hits for 8B and 27B](docs/images/grafana.png)

Figure 1, the evaluation at a glance:

![Within limits, invented facts and outcome for every system and ablation, on 8B and 27B](docs/images/quality.png)

## Commands

| Command | What it does |
|---|---|
| `./setup.sh` | Everything from a fresh clone (safe to rerun) |
| `./run.sh local` / `make local` | The app here: services, API and web in one terminal (`--offline` / `OFFLINE=1`: snapshot only) |
| `./run.sh local --tacc` | The app here with Qwen 27B on TACC through an SSH tunnel ([docs/tacc.md](docs/tacc.md); VPN needed) |
| `./run.sh tacc` / `make tacc` | The suite on Qwen 27B inside TACC, scored and loaded into the dashboard |
| `make up` / `make down` | Start or stop Postgres, SearXNG, Grafana (and OpenTripPlanner once built) |
| `make dev` / `make web` | API on :8000 with reload / app on :3000 |
| `make test` | 194 tests: no model, network or database needed |
| `make lint` | Ruff, ESLint and TypeScript |
| `make check-model` | The active model returns a valid typed reply |
| `make eval` / `make ablate` | The suite on the snapshot; ablations |
| `make eval-score` | Rescore the latest offline result of each system |
| `make obs` | Load TACC runs and evaluation scores into the dashboard |
| `make otp-graph` | Rebuild the transit graph (~2 min) |
| `make snapshot` / `make snapshot-import` | Freeze the current cache / load a snapshot |

## Project layout

```
backend/     FastAPI app and the agent: agent/ (one module per stage), tools/, storage/, tests/
web/         Next.js app: brief, live progress, result cards with maps, run inspector
eval/        query suite, baselines, scorer, results
infra/       SearXNG, OpenTripPlanner, Ollama, Grafana, and the TACC job
scripts/     snapshot export and import, experiment runners, MTR data builders
data/        the frozen market snapshot
docs/        architecture, evaluation, failure analysis, TACC guide, design decisions, build log
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `setup.sh` says a port is in use | Something else holds 5432, 8888, 8080 or 3001. Stop it, or change the left-hand port in `compose.yaml`. |
| Docker crashes or OTP never becomes healthy | Give Docker at least 6 GB (Docker Desktop > Settings > Resources), or run `./setup.sh --no-otp`. |
| Briefs hit the time limit | The model is slow on this machine: close other heavy apps, restart Ollama, or raise `RUN_MAX_SECONDS` in `.env`. Tokens per second are on the dashboard. |
| The app shows "Lost the connection" | `make dev` is not running, or stopped with an error: check its terminal. |
| Old styles after pulling changes | Stop `make web`, run `rm -rf web/.next`, start it again. |

## Documentation

- [Architecture](docs/architecture.md): the system, one run end to end, the agent loop, where each fact comes from
- [Evaluation](docs/evaluation.md): suite, baselines, snapshot, metrics, results of E1, E2 and E3
- [Failure analysis](docs/failure-analysis.md): what went wrong during development and the fix for each
- [TACC](docs/tacc.md): Qwen 27B on the course GPUs, for the suite (E3) or the app through a tunnel
- [Design decisions](docs/decisions/): one short record per decision
- [Build log](docs/build-log.md): dated development journal
