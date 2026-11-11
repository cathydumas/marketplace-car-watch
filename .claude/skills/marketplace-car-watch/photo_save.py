"""Write photos/<key>.jpg from saved photo_dump.js results.

Usage: python3 photo_save.py <tool result file>... [--out photos]

Accepts the raw text, a JSON-encoded string, or the tool's saved
[{"type": "text", "text": ...}] list. A photo cut off by the device bridge
is skipped and named, so it can be fetched again.
"""
import base64, binascii, json, re, sys
from pathlib import Path

args = sys.argv[1:]
out = Path("photos")
if "--out" in args:
    i = args.index("--out")
    out = Path(args[i + 1])
    args = args[:i] + args[i + 2:]
out.mkdir(parents=True, exist_ok=True)


def texts(raw):
    try:
        val = json.loads(raw)
    except ValueError:
        return [raw]
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [x.get("text", "") if isinstance(x, dict) else str(x) for x in val]
    if isinstance(val, dict):
        return [val.get("text", "") or json.dumps(val)]
    return [raw]


saved, bad = 0, []
for f in args:
    for t in texts(Path(f).read_text(encoding="utf-8")):
        t = t.replace("\\n", "\n")
        for key, b64 in re.findall(r"((?:facebook|autotrader)-[0-9a-f-]+)\|data:image/jpeg;base64,([A-Za-z0-9+/=]+)", t):
            try:
                data = base64.b64decode(b64, validate=True)
            except binascii.Error:
                bad.append(key)
                continue
            if not data.endswith(b"\xff\xd9"):
                bad.append(key)
                continue
            (out / f"{key}.jpg").write_bytes(data)
            saved += 1
print(f"saved {saved} photos to {out}/")
if bad:
    print("cut off, fetch again: " + ", ".join(bad))
