"""Parse Facebook Marketplace alert emails into Listing objects.

The real layout of these emails is not verified yet. The parser does not
depend on a fixed layout. It finds links to Marketplace items, then reads
the text near each link. It works on HTML bodies, plain text bodies and
markdown style links.
"""
from __future__ import annotations

import json
import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from .models import Listing

ITEM_RE = re.compile(r"marketplace/item/(\d{6,})")
LINK_OR_URL_RE = re.compile(
    r"\[([^\]]*)\]\((https?://[^)\s]+)\)|https?://[^\s<>\")\]]+"
)
PRICE_RE = re.compile(
    r"(?:CA\s?\$|C\$|\$)\s?(\d{1,3}(?:,\d{3})+|\d{3,6})(?![\d,])"
)
PROVINCES = "BC|B\\.C\\.|AB|SK|MB|ON|QC|NB|NS|PE|PEI|NL|YT|NT|NU"
LOC_RE = re.compile(
    r"((?:[A-Z][A-Za-z.'\-]+\s)?[A-Z][A-Za-z.'\-]+),\s?(" + PROVINCES + r")\b"
)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
KM_RE = re.compile(
    r"(?<![$\d,])(\d{1,3}(?:,\d{3})+|\d{2,6})\s?(?:km|kms|kilometres|kilometers)\b",
    re.I,
)
KM_K_RE = re.compile(r"(?<![$\d])(\d{2,3})\s?k\s?(?:km|kms)\b", re.I)
GENERIC_RE = re.compile(
    r"^(view|see|open|message|send|share|save|get|shop|new listing|marketplace|"
    r"listed|notify|unsubscribe|facebook)\b",
    re.I,
)
FOOTER_RE = re.compile(
    r"unsubscribe|notification settings|manage .{0,30}notifications|privacy policy",
    re.I,
)
CONTEXT_BUDGET = 350


def _item_id(href: str):
    """Find a Marketplace item id, even inside redirect-wrapped links."""
    current = href
    for _ in range(4):
        match = ITEM_RE.search(current)
        if match:
            return match.group(1)
        decoded = unquote(current)
        if decoded == current:
            break
        current = decoded
    match = ITEM_RE.search(current)
    return match.group(1) if match else None


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "a":
            self.events.append(("a_start", dict(attrs).get("href") or ""))
        elif tag in ("br", "p", "div", "tr", "td", "li", "h1", "h2", "h3", "table"):
            self.events.append(("text", "\n"))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "a":
            self.events.append(("a_end",))
        elif tag in ("p", "div", "tr", "li", "table"):
            self.events.append(("text", "\n"))

    def handle_data(self, data):
        if not self._skip:
            self.events.append(("text", re.sub(r"[ \t\r\f\v]+", " ", data)))


def _events_from_html(html: str) -> list:
    collector = _Collector()
    collector.feed(html)
    collector.close()
    return collector.events


def _events_from_text(text: str) -> list:
    events = []
    pos = 0
    for match in LINK_OR_URL_RE.finditer(text):
        if match.start() > pos:
            events.append(("text", text[pos:match.start()]))
        if match.group(2):
            events.append(("a_start", match.group(2)))
            events.append(("text", match.group(1)))
            events.append(("a_end",))
        else:
            events.append(("a_start", match.group(0)))
            events.append(("a_end",))
        pos = match.end()
    if pos < len(text):
        events.append(("text", text[pos:]))
    return events


def _blocks(events: list):
    blocks = {}
    order = []
    current = None
    budget = 0
    anchor_id = None
    for event in events:
        kind = event[0]
        if kind == "a_start":
            item_id = _item_id(event[1])
            anchor_id = item_id
            if item_id:
                current = item_id
                budget = CONTEXT_BUDGET
                if item_id not in blocks:
                    blocks[item_id] = {"anchor_text": [], "text": []}
                    order.append(item_id)
        elif kind == "a_end":
            anchor_id = None
        else:
            chunk = event[1]
            if current is None:
                continue
            reached_footer = False
            footer = FOOTER_RE.search(chunk)
            if footer and not anchor_id:
                chunk = chunk[:footer.start()]
                reached_footer = True
            if chunk:
                if anchor_id:
                    blocks[current]["anchor_text"].append(chunk)
                blocks[current]["text"].append(chunk)
                budget -= len(chunk)
            if reached_footer or (budget <= 0 and not anchor_id):
                current = None
    return order, blocks


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_price(text: str) -> str:
    return _clean(PRICE_RE.sub("", text))


def _pick_title(block: dict) -> str:
    anchors = [_clean(piece) for piece in block["anchor_text"]]
    lines = [_clean(chunk) for chunk in "".join(block["text"]).split("\n")]
    for source in (anchors, lines):
        for piece in source:
            candidate = _strip_price(piece)
            if len(re.findall(r"[A-Za-z]", candidate)) < 4:
                continue
            if GENERIC_RE.match(candidate):
                continue
            if LOC_RE.fullmatch(candidate):
                continue
            return candidate[:160]
    return ""


def _pick_price(text: str):
    prices = []
    for match in PRICE_RE.finditer(text):
        value = int(match.group(1).replace(",", ""))
        if value not in prices:
            prices.append(value)
        if len(prices) == 2:
            break
    if not prices:
        return None
    # Two prices in one card is usually an old price and a new one. Take the lower.
    return min(prices)


def _pick_location(lines: list, text: str) -> str:
    for line in lines:
        if 0 < len(line) <= 60:
            match = LOC_RE.search(line)
            if match:
                return f"{match.group(1)}, {match.group(2).replace('.', '')}"
    match = LOC_RE.search(text)
    if match:
        return f"{match.group(1)}, {match.group(2).replace('.', '')}"
    return ""


def _pick_km(text: str):
    match = KM_RE.search(text)
    if match:
        return int(match.group(1).replace(",", ""))
    match = KM_K_RE.search(text)
    if match:
        return int(match.group(1)) * 1000
    return None


def _build(item_id: str, block: dict) -> Listing:
    raw = "".join(block["text"])
    lines = [_clean(chunk) for chunk in raw.split("\n")]
    lines = [line for line in lines if line]
    flat = _clean(raw)
    title = _pick_title(block)
    year_match = YEAR_RE.search(title) or YEAR_RE.search(flat)
    return Listing(
        listing_id=item_id,
        url=f"https://www.facebook.com/marketplace/item/{item_id}/",
        title=title,
        price=_pick_price(flat),
        location=_pick_location(lines, flat),
        year=int(year_match.group(1)) if year_match else None,
        km=_pick_km(flat),
        raw_text=flat[:600],
    )


def parse_body(html: str = "", text: str = "") -> list:
    """Return listings found in one email body. HTML first, then plain text."""
    for events in (
        _events_from_html(html) if html else [],
        _events_from_text(text) if text else [],
    ):
        order, blocks = _blocks(events)
        if order:
            return [_build(item_id, blocks[item_id]) for item_id in order]
    return []


def parse_email(email: dict) -> list:
    listings = parse_body(email.get("html", ""), email.get("text", ""))
    for listing in listings:
        listing.source_email_id = email.get("id", "")
        listing.email_date = email.get("date", "")
    return listings


def load_email(path: Path) -> dict:
    """Load one saved email. Supports .json (from the skill), .eml, .html and .txt."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "id": str(data.get("id") or path.stem),
            "date": data.get("date", ""),
            "subject": data.get("subject", ""),
            "sender": data.get("sender", ""),
            "html": data.get("html") or data.get("htmlBody") or "",
            "text": data.get("text") or data.get("plaintextBody") or "",
        }
    if suffix == ".eml":
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        html_part = message.get_body(preferencelist=("html",))
        text_part = message.get_body(preferencelist=("plain",))
        return {
            "id": path.stem,
            "date": str(message["date"] or ""),
            "subject": str(message["subject"] or ""),
            "sender": str(message["from"] or ""),
            "html": html_part.get_content() if html_part else "",
            "text": text_part.get_content() if text_part else "",
        }
    body = path.read_text(encoding="utf-8", errors="replace")
    is_html = suffix in (".html", ".htm")
    return {
        "id": path.stem,
        "date": "",
        "subject": "",
        "sender": "",
        "html": body if is_html else "",
        "text": "" if is_html else body,
    }
