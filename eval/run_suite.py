"""Run the query suite (eval/suite.yaml) on one system and write one JSON line per case.

Systems (experiment E1):
  flatjai  the full agent, through the same RunManager the API uses (every turn, in order)
  b1       one search with the brief, read the top pages, one model call writes the shortlist
  b0       the model alone: one call, no tools

Every system returns homes in one shape (source_url, title, rent, size, bedrooms, room, commute), so
score.py scores them the same way. B0 and B1 see all turns joined into one brief and cannot ask.

Run from backend/ (FJ_OFFLINE=1 for the frozen snapshot):
  uv run python ../eval/run_suite.py --system flatjai [--cases id1,id2] [--repeat 3] [--tag name]
  uv run python ../eval/run_suite.py --system flatjai --ablate no_reflect   # E2, see agent/ablations.py
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel, Field

from flatjai.agent.ablations import parse_ablations
from flatjai.api import build_run_manager
from flatjai.config import active_profile, settings
from flatjai.model_client import ModelClient
from flatjai.storage.blobs import BlobStore
from flatjai.storage.store import Store, make_engine
from flatjai.tools.cache import CachedFetcher, CachedSearcher
from flatjai.tools.fetch import Fetcher, FetchError
from flatjai.tools.portals import PORTALS
from flatjai.tools.search import Searcher, SearchError

EVAL = Path(__file__).resolve().parent
RESULTS = EVAL / "results"


def load_cases(only: set[str] | None, drafts: bool = False) -> list[dict]:
    """Reviewed cases; drafts (status: draft, not yet in the snapshot) only when asked or named."""
    cases = yaml.safe_load((EVAL / "suite.yaml").read_text())["cases"]
    if only:
        return [c for c in cases if c["id"] in only]
    return [c for c in cases if drafts or c.get("status") != "draft"]


# --- FlatJai -----------------------------------------------------------------------------------


def home_from_card(card: dict, rank: int, reasons: list[str]) -> dict:
    lst, commute = card["listing"], card.get("commute") or {}
    return {
        "rank": rank,
        "source_url": lst["source_url"],
        "title": lst["title"],
        "rent_hkd_month": lst["rent_hkd_month"],
        "saleable_sqft": lst.get("saleable_sqft"),
        "gross_sqft": lst.get("gross_sqft"),
        "bedrooms": lst.get("bedrooms"),
        # stated on the page, or implied by a bedroom count; else unknown (the field defaults to false)
        "room_only": lst.get("room_only")
        if "room_only" in (lst.get("evidence") or {}) or lst.get("bedrooms") is not None
        else None,
        "commute_min": commute.get("minutes"),
        "commute_method": commute.get("method"),
        "monthly_hkd": card["cost"]["monthly_hkd"],
        "move_in_hkd": card["cost"]["move_in_hkd"],
        # the tools' figures: the same as shown, except under the model_facts ablation (E2)
        "tool_commute_min": commute.get("tool_minutes", commute.get("minutes")),
        "tool_monthly_hkd": card["cost"].get("tool_monthly_hkd", card["cost"]["monthly_hkd"]),
        "tool_move_in_hkd": card["cost"].get("tool_move_in_hkd", card["cost"]["move_in_hkd"]),
        "reasons": reasons,
    }


async def run_flatjai(case: dict, runs, store: Store) -> dict:
    session, turns = None, []
    for text in case["turns"]:
        run, _ = await runs.start(text, session_id=session)
        session = run.session_id
        await runs.tasks[run.id]
        events = [(e.type, e.data) for e in await store.events(run.id)]
        cards = {d["listing_id"]: d for t, d in events if t == "card"}
        profile = next((d["profile"] for t, d in reversed(events) if t == "state" and d.get("profile")), None)
        done = next((d for t, d in events if t == "done"), None)
        clarify = next((d for t, d in events if t == "clarify"), None)
        error = next((d["message"] for t, d in events if t == "error"), None)
        homes = []
        if done:
            for item in done["shortlist"]:
                if item["listing_id"] in cards:
                    homes.append(
                        home_from_card(cards[item["listing_id"]], item["rank"], item.get("reasons", []))
                    )
        turns.append(
            {
                "run_id": run.id,
                "asked": clarify["question"] if clarify else None,
                "profile": profile,
                "homes": homes,
                "summary": done["summary"] if done else None,
                "relaxations": done["relaxations"] if done else [],
                "usage": done["usage"] if done else None,
                "error": error,
            }
        )
    return {"session_id": session, "turns": turns}


# --- Baselines ---------------------------------------------------------------------------------


class BaselineHome(BaseModel):
    title: str = Field(description="Building or estate name with district")
    source_url: str = Field(description="Link to the listing")
    rent_hkd_month: int
    saleable_sqft: int | None = None
    bedrooms: int | None = None
    room_only: bool | None = Field(None, description="true: a room in a shared flat; false: a whole flat")
    commute_min: int | None = Field(None, description="One-way minutes to the student's campus")
    reason: str = ""


class BaselineAnswer(BaseModel):
    summary: str
    homes: list[BaselineHome] = Field(default_factory=list, max_length=5)


B0_SYSTEM = (
    "You help a university student in Hong Kong find a home to rent. Reply with up to 5 specific homes "
    "that fit the brief: building, link, monthly rent, size, bedrooms, room or whole flat, commute to "
    "campus. If nothing fits, return no homes and say what to change."
)
B1_SYSTEM = (  # B1: one model-written query on each readable site, the top pages, one answer
    "You help a university student in Hong Kong find a home to rent. Below are listing pages found by "
    "one web search. Reply with up to 5 homes from these pages that fit the brief, using only facts on "
    "the pages, with each home's page URL as source_url. If nothing fits, return no homes and say what "
    "to change."
)
B1_PAGES, B1_CHARS = 5, 2500
B1_SITES = ("centaline", "uhomes", "amber")  # the sites FlatJai can read; free engines need "site:"


class SearchQuery(BaseModel):
    query: str = Field(description="One short web search query for rental listings, in English")


QUERY_SYSTEM = (
    "Write ONE short web search query (4 to 8 words) that would find rental listings in Hong Kong for "
    "this student's brief, e.g. 'room for rent Hang Hau' or '2 bedroom flat for rent Kennedy Town'."
)


async def run_baseline(system: str, case: dict, model: ModelClient, searcher, fetcher) -> dict:
    brief = " ".join(case["turns"])
    client = model.for_run()
    started = time.monotonic()
    pages_used: list[str] = []
    if system == "b0":
        user = f"Brief: {brief}"
        prompt = B0_SYSTEM
    else:
        q = await client.typed_call("b1_query", QUERY_SYSTEM, f"Brief: {brief}", SearchQuery)
        results = []
        for site in B1_SITES:  # the one query, on each readable site
            try:
                results += await searcher.search(q.query, portal=portal_by_name(site))
            except SearchError:
                pass
        results.sort(key=lambda r: r.kind != "listing")  # listing pages before list pages, stable
        texts = []
        for r in results:
            if len(texts) >= B1_PAGES:
                break
            try:
                page = await fetcher.fetch(r.url)
            except FetchError:
                continue
            pages_used.append(r.url)
            texts.append(f"URL: {r.url}\nTITLE: {page.title}\n{page.text[:B1_CHARS]}")
        user = f"Brief: {brief}\n\n" + ("\n\n---\n\n".join(texts) if texts else "(the search found no pages)")
        prompt = B1_SYSTEM
    error = None
    try:
        ans = await client.typed_call(f"{system}_answer", prompt, user, BaselineAnswer)
    except Exception as e:  # noqa: BLE001 - a failed call is a failed case, not a crash of the suite
        ans, error = BaselineAnswer(summary=""), f"{type(e).__name__}: {e}"
    homes = [
        {
            **h.model_dump(),
            "rank": i + 1,
            "gross_sqft": None,
            "commute_method": "model",
            "reasons": [h.reason],
        }
        for i, h in enumerate(ans.homes)
    ]
    calls = client.calls
    return {
        "pages_read": pages_used,
        "query": q.query if system == "b1" else None,
        "turns": [
            {
                "asked": None,
                "profile": None,
                "homes": homes,
                "summary": ans.summary,
                "relaxations": [],
                "usage": {
                    "seconds": round(time.monotonic() - started, 1),
                    "model_calls": len(calls),
                    "tokens_in": sum(c.tokens_in for c in calls),
                    "tokens_out": sum(c.tokens_out for c in calls),
                },
                "error": error,
            }
        ],
    }


def portal_by_name(name: str):
    return next(p for p in PORTALS if p.name == name)


# --- Main --------------------------------------------------------------------------------------


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=["flatjai", "b0", "b1"], required=True)
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--tag", default="")
    ap.add_argument("--drafts", action="store_true", help="include draft cases (e.g. to record them live)")
    ap.add_argument("--ablate", default="", help="E2: comma-separated parts to switch off (flatjai only)")
    args = ap.parse_args()
    ablate = parse_ablations(args.ablate)  # given to the run manager: settings() is cached at import
    if ablate and args.system != "flatjai":
        ap.error("--ablate applies to --system flatjai only")
    label = args.system + "".join(f"-{a.strip()}" for a in args.ablate.split(",") if a.strip())

    s = settings()
    cases = load_cases(set(args.cases.split(",")) if args.cases else None, drafts=args.drafts)
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    out = RESULTS / f"{stamp}-{label}{'-' + args.tag if args.tag else ''}.jsonl"
    profile = active_profile()
    print(
        f"{label} on {profile.name} ({profile.model}), offline={s.fj_offline}, "
        f"{len(cases)} cases x {args.repeat} -> {out.relative_to(EVAL.parent)}"
    )

    engine = make_engine(s.database_url)
    store = Store(engine)
    model = ModelClient(profile)
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
        runs = build_run_manager(http, model, store, ablate=ablate) if args.system == "flatjai" else None
        blobs = BlobStore(s.data_dir / "blobs")
        fetcher = CachedFetcher(
            Fetcher(
                http,
                blobs,
                user_agent=s.user_agent,
                min_interval_s=s.min_fetch_interval_s,
                max_chars=s.page_text_max_chars,
            ),
            store,
            blobs,
            offline=s.fj_offline,
        )
        searcher = CachedSearcher(Searcher(http, s.searxng_url), store, offline=s.fj_offline)
        with out.open("w") as f:
            for rep in range(args.repeat):
                for case in cases:
                    t0 = time.monotonic()
                    if runs is not None:
                        result = await run_flatjai(case, runs, store)
                    else:
                        result = await run_baseline(args.system, case, model, searcher, fetcher)
                    row = {
                        "case": case["id"],
                        "category": case["category"],
                        "system": label,
                        "repeat": rep,
                        "model": profile.model,
                        "profile": profile.name,
                        "offline": s.fj_offline,
                        "ablate": sorted(runs.budget.ablate) if runs is not None else [],
                        "wall_s": round(time.monotonic() - t0, 1),
                        **result,
                    }
                    f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                    f.flush()
                    last = result["turns"][-1]
                    print(
                        f"  [{rep}] {case['id']:28s} {row['wall_s']:6.1f}s  homes={len(last['homes'])}"
                        f"{'  asked' if result['turns'][0]['asked'] else ''}"
                        f"{'  ERROR ' + last['error'] if last['error'] else ''}",
                        flush=True,
                    )
        if runs is not None:
            await runs.shutdown()
    await engine.dispose()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
