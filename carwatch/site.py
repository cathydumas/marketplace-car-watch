"""Build a static copy of the dashboard for GitHub Pages.

The dashboard page (dashboard/index.html) is written for the Claude
Dashboard artifact, which supplies a small `dash` runtime and theme tokens.
This module wraps the same page with a stand-in runtime that reads the
exported JSON files from data/, so it runs on any static host.

  python3 -m carwatch site --data export --out docs
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

DATASETS = ["listings", "photos", "comps", "sources", "filtered"]

HEAD = """<!doctype html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Car Watch</title>
<meta name="description" content="Daily BC listings for the Toyota GR86, Toyota 86, Subaru BRZ and Scion FR-S, valued against the market.">
<style>
:root {
  --font-anthropic-sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-anthropic-serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --cds-font-size-caption: .82rem; --cds-font-size-body: .95rem; --cds-font-size-heading: 1.1rem; --cds-font-size-title: 1.9rem;
  --cds-font-weight-medium: 600;
  --cds-gap-xs: .25rem; --cds-gap-sm: .5rem; --cds-gap-md: .75rem; --cds-gap-lg: 1rem; --cds-gap-xl: 1.75rem;
  --cds-pad-xs: .3rem; --cds-pad-sm: .6rem; --cds-pad-lg: 1rem;
  --cds-radius: 8px; --cds-dur-slow: 300ms;
  --color-bg: #f6f6f3; --color-panel: #ffffff; --color-fg: #17181a; --color-fg-muted: #5e6268; --color-border-line: #e2e2dc;
  --color-ok: #1f7a45; --color-warn: #9a5b00; --color-bad: #b42318;
  --cds-chart-muted: #c4c7cc; --cds-chart-grid: #ecece7; --cds-chart-axis: #b9bcc1;
  --cds-surface-popover: #ffffff; --cds-border: #dcdcd5; --cds-shadow-popover: 0 6px 20px rgba(0,0,0,.12); --cds-text-secondary: #5e6268;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #121314; --color-panel: #1c1d1f; --color-fg: #f1f1ee; --color-fg-muted: #a3a6ab; --color-border-line: #2f3134;
    --color-ok: #4cc27f; --color-warn: #e0a23b; --color-bad: #f0706a;
    --cds-chart-muted: #4a4d52; --cds-chart-grid: #26282b; --cds-chart-axis: #4a4d52;
    --cds-surface-popover: #232427; --cds-border: #3a3c40; --cds-shadow-popover: 0 6px 20px rgba(0,0,0,.5); --cds-text-secondary: #a3a6ab;
    color-scheme: dark;
  }
}
html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 15px; }
#dash-root { padding-block: 2rem 3rem; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.cw-foot { margin-top: 2rem; font-size: .8rem; color: var(--color-fg-muted); max-width: 78rem; margin-inline: auto; }
.cw-foot a { color: inherit; }
</style>
<script src="d3.min.js"></script>
<script>
(function () {
  var ids = __DATASETS__;
  var store = {}, calcs = {}, draws = [], listeners = [];
  ids.forEach(function (id) { store[id] = { status: 'loading', data: [] }; });
  function runCalc(id) {
    var c = calcs[id], ins = c.inputs.map(get);
    if (ins.some(function (x) { return x.status === 'error'; })) return { status: 'error', data: [] };
    if (ins.some(function (x) { return x.status !== 'ok'; })) return { status: 'loading', data: [] };
    try { return { status: 'ok', data: c.fn.apply(null, ins.map(function (x) { return x.data; })) }; }
    catch (e) { console.error(id, e); return { status: 'error', data: [] }; }
  }
  function get(id) { return store[id] || (calcs[id] ? runCalc(id) : { status: 'missing', data: [] }); }
  function redraw(only) {
    listeners.forEach(function (f) { try { f(); } catch (e) { console.error(e); } });
    draws.forEach(function (d) {
      if (only && d[0] !== only) return;
      document.querySelectorAll('[data-draw="' + d[0] + '"]').forEach(function (el) {
        try { d[1](el); } catch (e) { console.error(d[0], e); }
      });
    });
  }
  window.dash = {
    data: function (id) {
      var r = get(id), first = r.data && r.data[0];
      return { status: r.status, data: r.data, refreshing: false, meta: [], message: '', columns: first ? Object.keys(first) : [] };
    },
    calc: function (id, spec) { calcs[id] = spec; },
    loader: function () {},
    draw: function (name, fn) { if (fn) draws.push([name, fn]); else redraw(name); },
    onData: function (fn) { listeners.push(fn); },
    colors: ['#3b6fd8', '#1f8a4c', '#b26a00', '#9b3fb8', '#c2410c', '#0f766e', '#6b6f76', '#be123c'],
    params: function () { return {}; }, setParams: function () {}, resetParams: function () {},
    setLink: function () {}, refresh: function () {}
  };
  document.addEventListener('DOMContentLoaded', function () {
    redraw();
    Promise.all(ids.map(function (id) {
      return fetch('data/' + id + '.json?v=__BUILD__').then(function (r) { return r.json(); })
        .then(function (rows) { store[id] = { status: 'ok', data: rows }; })
        .catch(function () { store[id] = { status: 'error', data: [] }; });
    })).then(function () { redraw(); });
  });
  var t;
  window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(function () { redraw(); }, 150); });
})();
</script>
</head>
<body>
<div id="dash-root">
"""

FOOT = """
<p class="cw-foot">Updated __DATE__ from Facebook Marketplace, AutoTrader.ca, Craigslist and CarGurus.ca listings. Values are estimates from asking prices, not appraisals. Built with <a href="https://github.com/cathydumas/marketplace-car-watch">marketplace-car-watch</a>.</p>
</div>
</body>
</html>
"""


def build_site(dashboard_html: Path, data_dir: Path, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    for name in DATASETS:
        src = Path(data_dir) / f"{name}.json"
        if src.exists():
            shutil.copyfile(src, out_dir / "data" / f"{name}.json")
    page = Path(dashboard_html).read_text(encoding="utf-8")
    page = page.replace('<meta name="dash-one-writer">', "")
    date = datetime.now().astimezone().strftime("%B %-d, %Y")
    listings = Path(data_dir) / "listings.json"
    if listings.exists():
        rows = json.loads(listings.read_text(encoding="utf-8"))
        if rows and rows[0].get("date"):
            date = datetime.fromisoformat(rows[0]["date"]).strftime("%B %-d, %Y")
    build = datetime.now().strftime("%Y%m%d%H%M%S")
    html = HEAD.replace("__DATASETS__", json.dumps(DATASETS)).replace("__BUILD__", build) + page + FOOT.replace("__DATE__", date)
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    vendor = Path(__file__).parent / "vendor"
    shutil.copyfile(vendor / "d3.min.js", out_dir / "d3.min.js")
    shutil.copyfile(vendor / "d3-LICENSE.txt", out_dir / "d3-LICENSE.txt")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out
