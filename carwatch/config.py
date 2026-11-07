from __future__ import annotations

import tomllib
from pathlib import Path

from .valuation import VALUATION_DEFAULTS

DEFAULTS = {
    "search": {
        "budget_min": 15000,
        "budget_max": 22000,
        "min_year": 2013,
        "max_year": 2026,
        "models": ["GR86", "GT86", "Toyota 86", "BRZ", "FR-S"],
    },
    "location": {
        "allowed_provinces": ["BC"],
        "bc_cities": [
            "Victoria", "Saanich", "Langford", "Colwood", "Sidney", "Sooke",
            "Nanaimo", "Duncan", "Courtenay", "Comox", "Campbell River",
            "Vancouver", "Burnaby", "Richmond", "Surrey", "Delta", "Langley",
            "Coquitlam", "Abbotsford", "Chilliwack", "Kelowna", "Vernon",
            "Kamloops", "Penticton", "Prince George", "Nelson",
        ],
    },
    "email": {
        "gmail_query": "from:facebookmail.com newer_than:3d",
    },
    "valuation": dict(VALUATION_DEFAULTS),
}


def load_config(path: str | None = None) -> dict:
    """Load config.local.toml, falling back to config.example.toml, then defaults."""
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    if path:
        candidates = [Path(path)]
    else:
        candidates = [Path("config.local.toml"), Path("config.example.toml")]
    for candidate in candidates:
        if candidate.exists():
            with candidate.open("rb") as handle:
                user = tomllib.load(handle)
            for section, values in user.items():
                cfg.setdefault(section, {}).update(values)
            cfg["_path"] = str(candidate)
            break
    return cfg
