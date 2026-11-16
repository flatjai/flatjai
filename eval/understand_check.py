"""Understand-stage check against the active model: each brief must parse to the expected fields.

The seed of the M4 query suite. Run: make eval-understand
"""

import asyncio
import sys
import time

from flatjai.agent.understand import parse_brief
from flatjai.config import active_profile
from flatjai.model_client import ModelClient

CASES: dict[str, dict] = {
    "2-bedroom flat to share with a friend, 30k budget total, under 40 min to HKUST, move in February": dict(
        budget_hkd_month=30000, budget_is_total=True, campus="HKUST", max_commute_min=40, bedrooms=2,
        flatmates=1, room_only=False,
    ),
    "Own room, max HK$9,000 a month, under 40 min to HKUST, from January, quiet": dict(
        budget_hkd_month=9000, campus="HKUST", max_commute_min=40, room_only=True, budget_is_total=False
    ),
    "Studio near HKU, up to 15k, 30 minutes to campus, from 1 March": dict(
        budget_hkd_month=15000, campus="HKU", max_commute_min=30
    ),
    "想搵科大附近嘅單人房，每月八千以內，一月入住": dict(budget_hkd_month=8000, campus="HKUST", room_only=True),
    "cheap room please": dict(budget_hkd_month=None, campus=None, max_commute_min=None, room_only=True),
    "2-bedroom flat to share with a friend near campus, move in February": dict(
        budget_hkd_month=None, campus=None, bedrooms=2, flatmates=1, room_only=False
    ),
}


async def main() -> int:
    client = ModelClient(active_profile())
    print(f"model: {client.profile.model}")
    passed = 0
    for brief, want in CASES.items():
        start = time.perf_counter()
        got = (await parse_brief(client, brief)).model_dump()
        wrong = {k: {"got": got[k], "want": v} for k, v in want.items() if got[k] != v}
        passed += not wrong
        print(f"{time.perf_counter() - start:5.1f}s {'OK ' if not wrong else 'BAD'} {brief[:50]!r} {wrong or ''}")
    print(f"{passed}/{len(CASES)} briefs parsed correctly")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
