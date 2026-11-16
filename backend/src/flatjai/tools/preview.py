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
    rent = _RENT.search(text)
    district = _AFTER_ROOMS.search(text)
    sa = _SA.search(text)
    rooms = _ROOMS.search(text)
    if not (rent or district):
        return None
    return ListingPreview(
        rent_hkd=_int(rent.group(1)) if rent else None,
        district=district.group(1) if district else None,
        saleable_sqft=_int(sa.group(1)) if sa else None,
        bedrooms=int(rooms.group(1)) if rooms else None,
    )


def preview_from_page(text: str) -> ListingPreview | None:
    """The labelled rent on a listing's own page ("Rent $19,000"), read with a regex before any model
    call. Used only to skip a listing that is surely over budget; extraction stays the source of truth."""
    rent = _RENT.search(" ".join(text.split()))
    return ListingPreview(rent_hkd=_int(rent.group(1))) if rent else None
