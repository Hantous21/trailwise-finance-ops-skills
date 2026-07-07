from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "1_Trailwise_Toolkit/retainage-tracker/fixtures/input/retainage_draws.csv"
EXPECTED = ROOT / "1_Trailwise_Toolkit/retainage-tracker/fixtures/expected/retainage_draws.json"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ret = load("retainage_tracker", "1_Trailwise_Toolkit/retainage-tracker/scripts/retainage_tracker.py")


def _by_project(report: dict) -> dict[str, dict]:
    return {p["project"]: p for p in report["projects"]}


AS_OF = date(2026, 7, 1)


class RetainageGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture_output(self):
        report = ret.evaluate(ret.load_draws(FIXTURE), AS_OF)
        projects = _by_project(report)

        maple = projects["Maple Office TI"]
        self.assertEqual(maple["outstanding"], 24000.0)
        self.assertEqual(maple["days_since_completion"], 61)
        self.assertEqual(maple["flags"], ["release_overdue"])

        riverside = projects["Riverside Retail"]
        self.assertEqual(riverside["outstanding"], 2500.0)
        self.assertIsNone(riverside["days_since_completion"])
        self.assertEqual(riverside["flags"], ["retainage_rate_change"])

        hwy = projects["Hwy 7 Culvert"]
        self.assertEqual(hwy["outstanding"], 0.0)
        self.assertEqual(hwy["flags"], [])

        self.assertEqual(report["total_outstanding_receivable"], 26500.0)
        self.assertEqual(report["project_count"], 3)

        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)


class RetainageEdgeCases(unittest.TestCase):
    def test_withholding_mismatch_is_flagged(self):
        draws = [ret.Draw("P", 1, date(2026, 1, 1), 100000.0, 10.0, 9500.0, 0.0, None)]
        report = ret.evaluate(draws, date(2026, 7, 1))
        self.assertEqual(report["projects"][0]["flags"], ["withholding_mismatch"])

    def test_over_release_is_flagged(self):
        draws = [ret.Draw("P", 1, date(2026, 1, 1), 10000.0, 10.0, 1000.0, 2000.0, None)]
        report = ret.evaluate(draws, date(2026, 7, 1))
        self.assertIn("over_release", report["projects"][0]["flags"])

    def test_release_overdue_boundary(self):
        # completion exactly 45 days ago -> NOT overdue
        draws = [ret.Draw("P", 1, date(2026, 1, 1), 10000.0, 10.0, 1000.0, 0.0,
                          date(2026, 5, 17))]
        report = ret.evaluate(draws, date(2026, 7, 1))  # 45 days exactly
        self.assertEqual(report["projects"][0]["days_since_completion"], 45)
        self.assertNotIn("release_overdue", report["projects"][0]["flags"])
        # 46 days -> overdue
        report2 = ret.evaluate(draws, date(2026, 7, 2))
        self.assertEqual(report2["projects"][0]["days_since_completion"], 46)
        self.assertIn("release_overdue", report2["projects"][0]["flags"])


if __name__ == "__main__":
    unittest.main()
