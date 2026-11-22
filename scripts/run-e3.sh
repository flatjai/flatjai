#!/usr/bin/env bash
# Experiment E3: the suite on Qwen3.8-27B on TACC, from the laptop in one command.
#
#   scripts/run-e3.sh                      # FlatJai, B1 and B0 (1 repeat each)
#   SYSTEMS="flatjai flatjai-model_facts" scripts/run-e3.sh
#
# Starts the course vLLM service (qwen-public-serve from the course kit), submits the FlatJai client
# job (deploy/tacc/job) with the service's URL, follows it, downloads the results into eval/results/,
# and cancels the service. The client runs inside TACC because the service URL is cluster-internal.
# Needs: tcloud configured (tcloud config -u USER -f KEY; tcloud init), the course kit unpacked
# (TACC_KIT, default below) with setup-sdk-account.sh run once, and Postgres up for the bundle.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
KIT=${TACC_KIT:-$HOME/Work/ust/coursework/Adv-AI-Computing-And-Systems-CSIT6000V/project/tacc-kit/qwen27b-student-release}
JOB=deploy/tacc/job
SYSTEMS=${SYSTEMS:-flatjai b1 b0}
command -v tcloud >/dev/null || { echo "tcloud not on PATH (see deploy/tacc/README.md)"; exit 1; }
[ -d "$KIT/qwen-public-serve" ] || { echo "course kit not found at $KIT (set TACC_KIT)"; exit 1; }

echo "Bundling FlatJai and the frozen market..."
(cd backend && uv run python ../deploy/tacc/bundle.py | tail -1)
echo "$SYSTEMS" > "$JOB/systems.txt"

job_id() { sed -n 's/^Submitted batch job \([0-9]*\).*/\1/p'; }
SERVICE=$(cd "$KIT/qwen-public-serve" && tcloud submit 2>&1 | job_id)
[ -n "$SERVICE" ] || { echo "service submit failed"; exit 1; }
cleanup() { tcloud cancel -j "$SERVICE" >/dev/null 2>&1 && echo "Cancelled service $SERVICE"; }
trap cleanup EXIT
echo "Service job $SERVICE; waiting for its URL..."
url=""
for _ in $(seq 1 40); do
  url=$(tcloud cat "slurm_log/qwen-public-serve-$SERVICE.log" 2>/dev/null | sed -n 's/^SERVICE_BASE_URL=//p' | tail -1)
  [ -n "$url" ] && break
  sleep 15
done
[ -n "$url" ] || { echo "no SERVICE_BASE_URL in the service log"; exit 1; }
echo "$url" > "$JOB/server-url.txt"
CLIENT=$(cd "$JOB" && tcloud submit 2>&1 | job_id)
[ -n "$CLIENT" ] || { echo "client submit failed"; exit 1; }
echo "Service $SERVICE at $url; client $CLIENT (waits for the model, then runs: $SYSTEMS)"

seen=0
while tcloud ps -j "$CLIENT" 2>/dev/null | grep -q "^ *$CLIENT "; do
  out=$(tcloud cat "slurm_log/flatjai-e3-$CLIENT.log" 2>/dev/null || true)
  n=$(printf '%s\n' "$out" | wc -l)
  if [ "$n" -gt "$seen" ]; then printf '%s\n' "$out" | tail -n +$((seen + 1)); seen=$n; fi
  sleep 30
done
tcloud cat "slurm_log/flatjai-e3-$CLIENT.log" 2>/dev/null | tail -n +$((seen + 1)) || true

echo "Downloading results..."
dest=eval/results/tacc-$CLIENT
mkdir -p "$dest"
for f in $(tcloud ls "flatjai-e3/$CLIENT" 2>/dev/null | tr -s ' \t' '\n' | grep -E '\.(jsonl|db)$'); do
  tcloud download "flatjai-e3/$CLIENT/$f" "$dest/$f" >/dev/null  # tcloud downloads files, not folders
done
find "$dest" -name '*.jsonl' -exec cp {} eval/results/ \;
echo "Results in eval/results/ (raw job output in $dest). Score with:"
echo "  cd backend && uv run python ../eval/score.py \$(ls -t ../eval/results/*-tacc.jsonl) --out ../eval/results/report-tacc.md"
