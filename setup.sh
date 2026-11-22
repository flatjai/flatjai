#!/usr/bin/env bash
# FlatJai setup: from a fresh clone to a running app, in one command. Safe to run again.
#
#   ./setup.sh               everything: services, snapshot, commute graph, local model
#   ./setup.sh --no-otp      skip OpenTripPlanner (needs ~4 GB for Docker); commutes use the estimate
#   ./setup.sh --no-model    skip the local model (~5 GB download); use FJ_MODEL=tacc or replay only
#
# Needs: macOS or Linux (Windows: WSL2), Docker (Desktop) running, uv, Node 20.9+ with pnpm, zstd,
# and Ollama for the local model. The script checks each one and says how to install what is missing.
set -euo pipefail
cd "$(dirname "$0")"

WITH_OTP=1 WITH_MODEL=1
for arg in "$@"; do
  case "$arg" in
    --no-otp) WITH_OTP=0 ;;
    --no-model) WITH_MODEL=0 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)"; exit 2 ;;
  esac
done

bold=$'\033[1m' green=$'\033[32m' yellow=$'\033[33m' red=$'\033[31m' off=$'\033[0m'
step() { printf '\n%s==> %s%s\n' "$bold" "$*" "$off"; }
ok()   { printf '%s  ok%s %s\n' "$green" "$off" "$*"; }
warn() { printf '%s  !%s  %s\n' "$yellow" "$off" "$*"; }
die()  { printf '%s  x%s  %s\n' "$red" "$off" "$*"; exit 1; }
has()  { command -v "$1" >/dev/null 2>&1; }
mac()  { [ "$(uname)" = Darwin ]; }
hint() { if mac; then echo "brew install $1"; else echo "$2"; fi; }

# --- 1. tools ---------------------------------------------------------------------------------
step "Checking tools"
missing=0
need() {  # need <command> <install hint>
  if has "$1"; then ok "$1"; else warn "$1 missing: $2"; missing=1; fi
}
need docker "$(hint '--cask docker  (then open Docker Desktop)' 'https://docs.docker.com/engine/install/')"
need uv "curl -LsSf https://astral.sh/uv/install.sh | sh"
need node "$(hint node 'https://nodejs.org (20.9 or newer)')"
need zstd "$(hint zstd 'sudo apt install zstd')"
need curl "$(hint curl 'sudo apt install curl')"
if [ "$WITH_MODEL" = 1 ]; then
  need ollama "$(hint ollama 'curl -fsSL https://ollama.com/install.sh | sh')  (or rerun with --no-model)"
fi
[ "$missing" = 0 ] || die "install the tools above, then run ./setup.sh again"

node_major=$(node -p 'process.versions.node.split(".")[0]')
[ "$node_major" -ge 20 ] || die "Node $(node -v) is too old: Next.js needs 20.9 or newer"
if ! has pnpm; then
  warn "pnpm missing: enabling it through corepack (comes with Node)"
  corepack enable pnpm 2>/dev/null || npm install -g pnpm || die "could not install pnpm: npm install -g pnpm"
fi
ok "pnpm $(cd web && pnpm -v)"

docker info >/dev/null 2>&1 || die "Docker is installed but not running: start Docker Desktop and run ./setup.sh again"
docker compose version >/dev/null 2>&1 || die "the Docker Compose plugin is missing (docker compose version failed)"
ok "Docker is running"

if [ "$WITH_OTP" = 1 ]; then
  mem_gb=$(( $(docker info --format '{{.MemTotal}}') / 1024 / 1024 / 1024 ))
  if [ "$mem_gb" -lt 6 ]; then
    warn "Docker has ${mem_gb} GB of memory; OpenTripPlanner needs about 4 GB on top of the rest."
    warn "Raise it in Docker Desktop > Settings > Resources, or rerun with --no-otp. Skipping OTP."
    WITH_OTP=0
  fi
fi

# ports the stack needs, unless our own containers already hold them
for port in 5432 8888 8080 3001; do
  [ "$port" = 8080 ] && [ "$WITH_OTP" = 0 ] && continue
  has lsof || break
  holder=$(lsof -iTCP:"$port" -sTCP:LISTEN -Pn 2>/dev/null | awk 'NR>1{print $1}' | grep -v -e docker -e com.docke -e vpnkit | head -1 || true)
  if [ -n "$holder" ]; then
    warn "port $port is in use by $holder; stop it if a service below fails to start"
  fi
done

# --- 2. configuration -------------------------------------------------------------------------
step "Configuration (.env)"
if [ -f .env ]; then
  ok ".env exists, left as it is"
else
  cp .env.example .env
  # a laptop model reads a page in ~20 s: give each brief 4 minutes instead of the 90 s TACC target
  sed -i.bak 's/^RUN_MAX_SECONDS=.*/RUN_MAX_SECONDS=240/' .env && rm -f .env.bak
  ok "created .env from .env.example (RUN_MAX_SECONDS=240 for a laptop model)"
fi
if [ "$WITH_OTP" = 0 ] && grep -q '^OTP_URL=' .env; then
  sed -i.bak 's/^OTP_URL=/# OTP_URL=/' .env && rm -f .env.bak
  ok "OTP_URL commented out: commutes use the offline estimate"
fi

# --- 3. dependencies --------------------------------------------------------------------------
step "Python dependencies (uv)"
(cd backend && uv sync --frozen --quiet) && ok "backend/.venv"

step "Web dependencies (pnpm)"
(cd web && pnpm install --frozen-lockfile --silent) && ok "web/node_modules"

# --- 4. services and database -----------------------------------------------------------------
step "Starting Postgres and SearXNG (Docker)"
docker compose up -d --wait postgres searxng >/dev/null 2>&1 \
  || die "services did not start: run 'docker compose up postgres searxng' to see why"
ok "postgres :5432, searxng :8888"

step "Database schema"
(cd backend && uv run --frozen alembic upgrade head >/dev/null 2>&1) && ok "migrations applied"

step "Frozen snapshot (listing pages, extractions, tool answers)"
pages=$(docker compose exec -T postgres psql -U flatjai -d flatjai -tAc "select count(*) from pages")
snapshot=$(ls data/snapshot-*.tar.zst 2>/dev/null | sort | tail -1 || true)
if [ "$pages" -gt 0 ]; then
  ok "database already holds $pages pages: not overwritten (make snapshot-import replaces them)"
elif [ -n "$snapshot" ]; then
  scripts/snapshot.sh import "$snapshot" >/dev/null || die "snapshot import failed: run 'make snapshot-import' to see why"
  ok "loaded $snapshot"
else
  warn "no data/snapshot-*.tar.zst found: FlatJai will start with an empty cache"
fi
(cd backend && uv run --frozen python ../infra/grafana/load.py >/dev/null 2>&1) \
  && ok "dashboard data loaded (Grafana on http://localhost:3001)" || warn "dashboard data not loaded: run 'make obs' to see why"

# --- 5. commute router ------------------------------------------------------------------------
if [ "$WITH_OTP" = 1 ]; then
  step "OpenTripPlanner (real bus, minibus and MTR journeys)"
  if [ -f infra/otp/data/graph.obj ]; then
    ok "graph already built"
  else
    echo "  downloading open data (~50 MB) and building the graph (~2 min)..."
    make otp-graph >/dev/null 2>&1 || die "OTP graph build failed: run 'make otp-graph' to see why, or rerun with --no-otp"
    ok "graph built"
  fi
  docker compose --profile otp up -d --wait otp >/dev/null 2>&1 \
    || die "OpenTripPlanner did not start: run 'docker compose --profile otp up otp' to see why"
  ok "otp :8080"
fi

# --- 6. local model ---------------------------------------------------------------------------
if [ "$WITH_MODEL" = 1 ]; then
  step "Local model (Ollama, qwen3:8b with a 16K context)"
  if ! curl -sf -m 3 http://localhost:11434/api/tags >/dev/null; then
    if mac && has brew; then brew services start ollama >/dev/null 2>&1 || true; else (ollama serve >/dev/null 2>&1 &); fi
    for _ in $(seq 1 20); do curl -sf -m 2 http://localhost:11434/api/tags >/dev/null && break; sleep 1; done
  fi
  curl -sf -m 3 http://localhost:11434/api/tags >/dev/null || die "Ollama is not answering on :11434: start it (ollama serve) and run ./setup.sh again"
  models=$(ollama list 2>/dev/null || true)  # captured: "| grep -q" + pipefail fails on SIGPIPE
  if grep -q '^flatjai-qwen3-8b' <<<"$models"; then
    ok "flatjai-qwen3-8b already built"
  else
    echo "  pulling qwen3:8b (~5 GB, once)..."
    grep -q '^qwen3:8b' <<<"$models" || ollama pull qwen3:8b
    make model >/dev/null 2>&1 && ok "flatjai-qwen3-8b built"
  fi
  (cd backend && uv run --frozen python -m flatjai.check_model >/dev/null 2>&1) \
    && ok "the model returns a valid structured answer" \
    || warn "model check failed: run 'make check-model' to see why"
fi

# --- 7. tests ---------------------------------------------------------------------------------
step "Tests (no model, network or database needed)"
(cd backend && uv run --frozen pytest -q 2>&1 | tail -1)

# --- done -------------------------------------------------------------------------------------
cat <<EOF

${bold}${green}FlatJai is set up.${off} Run each in its own terminal:

  make dev        API on http://localhost:8000/docs
  make web        UI on  http://localhost:3000
  Grafana         metrics on http://localhost:3001 (make obs refreshes the TACC and eval data)

  FJ_OFFLINE=1 make dev   the frozen snapshot only: no listing site is contacted
  make eval               the query suite on the snapshot (B0, B1, FlatJai) -> eval/results/report.md

Stop the services with: make down   (data stays in the Docker volume)
EOF
[ "$WITH_MODEL" = 0 ] && echo "No local model: set FJ_MODEL=tacc in .env (see README) before 'make dev'."
[ "$WITH_OTP" = 0 ] && echo "No OpenTripPlanner: commutes are offline estimates. './setup.sh' again adds it later."
exit 0
