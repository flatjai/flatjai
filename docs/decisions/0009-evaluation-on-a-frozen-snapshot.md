# 0009 Evaluation on a frozen snapshot, scored by code that does not trust the agent

Date: 2026-11-20 · Status: accepted

## Context
M4 asks for a query suite, baselines and numbers that can be reproduced. Live listing sites change
by the hour and must not be hit by repeated evaluation runs (one request per 2 s per site, decision
0002). The design's full record/replay layer (every tool and model call stored by request hash) is
more than the deadline allows, and most of what it gives is already in the caches FlatJai keeps.

## Decision
- **Snapshot = the caches.** A live pass over the suite fills the page cache (text + raw HTML blobs),
  the extraction cache, and the search, geocode and OTP caches. `scripts/snapshot.sh export` writes
  those three tables and the blobs they point to into `data/snapshot-<date>.tar.zst` (6 MB for 310
  pages); `import` loads it into a fresh database.
- **Offline mode** (`FJ_OFFLINE=1`): pages and searches come only from the cache, whatever their
  age. A page never seen raises "not in the snapshot". A search never seen gets the cached results of
  the most similar earlier query for the same site (word overlap, at least 0.3), because the model
  words its queries a little differently each run. Model calls stay live: the evaluation measures the
  model's decisions on a fixed market.
- **Baselines** use the same model profile and the same snapshot: B0 is one model call with the brief;
  B1 is one search with the brief, the top 5 pages, one model call. B1's search is the brief itself,
  so after its own live pass it replays from exact cache hits.
- **The scorer does not trust the agent.** Each shown home is checked against the case's `truth`
  (the limits as we read the brief), and each shown rent and size must appear on the home's source
  page in the snapshot. Summary figures must match a card, the budget, a relaxation or a difference of
  two of these. A fact the listing does not state is "unknown", reported apart from "violated".

## Consequences
- A fresh clone runs the suite with `make snapshot-import && make eval`: no listing site is touched.
- Not replayed: model calls (each run differs a little; `REPEAT=3` gives the spread), geocoding of a
  building never seen (it calls the government's ALS), OTP (a local server, deterministic per graph).
- Commute is scored against OTP, not against hand-timed journeys; the MTR feed is fitted to
  timetable times instead. Precision@5 needs hand labels and is not reported yet.
