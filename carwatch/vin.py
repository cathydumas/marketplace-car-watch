"""VINs and ICBC's free vehicle status lookup.

Dealer ads often post the VIN, and sometimes it shows in a listing photo.
ICBC's free Vehicle Claims History search takes a VIN and model year and
returns the car's status on the B.C. registry: normal, rebuilt, salvage,
altered or non-repairable. A browser run saves results to
state/vin-status.json:

  {"JF1ZCAC15D1612628": {"year": 2013, "status": "normal", "checked": "2026-11-08"}}

A rebuilt, salvage, altered or non-repairable status makes the car's title
branded, even when the ad does not say so. "normal" counts as a clean title.
The status says nothing about accidents that did not brand the title: for
that, the buyer needs ICBC's paid claims report or a CARFAX report.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_VALUES = {**{str(d): d for d in range(10)},
           **dict(zip("ABCDEFGH", range(1, 9))), **dict(zip("JKLMN", range(1, 6))),
           "P": 7, "R": 9, **dict(zip("STUVWXYZ", range(2, 10)))}
_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
BRANDED_STATUSES = {"rebuilt", "salvage", "altered", "non-repairable"}


def valid_vin(vin: str) -> bool:
    """North American VIN with a correct check digit."""
    vin = (vin or "").upper()
    if not VIN_RE.fullmatch(vin) or not re.search(r"[A-Z]", vin):
        return False
    total = sum(_VALUES[c] * w for c, w in zip(vin, _WEIGHTS))
    check = total % 11
    return vin[8] == ("X" if check == 10 else str(check))


def find_vin(text: str) -> str:
    for match in VIN_RE.finditer((text or "").upper()):
        if valid_vin(match.group(0)):
            return match.group(0)
    return ""


def load_vin_status(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_vin(listing, statuses: dict, photo_vin: str = "") -> None:
    """Set listing.vin and fold ICBC's status into the listing text."""
    if not listing.vin:
        listing.vin = find_vin(" ".join([listing.title, listing.raw_text, listing.description])) or (
            photo_vin.upper() if valid_vin(photo_vin) else "")
    found = statuses.get(listing.vin) if listing.vin else None
    if not found:
        return
    status = (found.get("status") or "").lower()
    listing.vin_status = status
    if status in BRANDED_STATUSES:
        listing.raw_text = f"{listing.raw_text} ICBC registry status: {status}".strip()
    elif status == "normal" and "clean title" not in (listing.raw_text or "").lower():
        listing.raw_text = f"{listing.raw_text} Clean title (ICBC registry status normal)".strip()
