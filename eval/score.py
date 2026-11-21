"""Score suite runs (run_suite.py output) and write a Markdown report.

Every check is code, independent of the agent's own checks:
  constraints  each shortlisted home against the case's `truth`: rent vs budget, room vs flat (a
               whole flat also serves an own-room brief, not the other way round),
               bedrooms, commute. Per limit a home is ok, violated, or unknown (the fact is missing).
               Constraint satisfaction = homes with no violated limit / homes shown.
               Confirmed = homes with every limit known and ok / homes shown.
  grounding    each shown rent and size must appear on the home's source page in the snapshot
               (pages table), and the page must exist there at all (else an invented listing).
               Summary figures (HK$ amounts, minutes) must match a figure on a shown card, the
               student's budget, a relaxation or a difference of two of these.
               Invented-fact rate = unsupported figures / figures shown.
  asking       the first turn asks a question exactly when the case says it should.
  outcome      enough homes (min_items), or for infeasible cases: no home that breaks a limit and,
               with nothing shown, concrete relaxations.
  profile      the parsed profile after the last turn has the expected fields (FlatJai only).

Run from backend/:  uv run python ../eval/score.py eval/results/<file>.jsonl [more files]
Writes eval/results/report.md (or --out).
"""

import argparse
import asyncio
import json
import random
import re
import statistics
from collections import defaultdict
from pathlib import Path

import yaml
from sqlalchemy import text

from flatjai.config import settings
from flatjai.storage.store import make_engine

EVAL = Path(__file__).resolve().parent
CASES = {c["id"]: c for c in yaml.safe_load((EVAL / "suite.yaml").read_text())["cases"]}


# --- page lookup -------------------------------------------------------------------------------


async def load_pages(urls: set[str]) -> dict[str, str]:
    """url -> text of the latest stored page (matched on url or final_url)."""
    if not urls:
        return {}
    engine = make_engine(settings().database_url)
    out: dict[str, str] = {}
    async with engine.connect() as c:
        rows = await c.execute(
            text(
                "select url, final_url, text from pages where url = any(:u) or final_url = any(:u) "
                "order by fetched_at"
            ),
            {"u": list(urls)},
        )
        for url, final_url, body in rows:
            out[url] = body or ""
            if final_url:
                out[final_url] = body or ""
    await engine.dispose()
    return out


def number_on_page(n: int, page: str) -> bool:
    flat = page.replace(",", "")
    if re.search(rf"(?<![\d.]){n}(?![\d])", flat):
        return True
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([kK千萬万])", flat):
        mult = {"k": 1000, "K": 1000, "千": 1000, "萬": 10000, "万": 10000}[m.group(2)]
        if round(float(m.group(1)) * mult) == n:
            return True
    return False


# --- per case ----------------------------------------------------------------------------------


def check_home(h: dict, truth: dict) -> dict[str, bool | None]:
    out: dict[str, bool | None] = {}
    rent = h.get("rent_hkd_month")
    share = truth.get("share", 1)
    out["budget"] = None if rent is None else rent / share <= truth["budget"]
    room = truth.get("room", "any")
    if room != "any":  # a whole flat also serves an own-room brief; a room never serves a flat brief
        ro = h.get("room_only")
        out["room"] = None if ro is None else (room == "room" or ro is False)
    if "bedrooms_min" in truth:
        b = h.get("bedrooms")
        out["bedrooms"] = None if b is None else b >= truth["bedrooms_min"]
    if "commute_max" in truth:  # judged on the router's minutes where known (not a model's claim)
        c = h.get("tool_commute_min", h.get("commute_min"))
        out["commute"] = None if c is None else c <= truth["commute_max"]
    return out


_MONEY = re.compile(r"(?:HK\$|\$)\s?(\d[\d,]*)")
_MIN = re.compile(r"(\d+)\s?(?:min|minutes|分鐘)")


_PLACE_WORDS = re.compile(r"\b(?:hong kong|china|tower|block|flat|room|for|rent|in|the)\b|[^a-z0-9 ]", re.I)


def _title_words(title: str) -> frozenset[str]:
    """The building's words: the part after "District ·" when there is one, without filler."""
    building = title.split("·", 1)[-1]
    return frozenset(_PLACE_WORDS.sub(" ", building.lower()).split())


def duplicate_homes(homes: list[dict]) -> int:
    """Shown homes that repeat an earlier one: the same page, or the same rent with the same size or
    mostly the same title words (the scorer's own rule, simpler than the agent's)."""
    dups = 0
    for i, h in enumerate(homes):
        for g in homes[:i]:
            same_page = h["source_url"] == g["source_url"]
            same_rent = h.get("rent_hkd_month") == g.get("rent_hkd_month")
            size = h.get("saleable_sqft") or h.get("gross_sqft")
            same_size = size is not None and size == (g.get("saleable_sqft") or g.get("gross_sqft"))
            a, b = _title_words(h.get("title") or ""), _title_words(g.get("title") or "")
            similar = bool(a and b) and len(a & b) / len(a | b) >= 0.5
            if same_page or (same_rent and (same_size or similar)):
                dups += 1
                break
    return dups


def summary_figures(summary: str) -> list[int]:
    s = summary or ""
    return [int(x.replace(",", "")) for x in _MONEY.findall(s)] + [int(x) for x in _MIN.findall(s)]


def score_case(row: dict, pages: dict[str, str]) -> dict:
    case = CASES[row["case"]]
    truth, expect = case["truth"], case["expect"]
    first, last = row["turns"][0], row["turns"][-1]
    homes = last["homes"]

    checks = [check_home(h, truth) for h in homes]
    violated = sum(any(v is False for v in c.values()) for c in checks)
    confirmed = sum(all(v is True for v in c.values()) for c in checks)
    by_limit: dict[str, list[bool | None]] = defaultdict(list)
    for c in checks:
        for k, v in c.items():
            by_limit[k].append(v)

    facts = supported = invented_listings = 0
    allowed = {truth["budget"]} | {
        int(x) for r in last.get("relaxations") or [] for x in re.findall(r"\d+", r.replace(",", ""))
    }
    for h in homes:
        page = pages.get(h["source_url"])
        if page is None:
            invented_listings += 1
        for key in ("rent_hkd_month", "saleable_sqft", "gross_sqft"):
            if h.get(key) is not None:
                facts += 1
                supported += page is not None and number_on_page(int(h[key]), page)
        allowed |= {
            h.get(k)
            for k in (
                "rent_hkd_month",
                "monthly_hkd",
                "move_in_hkd",
                "saleable_sqft",
                "gross_sqft",
                "commute_min",
            )
            if h.get(k) is not None
        }
    allowed |= {abs(a - b) for a in list(allowed) for b in list(allowed)}
    figs = summary_figures(last.get("summary") or "")
    facts += len(figs)
    supported += sum(f in allowed for f in figs)

    # E2 measures, FlatJai rows only (they carry the tools' figures beside the shown ones)
    commute_err = [
        abs(h["commute_min"] - h["tool_commute_min"])
        for h in homes
        if h.get("commute_min") is not None and h.get("tool_commute_min") is not None
    ]
    cost_pairs = [
        (h[k], h[f"tool_{k}"]) for h in homes for k in ("monthly_hkd", "move_in_hkd") if f"tool_{k}" in h
    ]
    asked = first["asked"] is not None
    ask_ok = asked == expect.get("ask_first", False)
    if expect.get("min_items", 0) == 0:  # infeasible: honest, and helpful when empty
        outcome_ok = violated == 0 and (
            bool(homes) or not expect.get("relaxations") or bool(last["relaxations"])
        )
    else:
        outcome_ok = len(homes) >= expect["min_items"]
    prof = last.get("profile")
    profile_ok = None
    if prof is not None and expect.get("profile"):
        profile_ok = all((str(prof.get(k)).lower() == str(v).lower()) for k, v in expect["profile"].items())
    usage = [t["usage"] for t in row["turns"] if t.get("usage")]
    return {
        "case": row["case"],
        "category": row["category"],
        "system": row["system"],
        "repeat": row["repeat"],
        "homes": len(homes),
        "violated": violated,
        "confirmed": confirmed,
        "by_limit": dict(by_limit),
        "facts": facts,
        "supported": supported,
        "invented_listings": invented_listings,
        "duplicates": duplicate_homes(homes),
        "commute_err": commute_err,
        "cost_figures": len(cost_pairs),
        "cost_off": sum(shown != tool for shown, tool in cost_pairs),
        "summary_figures": len(figs),
        "summary_supported": sum(f in allowed for f in figs),
        "asked": asked,
        "ask_ok": ask_ok,
        "outcome_ok": outcome_ok,
        "profile_ok": profile_ok,
        "seconds": sum(u["seconds"] for u in usage) if usage else row["wall_s"],
        "model_calls": sum(u["model_calls"] for u in usage),
        "tokens": sum(u["tokens_in"] + u["tokens_out"] for u in usage),
        "error": next((t["error"] for t in row["turns"] if t.get("error")), None),
    }


# --- aggregate ---------------------------------------------------------------------------------


def ratio(rows: list[dict], num: str, den: str) -> float | None:
    d = sum(r[den] for r in rows)
    return None if d == 0 else sum(r[num] for r in rows) / d


def boot_ci(rows: list[dict], fn, n: int = 2000) -> tuple[float, float] | None:
    """95% bootstrap interval, resampling cases."""
    if len(rows) < 2:
        return None
    rng, vals = random.Random(7), []
    for _ in range(n):
        v = fn([rows[rng.randrange(len(rows))] for _ in rows])
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def pct(v: float | None, ci: tuple[float, float] | None = None) -> str:
    if v is None:
        return "–"
    return f"{100 * v:.0f}%" + (f" [{100 * ci[0]:.0f}–{100 * ci[1]:.0f}]" if ci else "")


METRICS = {
    "Constraint satisfaction": lambda rs: (
        None
        if not sum(r["homes"] for r in rs)
        else 1 - sum(r["violated"] for r in rs) / sum(r["homes"] for r in rs)
    ),
    "All limits confirmed": lambda rs: ratio(rs, "confirmed", "homes"),
    "Invented facts": lambda rs: (
        None
        if not sum(r["facts"] for r in rs)
        else 1 - sum(r["supported"] for r in rs) / sum(r["facts"] for r in rs)
    ),
    "Invented listings": lambda rs: ratio(rs, "invented_listings", "homes"),
    "Correct ask/no-ask": lambda rs: sum(r["ask_ok"] for r in rs) / len(rs),
    "Outcome ok": lambda rs: sum(r["outcome_ok"] for r in rs) / len(rs),
    "Duplicate homes shown": lambda rs: ratio(rs, "duplicates", "homes"),
    "Cost figures off the cost tool": lambda rs: ratio(rs, "cost_off", "cost_figures"),
}


def report(scored: list[dict]) -> str:
    order = ["b0", "b1", "flatjai"]
    systems = sorted({r["system"] for r in scored}, key=lambda s: (order.index(s) if s in order else 3, s))
    lines = ["# FlatJai evaluation", ""]
    lines += ["## E1 and E2: systems and ablations on the suite (95% bootstrap intervals over cases)", ""]
    lines += ["| Metric | " + " | ".join(systems) + " |", "|---|" + "---|" * len(systems)]
    for name, fn in METRICS.items():
        cells = []
        for s in systems:
            rs = [r for r in scored if r["system"] == s]
            cells.append(pct(fn(rs), boot_ci(rs, fn)))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    for name, key in [
        ("Homes shown per case", "homes"),
        ("Seconds per case (median)", "seconds"),
        ("Model calls per case (median)", "model_calls"),
        ("Tokens per case (median)", "tokens"),
    ]:
        cells = []
        for s in systems:
            vals = [r[key] for r in scored if r["system"] == s]
            cells.append(
                f"{statistics.median(vals):.1f}" if key != "homes" else f"{statistics.mean(vals):.1f}"
            )
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    errs = {s: [e for r in scored if r["system"] == s for e in r["commute_err"]] for s in systems}
    lines.append(
        "| Commute error vs router, min (median / max) | "
        + " | ".join(f"{statistics.median(v):.0f} / {max(v)}" if v else "n/a" for v in errs.values())
        + " |"
    )
    lines += ["", f"Cases: {', '.join(f'{s} {sum(r["system"] == s for r in scored)}' for s in systems)}.", ""]

    lines += ["## By category", ""]
    cats = list(dict.fromkeys(c["category"] for c in CASES.values()))
    lines += [
        "| Category | System | Cases | Homes | Constraint sat. | Invented facts | Ask ok | Outcome ok |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cat in cats:
        for s in systems:
            rs = [r for r in scored if r["system"] == s and r["category"] == cat]
            if rs:
                lines.append(
                    f"| {cat} | {s} | {len(rs)} | {sum(r['homes'] for r in rs)} | "
                    f"{pct(METRICS['Constraint satisfaction'](rs))} | {pct(METRICS['Invented facts'](rs))} | "
                    f"{pct(METRICS['Correct ask/no-ask'](rs))} | {pct(METRICS['Outcome ok'](rs))} |"
                )

    lines += ["", "## Limits checked on shown homes (ok / violated / unknown)", ""]
    lines += ["| System | Limit | ok | violated | unknown |", "|---|---|---|---|---|"]
    for s in systems:
        agg: dict[str, list] = defaultdict(list)
        for r in scored:
            if r["system"] == s:
                for k, v in r["by_limit"].items():
                    agg[k] += v
        for k, v in agg.items():
            lines.append(f"| {s} | {k} | {v.count(True)} | {v.count(False)} | {v.count(None)} |")

    lines += ["", "## Every case", ""]
    lines += [
        "| System | Case | Rep | Homes | Violated | Facts ok | Asked | Outcome | Profile | s | Error |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in scored:
        lines.append(
            f"| {r['system']} | {r['case']} | {r['repeat']} | {r['homes']} | {r['violated']} | "
            f"{r['supported']}/{r['facts']} | {'yes' if r['asked'] else 'no'} | "
            f"{'ok' if r['outcome_ok'] else 'FAIL'} | {'' if r['profile_ok'] is None else ('ok' if r['profile_ok'] else 'FAIL')} | "
            f"{r['seconds']:.0f} | {(r['error'] or '')[:60]} |"
        )
    return "\n".join(lines) + "\n"


def ablation_mismatches(rows: list[dict]) -> list[str]:
    """Rows labelled `flatjai-<ablation>` whose run did not record that ablation as active (the first
    E2 run on 2026-11-21 ran the full agent under ablation labels)."""
    bad = []
    for r in rows:
        named = sorted(r["system"].split("-")[1:]) if r["system"].startswith("flatjai-") else []
        if named and r.get("ablate") != named:
            bad.append(f"{r['system']}/{r['case']}")
    return sorted(set(bad))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=EVAL / "results" / "report.md")
    args = ap.parse_args()
    rows = [json.loads(line) for f in args.files for line in f.read_text().splitlines() if line.strip()]
    if bad := ablation_mismatches(rows):
        raise SystemExit(f"ablation named in the label but not active in the run: {bad}")
    urls = {h["source_url"] for r in rows for t in r["turns"] for h in t["homes"]}
    pages = await load_pages(urls)
    scored = [score_case(r, pages) for r in rows]
    args.out.write_text(report(scored))
    (args.out.with_suffix(".jsonl")).write_text("\n".join(json.dumps(s, default=str) for s in scored) + "\n")
    print(args.out.read_text())


if __name__ == "__main__":
    asyncio.run(main())
