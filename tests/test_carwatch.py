import tempfile
import unittest
from pathlib import Path

from carwatch.cli import main
from carwatch.config import load_config
from carwatch.filters import evaluate
from carwatch.parser import load_email, parse_email
from carwatch.store import Store

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
        for item_id in ("1111111111111111", "2222222222222222", "5555555555555555"):
            self.assertEqual(self.reason(item_id), "", item_id)

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
        self.assertIn("rebuilt or salvage title", flags)
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
            self.assertEqual(len(store.data), 3)

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


if __name__ == "__main__":
    unittest.main()
