# eval

The query suite, the baselines and the scorer.

| File | What it is |
|---|---|
| `suite.yaml` | 20 student briefs in 7 categories, each with the student's hard limits as we read them (`truth`) and what a good answer does (`expect`) |
| `run_suite.py` | Runs one system over the suite and writes one JSON line per case to `results/` |
| `score.py` | Scores result files with its own code and writes `results/report.md` |
| `understand_check.py` | The Understand stage alone: briefs to expected profile fields (`make eval-understand`) |

## Systems

- **flatjai**: the full agent, through the same `RunManager` the API uses, every turn in order.
- **b1**: one search with the brief, the top 5 pages read, one model call writes the shortlist.
- **b0**: the model alone, one call, no tools.

All three use the active model profile (`FJ_MODEL`), so a comparison is about the system, not the model.
B0 and B1 get all turns joined into one brief and cannot ask a question.

## Ablations (E2)

`FJ_ABLATE` (or `run_suite.py --ablate`) switches off one agent part; see `backend/src/flatjai/agent/ablations.py`.

| Ablation | What is off | What the scorer shows |
|---|---|---|
| `no_reflect` | read-more and re-plan: one search pass, then answer | homes per brief, outcome ok |
| `no_dedup` | merging the same home found twice | duplicate homes shown |
| `model_facts` | the cost tool and the router: the model states cost and commute | cost figures off the cost tool, commute error vs router, limits judged on the router's minutes |

```
make ablate                       # the three ablations offline, then one report with E1
make ablate ABLATIONS=no_dedup REPEAT=3
```

### E2 results (2026-11-21, Qwen 8B, snapshot, 20 briefs x 1)

| Metric | FlatJai | no_reflect | no_dedup | model_facts |
|---|---|---|---|---|
| Constraint satisfaction | 100% | 100% | 100% | 76% |
| Outcome ok | 100% | 90% | 100% | 85% |
| Homes shown per brief | 3.5 | 2.6 | 3.6 | 2.7 |
| Duplicate homes shown | 0% | 0% | 3% | 0% |
| Cost figures off the cost tool | 0% | 0% | 0% | 100% |
| Commute error vs router (median / max) | 0 | 0 | 0 | 17 / 29 min |
| Seconds per brief (median) | 26 | 17 | 26 | 38 |

Without the tools the model understated every cost (monthly by a median HK$600, move-in by HK$18,900)
and put 24% of shown homes over a limit the router would have caught. Without re-planning, harder
briefs end with fewer or no homes. Duplicates matter less on this snapshot than expected. Full table
with intervals: `results/report.md`.

## E3: Qwen3.8-27B on TACC (2026-11-22, 20 briefs x 1, snapshot)

Run inside TACC with `scripts/run-e3.sh` (see `deploy/tacc/README.md`); report: `results/report-tacc.md`.

| Metric | B0 | B1 | FlatJai | FlatJai, model_facts |
|---|---|---|---|---|
| Constraint satisfaction | – | 100% | 100% | 81% |
| All limits confirmed | – | 25% | 62% (8B: 52%) | 40% |
| Invented facts | – | 52% | 0% | 0% |
| Outcome ok | 0% | 10% | 100% | 100% |
| Cost figures off the cost tool | – | – | 0% | 100% (move-in median HK$3,000 low) |
| Commute error vs router (median / max) | – | – | 0 | 13 / 39 min |
| Seconds per brief (median) | 0.4 | 5.2 | 19.1 (8B: 26.3) | 22.4 |

The larger model confirms more limits and runs faster on the GPUs, but the baselines stay poor and
the model's own cost and commute figures stay wrong: the design (tools for facts, checks in code)
carries the honesty on both models.

## Draft cases

Cases 21 to 50 in `suite.yaml` carry `status: draft`: written, not yet reviewed, and not yet in the
snapshot. `make eval` skips them. To add them: review each `truth`, record their pages with one live
pass (`FJ_OFFLINE=0 uv run python ../eval/run_suite.py --system flatjai --drafts --tag record`),
`make snapshot`, then drop the `status` lines.

## Frozen snapshot

A live run caches every page, search, extraction, geocode and OTP journey in Postgres. With
`FJ_OFFLINE=1` FlatJai reads only that cache: a page never seen is "not in the snapshot", and a search
never seen gets the cached results of the most similar earlier query for the same site. So a suite run
on the snapshot never touches a listing site, and two runs see the same market.

```
make snapshot            # cache -> data/snapshot-<date>.tar.zst (pages, extractions, tool answers)
make snapshot-import     # a fresh clone loads it (SNAPSHOT=file for an older one)
make eval                # b0, b1, flatjai offline on the snapshot, then the report
make eval SYSTEMS=flatjai REPEAT=3
make eval-score          # rescore the latest result of each system
```

The snapshot is recorded by one live pass: `FJ_OFFLINE=0 uv run python ../eval/run_suite.py --system flatjai --tag record`.

## What the scorer checks (all in code, none from the agent's own checks)

| Metric | Definition |
|---|---|
| Constraint satisfaction | shown homes with no limit broken / shown homes. A limit is broken only when the fact is known and fails; an unknown fact (no bedroom count) is counted separately |
| All limits confirmed | shown homes with every limit known and met / shown homes |
| Invented facts | shown rents and sizes not found on the home's page in the snapshot, plus summary figures (HK$, minutes) that match no card, budget, relaxation or difference of two of these, / all such figures |
| Invented listings | shown homes whose page is not in the snapshot / shown homes |
| Correct ask/no-ask | the first turn asks a question exactly when the brief is missing something essential |
| Outcome ok | enough homes; for an infeasible brief, no home that breaks a limit and, when empty, concrete relaxations |

Rules worth knowing: a whole flat also serves an own-room brief (not the other way round), the same
rule the agent uses; a room counts as known only when its page says so or gives a bedroom count. The
rules are pinned by `backend/tests/test_eval_score.py`.

## Results (2026-11-20, Qwen3 8B local, frozen snapshot, 20 briefs x 3 repeats)

Full tables: `results/report.md`. Failures found on the way and their fixes: `docs/failure-analysis.md`.

| | B0 model only | B1 search + answer | FlatJai |
|---|---|---|---|
| Invented facts | 85% | 44% | **0%** |
| Invented listings | 100% | 0% | **0%** |
| Constraint satisfaction | 100%* | 71% | **100%** |
| All limits confirmed | 100%* | 36% | 52% |
| Correct ask/no-ask | 85% | 85% | **100%** |
| Outcome ok | 12% | 15% | **100%** |
| Homes per brief | 0.6 | 0.7 | 3.5 |
| Seconds per brief (median) | 2.8 | 8.1 | 26.3 |

\* B0's homes do not exist (every one is an invented listing), so its "limits met" are its own claims.

Reading it: on most briefs Qwen 8B alone declines to name homes, and when it does, they are made
up. B1 reads real pages but cannot check a commute, so it mostly declines too; when it answers, it
offers rooms for flat briefs and figures not on the page. FlatJai meets every hard limit it can
check and shows no figure that is not on its source page. "All limits confirmed" is 52% because many
pages do not say whether a home is a room (94 of 207 unknown) or how many bedrooms a flat has (36 of
39 unknown): FlatJai shows these as "?" and puts them in "What to ask the agent".

Times are on the snapshot with cached extractions; a live run on the laptop takes 20 to 210 s.

## Limits of this evaluation

- Commute is checked against the commute FlatJai shows (OpenTripPlanner on open data), not against
  journeys timed by hand. The OTP feed's MTR running times are fitted to timetable times
  (`backend/scripts/build_mtr_gtfs.py`).
- B0 and B1 commutes are the model's own claims; they are scored as claimed.
- 20 cases, so intervals are wide. Precision@5 against hand labels and the LLM-judged explanation
  quality from the design are not built yet.
