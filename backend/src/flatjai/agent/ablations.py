"""Ablations for experiment E2: switch off one agent part to see what it earns.

Set with FJ_ABLATE (comma-separated), evaluation only; the default runs the full agent.
  no_reflect   one plan -> search -> read pass, then answer (no read-more, no re-plan)
  no_dedup     the same home on two sites (or twice on one) is not merged
  model_facts  the model states each home's monthly cost, move-in cost and commute instead of the
               cost tool and the router; the tool figures are kept beside them (tool_*) so the
               scorer can measure the model's error. Hard checks use the model's figures, as an
               agent without these tools would.
"""

from pydantic import BaseModel, Field

from ..model_client import ModelClient
from ..schemas import Listing, Profile
from ..tools.cost import Cost, CostItem

ABLATIONS = ("no_reflect", "no_dedup", "model_facts")


def parse_ablations(raw: str) -> frozenset[str]:
    names = frozenset(a.strip() for a in raw.split(",") if a.strip())
    if unknown := names - set(ABLATIONS):
        raise ValueError(f"unknown ablation(s) {sorted(unknown)}; known: {list(ABLATIONS)}")
    return names


class ModelFacts(BaseModel):
    monthly_hkd: int = Field(description="Total monthly cost for the student: rent, fees, utilities")
    move_in_hkd: int = Field(description="Total cash needed at move-in: deposit, first rent, agent fee")
    commute_min: int = Field(description="One-way minutes by public transport to the campus at 08:30")


SYSTEM = """You help a university student in Hong Kong judge a rental home. From the listing, state
the student's total monthly cost, the cash needed at move-in, and the one-way public-transport
commute in minutes to their campus on a weekday morning. Give your best single figures.
Reply with JSON only."""


async def model_facts(model: ModelClient, listing: Listing, profile: Profile) -> ModelFacts:
    user = (
        f"Campus: {profile.campus}\nListing: {listing.title}; district {listing.district}; "
        f"address {listing.address}; rent HK${listing.rent_hkd_month:,}/month; "
        f"management fee included: {listing.mgmt_fee_included}; agent fee: {listing.agent_fee}"
    )
    return await model.typed_call("model_facts", SYSTEM, user, ModelFacts)


def model_cost(f: ModelFacts, tool: Cost) -> tuple[Cost, dict[str, int]]:
    """The model's figures in the Cost shape, with the cost tool's totals kept for scoring."""
    return Cost(
        monthly_hkd=f.monthly_hkd,
        move_in_hkd=f.move_in_hkd,
        monthly_items=[CostItem(label="Model estimate", hkd=f.monthly_hkd, assumed=True)],
        move_in_items=[CostItem(label="Model estimate", hkd=f.move_in_hkd, assumed=True)],
    ), {"tool_monthly_hkd": tool.monthly_hkd, "tool_move_in_hkd": tool.move_in_hkd}
