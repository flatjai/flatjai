from flatjai.schemas import Listing
from flatjai.tools.cost import cost


def listing(**kw) -> Listing:
    base = {"source_url": "https://example.com/1", "portal": "test", "title": "t", "rent_hkd_month": 9000}
    return Listing(**(base | kw))


def test_half_month_agent_fee_and_two_month_deposit():
    c = cost(listing(agent_fee="half"), utilities_hkd_month=600)
    assert c.monthly_hkd == 9600
    assert c.move_in_hkd == 18000 + 9000 + 4500


def test_management_fee_added_only_when_not_included():
    assert cost(listing(mgmt_fee_included=False, mgmt_fee_hkd_month=800)).monthly_hkd == 9000 + 800 + 600
    assert cost(listing(mgmt_fee_included=True, mgmt_fee_hkd_month=800)).monthly_hkd == 9000 + 600


def test_unknown_agent_fee_is_flagged_as_assumed():
    item = next(i for i in cost(listing()).move_in_items if i.label == "Agent commission")
    assert item.assumed and item.hkd == 4500
