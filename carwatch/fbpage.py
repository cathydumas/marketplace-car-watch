"""Read a Facebook Marketplace listing page saved as text.

The skill opens a listing in a browser and saves the page text to
pages/<listing id>.txt. This module pulls out the details the alert email
leaves out: km, transmission, description and how long it has been listed.
"""
from __future__ import annotations

import re
from pathlib import Path

from .parser import _pick_km

PRICE_LINE_RE = re.compile(r"^CA\s?\$\s?([\d,]+)$")
LISTED_RE = re.compile(
    r"Listed (\d+|a|an) (minute|hour|day|week|month|year)s? ago in (.+)$", re.I
)
DRIVEN_RE = re.compile(r"Driven ([\d,]+)\s?(?:km|kilometres|kilometers)", re.I)
TRANS_RE = re.compile(r"^(Manual|Automatic) transmission$", re.I)
DESC_START = ("Seller's description", "Details")
DESC_STOP_RE = re.compile(
    r"^(See more|See less|Seller information|Seller details|.+ · Location is approximate)$"
)
DEALER_RE = re.compile(
    r"\b(dealer(ship)?|financing|everyone is approved|we deliver|stock ?#|#[A-Z]?\d{4,}|"
    r"auto group|motors|auto sales|carfax and inspection|warranty available)\b",
    re.I,
)
UNIT_DAYS = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}


def parse_page(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out = {}
    price_index = next((i for i, l in enumerate(lines) if PRICE_LINE_RE.match(l)), None)
    if price_index is not None:
        prices = []
        for line in lines[price_index:price_index + 2]:
            match = PRICE_LINE_RE.match(line)
            if match:
                prices.append(int(match.group(1).replace(",", "")))
        out["price"] = min(prices)
        if price_index > 0:
            out["title"] = lines[price_index - 1]
    for line in lines:
        listed = LISTED_RE.search(line)
        if listed and "days_listed" not in out:
            count = 1 if listed.group(1).lower() in ("a", "an") else int(listed.group(1))
            out["days_listed"] = count * UNIT_DAYS[listed.group(2).lower()]
            out["location"] = listed.group(3).strip()
        driven = DRIVEN_RE.search(line)
        if driven and "km" not in out:
            out["km"] = int(driven.group(1).replace(",", ""))
        if line.lower() == "clean title":
            out["clean_title"] = True
        trans = TRANS_RE.match(line)
        if trans and "transmission" not in out:
            out["transmission"] = trans.group(1).lower()
    start = next((i for i, l in enumerate(lines) if l in DESC_START), None)
    if start is not None:
        desc = []
        for line in lines[start + 1:]:
            if DESC_STOP_RE.match(line):
                break
            desc.append(line)
        out["description"] = "\n".join(desc)
    body = out.get("description", "")
    if body:
        out["seller_type"] = "dealer" if DEALER_RE.search(body) else "private"
    return out


def load_pages(folder: Path) -> dict:
    """Return {listing id: parsed page} for every pages/<id>.txt file."""
    pages = {}
    folder = Path(folder)
    if not folder.is_dir():
        return pages
    for path in sorted(folder.glob("*.txt")):
        if path.stem.isdigit():
            pages[path.stem] = parse_page(path.read_text(encoding="utf-8", errors="replace"))
    return pages


def apply_page(listing, page: dict) -> None:
    """Fill gaps in a listing from its page. The page wins for km and price."""
    for key in ("km", "price", "transmission", "description", "days_listed", "seller_type"):
        if page.get(key) not in (None, ""):
            setattr(listing, key, page[key])
    if page.get("clean_title") and "clean title" not in (listing.raw_text or "").lower():
        listing.raw_text = ((listing.raw_text or "") + " Clean title").strip()
    if listing.km is None and listing.description:
        listing.km = _pick_km(listing.description)
    for key in ("title", "location"):
        if page.get(key) and not getattr(listing, key):
            setattr(listing, key, page[key])
    if page.get("title") and not listing.year:
        match = re.search(r"\b(19[89]\d|20[0-3]\d)\b", page["title"])
        if match:
            listing.year = int(match.group(1))
