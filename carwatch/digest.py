from __future__ import annotations

from collections import Counter


def _money(value) -> str:
    return "price not shown" if value is None else f"${value:,}"


def _trim_line(listing) -> str:
    trim = listing.trim or "trim not stated"
    gearbox = listing.transmission or "transmission not stated"
    return f"{trim}, {gearbox}"


def _sentences(parts: list) -> str:
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        part = part[0].upper() + part[1:]
        out.append(part if part.endswith(".") else part + ".")
    return " ".join(out)


def _value_lines(listing) -> list:
    v = listing.valuation or {}
    lines = []
    if listing.call:
        lines.append(f"- Call: {_sentences([listing.call] + listing.call_reasons)}")
    if "fair_ask" in v:
        low, high = v["range"]
        lines.append(
            f"- Market: similar cars ask about ${v['fair_ask']:,} "
            f"(most between ${low:,} and ${high:,}). Likely sells near ${v['likely_sale']:,}. "
            f"Based on {v['comps']} comps, {v['similar_comps']} close matches, "
            f"{v['confidence']} confidence."
        )
    if "hold_loss" in v:
        months = int(round(v["hold_years"] * 12))
        lines.append(
            f"- Flip check: bought at ${v['buy_at']:,} and sold after {months} months, "
            f"expect about ${v['resale_after_hold']:,}. Depreciation about ${v['hold_loss']:,}, "
            "before tax, insurance and repairs."
        )
    return lines


def _entry(listing) -> str:
    price = _money(listing.price)
    if listing.status == "price_drop" and listing.prev_price is not None:
        price += f" (was {_money(listing.prev_price)})"
    details = []
    if listing.year:
        details.append(str(listing.year))
    if listing.km:
        details.append(f"{listing.km:,} km")
    if listing.days_listed is not None:
        details.append(f"listed about {listing.days_listed} days")
    if listing.seller_type:
        details.append(f"likely {listing.seller_type}")
    lines = [
        f"### {listing.title or 'Untitled listing'}",
        f"- Price: {price}",
        f"- Where: {listing.location or 'not shown in the email'}",
        f"- Details: {', '.join(details) if details else 'year and km not shown'}",
        f"- Trim: {_trim_line(listing)}",
    ]
    lines.extend(_value_lines(listing))
    lines.append(f"- Link: {listing.url}")
    if listing.flags:
        lines.append("- Watch for: " + ", ".join(listing.flags))
    if listing.positives:
        lines.append("- Good signs: " + ", ".join(listing.positives))
    return "\n".join(lines)


def _score(listing) -> float:
    return (listing.valuation or {}).get("score", 0.0)


def render(kept: list, excluded: list, today, email_count: int, comp_count: int = 0) -> str:
    new = sorted([l for l in kept if l.status == "new"], key=_score, reverse=True)
    drops = sorted([l for l in kept if l.status == "price_drop"], key=_score, reverse=True)
    seen = [l for l in kept if l.status == "seen"]
    out = [f"# Car watch for {today.isoformat()}", ""]
    out.append(
        f"Read {email_count} alert emails. {len(kept)} listings match. "
        f"{len(new)} new, {len(drops)} price drops, {len(seen)} already reported. "
        f"Values use {comp_count} comparable listings."
    )
    out.append("")
    picks = [l for l in new + drops if l.call == "Buy" or l.call.startswith("Offer")]
    if picks:
        best = max(picks, key=_score)
        out.append("## Best value today")
        out.append("")
        out.append(f"{best.title or 'Untitled listing'}: {best.call}. {best.url}")
        out.append("")
    out.append("## New listings")
    out.append("")
    out.append("\n\n".join(_entry(l) for l in new) if new else "Nothing new today.")
    out.append("")
    if drops:
        out.append("## Price drops")
        out.append("")
        out.append("\n\n".join(_entry(l) for l in drops))
        out.append("")
    if excluded:
        reasons = Counter(reason for _, reason in excluded)
        out.append("## Filtered out")
        out.append("")
        for reason, count in reasons.most_common():
            out.append(f"- {reason}: {count}")
        out.append("")
    out.append("## How to read the values")
    out.append("")
    out.append(
        "Values come from real asking prices on AutoTrader.ca and Facebook, not a blue book. "
        "A Buy means the asking price is well under similar cars. An Offer is a "
        "suggested opening number. Every car still needs a history report and a "
        "pre-purchase inspection."
    )
    out.append("")
    return "\n".join(out)
