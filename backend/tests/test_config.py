"""Smoke tests for config/*.json: shape, counts, duplicates and the no-alert-fatigue rule.

Run from the repo root: py -m unittest discover -s backend/tests -v
"""
import json
import re
import unittest
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "config"

TICKER = re.compile(r"^[A-Z0-9&\-]{1,20}$")  # same rule the API applies to user input
SIZE_BUCKETS = {"large", "mid", "small"}
CARD_TYPES = {"results", "management", "one_liner", "surface_only"}
CATEGORY_IDS = {
    "results", "m_and_a", "fund_raise", "management_change", "litigation", "insider_trading",
    "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex",
    "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified",
}


def load(name):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


class CompanyListTests(unittest.TestCase):
    def check_list(self, filename, expected_count):
        companies = load(filename)["companies"]
        self.assertEqual(len(companies), expected_count)
        symbols = [c["symbol"] for c in companies]
        self.assertEqual(len(symbols), len(set(symbols)), "duplicate symbols")
        for c in companies:
            self.assertEqual(set(c), {"symbol", "name", "sector", "size_bucket"})
            self.assertRegex(c["symbol"], TICKER)
            self.assertIn(c["size_bucket"], SIZE_BUCKETS)
            self.assertTrue(c["name"].strip() and c["sector"].strip())
        return set(symbols)

    def test_portfolio_has_18_companies(self):
        self.check_list("portfolio.json", 18)

    def test_research_has_4_companies_outside_the_portfolio(self):
        research = self.check_list("research.json", 4)
        portfolio = {c["symbol"] for c in load("portfolio.json")["companies"]}
        self.assertFalse(research & portfolio)


class CategoryTests(unittest.TestCase):
    def setUp(self):
        self.categories = load("categories.json")["categories"]

    def test_exactly_the_17_expected_categories(self):
        ids = [c["id"] for c in self.categories]
        self.assertEqual(len(ids), len(set(ids)), "duplicate category ids")
        self.assertEqual(set(ids), CATEGORY_IDS)

    def test_every_category_is_fully_specified(self):
        for c in self.categories:
            self.assertEqual(
                set(c),
                {"id", "label", "why", "weight", "is_routine", "default_alert", "card_type", "rationale"},
            )
            self.assertTrue(c["why"].strip() and len(c["why"]) <= 70, f"{c['id']}: why must fit one short line")
            self.assertIsInstance(c["weight"], int)
            self.assertTrue(0 <= c["weight"] <= 100, c["id"])
            self.assertIsInstance(c["is_routine"], bool)
            self.assertIsInstance(c["default_alert"], bool)
            self.assertIn(c["card_type"], CARD_TYPES)
            self.assertTrue(c["label"].strip() and c["rationale"].strip())

    def test_routine_filings_never_alert_by_default(self):
        for c in self.categories:
            if c["is_routine"]:
                self.assertFalse(c["default_alert"], c["id"])

    def test_special_cards_are_wired_to_the_right_categories(self):
        by_id = {c["id"]: c for c in self.categories}
        self.assertEqual(by_id["results"]["card_type"], "results")
        self.assertEqual(by_id["management_change"]["card_type"], "management")


class DefaultsTests(unittest.TestCase):
    def test_smart_defaults(self):
        self.assertEqual(
            load("defaults.json"),
            {"window_hours": 24, "volume_multiple": 2.0, "price_move_pct": 5.0, "volume_lookback_days": 20},
        )


if __name__ == "__main__":
    unittest.main()
