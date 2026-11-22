"""Build infra/otp/data/mtr-gtfs.zip: the MTR as a GTFS feed for OpenTripPlanner.

The Transport Department's GTFS (data.gov.hk) covers buses, minibuses, trams and ferries, but not the
MTR. This feed adds it from data FlatJai already holds: each line's station order (MTR Open Data)
and station coordinates (src/flatjai/data/mtr.json). Trains run every few minutes all day (GTFS
frequencies), since the MTR publishes no timetable as open data.

Running times: straight-line distance x TRACK_FACTOR at a line speed, plus DWELL_MIN per stop. The
speeds are fitted to end-to-end timetable times (2026-11-20), not to door-to-door journeys:
  Tsuen Wan line Central -> Tsuen Wan 30 min (the old 33 km/h gave 39), East Rail Hung Hom -> Lo Wu
  42 min (gave 47), Airport Express Hong Kong -> Airport 24 min (gave 27).
Checked on short rides: Central -> HKU 5.2 min (real ~5, was 6.6), Mong Kok -> Central 10.7 (real
~11, was 13.9). The offline estimate (tools/transit.py) keeps its slower speeds on purpose: they
were tuned door to door, with waits and interchanges folded in, which OTP models itself.

Run: cd backend && uv run python ../scripts/build_mtr_gtfs.py
"""

import csv
import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

from flatjai.tools.transit import DWELL_MIN, TRACK_FACTOR, distance_m

URBAN_M_PER_MIN = 770  # ~46 km/h between stops
LINE_M_PER_MIN = {"EAL": 950, "TML": 950, "TCL": 950, "AEL": 1450}

ROOT = Path(__file__).resolve().parents[1]
MTR = ROOT / "backend/src/flatjai/data/mtr.json"
OUT = ROOT / "infra/otp/data/mtr-gtfs.zip"

NAMES = {
    "AEL": "Airport Express",
    "DRL": "Disneyland Resort Line",
    "EAL": "East Rail Line",
    "ISL": "Island Line",
    "KTL": "Kwun Tong Line",
    "SIL": "South Island Line",
    "TCL": "Tung Chung Line",
    "TKL": "Tseung Kwan O Line",
    "TML": "Tuen Ma Line",
    "TWL": "Tsuen Wan Line",
}
COLOURS = {  # MTR's own line colours, for the map
    "AEL": "00888A",
    "DRL": "F550A6",
    "EAL": "5EB6E4",
    "ISL": "0860A8",
    "KTL": "1A9431",
    "SIL": "B5BD00",
    "TCL": "F38B00",
    "TKL": "6B208B",
    "TML": "9A3B26",
    "TWL": "E2231A",
}
HEADWAY_S = {"main": 240, "branch": 480, "AEL": 600, "DRL": 600}  # off-peak-ish, a fair average
SERVICE_HOURS = ("06:00:00", "25:00:00")  # first to last train, roughly


def hhmmss(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def hop_seconds(line: str, a: dict, b: dict) -> float:
    speed = LINE_M_PER_MIN.get(line, URBAN_M_PER_MIN)
    return (distance_m((a["lat"], a["lon"]), (b["lat"], b["lon"])) * TRACK_FACTOR / speed + DWELL_MIN) * 60


def build(mtr: dict, today: date) -> dict[str, list[list[str]]]:
    stations, lines = mtr["stations"], mtr["lines"]
    used = sorted({code for seq in lines.values() for code in seq})
    tables: dict[str, list[list[str]]] = {
        "agency.txt": [
            ["agency_id", "agency_name", "agency_url", "agency_timezone"],
            ["MTR", "MTR", "https://www.mtr.com.hk", "Asia/Hong_Kong"],
        ],
        "stops.txt": [["stop_id", "stop_name", "stop_lat", "stop_lon"]]
        + [[f"MTR_{c}", stations[c]["name"], str(stations[c]["lat"]), str(stations[c]["lon"])] for c in used],
        "routes.txt": [
            ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color"]
        ],
        "calendar.txt": [
            [
                "service_id",
                *"monday tuesday wednesday thursday friday saturday sunday".split(),
                "start_date",
                "end_date",
            ],
            [
                "DAILY",
                *["1"] * 7,
                (today - timedelta(days=30)).strftime("%Y%m%d"),
                (today + timedelta(days=365)).strftime("%Y%m%d"),
            ],
        ],
        "trips.txt": [["route_id", "service_id", "trip_id", "trip_headsign", "direction_id"]],
        "stop_times.txt": [["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]],
        "frequencies.txt": [["trip_id", "start_time", "end_time", "headway_secs", "exact_times"]],
    }
    for line in sorted({k.split("-")[0] for k in lines}):
        rail = "2" if line == "AEL" else "1"  # Airport Express: rail; the rest: metro
        tables["routes.txt"].append(
            [line, "MTR", line, NAMES.get(line, line), rail, COLOURS.get(line, "888888")]
        )
    for key, seq in sorted(lines.items()):
        line = key.split("-")[0]
        branch = key.count("-") > 1  # EAL-LMC-DT, TKL-TKS-DT: a branch shares the line's track
        headway = HEADWAY_S.get(line, HEADWAY_S["branch" if branch else "main"])
        for direction, order in enumerate((seq, list(reversed(seq)))):
            trip = f"{key}-{direction}"
            tables["trips.txt"].append([line, "DAILY", trip, stations[order[-1]]["name"], str(direction)])
            t = 0.0
            for i, code in enumerate(order):
                if i:
                    t += hop_seconds(line, stations[order[i - 1]], stations[code])
                tables["stop_times.txt"].append([trip, hhmmss(t), hhmmss(t), f"MTR_{code}", str(i + 1)])
            tables["frequencies.txt"].append([trip, *SERVICE_HOURS, str(headway), "0"])
    return tables


def main() -> None:
    tables = build(json.loads(MTR.read_text()), date.today())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name, rows in tables.items():
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\n").writerows(rows)
            z.writestr(name, buf.getvalue())
    trips = len(tables["trips.txt"]) - 1
    print(f"wrote {OUT} ({len(tables['stops.txt']) - 1} stations, {trips} trip patterns)")


if __name__ == "__main__":
    main()
