# TACC: FlatJai on Qwen3.8-27B (experiment E3)

The course serves Qwen3.8-27B (AWQ INT4, vLLM, 2 GPUs, 32K context, 4 concurrent requests, model name
`qwen3.8-27b`) as a TACC job whose URL (`http://<node>:8000/v1`) is reachable only inside the cluster.
So FlatJai runs its evaluation inside TACC too, as a CPU job built from the course kit's
`qwen-public-client` (same environment checks, `qwen-python`, proxy bypass for the internal URL).

```
scripts/run-e3.sh                                   # service + FlatJai, B1, B0 -> eval/results/*-tacc.jsonl
SYSTEMS="flatjai-model_facts" scripts/run-e3.sh     # an ablation on 27B
```

## How the job works
- `bundle.py` (laptop) packs the code, the frozen market as one SQLite file (pages, extractions, tool
  answers, and the page blobs they point to) and the libraries the course runtime lacks
  (sqlalchemy, aiosqlite, selectolax; openai and pydantic pinned to our lock) as Linux wheels.
- `job/run.py` (TACC) unpacks it on the node's local disk (the shared `/mnt/home` is nearly full),
  checks the imports before waiting, waits for the service, runs each system offline
  (`FJ_OFFLINE=1`, no listing site touched) and copies results to `$TACC_USERDIR/flatjai-e3/<job>/`
  after each system, so a job that hits its limit keeps what it finished.
- Same conditions as the laptop runs: no OTP or SearXNG in the job; searches, geocodes and commutes
  come from the snapshot's cache. Pages read for the first time by 27B are extracted by 27B.

## One-time setup (done 2026-11-21)
1. tcloud v0.4.1 (Intel build, runs under Rosetta) in `~/.local/bin`.
2. `tcloud config -u bhanurana -f ~/.ssh/id_rsa_tacc && tcloud init`.
3. Course kit `project-release-1.zip` unpacked under the coursework folder (`TACC_KIT`), then
   `bash setup-sdk-account.sh` once.

## Limits
Service jobs end after 1 hour (cancel when done to free GPUs); a new job means a new URL. The first
start compiles for ~4 min (cached in USERDIR afterwards). Client jobs here allow 55 min.
