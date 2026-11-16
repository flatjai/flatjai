"""Typed contracts shared by the agent, tools and the model (Pydantic -> JSON schema)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Profile(BaseModel):
    """What the student needs, parsed from a plain-language brief."""

    budget_hkd_month: int | None = Field(None, description="Max monthly rent in HK$; null if not stated")
    campus: str | None = Field(None, description="Campus or place to commute to, e.g. 'HKUST'")
    max_commute_min: int | None = Field(None, description="Max door-to-door minutes to the campus")
    districts: list[str] = Field(default_factory=list, description="Preferred districts or areas")
    room_only: bool | None = Field(None, description="True if a room in a shared flat is fine")
    bedrooms: int | None = None
    flatmates: int | None = None
    move_in: date | None = None
    lease_months: int | None = None
    soft_preferences: list[str] = Field(default_factory=list, description="e.g. 'quiet', 'near MTR', 'gym'")
    missing: list[str] = Field(
        default_factory=list,
        description="Hard constraints the brief does not give and the agent should ask about",
    )


class Listing(BaseModel):
    source_url: HttpUrl
    portal: str
    title: str
    rent_hkd_month: int
    saleable_sqft: int | None = None
    gross_sqft: int | None = None
    bedrooms: int | None = None
    room_only: bool = False
    furnished: bool | None = None
    estate: str | None = None
    address: str | None = None
    district: str | None = None
    mgmt_fee_included: bool | None = None
    mgmt_fee_hkd_month: int | None = None
    agent_fee: Literal["half", "full", "none", "unknown"] = "unknown"
    available_from: date | None = None
    evidence: dict[str, str] = Field(default_factory=dict, description="field name -> exact source text")
