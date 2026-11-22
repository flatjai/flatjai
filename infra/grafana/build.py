"""Writes flatjai.json, the FlatJai observability dashboard (python3 build_dashboard.py).

Every panel is a SQL query on the views in schema obs (infra/grafana/load.py): runs and spans from this
laptop and from TACC, and the scored suite. Edit here, not in the JSON, then rebuild; Grafana picks up
the file within 30 s.
"""

import json
from pathlib import Path

DS = {"type": "grafana-postgresql-datasource", "uid": "flatjai-pg"}
F = "source IN ($source) AND $__timeFilter(started_at)"
STAGES = "ARRAY['understand','plan','search','read','match','reflect','answer']"
SOURCES = ["Qwen 8B (laptop)", "Qwen 27B (TACC)"]
COLORS = {"Qwen 8B (laptop)": "#ff8a5c", "Qwen 27B (TACC)": "#5794f2"}
# a run interrupted and resumed later (wall time over 10 min; the budget is 240 s) is left out of timings
DONE = "AND status = 'done' AND seconds < 600"
INSPECTOR = "http://localhost:3000/runs/${__value.raw}"

panels: list[dict] = []
y = 0


def target(sql: str, fmt: str = "table") -> dict:
    return {
        "refId": "A",
        "datasource": DS,
        "editorMode": "code",
        "rawQuery": True,
        "format": fmt,
        "rawSql": sql,
    }


def place(panel: dict, x: int, w: int, h: int) -> dict:
    panel["gridPos"] = {"x": x, "y": y, "w": w, "h": h}
    panel["id"] = len(panels) + 1
    panel.setdefault("datasource", DS)
    panels.append(panel)
    return panel


def row(title: str) -> None:
    global y
    place({"type": "row", "title": title, "collapsed": False, "panels": []}, 0, 24, 1)
    y += 1


def by_source(overrides: list | None = None) -> list:
    return (overrides or []) + [
        {
            "matcher": {"id": "byName", "options": s},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}],
        }
        for s, c in COLORS.items()
    ]


def stat(title: str, sql: str, unit: str, x: int, w: int = 4, decimals: int = 0, desc: str = "") -> None:
    place(
        {
            "type": "stat",
            "title": title,
            "description": desc,
            "targets": [target(sql)],
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "decimals": decimals,
                    "color": {"mode": "fixed", "fixedColor": "#ff8a5c"},
                },
                "overrides": [],
            },
            "options": {
                "reduceOptions": {"values": True, "calcs": ["lastNotNull"], "fields": "/^value$/"},
                "colorMode": "value",
                "graphMode": "none",
                "textMode": "value_and_name",
                "justifyMode": "center",
                "orientation": "horizontal",
                "text": {"titleSize": 12, "valueSize": 26},
            },
        },
        x,
        w,
        4,
    )


def per_source(expr: str, table: str = "obs.runs", where: str = "") -> str:
    """One row per model: the stat shows 8B and 27B side by side."""
    return (
        f"SELECT source, {expr} AS value FROM {table} WHERE {F} {where} GROUP BY source ORDER BY source DESC"
    )


def timeseries(title: str, sql: str, x: int, w: int, unit: str, style: str, desc: str = "") -> None:
    custom = {"drawStyle": style, "pointSize": 5, "lineWidth": 2, "fillOpacity": 70 if style == "bars" else 0}
    if style == "bars":
        custom["stacking"] = {"mode": "normal", "group": "A"}
    place(
        {
            "type": "timeseries",
            "title": title,
            "description": desc,
            "targets": [target(sql, "time_series")],
            "fieldConfig": {
                "defaults": {"unit": unit, "custom": custom},
                "overrides": by_source(
                    [
                        {
                            "matcher": {"id": "byName", "options": n},
                            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}],
                        }
                        for n, c in {
                            "done": "green",
                            "needs_input": "yellow",
                            "error": "red",
                            "running": "blue",
                        }.items()
                    ]
                ),
            },
            "options": {
                "legend": {"displayMode": "list", "placement": "bottom"},
                "tooltip": {"mode": "multi"},
            },
        },
        x,
        w,
        8,
    )


def table(
    title: str, sql: str, x: int, w: int, h: int, units: dict, desc: str = "", links: dict | None = None
) -> None:
    overrides = [
        {
            "matcher": {"id": "byRegexp", "options": f".*(?:{pattern}).*"},
            "properties": [{"id": "unit", "value": u}, {"id": "decimals", "value": d}],
        }
        for pattern, (u, d) in units.items()
    ]
    for col, url in (links or {}).items():
        overrides.append(
            {
                "matcher": {"id": "byName", "options": col},
                "properties": [
                    {
                        "id": "links",
                        "value": [{"title": "Open in the run inspector", "url": url, "targetBlank": True}],
                    }
                ],
            }
        )
    place(
        {
            "type": "table",
            "title": title,
            "description": desc,
            "targets": [target(sql)],
            "fieldConfig": {"defaults": {"custom": {"align": "auto"}}, "overrides": overrides},
            "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
        },
        x,
        w,
        h,
    )


def barchart(
    title: str,
    sql: str,
    x: int,
    w: int,
    h: int,
    unit: str,
    horizontal: bool,
    desc: str = "",
    colors: dict | None = None,
) -> None:
    overrides = by_source() + [
        {
            "matcher": {"id": "byName", "options": n},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}],
        }
        for n, c in (colors or {}).items()
    ]
    place(
        {
            "type": "barchart",
            "title": title,
            "description": desc,
            "targets": [target(sql)],
            "fieldConfig": {
                "defaults": {"unit": unit, "custom": {"fillOpacity": 85, "lineWidth": 0}},
                "overrides": overrides,
            },
            "options": {
                "orientation": "horizontal" if horizontal else "vertical",
                "showValue": "auto",
                "groupWidth": 0.75,
                "barWidth": 0.9,
                "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                "tooltip": {"mode": "multi"},
                "xTickLabelRotation": 0,
            },
        },
        x,
        w,
        h,
    )


# --- runs ------------------------------------------------------------------------------------------
row("Runs: every brief and reply, live from this laptop plus the TACC runs")
stat("Runs", per_source("count(*)"), "none", 0)
stat("Shortlist returned", per_source("100.0 * avg((status = 'done')::int)"), "percent", 4)
stat(
    "Asked a question first",
    per_source("100.0 * avg((status = 'needs_input')::int)"),
    "percent",
    8,
    desc="The brief lacked a budget or campus, so the agent asked once instead of guessing.",
)
stat("Errors", per_source("100.0 * avg((status = 'error')::int)"), "percent", 12, decimals=1)
stat(
    "Median time per brief",
    per_source("percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds)", where=DONE),
    "s",
    16,
    decimals=1,
)
stat(
    "p95 time per brief",
    per_source("percentile_cont(0.95) WITHIN GROUP (ORDER BY seconds)", where=DONE),
    "s",
    20,
    decimals=1,
    desc="Runs stop at the 240 s budget (RUN_MAX_SECONDS) and answer with what they have.",
)
y += 4
stat(
    "Model calls per run",
    per_source("count(*) FILTER (WHERE kind = 'model')::float / count(DISTINCT run_id)", "obs.spans"),
    "none",
    0,
    decimals=1,
)
stat(
    "Tokens per run",
    per_source("sum(tokens_in + tokens_out)::float / count(DISTINCT run_id)", "obs.spans"),
    "short",
    4,
)
stat(
    "Output tokens / s",
    per_source(
        "1000.0 * sum(tokens_out) / nullif(sum(ms), 0)", "obs.spans", "AND kind = 'model' AND tokens_out > 0"
    ),
    "none",
    8,
    decimals=1,
    desc="Tokens written per second of model-call time, reading the prompt included (8B: Ollama on a 16 GB Mac; 27B: vLLM, AWQ INT4, 2 GPUs).",
)
stat(
    "Tool calls per run",
    per_source("count(*) FILTER (WHERE kind = 'tool')::float / count(DISTINCT run_id)", "obs.spans"),
    "none",
    12,
    decimals=1,
)
stat(
    "Tool cache hits",
    per_source("100.0 * avg((attrs->>'cache' = 'hit')::int)", "obs.spans", "AND kind = 'tool'"),
    "percent",
    16,
    desc="Searches, pages, geocodes and routes answered from the cache (the frozen snapshot in evaluation runs).",
)
stat(
    "Replies repaired",
    per_source("100.0 * avg(((attrs->>'attempts')::int > 1)::int)", "obs.spans", "AND kind = 'model'"),
    "percent",
    20,
    decimals=1,
    desc="Typed calls whose first reply failed the JSON schema and needed the one repair retry.",
)
y += 4
timeseries(
    "Runs per hour by outcome",
    f"SELECT $__timeGroupAlias(started_at, '1h'), status AS metric, count(*) AS value FROM obs.runs WHERE {F} GROUP BY 1, 2 ORDER BY 1",
    0,
    12,
    "none",
    "bars",
)
timeseries(
    "Time per brief (each dot is a run that returned a shortlist; resumed runs left out)",
    f"SELECT started_at AS time, source AS metric, seconds AS value FROM obs.runs WHERE {F} {DONE} ORDER BY 1",
    12,
    12,
    "s",
    "points",
)
y += 8

# --- stages ----------------------------------------------------------------------------------------
row("Where the time goes: the seven stages")
barchart(
    "Seconds per run in each stage (average)",
    "SELECT name AS stage, "
    + ", ".join(
        f"sum(ms) FILTER (WHERE source = '{s}') / 1000.0"
        f" / nullif(count(DISTINCT run_id) FILTER (WHERE source = '{s}'), 0) AS \"{s}\""
        for s in SOURCES
    )
    + f" FROM obs.spans WHERE kind = 'stage' AND parent_id IS NULL AND {F}"
    + f" GROUP BY name ORDER BY array_position({STAGES}, name::text)",
    0,
    10,
    9,
    "s",
    True,
    desc="Read (fetch, extract and verify each new page) takes the most time on both models.",
)
table(
    "Stage timings",
    'SELECT name AS "Stage", source AS "Model",'
    ' sum(ms) / 1000.0 / count(DISTINCT run_id) AS "Per run s",'
    ' percentile_cont(0.5) WITHIN GROUP (ORDER BY ms) / 1000 AS "Median s",'
    ' percentile_cont(0.95) WITHIN GROUP (ORDER BY ms) / 1000 AS "p95 s",'
    ' 100.0 * sum(ms) / sum(sum(ms)) OVER (PARTITION BY source) AS "Share of time"'
    f" FROM obs.spans WHERE kind = 'stage' AND parent_id IS NULL AND {F}"
    f" GROUP BY name, source ORDER BY source DESC, array_position({STAGES}, name::text)",
    10,
    14,
    9,
    {"(Per run|Median|p95) s$": ("s", 1), "Share": ("percent", 0)},
    desc="Median and p95 are per stage visit; a run can plan, read and reflect more than once.",
)
y += 9

# --- model -----------------------------------------------------------------------------------------
row("Model calls: every typed call through ModelClient")
table(
    "Model calls by purpose",
    'SELECT name AS "Call", source AS "Model", count(*) AS "Calls",'
    ' percentile_cont(0.5) WITHIN GROUP (ORDER BY ms) / 1000 AS "Median s",'
    ' percentile_cont(0.95) WITHIN GROUP (ORDER BY ms) / 1000 AS "p95 s",'
    ' avg(tokens_in) AS "Tokens in", avg(tokens_out) AS "Tokens out",'
    ' 1000.0 * sum(tokens_out) / nullif(sum(ms) FILTER (WHERE tokens_out > 0), 0) AS "Tokens / s",'
    " 100.0 * avg(((attrs->>'attempts')::int > 1)::int) AS \"Repaired\","
    " 100.0 * avg((attrs->>'cancelled' IS NOT NULL)::int) AS \"Cancelled\""
    f" FROM obs.spans WHERE kind = 'model' AND {F} GROUP BY name, source ORDER BY source DESC, count(*) DESC",
    0,
    24,
    9,
    {
        "(Median|p95) s$": ("s", 1),
        "^Tokens [io]": ("short", 0),
        "Tokens / s": ("none", 1),
        "Repaired|Cancelled": ("percent", 0),
    },
    desc="Cancelled: stopped on purpose, when enough homes were found or the time budget ran out.",
)
y += 9
timeseries(
    "Output tokens per call-second over time",
    f"SELECT $__timeGroupAlias(started_at, '1h'), source AS metric, 1000.0 * sum(tokens_out) / nullif(sum(ms), 0) AS value"
    f" FROM obs.spans WHERE kind = 'model' AND tokens_out > 0 AND {F} GROUP BY 1, 2 ORDER BY 1",
    0,
    24,
    "none",
    "points",
    desc="A drop on the laptop means memory pressure: other apps running beside Ollama.",
)
y += 8

# --- tools -----------------------------------------------------------------------------------------
row("Tools: search, fetch, geocode, route, commute")
table(
    "Tool calls",
    'SELECT name AS "Tool", source AS "Model", count(*) AS "Calls",'
    ' percentile_cont(0.5) WITHIN GROUP (ORDER BY ms) AS "Median ms",'
    ' percentile_cont(0.95) WITHIN GROUP (ORDER BY ms) AS "p95 ms",'
    " 100.0 * avg((attrs->>'cache' = 'hit')::int) AS \"Cache hits\","
    " count(*) FILTER (WHERE attrs->>'cache' = 'miss-offline') AS \"Not in snapshot\","
    ' count(*) FILTER (WHERE error IS NOT NULL) AS "Errors"'
    f" FROM obs.spans WHERE kind = 'tool' AND {F} GROUP BY name, source ORDER BY source DESC, count(*) DESC",
    0,
    15,
    9,
    {"ms$": ("ms", 0), "Cache": ("percent", 0)},
    desc="Not in snapshot: an offline run asked for a page the frozen market never saw; it is skipped, never fetched.",
)
barchart(
    "Cache hit rate by tool",
    "SELECT name AS tool, "
    + ", ".join(
        f"100.0 * avg((attrs->>'cache' = 'hit')::int) FILTER (WHERE source = '{s}') AS \"{s}\""
        for s in SOURCES
    )
    + f" FROM obs.spans WHERE kind = 'tool' AND attrs->>'cache' IS NOT NULL AND {F}"
    + " GROUP BY name ORDER BY count(*) DESC",
    15,
    9,
    9,
    "percent",
    True,
)
y += 9

# --- quality ---------------------------------------------------------------------------------------
row("Answer quality: the scored suite (E1 systems, E2 ablations, E3 on 27B), same formulas as eval/score.py")
QUALITY = (
    ' 100.0 * (1 - sum(violated)::float / nullif(sum(homes), 0)) AS "Within limits",'
    ' 100.0 * sum(confirmed)::float / nullif(sum(homes), 0) AS "All limits confirmed",'
    ' 100.0 * (1 - sum(supported)::float / nullif(sum(facts), 0)) AS "Invented facts",'
    ' 100.0 * avg(outcome_ok::int) AS "Outcome ok"'
)
barchart(
    "Within limits, invented facts and outcome by system",
    f"SELECT CASE WHEN source LIKE '%27B%' THEN '27B ' ELSE '8B ' END || system AS system, {QUALITY} FROM obs.eval"
    " GROUP BY source, system ORDER BY source DESC, array_position(ARRAY['flatjai','b1','b0'], system), system",
    0,
    24,
    9,
    "percent",
    False,
    desc="8B: Qwen 8B on the laptop; 27B: Qwen 27B on TACC. b0: the model alone. b1: one search, the top pages, one answer. flatjai-X: FlatJai with part X switched off.",
    colors={
        "Within limits": "#73bf69",
        "All limits confirmed": "#5794f2",
        "Invented facts": "#f2495c",
        "Outcome ok": "#ff8a5c",
    },
)
y += 9
table(
    "Scored suite",
    f'SELECT source AS "Model", system AS "System", sum(homes) AS "Homes shown", {QUALITY},'
    ' 100.0 * sum(duplicates)::float / nullif(sum(homes), 0) AS "Duplicates",'
    ' 100.0 * sum(cost_off)::float / nullif(sum(cost_figures), 0) AS "Costs off the tool",'
    ' percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds) AS "Median s"'
    " FROM obs.eval GROUP BY source, system ORDER BY source DESC, array_position(ARRAY['flatjai','b1','b0'], system), system",
    0,
    24,
    12,
    {"Within|confirmed|Invented|Outcome|Duplicates|Costs": ("percent", 0), "Median s": ("s", 1)},
    desc="One row per scored brief and repeat (8B ran E1 three times); Median s is wall time per brief.",
)
y += 12

# --- runs list -------------------------------------------------------------------------------------
row("Slowest runs")
table(
    "Slowest runs in the time range (click a run id to open its trace)",
    "WITH m AS (SELECT run_id, count(*) FILTER (WHERE kind = 'model') AS calls, sum(tokens_in + tokens_out) AS tokens,"
    " count(*) FILTER (WHERE kind = 'tool') AS tools FROM obs.spans GROUP BY run_id)"
    ' SELECT r.started_at AS "Started", r.source AS "Model", r.status AS "Status", r.seconds AS "Seconds",'
    ' m.calls AS "Model calls", m.tools AS "Tool calls", m.tokens AS "Tokens", r.id AS "Run", r.brief AS "Brief"'
    " FROM obs.runs r LEFT JOIN m ON m.run_id = r.id WHERE r.source IN ($source) AND $__timeFilter(r.started_at)"
    " AND r.seconds < 600 ORDER BY r.seconds DESC NULLS LAST LIMIT 50",
    0,
    24,
    10,
    {"Seconds": ("s", 1), "Tokens": ("short", 0)},
    links={"Run": INSPECTOR},
    desc="Runs resumed after a restart (over 10 min) are left out. The run inspector (make web) holds"
    " laptop runs only; TACC runs live in eval/results/tacc-*/flatjai.db.",
)

dashboard = {
    "uid": "flatjai",
    "title": "FlatJai: agent observability",
    "description": "Runs, stages, model and tool calls, and answer quality, from FlatJai's own traces in Postgres.",
    "tags": ["flatjai"],
    "timezone": "browser",
    "editable": True,
    "graphTooltip": 1,
    "time": {"from": "now-7d", "to": "now"},
    "refresh": "1m",
    "schemaVersion": 41,
    "templating": {
        "list": [
            {
                "name": "source",
                "label": "Model",
                "type": "query",
                "datasource": DS,
                "query": "SELECT DISTINCT source FROM obs.runs ORDER BY 1 DESC",
                "definition": "SELECT DISTINCT source FROM obs.runs ORDER BY 1 DESC",
                "refresh": 1,
                "multi": True,
                "includeAll": True,
                "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            }
        ]
    },
    "links": [
        {
            "title": "FlatJai",
            "type": "link",
            "url": "http://localhost:3000",
            "targetBlank": True,
            "icon": "external link",
        }
    ],
    "panels": panels,
}

out = Path(__file__).parent / "flatjai.json"
out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {out} ({len(panels)} panels)")
