"""Build the TACC job bundle: FlatJai's code, the frozen market as one SQLite file, and the libraries
the course environment lacks, as Linux wheels unpacked into vendor/.

The course runtime (Python 3.12, x86_64, glibc 2.35) has openai, httpx, pydantic and fastapi but no
pip, sqlalchemy, aiosqlite or selectolax, and the shared disk is nearly full, so the job ships one
small archive and unpacks it on the node's local /tmp.

Run from backend/:  uv run python ../infra/tacc/bundle.py
Writes infra/tacc/job/flatjai.tar.gz (the job directory tcloud submit uploads).
"""

import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import create_engine, select

from flatjai.config import settings
from flatjai.storage import models as m

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "infra" / "tacc" / "job"
TABLES = (m.Page, m.Listing, m.CacheEntry)  # the snapshot: pages, extractions, tool answers

# Locked versions (backend/uv.lock); everything FlatJai imports, pinned, so the job does not depend on
# whichever openai or pydantic the course environment happens to carry.
WHEELS = [
    "sqlalchemy==2.1.8",
    "greenlet==3.5.6",
    "aiosqlite==0.22.1",
    "selectolax==1.0.2",
    "openai==3.51.0",
    "pydantic==2.14.3",
    "pydantic-core==2.50.4",
]


def copy_market(db: Path) -> set[str]:
    """Postgres -> SQLite for the snapshot tables; returns the page hashes (their blobs go too)."""
    src = create_engine(settings().database_url)  # postgresql+psycopg: psycopg 3 sync works too
    dst = create_engine(f"sqlite:///{db}")
    m.Base.metadata.create_all(dst)
    hashes: set[str] = set()
    with src.connect() as r, dst.begin() as w:
        for model in TABLES:
            rows = [dict(x) for x in r.execute(select(model.__table__)).mappings()]
            if rows:
                w.execute(model.__table__.insert(), rows)
            if model is m.Page:
                hashes = {x["page_hash"] for x in rows}
            print(f"  {model.__tablename__}: {len(rows)} rows")
    return hashes


def vendor(dest: Path) -> None:
    wheels = dest.parent / "wheels"
    cmd = [
        "uvx", "pip", "download", "--quiet", "--no-deps", "--only-binary=:all:",
        "--python-version", "3.12", "--implementation", "cp", "--abi", "cp312",
        "--platform", "manylinux_2_17_x86_64", "--platform", "manylinux2014_x86_64",
        "--platform", "manylinux_2_28_x86_64", "--platform", "any",
        "-d", str(wheels), *WHEELS,
    ]  # fmt: skip
    subprocess.run(cmd, check=True)
    # openai's own dependencies the course env may lack (jiter is compiled)
    subprocess.run(
        [*cmd[: -len(WHEELS)], "jiter", "distro", "sniffio", "tqdm", "typing-inspection"], check=True
    )
    for whl in sorted(wheels.glob("*.whl")):
        zipfile.ZipFile(whl).extractall(dest)  # a wheel is a zip of site-packages content
        print(f"  {whl.name}")


def main() -> int:
    blobs_src = settings().data_dir / "blobs"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "flatjai"
        (stage / "data").mkdir(parents=True)
        print("market (Postgres -> SQLite):")
        hashes = copy_market(stage / "data" / "flatjai.db")
        missing = 0
        for h in hashes:
            src = blobs_src / h[:2] / h[2:]
            if src.exists():
                (stage / "data" / "blobs" / h[:2]).mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, stage / "data" / "blobs" / h[:2] / h[2:])
            else:
                missing += 1
        print(f"  blobs: {len(hashes) - missing} ({missing} missing)")
        shutil.copytree(ROOT / "backend" / "src", stage / "backend" / "src",
                        ignore=shutil.ignore_patterns("__pycache__"))  # fmt: skip
        shutil.copy2(ROOT / "backend" / "models.yaml", stage / "backend" / "models.yaml")
        (stage / "eval").mkdir()
        for f in ("run_suite.py", "score.py", "suite.yaml"):
            shutil.copy2(ROOT / "eval" / f, stage / "eval" / f)
        print("vendor (Linux wheels):")
        vendor(stage / "vendor")
        out = JOB / "flatjai.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(stage, arcname="flatjai")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
