"""Geocoder against a fake Address Lookup Service, and the commute check in the read stage."""

import httpx

from flatjai.agent.match import with_commute
from flatjai.agent.state import Check
from flatjai.schemas import Profile
from flatjai.tools.geocode import Geocoder


def als(entries):
    """A fake ALS: query text -> list of (building, estate, lat, lon, score)."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        calls.append(q)
        suggestions = [
            {
                "Address": {
                    "PremisesAddress": {
                        "EngPremisesAddress": {"BuildingName": b, "EngEstate": {"EstateName": e}},
                        "GeospatialInformation": {"Latitude": str(lat), "Longitude": str(lon)},
                    }
                },
                "ValidationInformation": {"Score": score},
            }
            for b, e, lat, lon, score in entries.get(q, [])
        ]
        return httpx.Response(200, json={"SuggestedAddress": suggestions})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def test_building_found_when_the_names_agree(store):
    http, _ = als(
        {"LUNG POON COURT Diamond Hill": [("LUNG SAN HOUSE", "LUNG POON COURT", 22.342, 114.201, 63)]}
    )
    place = await Geocoder(http, store).locate("LUNG POON COURT", "Diamond Hill")
    assert place.precision == "building" and place.lat == 22.342


async def test_wrong_match_falls_back_to_the_district(store):
    http, _ = als(
        {
            "Test Court Hang Hau": [("MTR HUNG HOM BUILDING", "MTR HUNG HOM STATION", 22.30, 114.18, 60)],
            "Hang Hau": [("HANG HAU VILLAGE", None, 22.315, 114.264, 70)],
        }
    )
    place = await Geocoder(http, store).locate("Test Court", "Hang Hau")
    assert place.precision == "area" and place.lat == 22.315  # never placed at Hung Hom


async def test_results_are_cached(store):
    http, calls = als({"LUNG POON COURT Diamond Hill": [("X", "LUNG POON COURT", 22.342, 114.201, 63)]})
    g = Geocoder(http, store)
    await g.locate("LUNG POON COURT", "Diamond Hill")
    await g.locate("LUNG POON COURT", "Diamond Hill")
    assert calls == ["Diamond Hill", "LUNG POON COURT Diamond Hill"]  # the second lookup is all cache


def test_commute_replaces_the_area_check():
    p = Profile(campus="HKUST", max_commute_min=40)
    checks = [Check(name="budget", ok=True, detail="ok"), Check(name="area", ok=False, detail="too far")]
    out = with_commute(checks, 32, "walk 6 min · MTR 14 min", p, "building")
    assert [c.name for c in out] == ["budget", "commute"]
    assert out[1].ok is True and out[1].value == 32 and "~32 min to HKUST" in out[1].detail
    assert with_commute(checks, 55, "...", p, "area")[1].ok is False


async def test_read_stage_adds_the_commute(store, monkeypatch):
    from conftest import DRAFT_JSON
    from test_loop import run

    from flatjai.agent import read
    from flatjai.tools.geocode import Place
    from flatjai.tools.transit import Commute, Leg

    class FakeGeocoder:
        async def building(self, name, district):
            return Place(lat=22.315, lon=114.264, matched=name or "", precision="building")

        async def area(self, district):
            return None

    monkeypatch.setattr(
        read,
        "commute",
        lambda home, key: Commute(minutes=18, legs=[Leg(mode="bus", text="minibus 11", minutes=18)]),
    )
    replies = {"Profile": {"budget_hkd_month": 15000, "campus": "HKUST", "max_commute_min": 30}}
    original_run = run

    async def run_with_geocoder():
        import test_loop

        orig = test_loop.Toolbox

        def toolbox(mc, s, f):
            return orig(mc, s, f, geocoder=FakeGeocoder())

        monkeypatch.setattr(test_loop, "Toolbox", toolbox)
        return await original_run(store, replies, brief="flat near HKUST, 15k, 30 min")

    events, state, _, _ = await run_with_geocoder()
    card = next(e.data for e in events if e.type == "card")
    commute_check = next(c for c in card["checks"] if c["name"] == "commute")
    assert commute_check["ok"] is True and commute_check["value"] == 18
    assert "area" not in [c["name"] for c in card["checks"]]
    assert DRAFT_JSON["district"] == "Hang Hau"


async def test_one_shared_word_is_not_a_match(store):
    http, _ = als(
        {
            "Sierra Sea Sai Sha": [("SIERRA TERRACE", "CASA SIERRA", 22.4887, 114.1393, 70)],  # Fanling
            "Sai Sha": [("SAI SHA ROAD", None, 22.42, 114.27, 70)],
        }
    )
    place = await Geocoder(http, store).locate("Sierra Sea", "Sai Sha")
    assert place.precision == "area" and place.lat == 22.42


async def test_a_road_is_not_a_building(store):
    http, calls = als(
        {
            "Choi Hung": [("CHOI HUNG ESTATE", None, 22.335, 114.207, 70)],
            "Clear Water Bay Road Choi Hung": [
                ("X", "CLEAR WATER BAY ROAD", 22.333, 114.258, 80)
            ],  # near HKUST
        }
    )
    place = await Geocoder(http, store).locate("Clear Water Bay Road", "Choi Hung")
    assert place.precision == "area" and place.lon == 114.207
    assert "Clear Water Bay Road Choi Hung" not in calls


async def test_building_far_from_its_district_is_not_trusted(store):
    http, _ = als(
        {
            "Hang Hau": [("HANG HAU VILLAGE", None, 22.315, 114.264, 70)],
            "Garden Vista Hang Hau": [
                ("GARDEN VISTA", "GARDEN VISTA", 22.38, 114.19, 80)
            ],  # Sha Tin, ~10 km off
        }
    )
    place = await Geocoder(http, store).locate("Garden Vista", "Hang Hau")
    assert place.precision == "area" and place.lat == 22.315


async def test_a_vague_district_places_nothing(store):
    http, calls = als({"Hong Kong": [("HONG KONG", None, 22.28, 114.16, 90)]})
    g = Geocoder(http, store)
    assert await g.area("Hong Kong") is None and await g.area("Kowloon") is None
    assert calls == []


async def test_station_named_in_the_title_places_a_home_when_the_building_is_unknown(monkeypatch):
    from flatjai.agent import read
    from flatjai.agent.context import Toolbox
    from flatjai.schemas import Listing, Profile
    from flatjai.tools.transit import Commute, network

    class NoBuilding:
        async def building(self, name, district):
            return None

        async def area(self, district):
            return None

    seen = {}

    def fake_commute(home, key):
        seen["home"] = home
        return Commute(minutes=17, legs=[])

    monkeypatch.setattr(read, "commute", fake_commute)
    ctx = type("Ctx", (), {"tools": Toolbox(None, None, None, geocoder=NoBuilding())})()
    listing = Listing(
        source_url="https://en.uhomes.com/hk/hongkong/detail-apartments-1",
        portal="uhomes",
        title="Hang Hau Metro City",
        rent_hkd_month=7700,
        district="Hong Kong",
    )
    journey, precision = await read._commute(ctx, listing, Profile(campus="HKUST"))
    hah = network().stations["HAH"]
    assert seen["home"] == (hah["lat"], hah["lon"]) and precision == "area"


def test_worldwide_list_page_links_keep_hong_kong_only():
    import asyncio

    from flatjai.tools.search import expand_list

    class ListPage:
        links = [
            "https://amberstudent.com/places/dwell-ho-man-tin-hong-kong-2605287178625",
            "https://amberstudent.com/places/the-rook-orlando-2608063813595",
        ]
        link_text = {links[0]: "Dwell Ho Man Tin, Hong Kong Kowloon, HK", links[1]: "The Rook, Orlando, FL"}

    class Fetcher:
        async def fetch(self, url):
            return ListPage()

    found = asyncio.run(
        expand_list(Fetcher(), "https://amberstudent.com/places/search/hong-kong-china-2602036575849")
    )
    assert [r.url for r in found] == [ListPage.links[0]]
