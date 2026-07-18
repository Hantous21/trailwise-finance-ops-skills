from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    "7_Restaurant_Operations/labor-percent-guard/scripts/labor_percent_guard.py"
)
INPUT = ROOT / "7_Restaurant_Operations/labor-percent-guard/fixtures/input/dayparts.csv"
EXPECTED = (
    ROOT
    / "7_Restaurant_Operations/labor-percent-guard/fixtures/expected/dayparts_report.json"
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


labor = load("labor_percent_guard", SCRIPT)


class LaborPercentGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture(self):
        report = labor.evaluate(labor.load_dayparts(INPUT))
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)
        self.assertIn("cut_before_ot", report["action_counts"])
        self.assertIn("add_body", report["action_counts"])


class LaborPercentEdgeCases(unittest.TestCase):
    def test_cut_before_ot_when_over_target_and_under_covers(self):
        rows = labor.load_dayparts(INPUT)
        lunch = next(
            r
            for r in labor.evaluate(rows)["dayparts"]
            if r["business_date"] == "2026-07-02" and r["daypart"] == "lunch"
        )
        self.assertEqual(lunch["action"], "cut_before_ot")
        self.assertIn("over_target", lunch["flags"])

    def test_add_body_on_cover_surge(self):
        report = labor.evaluate(labor.load_dayparts(INPUT))
        brunch = next(
            r
            for r in report["dayparts"]
            if r["business_date"] == "2026-07-03" and r["daypart"] == "brunch"
        )
        self.assertEqual(brunch["action"], "add_body")
        self.assertIn("add_body", brunch["flags"])


if __name__ == "__main__":
    unittest.main()
