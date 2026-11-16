"""HTML -> the plain text a model reads. Deterministic, so the same page always gives the same text
(evidence spans are matched against this text, and extraction is cached by its hash)."""

import re
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

DROP = "script, style, noscript, svg, iframe, template, header, footer, nav, form, button"
_WS = re.compile(r"[ \t 　]+")


def html_to_text(html: str, max_chars: int | None = None) -> str:
    tree = LexborHTMLParser(html)
    for node in tree.css(DROP):
        node.decompose()
    root = tree.body or tree.root
    if root is None:
        return ""
    lines: list[str] = []
    for raw in root.text(separator="\n").split("\n"):
        line = _WS.sub(" ", raw).strip()
        if not line or (lines and lines[-1] == line):
            continue
        # Portals split figures over elements ("$", "13,500"); glue lone symbols to the next value.
        if lines and lines[-1] in {"$", "HK$", "HKD"}:
            lines[-1] = f"{lines[-1]}{line}"
        else:
            lines.append(line)
    text = "\n".join(lines)
    return text[:max_chars] if max_chars else text


def page_title(html: str) -> str:
    node = LexborHTMLParser(html).css_first("title")
    return node.text(strip=True) if node else ""


def page_links(html: str, base_url: str) -> list[str]:
    """Absolute http(s) links in document order, without duplicates."""
    seen: dict[str, None] = {}
    for a in LexborHTMLParser(html).css("a[href]"):
        url = urljoin(base_url, a.attributes.get("href") or "").split("#")[0]
        if url.startswith(("http://", "https://")):
            seen.setdefault(url, None)
    return list(seen)
