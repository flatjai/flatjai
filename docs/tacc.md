# TACC: FlatJai's model on the course GPUs

FlatJai's model is **Qwen3.8-27B** (AWQ INT4, vLLM, 2 GPUs, 32K context, model name `qwen3.8-27b`),
served by the course on TACC as a GPU job. That job's URL (`http://<node>:8000/v1`) is reachable only
inside the cluster, so FlatJai reaches it in two ways:

| Command | What runs where | Use it for |
|---|---|---|
| `./run.sh app` | the app (API, web, search, routing, Postgres) runs on your machine; only model calls go to TACC, through an SSH tunnel | using FlatJai |
| `./run.sh suite` | the evaluation suite runs inside TACC as a CPU job next to the service | experiment E3 ([evaluation.md](evaluation.md)) |

Without TACC access, Qwen3 8B on your own machine can stand in (`./setup.sh --model local`); it is
slower and less precise, and it is the fallback, not the default.

## One-time setup

Needs a TACC account for the course, the HKUST network or VPN, and the course kit.

1. Install tcloud (v0.4.1; on Apple Silicon the Intel build runs under Rosetta) somewhere on `PATH`,
   for example `~/.local/bin`.
2. `tcloud config -u <your TACC user> -f <your TACC SSH key> && tcloud init`. FlatJai reads the same
   settings from `~/.tcloud/.userconfig`, so it always runs as you.
3. Unzip the course kit (`project-release-1.zip`), run `bash setup-sdk-account.sh` from it once, and
   point `TACC_KIT` at its `qwen27b-student-release` folder (for example in your shell profile).
4. Run `./setup.sh` and choose **1) TACC** (the default; `./setup.sh --model tacc` skips the
   question). It sets `FJ_MODEL=tacc-tunnel` in `.env` and checks tcloud, your login, the kit and
   that the TACC gateway answers.

If `tcloud ps` hangs, the machine is not reaching the gateway: connect to the HKUST network or VPN
and turn off any other VPN.

## The app on 27B: `./run.sh app`

```
./run.sh app                                                    # start the service, tunnel it, run the app
./run.sh app --offline                                          # the same on the frozen snapshot only
scripts/tacc-tunnel.sh                                          # only the service and its tunnel (for make dev, make eval)
TACC_SERVICE_URL=http://10.0.1.11:8000/v1 scripts/tacc-tunnel.sh   # tunnel a service already running
```

`scripts/tacc-tunnel.sh`:

1. submits the course's `qwen-public-serve` job (or reuses the one in `TACC_SERVICE_URL`) and reads
   its URL from the job log;
2. opens an SSH tunnel through the TACC gateway from `localhost:8001` to the service, as the person
   running it (user, gateway, port and key from `~/.tcloud/.userconfig`);
3. waits until the model answers: 4 to 7 minutes after the job starts, while vLLM loads the model,
   with a progress line each minute.

`./run.sh app` then starts the API and the web app with the `tacc-tunnel` profile
(`backend/models.yaml`). If a tunnel is already open on `localhost:8001` it is reused. Ctrl-C stops
the app, closes the tunnel and cancels the service job. To use another local port, set `TUNNEL_PORT`
and change `base_url` of the `tacc-tunnel` profile to match.

## The suite on 27B: `./run.sh suite`

```
./run.sh suite                                      # FlatJai, B1, B0 on 27B, scored, on the dashboard
SYSTEMS="flatjai-model_facts" ./run.sh suite        # an ablation on 27B
scripts/run-e3.sh                                   # the job round trip alone (no scoring)
```

It starts the service, submits the client job, follows its log, downloads the results into
`eval/results/`, cancels the service, scores the latest run of each system into
`eval/results/report-tacc.md` and loads them into Grafana (`make obs`). About 15 to 40 minutes.

How the job works:

- `infra/tacc/bundle.py` (here) packs the code, the frozen market as one SQLite file (pages,
  extractions, tool answers and the page blobs they point to) and the libraries the course runtime
  lacks (sqlalchemy, aiosqlite, selectolax; openai and pydantic pinned to our lock) as Linux wheels.
- `infra/tacc/job/job.sh` is the course kit's `qwen-public-client` job (same environment checks,
  `qwen-python`, proxy bypass for the internal URL) running `infra/tacc/job/run.py`.
- `run.py` (in TACC) unpacks the bundle on the node's local disk (the shared `/mnt/home` is nearly
  full), checks the imports before waiting, waits for the service, runs each system offline
  (`FJ_OFFLINE=1`, no listing site touched, profile `tacc`) and copies results to
  `$TACC_USERDIR/flatjai-e3/<job>/` after each system, so a job that hits its limit keeps what it
  finished.
- Same conditions as the runs on your machine: no OTP or SearXNG in the job; searches, geocodes and
  commutes come from the snapshot's cache. Pages read for the first time by 27B are extracted by 27B.

## Limits

- Service jobs end after 1 hour (cancel when done to free GPUs); a new job means a new URL. Client
  jobs allow 55 minutes.
- The service handles 4 requests at once and is shared by the course; a busy cluster queues the job
  (`tcloud ps` shows it as pending).
- The service log names its node like `10-0-1-11`, which does not resolve from other nodes; the
  scripts use the IP (`10.0.1.11`).
- `tcloud download` takes files, not folders.
