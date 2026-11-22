#!/usr/bin/env bash
# Run FlatJai. Its model is Qwen3.8-27B on TACC GPUs; Qwen3 8B on this machine is the fallback.
# (First time: ./setup.sh, which asks where the model runs.)
#
#   ./run.sh app                  the app: services, API and web here, the model chosen at setup
#                                 (TACC: starts the 27B service and tunnels it here, ~5 min)
#   ./run.sh app --offline        the same, answering from the frozen snapshot only (no listing site)
#   ./run.sh app --model tacc     this run on Qwen 27B on TACC, whatever setup chose
#   ./run.sh app --model local    this run on Qwen 8B on this machine (Ollama), whatever setup chose
#   ./run.sh suite                the evaluation suite on Qwen 27B inside TACC, scored, on the dashboard
#   SYSTEMS="flatjai flatjai-model_facts" ./run.sh suite    choose systems (default: flatjai b1 b0)
#
# Older names still work: "local" for app, "tacc" for suite, "--tacc" for "--model tacc".
set -euo pipefail
cd "$(dirname "$0")"

bold=$'\033[1m' green=$'\033[32m' red=$'\033[31m' off=$'\033[0m'
say() { printf '%s==> %s%s\n' "$bold" "$*" "$off"; }
die() { printf '%sx  %s%s\n' "$red" "$*" "$off"; exit 1; }
usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; }

mode=${1:-}
[ -n "$mode" ] || { usage; exit 2; }
shift || true

# the profile setup.sh wrote to .env: tacc-tunnel (TACC) or local (Ollama)
env_model() { sed -n 's/^FJ_MODEL=//p' .env 2>/dev/null | tail -1; }

# --- app: Docker services + (TACC tunnel) + API + web, stopped together with Ctrl-C ------------
run_app() {
  local offline=0 model=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --offline) offline=1 ;;
      --tacc) model=tacc ;;
      --model) shift; model=${1:-} ;;
      --model=*) model=${1#--model=} ;;
      *) die "unknown option for app: $1 (try ./run.sh)" ;;
    esac
    shift
  done
  [ -f .env ] && [ -d backend/.venv ] && [ -d web/node_modules ] || die "not set up yet: run ./setup.sh first"
  if [ -z "$model" ]; then
    case "$(env_model)" in
      local) model=local ;;
      *) model=tacc ;;
    esac
  fi
  case "$model" in
    tacc|local) ;;
    *) die "--model takes tacc or local, not '$model'" ;;
  esac

  docker info >/dev/null 2>&1 || die "Docker is not running: start Docker Desktop and try again"
  # a tunnel already open (scripts/tacc-tunnel.sh in another terminal) is reused, not started again
  local reuse=0
  if [ "$model" = tacc ] && curl -s -m 5 "http://localhost:${TUNNEL_PORT:-8001}/v1/models" 2>/dev/null | grep -q qwen3.8-27b; then
    reuse=1
  fi
  local ports="8000 3000"
  [ "$model" = tacc ] && [ "$reuse" = 0 ] && ports="$ports ${TUNNEL_PORT:-8001}"
  for port in $ports; do
    if lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1; then
      die "port $port is already in use (an earlier run, make dev or make web still running?)"
    fi
  done
  if [ "$model" = local ] && ! curl -s -o /dev/null http://localhost:11434/api/tags; then
    die "Ollama is not running: open the Ollama app (or 'ollama serve'), or use the TACC model: ./run.sh app --model tacc"
  fi
  if [ "$model" = tacc ] && [ "$reuse" = 0 ]; then
    command -v tcloud >/dev/null || die "tcloud not found: TACC needs the one-time setup in docs/tacc.md (or ./run.sh app --model local)"
  fi

  say "Starting Postgres, SearXNG, Grafana (and OpenTripPlanner if built)"
  make -s up

  # one process group: Ctrl-C (or either server exiting) stops everything, and the tunnel's own
  # handler cancels the TACC service job
  trap 'trap - INT TERM EXIT; printf "\nStopping (Docker services keep running: make down)\n"; kill 0 2>/dev/null' INT TERM EXIT

  if [ "$model" = tacc ] && [ "$reuse" = 1 ]; then
    export FJ_MODEL=tacc-tunnel
    say "Model: Qwen3.8-27B on TACC, through the tunnel already open on localhost:${TUNNEL_PORT:-8001}"
  elif [ "$model" = tacc ]; then
    local port=${TUNNEL_PORT:-8001}
    say "Starting Qwen 27B on TACC and tunnelling it to localhost:$port (about 5 minutes)"
    scripts/tacc-tunnel.sh &
    local tunnel=$!
    until curl -s -m 5 "http://localhost:$port/v1/models" 2>/dev/null | grep -q qwen3.8-27b; do
      kill -0 "$tunnel" 2>/dev/null || die "the TACC tunnel stopped: see the [tunnel] lines above"
      sleep 5
    done
    export FJ_MODEL=tacc-tunnel
    say "Model: Qwen3.8-27B on TACC (the service job lasts 1 h)"
  else
    export FJ_MODEL=local
    say "Model: Qwen3 8B on this machine (Ollama)"
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

${green}${bold}FlatJai is running.${off} Ctrl-C stops it$([ "$model" = tacc ] && [ "$reuse" = 0 ] && printf ' and cancels the TACC job').

  App        http://localhost:3000
  Metrics    http://localhost:3001
  API docs   http://localhost:8000/docs

EOF
  wait
}

# --- suite: the evaluation on Qwen 27B inside TACC, then the score and the dashboard -----------
run_suite() {
  [ $# -eq 0 ] || die "suite takes no options; choose systems with SYSTEMS=\"...\""
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
  app|local) run_app "$@" ;;
  suite|tacc) run_suite "$@" ;;
  -h|--help|help) usage ;;
  *) usage; exit 2 ;;
esac
