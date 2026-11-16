"""Listing portals FlatJai knows about, and which of their URLs are single-listing pages.

`allowed=False` means the site answers automated clients with a bot challenge (HTTP 403) or its
terms rule us out. We never try to get around that: such URLs are dropped before fetching.
Checked 2026-11-16; see docs/decisions/0002-listing-sources.md.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Portal:
    name: str
    domains: tuple[str, ...]
    allowed: bool
    listing_path: re.Pattern[str] | None = None  # path of a single-listing page
    list_path: re.Pattern[str] | None = None  # path of a page listing many rentals (an area, an estate)
    browse_url: str | None = None  # the portal's own list of rentals (fallback when web search is down)

    def is_listing(self, url: str) -> bool:
        return _matches(self.listing_path, url)

    def is_list(self, url: str) -> bool:
        return _matches(self.list_path, url)


def _matches(pattern: re.Pattern[str] | None, url: str) -> bool:
    return pattern is not None and bool(pattern.search(urlsplit(url).path))


PORTALS: tuple[Portal, ...] = (
    Portal(
        name="centaline",
        domains=("hk.centanet.com",),
        allowed=True,
        # /findproperty/en/detail/Le-Mont_APM869?theme=rent (also /zh-hk/ pages)
        listing_path=re.compile(r"^/findproperty/[\w-]+/detail/[^/]+_[A-Z]{3}\d+"),
        # /findproperty/en/list/rent/Tseung-Kwan-O_19-HMA112 (an area or estate)
        list_path=re.compile(r"^/findproperty/[\w-]+/list/rent(/[^/]+)?/?$"),
        browse_url="https://hk.centanet.com/findproperty/en/list/rent",
    ),
    Portal(
        name="midland", domains=("www.midland.com.hk",), allowed=True
    ),  # pages render client-side; no reader yet
    Portal(name="28hse", domains=("www.28hse.com",), allowed=False),
    Portal(name="spacious", domains=("www.spacious.hk",), allowed=False),
    Portal(name="squarefoot", domains=("www.squarefoot.com.hk",), allowed=False),
    Portal(name="house730", domains=("www.house730.com",), allowed=False),
)


def portal_for(url: str) -> Portal | None:
    host = (urlsplit(url).hostname or "").lower()
    return next((p for p in PORTALS if host in p.domains), None)


def readable_listing_portals() -> list[Portal]:
    """Portals we may fetch and whose listing pages we know how to recognise."""
    return [p for p in PORTALS if p.allowed and p.listing_path is not None]
