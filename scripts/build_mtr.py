"""Build src/flatjai/data/mtr.json: MTR stations with coordinates, and each line's station order.

Sources (open data, fetched once; the app never calls them at run time):
- lines and station order: MTR Open Data, https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv
- coordinates: English Wikipedia page summaries ("<Name> station"), checked to lie inside Hong Kong
  and to describe a Hong Kong (MTR) station; the build fails rather than guess.

Run: cd backend && uv run python scripts/build_mtr.py
"""

import csv
import io
import json
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

import httpx

CSV_URL = "https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv"
WIKI = "https://en.wikipedia.org/api/rest_v1/page/summary/"
UA = {"User-Agent": "FlatJai/0.1 (HKUST student course project; one-off MTR station list build)"}
OUT = Path(__file__).resolve().parents[1] / "src/flatjai/data/mtr.json"
PARTIAL = OUT.with_suffix(".partial.json")  # resume file, deleted when the build completes
HK_BOX = (22.15, 22.58, 113.82, 114.45)  # lat min/max, lon min/max
TITLE_FIXES = {"HKU": ["HKU station"], "LOHAS Park": ["LOHAS Park station"], "AsiaWorld-Expo": ["AsiaWorld–Expo station"]}


def polite_get(client: httpx.Client, url: str) -> httpx.Response:
    """GET with backoff on HTTP 429, honouring Retry-After."""
    wait = 5.0
    for _ in range(8):
        r = client.get(url, headers=UA, follow_redirects=True)
        if r.status_code != 429:
            time.sleep(1.0)
            return r
        pause = float(r.headers.get("retry-after") or wait)
        print(f"  rate limited, waiting {pause:.0f} s")
        time.sleep(pause)
        wait = min(wait * 2, 120)
    raise SystemExit("still rate limited; run again later (progress is saved)")


def station_coords(client: httpx.Client, name: str) -> tuple[float, float]:
    for title in [*TITLE_FIXES.get(name, []), f"{name} station", f"{name} station (MTR)"]:
        r = polite_get(client, WIKI + quote(title.replace(" ", "_")))
        if r.status_code != 200:
            continue
        d = r.json()
        c, desc = d.get("coordinates"), (d.get("description") or "") + " " + (d.get("extract") or "")[:300]
        if c and HK_BOX[0] < c["lat"] < HK_BOX[1] and HK_BOX[2] < c["lon"] < HK_BOX[3] and ("MTR" in desc or "Hong Kong" in desc):
            return round(c["lat"], 5), round(c["lon"], 5)
    raise SystemExit(f"no verified coordinates for {name!r}; add a title to TITLE_FIXES")


def main() -> int:
    with httpx.Client(timeout=20) as client:
        rows = list(csv.DictReader(io.StringIO(client.get(CSV_URL, headers=UA).content.decode("utf-8-sig"))))
        rows = [r for r in rows if r["Station Code"]]
        names = {r["Station Code"]: r["English Name"] for r in rows}
        stations = json.loads(PARTIAL.read_text()) if PARTIAL.exists() else {}
        for code, name in sorted(names.items()):
            if code in stations:
                continue
            lat, lon = station_coords(client, name)
            stations[code] = {"name": name, "lat": lat, "lon": lon}
            PARTIAL.write_text(json.dumps(stations))
            print(f"{code} {name}: {lat}, {lon}")
    lines: dict[str, list[str]] = {}
    for r in sorted(rows, key=lambda r: (r["Line Code"], r["Direction"], float(r["Sequence"]))):
        if r["Direction"].endswith("UT"):
            continue  # each down-track sequence already gives every adjacent pair
        lines.setdefault(f'{r["Line Code"]}-{r["Direction"]}', []).append(r["Station Code"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "built": date.today().isoformat(),
        "sources": {"lines": CSV_URL, "coordinates": "en.wikipedia.org page summaries"},
        "stations": stations,
        "lines": lines,
    }, ensure_ascii=False, indent=1))
    PARTIAL.unlink(missing_ok=True)
    print(f"{len(stations)} stations, {len(lines)} line sequences -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
