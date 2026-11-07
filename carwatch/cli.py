from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import load_config
from .digest import render
from .filters import evaluate
from .parser import load_email, parse_email
from .store import Store

EMAIL_SUFFIXES = {".json", ".eml", ".html", ".htm", ".txt"}


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


def cmd_ingest(args) -> int:
    cfg = load_config(args.config)
    files = _email_files(Path(args.path))
    listings = _parse_all(files)

    kept, excluded = [], []
    for listing in listings:
        reason = evaluate(listing, cfg)
        if reason:
            excluded.append((listing, reason))
        else:
            kept.append(listing)

    store = Store(Path(args.data_dir) / "seen.json")
    store.annotate(kept)
    today = datetime.now().astimezone().date()
    text = render(kept, excluded, today, len(files))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{today.isoformat()}.md"
    out_file.write_text(text, encoding="utf-8")
    if not args.dry_run:
        store.commit(kept)

    new = sum(1 for l in kept if l.status == "new")
    drops = sum(1 for l in kept if l.status == "price_drop")
    print(
        f"emails={len(files)} parsed={len(listings)} kept={len(kept)} "
        f"new={new} price_drops={drops} filtered={len(excluded)}"
    )
    print(f"digest: {out_file}")
    if files and not listings:
        print(
            "WARNING: no Marketplace item links found in these emails. "
            "Run 'python -m carwatch inspect <file>' on one of them.",
            file=sys.stderr,
        )
    if args.dry_run:
        print("dry run: seen-listing memory was not updated")
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="carwatch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="parse saved emails and write a digest")
    ingest.add_argument("path", help="a folder of saved emails, or one file")
    ingest.add_argument("--config", default=None)
    ingest.add_argument("--data-dir", default="data")
    ingest.add_argument("--out-dir", default="digests")
    ingest.add_argument("--dry-run", action="store_true")
    ingest.set_defaults(func=cmd_ingest)

    inspect = sub.add_parser("inspect", help="show what the parser extracted")
    inspect.add_argument("path")
    inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args(argv)
    return args.func(args)
