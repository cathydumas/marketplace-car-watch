"""Comparable listings: real asking prices the value model learns from.

Sources:
  AutoTrader.ca search pages, saved as page text (.txt) or as the compact
  pipe format the skill's extract script prints (.psv)
  Facebook listings the car watch has seen, when they have year, km and price

Comps come from all of Canada. A car in Ontario is a fine price reference
even though Maggie only buys in BC.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from .filters import MODEL_PATTERNS, SEVERE_PATTERN
from .trims import build_spec

YEAR_TITLE_RE = re.compile(r"^((?:19|20)\d\d)\s+(.+)$")
AT_PRICE_RE = re.compile(r"^\$\s?([\d,]+)$")
AT_KM_RE = re.compile(r"^([\d,]+)\s?km$", re.I)
AT_LOC_RE = re.compile(r",\s?([A-Z]{2})$")
AT_FOOTER = "Do you want to be informed"


@dataclass
class Comp:
    key: str
    source: str
    year: int
    model: str
    price: int
    km: int
    transmission: str = ""
    trim: str = ""
    trim_tier: str = "unknown"
    make: str = ""
    generation: int = 0
    seller_type: str = ""
    province: str = ""
    text: str = ""
    first_seen: str = ""
    last_seen: str = ""
    price_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def model_from_title(title: str) -> str:
    lowered = title.lower()
    for name, pattern in MODEL_PATTERNS.items():
        if re.search(pattern, lowered, re.I):
            return name
    return ""


def _make_comp(source, year, title, subtitle, price, km, transmission, seller, province, seen):
    model = model_from_title(title)
    if not model or not year or price is None or km is None:
        return None
    spec = build_spec(model, year, f"{title}\n{subtitle}", transmission)
    key = f"{source}:{year}:{model}:{km}:{spec.transmission or 'x'}"
    return Comp(
        key=key,
        source=source,
        year=year,
        model=model,
        price=price,
        km=km,
        transmission=spec.transmission,
        trim=spec.trim,
        trim_tier=spec.trim_tier,
        make=spec.make,
        generation=spec.generation,
        seller_type=seller,
        province=province,
        text=subtitle[:120],
        first_seen=seen,
        last_seen=seen,
        price_history=[[seen, price]],
    )


def parse_autotrader_text(text: str, seen: str) -> list:
    """Parse AutoTrader.ca search results copied as page text."""
    if AT_FOOTER in text:
        text = text[: text.index(AT_FOOTER)]
    comps = []
    for block in text.split("Open listing details")[1:]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        title_index = next(
            (i for i, line in enumerate(lines) if YEAR_TITLE_RE.match(line)), None
        )
        if title_index is None:
            continue
        if "New" in lines and "vehicle" in lines:
            continue
        year = int(YEAR_TITLE_RE.match(lines[title_index]).group(1))
        title = lines[title_index]
        subtitle = ""
        if title_index + 1 < len(lines) and not lines[title_index + 1].startswith("$"):
            subtitle = lines[title_index + 1]
        prices = [
            int(m.group(1).replace(",", ""))
            for m in (AT_PRICE_RE.match(line) for line in lines)
            if m
        ]
        km = transmission = None
        for i, line in enumerate(lines):
            km_match = AT_KM_RE.match(line)
            if km_match:
                km = int(km_match.group(1).replace(",", ""))
                transmission = lines[i + 1] if i + 1 < len(lines) else ""
                break
        province = ""
        for line in reversed(lines):
            loc = AT_LOC_RE.search(line)
            if loc:
                province = loc.group(1)
                break
        seller = "private" if "Private seller" in lines else "dealer"
        if km is not None and km < 1000:
            continue
        comp = _make_comp(
            "autotrader", year, title, subtitle, min(prices) if prices else None,
            km, transmission or "", seller, province, seen,
        )
        if comp:
            comps.append(comp)
    return comps


def parse_autotrader_compact(text: str, seen: str) -> list:
    """Parse the pipe format: year|model|subtitle|price|km|transmission|P or D|province."""
    comps = []
    for line in text.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 8 or not parts[0].isdigit():
            continue
        year, model, subtitle, price, km, trans, seller, prov = parts
        if not price.isdigit() or not km.isdigit():
            continue
        if int(km) < 1000:
            continue
        comp = _make_comp(
            "autotrader", int(year), f"{year} {model}", subtitle, int(price), int(km),
            trans, "private" if seller == "P" else "dealer", prov, seen,
        )
        if comp:
            comps.append(comp)
    return comps


def comp_from_listing(listing, seen: str) -> Optional[Comp]:
    """Turn a Facebook listing into a comp, when it has enough detail."""
    if not (listing.model_match and listing.year and listing.price and listing.km):
        return None
    province = ""
    if "," in listing.location:
        province = listing.location.rsplit(",", 1)[1].strip().upper()
    comp = _make_comp(
        "facebook", listing.year, listing.title or f"{listing.year} {listing.model_match}",
        listing.description[:200], listing.price, listing.km, listing.transmission,
        listing.seller_type, province, seen,
    )
    if comp:
        comp.key = f"facebook:{listing.listing_id}"
    return comp


def usable(comp: Comp) -> bool:
    """Keep comps that look like normal running cars."""
    if comp.price < 5000:
        return False
    if re.search(SEVERE_PATTERN, comp.text or "", re.I):
        return False
    return True


class CompStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, comps: list) -> tuple:
        added = updated = 0
        for comp in comps:
            known = self.data.get(comp.key)
            if known is None:
                self.data[comp.key] = comp.to_dict()
                added += 1
                continue
            known["last_seen"] = max(known.get("last_seen", ""), comp.last_seen)
            history = known.setdefault("price_history", [])
            if not history or history[-1][1] != comp.price:
                history.append([comp.last_seen, comp.price])
            known["price"] = comp.price
            updated += 1
        return added, updated

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def recent(self, today: date, max_age_days: int) -> list:
        out = []
        for record in self.data.values():
            seen = record.get("last_seen") or record.get("first_seen") or ""
            try:
                seen_day = date.fromisoformat(seen[:10])
            except ValueError:
                continue
            if (today - seen_day).days > max_age_days:
                continue
            comp = Comp(**{k: v for k, v in record.items() if k in Comp.__dataclass_fields__})
            if usable(comp):
                out.append(comp)
        return out


def load_comp_file(path: Path, seen: str = "") -> list:
    if not seen:
        seen = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".psv":
        return parse_autotrader_compact(text, seen)
    return parse_autotrader_text(text, seen)
