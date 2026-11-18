"""Transit router against a recorded OpenTripPlanner reply (Hang Hau station -> HKUST, a weekday 08:30)."""

import json
from pathlib import Path

import httpx

from flatjai.tools.otp import TransitRouter, decode_polyline

REPLY = json.loads((Path(__file__).parent / "fixtures_otp_hang_hau.json").read_text())
HOME = (22.3155, 114.2643)


def router(reply=REPLY, status=200, store=None):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(status, json=reply)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TransitRouter(http, "http://otp:8080", store=store), calls


async def test_fastest_transit_journey_with_real_legs():
    r, calls = router()
    journey = await r.journey(HOME, "HKUST")
    assert journey is not None and journey.method == "otp"
    assert journey.minutes == 18  # KMB 91B, not the 52 min walk
    modes = [leg.mode for leg in journey.legs]
    assert modes == ["walk", "bus", "walk"]
    bus = journey.legs[1]
    assert bus.text == "bus 91B to HKUST (Shaw Auditorium)"
    assert len(bus.path) >= 2 and all(22.2 < lat < 22.6 for lat, _ in bus.path)
    # the map's stops: home, where each ride starts and ends, campus
    assert [p.kind for p in journey.route][0] == "home" and journey.route[-1].kind == "campus"
    assert calls[0]["variables"]["d"]["location"]["coordinate"]["latitude"] == 22.3364  # HKUST


async def test_no_journey_when_otp_is_down_or_has_no_route():
    r, _ = router(status=503)
    assert await r.journey(HOME, "HKUST") is None
    r, _ = router(reply={"data": {"planConnection": {"edges": []}}})
    assert await r.journey(HOME, "HKUST") is None
    r, calls = router()
    assert await r.journey(HOME, "Nowhere U") is None and not calls  # unknown campus: not asked


async def test_journeys_are_cached(store):
    r, calls = router(store=store)
    first = await r.journey(HOME, "HKUST")
    again = await r.journey((22.31551, 114.26431), "HKUST")  # the same spot, to ~10 m
    assert again == first and len(calls) == 1


def test_decode_polyline():
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2),
        (40.7, -120.95),
        (43.252, -126.453),
    ]


def test_stop_names_read_cleanly():
    from flatjai.tools.otp import _stop_name

    raw = "Fok On Garden, Sai Sha Road|[Kmb+Ctb] Fok On Garden/<Br>Fok On Garden, Sai Sha Road|[Kmb] Fok On Garden"
    assert _stop_name(raw) == "Fok On Garden, Sai Sha Road"
    assert _stop_name("[KMB] H.K.U.S.T. (SHAW AUDITORIUM)") == "HKUST (Shaw Auditorium)"
    assert (
        _stop_name("HONG KONG UNIVERSITY OF SCIENCE AND TECHNOLOGY (SOUTH STATION)")
        == "HKUST (South Station)"
    )
    assert (
        _stop_name("HANG HAU STATION PUBLIC TRANSPORT INTERCHANGE")
        == "Hang Hau Station Public Transport Interchange"
    )
