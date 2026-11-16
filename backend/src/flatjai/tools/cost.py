"""Cost tool: what a home really costs a student. Pure function, no model involved.

Hong Kong customs (stated as assumptions in the answer):
- deposit: 2 months' rent, refundable, paid at move-in
- first month's rent paid in advance
- agent commission: half a month's rent from the tenant, unless the listing says otherwise
- management fee: usually included in rent for residential leases; added when the listing says not
"""
from pydantic import BaseModel

from ..schemas import Listing

DEPOSIT_MONTHS = 2
AGENT_FEE_MONTHS = {"half": 0.5, "full": 1.0, "none": 0.0, "unknown": 0.5}
UTILITIES_HKD_MONTH = 600  # electricity + water + gas estimate for one student; tune with real bills


class CostItem(BaseModel):
    label: str
    hkd: int
    assumed: bool = False


class Cost(BaseModel):
    monthly_hkd: int
    move_in_hkd: int
    monthly_items: list[CostItem]
    move_in_items: list[CostItem]


def cost(listing: Listing, utilities_hkd_month: int = UTILITIES_HKD_MONTH) -> Cost:
    rent = listing.rent_hkd_month
    monthly = [CostItem(label="Rent", hkd=rent)]
    if listing.mgmt_fee_included is False and listing.mgmt_fee_hkd_month:
        monthly.append(CostItem(label="Management fee", hkd=listing.mgmt_fee_hkd_month))
    monthly.append(CostItem(label="Utilities (estimate)", hkd=utilities_hkd_month, assumed=True))

    agent = round(rent * AGENT_FEE_MONTHS[listing.agent_fee])
    move_in = [
        CostItem(label="Deposit (2 months, refundable)", hkd=rent * DEPOSIT_MONTHS, assumed=True),
        CostItem(label="First month's rent", hkd=rent),
        CostItem(label="Agent commission", hkd=agent, assumed=listing.agent_fee == "unknown"),
    ]
    return Cost(
        monthly_hkd=sum(i.hkd for i in monthly),
        move_in_hkd=sum(i.hkd for i in move_in),
        monthly_items=monthly,
        move_in_items=move_in,
    )
