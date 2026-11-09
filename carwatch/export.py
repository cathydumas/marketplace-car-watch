"""Write the day's results as JSON files for a dashboard.

Files written to the export folder:
  listings.json   one row per car in the digest
  comps.json      the comparable listings the values came from
  sources.json    how many listings each site gave
  filtered.json   how many were dropped, and why
  photos.json     one row per car photo, as a data URL
  coverage.json   for each search or site, how many of today's cars it found
                  and how many no other search found

Photos are read from photos/<listing key>.jpg, where the key is the
listing id with ":" replaced by "-" (facebook-1234..., autotrader-<id>).
"""
from __future__ import annotations

import base64
import io
import json
from collections import Counter
from pathlib import Path

from .sources import source_name


def photo_key(listing) -> str:
    lid = listing.listing_id
    return lid.replace(":", "-") if ":" in lid else f"{listing.source}-{lid}"


def _lean(call: str) -> str:
    if call.startswith("Buy"):
        return "Buy"
    if call.startswith("Check it out"):
        return "Check it out"
    if call.startswith("Offer"):
        return "Offer"
    if call.startswith("Pass"):
        return "Pass"
    return "Check price"


def listing_row(listing) -> dict:
    v = listing.valuation or {}
    low, high = (v.get("range") or [None, None])[:2]
    return {
        "id": photo_key(listing),
        "title": listing.title,
        "year": listing.year,
        "model": listing.model_match,
        "trim": listing.trim or "",
        "transmission": listing.transmission or "",
        "km": listing.km,
        "price": listing.price,
        "dealer_fees": listing.dealer_fees or 0,
        "location": listing.location,
        "source": source_name(listing.source),
        "url": listing.url,
        "also_on": "; ".join(
            f"{source_name(o['source'])}|{o['url']}" for o in listing.also_listed if o.get("url")
        ),
        "days_listed": listing.days_listed,
        "found_by": "; ".join(listing.found_by),
        "found_count": len(listing.found_by),
        "title_status": listing.title_status,
        "vin": listing.vin,
        "vin_status": listing.vin_status,
        "carfax_url": listing.carfax_url,
        "photo_notes": "; ".join(
            x for x in (
                (listing.photo_check or {}).get("trim_evidence", ""),
                (listing.photo_check or {}).get("transmission_evidence", ""),
            ) if x
        ),
        "seller": listing.seller_type or "",
        "status": listing.status,
        "call": listing.call,
        "verdict": _lean(listing.call),
        "reasons": " | ".join(listing.call_reasons),
        "fair_ask": v.get("fair_ask"),
        "likely_sale": v.get("likely_sale"),
        "range_low": low,
        "range_high": high,
        "vs_market": None if v.get("ratio") is None else round(v["ratio"] - 1, 3),
        "confidence": v.get("confidence", ""),
        "buy_at": v.get("buy_at"),
        "resale": v.get("resale_after_hold"),
        "hold_loss": v.get("hold_loss"),
        "hold_months": int(round(v.get("hold_years", 1.5) * 12)),
        "score": v.get("score", 0),
        "flags": " | ".join(listing.flags),
        "positives": " | ".join(listing.positives),
        "ratings": " | ".join(
            sorted({f"{source_name(r['source'])}: {r['rating']}" for r in listing.references if r.get("rating")})
        ),
    }


def _photo_data_url(path: Path, width: int = 480) -> str:
    data = path.read_bytes()
    try:
        from PIL import Image  # optional

        image = Image.open(io.BytesIO(data)).convert("RGB")
        if image.width > width:
            image = image.resize((width, round(image.height * width / image.width)))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=72)
        data = buffer.getvalue()
    except Exception:
        pass
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def coverage_rows(kept: list) -> list:
    """How much each search or site adds, over the cars with a real price.

    A car that only one search found is the warning sign: one more blind spot
    in that search and it would have been missed.
    """
    cars = [l for l in kept if l.price and l.price >= 2000]
    found = Counter()
    only = Counter()
    for listing in cars:
        finders = set(listing.found_by)
        found.update(finders)
        if len(finders) == 1:
            only.update(finders)
    rows = [
        {"finder": f.replace("search: ", "Facebook search: "), "cars": n, "only_here": only.get(f, 0), "total": len(cars)}
        for f, n in found.most_common()
    ]
    return rows


def write_export(out_dir: Path, kept: list, excluded: list, comps: list,
                 source_counts: dict, email_count: int, photos_dir: Path, today) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted((listing_row(l) for l in kept), key=lambda r: -(r["score"] or 0))
    for row in rows:
        row["date"] = today.isoformat()
    (out_dir / "listings.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    comp_rows = [
        {
            "year": c.year, "model": c.model, "price": c.price, "km": c.km,
            "transmission": c.transmission, "trim_tier": c.trim_tier,
            "province": c.province, "source": source_name(c.source),
        }
        for c in comps
    ]
    (out_dir / "comps.json").write_text(json.dumps(comp_rows), encoding="utf-8")

    src = [{"site": source_name(s), "listings": n} for s, n in sorted(source_counts.items(), key=lambda kv: -kv[1])]
    if email_count:
        src.insert(0, {"site": "Facebook alert emails", "listings": email_count})
    (out_dir / "sources.json").write_text(json.dumps(src), encoding="utf-8")

    reasons = Counter(reason for _, reason in excluded)
    filtered = [{"reason": r, "listings": n} for r, n in reasons.most_common()]
    (out_dir / "filtered.json").write_text(json.dumps(filtered), encoding="utf-8")

    (out_dir / "coverage.json").write_text(json.dumps(coverage_rows(kept)), encoding="utf-8")

    photos = []
    photos_dir = Path(photos_dir)
    for row in rows:
        path = photos_dir / f"{row['id']}.jpg"
        if path.exists():
            photos.append({"id": row["id"], "photo": _photo_data_url(path)})
    (out_dir / "photos.json").write_text(json.dumps(photos), encoding="utf-8")
    return {"listings": len(rows), "comps": len(comp_rows), "photos": len(photos)}
