"""Commute model on a small synthetic network: line A-B-C east-west, line X crossing at B."""

from flatjai.tools.transit import Campus, build_network, commute, distance_m

# about 1.1 km per 0.01 degree of longitude at this latitude
STATIONS = {
    "AAA": {"name": "Alpha", "lat": 22.30, "lon": 114.10},
    "BBB": {"name": "Bravo", "lat": 22.30, "lon": 114.13},
    "CCC": {"name": "Charlie", "lat": 22.30, "lon": 114.16},
    "XXX": {"name": "Xray", "lat": 22.33, "lon": 114.13},
}
NET = build_network(
    {"stations": STATIONS, "lines": {"EWL-DT": ["AAA", "BBB", "CCC"], "NSL-DT": ["XXX", "BBB"]}}
)
CAMPUS = {"UNI": Campus("Uni", 22.30, 114.20, {"CCC": (10, "minibus from Charlie")})}


def test_walk_ride_and_last_mile():
    c = commute((22.3005, 114.1005), "UNI", NET, CAMPUS)  # next to Alpha
    assert [leg.mode for leg in c.legs] == ["walk", "mtr", "bus"]
    assert c.legs[1].text == "MTR to Charlie"
    # ~6.2 km of track at 33 km/h + stops + 3 min wait, plus the 10 min minibus
    assert 20 <= c.minutes <= 30


def test_changing_lines_costs_time():
    straight = commute((22.3005, 114.1005), "UNI", NET, CAMPUS)
    via_change = commute((22.3305, 114.1305), "UNI", NET, CAMPUS)  # next to Xray: change at Bravo
    ride_x = via_change.legs[1].minutes
    assert ride_x > distance_m((22.33, 114.13), (22.30, 114.16)) / 550 + 4  # includes the 4 min change
    assert straight.minutes != via_change.minutes


def test_far_from_any_station_takes_a_feeder_bus():
    c = commute((22.36, 114.10), "UNI", NET, CAMPUS)  # several km from every station
    assert c.legs[0].mode == "bus"


def test_close_to_campus_goes_direct():
    c = commute((22.30, 114.195), "UNI", NET, CAMPUS)  # ~500 m from campus
    assert len(c.legs) == 1 and c.legs[0].mode == "walk" and c.minutes <= 10


def test_unknown_campus_has_no_estimate():
    assert commute((22.30, 114.10), "NOWHERE", NET, CAMPUS) is None
