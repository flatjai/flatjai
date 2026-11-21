"""Transit router: a home -> campus journey from a local OpenTripPlanner (free, no API key).

OTP routes over OpenStreetMap streets, the Transport Department's GTFS (buses, minibuses, trams,
ferries) and an MTR feed FlatJai builds from MTR Open Data (scripts/build_mtr_gtfs.py). It returns real
legs (walk to the stop, bus 91B, MTR, walk to campus) with each leg's path for the map. Journeys are
for a weekday 08:30 departure, the fastest of a few, and cached (a home and a campus do not move).
When OTP is not running or finds no route, the caller falls back to the offline estimate
(tools/transit.py), so FlatJai never depends on it.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from ..storage.store import Store
from ..tracing import span
from .transit import CAMPUSES, Commute, Leg, Place

HKT = timezone(timedelta(hours=8))
MAX_PATH_POINTS = 40  # per leg: enough to draw it, small enough to keep in every card event
QUERY = """
query($o: PlanLabeledLocationInput!, $d: PlanLabeledLocationInput!, $t: OffsetDateTime!) {
  planConnection(origin: $o, destination: $d, dateTime: {earliestDeparture: $t}, first: 3) {
    edges { node { duration legs {
      mode duration
      from { name lat lon } to { name lat lon }
      route { shortName longName color agency { gtfsId } }
      legGeometry { points }
    } } }
  }
}"""


@dataclass(frozen=True)
class Shuttle:
    """A free campus bus the GTFS does not carry: OTP alone walks students up the hill."""

    stop: str
    lat: float
    lon: float
    minutes: float  # ride and wait, as in the offline estimate (transit.CAMPUSES egress)
    text: str


# CUHK's campus buses leave from University station; without them OTP walked 18 min from the
# station, so a bus stopping nearer tied with East Rail from Sha Tin (both 32 min, seen 2026-11-21).
SHUTTLES = {"CUHK": Shuttle("University station", 22.4134, 114.2102, 8, "campus bus from University station")}

MODES = {"WALK": "walk", "BUS": "bus", "SUBWAY": "mtr", "RAIL": "mtr", "TRAM": "tram", "FERRY": "ferry"}


class TransitRouter:
    def __init__(self, http: httpx.AsyncClient, base_url: str, store: Store | None = None) -> None:
        self.http, self.url, self.store = http, base_url.rstrip("/") + "/otp/gtfs/v1", store

    async def journey(self, home: tuple[float, float], campus: str) -> Commute | None:
        target = CAMPUSES.get(campus)
        if target is None:
            return None
        key = f"{campus}|{home[0]:.4f},{home[1]:.4f}" + ("|shuttle" if campus in SHUTTLES else "")
        if self.store is not None and (row := await self.store.cache_get("otp", key)) is not None:
            async with span("route", "tool", campus=campus, cache="hit"):
                return Commute.model_validate(row.value) if row.value else None
        async with span("route", "tool", campus=campus, home=list(home)) as sp:
            journey = await self._best(home, campus)
            sp.attrs["minutes"] = journey.minutes if journey else None
        if self.store is not None and journey is not None:  # a failure is not cached: OTP may be back later
            await self.store.cache_put("otp", key, journey.model_dump())
        return journey

    async def _best(self, home: tuple[float, float], campus: str) -> Commute | None:
        """Straight to campus, or (where there is one) to the campus bus and on by it: the faster,
        and on a tie the one with a train (more frequent and on time than a road bus)."""
        target, shuttle = CAMPUSES[campus], SHUTTLES.get(campus)
        if shuttle is None:
            return await self._ask(home, target, target.name)
        direct, via = await asyncio.gather(
            self._ask(home, target, target.name),
            self._ask(home, target, target.name, shuttle=shuttle),
        )
        options = [j for j in (direct, via) if j is not None]
        return min(
            options, key=lambda j: (j.minutes, not any(leg.mode == "mtr" for leg in j.legs)), default=None
        )

    async def _ask(
        self, home: tuple[float, float], campus, campus_name: str, shuttle: Shuttle | None = None
    ) -> Commute | None:
        point = lambda lat, lon: {"location": {"coordinate": {"latitude": lat, "longitude": lon}}}  # noqa: E731
        dest = point(shuttle.lat, shuttle.lon) if shuttle else point(campus.lat, campus.lon)
        variables = {"o": point(*home), "d": dest, "t": morning().isoformat()}
        try:
            resp = await self.http.post(self.url, json={"query": QUERY, "variables": variables}, timeout=20.0)
            resp.raise_for_status()
            edges = resp.json()["data"]["planConnection"]["edges"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
        if not edges:
            return None
        rail = lambda n: not any(leg["mode"] in ("SUBWAY", "RAIL") for leg in n["legs"])  # noqa: E731
        best = min((e["node"] for e in edges), key=lambda n: (round(n["duration"] / 60), rail(n)))
        return to_commute(best, home, campus_name, shuttle)


def morning(today: date | None = None) -> datetime:
    """The next Tuesday, 08:30 in Hong Kong: a normal term-time morning, never a holiday timetable."""
    today = today or date.today()
    day = today + timedelta(days=(1 - today.weekday()) % 7 or 7)
    return datetime(day.year, day.month, day.day, 8, 30, tzinfo=HKT)


def to_commute(
    itinerary: dict, home: tuple[float, float], campus_name: str, shuttle: Shuttle | None = None
) -> Commute:
    legs: list[Leg] = []
    route = [Place(name="Home", kind="home", lat=home[0], lon=home[1])]
    raw = itinerary["legs"]
    for i, leg in enumerate(raw):
        mode = MODES.get(leg["mode"], "bus")
        line = leg.get("route") or {}
        agency = ((line.get("agency") or {}).get("gtfsId") or "").split(":")[-1]
        if mode == "bus" and agency == "GMB":
            mode = "minibus"
        final = i == len(raw) - 1 and (shuttle is None or mode == "walk")  # a train ends at its station
        to = ("the campus bus" if shuttle else "campus") if final else _stop_name(leg["to"]["name"])
        name = line.get("shortName") or line.get("longName") or ""
        if mode == "walk":
            text = f"walk to {to}"
        elif mode == "mtr":
            text = f"MTR {name} to {to}"
        else:
            text = f"{mode} {name} to {to}".replace("  ", " ")
        path = decode_polyline((leg.get("legGeometry") or {}).get("points") or "")
        legs.append(
            Leg(mode=mode, text=text, minutes=leg["duration"] / 60, path=_thin(path), color=line.get("color"))
        )
        if mode != "walk":
            for end, kind in ((leg["from"], "board"), (leg["to"], "alight")):
                route.append(Place(name=_stop_name(end["name"]), kind=kind, lat=end["lat"], lon=end["lon"]))
    campus = CAMPUSES_BY_NAME[campus_name]
    minutes = itinerary["duration"] / 60
    if shuttle:
        hub, end = (shuttle.lat, shuttle.lon), (campus.lat, campus.lon)
        legs.append(Leg(mode="bus", text=shuttle.text, minutes=shuttle.minutes, path=[hub, end]))
        route.append(Place(name=shuttle.stop, kind="board", lat=shuttle.lat, lon=shuttle.lon))
        minutes += shuttle.minutes
    route.append(Place(name=campus_name, kind="campus", lat=campus.lat, lon=campus.lon))
    return Commute(minutes=round(minutes), legs=legs, method="otp", route=route)


CAMPUSES_BY_NAME = {c.name: c for c in CAMPUSES.values()}


_CAMPUS_STOP = re.compile(r"h\.?k\.?u\.?s\.?t\.?|hong kong university of science (?:and|&) technology", re.I)
_SMALL = {"Of", "And", "The", "To", "At", "Near", "Outside", "Opposite"}


def _stop_name(name: str) -> str:
    """GTFS stop names as a student reads them: the first of several names joined with "|", no
    operator tag ("[KMB] "), no markup ("/<Br>"), HKUST by its short name, Title Case for ALL CAPS."""
    name = name.split("|")[0]
    name = re.sub(r"/?<br\s*/?>.*$", "", name, flags=re.I)
    name = re.sub(r"^\[[^\]]+\]\s*", "", name).strip()
    if name.isupper():
        words = [w.title() if not re.search(r"\.", w) else w for w in name.split()]
        name = " ".join(w if i == 0 or w not in _SMALL else w.lower() for i, w in enumerate(words))
    return _CAMPUS_STOP.sub("HKUST", name)


def _thin(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= MAX_PATH_POINTS:
        return points
    step = (len(points) - 1) / (MAX_PATH_POINTS - 1)
    return [points[round(i * step)] for i in range(MAX_PATH_POINTS)]


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Google's encoded polyline (what OTP returns) -> [(lat, lon)]."""
    points, index, lat, lon = [], 0, 0, 0
    while index < len(encoded):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lon += delta
        points.append((round(lat / 1e5, 5), round(lon / 1e5, 5)))
    return points
