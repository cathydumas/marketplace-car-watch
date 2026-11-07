from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Listing:
    listing_id: str
    url: str
    title: str = ""
    price: Optional[int] = None
    location: str = ""
    year: Optional[int] = None
    km: Optional[int] = None
    source_email_id: str = ""
    email_date: str = ""
    raw_text: str = ""
    # Filled in by filters.evaluate
    model_match: str = ""
    province_status: str = "unknown"  # allowed, other, unknown
    flags: list = field(default_factory=list)
    positives: list = field(default_factory=list)
    # Filled in by the store
    status: str = "new"  # new, price_drop, seen
    prev_price: Optional[int] = None

    def filled_fields(self) -> int:
        values = [self.title, self.price, self.location, self.year, self.km]
        return sum(1 for v in values if v not in ("", None))

    def to_dict(self) -> dict:
        return asdict(self)
