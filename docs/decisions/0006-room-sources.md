# 0006 Rooms from student-housing sites: uhomes and Amber Student

Date: 2026-11-17 · Status: accepted (personal project; facts and links only)

## Context
Centaline lists whole flats. The main student brief ("own room, 9k, near HKUST") found nothing.
Six further sites were checked on 2026-11-17 (robots.txt with our user agent, one polite request,
terms of use):

| Site | robots / access | Terms | Content | Decision |
|---|---|---|---|---|
| uhomes (en.uhomes.com) | allowed; listings in HTML; 55 properties on the city page | Disclaimer has no scraping or copying clause | rooms, e.g. Hang Hau HK$7,300-8,000, 12-month leases | read |
| Amber Student (amberstudent.com) | allowed; 3 HK properties in HTML, the rest via a private API | copyright on content | rooms, e.g. TKO from HK$7,380 | read pages only, never the API |
| OKAY.com | allowed | copyright; reuse for personal use with credit | whole flats, mostly expat | not yet |
| HongKongHomes | no robots.txt; listings rendered client-side | not found | luxury | skip |
| Expat.com | allowed | forbids reproducing content without written consent; classifieds by individuals | rooms | excluded |
| Savills | empty 202 to our client; robots names AI crawlers | n/a | luxury | excluded |

## Decision
- uhomes and Amber are portals with `rooms=True`: their own list pages are read every first round,
  and they are searched first when the student wants a room. Web results from these worldwide sites
  must mention Hong Kong (search returned Orlando, Boston and Singapore listings).
- Same rules as Centaline: robots.txt, 1 request per 2 s per site, facts with evidence and a link
  back, no photos, no text copied onto our pages, no private APIs.
- A property page may offer several room types: the extractor describes the cheapest room that is
  not sold out; the page pre-filter uses the lowest monthly price, so a cheap room is never skipped.
  A sold-out page is skipped. New listing fields: bathroom (private or shared), lease months.
- A price written "HK$7,300 /month" counts as rent (the grounding check accepted only a "Rent"
  label); "Monthly：$14,623" (a mortgage) still does not.
- When the model reports a rental but leaves the rent empty while quoting it (seen on both sites),
  the lowest monthly price on the page is filled in by code, quoted as evidence, and verified.
- On a student-housing site an unstated room type is unknown, not "whole flat".

## Result
The own-room 9k HKUST brief now returns a room: Hang Hau Metro City, HK$7,700/month, budget, room
and area checks passed. Amber's HK supply is small and mostly far from HKUST.
