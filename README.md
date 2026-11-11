# Marketplace car watch

Watches Facebook Marketplace alert emails for a Toyota GR86, Toyota 86, Subaru BRZ or Scion FR-S in BC. It values each car against real Canadian asking prices and says Buy, Offer $X or Pass. The aim is a car that holds its value, so it can be sold later without a big loss. A Claude Code skill runs it.

## How it works

1. Facebook emails you when a new listing matches a saved search.
2. The skill finds those emails in Gmail and saves them in `inbox/`.
3. A small Python program reads the emails and pulls out each listing.
4. It drops cars that are the wrong model, out of budget or outside BC.
5. If a browser is available, the skill also collects BC listings from AutoTrader.ca and Craigslist, and CarGurus.ca deal ratings. If the browser is signed in to Facebook, it also runs 12 Marketplace searches, each twice and with a 500 km radius, since Facebook shows a different set of cars on every load. It opens each promising listing and saves the page. That fills in km, transmission, the description and how long the car has been listed. Claude also looks at the photos of each promising car for trim, transmission, mods and damage, and saves what it saw in `state/photo-checks/` so the next run does not redo it.
6. The same car listed on several sites becomes one entry with all its links. If the km differs between sites, the digest says so.
7. The program works out the trim and values the car against comparable listings (comps) from AutoTrader.ca and Facebook.
8. It writes a digest with a call for each car, the other sites' ratings next to it, and a flip check: what the car should resell for after the hold period you set.
9. It remembers what it has shown you, so each digest lists only new listings and price drops.

## Status

This is an early version. The value model and the AutoTrader parser are tested on real listings captured in November 2026. The email parser has not been checked against a real Facebook alert email yet. Expect to tune it after the first real emails arrive. The skill has a step for that.

## What you need

- Claude Code installed
- Python 3.11 or newer
- Git
- The Gmail connector turned on in your Claude account, for the Gmail account that receives the alerts
- A Facebook account that can use Marketplace
- Optional but recommended: a browser Claude can use (Claude in Chrome or the built-in browser in the Claude desktop app). Without one, values are based on the email only, and AutoTrader comps need adding by hand.

## Setup

### 1. Get the code

```
git clone https://github.com/cathydumas/marketplace-car-watch.git
cd marketplace-car-watch
```

### 2. Make your config

```
cp config.example.toml config.local.toml
```

Open `config.local.toml` and set your budget, years and models. The `[valuation]` section sets how long you plan to keep the car and how many km you drive a year. This file is git-ignored. Your changes stay on your computer.

### 3. Set up Facebook alerts

Facebook's search is fuzzy. It returns a different handful of results for each wording and quietly drops listings that are a close match. Several narrow alerts catch far more than one broad one.

Create one alert for each of these searches. Open the link, tap the bell next to Filters, then tap Create alert. Leave the price blank. The tool filters on price itself.

- [GR86](https://www.facebook.com/marketplace/vancouver/search/?query=gr86&radius=500)
- [GT86](https://www.facebook.com/marketplace/vancouver/search/?query=gt86&radius=500)
- [Scion FRS](https://www.facebook.com/marketplace/vancouver/search/?query=scion%20frs&radius=500)
- [Scion FR-S](https://www.facebook.com/marketplace/vancouver/search/?query=scion%20fr-s&radius=500)
- [Subaru BRZ](https://www.facebook.com/marketplace/vancouver/search/?query=subaru%20brz&radius=500)
- [2017 Toyota 86](https://www.facebook.com/marketplace/vancouver/search/?query=2017%20toyota%2086&radius=500)
- [2018 Toyota 86](https://www.facebook.com/marketplace/vancouver/search/?query=2018%20toyota%2086&radius=500)
- [2019 Toyota 86](https://www.facebook.com/marketplace/vancouver/search/?query=2019%20toyota%2086&radius=500)
- [2020 Toyota 86](https://www.facebook.com/marketplace/vancouver/search/?query=2020%20toyota%2086&radius=500)

Search tips learned the hard way:

- Do not sort by newest. With `sortBy=creation_time_descend` Facebook ignores the search words and shows the newest listings of anything.
- Do not add a `make=` filter. The make IDs are not documented and a wrong one returns nothing.
- The 500 km radius from Vancouver reaches Vancouver Island and the Okanagan.

Then check where the emails go. In Facebook, open Settings, then Notifications. Make sure Marketplace has Email turned on. Under Email, the frequency setting matters. Suggested lets Facebook decide which alerts to email, so some may only show in the app. All emails every alert, but also turns on other email you will want to switch off. Start with Suggested. Switch to All if you see cars in the app that never reached your inbox.

### 4. Get the emails into Gmail

The alerts go to the email address on the Facebook account. If that is the Gmail account you connected to Claude, you are done. If not, set up a Gmail filter on the receiving account. Match mail from `facebookmail.com` and forward it to the Gmail address you connected to Claude. Gmail will ask you to confirm the forwarding address.

### 5. Load comparable listings

The value model needs at least 12 comps. Open Claude Code in this folder and say:

```
refresh the AutoTrader comps for the car watch
```

Claude opens AutoTrader.ca search pages for each model, saves the results to `comps/` and loads them. Check what it learned with:

```
python3 -m carwatch comps stats
```

### 6. Run it

Open Claude Code in this folder and say:

```
run the marketplace car watch
```

Claude reads your alert emails, fills in details from the listing pages, builds the digest and tells you which car to go after and what to offer.

To value one listing you found yourself, paste the link and ask Claude what it is worth.

## How the values work

There is no free Canadian blue book. Canadian Black Book now sells to dealers and lenders only. Kelley Blue Book's Canadian products are for businesses. Clutch.ca's free calculator gives a dealer buy price, well below what cars list for.

So the tool learns from real asking prices. It fits a simple model of price against age, km, transmission, generation (2013 to 2021 or 2022 on), trim tier and make. Trims are grouped into tiers:

- Base
- Upper: GT, Premium, Sport-tech, RS, Limited
- Limited editions: Hakone, Special Edition, 860, TRD, Release Series, 10 Series, tS, Raiu, Inazuma, Hikari, Aozora, Series.Blue, Murasaki, Kaminari, Trueno, Yuzu

Facebook has no trim field, so trim comes from the title and description. If the seller does not say, the car is valued as a typical mix and the digest says so.

Each car in the digest gets:

- Market: what similar cars ask, the usual range, and a likely sale price after haggling.
- Call: Buy when the asking price is well under similar cars. Offer $X when it is near market, with an opening number. Pass at this price when it is well over. Pass when the text mentions a blown engine, a rebuilt or salvage title, or similar.
- Flip check: what the car should resell for after your hold period, and the depreciation in between.

Mods, tunes, track use, accident history and out-of-province history lower the value. Long-listed cars get a lower suggested offer. When a dealer says its price does not include doc or prep fees, the tool adds them before comparing, and the suggested offer is the sticker number to open with.

CarGurus deal ratings and AutoTrader price badges show up as other ratings. They judge the asking price only, not condition, mods or fees. When they disagree with the tool, the digest says to look closer. Cars a little outside the budget (10% by default, `budget_stretch`) still show, flagged, since prices are negotiable.

The values are estimates. `comps stats` shows the typical error. Asking prices run higher than sale prices. Always get a vehicle history report and a pre-purchase inspection.

## Credentials

There are no passwords or tokens in this repo. Gmail access goes through your own Claude connector. Your settings live in `config.local.toml`. Saved emails, listing pages, other sites' listings, comps, digests and the seen-listings memory live in `inbox/`, `pages/`, `listings/`, `comps/`, `digests/` and `data/`. All of these are git-ignored. Two folders are committed on purpose: `history/` holds the daily AutoTrader search snapshots used for price trends, and `state/photo-checks/` holds only what Claude saw in listing photos, with no seller details.

## Commands

```
python3 -m carwatch ingest inbox              # build today's digest
python3 -m carwatch ingest inbox --listings listings   # include other sites
python3 -m carwatch ingest inbox --dry-run    # build it without updating memory
python3 -m carwatch inspect inbox             # show what the email parser read
python3 -m carwatch comps add comps           # load saved AutoTrader results
python3 -m carwatch comps stats               # summarise comps and the model
python3 -m carwatch value --model "Toyota 86" --year 2018 --km 80000 --price 19850
python3 -m carwatch trends --history history --out docs/data/trends.json   # monthly median prices
python3 -m carwatch site --data export --out docs   # rebuild the dashboard page
```

## Dashboard

The latest run is published at https://cathydumas.github.io/marketplace-car-watch/. To rebuild it after a run:

```
python3 -m carwatch ingest inbox --listings listings --export export
python3 -m carwatch site --data export --out docs
```

Commit `docs/` and GitHub Pages serves it. The page itself lives in `dashboard/index.html`. `site` wraps it with the data and writes `docs/index.html`, so edit `dashboard/index.html`, not the copy in `docs/`.

What the page shows:

- Four tiles: cars worth a look (Buy or Offer), with how many of those state a clean title, Buy calls, listings scanned and listings filtered out.
- Filters: All, Buy, Offer or Pass, a "Clean title only" toggle (on by default) and a km slider (120,000 km by default, all the way right for any km). A line under the filters says how many cars show and why the rest are hidden. Cars whose ad gives no km always show.
- A card for each priced car, with its photo, call, gap to market, market range, flip check, VIN check link and what Claude saw in the photos.
- A scatter of asking price against km. Grey dots are comparable listings across Canada. Today's BC cars are coloured by call: green Buy, orange Offer, grey Pass. A filled dot matches your filters and an empty ring is hidden by them. The shaded strip is the $15k to $22k budget and the dashed line is the km limit. Hover over a car for details, click it to open the listing.
- Listings scanned per site, why listings were dropped, which searches found each car, and dealer listings with no real price.

A month-by-month price trend chart was removed in November 2026, when there was too little history for it to say anything. `docs/data/trends.json` keeps building from the daily AutoTrader snapshots in `history/`. The plan is to bring it back as small sparklines once there are a few months of data.

The page shows listing photos and links from public listings. The repo is public, so anything in `docs/` is public too.

## Test it without Claude

```
python3 -m unittest discover -s tests -t .
```

The tests use real AutoTrader.ca listings and two real Facebook listing pages from November 2026, with seller names removed. The alert email samples in `tests/fixtures` are made up. They are not real Facebook emails.

## Update

```
git pull
```

Your `config.local.toml` and your saved data are not touched.

## Limits

- Without a saved listing page, the digest only holds what the alert email shows. Mileage and descriptions are often missing.
- Facebook can send alerts late. Delays from minutes to hours are common.
- Values come from asking prices, not sold prices.
- This does not check vehicle history or condition.
- Meta's terms of service do not cover automated access to Marketplace, and AutoTrader.ca's terms likely restrict automated collection. The skill reads pages in your own signed-in browser at a human pace, for personal use. It never messages sellers or changes anything. Keep it that way.
