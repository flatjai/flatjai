"""Stage 1, Understand: brief -> Profile, and whether to ask the student a question first.

In a session, a later message (an answer to our question, or a refinement) is read together with
the profile so far; fields the new message does not mention keep their earlier values.
Asking is the model's decision, gated in code: only when a hard constraint is missing, and never
twice about the same constraint in one session.
"""

import re
from datetime import date

from pydantic import BaseModel, Field

from ..model_client import ModelClient
from ..schemas import Profile

SYSTEM = """You are FlatJai, a home-search assistant for students in Hong Kong.
Read the student's brief (English, Chinese or both) and fill every Profile field the brief states or clearly implies.
Use null (never 0 or "") for a field the brief says nothing about, and an empty list for lists. Do not guess.

How to read common phrases:
- "9k", "$9,000", "九千" -> budget_hkd_month 9000 (HK$ per month).
- "under 40 min to HKUST", "within 40 minutes of campus" -> campus "HKUST", max_commute_min 40.
- "own room", "a room", "share a flat" -> room_only true. "a 2-bedroom flat", "whole flat" -> room_only false.
- "studio" -> a whole small flat: room_only false, bedrooms 0.
- "with a friend", "with my partner" -> flatmates 1 (people sharing besides the student).
- "from January", "moving in Jan" -> move_in = the next 1 January after today.
- "quiet", "near MTR", "with a gym", "pet friendly" -> soft_preferences.
- Vague words are not numbers: "cheap", "affordable", "near campus" give NO budget and NO campus.
- Read every limit in the brief, even in a long sentence: "..., under 40 min to HKUST, ..." -> max_commute_min 40.

Example 1. Brief: "Need my own room near Hang Hau, 8k max, 30 min to HKUST, start March, no smokers"
{"budget_hkd_month": 8000, "campus": "HKUST", "max_commute_min": 30, "districts": ["Hang Hau"],
 "room_only": true, "move_in": "<next 1 March>", "soft_preferences": ["non-smoking flatmates"]}

Example 2. Brief: "2-bedroom flat to share with a friend, 20k total, near CUHK, gym would be nice"
{"budget_hkd_month": 20000, "budget_is_total": true, "campus": "CUHK", "room_only": false, "bedrooms": 2,
 "flatmates": 1, "soft_preferences": ["gym"]}

When a "Profile so far" is given, the new message adds to or changes it: return the complete updated profile.
Reply with the JSON object only."""


async def parse_brief(
    client: ModelClient, brief: str, today: date | None = None, previous: Profile | None = None
) -> Profile:
    today = today or date.today()
    context = f"Profile so far:\n{previous.model_dump_json()}\n\nNew message:\n" if previous else "Brief:\n"
    parsed = await client.typed_call(
        "parse_brief", SYSTEM, f"Today is {today.isoformat()}.\n\n{context}{brief}", Profile
    )
    parsed = ground_profile(parsed, brief)
    return merge(previous, parsed) if previous else parsed


# Numbers the student actually wrote: "9k", "$9,000", "9000", "1.5萬", "八千", "一萬"
_ARABIC = re.compile(r"(\d+(?:[.,]\d+)*)\s*(k|K|千|萬|万)?")
_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "兩": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_CN = re.compile(r"([一二兩两三四五六七八九十])\s*(千|萬|万)")
_SCALE = {"k": 1000, "K": 1000, "千": 1000, "萬": 10000, "万": 10000}
_TOTAL = re.compile(r"\btotal\b|in total|altogether|總共|一共|合共", re.I)
_MINUTES = re.compile(r"(\d+)\s*(?:min|mins|minutes|分鐘|分钟)", re.I)


def numbers_in(text: str) -> set[int]:
    found: set[int] = set()
    for raw, scale in _ARABIC.findall(text):
        value = float(raw.replace(",", "")) if raw.count(".") <= 1 else 0
        found.add(round(value * _SCALE.get(scale, 1)))
    for digit, scale in _CN.findall(text):
        found.add(_CN_DIGITS[digit] * _SCALE[scale])
    return found


def ground_profile(profile: Profile, text: str) -> Profile:
    """No figure from the model's head: a budget must be a number the student wrote, and a commute
    limit the student wrote ("40 min") is never lost."""
    update: dict = {}
    minutes = {int(m) for m in _MINUTES.findall(text)}
    money = {n for n in numbers_in(text) if n >= 1000} - minutes
    if profile.budget_hkd_month is not None and profile.budget_hkd_month not in money:
        update["budget_hkd_month"] = None
    if profile.budget_hkd_month is None and len(money) == 1:  # the model dropped a stated budget
        update["budget_hkd_month"] = money.pop()
        if _TOTAL.search(text):
            update["budget_is_total"] = True
    if profile.campus is None and len(named := campuses_named(text)) == 1:
        update["campus"] = named.pop()  # the model dropped a campus the student wrote
    if _STUDIO.search(text) and not _ROOM.search(text):
        # a studio is a whole small flat with no separate bedroom, not a room in a shared flat
        update |= {"room_only": False, "bedrooms": 0}
    if profile.max_commute_min is None and len(minutes) == 1:
        update["max_commute_min"] = minutes.pop()
    elif profile.max_commute_min is not None and minutes and profile.max_commute_min not in minutes:
        update["max_commute_min"] = None
    return profile.model_copy(update=update) if update else profile


# Campus names as students write them; the Chinese University is matched before "University of Hong Kong"
_CAMPUS_NAMES = {
    "HKUST": r"\bhkust\b|\bust\b|science\s*(?:and|&)\s*technology|科大|科技大學",
    "CUHK": r"\bcuhk\b|chinese university|中大|中文大學",
    "HKU": r"\bhku\b|(?<!chinese )university of hong kong(?!\s*of)|港大|香港大學",
    "CityU": r"\bcityu\b|city university|城大",
    "HKBU": r"\bhkbu\b|baptist university|浸大",
    "PolyU": r"\bpolyu\b|polytechnic|理大",
}


def campuses_named(text: str) -> set[str]:
    return {name for name, pattern in _CAMPUS_NAMES.items() if re.search(pattern, text, re.I)}


_STUDIO = re.compile(r"\bstudios?\b|開放式|套房", re.I)
_ROOM = re.compile(r"\b(?:own|a|private|single|shared)\s+room\b|房間", re.I)
_PLACEHOLDER = re.compile(r"^\s*(?:none|n/?a|other|others|not sure|any|-)\s*\.?$", re.I)


def tidy_suggestions(suggestions: list[str]) -> list[str]:
    """Answers a student can tap: no placeholders ("None" offered as a campus, seen live), no repeats."""
    seen: list[str] = []
    for s in suggestions:
        if s.strip() and not _PLACEHOLDER.match(s) and s.strip() not in seen:
            seen.append(s.strip())
    return seen


def merge(previous: Profile, new: Profile) -> Profile:
    """New values win; anything the new message left empty keeps its earlier value."""
    kept = {k: v for k, v in new.model_dump().items() if v not in (None, [])}
    return previous.model_copy(update=kept)


class ClarifyDecision(BaseModel):
    ask: bool = Field(description="true if the search would likely go wrong without this information")
    question: str = Field("", description="One short, friendly question covering the missing information")
    suggestions: list[str] = Field(
        default_factory=list, max_length=4, description="2-4 short example answers the student can tap"
    )


CLARIFY_SYSTEM = """You are FlatJai, a home-search assistant for students in Hong Kong.
Some hard constraints are missing from the student's brief. Decide whether to ask before searching.
Ask when the search would likely show useless homes without it (no budget, or no idea where they study).
Do not ask when a sensible search is still possible (e.g. only the move-in date is missing).
If you ask, ask ONE short question that covers everything missing (e.g. budget AND campus together),
with 2-4 tap-able example answers that each answer all of it (e.g. "HKUST, HK$10,000 a month").
Reply with JSON only."""


async def decide_clarify(
    client: ModelClient, brief: str, profile: Profile, missing: list[str], today: date | None = None
) -> ClarifyDecision:
    today = today or date.today()
    user = (
        f"Today is {today.isoformat()}.\nBrief: {brief}\nUnderstood so far: {profile.model_dump_json()}\n"
        f"Missing: {', '.join(missing)}"
    )
    return await client.typed_call("decide_clarify", CLARIFY_SYSTEM, user, ClarifyDecision)
