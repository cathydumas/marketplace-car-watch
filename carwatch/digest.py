from __future__ import annotations

from collections import Counter


def _money(value) -> str:
    return "price not shown" if value is None else f"${value:,}"


def _entry(listing) -> str:
    price = _money(listing.price)
    if listing.status == "price_drop" and listing.prev_price is not None:
        price += f" (was {_money(listing.prev_price)})"
    details = []
    if listing.year:
        details.append(str(listing.year))
    if listing.km:
        details.append(f"{listing.km:,} km")
    lines = [
        f"### {listing.title or 'Untitled listing'}",
        f"- Price: {price}",
        f"- Where: {listing.location or 'not shown in the email'}",
        f"- Details: {', '.join(details) if details else 'year and km not shown'}",
        f"- Link: {listing.url}",
    ]
    if listing.flags:
        lines.append("- Watch for: " + ", ".join(listing.flags))
    if listing.positives:
        lines.append("- Good signs: " + ", ".join(listing.positives))
    return "\n".join(lines)


def render(kept: list, excluded: list, today, email_count: int) -> str:
    new = [l for l in kept if l.status == "new"]
    drops = [l for l in kept if l.status == "price_drop"]
    seen = [l for l in kept if l.status == "seen"]
    out = [f"# Car watch for {today.isoformat()}", ""]
    out.append(
        f"Read {email_count} alert emails. {len(kept)} listings match. "
        f"{len(new)} new, {len(drops)} price drops, {len(seen)} already reported."
    )
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
    return "\n".join(out)
