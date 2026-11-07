"""Estimate what a car is worth and whether to buy it.

There is no free Canadian blue book, so the model learns from real asking
prices (comps). It fits log(price) against age, km, transmission,
generation, trim tier and make. Prior guesses keep the fit sensible when
comps are thin. Those guesses are ordinary depreciation rules of thumb, not
measured numbers, and the data overrides them as comps build up.

The output for each listing:
  fair asking price    what similar cars are listed for
  likely sale price    asking less a small haggle discount
  hold estimate        likely resale after the hold period, and the loss
  call                 Buy, Offer $X, or Pass, with reasons
"""
from __future__ import annotations

import math
from datetime import date

FEATURES = ["intercept", "age", "km_10k", "manual", "gen2", "upper", "limited", "toyota"]

# Prior coefficient guesses in log-price units, and how strongly to hold them.
PRIOR = {
    "intercept": (math.log(30000), 1e-4),
    "age": (-0.06, 3.0),
    "km_10k": (-0.025, 3.0),
    "manual": (0.04, 3.0),
    "gen2": (0.15, 3.0),
    "upper": (0.05, 3.0),
    "limited": (0.12, 3.0),
    "toyota": (0.0, 3.0),
}

# Price cuts for problems the comps do not capture.
FLAG_PENALTIES = {
    "accident or claim mentioned": 0.07,
    "tune or forced induction": 0.08,
    "modified": 0.05,
    "track or race use": 0.05,
    "possible out-of-province history": 0.03,
}

VALUATION_DEFAULTS = {
    "sale_discount": 0.05,
    "hold_years": 1.5,
    "km_per_year": 12000,
    "buy_threshold": 0.93,
    "pass_threshold": 1.10,
    "stale_days": 30,
    "min_comps": 12,
    "comps_max_age_days": 60,
}


def _solve(matrix, vector):
    """Gaussian elimination with partial pivoting. Small systems only."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        if abs(a[col][col]) < 1e-12:
            raise ValueError("singular matrix")
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))) / a[r][r]
    return x


class ValueModel:
    def __init__(self, comps: list, today: date, settings: dict):
        self.today = today
        self.settings = {**VALUATION_DEFAULTS, **(settings or {})}
        self.comps = comps
        self.n = len(comps)
        known_trans = [c for c in comps if c.transmission]
        self.manual_share = (
            sum(c.transmission == "manual" for c in known_trans) / len(known_trans)
            if known_trans else 0.7
        )
        known_tier = [c for c in comps if c.trim_tier != "unknown"]
        self.upper_share = (
            sum(c.trim_tier == "upper" for c in known_tier) / len(known_tier)
            if known_tier else 0.4
        )
        self.coef = [PRIOR[f][0] for f in FEATURES]
        self.sd = 0.15
        if comps:
            self._fit()

    def features(self, year, km, transmission, generation, trim_tier, make):
        if transmission == "manual":
            manual = 1.0
        elif transmission == "automatic":
            manual = 0.0
        else:
            manual = self.manual_share
        if trim_tier == "unknown":
            upper, limited = self.upper_share, 0.0
        else:
            upper = 1.0 if trim_tier == "upper" else 0.0
            limited = 1.0 if trim_tier == "limited" else 0.0
        return [
            1.0,
            float(self.today.year - year),
            km / 10000.0,
            manual,
            1.0 if generation == 2 else 0.0,
            upper,
            limited,
            1.0 if make == "toyota" else 0.0,
        ]

    def _fit(self):
        rows = [
            self.features(c.year, c.km, c.transmission, c.generation, c.trim_tier, c.make)
            for c in self.comps
        ]
        ys = [math.log(c.price) for c in self.comps]
        k = len(FEATURES)
        xtx = [[0.0] * k for _ in range(k)]
        xty = [0.0] * k
        for row, y in zip(rows, ys):
            for i in range(k):
                xty[i] += row[i] * y
                for j in range(k):
                    xtx[i][j] += row[i] * row[j]
        for i, name in enumerate(FEATURES):
            mean, strength = PRIOR[name]
            xtx[i][i] += strength
            xty[i] += strength * mean
        self.coef = _solve(xtx, xty)
        residuals = [y - self._dot(row) for row, y in zip(rows, ys)]
        dof = max(1, len(ys) - k)
        self.sd = max(0.05, math.sqrt(sum(r * r for r in residuals) / dof))

    def _dot(self, row):
        return sum(c * x for c, x in zip(self.coef, row))

    def predict(self, year, km, transmission="", generation=1, trim_tier="unknown", make=""):
        """Predicted asking price."""
        return math.exp(self._dot(self.features(year, km, transmission, generation, trim_tier, make)))

    def similar_count(self, year, generation, make) -> int:
        return sum(
            1 for c in self.comps
            if c.generation == generation and c.make == make and abs(c.year - year) <= 2
        )

    def typical_km(self, year) -> int:
        age = max(0.5, self.today.year - year + 0.5)
        return int(age * self.settings["km_per_year"])

    def coefficients(self) -> dict:
        return dict(zip(FEATURES, self.coef))


def _round_down(value: float, step: int = 250) -> int:
    return int(value // step * step)


def appraise(listing, model: ValueModel) -> None:
    """Fill listing.valuation, listing.call and listing.call_reasons."""
    s = model.settings
    reasons = []
    listing.valuation = {}
    if listing.flags and listing.flags[0].startswith("serious"):
        listing.call = "Pass"
        listing.call_reasons = ["serious mechanical or title problem in the text"]
        listing.valuation["score"] = -1.0
        return
    if not listing.year or not listing.make:
        listing.call = "Check details"
        listing.call_reasons = ["year or model not clear, so no value estimate"]
        listing.valuation["score"] = -0.5
        return
    if model.n < s["min_comps"]:
        listing.call = "Check details"
        listing.call_reasons = [
            f"only {model.n} comps saved, need {s['min_comps']}. Run the AutoTrader refresh."
        ]
        listing.valuation["score"] = -0.5
        return

    km = listing.km
    if km is None:
        km = model.typical_km(listing.year)
        reasons.append(f"km unknown, assumed {km:,} for the age")
    gen = listing.generation or (2 if listing.year >= 2022 else 1)
    ask = model.predict(listing.year, km, listing.transmission, gen, listing.trim_tier, listing.make)

    penalty = 0.0
    for flag in listing.flags:
        cut = FLAG_PENALTIES.get(flag)
        if cut:
            penalty += cut
            reasons.append(f"{flag}: about {int(cut * 100)}% off value")
    penalty = min(penalty, 0.25)
    adj_ask = ask * (1 - penalty)
    sale = adj_ask * (1 - s["sale_discount"])
    low, high = adj_ask * math.exp(-model.sd), adj_ask * math.exp(model.sd)

    future_ask = model.predict(
        listing.year, km + s["km_per_year"] * s["hold_years"], listing.transmission,
        gen, listing.trim_tier, listing.make,
    ) * (1 - penalty)
    # The car also gets older over the hold.
    future_ask *= math.exp(model.coefficients()["age"] * s["hold_years"])
    resale = future_ask * (1 - s["sale_discount"])

    similar = model.similar_count(listing.year, gen, listing.make)
    confidence = "high" if similar >= 8 else "medium" if similar >= 3 else "low"
    if listing.trim_tier == "unknown":
        reasons.append("trim not stated, valued as a typical mix")
    if not listing.transmission:
        reasons.append("transmission not stated")

    listing.valuation = {
        "fair_ask": round(adj_ask),
        "likely_sale": round(sale),
        "range": [round(low), round(high)],
        "comps": model.n,
        "similar_comps": similar,
        "confidence": confidence,
        "resale_after_hold": round(resale),
        "hold_years": s["hold_years"],
        "km_used": km,
    }

    if listing.price is None or listing.price < 2000:
        listing.call = "Check price"
        listing.call_reasons = reasons + [f"worth about ${round(sale):,} if it checks out"]
        listing.valuation["score"] = -0.2
        return

    price = listing.price
    ratio = price / adj_ask
    listing.valuation["ratio"] = round(ratio, 3)
    listing.valuation["score"] = round(1 - ratio, 3)
    offer = _round_down(sale)
    stale = listing.days_listed is not None and listing.days_listed >= s["stale_days"]
    if stale:
        offer = _round_down(sale * 0.97)
        reasons.append(f"listed about {listing.days_listed} days, room to negotiate")

    pct = abs(round((1 - ratio) * 100))
    if ratio <= s["buy_threshold"]:
        listing.call = "Buy"
        reasons.insert(0, f"asking is {pct}% under similar cars")
        buy_at = price
    elif ratio <= s["pass_threshold"]:
        if offer >= price:
            listing.call = "Buy"
            reasons.insert(0, "asking is about market")
            buy_at = price
        else:
            listing.call = f"Offer ${offer:,}"
            where = "under" if ratio < 1 else "over"
            reasons.insert(0, f"asking is {pct}% {where} similar cars")
            buy_at = offer
    else:
        listing.call = "Pass at this price"
        reasons.insert(0, f"asking is {pct}% over similar cars. Worth about ${offer:,}")
        buy_at = offer
    listing.valuation["buy_at"] = buy_at
    listing.valuation["hold_loss"] = round(buy_at - resale)
    listing.call_reasons = reasons
