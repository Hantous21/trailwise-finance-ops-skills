from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "6_Contractor_Operations/lien-waiver-tracker/fixtures/input/waiver_log.csv"
EXPECTED = ROOT / "6_Contractor_Operations/lien-waiver-tracker/fixtures/expected/waiver_log.json"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


wt = load("lien_waiver_tracker", "6_Contractor_Operations/lien-waiver-tracker/scripts/lien_waiver_tracker.py")


def _by_project(report: dict) -> dict[str, dict]:
    return {p["project"]: p for p in report["projects"]}


class LienWaiverGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture_output(self):
        report = wt.evaluate(wt.load_rows(FIXTURE))
        projects = _by_project(report)

        maple = projects["Maple Office TI"]
        self.assertEqual(maple["exposure"], 60000.0)
        # next_draw_blockers contains Delta Electric #1 (only sub with missing waiver)
        self.assertEqual(
            maple["next_draw_blockers"],
            [{"subcontractor": "Delta Electric", "draw_number": 1}],
        )

        # Maple row 2 (Delta Electric, draw 1) -> missing_waiver
        delta = next(r for r in maple["rows"]
                     if r["subcontractor"] == "Delta Electric" and r["draw_number"] == 1)
        self.assertEqual(delta["flags"], ["missing_waiver"])
        self.assertEqual(delta["risks"], ["high"])

        # Maple row 3 (Apex Plumbing, draw 2) -> both critical flags
        apex_d2 = next(r for r in maple["rows"]
                       if r["subcontractor"] == "Apex Plumbing" and r["draw_number"] == 2)
        self.assertIn("unconditional_before_cleared", apex_d2["flags"])
        self.assertIn("waiver_predates_payment", apex_d2["flags"])
        self.assertEqual(apex_d2["risks"], ["critical", "critical"])

        riverside = projects["Riverside Retail"]
        self.assertEqual(riverside["exposure"], 0.0)
        self.assertEqual(riverside["next_draw_blockers"], [])

        self.assertEqual(report["total_exposure"], 60000.0)
        self.assertEqual(report["critical_reason_count"], 2)
        self.assertEqual(report["project_count"], 2)

        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)


class LienWaiverEdgeCases(unittest.TestCase):
    def test_all_clean_log_zero_exposure(self):
        rows = [
            wt.WaiverRow("P", "Sub", 1, 1000.0, date(2026, 1, 1), "Y",
                         "conditional_progress", "Y", date(2026, 1, 1)),
        ]
        report = wt.evaluate(rows)
        self.assertEqual(report["total_exposure"], 0.0)
        self.assertEqual(report["critical_reason_count"], 0)
        self.assertEqual(report["projects"][0]["next_draw_blockers"], [])

    def test_unknown_waiver_type_raises(self):
        with self.assertRaisesRegex(ValueError, "unknown waiver_type"):
            wt.WaiverRow("P", "S", 1, 100.0, date(2026, 1, 1), "Y", "bogus_type", "Y", date(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
