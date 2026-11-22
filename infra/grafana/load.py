"""Prepare the observability dashboard's data (Grafana, infra/grafana): `make obs`.

Grafana reads Postgres directly, through the views in schema `obs`:
  obs.runs, obs.spans  every run and span on this laptop (public.runs/spans, live) plus the runs
                       copied from TACC job databases (eval/results/tacc-*/flatjai.db), each row
                       labelled with its source ("Qwen 8B (laptop)" or "Qwen 27B (TACC)")
  obs.eval             one row per scored brief from eval/results/report*.jsonl (E1, E2, E3)
It also creates the read-only login `grafana`, which may only read schema obs.
Safe to run again: the copied tables are reloaded each time; the app's own tables are only read.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "eval" / "results"
REPORTS = {"report.jsonl": "Qwen 8B (laptop)", "report-tacc.jsonl": "Qwen 27B (TACC)"}
EVAL_COLS = [
    "case", "category", "system", "repeat", "homes", "violated", "confirmed", "facts", "supported",
    "invented_listings", "duplicates", "cost_figures", "cost_off", "asked", "ask_ok", "outcome_ok",
    "seconds", "model_calls", "tokens", "error",
]  # fmt: skip
SOURCE = "CASE r.model_profile WHEN 'tacc' THEN 'Qwen 27B (TACC)' ELSE 'Qwen 8B (laptop)' END"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS obs;
CREATE TABLE IF NOT EXISTS obs.tacc_runs (
  id varchar(32) PRIMARY KEY, brief text, status varchar(20), stage varchar(20),
  model_profile varchar(40), model varchar(100), started_at timestamptz, ended_at timestamptz);
CREATE TABLE IF NOT EXISTS obs.tacc_spans (
  id varchar(16) PRIMARY KEY, run_id varchar(32), parent_id varchar(16), name varchar(80),
  kind varchar(10), started_at timestamptz, ms double precision, tokens_in int, tokens_out int,
  error text, attrs jsonb);
DROP TABLE IF EXISTS obs.eval CASCADE;
CREATE TABLE obs.eval (
  source text, file text, "case" text, category text, system text, repeat int, homes int,
  violated int, confirmed int, facts int, supported int, invented_listings int, duplicates int,
  cost_figures int, cost_off int, asked boolean, ask_ok boolean, outcome_ok boolean,
  seconds double precision, model_calls int, tokens int, error text);
CREATE OR REPLACE VIEW obs.runs AS
  SELECT r.id, r.brief, r.status, r.stage, r.model, r.started_at, r.ended_at,
         extract(epoch FROM r.ended_at - r.started_at) AS seconds, {SOURCE} AS source
  FROM public.runs r
  UNION ALL
  SELECT r.id, r.brief, r.status, r.stage, r.model, r.started_at, r.ended_at,
         extract(epoch FROM r.ended_at - r.started_at), {SOURCE}
  FROM obs.tacc_runs r;
CREATE OR REPLACE VIEW obs.spans AS
  SELECT s.id, s.run_id, s.parent_id, s.name, s.kind, s.started_at, s.ms, s.tokens_in,
         s.tokens_out, s.error, s.attrs, {SOURCE} AS source
  FROM public.spans s JOIN public.runs r ON r.id = s.run_id
  UNION ALL
  SELECT s.id, s.run_id, s.parent_id, s.name, s.kind, s.started_at, s.ms, s.tokens_in,
         s.tokens_out, s.error, s.attrs, {SOURCE}
  FROM obs.tacc_spans s JOIN obs.tacc_runs r ON r.id = s.run_id;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana') THEN
    CREATE ROLE grafana LOGIN PASSWORD 'grafana';
  END IF;
END $$;
GRANT USAGE ON SCHEMA obs TO grafana;
GRANT SELECT ON ALL TABLES IN SCHEMA obs TO grafana;
"""


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    env = ROOT / ".env"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url or "postgresql://flatjai:flatjai@localhost:5432/flatjai"
    if not url.startswith("postgresql"):
        sys.exit(f"the dashboard needs Postgres, DATABASE_URL is {url}")
    return url.replace("postgresql+psycopg://", "postgresql://")


def load_tacc(cur: psycopg.Cursor) -> tuple[int, int]:
    cur.execute("TRUNCATE obs.tacc_runs, obs.tacc_spans")
    runs = spans = 0
    for db in sorted(RESULTS.glob("tacc-*/flatjai.db")):
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = src.execute(
            "SELECT id, brief, status, stage, model_profile, model, started_at || '+00',"
            " ended_at || '+00' FROM runs"
        ).fetchall()
        cur.executemany(
            "INSERT INTO obs.tacc_runs VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows
        )
        runs += len(rows)
        rows = src.execute(
            "SELECT id, run_id, parent_id, name, kind, started_at || '+00', ms, tokens_in,"
            " tokens_out, error, attrs FROM spans"
        ).fetchall()
        cur.executemany(
            "INSERT INTO obs.tacc_spans VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            rows,
        )
        spans += len(rows)
        src.close()
    return runs, spans


def load_eval(cur: psycopg.Cursor) -> int:
    n = 0
    cols = ", ".join(f'"{c}"' for c in EVAL_COLS)
    marks = ", ".join(["%s"] * (len(EVAL_COLS) + 2))
    for name, source in REPORTS.items():
        path = RESULTS / name
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        cur.executemany(
            f"INSERT INTO obs.eval (source, file, {cols}) VALUES ({marks})",
            [[source, name] + [r.get(c) for c in EVAL_COLS] for r in rows],
        )
        n += len(rows)
    return n


def main() -> None:
    with psycopg.connect(database_url()) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        runs, spans = load_tacc(cur)
        scored = load_eval(cur)
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA obs TO grafana")
    print(f"obs ready: {runs} TACC runs, {spans} TACC spans, {scored} scored briefs")


if __name__ == "__main__":
    main()
