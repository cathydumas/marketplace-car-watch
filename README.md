# Marketplace car watch

Watches Facebook Marketplace alert emails for a Toyota GR86, Toyota 86, Subaru BRZ or Scion FR-S in BC. It builds a short digest of new listings and price drops. A Claude Code skill runs it.

## How it works

1. Facebook emails you when a new listing matches a saved search.
2. The skill finds those emails in Gmail and saves them in `inbox/`.
3. A small Python program reads the emails and pulls out each listing.
4. It drops cars that are the wrong model, out of budget or outside BC.
5. It remembers what it has shown you, so each digest lists only new listings and price drops.

## Status

This is an early version. Nobody has checked it against a real Facebook alert email yet. The tests use synthetic samples. Expect to tune the parser after the first real emails arrive. The skill has a step for that.

## What you need

- Claude Code installed
- Python 3.11 or newer
- Git
- The Gmail connector turned on in your Claude account, for the Gmail account that receives the alerts
- A Facebook account that can use Marketplace

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

Open `config.local.toml` and set your budget, years and models. This file is git-ignored. Your changes stay on your computer.

### 3. Set up Facebook alerts

Create one alert for each model you want. Open Marketplace, search for the model, set the price range and the location, then look for the Notify Me bell near Filters. Turn on email for the alert. Facebook's menus change, so you may need to look around Settings, then Notifications, then Marketplace to find the email option.

Good searches to start with:

- Toyota GR86
- Toyota 86
- Subaru BRZ
- Scion FR-S

Marketplace searches one location at a time. Make an alert for each area you would drive to, such as Victoria, Vancouver and Kelowna.

### 4. Get the emails into Gmail

If your Facebook account uses the Gmail address you connected to Claude, you are done. If not, set up a Gmail filter on the receiving account. Match mail from `facebookmail.com` and forward it to the Gmail address you connected to Claude. Gmail will ask you to confirm the forwarding address.

### 5. Run it

Open Claude Code in this folder and say:

```
run the marketplace car watch
```

Claude will read your alert emails, save them to `inbox/`, build the digest and tell you what looks worth a look.

## Credentials

There are no passwords or tokens in this repo. Gmail access goes through your own Claude connector. Your settings live in `config.local.toml`. Saved emails, digests and the seen-listings memory live in `inbox/`, `digests/` and `data/`. All of these are git-ignored.

## Test it without Claude

```
python3 -m unittest discover -s tests -t .
python3 -m carwatch ingest tests/fixtures --dry-run
```

The first command runs the tests. The second builds a digest from the synthetic sample emails in `tests/fixtures`. Those samples are made up. They are not real Facebook emails.

## Check what the parser reads

```
python3 -m carwatch inspect inbox
```

This prints each listing the parser found and counts the fields it could not read. Use it when a digest looks thin or a listing is missing.

## Update

```
git pull
```

Your `config.local.toml` and your saved data are not touched.

## Limits

- The digest only holds what the alert email shows. Mileage and descriptions are often missing.
- Facebook can send alerts late. Delays from minutes to hours are common.
- This does not check vehicle history or condition. Get a history report and a pre-purchase inspection before you pay for anything.
- Meta's terms of service do not cover automated access to Marketplace. This project reads only emails sent to you. It does not touch Marketplace.
