"""Stage 1, Understand: brief -> Profile (a typed model call)."""
from datetime import date

from ..model_client import ModelClient
from ..schemas import Profile

SYSTEM = """You are FlatJai, a home-search assistant for students in Hong Kong.
Read the student's brief and fill the Profile JSON. Rules:
- Only record what the brief states or clearly implies; leave other fields null or empty.
- Rent is HK$ per month. "9k" means 9000.
- "near campus" with no campus named: leave campus null and add "campus" to missing.
- Put budget, campus and move_in into `missing` when they are not given.
Reply with JSON only."""


async def parse_brief(client: ModelClient, brief: str, today: date | None = None) -> Profile:
    today = today or date.today()
    user = f"Today is {today.isoformat()}.\n\nBrief:\n{brief}"
    return await client.typed_call("parse_brief", SYSTEM, user, Profile)
