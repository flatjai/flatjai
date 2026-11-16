"""Commute estimate: home -> campus by MTR (or a direct bus), computed offline from open data.

The design's router is OpenTripPlanner on Transport Department GTFS; its fallback, used here until
that is set up, is this model:

  access   walk to one of the 3 nearest MTR stations (street factor 1.3, 80 m/min), or a feeder
           bus or minibus when the nearest is over 1.2 km away (6 min wait, 300 m/min)
  MTR      shortest route over the official line sequences: each hop at ~33 km/h on urban lines
           (~50 km/h on Tuen Ma, East Rail, Tung Chung) plus a 30 s stop, 3 min initial wait,
           4 min per line change
  egress   station -> campus from CAMPUSES (estimates, listed below)
  direct   for a home within 8 km of campus, a bus or minibus straight there (8 min wait, 300 m/min)

The faster of MTR and direct wins. Every figure is an estimate and is shown as "~N min"; the
evaluation's commute-error metric checks the model against real journeys.
Station data: data/mtr.json, built by scripts/build_mtr.py.
"""

import heapq
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DATA = Path(__file__).resolve().parents[1] / "data" / "mtr.json"

WALK_M_PER_MIN = 80
STREET_FACTOR = 1.3
MAX_WALK_M = 1200
FEEDER_WAIT_MIN = 6
BUS_M_PER_MIN = 300  # ~18 km/h including stops
TRAIN_M_PER_MIN = 550  # ~33 km/h on urban lines, stops included in DWELL_MIN
# suburban lines with stations far apart run much faster between stops (calibrated on Tuen Mun and
# Sha Tin journeys: one urban speed made Tuen Mun -> Choi Hung take 94 min)
FAST_LINES_M_PER_MIN = {"TML": 830, "EAL": 830, "TCL": 830, "AEL": 1300}  # ~50 km/h; Airport Express ~78
TRACK_FACTOR = 1.15
DWELL_MIN = 0.5
TRAIN_WAIT_MIN = 3
TRANSFER_MIN = 4
DIRECT_MAX_M = 8000
DIRECT_WAIT_MIN = 8


@dataclass(frozen=True)
class Campus:
    name: str
    lat: float
    lon: float
    # station code -> (minutes from the station to campus, how)
    egress: dict[str, tuple[float, str]]


# Campus access estimates (minutes include waiting). Coordinates: campus centres, checked against
# Address Lookup Service results for each university on 2026-11-16 (all within about 0.5 km).
CAMPUSES: dict[str, Campus] = {
    "HKUST": Campus(
        "HKUST",
        22.3364,
        114.2654,
        {
            "HAH": (15, "minibus 11 from Hang Hau"),
            "CHH": (25, "bus 91 or 91M from Choi Hung"),
            "DIH": (30, "bus 91M from Diamond Hill"),
        },
    ),
    "HKU": Campus("HKU", 22.2830, 114.1371, {"HKU": (5, "walk from HKU station")}),
    "CUHK": Campus("CUHK", 22.4196, 114.2068, {"UNI": (8, "campus bus from University station")}),
    "CITYU": Campus("CityU", 22.3363, 114.1730, {"KOT": (6, "walk from Kowloon Tong")}),
    "HKBU": Campus("HKBU", 22.3387, 114.1820, {"KOT": (12, "walk from Kowloon Tong")}),
    "POLYU": Campus("PolyU", 22.3043, 114.1795, {"HUH": (8, "walk from Hung Hom")}),
}


class Leg(BaseModel):
    mode: str  # walk | bus | mtr
    text: str
    minutes: float


class Commute(BaseModel):
    minutes: int
    legs: list[Leg]
    method: str = "estimate"

    def summary(self) -> str:
        return " · ".join(f"{leg.text} {round(leg.minutes)} min" for leg in self.legs)


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


@dataclass
class Network:
    stations: dict[str, dict]
    edges: dict[tuple[str, str], list[tuple[tuple[str, str], float]]]  # (station, line) -> [(node, min)]
    lines_at: dict[str, set[str]]


@lru_cache
def network() -> Network:
    return build_network(json.loads(DATA.read_text()))


def build_network(data: dict) -> Network:
    stations = data["stations"]
    edges: dict[tuple[str, str], list[tuple[tuple[str, str], float]]] = {}
    lines_at: dict[str, set[str]] = {}
    for key, seq in data["lines"].items():
        line = key.split("-")[0]
        for a, b in zip(seq, seq[1:], strict=False):
            pa, pb = (stations[a]["lat"], stations[a]["lon"]), (stations[b]["lat"], stations[b]["lon"])
            speed = FAST_LINES_M_PER_MIN.get(line, TRAIN_M_PER_MIN)
            t = distance_m(pa, pb) * TRACK_FACTOR / speed + DWELL_MIN
            edges.setdefault((a, line), []).append(((b, line), t))
            edges.setdefault((b, line), []).append(((a, line), t))
        for s in seq:
            lines_at.setdefault(s, set()).add(line)
    for s, lines in lines_at.items():  # changing lines at a station
        for la in lines:
            for lb in lines - {la}:
                edges.setdefault((s, la), []).append(((s, lb), TRANSFER_MIN))
    return Network(stations, edges, lines_at)


def ride_minutes(net: Network, origin: str, targets: set[str]) -> dict[str, float]:
    """Shortest MTR time from `origin` to each target station (Dijkstra over station-line nodes)."""
    dist: dict[tuple[str, str], float] = {}
    heap = [(0.0, (origin, line)) for line in net.lines_at.get(origin, ())]
    best: dict[str, float] = {}
    while heap:
        d, node = heapq.heappop(heap)
        if node in dist:
            continue
        dist[node] = d
        if node[0] in targets and node[0] not in best:
            best[node[0]] = d
            if len(best) == len(targets):
                break
        for nxt, w in net.edges.get(node, ()):
            if nxt not in dist:
                heapq.heappush(heap, (d + w, nxt))
    return best


def access(net: Network, home: tuple[float, float], code: str) -> Leg:
    st = net.stations[code]
    metres = distance_m(home, (st["lat"], st["lon"])) * STREET_FACTOR
    if metres <= MAX_WALK_M:
        return Leg(mode="walk", text=f"walk to {st['name']}", minutes=metres / WALK_M_PER_MIN)
    return Leg(
        mode="bus", text=f"bus or minibus to {st['name']}", minutes=FEEDER_WAIT_MIN + metres / BUS_M_PER_MIN
    )


def commute(
    home: tuple[float, float],
    campus_key: str,
    net: Network | None = None,
    campuses: dict[str, Campus] | None = None,
) -> Commute | None:
    campus = (campuses or CAMPUSES).get(campus_key)
    if campus is None:
        return None
    net = net or network()
    nearest = sorted(
        net.stations, key=lambda c: distance_m(home, (net.stations[c]["lat"], net.stations[c]["lon"]))
    )[:3]
    options: list[Commute] = []
    for code in nearest:
        to_station = access(net, home, code)
        rides = ride_minutes(net, code, set(campus.egress))
        for target, ride in rides.items():
            egress_min, how = campus.egress[target]
            legs = [to_station]
            if target != code:
                legs.append(
                    Leg(
                        mode="mtr",
                        text=f"MTR to {net.stations[target]['name']}",
                        minutes=TRAIN_WAIT_MIN + ride,
                    )
                )
            legs.append(Leg(mode="bus" if "bus" in how else "walk", text=how, minutes=egress_min))
            options.append(Commute(minutes=round(sum(leg.minutes for leg in legs)), legs=legs))
    direct_m = distance_m(home, (campus.lat, campus.lon)) * STREET_FACTOR
    if direct_m <= DIRECT_MAX_M:
        if direct_m <= MAX_WALK_M:
            leg = Leg(mode="walk", text=f"walk to {campus.name}", minutes=direct_m / WALK_M_PER_MIN)
        else:
            leg = Leg(
                mode="bus",
                text=f"bus or minibus to {campus.name}",
                minutes=DIRECT_WAIT_MIN + direct_m / BUS_M_PER_MIN,
            )
        options.append(Commute(minutes=round(leg.minutes), legs=[leg]))
    return min(options, key=lambda c: c.minutes) if options else None
