# 0008 Demo deployment: a static site that replays real runs, live only when Bhanu turns it on

Date: 2026-11-20 · Status: planned (deploy after M4/M5; nothing here is built yet)

## The lock
**Recurring cost: HK$0.** No paid service, no card on file, nothing that bills by usage. A paid
option needs Bhanu's explicit yes first, and then it gets a budget alert and a hard cap before it
goes live. This holds even if a free tier looks generous, because a public URL can be abused at any
hour. The design below stays at $0 because nothing public ever calls a model or scrapes a site.

## Why not host everything
The full stack is FastAPI, Postgres, SearXNG, OpenTripPlanner (~3 GB RAM) and a model. Free tiers
(Render, Fly, Cloud Run) cannot hold OTP's graph, and no free tier serves an LLM. A public live
search box would also let strangers make FlatJai scrape listing sites, which our pacing and site
terms do not allow at scale.

## Plan: two modes, one UI
### 1. Showcase mode, always on, $0: GitHub Pages
- Where it lives: a Pages URL comes from the owner, not the repo. This repo pushed as `flatjai` under
  Bhanu's account publishes at `https://bhanurana.github.io/flatjai/` (a project site: the static
  build sets `basePath: "/flatjai"`). For `https://flatjai.github.io` exactly, create a free GitHub
  organisation named `flatjai` (the name was free on 2026-11-20) and host the repo, or a small
  `flatjai.github.io` repo for the built site, there. Either way costs nothing.
- GitHub Pages on a free plan needs a public repo. Before making it public: review history for
  private details (CLAUDE.md names coursework paths and the TACC user; `.env` is ignored), or keep
  the code private and publish only the built site from a separate public repo.
- The Next.js app is built as a static export (`output: "export"`) and deployed by a GitHub Action
  on push (free for public repos).
- The site shows **recorded chats**: real runs from the M4 frozen snapshot, saved as the same JSON
  that `GET /sessions/{id}` returns (one file per chat, plus an index). The page already rebuilds a
  chat from that JSON (`buildChat`), so the replay is the real product, with cards, checks, commute
  legs and maps, and the "Inspect" traces as static JSON too.
- About 10 to 15 curated briefs across the suite's categories (own room near HKUST, 2-bed share,
  studio near HKU, a clarify turn, a "nothing fits" answer with relaxations).
- The brief box in showcase mode offers the recorded briefs and says plainly that live search runs
  during demos. It never pretends a recording is live.

### 2. Live mode, during a demo only, $0: the laptop behind a Cloudflare Tunnel
- The laptop runs the whole stack as today (`make up`, `make dev`); the model is Ollama, or the
  TACC vLLM endpoint during M5.
- `cloudflared tunnel --url http://localhost:8000` (a free quick tunnel, no account or domain) gives
  a temporary https URL. The site switches to live with `?api=<tunnel-url>` (kept in session storage).
- The backend accepts live runs only with a demo code typed in at the start (a header checked
  against `DEMO_CODE` in `.env`, never in the static site), allows CORS only from the
  site's origin (`https://bhanurana.github.io` or `https://flatjai.github.io`), and keeps today's per-site pacing, run budget and caches.
- When the demo ends: stop the tunnel; the site falls back to showcase on its own.

## Where the final code lives (Bhanu's plan, 2026-11-20)
- After the work is finished, Bhanu creates the free GitHub organisation `flatjai` and, in it, a
  separate final repo with a clean, iterative history of the project as a team, rebuilt step by step
  from this private repo (the way DuraLedger was rebuilt from its private build). This repo stays
  the private working copy.
- The org also holds `flatjai.github.io`, where a GitHub Action publishes the built static site.
- Authorship in the final history should match who did each part (each teammate commits their own
  work, or a real `Co-authored-by` trailer), since it is coursework that is graded.

## Anyone can run it from the final repo (the submission)
The org's final repo is for graders and anyone curious: clone, run one command, see FlatJai work.
It ships none of Bhanu's private setup (no tunnel, no demo code, no TACC user or key, no `.env`).
- `./setup.sh` (macOS and Linux; Windows through WSL), safe to run again:
  1. Check the prerequisites and say exactly what is missing: Docker, uv, Node + pnpm, and Ollama
     only if a local model is wanted; warn under ~12 GB of free memory.
  2. `cp .env.example .env` with working defaults (local model, OTP on, RUN_MAX_SECONDS=240).
  3. Install the backend (`uv sync`) and the web app (`pnpm install`), then `next typegen`.
  4. Download the open data and build the OpenTripPlanner graph (`make otp-graph`: HK GTFS, the OSM
     extract, the MTR feed). With `--no-otp`, skip it and use the offline commute estimate.
  5. Start Postgres and SearXNG (+ OTP) and run the migrations.
  6. Model: `ollama pull qwen3:8b` + `make model`, or any OpenAI-compatible server set in `.env`
     (a `custom` profile in `models.yaml`: base URL, model name, key from the environment).
  7. Run the tests, then print the two commands to start (`make dev`, `make web`) and the URL.
- **Replay mode, no model needed:** the M4 frozen snapshot ships in the repo (or as a release
  asset), and `make demo` serves the recorded chats, exactly as the showcase site does, so the
  project can be seen on a laptop without a GPU or a model download.
- README for the submission: what FlatJai is, the one-command setup, the two modes (replay and live
  with your own model), the architecture, the evaluation results, and the data sources with their
  terms (robots.txt, pacing, no copied photos).

## Map tiles
Stadia serves localhost without a key, but not github.io. Use Stadia's free non-commercial plan
with the site's domain registered as an allowed domain (no card), keep the attribution, and set a
usage alert. Fallback: OpenStreetMap's standard tiles within their usage policy (light use,
attribution). CARTO is out: it watermarks keyless use.

## Changes the deploy will need (later)
- Static export: `/runs/[id]` becomes `/runs?id=` (no server for dynamic routes); the `/runs`
  redirect in `next.config.ts` moves to a client redirect; check `cacheComponents` and
  `partialPrefetching` under export; set `basePath: "/flatjai"` for a project site.
- `NEXT_PUBLIC_API_URL` unset in the static build: an `api.ts` data source that reads the recorded
  JSON in showcase mode and the tunnel URL in live mode, behind one interface.
- `scripts/export_showcase.py`: snapshot chats + traces to `web/public/showcase/`, with stored
  listing text trimmed to what the cards show (links only, no copied photos; site terms as today).
- Backend: `DEMO_CODE` check on `POST /runs`, CORS origin from settings.

## If an always-on live demo is ever required
Only with Bhanu's yes, in this order: (1) Oracle Cloud Always Free ARM VM (4 cores, 24 GB) for
backend, Postgres, SearXNG and OTP, still $0, with the model on TACC or a capped API key; (2) a
model API with a monthly spend limit set at the provider and the demo code kept. Never a GPU host.
