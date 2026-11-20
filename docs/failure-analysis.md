# Failure analysis

Failures found by the query suite (`eval/suite.yaml`) on Qwen3 8B (local), 2026-11-20. Each has a
failing case, its trace, the root cause, the fix and the measured before and after. Every fix has a
test that reproduces the failure.

## 1. The agent stopped complete briefs to ask for a move-in date

**Seen.** First live pass: 12 of 20 briefs ended in a question, 9 of them complete. "Room near
CityU, budget 7,000 per month, max 35 minutes commute" got "When do you need to move in?" and no
search. All three infeasible briefs ended the same way, so they never said that nothing fits.

**Root cause.** Understand computes the missing hard fields in code (budget, campus, move-in) and
lets the model decide whether to ask (`decide_clarify`). Qwen asked whenever anything was missing.
Move-in barely matters to the search: listings rarely state availability, and on cards the move-in
check is almost always "?". The question cost the student a round trip for an unchanged answer.

**Fix.** Code decides that a question needs a missing budget or campus; move-in is only asked
together with one of them (`agent/loop.py`, `BLOCKING`). The model still words the question.
Test: `test_a_missing_move_in_alone_never_stops_the_search`.

**Before and after** (same 20 briefs, live):

| | Before | After |
|---|---|---|
| Correct ask/no-ask | 40% | 95% |
| Outcome ok | 50% | 90% |
| Homes shown per brief | 2.1 | 3.1 |

The one remaining wrong ask was failure 3.

## 2. The same home on two sites was shown twice, and both were called the cheapest

**Seen.** "Own room, max HK$9,000, under 40 min to HKUST": the shortlist held "Tseung Kwan O ·
East Point City" and "Hang Hau East Point City", both HK$4,800 a month, from two sites. The summary
said each was the cheapest.

**Root cause.** Duplicate detection compared whole names. Each site puts the district around the
estate in its own way, so the names never matched.

**Fix.** Estates are compared without district and MTR station names (`agent/match.py`,
`estate_core`), with the rent within 5% as before. A name that is only a place ("Hang Hau") is
still compared in full, so two different homes in one district are not merged.
Test: `test_the_same_estate_named_differently_on_two_sites_is_one_home`.

## 3. Campuses written in or next to Chinese were lost or swapped

**Seen.** "想租港大附近嘅開放式單位, budget 15k, 30分鐘內返到學校" (a studio near HKU) was searched
for HKUST, on the other side of Hong Kong, and found nothing. "CUHK附近 own room, 每月6500以下,
40 min 內" put "CUHK" under districts with no campus, and the agent asked which campus.

**Root cause.** Two things. The model read 港大 (HKU) as HKUST, and the code that fills in a
campus the student named only ran when the model left the campus empty, never when it chose a
different one. Separately, that code matched `\bcuhk\b`: in Python a CJK character is a word
character, so there is no word boundary between "CUHK" and "附", and the name was not found.

**Fix.** Campus names match with ASCII-only boundaries. A campus the student names overrides a
different one from the model. A campus name is removed from districts (`agent/understand.py`).
Test: `test_campuses_written_next_to_chinese_are_found_and_win_over_the_model`.

**Before and after:** the HKU studio brief went from 0 homes (searched near HKUST) to 3 in Kennedy
Town and Sheung Wan; the CUHK room brief from a question to 4 homes, with no question asked.

## 4. Commutes leaned on buses because the MTR feed ran slow

**Seen.** OpenTripPlanner chose buses where students take the train. Its MTR legs were slow:
Mong Kok -> Central 14 min (timetable about 11), Central -> HKU 6.6 min (about 5).

**Root cause.** The MTR GTFS FlatJai builds from open data (the MTR publishes no timetable) reused
the speeds tuned for the offline estimate. Those were fitted to door-to-door journeys, waits
included, and OTP adds its own waits on top.

**Fix.** The feed's speeds are fitted to end-to-end timetable times (Tsuen Wan line 30 min, East
Rail Hung Hom -> Lo Wu 42, Airport Express 24): urban lines 770 m/min, East Rail, Tuen Ma and
Tung Chung 950, Airport Express 1,450 (`scripts/build_mtr_gtfs.py`).

**Before and after:** Tsuen Wan line 39 -> 30 min, Central -> HKU 6.6 -> 5.2, Mong Kok -> Central
13.9 -> 10.7 (OTP leg 14 -> 11). Still open: Sha Tin -> CUHK takes minibus 28K (29 min) where East
Rail to University and a walk may be quicker.

## 5. A 1-bedroom flat brief shortlisted five rooms on one run of three

**Seen.** Offline evaluation, three repeats: "1-bedroom flat for one, PolyU, up to 18k a month"
showed five Amber rooms (HK$4,900 to 5,600) on every repeat. The scorer flagged all 15 as breaking
the brief, so FlatJai's constraint satisfaction was 93%, the only violations in 60 runs.

**Root cause.** Qwen parsed the brief as `room_only: true` with `bedrooms: 1`. The match rule ("a
room never passes a whole-flat brief") is right, but it trusts the profile, and the profile said a
room. On the live pass the same brief had parsed as a whole flat: this is run-to-run variance in a
small model, which only repeats expose.

**Fix.** Like a studio, a brief that names a flat, an apartment or a bedroom count and no room
phrase ("own room", "single room") is a whole flat, held in code (`agent/understand.py`, `_WHOLE`).
"Own room in a shared flat" stays a room.
Test: `test_a_flat_brief_is_a_whole_flat_even_if_the_model_says_room`.

**Before and after:** constraint satisfaction 93% -> 100% over 60 runs; the brief now shows five
whole flats near PolyU on every repeat (`20261120-1602` vs `20261120-1637-flatjai-offline.jsonl`).

## 6. Our own scorer at first counted unknown room types as whole flats

**Seen.** The scorer's first version marked an own-room home as breaking the brief: a uhomes room
at HK$4,800, shown by FlatJai as "room or whole flat not stated".

**Root cause.** The `Listing` schema defaults `room_only` to false, so "not stated" and "a whole
flat" look the same in the stored listing. The agent's own check already treated it as unknown;
the scorer read the raw field.

**Fix.** The scorer counts a room as known only when its page says so (evidence) or gives a bedroom
count, and a whole flat also serves an own-room brief, the same one-way rule the agent applies.
Pinned in `backend/tests/test_eval_score.py`. Lesson: an evaluator needs tests as much as the agent.
