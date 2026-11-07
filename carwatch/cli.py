from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from .comps import CompStore, comp_from_listing, load_comp_file
from .config import load_config
from .digest import render
from .fbpage import apply_page, load_pages
from .filters import MODEL_PATTERNS, SEVERE_LABEL, evaluate
from .models import Listing
from .parser import load_email, parse_email
from .export import write_export
from .sources import attach_references, load_listings, merge_duplicates
from .store import Store
from .valuation import ValueModel, appraise

EMAIL_SUFFIXES = {".json", ".eml", ".html", ".htm", ".txt"}
COMP_SUFFIXES = {".txt", ".psv"}


def _email_files(path: Path) -> list:
    if path.is_dir():
        return sorted(
            p for p in path.iterdir()
            if p.is_file() and p.suffix.lower() in EMAIL_SUFFIXES and not p.name.startswith(".")
        )
    return [path]


def _parse_all(files: list) -> list:
    best = {}
    for file in files:
        for listing in parse_email(load_email(file)):
            known = best.get(listing.listing_id)
            if known is None or listing.filled_fields() > known.filled_fields():
                best[listing.listing_id] = listing
    return list(best.values())


def _today():
    return datetime.now().astimezone().date()


def _value_model(cfg: dict, data_dir: Path, today) -> tuple:
    store = CompStore(data_dir / "comps.json")
    settings = cfg.get("valuation", {})
    max_age = settings.get("comps_max_age_days", 60)
    comps = store.recent(today, max_age)
    return store, ValueModel(comps, today, settings)


def cmd_ingest(args) -> int:
    cfg = load_config(args.config)
    data_dir = Path(args.data_dir)
    today = _today()
    files = _email_files(Path(args.path)) if args.path else []
    listings = _parse_all(files)
    references = []
    source_counts = Counter()
    for extra in args.listings or []:
        more, refs = load_listings(Path(extra))
        listings.extend(more)
        references.extend(refs)
        source_counts.update(l.source for l in more)
        source_counts.update(r.get("source", "other") for r in refs)

    pages = load_pages(Path(args.pages))
    for listing in listings:
        if listing.listing_id in pages:
            apply_page(listing, pages[listing.listing_id])

    # First pass sets the model so duplicates across sites can be matched.
    for listing in listings:
        evaluate(listing, cfg)
    listings = merge_duplicates(listings)
    attach_references(listings, references)

    kept, excluded = [], []
    for listing in listings:
        reason = evaluate(listing, cfg)
        if reason:
            excluded.append((listing, reason))
        else:
            kept.append(listing)

    comp_store, model = _value_model(cfg, data_dir, today)
    new_comps = []
    for listing in listings:
        if listing.flags and listing.flags[0] == SEVERE_LABEL:
            continue
        if listing.source == "autotrader":
            continue  # AutoTrader cars already come in through the comps refresh
        comp = comp_from_listing(listing, today.isoformat())
        if comp:
            new_comps.append(comp)
    for listing in kept:
        appraise(listing, model)

    store = Store(data_dir / "seen.json")
    store.annotate(kept)
    text = render(kept, excluded, today, len(files), model.n, dict(source_counts))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{today.isoformat()}.md"
    out_file.write_text(text, encoding="utf-8")
    if not args.dry_run:
        store.commit(kept)
        if new_comps:
            comp_store.add(new_comps)
            comp_store.save()

    new = sum(1 for l in kept if l.status == "new")
    drops = sum(1 for l in kept if l.status == "price_drop")
    print(
        f"emails={len(files)} parsed={len(listings)} kept={len(kept)} "
        f"new={new} price_drops={drops} filtered={len(excluded)} comps={model.n} "
        f"pages={len(pages)}"
    )
    print(f"digest: {out_file}")
    if files and not listings:
        print(
            "WARNING: no Marketplace item links found in these emails. "
            "Run 'python3 -m carwatch inspect <file>' on one of them.",
            file=sys.stderr,
        )
    min_comps = cfg.get("valuation", {}).get("min_comps", 12)
    if model.n < min_comps:
        print(
            f"WARNING: only {model.n} comps saved. Add AutoTrader.ca results with "
            "'python3 -m carwatch comps add <file>' to get value estimates.",
            file=sys.stderr,
        )
    if args.export:
        counts = write_export(
            Path(args.export), kept, excluded, model.comps, dict(source_counts),
            len(files), Path(args.photos), today,
        )
        print(f"export: {args.export} {counts}")
    if args.dry_run:
        print("dry run: seen-listing memory and comps were not updated")
    return 0


def cmd_inspect(args) -> int:
    files = _email_files(Path(args.path))
    result = []
    missing = {"title": 0, "price": 0, "location": 0, "year": 0, "km": 0}
    for file in files:
        listings = parse_email(load_email(file))
        for listing in listings:
            for key in missing:
                if getattr(listing, key) in ("", None):
                    missing[key] += 1
        result.append({"file": file.name, "listings": [l.to_dict() for l in listings]})
    total = sum(len(r["listings"]) for r in result)
    print(json.dumps({"total_listings": total, "missing_counts": missing, "emails": result}, indent=2))
    return 0


def cmd_comps_add(args) -> int:
    store = CompStore(Path(args.data_dir) / "comps.json")
    total_added = total_updated = 0
    for raw in args.paths:
        path = Path(raw)
        files = (
            sorted(p for p in path.iterdir() if p.suffix.lower() in COMP_SUFFIXES)
            if path.is_dir() else [path]
        )
        for file in files:
            comps = load_comp_file(file, args.seen or "")
            added, updated = store.add(comps)
            total_added += added
            total_updated += updated
            print(f"{file.name}: {len(comps)} comps read, {added} new, {updated} updated")
            if not comps:
                print(
                    f"WARNING: no comps found in {file.name}. Check it is AutoTrader.ca "
                    "results text or the extract script output.",
                    file=sys.stderr,
                )
    store.save()
    print(f"total comps saved: {len(store.data)} (+{total_added} new, {total_updated} updated)")
    return 0


def cmd_comps_stats(args) -> int:
    cfg = load_config(args.config)
    store, model = _value_model(cfg, Path(args.data_dir), _today())
    by_model = Counter(c.model for c in model.comps)
    by_tier = Counter(c.trim_tier for c in model.comps)
    print(f"saved comps: {len(store.data)}, recent and usable: {model.n}")
    print("by model: " + ", ".join(f"{k} {v}" for k, v in by_model.most_common()))
    print("by trim tier: " + ", ".join(f"{k} {v}" for k, v in by_tier.most_common()))
    print("model coefficients (log price):")
    for name, value in model.coefficients().items():
        print(f"  {name}: {value:+.4f}")
    print(f"typical error: about {round(model.sd * 100)}% of price")
    return 0


def cmd_value(args) -> int:
    """Value one car typed in by hand."""
    cfg = load_config(args.config)
    _, model = _value_model(cfg, Path(args.data_dir), _today())
    title = f"{args.year} {args.model}"
    listing = Listing(
        listing_id="manual",
        url=args.url or "",
        title=title,
        price=args.price,
        location=args.location or "",
        year=args.year,
        km=args.km,
        description=args.text or "",
        transmission=args.transmission or "",
        days_listed=args.days_listed,
    )
    cfg_any = dict(cfg)
    cfg_any["search"] = {**cfg["search"], "budget_min": 0, "budget_max": 10**9}
    evaluate(listing, cfg_any)
    listing.flags = [f for f in listing.flags if "not shown in the email" not in f]
    if not listing.model_match:
        print(f"Model not recognised. Use one of: {', '.join(MODEL_PATTERNS)}", file=sys.stderr)
        return 2
    appraise(listing, model)
    print(json.dumps(
        {
            "car": title,
            "trim": listing.trim or "not stated",
            "trim_tier": listing.trim_tier,
            "transmission": listing.transmission or "not stated",
            "call": listing.call,
            "reasons": listing.call_reasons,
            "valuation": listing.valuation,
            "flags": listing.flags,
        },
        indent=2,
    ))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="carwatch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="parse saved emails and write a digest")
    ingest.add_argument("path", nargs="?", help="a folder of saved emails, or one file")
    ingest.add_argument(
        "--listings", action="append",
        help="a .jsonl file or folder of listings from other sites. Can be repeated.",
    )
    ingest.add_argument("--config", default=None)
    ingest.add_argument("--data-dir", default="data")
    ingest.add_argument("--out-dir", default="digests")
    ingest.add_argument("--pages", default="pages", help="folder of saved listing pages")
    ingest.add_argument("--dry-run", action="store_true")
    ingest.add_argument("--export", help="folder to write dashboard data files to")
    ingest.add_argument("--photos", default="photos", help="folder of listing photos")
    ingest.set_defaults(func=cmd_ingest)

    inspect = sub.add_parser("inspect", help="show what the parser extracted")
    inspect.add_argument("path")
    inspect.set_defaults(func=cmd_inspect)

    comps = sub.add_parser("comps", help="manage comparable listings")
    comps_sub = comps.add_subparsers(dest="comps_cmd", required=True)
    add = comps_sub.add_parser("add", help="add AutoTrader.ca results files")
    add.add_argument("paths", nargs="+")
    add.add_argument("--data-dir", default="data")
    add.add_argument("--seen", default="", help="capture date, YYYY-MM-DD")
    add.set_defaults(func=cmd_comps_add)
    stats = comps_sub.add_parser("stats", help="summarise saved comps and the model")
    stats.add_argument("--config", default=None)
    stats.add_argument("--data-dir", default="data")
    stats.set_defaults(func=cmd_comps_stats)

    value = sub.add_parser("value", help="value one car by hand")
    value.add_argument("--model", required=True, help='for example "Toyota 86" or "BRZ"')
    value.add_argument("--year", type=int, required=True)
    value.add_argument("--km", type=int)
    value.add_argument("--price", type=int)
    value.add_argument("--transmission", choices=["manual", "automatic"])
    value.add_argument("--text", help="title or description, used for trim and red flags")
    value.add_argument("--location")
    value.add_argument("--days-listed", type=int)
    value.add_argument("--url")
    value.add_argument("--config", default=None)
    value.add_argument("--data-dir", default="data")
    value.set_defaults(func=cmd_value)

    args = parser.parse_args(argv)
    return args.func(args)
