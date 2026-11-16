"""Grounding check in code: every extracted fact must be backed by text on the fetched page.

For each filled field the extractor must quote an evidence span. A span counts only if it occurs in
the page text (ignoring whitespace and case), and for numbers the value must occur inside the span.
Unsupported optional fields are cleared; an unsupported rent rejects the listing outright, because a
wrong price is the most expensive mistake FlatJai can make.
"""

import re

from pydantic import BaseModel

from ..schemas import Listing

ALWAYS_PRESENT = {"source_url", "portal", "title", "evidence", "agent_fee"}
# Booleans whose default is the safe reading: claiming the other value needs evidence.
DEFAULTS = {"room_only": False}
# The rent span must say it is rent: portals also show sale prices, price per ft² and mortgage
# estimates ("Monthly：$14,623") on the same page, all as bare dollar figures.
RENT_LABELS = ("rent", "租")
_SPACE = re.compile(r"\s+")


class Unsupported(Exception):
    pass


class Verified(BaseModel):
    listing: Listing
    dropped: list[str]  # fields cleared because the page does not support them


def _norm(s: str) -> str:
    return _SPACE.sub("", s).lower()


def _digits(s: str) -> str:
    return re.sub(r"(?<=\d)[,\s](?=\d{3})", "", s)


def supports(field: str, value: object, span: str | None, page_norm: str) -> bool:
    if not span or _norm(span) not in page_norm:
        return False
    if isinstance(value, bool) or value is None:
        return True
    if field == "rent_hkd_month":
        # labelled as rent AND written as a money amount: "Rent $12,800", "月租 HK$12,800", "12,800元"
        money = rf"(?:\$|HK\$|HKD)\s*{value}(?!\d)|(?<!\d){value}\s*(?:元|港元|HKD)"
        return any(label in span.lower() for label in RENT_LABELS) and bool(re.search(money, _digits(span)))
    if isinstance(value, int):
        return re.search(rf"(?<!\d){value}(?!\d)", _digits(span)) is not None
    if isinstance(value, str):
        # names: the value should be in the span or at least on the page (breadcrumbs, headings)
        return _norm(value) in _norm(span) or _norm(value) in page_norm
    return True  # dates and others: the span is on the page, accept


def verify_listing(listing: Listing, page_text: str) -> Verified:
    page_norm = _norm(page_text)
    data = listing.model_dump()
    dropped: list[str] = []
    for field, value in data.items():
        if field in ALWAYS_PRESENT or value is None or DEFAULTS.get(field, object()) == value:
            continue
        if supports(field, value, listing.evidence.get(field), page_norm):
            continue
        if field == "rent_hkd_month":
            raise Unsupported(f"rent {value} not found on {listing.source_url}")
        dropped.append(field)
        data[field] = DEFAULTS.get(field)
    # keep evidence only for fields that still hold a value (models sometimes cite empty fields)
    data["evidence"] = {
        k: v for k, v in listing.evidence.items() if k not in dropped and data.get(k) not in (None, False)
    }
    return Verified(listing=Listing.model_validate(data), dropped=dropped)
