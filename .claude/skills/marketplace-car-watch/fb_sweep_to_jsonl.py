"""Turn the saved fb_sweep_dump.js result into a listings file.

  python3 .claude/skills/marketplace-car-watch/fb_sweep_to_jsonl.py <saved tool output> listings/facebook-<YYYY-MM-DD>.jsonl

Prints the runs log and how many cars were written. Keeps cards whose title
names a year and skips parts, toys and year ranges like "2017-2020". Run from the repo root.
"""
import json
import re
import sys
from pathlib import Path

# Year ranges like "2017-2020 BRZ" and these words mark parts, not cars.
# Words that also show up in real car ads (wheels, tires, exhaust, wing)
# are left out on purpose. The tool drops leftovers with no real price.
PARTS = re.compile(r"\b(parts? car|parts|grill|grille|oil pan|baffle|floor mats?|seat delete|diecast|1:\d\d)\b", re.I)

raw = Path(sys.argv[1]).read_text()
# The tool saves either the plain text or a JSON list of {type, text} parts,
# and the script's return value may itself be a JSON-encoded string.
try:
    data = json.loads(raw)
    if isinstance(data, list):
        raw = "".join(x.get("text", "") for x in data if isinstance(x, dict))
    elif isinstance(data, str):
        raw = data
except json.JSONDecodeError:
    pass
raw = raw.lstrip()
if raw.startswith('"'):
    raw = json.JSONDecoder().raw_decode(raw)[0]
if " runs\n" not in raw[:20]:
    sys.exit("no dump found in the file")
head, _, body = raw.partition("\n---\n")
body = body.split("\n---END---")[0]
print(head)
out = []
for line in body.splitlines():
    parts = [p.strip() for p in line.split(" | ")]
    if len(parts) < 4:
        continue
    item_id, searches, location = parts[0], parts[-1], parts[-2]
    rest = parts[1:-2]
    prices = [p for p in rest if re.fullmatch(r"(CA\$[\d,.]+|Free)", p)]
    title = " | ".join(p for p in rest if p not in prices)
    if not re.match(r"(19|20)\d\d ", title) and not re.search(r"\b(19|20)\d\d\b", title[:40]):
        continue
    if re.match(r"(19|20)\d\d\s*[-+/]", title) or PARTS.search(title):
        continue
    price = None
    if prices and prices[0] != "Free":
        price = int(float(prices[0][3:].replace(",", "")))
    out.append({
        "source": "facebook",
        "id": item_id,
        "url": f"https://www.facebook.com/marketplace/item/{item_id}/",
        "title": title,
        "price": price,
        "location": location,
        "found_by": ["search: " + q for q in searches.split(",") if q],
    })
Path(sys.argv[2]).write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out))
print(f"{len(out)} cars written to {sys.argv[2]}")
