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
    # Filled in from a saved listing page, when there is one
    description: str = ""
    transmission: str = ""
    days_listed: Optional[int] = None
    seller_type: str = ""  # dealer, private, or ""
    # Filled in by trims and valuation
    make: str = ""
    generation: int = 0
    trim: str = ""
    trim_tier: str = "unknown"
    valuation: dict = field(default_factory=dict)
    call: str = ""
    call_reasons: list = field(default_factory=list)
    # Where the listing came from, other sites it is on, and their deal ratings
    source: str = "facebook"
    also_listed: list = field(default_factory=list)
    references: list = field(default_factory=list)
    flags_extra: list = field(default_factory=list)
    dealer_fees: int = 0

    def filled_fields(self) -> int:
        values = [self.title, self.price, self.location, self.year, self.km]
        return sum(1 for v in values if v not in ("", None))

    def to_dict(self) -> dict:
        return asdict(self)
