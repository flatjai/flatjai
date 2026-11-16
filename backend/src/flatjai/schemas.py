"""Typed contracts shared by the agent, tools and the model (Pydantic -> JSON schema)."""

from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Profile(BaseModel):
    """What the student needs, parsed from a plain-language brief."""

    budget_hkd_month: int | None = Field(
        None, description="Max monthly rent in HK$ ('9k' = 9000); null if not stated"
    )
    budget_is_total: bool = Field(
        False, description="true if the budget is for the whole flat shared with flatmates ('20k total')"
    )
    campus: str | None = Field(
        None, description="Campus or place to commute to, e.g. 'HKUST', 'HKU', 'CityU'"
    )
    max_commute_min: int | None = Field(
        None, description="Max one-way commute in minutes ('under 40 min' = 40)"
    )
    districts: list[str] = Field(
        default_factory=list, max_length=5, description="Districts or areas the student names"
    )
    room_only: bool | None = Field(
        None,
        description="true: a room in a shared flat ('own room', 'room'); false: a whole flat; null: not said",
    )
    bedrooms: int | None = Field(None, description="Bedrooms wanted when renting a whole flat")
    flatmates: int | None = Field(None, description="People sharing with the student, if said")
    move_in: date | None = Field(None, description="Earliest move-in date; a month alone means its 1st day")
    lease_months: int | None = None
    soft_preferences: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Wishes that are not hard limits, e.g. 'quiet', 'near MTR', 'gym'",
    )

    HARD_CONSTRAINTS: ClassVar[tuple[str, ...]] = ("budget_hkd_month", "campus", "move_in")
    ZERO_MEANS_UNKNOWN: ClassVar[tuple[str, ...]] = ("budget_hkd_month", "max_commute_min", "lease_months")

    @model_validator(mode="before")
    @classmethod
    def placeholders_mean_unknown(cls, data: object) -> object:
        """Models asked to write every key sometimes put 0 or "" where they mean "not stated".
        (bedrooms 0 stays: it means a studio.)"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for key, value in data.items():
            if value == "" or (key in cls.ZERO_MEANS_UNKNOWN and value == 0):
                data[key] = None
        return data

    def missing(self) -> list[str]:
        """Hard constraints the brief leaves open (checked in code, not by the model)."""
        return [f for f in self.HARD_CONSTRAINTS if getattr(self, f) is None]


class Listing(BaseModel):
    source_url: HttpUrl
    portal: str
    title: str
    rent_hkd_month: int
    saleable_sqft: int | None = None
    gross_sqft: int | None = None
    bedrooms: int | None = None
    room_only: bool = False
    bathroom: Literal["private", "shared"] | None = None  # for a room: its own bathroom or a shared one
    lease_months: int | None = None  # minimum or fixed lease length
    furnished: bool | None = None
    estate: str | None = None
    address: str | None = None
    district: str | None = None
    mgmt_fee_included: bool | None = None
    mgmt_fee_hkd_month: int | None = None
    agent_fee: Literal["half", "full", "none", "unknown"] = "unknown"
    available_from: date | None = None
    evidence: dict[str, str] = Field(default_factory=dict, description="field name -> exact source text")
