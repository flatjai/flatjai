"""Geocode tool: listing -> coordinates, via the government Address Lookup Service (ALS, free).

A result is accepted only when every significant word of the listing's estate or title appears in what
ALS matched; otherwise the listing's district is located instead and marked precision="area".
Results are cached permanently: an estate does not move.
"""

import re

import httpx
from pydantic import BaseModel

from ..storage.store import Store
from ..tracing import span

ALS_URL = "https://www.als.gov.hk/lookup"
MIN_SCORE = 50.0
STOPWORDS = {
    "the",
    "tower",
    "block",
    "phase",
    "court",
    "house",
    "garden",
    "gardens",
    "estate",
    "building",
    "flat",
    "floor",
    "middle",
    "high",
    "low",
    "road",
    "street",
    "hong",
    "kong",
}


class Place(BaseModel):
    lat: float
    lon: float
    matched: str  # what ALS matched, for the trace
    precision: str  # building | area


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


class Geocoder:
    def __init__(self, http: httpx.AsyncClient, store: Store | None = None) -> None:
        self.http, self.store = http, store

    async def locate(self, name: str | None, district: str | None) -> Place | None:
        """Building first (name + district), then the district on its own."""
        if name:
            if place := await self._lookup(
                f"{name} {district or ''}".strip(), must_match=name, precision="building"
            ):
                return place
        if district:
            return await self._lookup(district, must_match=district, precision="area")
        return None

    async def _lookup(self, query: str, must_match: str, precision: str) -> Place | None:
        key = f"{precision}|{query.lower()}"
        if self.store is not None and (row := await self.store.cache_get("geocode", key)) is not None:
            async with span("geocode", "tool", query=query, cache="hit"):
                return Place.model_validate(row.value) if row.value else None
        async with span("geocode", "tool", query=query) as sp:
            place = await self._ask_als(query, must_match, precision)
            sp.attrs["result"] = place.model_dump() if place else None
        if self.store is not None:
            await self.store.cache_put("geocode", key, place.model_dump() if place else None)
        return place

    async def _ask_als(self, query: str, must_match: str, precision: str) -> Place | None:
        try:
            resp = await self.http.get(
                ALS_URL, params={"q": query, "n": 3}, headers={"Accept": "application/json"}, timeout=8.0
            )
            resp.raise_for_status()
            suggestions = resp.json().get("SuggestedAddress", [])
        except (httpx.HTTPError, ValueError):
            return None
        wanted = _words(must_match)
        for s in suggestions:
            if s.get("ValidationInformation", {}).get("Score", 0) < MIN_SCORE:
                continue
            premises = s["Address"]["PremisesAddress"]
            eng = premises.get("EngPremisesAddress", {})
            names = " ".join(
                filter(
                    None,
                    [
                        eng.get("BuildingName"),
                        (eng.get("EngEstate") or {}).get("EstateName"),
                        (eng.get("EngStreet") or {}).get("StreetName"),
                        (eng.get("EngDistrict") or {}).get("DcDistrict"),
                        (eng.get("EngVillage") or {}).get("VillageName"),
                    ],
                )
            )
            if wanted and not wanted <= _words(names):
                # every significant word must match: one shared word placed "Sierra Sea" (Sai Sha)
                # at "Casa Sierra" in Fanling
                continue
            geo = premises["GeospatialInformation"]
            return Place(
                lat=float(geo["Latitude"]), lon=float(geo["Longitude"]), matched=names, precision=precision
            )
        return None
