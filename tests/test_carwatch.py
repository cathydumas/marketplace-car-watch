import tempfile
import unittest
from datetime import date
from pathlib import Path

from carwatch.cli import main
from carwatch.comps import CompStore, load_comp_file
from carwatch.config import load_config
from carwatch.fbpage import apply_page, load_pages
from carwatch.filters import dealer_fees, evaluate, title_status
from carwatch.sources import attach_references, load_listings, merge_duplicates
from carwatch.models import Listing
from carwatch.photocheck import apply_photo_check
from carwatch.history import load_history, trend_rows
from carwatch.parser import load_email, parse_email
from carwatch.store import Store
from carwatch.trims import detect_transmission, detect_trim
from carwatch.valuation import ValueModel, appraise

FIXTURES = Path(__file__).parent / "fixtures"


def parsed_cards():
    return {l.listing_id: l for l in parse_email(load_email(FIXTURES / "synthetic_cards.html"))}


class ParserTests(unittest.TestCase):
    def test_finds_every_item_including_redirect_wrapped(self):
        ids = set(parsed_cards())
        self.assertEqual(len(ids), 6)
        self.assertIn("5555555555555555", ids)

    def test_footer_text_does_not_leak_into_last_card(self):
        last = parsed_cards()["5555555555555555"]
        self.assertNotIn("Unsubscribe", last.raw_text)

    def test_fields_for_plain_card(self):
        listing = parsed_cards()["1111111111111111"]
        self.assertEqual(listing.title, "2015 Subaru BRZ Premium")
        self.assertEqual(listing.price, 18500)
        self.assertEqual(listing.location, "Victoria, BC")
        self.assertEqual(listing.year, 2015)

    def test_km_and_two_prices(self):
        cards = parsed_cards()
        self.assertEqual(cards["2222222222222222"].km, 62000)
        self.assertEqual(cards["5555555555555555"].price, 17250)

    def test_text_email_with_markdown_link(self):
        listings = parse_email(load_email(FIXTURES / "synthetic_text_alert.txt"))
        self.assertEqual(len(listings), 1)
        listing = listings[0]
        self.assertEqual(listing.title, "2016 Scion FR-S Monogram")
        self.assertEqual(listing.price, 16800)
        self.assertEqual(listing.location, "Nanaimo, BC")
        self.assertEqual(listing.km, 105000)

    def test_email_with_no_item_links(self):
        self.assertEqual(parse_email({"id": "x", "html": "<p>Hello</p>", "text": ""}), [])


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(None)
        self.cards = parsed_cards()

    def reason(self, item_id):
        return evaluate(self.cards[item_id], self.cfg)

    def test_keeps_in_budget_bc_targets(self):
        for item_id in ("1111111111111111", "2222222222222222"):
            self.assertEqual(self.reason(item_id), "", item_id)

    def test_rebuilt_title_is_dropped(self):
        self.assertEqual(self.reason("5555555555555555"), "rebuilt, salvage or branded title")

    def test_excludes_other_province(self):
        self.assertEqual(self.reason("3333333333333333"), "outside allowed provinces")

    def test_excludes_over_budget(self):
        self.assertEqual(self.reason("4444444444444444"), "over budget")

    def test_excludes_other_models(self):
        self.assertEqual(self.reason("6666666666666666"), "not a target model")

    def test_flags_and_positives(self):
        self.reason("5555555555555555")
        self.reason("2222222222222222")
        flags = self.cards["5555555555555555"].flags
        self.assertIn("rebuilt, salvage or branded title", flags)
        self.assertIn("tune or forced induction", flags)
        self.assertIn("modified", flags)
        positives = self.cards["2222222222222222"].positives
        self.assertIn("one owner", positives)
        self.assertIn("service records", positives)

    def test_no_accidents_is_not_a_red_flag(self):
        listing = parse_email(
            {"id": "a", "text": "[2016 Subaru BRZ](https://facebook.com/marketplace/item/9999999999/) $17,000 Victoria, BC no accidents"}
        )[0]
        evaluate(listing, self.cfg)
        self.assertNotIn("accident or claim mentioned", listing.flags)
        self.assertIn("clean history", listing.positives)


class StoreAndCliTests(unittest.TestCase):
    def test_second_run_reports_nothing_new_then_price_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = [
                "ingest", str(FIXTURES / "synthetic_cards.html"),
                "--data-dir", f"{tmp}/data", "--out-dir", f"{tmp}/digests",
            ]
            self.assertEqual(main(args), 0)
            store = Store(Path(tmp) / "data" / "seen.json")
            self.assertEqual(len(store.data), 2)

            cards = list(parsed_cards().values())
            kept = []
            for listing in cards:
                if not evaluate(listing, load_config(None)):
                    kept.append(listing)
            store.annotate(kept)
            self.assertTrue(all(l.status == "seen" for l in kept))

            kept[0].price -= 1000
            store.annotate(kept)
            self.assertEqual(kept[0].status, "price_drop")
            self.assertEqual(kept[0].prev_price, kept[0].price + 1000)

    def test_digest_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            main([
                "ingest", str(FIXTURES), "--data-dir", f"{tmp}/data",
                "--out-dir", f"{tmp}/digests", "--dry-run",
            ])
            files = list((Path(tmp) / "digests").glob("*.md"))
            self.assertEqual(len(files), 1)
            text = files[0].read_text(encoding="utf-8")
            self.assertIn("2015 Subaru BRZ Premium", text)
            self.assertIn("2016 Scion FR-S Monogram", text)
            self.assertNotIn("Calgary", text)
            self.assertFalse((Path(tmp) / "data" / "seen.json").exists())


COMPS = FIXTURES / "comps"
PAGES = FIXTURES / "pages"
TODAY = date(2026, 11, 7)


def real_comps():
    comps = []
    for path in sorted(COMPS.iterdir()):
        comps.extend(load_comp_file(path, "2026-11-07"))
    return comps


def hand_listing(model, year, km=None, price=None, text="", transmission="", days=None, location="Kelowna, BC"):
    listing = Listing(
        listing_id="x", url="", title=f"{year} {model}", price=price, location=location,
        year=year, km=km, description=text, transmission=transmission, days_listed=days,
    )
    cfg = load_config(None)
    cfg["search"] = {**cfg["search"], "budget_min": 0, "budget_max": 10**9}
    evaluate(listing, cfg)
    return listing


class TrimTests(unittest.TestCase):
    def test_trims(self):
        self.assertEqual(detect_trim("2019 Toyota 86 GT 6M", "toyota"), ("GT", "upper"))
        self.assertEqual(detect_trim("2018 Toyota GT86", "toyota"), ("", "unknown"))
        self.assertEqual(detect_trim("2020 BRZ Sport-tech RS Manual", "subaru"), ("Sport-tech RS", "upper"))
        self.assertEqual(detect_trim("2018 BRZ tS / 6-Speed", "subaru"), ("tS", "limited"))
        self.assertEqual(detect_trim("2020 86 Hakone Edition GT", "toyota"), ("Hakone Edition", "limited"))
        self.assertEqual(detect_trim("2017 Toyota 86 BASE", "toyota"), ("Base", "base"))

    def test_transmission(self):
        self.assertEqual(detect_transmission("6 SPD M/T"), "manual")
        self.assertEqual(detect_transmission("2dr Cpe Auto"), "automatic")
        self.assertEqual(detect_transmission("Skyline Auto Group, manual"), "manual")
        self.assertEqual(detect_transmission("6-speed"), "")


class CompTests(unittest.TestCase):
    def test_autotrader_page_text(self):
        comps = load_comp_file(COMPS / "autotrader_toyota86_page.txt", "2026-11-07")
        self.assertEqual(len(comps), 19)  # the new 2027 is skipped
        first = comps[0]
        self.assertEqual((first.year, first.price, first.km), (2017, 22450, 24933))
        self.assertEqual(first.trim_tier, "limited")
        self.assertEqual(first.province, "ON")
        private = [c for c in comps if c.seller_type == "private"]
        self.assertEqual(len(private), 6)

    def test_autotrader_compact(self):
        comps = load_comp_file(COMPS / "autotrader_2026-11-07.psv", "2026-11-07")
        self.assertEqual(len(comps), 121)
        self.assertEqual({c.model for c in comps}, {"BRZ", "GR86", "FR-S"})

    def test_store_tracks_price_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CompStore(Path(tmp) / "comps.json")
            comps = real_comps()
            self.assertEqual(store.add(comps), (len(comps), 0))
            comps[0].price -= 500
            comps[0].last_seen = "2026-11-14"
            store.add(comps[:1])
            record = store.data[comps[0].key]
            self.assertEqual(len(record["price_history"]), 2)


class PageTests(unittest.TestCase):
    def test_vehicle_page(self):
        page = load_pages(PAGES)["1775877630223040"]
        self.assertEqual(page["price"], 22889)
        self.assertEqual(page["km"], 65000)
        self.assertEqual(page["transmission"], "manual")
        self.assertEqual(page["days_listed"], 49)
        self.assertEqual(page["location"], "Vancouver, BC")
        self.assertEqual(page["seller_type"], "dealer")

    def test_general_item_page_blown_engine(self):
        listing = Listing(listing_id="3021502318197351", url="")
        apply_page(listing, load_pages(PAGES)["3021502318197351"])
        self.assertEqual(listing.km, 130000)
        self.assertEqual(listing.year, 2014)
        cfg = load_config(None)
        evaluate(listing, cfg)
        self.assertEqual(listing.flags[0], "serious mechanical or title problem")


class ValuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = ValueModel(real_comps(), TODAY, {})

    def test_fit_is_sensible(self):
        coef = self.model.coefficients()
        self.assertLess(coef["age"], 0)
        self.assertLess(coef["km_10k"], 0)
        self.assertLess(self.model.sd, 0.25)
        value = self.model.predict(2018, 80000, "manual", 1, "unknown", "toyota")
        self.assertTrue(16000 < value < 23000, value)

    def test_fair_listing_gets_offer(self):
        listing = hand_listing("Toyota 86", 2018, 80000, 19850)
        appraise(listing, self.model)
        self.assertTrue(listing.call.startswith("Offer $"), listing.call)
        self.assertGreater(listing.valuation["hold_loss"], 0)

    def test_overpriced_listing_passes(self):
        listing = hand_listing("Toyota 86", 2018, 65000, 22889, transmission="manual", days=49)
        appraise(listing, self.model)
        self.assertEqual(listing.call, "Pass at this price")

    def test_cheap_listing_is_buy(self):
        listing = hand_listing("FR-S", 2014, 72500, 13500, transmission="manual", text="Base, one owner")
        appraise(listing, self.model)
        self.assertEqual(listing.call, "Buy")

    def test_cheap_listing_with_no_details_is_a_lead(self):
        listing = hand_listing("FR-S", 2014, 72500, 13500, transmission="manual")
        appraise(listing, self.model)
        self.assertEqual(listing.call, "Check it out")

    def test_dealer_fees_raise_the_compared_price(self):
        text = "All advertised vehicle prices do not include our $695 Documentation Fee, $295 Preparation fee, $10 VSA transaction levy or $1295 finance fees(if applicable)."
        listing = hand_listing("BRZ", 2013, 72537, 14500, transmission="manual", text=text)
        self.assertEqual(listing.dealer_fees, 990)
        appraise(listing, self.model)
        self.assertIn("compared at $15,490 including dealer fees", listing.call_reasons)

    def test_blown_engine_passes(self):
        listing = hand_listing("BRZ", 2014, 130000, 6000, text="HAS BLOWN ENGINE")
        appraise(listing, self.model)
        self.assertEqual(listing.call, "Pass")

    def test_flags_lower_value(self):
        clean = hand_listing("BRZ", 2017, 80000, 18000, transmission="manual")
        tuned = hand_listing("BRZ", 2017, 80000, 18000, text="tuned, coilovers", transmission="manual")
        appraise(clean, self.model)
        appraise(tuned, self.model)
        self.assertLess(tuned.valuation["fair_ask"], clean.valuation["fair_ask"])

    def test_needs_comps(self):
        listing = hand_listing("BRZ", 2017, 80000, 18000)
        appraise(listing, ValueModel([], TODAY, {}))
        self.assertEqual(listing.call, "Check details")

    def test_placeholder_price_is_kept_and_flagged(self):
        listing = Listing(
            listing_id="y", url="", title="2016 Subaru BRZ", price=1, location="Victoria, BC", year=2016
        )
        self.assertEqual(evaluate(listing, load_config(None)), "")
        self.assertIn("price unclear, check the listing", listing.flags)


class FilterDetailTests(unittest.TestCase):
    def test_fees_included_in_price_are_not_counted(self):
        text = ("Advertised price includes Vehicle Preparation ($695: safety inspection) and Deal Processing ($595). "
                "Advertised price excludes the $10 VSA Transaction Levy.")
        self.assertEqual(dealer_fees(text), 0)
        self.assertEqual(dealer_fees("Price Subject to Tax and Doc Fee of 695"), 695)

    def test_parts_listings_are_filtered(self):
        for title in ("2022 SUBARU BRZ DOORS", "Subaru BRZ Headlight Nostril", "2015 BRZ fa20 engine",
                      "Hot wheels Subaru BRZ, Toyota GR86 CUP", "AutoArt Rocket Bunny Toyota 86"):
            listing = Listing(listing_id="p", url="", title=title, price=500, location="Surrey, BC")
            self.assertEqual(evaluate(listing, load_config(None)), "parts or accessories, not a car", title)

    def test_payment_price_is_flagged(self):
        listing = hand_listing("GR86", 2023, 39645, 263, text="$0 Down low as $262.91 biweekly for 84 months")
        self.assertIn("price shown is a payment, not the car price", listing.flags)

    def test_budget_stretch(self):
        cfg = load_config(None)
        near = Listing(listing_id="a", url="", title="2018 Toyota 86", price=22889, location="Surrey, BC", year=2018)
        far = Listing(listing_id="b", url="", title="2023 Subaru BRZ", price=29995, location="Surrey, BC", year=2023)
        self.assertEqual(evaluate(near, cfg), "")
        self.assertIn("over budget, only worth it if the seller comes down", near.flags)
        self.assertEqual(evaluate(far, cfg), "over budget")

    def test_flag_wording_traps(self):
        listing = hand_listing("GR86", 2023, 39645, 30000,
                               text="sport-tuned suspension, Stock #: NLB68450, 6-Speed Automatic")
        self.assertNotIn("tune or forced induction", listing.flags)
        self.assertNotIn("stock", listing.positives)
        self.assertNotIn("manual", listing.positives)
        modded = hand_listing("Toyota 86", 2020, 48000, 20500, text="after market Exhust and cold air intake")
        self.assertIn("modified", modded.flags)


class TitleTests(unittest.TestCase):
    def test_title_wording(self):
        cases = {
            "Rebuilt title, drives great": "branded",
            "Salvage title from ICBC": "branded",
            "status: rebuilt": "branded",
            "previously written off": "branded",
            "Rebuilt engine at 90k, clean title": "clean",
            "No salvage title, never been in an accident": "clean",
            "not a write-off": "clean",
            "Clean Carfax": "clean",
            "Rebuilt transmission last year": "unknown",
            "Garage kept, summer only": "unknown",
        }
        for text, expected in cases.items():
            self.assertEqual(title_status(text), expected, text)

    def test_clean_only_drops_unknown(self):
        cfg = load_config(None)
        cfg["search"] = {**cfg["search"], "title": "clean_only"}
        unknown = Listing(listing_id="u", url="", title="2017 Subaru BRZ", price=18000, location="Surrey, BC", year=2017)
        clean = Listing(listing_id="c", url="", title="2017 Subaru BRZ", price=18000, location="Surrey, BC", year=2017,
                        description="Clean title, one owner")
        self.assertEqual(evaluate(unknown, cfg), "title status not stated")
        self.assertEqual(evaluate(clean, cfg), "")
        self.assertIn("clean title (seller says)", clean.positives)

    def test_facebook_clean_title_field(self):
        listing = Listing(listing_id="1005267709269383", url="")
        apply_page(listing, load_pages(PAGES)["1775877630223040"])
        page_with_field = {"clean_title": True}
        apply_page(listing, page_with_field)
        evaluate(listing, load_config(None))
        self.assertEqual(listing.title_status, "clean")


class PhotoAndHistoryTests(unittest.TestCase):
    def test_photo_check_fills_trim_and_flags_conflicts(self):
        listing = hand_listing("Toyota 86", 2018, 65000, 22889, transmission="automatic")
        apply_photo_check(listing, {"trim": "Base", "transmission": "manual", "mods": ["aftermarket rear wing"]})
        self.assertEqual((listing.trim, listing.trim_tier), ("Base", "base"))
        self.assertIn("ad says automatic, photos show manual", listing.flags)
        self.assertIn("modified", listing.flags)

    def test_photo_check_agrees(self):
        listing = hand_listing("BRZ", 2019, 43000, 18850, text="Sport-tech", transmission="automatic")
        apply_photo_check(listing, {"trim": "Sport-tech", "transmission": "automatic"})
        self.assertIn("automatic confirmed in photos", listing.positives)
        self.assertFalse(any("photos suggest" in f for f in listing.flags))

    def test_trend_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = (COMPS / "autotrader_2026-11-07.psv").read_text(encoding="utf-8")
            Path(tmp, "autotrader-all-2026-11-07.psv").write_text(src, encoding="utf-8")
            Path(tmp, "autotrader-all-2026-12-07.psv").write_text(src.replace("|17990|", "|16990|"), encoding="utf-8")
            rows = trend_rows(load_history(Path(tmp)))
            months = {r["month"] for r in rows}
            self.assertEqual(months, {"2026-11", "2026-12"})
            self.assertTrue(all(r["listings"] > 0 for r in rows))


class SourceTests(unittest.TestCase):
    def test_load_merge_and_references(self):
        listings, refs = load_listings(FIXTURES / "listings")
        self.assertEqual(len(listings), 4)
        self.assertEqual(len(refs), 1)
        cfg = load_config(None)
        for listing in listings:
            evaluate(listing, cfg)
        merged = merge_duplicates(listings)
        self.assertEqual(len(merged), 2)
        eighty_six = next(l for l in merged if l.year == 2018)
        self.assertEqual(len(eighty_six.also_listed), 1)
        self.assertTrue(any("km differs" in f for f in eighty_six.flags_extra))
        attach_references(merged, refs)
        gt = next(l for l in merged if l.year == 2019)
        self.assertIn({"source": "cargurus", "rating": "Fair Deal"}, gt.references)


class IngestWithValuesTests(unittest.TestCase):
    def test_digest_has_calls_and_comps_grow(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            self.assertEqual(main(["comps", "add", str(COMPS), "--data-dir", str(data), "--seen", date.today().isoformat()]), 0)
            inbox = Path(tmp) / "inbox"
            inbox.mkdir()
            (inbox / "a.txt").write_text(
                "[2018 Toyota 86](https://www.facebook.com/marketplace/item/1775877630223040/) "
                "CA$22,889\nVancouver, BC\n",
                encoding="utf-8",
            )
            cfg = Path(tmp) / "config.toml"
            cfg.write_text("[search]\nbudget_max = 25000\n", encoding="utf-8")
            main([
                "ingest", str(inbox), "--config", str(cfg), "--data-dir", str(data),
                "--out-dir", str(Path(tmp) / "digests"), "--pages", str(PAGES),
            ])
            text = next((Path(tmp) / "digests").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("- Call: Pass at this price.", text)
            self.assertIn("65,000 km", text)
            self.assertIn("Flip check", text)
            saved = CompStore(data / "comps.json").data
            self.assertIn("facebook:1775877630223040", saved)


if __name__ == "__main__":
    unittest.main()
