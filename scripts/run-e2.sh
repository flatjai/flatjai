#!/bin/zsh
# Run experiment E2 (the ablations) on a laptop that is short of memory, then bring the app stack back.
# Stops the run if swap passes 22 GB or free memory drops under 8% (Docker crashed at 22 GB swap on
# 2026-11-20). Needs Docker Desktop and Ollama; OTP and the web app are stopped for the run (commutes
# come from the snapshot's cache). Results: eval/results/report.md. Log: eval/results/e2.log.
set -u
cd "$(dirname "$0")/.."
LOG=eval/results/e2.log

docker compose --profile otp stop otp >/dev/null 2>&1
docker compose up -d --wait postgres searxng || { echo "Docker is not up: start Docker Desktop first"; exit 1; }
curl -sf localhost:11434/api/tags >/dev/null || { echo "Ollama is not running: open Ollama first"; exit 1; }

echo "E2 started $(date '+%H:%M'), about 45 min. Log: $LOG"
make ablate REPEAT=1 >"$LOG" 2>&1 &
RUN=$!
rc=0
while kill -0 $RUN 2>/dev/null; do
  used=$(sysctl -n vm.swapusage | awk '{gsub("M","",$6); print int($6)}')
  free=$(memory_pressure | awk -F': ' '/free percentage/ {gsub("%","",$2); print int($2)}')
  if [ "$used" -gt 22000 ] || [ "$free" -lt 8 ]; then
    echo "GUARD: swap ${used}M, free ${free}%: stopping E2" | tee -a "$LOG"
    pkill -f 'make ablate'; pkill -f 'run_suite.py --system flatjai --ablate'
    rc=3
    break
  fi
  grep -E '^\s+\[0\]|offline=True' "$LOG" | tail -1
  sleep 30
done
[ $rc -eq 0 ] && { wait $RUN; rc=$?; }

echo "Restarting OTP for the app..."
docker compose --profile otp up -d otp >/dev/null 2>&1
if [ $rc -eq 0 ]; then
  echo "E2 done $(date '+%H:%M'). Report: eval/results/report.md"
  sed -n '/^## E1 and E2/,/^Cases:/p' eval/results/report.md
else
  echo "E2 stopped (exit $rc). See $LOG"
fi
exit $rc
