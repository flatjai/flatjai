"""M0 acceptance check: the active model profile answers a typed call with a valid Profile."""
import asyncio
import sys

from .agent.understand import parse_brief
from .config import active_profile
from .model_client import ModelClient

BRIEF = "Looking for my own room, max 9k a month, under 40 min to HKUST, moving in January. Quiet please."


async def main() -> int:
    profile = active_profile()
    print(f"profile={profile.name} model={profile.model} base_url={profile.base_url}")
    client = ModelClient(profile)
    try:
        result = await parse_brief(client, BRIEF)
    except Exception as e:  # noqa: BLE001 - print and fail for a CLI check
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1
    s = client.calls[-1]
    print(result.model_dump_json(indent=2))
    print(f"OK in {s.ms:.0f} ms, {s.tokens_in} in / {s.tokens_out} out tokens, {s.attempts} attempt(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
