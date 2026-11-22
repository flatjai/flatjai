#!/usr/bin/env bash
# Run FlatJai locally, or run its evaluation on Qwen 27B on TACC. (First time: ./setup.sh)
#
#   ./run.sh local              the app on this machine: services, API and web in one terminal
#   ./run.sh local --offline    the same, answering from the frozen snapshot only (no listing site)
#   ./run.sh local --tacc       the app here, with Qwen 27B on TACC through an SSH tunnel (VPN needed)
#   ./run.sh tacc               the evaluation suite on Qwen 27B inside TACC, scored and on the dashboard
#   SYSTEMS="flatjai flatjai-model_facts" ./run.sh tacc     choose systems (default: flatjai b1 b0)
#
# Why "tacc" runs the suite and not the app: the course's 27B service is reachable only from inside
# the cluster, so FlatJai goes to it as a TACC job (docs/tacc.md) instead of the model coming here.
set -euo pipefail
cd "$(dirname "$0")"

bold=$'\033[1m' green=$'\033[32m' red=$'\033[31m' off=$'\033[0m'
say() { printf '%s==> %s%s\n' "$bold" "$*" "$off"; }
die() { printf '%sx  %s%s\n' "$red" "$*" "$off"; exit 1; }
usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; }

mode=${1:-}
[ -n "$mode" ] || { usage; exit 2; }
shift || true

# --- local: Docker services + API + web, stopped together with Ctrl-C ------------------------
run_local() {
  local offline=0 tacc=0
  for arg in "$@"; do
    case "$arg" in
      --offline) offline=1 ;;
      --tacc) tacc=1 ;;
      *) die "unknown option for local: $arg" ;;
    esac
  done
  [ -f .env ] && [ -d backend/.venv ] && [ -d web/node_modules ] || die "not set up yet: run ./setup.sh first"
  docker info >/dev/null 2>&1 || die "Docker is not running: start Docker Desktop and try again"
  for port in 8000 3000; do
    if lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1; then
      die "port $port is already in use (a make dev or make web still running?)"
    fi
  done
  if [ "$tacc" = 0 ] && grep -q '^FJ_MODEL=local' .env && ! curl -s -o /dev/null http://localhost:11434/api/tags; then
    die "Ollama is not running: open the Ollama app (or 'ollama serve') and try again"
  fi

  say "Starting Postgres, SearXNG, Grafana (and OpenTripPlanner if built)"
  make -s up

  # one process group: Ctrl-C (or either server exiting) stops both
  trap 'trap - INT TERM EXIT; printf "\nStopping API and web (Docker services keep running: make down)\n"; kill 0 2>/dev/null' INT TERM EXIT
  if [ "$tacc" = 1 ]; then
    local port=${TUNNEL_PORT:-8001}
    say "Starting Qwen 27B on TACC and tunnelling it to localhost:$port (scripts/tacc-tunnel.sh)"
    scripts/tacc-tunnel.sh &
    local tunnel=$!
    until curl -s -m 5 "http://localhost:$port/v1/models" | grep -q qwen3.8-27b; do
      kill -0 "$tunnel" 2>/dev/null || die "the TACC tunnel stopped: see the [tunnel] lines above"
      sleep 5
    done
    export FJ_MODEL=tacc-tunnel
    say "Model: Qwen 27B on TACC (the service job lasts 1 h)"
  fi
  local env_offline=""
  [ "$offline" = 1 ] && env_offline="FJ_OFFLINE=1" && say "Offline: answers come from the frozen snapshot only"
  (env $env_offline make -s dev 2>&1 | awk '{print "\033[36m[api]\033[0m " $0; fflush()}') &
  (make -s web 2>&1 | awk '{print "\033[35m[web]\033[0m " $0; fflush()}') &

  say "Waiting for the API and the web app"
  for _ in $(seq 1 60); do
    curl -s -o /dev/null http://localhost:8000/health && curl -s -o /dev/null http://localhost:3000 && break
    sleep 2
  done
  curl -s -o /dev/null http://localhost:8000/health || die "the API did not start: see the [api] lines above"
  cat <<EOF

${green}${bold}FlatJai is running.${off} Ctrl-C stops it.

  App        http://localhost:3000
  Metrics    http://localhost:3001
  API docs   http://localhost:8000/docs

EOF
  wait
}

# --- tacc: the suite on Qwen 27B inside TACC, then the score and the dashboard ----------------
run_tacc() {
  [ $# -eq 0 ] || die "tacc takes no options; choose systems with SYSTEMS=\"...\""
  command -v tcloud >/dev/null || die "tcloud not found: see docs/tacc.md (one-time setup)"
  docker info >/dev/null 2>&1 || die "Docker is not running: the bundle reads the snapshot from Postgres"
  make -s up >/dev/null

  say "Running on TACC: ${SYSTEMS:-flatjai b1 b0} (a 27B service job plus a client job; ~15 to 40 min)"
  scripts/run-e3.sh

  say "Scoring the latest TACC run of each system"
  local files=() s
  for s in $(ls eval/results | sed -nE 's#^[0-9]{8}-[0-9]{4}-(.*)-tacc\.jsonl$#\1#p' | sort -u); do
    files+=("../$(ls -t eval/results/*-"$s"-tacc.jsonl | head -1)")
  done
  (cd backend && uv run python ../eval/score.py "${files[@]}" --out ../eval/results/report-tacc.md)

  say "Loading the runs into the dashboard"
  make -s obs
  printf '\n%sDone.%s Report: eval/results/report-tacc.md  Dashboard: http://localhost:3001\n' "$green$bold" "$off"
}

case "$mode" in
  local) run_local "$@" ;;
  tacc) run_tacc "$@" ;;
  -h|--help|help) usage ;;
  *) usage; exit 2 ;;
esac
