# 0005 Skip what surely cannot fit before the model; estimate commutes offline

Date: 2026-11-16 · Status: accepted

## Context
Traces showed most model time went on listings that could never fit: a laptop extraction takes
about 25 s, and in one run 5 of 7 listings read were over budget. Commute was part of every brief,
but only an interim table of "areas near each campus" stood in for it.

## Decision: pre-filter (`tools/preview.py`, `agent/match.quick_reject`)
- Centaline's rental list prints each listing's rent, size, rooms and district inside its link;
  a listing page prints its labelled rent ("Rent $13,500"). Both are read with regexes.
- A listing is skipped before any model call only when it surely fails: the rent alone is over the
  budget (rent is a floor on the monthly cost; shared and total budgets handled), or its district
  is out of reach under a commute limit. Unknowns are always read. Promising listings go first.
- These figures are never shown as facts: every figure on a card is still verified on the
  listing's own page. Skipped listings' rents feed "about" budget suggestions only.
- Result: a HK$30,000 shared-flat brief went from ~240 s (2 homes) to 73 s (5 homes); a 9k
  own-room brief finished on its own with 14 model calls instead of hitting the time budget.

## Decision: commute estimate (`tools/geocode.py`, `tools/transit.py`)
The design's router is OpenTripPlanner on Transport Department GTFS; its stated fallback is a
straight-line + MTR model, used now because it needs no server and runs offline:
- Geocode: the Address Lookup Service (free, government), accepted only when the matched estate
  or building shares a word with the listing's name; otherwise the district is located and the
  result is marked "area". Cached permanently.
- Transit: official MTR line sequences (MTR Open Data) with station coordinates from Wikipedia
  page summaries (validated to lie in Hong Kong), built once into `data/mtr.json` by
  `scripts/build_mtr.py`. Walk or feeder bus to one of the 3 nearest stations, the shortest MTR
  route (~33 km/h, 30 s stops, 3 min wait, 4 min per line change), then a campus last-mile table;
  or a direct bus for homes within 8 km. The faster wins.
- With a commute limit it is a hard check and replaces the interim area check; it is always shown
  as "~N min" and labelled an estimate.

## Sources tried and rejected
ALS for MTR stations (matched Diamond Hill, Hang Hau and HKU to Hung Hom), the Overpass API (all
mirrors at capacity), Nominatim (empty results), the Wikidata query service (errors).

## Consequences and next steps
- Campus last-mile minutes are estimates; the evaluation's commute-error metric (design section 12)
  must check the model against real journeys and recalibrate the constants.
- Homes in areas without MTR (Sai Kung, Clear Water Bay) rely on the feeder-bus or direct-bus
  estimate, the weakest part of the model; OpenTripPlanner with GTFS would fix it.
