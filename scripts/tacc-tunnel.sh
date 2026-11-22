#!/usr/bin/env bash
# Qwen 27B on TACC for the local app: start the course vLLM service (or reuse one), then forward it to
# this machine through the TACC SSH gateway. The app then calls http://localhost:$TUNNEL_PORT/v1.
#
#   scripts/tacc-tunnel.sh                          start a service job, tunnel it, cancel it on Ctrl-C
#   TACC_SERVICE_URL=http://10.0.1.11:8000/v1 scripts/tacc-tunnel.sh    tunnel a service already running
#
# Uses whoever runs it: user, gateway, port and key come from ~/.tcloud/.userconfig (tcloud config),
# so the HKUST network or VPN must reach the gateway. ./run.sh local --tacc runs this for you.
# Needs the course kit for starting a service (TACC_KIT, see docs/tacc.md).
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=${TUNNEL_PORT:-8001}
KIT=${TACC_KIT:-$HOME/Work/ust/coursework/Adv-AI-Computing-And-Systems-CSIT6000V/project/tacc-kit/qwen27b-student-release}
CONF=${TCLOUD_USERCONFIG:-$HOME/.tcloud/.userconfig}

log() { printf '[tunnel] %s\n' "$*"; }
die() { printf '[tunnel] x %s\n' "$*" >&2; exit 1; }

[ -f "$CONF" ] || die "no $CONF: run 'tcloud config -u USER -f KEY' first (docs/tacc.md)"
read -r USER_NAME GATEWAY GW_PORT KEY < <(python3 -c '
import json, sys
c = json.load(open(sys.argv[1]))
gw = c["SSHpath"][0] if isinstance(c["SSHpath"], list) else c["SSHpath"]
print(c["UserName"], gw, c.get("Port", "22"), c["AuthFile"])' "$CONF")
SSH=(ssh -i "$KEY" -p "$GW_PORT" -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=30
     -o ExitOnForwardFailure=yes "$USER_NAME@$GATEWAY")

SERVICE=""
cleanup() {
  [ -n "${TUNNEL_PID:-}" ] && kill "$TUNNEL_PID" 2>/dev/null || true
  if [ -n "$SERVICE" ]; then tcloud cancel -j "$SERVICE" >/dev/null 2>&1 && log "cancelled service job $SERVICE"; fi
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

url=${TACC_SERVICE_URL:-}
if [ -z "$url" ]; then
  command -v tcloud >/dev/null || die "tcloud not on PATH (docs/tacc.md)"
  [ -d "$KIT/qwen-public-serve" ] || die "course kit not found at $KIT (set TACC_KIT)"
  SERVICE=$(cd "$KIT/qwen-public-serve" && tcloud submit 2>&1 | sed -n 's/^Submitted batch job \([0-9]*\).*/\1/p')
  [ -n "$SERVICE" ] || die "service submit failed (is the gateway reachable? HKUST network or VPN)"
  log "service job $SERVICE submitted; waiting for its URL (the job lasts 1 h)"
  for _ in $(seq 1 40); do
    url=$(tcloud cat "slurm_log/qwen-public-serve-$SERVICE.log" 2>/dev/null | sed -n 's/^SERVICE_BASE_URL=//p' | tail -1)
    [ -n "$url" ] && break
    sleep 15
  done
  [ -n "$url" ] || die "no SERVICE_BASE_URL in the service log"
fi
# the log names the node "10-0-1-11", which does not resolve; its IP does
url=$(printf '%s' "$url" | sed -E 's#//([0-9]+)-([0-9]+)-([0-9]+)-([0-9]+):#//\1.\2.\3.\4:#')
hostport=${url#*://}; hostport=${hostport%%/*}
log "service at $url; forwarding localhost:$PORT -> $hostport via $GATEWAY:$GW_PORT"

"${SSH[@]}" -N -L "127.0.0.1:$PORT:$hostport" &
TUNNEL_PID=$!
sleep 3
kill -0 "$TUNNEL_PID" 2>/dev/null || die "the SSH tunnel did not open: check the VPN, and that $GATEWAY allows port forwarding"

log "waiting for the model (the first start compiles for ~4 min)"
for _ in $(seq 1 60); do
  if curl -s -m 10 "http://localhost:$PORT/v1/models" | grep -q qwen3.8-27b; then
    log "ready: http://localhost:$PORT/v1 serves qwen3.8-27b. Ctrl-C closes the tunnel${SERVICE:+ and cancels the service}"
    wait "$TUNNEL_PID"
    die "the tunnel closed (service ended after its 1 h limit, or the network dropped)"
  fi
  kill -0 "$TUNNEL_PID" 2>/dev/null || die "the tunnel closed while waiting for the model"
  sleep 10
done
die "the model did not answer through the tunnel within 10 min"
