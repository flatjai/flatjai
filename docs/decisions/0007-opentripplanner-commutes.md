# 0007 Real commutes from OpenTripPlanner, with an MTR feed built from open data

Date: 2026-11-19 · Status: accepted

## Context
Decision 0005's commute was an offline estimate: walk or feeder bus to a station, the MTR at a
calibrated speed, a campus last-mile table. Its map joined home, stations and campus with straight
lines, which read as a route but were not the bus or MTR path, so the map was removed (2026-11-18).
The design names OpenTripPlanner (OTP) on the Transport Department's GTFS as the router.

## Decision
- OTP 2.10 runs locally in Docker (`compose.yaml`, profile `otp`) on three inputs, all open data:
  the OpenStreetMap extract for Hong Kong (Geofabrik), the Transport Department's GTFS on
  data.gov.hk (buses, green minibuses, trams, ferries; updated every two weeks), and an MTR GTFS.
- The Transport Department feed has no MTR. `scripts/build_mtr_gtfs.py` writes one from data FlatJai
  already holds (MTR Open Data line orders, station coordinates in `data/mtr.json`), with the
  running times calibrated for 0005 and trains every 4 minutes (8 on branches, 10 on the Airport
  Express and Disneyland lines), 06:00 to 01:00. The MTR publishes no timetable as open data.
- `tools/otp.py` asks for a weekday 08:30 departure (the next Tuesday) and keeps the fastest of
  three itineraries: legs (walk, bus 91B, minibus 11, MTR line) with their minutes and their path.
  Journeys are cached; a failure is not, so OTP coming back helps at once.
- OTP is optional. Without `OTP_URL`, or when it finds no route, the 0005 estimate is used and no
  map is drawn. Tests use a recorded OTP reply and need no server.
- The card's map draws only real leg paths (`RouteMap`): MTR in its line's colour, buses amber,
  minibuses green, walks dotted.

## Results
Hang Hau station -> HKUST: KMB 91B, 18 min, or minibus 11, 19 min (real: about 15 to 20).
Sha Tin -> CUHK 28 min (bus 28K); Tuen Mun -> HKUST 81 min (960X, MTR, minibus 11).
On the 2-bed Tseung Kwan O brief, Park Central went from an estimated 22 min to 37 min,
which includes its 8 min walk to the station.

## Limits
- Bus legs follow the stops, not the road between them (the feed has no shapes): close enough to
  read, not survey-accurate. MTR legs run station to station.
- MTR running times are on the slow side of real (Central -> HKU 7 min, real ~5), so OTP sometimes
  prefers a bus where a student would take the train. Calibrate against OTP before M5.
- Building the graph needs about 3.5 GB in Docker and 90 s; the graph file (~250 MB) is not in git:
  `make otp-graph` rebuilds it.
