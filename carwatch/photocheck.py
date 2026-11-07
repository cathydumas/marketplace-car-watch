"""Findings from looking at a listing's photos.

The skill looks at each promising listing's photos and saves what it sees to
pages/<listing key>.photos.json:

  {
    "trim": "Sport-tech",              # trim the photos point to, or ""
    "trim_evidence": "navigation map, dual-zone AUTO climate, heated seat switches",
    "transmission": "automatic",       # manual, automatic, or ""
    "transmission_evidence": "paddle shifters, P shown in the gauge",
    "mods": ["aftermarket rear wing", "aftermarket wheels"],
    "concerns": ["dent on rear bumper"],
    "notes": "free text"
  }

The listing key is the Facebook item id, or <source>-<id> for other sites,
the same key the photos folder uses.

Photos can be stock images or of another car. Treat findings as evidence,
not proof, and say so where it matters.
"""
from __future__ import annotations

import json
from pathlib import Path

from .trims import detect_trim


def load_photo_checks(folder: Path) -> dict:
    checks = {}
    folder = Path(folder)
    if not folder.is_dir():
        return checks
    for path in sorted(folder.glob("*.photos.json")):
        key = path.name[: -len(".photos.json")]
        try:
            checks[key] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return checks


def apply_photo_check(listing, check: dict) -> None:
    """Fold photo findings into the listing after evaluate() has run."""
    if not check:
        return
    listing.photo_check = check
    trim = (check.get("trim") or "").strip()
    if trim:
        name, tier = detect_trim(trim, listing.make)
        if not name:
            name, tier = trim, "unknown"
        if listing.trim and listing.trim.lower() != name.lower():
            listing.flags.append(f"ad says {listing.trim} trim, photos suggest {name}")
        elif not listing.trim:
            listing.trim, listing.trim_tier = name, tier
            listing.positives.append(f"trim from photos: {name}")
    trans = (check.get("transmission") or "").strip().lower()
    if trans in ("manual", "automatic"):
        if listing.transmission and listing.transmission != trans:
            listing.flags.append(f"ad says {listing.transmission}, photos show {trans}")
        elif not listing.transmission:
            listing.transmission = trans
            listing.positives.append(f"{trans} confirmed in photos")
        else:
            listing.positives.append(f"{trans} confirmed in photos")
    mods = [m for m in check.get("mods") or [] if m]
    if mods:
        if "modified" not in listing.flags:
            listing.flags.append("modified")
        listing.flags.append("seen in photos: " + ", ".join(mods))
    for concern in check.get("concerns") or []:
        if concern:
            listing.flags.append(f"photos: {concern}")
