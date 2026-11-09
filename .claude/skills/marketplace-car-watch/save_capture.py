"""Save fb_listing_capture.js results.

  python3 .claude/skills/marketplace-car-watch/save_capture.py <saved tool output>...

For each file, writes pages/<id>.txt (phone numbers removed),
photos/facebook-<id>.jpg (main photo) and sheets/<id>.jpg (a contact sheet of
all photos, for the photo check), and prints the start of the listing text.
Run from the repo root.
"""
import base64
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

PHONE = re.compile(r"(\+?1[\s.-]?)?\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?[\dO]{4}\b")
NOISE = re.compile(r"^\s*(\d+\s*)?(Unread Chats|Number of unread notifications|\d+\+?)\s*$")
dec = json.JSONDecoder()


def load(path):
    raw = json.loads(Path(path).read_text())
    text = raw[0]["text"] if isinstance(raw, list) else raw
    text = text.lstrip()
    if text.startswith('"'):
        text, _ = dec.raw_decode(text)
    data, _ = dec.raw_decode(text[text.index("{"):])
    return data


for name in ("pages", "photos", "sheets"):
    Path(name).mkdir(exist_ok=True)
for path in sys.argv[1:]:
    d = load(path)
    i = d["id"]
    lines = [PHONE.sub("[phone removed]", l) for l in d["text"].split("\n") if l.strip() and not NOISE.match(l.strip())]
    Path(f"pages/{i}.txt").write_text("\n".join(lines) + "\n")
    if d.get("main"):
        Path(f"photos/facebook-{i}.jpg").write_bytes(base64.b64decode(d["main"].split(",", 1)[1]))
    ims = [Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1]))) for u in d["photos"]]
    if ims:
        w = 240
        ims = [im.resize((w, int(im.height * w / im.width))) for im in ims]
        h = max(im.height for im in ims)
        cols = 5
        sheet = Image.new("RGB", (w * cols, h * ((len(ims) + cols - 1) // cols)), "white")
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * w, (k // cols) * h))
        sheet.save(f"sheets/{i}.jpg", quality=75)
    print(f"== {i} photos={len(ims)}\n{' '.join(lines)[:700]}\n")
