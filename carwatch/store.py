from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class Store:
    """Remembers which listings were already reported, so each digest shows only new ones."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def annotate(self, listings: list) -> None:
        """Set status to new, price_drop or seen. Does not write to disk."""
        for listing in listings:
            record = self.data.get(listing.listing_id)
            if record is None:
                listing.status = "new"
            else:
                old = record.get("price")
                if old is not None and listing.price is not None and listing.price < old:
                    listing.status = "price_drop"
                    listing.prev_price = old
                else:
                    listing.status = "seen"

    def commit(self, listings: list) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for listing in listings:
            record = self.data.get(listing.listing_id, {"first_seen": now})
            record.update(
                {"price": listing.price, "title": listing.title, "last_seen": now}
            )
            self.data[listing.listing_id] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
