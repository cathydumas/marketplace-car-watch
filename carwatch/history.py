"""Daily AutoTrader.ca snapshots and the month-over-month price trend.

A daily run saves each model's AutoTrader.ca results to
history/autotrader-<model>-<YYYY-MM-DD>.psv (the extract script's format).
The files are kept in the repo, so the history survives between runs.

trend_rows() turns the snapshots into one row per month and model group:
the median asking price, the median km and how many cars were listed.
A car seen on several days in a month counts once, at its last price.
"""
from __future__ import annotations

import re
from pathlib import Path
from statistics import median

from .comps import load_comp_file

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def file_date(path: Path) -> str:
    match = DATE_RE.search(path.name)
    return match.group(1) if match else ""


def group_for(comp) -> str:
    if comp.model in ("GR86",) or (comp.make == "toyota" and comp.generation == 2):
        return "GR86 (2022 on)"
    if comp.model == "BRZ" and comp.generation == 2:
        return "BRZ (2022 on)"
    if comp.model == "BRZ":
        return "BRZ (2013 to 2020)"
    return "Toyota 86 and FR-S (2013 to 2020)"


def load_history(folder: Path) -> list:
    """Every comp from every dated snapshot, with last_seen set to the file's date."""
    comps = []
    for path in sorted(Path(folder).glob("*.psv")) + sorted(Path(folder).glob("*.txt")):
        day = file_date(path)
        if not day:
            continue
        for comp in load_comp_file(path, day):
            comps.append(comp)
    return comps


def trend_rows(comps: list) -> list:
    latest = {}
    for comp in comps:
        month = comp.last_seen[:7]
        key = (month, comp.key)
        if key not in latest or comp.last_seen >= latest[key].last_seen:
            latest[key] = comp
    groups = {}
    for (month, _), comp in latest.items():
        if comp.price < 5000:
            continue
        groups.setdefault((month, group_for(comp)), []).append(comp)
    rows = []
    for (month, group), items in sorted(groups.items()):
        rows.append({
            "month": month,
            "group": group,
            "median_price": int(median(c.price for c in items)),
            "median_km": int(median(c.km for c in items)),
            "listings": len(items),
            "days": len({c.last_seen for c in items}),
        })
    return rows
