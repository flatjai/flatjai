"""Stage 2, Plan: Profile (+ what was already tried, + Reflect's advice) -> search queries.

The model chooses areas and wording (typed call plan_search). Code keeps it honest: queries already
tried are dropped, at most MAX_QUERIES per round, and if the call fails we fall back to the
deterministic plan (campus areas). CAMPUS_AREAS is a hint until M3 brings real commute isochrones.
"""

from pydantic import BaseModel, Field

from ..model_client import ModelClient
from ..schemas import Profile

# Residential areas a student commonly rents in for each campus (short commute by MTR, bus or minibus).
CAMPUS_AREAS: dict[str, list[str]] = {
    "HKUST": [
        "Hang Hau",
        "Tseung Kwan O",
        "Sai Kung",
        "Po Lam",
        "Tiu Keng Leng",
        "LOHAS Park",
        "Clear Water Bay",
        "Choi Hung",
        "Diamond Hill",
        "Ngau Tau Kok",
        "Kowloon Bay",
        "Kwun Tong",
        "Lam Tin",
        "Yau Tong",
    ],
    "HKU": ["Kennedy Town", "Sai Ying Pun", "Sheung Wan", "Shek Tong Tsui", "Mid-Levels"],
    "CUHK": ["Sha Tin", "Tai Po", "Fo Tan", "Ma On Shan", "Tai Wai"],
    "CITYU": ["Kowloon Tong", "Shek Kip Mei", "Sham Shui Po", "Mong Kok", "Prince Edward"],
    "HKBU": ["Kowloon Tong", "Kowloon City", "Mong Kok", "Lok Fu"],
    "POLYU": ["Hung Hom", "To Kwa Wan", "Tsim Sha Tsui", "Ho Man Tin", "Whampoa"],
}
MAX_QUERIES = 3


class PlannedQuery(BaseModel):
    area: str = Field(description="One area or estate to search in")
    text: str = Field(description="Search words, e.g. 'Hang Hau 2 bedroom flat for rent'")


class SearchPlan(BaseModel):
    queries: list[PlannedQuery] = Field(max_length=3, description="1 to 3 searches, most promising first")
    rationale: str = Field("", description="One sentence: why these areas")


SYSTEM = """You plan property searches in Hong Kong for a student.
Pick 1 to 3 areas where homes matching the profile are most likely, given budget and campus.
Cheaper areas are usually further from the city centre. Each search is one area, in English,
like "Tseung Kwan O 2 bedroom flat for rent" or "Sai Kung room for rent".
Never repeat a search that was already tried; follow the advice if given. Reply with JSON only."""


def campus_key(campus: str | None) -> str | None:
    if not campus:
        return None
    key = campus.upper().replace(" ", "").replace(".", "")
    return key if key in CAMPUS_AREAS else None


def candidate_areas(profile: Profile) -> list[str]:
    areas = list(profile.districts)
    if key := campus_key(profile.campus):
        areas += [a for a in CAMPUS_AREAS[key] if a not in areas]
    return areas


def _kind(profile: Profile) -> str:
    if profile.room_only:
        return "room"
    return f"{profile.bedrooms} bedroom flat" if profile.bedrooms else "flat"


def fallback_queries(profile: Profile, tried: list[str]) -> list[str]:
    texts = [f"{a} {_kind(profile)} for rent" for a in candidate_areas(profile)] or [
        f"{_kind(profile)} for rent Hong Kong"
    ]
    return new_queries(texts, tried)


def within_reach(texts: list[str], profile: Profile) -> list[str]:
    """With a commute limit, keep only searches in areas within reach of the campus (or named by the
    student). Seen live: told to try "cheaper areas", the model searched Mong Kok for HKUST, and the
    whole round was then rejected as too far. Until M3 brings real commutes, the area list decides."""
    areas = candidate_areas(profile)
    if not profile.max_commute_min or not areas:
        return texts
    return [t for t in texts if any(a.lower() in t.lower() for a in areas)]


def new_queries(texts: list[str], tried: list[str]) -> list[str]:
    seen = {_norm(t) for t in tried}
    out: list[str] = []
    for t in texts:
        if t.strip() and _norm(t) not in seen:
            seen.add(_norm(t))
            out.append(t.strip())
    return out[:MAX_QUERIES]


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


async def plan_search(
    client: ModelClient, profile: Profile, tried: list[str], advice: str | None
) -> SearchPlan:
    lines = [f"Profile: {profile.model_dump_json()}"]
    if areas := candidate_areas(profile):
        lines.append(f"Areas within reach of the campus or named by the student: {', '.join(areas)}")
    if tried:
        lines.append(f"Already tried: {'; '.join(tried)}")
    if advice:
        lines.append(f"Advice from the last round: {advice}")
    return await client.typed_call("plan_search", SYSTEM, "\n".join(lines), SearchPlan)
