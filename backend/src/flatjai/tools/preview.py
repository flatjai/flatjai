"""What a portal's list page already says about each listing, before its own page is read.

Centaline's rental list shows each listing as one link whose text holds the key facts:
  "LUNG POON COURT・... 1 Room Diamond Hill Diamond Hill 39 years ... S.A. 340 ft² ... Rent $ 15,500"
(the district is printed twice, once for each screen size). These figures are only used to skip
listings that cannot fit and to read promising ones first. Nothing shown to the student comes from
here: every figure on a card is still verified on the listing's own page.
"""

import re

from pydantic import BaseModel

_RENT = re.compile(r"(?:\bRent|租)\s*\$\s*([\d,]{3,})")
# student-housing sites: "From HK$7,300 /month", "HK$7,380/month" (a room's monthly price)
_PER_MONTH = re.compile(r"HK\$\s*([\d,]{3,})\s*/\s*month", re.I)
# uhomes cards: "..., Sha Tin, Hong Kong(China)" -> the district before the city
_BEFORE_CITY = re.compile(r"([A-Z][A-Za-z' ]{2,30}),\s*Hong Kong\s*\(China\)")
_SA = re.compile(r"S\.A\.\s*([\d,]+)\s*ft")
_ROOMS = re.compile(r"(\d+)\s*Rooms?\b")
# the district: the first phrase printed twice in a row after the room count
_AFTER_ROOMS = re.compile(r"(?:Rooms?|Studio)(?:・\(\d+ Suite\))?\s+([A-Z][A-Za-z' ]{2,30}?) \1\b")


class ListingPreview(BaseModel):
    rent_hkd: int | None = None
    district: str | None = None
    saleable_sqft: int | None = None
    bedrooms: int | None = None


def _int(text: str) -> int:
    return int(text.replace(",", ""))


def preview_from_card(text: str) -> ListingPreview | None:
    text = " ".join(text.split())
    rent = _rent(text)
    district = _AFTER_ROOMS.search(text) or _BEFORE_CITY.search(text)
    sa = _SA.search(text)
    rooms = _ROOMS.search(text)
    if not (rent or district):
        return None
    return ListingPreview(
        rent_hkd=rent,
        district=district.group(1) if district else None,
        saleable_sqft=_int(sa.group(1)) if sa else None,
        bedrooms=int(rooms.group(1)) if rooms else None,
    )


def preview_from_page(text: str) -> ListingPreview | None:
    """The labelled rent on a listing's own page ("Rent $19,000", "HK$7,300 /month"), read with a regex
    before any model call. Used only to skip a listing that is surely over budget; extraction stays the
    source of truth. With several room types, the LOWEST monthly price counts, so a cheap room is never
    skipped because a dearer one is listed first."""
    rent = _rent(" ".join(text.split()))
    return ListingPreview(rent_hkd=rent) if rent else None


def _rent(text: str) -> int | None:
    """A labelled rent ("Rent $13,500"), else the lowest monthly price ("HK$7,380/month")."""
    if labelled := _RENT.search(text):
        return _int(labelled.group(1))
    amounts = [_int(m.group(1)) for m in _PER_MONTH.finditer(text)]
    return min(amounts) if amounts else None
