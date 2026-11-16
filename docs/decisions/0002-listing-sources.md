# 0002 Listing sources: read only portals that allow automated clients

Date: 2026-11-16 · Status: accepted (team to confirm the source list)

## What we checked (robots.txt with the FlatJai user agent, 2026-11-16)
| Portal | Result | Use |
|---|---|---|
| Centaline (hk.centanet.com) | robots.txt allows listing pages, crawl-delay 1; pages render on the server | **Read** |
| Midland (www.midland.com.hk) | robots.txt allows; pages render in the browser (data in `__NEXT_DATA__`) | Allowed, no reader yet |
| 28Hse, Spacious, Squarefoot, House730 | HTTP 403 bot challenge, even for robots.txt | **Not read** |

## Decision
- `tools/portals.py` lists every portal with `allowed`. Blocked portals are never fetched, and a bot
  challenge is never worked around: the fetcher raises `FetchBlocked` and the agent moves on.
- An unreadable robots.txt counts as "disallow everything".
- 1 request per 2 s per domain (robots crawl-delay wins if longer), user agent names the project,
  raw pages stored by SHA-256 so the evaluation snapshot never re-fetches.
- Search goes through SearXNG with `site:` restriction. It mostly returns Centaline **area list pages**
  (`/list/rent/Hang-Hau_19-HMA060`), so the agent opens one list page per query and reads the
  listing links on it; these are live, whereas indexed single listings are often already let (404).
  If search returns nothing, the agent reads the portal's own rental list.

## Consequences
- Centaline mostly lists whole flats; rooms in shared flats (the main student case) are rare.
  Finding a source for rooms that permits automated access is an open team decision (Nuttapat owns
  portal connectors). Options: Midland's embedded JSON, permission from a room-sharing site, or a
  hand-collected snapshot.
- Prices on Centaline sit next to a sale price and a mortgage estimate ("Monthly：$14,623"). The
  verifier requires the rent's evidence span to carry a rent label and a money amount.
