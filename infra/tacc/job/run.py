"""TACC CPU job: run the FlatJai suite against Qwen3.8-27B on the course vLLM service (experiment E3).

Runs inside the job (the service URL is cluster-internal). Unpacks flatjai.tar.gz onto the node's
local disk, points FlatJai at the frozen market (SQLite, FJ_OFFLINE=1) and the service URL, waits for
the service to answer, then runs each system in SYSTEMS and copies its results to
$TACC_USERDIR/flatjai-e3/<job id>/ after each one, so a job that hits its time limit keeps what it did.

systems.txt beside this file (or SYSTEMS): default "flatjai b1 b0"; "flatjai-model_facts" runs an ablation.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

WORKDIR = Path(os.environ["TACC_WORKDIR"])
OUT = Path(os.environ["TACC_USERDIR"]) / "flatjai-e3" / os.environ["SLURM_JOB_ID"]
LOCAL = Path(os.environ.get("QWEN_RUN_DIR") or "/tmp") / "fj"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_for_service(base: str, minutes: float = 25) -> None:
    deadline = time.monotonic() + minutes * 60
    while True:
        try:
            with urllib.request.urlopen(base + "/models", timeout=10) as r:
                ids = [m["id"] for m in json.load(r)["data"]]
            log(f"service ready: {ids}")
            return
        except Exception as e:  # noqa: BLE001 - not up yet
            if "name resolution" in str(e) or "Name or service not known" in str(e):
                raise SystemExit(f"cannot resolve the service host in {base}: {e}") from e
            if time.monotonic() > deadline:
                raise SystemExit(f"service at {base} not ready after {minutes} min: {e}") from e
            time.sleep(20)


def main() -> int:
    base = (WORKDIR / "server-url.txt").read_text().strip().rstrip("/")
    if "NODE" in base or not base.endswith("/v1"):
        raise SystemExit("server-url.txt must hold this run's SERVICE_BASE_URL, ending in /v1")
    # the service log names the node "10-0-1-11", which does not resolve from other nodes; its IP does
    base = re.sub(r"//(\d+)-(\d+)-(\d+)-(\d+):", r"//\1.\2.\3.\4:", base)
    log(f"service URL {base}")
    LOCAL.mkdir(parents=True, exist_ok=True)
    with tarfile.open(WORKDIR / "flatjai.tar.gz") as tar:
        tar.extractall(LOCAL, filter="data")
    root = LOCAL / "flatjai"
    (root / "infra" / "tacc").mkdir(parents=True, exist_ok=True)
    (root / "infra" / "tacc" / "server-url.txt").write_text(base + "\n")
    (root / ".env").write_text(
        "FJ_MODEL=tacc\nFJ_OFFLINE=1\nRUN_MAX_SECONDS=240\n"
        f"DATABASE_URL=sqlite+aiosqlite:///{root / 'data' / 'flatjai.db'}\n"
        # the same conditions as the laptop runs: OTP and SearXNG absent, answers from the snapshot cache
        "OTP_URL=http://localhost:8080\nSEARXNG_URL=http://localhost:8888\n"
    )
    env = os.environ | {
        "PYTHONPATH": f"{root / 'vendor'}:{root / 'backend' / 'src'}",
        "PYTHONUNBUFFERED": "1",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    check = "import flatjai.api, sqlalchemy, aiosqlite, selectolax, openai, pydantic; print('imports ok', openai.__version__, pydantic.__version__, sqlalchemy.__version__)"  # noqa: E501
    subprocess.run(
        [sys.executable, "-c", check], cwd=root / "backend", env=env, check=True
    )  # fail before waiting
    wait_for_service(base)

    status = 0
    listed = WORKDIR / "systems.txt"  # tcloud does not pass the laptop's environment to the job
    systems = os.environ.get("SYSTEMS") or (listed.read_text() if listed.exists() else "flatjai b1 b0")
    for system in systems.split():
        name, _, ablate = system.partition("-")
        cmd = [
            sys.executable,
            "../eval/run_suite.py",
            "--system",
            name,
            "--repeat",
            os.environ.get("REPEAT", "1"),
        ]
        cmd += ["--tag", "tacc"] + (["--ablate", ablate] if ablate else [])
        log(f"== {system}: {' '.join(cmd[1:])}")
        t0 = time.monotonic()
        rc = subprocess.run(cmd, cwd=root / "backend", env=env).returncode
        log(f"== {system} exit {rc} in {time.monotonic() - t0:.0f} s")
        status = status or rc
        for f in (root / "eval" / "results").glob("*.jsonl"):
            shutil.copy2(f, OUT / f.name)
        shutil.copy2(
            root / "data" / "flatjai.db", OUT / "flatjai.db"
        )  # runs and traces, for latency analysis
    log(f"RESULTS_DIR=flatjai-e3/{os.environ['SLURM_JOB_ID']}")
    return status


if __name__ == "__main__":
    sys.exit(main())
