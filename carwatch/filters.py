from __future__ import annotations

import re

from .trims import build_spec

MODEL_PATTERNS = {
    "GR86": r"\bgr\s?-?\s?86\b",
    "GT86": r"\bgt\s?-?\s?86\b",
    "Toyota 86": r"\b(?:toyota|scion)\s+86\b",
    "BRZ": r"\bbrz\b",
    "FR-S": r"\bfr[\s-]?s\b",
}

OTHER_PROVINCES = {"AB", "SK", "MB", "ON", "QC", "NB", "NS", "PE", "PEI", "NL", "YT", "NT", "NU"}

# Problems that rule a car out as a flip. Also used to drop bad comps.
SEVERE_PATTERN = (
    r"\b(blown|seized)\s+(engine|motor)\b|\b(engine|motor)\s+(is\s+)?(blown|seized|dead)\b|"
    r"\bneeds?\s+(an?\s+)?(new\s+)?(engine|motor|transmission|trans|clutch)\b|"
    r"\bnot running\b|\bdoes ?n[o']t run\b|\bwon'?t start\b|\bno start\b|"
    r"\bspun bearing\b|\brod knock\b|\bparts car\b|\bfor parts\b|\bnon[- ]?runner\b"
)
SEVERE_LABEL = "serious mechanical or title problem"
PRICE_UNCLEAR_BELOW = 2000

# Title status. In BC a branded vehicle shows as Rebuilt, Salvage, Altered or
# Non-repairable in ICBC records. "Rebuilt engine" is not a title brand.
BRANDED_RE = re.compile(
    r"\b(salvage|salvaged|rebuilt|rebuild|branded|altered|non[- ]?repairable|flood)\s+"
    r"(title|status|vehicle|car|history|registration)\b|"
    r"\b(title|status|registration)\s*(is|:|-)?\s*(salvage|rebuilt|branded|altered|non[- ]?repairable)\b|"
    r"\b(previously|was|been)\s+(salvaged|rebuilt|written[- ]off|a write[- ]?off|declared a total loss)\b|"
    r"\bwrite[- ]?off\b|\bwritten[- ]off\b|\btotal loss\b|\bbranded\b|\bsalvage\b",
    re.I,
)
NEGATION_RE = re.compile(r"\b(no|not|never|non|without|isn't|is not|wasn't|zero)\b[\s\w-]{0,12}$", re.I)
CLEAN_RE = re.compile(
    r"\bclean (bc |ontario |alberta )?title\b|\btitle\s*(is|:|-)?\s*clean\b|\bnormal (status|title)\b|"
    r"\bclean carfax\b|\bclean history\b|\bnever been (rebuilt|salvaged|written off)\b|"
    r"\bno (salvage|rebuilt|branded|brand)\b|\bnot (a )?(salvage|rebuilt|write[- ]?off)\b",
    re.I,
)


def title_status(text: str) -> str:
    """Return "branded", "clean" or "unknown" from listing text."""
    text = text or ""
    for match in BRANDED_RE.finditer(text):
        before = text[max(0, match.start() - 24):match.start()]
        if NEGATION_RE.search(before):
            continue
        return "branded"
    if CLEAN_RE.search(text):
        return "clean"
    return "unknown"

# Titles that are parts, accessories or toys rather than a car.
PARTS_TITLE_RE = re.compile(
    r"\b(doors?|headlights?|tail ?lights?|nostril|bodykit|body kit|side skirts?|lip|wing|spoiler|"
    r"diffuser|mirror|bumper|hood|fender|seats?|wheels?|rims?|tires?|exhaust|header|intake|"
    r"swap kit|parts?|engine|motor|transmission|hot wheels|diecast|die-cast|autoart|model car|"
    r"1:\d\d|deck|stereo|radio|cover|mats?|key ?fob|emblem|badge)\b",
    re.I,
)
CAR_SIGNAL_RE = re.compile(r"\b(km|kms|kilometers|kilometres|manual|automatic|one owner|clean title)\b", re.I)

PAYMENT_RE = re.compile(r"\b(bi-?weekly|per month|/mo\b|monthly|weekly payments?|payments?)\b", re.I)
FEE_WORD_RE = re.compile(
    r"\$\s?([\d,]{2,6})\s*(?:\w+\s){0,2}?(?:documentation|doc|prep(?:aration)?|admin(?:istration)?|"
    r"processing|dealer|reconditioning|etch|protection)\s+fees?|"
    r"(?:documentation|doc|prep(?:aration)?|admin(?:istration)?|processing|dealer)\s+fees?\s*(?:of|:)?\s*\$?\s?([\d,]{2,6})",
    re.I,
)
FEE_EXCLUDED_RE = re.compile(
    r"\b(not include|does not include|do not include|excludes?|excluded|plus|subject to|on top|extra|additional)\b|\+\s*\$?",
    re.I,
)


def dealer_fees(text: str) -> int:
    """Add up dealer fees the text says are charged on top of the price."""
    total = 0
    for sentence in re.split(r"(?<=[.!?\n])\s+", text or ""):
        if re.search(r"\bincludes?\b", sentence, re.I) and not re.search(r"not include", sentence, re.I):
            continue
        for match in FEE_WORD_RE.finditer(sentence):
            amount = match.group(1) or match.group(2)
            value = int(amount.replace(",", ""))
            if 50 <= value <= 5000:
                total += value
    return total


def is_parts_listing(listing) -> bool:
    title = listing.title or ""
    if not PARTS_TITLE_RE.search(title):
        return False
    if CAR_SIGNAL_RE.search(title) or listing.km:
        return False
    return True

RED_FLAGS = [
    ("accident or claim mentioned", r"(?<!no )\b(accidents?|icbc claims?|collision|damaged?)\b"),
    (
        "tune or forced induction",
        r"(?<!sport[- ])(?<!sport )(?<!factory[- ])\b(tuned?|turbo|supercharg\w*|e-?tune|flashed)\b"
        r"(?!\s+suspension)(?!\s+chassis)",
    ),
    (
        "modified",
        r"\b(after\s?market|modified|mods|coilovers?|lowered|straight[- ]pipe|catless|downpipe|"
        r"cat[- ]?back|headers?|cold air intake|intake|wing|diffuser|side skirts|front lip|"
        r"swap|built motor|big turbo|wide ?body|stance|subwoofer|amp)\b",
    ),
    ("track or race use", r"\b(track|race|drift|autocross)\b"),
    ("sold as is or needs work", r"\b(mechanic special|needs work|as[- ]is|project)\b"),
    (
        "possible out-of-province history",
        r"\b(out[- ]of[- ]province|imported|"
        r"(alberta|ontario|saskatchewan|manitoba|quebec|prairie|east(ern)?|ab|on|qc)\s+(car|vehicle)|"
        r"(from|came from|brought from|originally from)\s+(alberta|ontario|saskatchewan|manitoba|quebec|back east|the east))\b",
    ),
]

POSITIVES = [
    ("one owner", r"\b(one|1|single)[- ]owner\b"),
    ("service records", r"\b(service|maintenance) (records|history)\b"),
    ("clean history", r"\b(clean carfax|no accidents?|no claims?)\b"),
    ("stock", r"\b(all stock|bone stock|completely stock|100% stock|unmodified|stock\b(?!\s*(#|no\b|number|num\b|:)))"),
    ("manual", r"\b(manual|stick shift|stick|6\s?mt|m/t)\b"),
    ("dealer serviced", r"\bdealer(ship)?[- ]serviced\b"),
]


def detect_model(listing, models: list) -> str:
    haystacks = [listing.title.lower()]
    if not listing.title:
        haystacks.append(listing.raw_text.lower())
    for haystack in haystacks:
        for name in models:
            pattern = MODEL_PATTERNS.get(name)
            if pattern and re.search(pattern, haystack, re.I):
                return name
    return ""


def classify_province(listing, cfg: dict) -> str:
    allowed = {p.upper() for p in cfg["location"]["allowed_provinces"]}
    code = ""
    if "," in listing.location:
        code = listing.location.rsplit(",", 1)[1].strip().upper().replace(".", "")
    if code in allowed:
        return "allowed"
    if code in OTHER_PROVINCES:
        return "other"
    if not listing.location:
        blob = f"{listing.title} {listing.raw_text}".lower()
        for city in cfg["location"].get("bc_cities", []):
            if city.lower() in blob and "BC" in allowed:
                return "allowed"
    return "unknown"


def evaluate(listing, cfg: dict) -> str:
    """Fill in derived fields. Return an exclusion reason, or an empty string to keep."""
    search = cfg["search"]
    blob = " ".join(
        [listing.title, listing.location, listing.raw_text, listing.description]
    ).lower()
    listing.model_match = detect_model(listing, search["models"])
    listing.province_status = classify_province(listing, cfg)
    listing.flags = [label for label, pat in RED_FLAGS if re.search(pat, blob, re.I)]
    if re.search(SEVERE_PATTERN, blob, re.I):
        listing.flags.insert(0, SEVERE_LABEL)
    listing.positives = [label for label, pat in POSITIVES if re.search(pat, blob, re.I)]
    listing.title_status = title_status(blob)
    if listing.title_status == "branded":
        listing.flags.insert(0, "rebuilt, salvage or branded title")
    elif listing.title_status == "clean":
        listing.positives.insert(0, "clean title (seller says)")
    else:
        listing.flags.append("title status not stated")

    spec = build_spec(
        listing.model_match, listing.year,
        f"{listing.title}\n{listing.description or listing.raw_text}",
        listing.transmission,
    )
    listing.make = spec.make
    listing.generation = spec.generation
    listing.trim = spec.trim
    listing.trim_tier = spec.trim_tier
    listing.transmission = spec.transmission

    listing.dealer_fees = dealer_fees(listing.description or listing.raw_text)
    if listing.dealer_fees:
        listing.flags.append(f"dealer fees of about ${listing.dealer_fees:,} on top of the price")
    listing.flags.extend(listing.flags_extra)

    if not listing.model_match:
        return "not a target model"
    if is_parts_listing(listing):
        return "parts or accessories, not a car"
    title_rule = search.get("title", "no_branded")
    if listing.title_status == "branded" and title_rule in ("no_branded", "clean_only"):
        return "rebuilt, salvage or branded title"
    if listing.title_status == "unknown" and title_rule == "clean_only":
        return "title status not stated"
    if listing.year and not (search["min_year"] <= listing.year <= search["max_year"]):
        return "year out of range"
    if listing.price is not None:
        if listing.price < PRICE_UNCLEAR_BELOW:
            if PAYMENT_RE.search(listing.description or listing.raw_text or ""):
                listing.flags.append("price shown is a payment, not the car price")
            else:
                listing.flags.append("price unclear, check the listing")
        else:
            stretch = search.get("budget_stretch", 0.10)
            low = search["budget_min"] * (1 - stretch)
            high = search["budget_max"] * (1 + stretch)
            if listing.price < low:
                return "under budget range"
            if listing.price > high:
                return "over budget"
            if listing.price < search["budget_min"]:
                listing.flags.append("under your budget range, check why it is cheap")
            elif listing.price > search["budget_max"]:
                listing.flags.append("over budget, only worth it if the seller comes down")
    if listing.province_status == "other":
        return "outside allowed provinces"
    if listing.province_status == "unknown":
        listing.flags.append("location not shown in the email")
    if listing.price is None:
        listing.flags.append("price not shown in the email")
    return ""
