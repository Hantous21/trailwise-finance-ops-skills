from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    "7_Restaurant_Operations/food-cost-bleed-map/scripts/food_cost_bleed_map.py"
)
SALES = ROOT / "7_Restaurant_Operations/food-cost-bleed-map/fixtures/input/sales.csv"
RECIPES = (
    ROOT / "7_Restaurant_Operations/food-cost-bleed-map/fixtures/input/recipes.csv"
)
WASTE = ROOT / "7_Restaurant_Operations/food-cost-bleed-map/fixtures/input/waste.csv"
EXPECTED = (
    ROOT
    / "7_Restaurant_Operations/food-cost-bleed-map/fixtures/expected/bleed_report.json"
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


bleed = load("food_cost_bleed_map", SCRIPT)


class FoodCostBleedGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture(self):
        report = bleed.evaluate(SALES, RECIPES, WASTE)
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)
        self.assertEqual(report["bleed_total"], 400.0)
        self.assertEqual(report["top_culprits"][0]["item"], "Steak")


class FoodCostBleedEdgeCases(unittest.TestCase):
    def test_missing_recipe_flags_wrong_recipe_bucket(self):
        report = bleed.evaluate(SALES, RECIPES, WASTE)
        mystery = next(i for i in report["items"] if i["item"] == "Mystery Special")
        self.assertTrue(mystery["missing_recipe"])
        self.assertEqual(mystery["primary_bucket"], "wrong_recipe")
        self.assertIsNone(mystery["bleed_pct"])

    def test_zero_bleed_item_ranks_last(self):
        # Pasta bleed 30, salad 20 — both positive
        report = bleed.evaluate(SALES, RECIPES, WASTE)
        bleeds = [i["bleed"] for i in report["items"]]
        self.assertEqual(bleeds, sorted(bleeds, reverse=True))


if __name__ == "__main__":
    unittest.main()
