"""Listings from sources other than Facebook alert emails.

AutoTrader.ca, Craigslist, CarGurus.ca and any other site are read in a
browser and saved as JSON lines, one listing per line:

  {"source": "autotrader", "id": "...", "url": "...", "title": "2019 Subaru BRZ Sport-tech",
   "price": 18850, "km": 43000, "location": "Surrey, BC", "transmission": "automatic",
   "description": "...", "days_listed": 14, "seller_type": "dealer",
   "rating": "Great price"}

Only source, id, url, title and price are needed. A "rating" is the site's
own deal badge, kept as a reference next to the tool's call.

A file can also hold reference-only lines, for a site whose ratings we want
but whose listings duplicate other sources:

  {"source": "cargurus", "reference_only": true, "title": "2019 Toyota 86 GT",
   "price": 22900, "km": 78303, "rating": "Fair Deal", "url": "..."}

The same car is often listed on several sites. merge_duplicates keeps one
listing, notes the other links, and flags km that disagree.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Listing

SOURCE_NAMES = {
    "facebook": "Facebook Marketplace",
    "autotrader": "AutoTrader.ca",
    "craigslist": "Craigslist",
    "cargurus": "CarGurus.ca",
    "kijiji": "Kijiji",
}
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")


def source_name(source: str) -> str:
    return SOURCE_NAMES.get(source, source.title())


def _listing_from(record: dict) -> Listing:
    source = record.get("source", "other")
    raw_id = str(record.get("id") or record.get("url") or "")
    listing_id = raw_id if source == "facebook" else f"{source}:{raw_id}"
    title = record.get("title", "")
    year = record.get("year")
    if not year:
        match = YEAR_RE.search(title)
        year = int(match.group(1)) if match else None
    listing = Listing(
        listing_id=listing_id,
        url=record.get("url") or "",
        title=title,
        price=record.get("price"),
        location=record.get("location", ""),
        year=year,
        km=record.get("km"),
        raw_text=record.get("text", ""),
        description=record.get("description", ""),
        transmission=record.get("transmission", ""),
        days_listed=record.get("days_listed"),
        seller_type=record.get("seller_type", ""),
    )
    listing.source = source
    listing.found_by = list(record.get("found_by", [])) or [source_name(source)]
    listing.vin = (record.get("vin") or "").upper()
    listing.carfax_url = record.get("carfax_url", "")
    if record.get("rating"):
        listing.references.append({"source": source, "rating": record["rating"]})
    return listing


def load_listings(path: Path) -> tuple:
    """Return (listings, references) from a .jsonl file or a folder of them."""
    path = Path(path)
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    listings, references = [], []
    for file in files:
        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as err:
                raise ValueError(f"{file.name} line {number}: {err}") from err
            if record.get("reference_only"):
                references.append(record)
            else:
                listings.append(_listing_from(record))
    return listings, references


def _same_car(a: Listing, b: Listing) -> bool:
    if a.vin and b.vin:
        return a.vin == b.vin
    if not (a.year and b.year and a.year == b.year):
        return False
    if a.price is None or b.price is None or a.price < 2000 or b.price < 2000:
        return False
    if abs(a.price - b.price) > max(150, 0.01 * a.price):
        return False
    if a.model_match and b.model_match and a.model_match != b.model_match:
        same_family = {a.model_match, b.model_match} <= {"GR86", "GT86", "Toyota 86"}
        if not same_family:
            return False
    if a.km and b.km:
        return abs(a.km - b.km) <= max(8000, 0.12 * max(a.km, b.km))
    return True


def merge_duplicates(listings: list) -> list:
    """Collapse the same car listed on several sites into one listing."""
    kept = []
    for listing in listings:
        match = next((k for k in kept if _same_car(k, listing)), None)
        if match is None:
            kept.append(listing)
            continue
        # Prefer the record with more detail as the main one.
        main, other = (match, listing)
        if listing.filled_fields() + bool(listing.description) > match.filled_fields() + bool(match.description):
            kept[kept.index(match)] = listing
            main, other = listing, match
            main.also_listed.extend(other.also_listed)
        main.also_listed.append({"source": other.source, "url": other.url})
        main.references.extend(other.references)
        main.found_by = sorted(set(main.found_by) | set(other.found_by))
        # Keep what the other ad says, so a rebuilt title or a fee it mentions is not lost.
        extra = " ".join(x for x in (other.raw_text, other.description) if x)
        if extra and extra not in main.raw_text:
            main.raw_text = (main.raw_text + " " + extra).strip()
        if main.km and other.km and abs(main.km - other.km) >= 1000:
            main.flags_extra.append(
                f"km differs between sites: {main.km:,} on {source_name(main.source)}, "
                f"{other.km:,} on {source_name(other.source)}"
            )
        for key in ("km", "transmission", "description", "days_listed", "seller_type", "location", "vin", "carfax_url"):
            if getattr(main, key) in (None, "") and getattr(other, key) not in (None, ""):
                setattr(main, key, getattr(other, key))
    return kept


def attach_references(listings: list, references: list) -> None:
    """Attach reference-only ratings (for example CarGurus) to matching listings."""
    for record in references:
        ref = _listing_from(record)
        ref.model_match = ""
        for listing in listings:
            if _same_car(listing, ref):
                listing.references.append({"source": ref.source, "rating": record.get("rating", "")})
                if ref.url:
                    listing.also_listed.append({"source": ref.source, "url": ref.url})
                break
