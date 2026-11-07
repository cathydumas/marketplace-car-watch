"""Work out make, generation, trim tier and transmission from listing text.

Facebook has no trim field, so trim comes from the title and description.
AutoTrader.ca usually puts the trim in the subtitle.

Trim tiers, not exact trim names, feed the value model:
  base     the entry trim
  upper    GT, Premium, Sport-tech, RS, Limited
  limited  numbered or special editions that collectors look for
  unknown  nothing in the text says which trim it is
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TOYOTA_MODELS = {"GR86", "GT86", "Toyota 86", "FR-S"}

# Special and limited editions. Checked before upper trims.
LIMITED_PATTERNS = [
    ("Hakone Edition", r"\bhakone\b"),
    ("Special Edition", r"\bspecial edition\b|\b860\b"),
    ("TRD Special Edition", r"\btrd\b"),
    ("Release Series", r"\brelease series\b|\brs ?[123]\.0\b"),
    ("10 Series", r"\b10 series\b|\b10th anniversary\b"),
    ("Trueno Edition", r"\btrueno\b"),
    ("Yuzu Edition", r"\byuzu\b"),
    ("tS", r"(?<![\w-])ts(?![\w-])"),
    ("Raiu Edition", r"\braiu\b"),
    ("Inazuma Edition", r"\binazuma\b"),
    ("Hikari Edition", r"\bhikari\b"),
    ("Aozora Edition", r"\baozora\b"),
    ("Series.Blue", r"\bseries\.?\s?(blue|gray|grey|yellow)\b"),
    ("Murasaki Edition", r"\bmurasaki\b"),
    ("Kaminari Edition", r"\bkaminari\b"),
]

UPPER_PATTERNS = [
    ("Sport-tech RS", r"\bsport[\s-]?tech\s+rs\b"),
    ("Sport-tech", r"\bsport[\s-]?tech\b"),
    ("RS", r"(?<![\w-])rs(?![\w-])"),
    ("Premium", r"\bpremium\b"),
    ("Limited", r"\blimited\b(?! production)(?! edition)"),
    ("GT", r"\bgt\b(?!\s?-?\s?86)"),
]

BASE_PATTERN = r"\bbase\b"

MANUAL_PATTERN = (
    r"\bmanual\b|\bmanuelle?\b|\b6\s?mt\b|\bm/t\b|\b6\s?-?\s?spd\s?(?:m|manual)\b|"
    r"\bstick\b|\bstick shift\b|\b(?:2dr )?cpe man\b|^man$|\bbm\b"
)
AUTO_PATTERN = (
    r"\bautomatic\b|\bautomatique\b|\ba/t\b|\b6\s?at\b|\bpaddle shift\w*|"
    r"\bcpe auto\b|\bcoupe automatic\b|^auto$|"
    r"\bauto\b(?!\s*(?:group|sales|lounge|centre|center|mall|body|parts|loan|financ|deal|jean|gabriel|corp|inc|ltd|world|plaza|source|pro|city))"
)


@dataclass
class Spec:
    make: str = ""            # toyota or subaru
    generation: int = 0       # 1 for 2013 to 2021, 2 for 2022 on, 0 if unknown
    trim: str = ""            # best trim name found, or ""
    trim_tier: str = "unknown"
    transmission: str = ""    # manual, automatic, or ""


def make_for(model: str) -> str:
    if not model:
        return ""
    return "toyota" if model in TOYOTA_MODELS else "subaru"


def generation_for(model: str, year) -> int:
    if year:
        return 2 if year >= 2022 else 1
    if model == "GR86":
        return 2
    if model in ("FR-S", "GT86", "Toyota 86"):
        return 1
    return 0


def detect_trim(text: str, make: str = "") -> tuple:
    blob = (text or "").lower()
    for name, pattern in LIMITED_PATTERNS:
        if name == "tS" and make == "toyota":
            continue
        if name == "TRD Special Edition" and make == "subaru":
            continue
        if re.search(pattern, blob, re.I | re.M):
            return name, "limited"
    for name, pattern in UPPER_PATTERNS:
        if name in ("Sport-tech", "Sport-tech RS", "RS", "Limited") and make == "toyota":
            continue
        if name == "GT" and make == "subaru":
            continue
        if re.search(pattern, blob, re.I | re.M):
            return name, "upper"
    if re.search(BASE_PATTERN, blob, re.I):
        return "Base", "base"
    return "", "unknown"


def detect_transmission(text: str) -> str:
    blob = (text or "").lower()
    manual = bool(re.search(MANUAL_PATTERN, blob, re.I | re.M))
    auto = bool(re.search(AUTO_PATTERN, blob, re.I | re.M))
    if manual and not auto:
        return "manual"
    if auto and not manual:
        return "automatic"
    return ""


def normalise_transmission(value: str) -> str:
    value = (value or "").strip().lower()
    if value.startswith("man"):
        return "manual"
    if value.startswith("auto"):
        return "automatic"
    return ""


def build_spec(model: str, year, text: str, transmission: str = "") -> Spec:
    make = make_for(model)
    trim, tier = detect_trim(text, make)
    trans = normalise_transmission(transmission) or detect_transmission(text)
    return Spec(
        make=make,
        generation=generation_for(model, year),
        trim=trim,
        trim_tier=tier,
        transmission=trans,
    )
