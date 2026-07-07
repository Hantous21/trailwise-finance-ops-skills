from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TC_FIX = ROOT / "6_Contractor_Operations/certified-payroll-report/fixtures/input/timecards.csv"
WD_FIX = ROOT / "6_Contractor_Operations/certified-payroll-report/fixtures/input/wage_determination.csv"
EXPECTED = ROOT / "6_Contractor_Operations/certified-payroll-report/fixtures/expected/timecards.json"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


pr = load("certified_payroll_report", "6_Contractor_Operations/certified-payroll-report/scripts/certified_payroll_report.py")


def _by_employee(report: dict) -> dict[str, dict]:
    return {r["employee"]: r for r in report["rows"]}


class PayrollGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture_output(self):
        tc = pr.load_timecards(TC_FIX)
        wd = pr.load_determination(WD_FIX)
        report = pr.build_report(tc, wd)
        rows = _by_employee(report)

        alice = rows["Alice Moreno"]
        self.assertEqual(alice["total_hours"], 46)
        self.assertEqual(alice["ot_hours"], 6)
        self.assertEqual(alice["gross"], 1648.0)
        self.assertEqual(alice["flags"], [])  # 34 paid >= 31 prevailing

        ben = rows["Ben Carter"]
        self.assertEqual(ben["total_hours"], 40)
        self.assertEqual(ben["gross"], 1360.0)
        self.assertEqual(ben["flags"], ["underpaid"])
        self.assertEqual(ben["restitution"], 160.0)  # 4.00/hr * 40 hrs

        chris = rows["Chris Doyle"]
        self.assertEqual(chris["gross"], 1600.0)
        self.assertEqual(chris["flags"], ["unknown_classification"])
        # Plan: unknown_classification does NOT produce underpaid flag
        self.assertNotIn("underpaid", chris["flags"])
        self.assertEqual(chris["restitution"], 0.0)

        self.assertEqual(report["total_gross"], 4608.0)
        self.assertEqual(report["exception_count"], 2)
        self.assertEqual(report["row_count"], 3)

        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)


class PayrollEdgeCases(unittest.TestCase):
    def test_exactly_40_hours_zero_ot(self):
        tc = [pr.Timecard("E", "laborer", "P", date(2026, 6, 27),
                          (8, 8, 8, 8, 8, 0, 0), 26.0, 5.0)]
        wd = [pr.WageDetermination("laborer", 26.0, 5.0)]
        r = pr.build_report(tc, wd)["rows"][0]
        self.assertEqual(r["total_hours"], 40)
        self.assertEqual(r["ot_hours"], 0)
        self.assertEqual(r["gross"], 40 * 26.0 + 40 * 5.0)  # 1240

    def test_zero_hour_week_zero_gross(self):
        tc = [pr.Timecard("E", "laborer", "P", date(2026, 6, 27),
                          (0, 0, 0, 0, 0, 0, 0), 26.0, 5.0)]
        wd = [pr.WageDetermination("laborer", 26.0, 5.0)]
        r = pr.build_report(tc, wd)["rows"][0]
        self.assertEqual(r["total_hours"], 0)
        self.assertEqual(r["gross"], 0.0)
        self.assertEqual(r["flags"], [])  # 0 hrs, 0 owed, no underpayment
        self.assertEqual(r["restitution"], 0.0)

    def test_paid_exactly_equals_prevailing_compliant(self):
        # 26 + 5 = 31 = 26 + 5 -> compliant
        tc = [pr.Timecard("E", "laborer", "P", date(2026, 6, 27),
                          (8, 8, 8, 8, 8, 0, 0), 26.0, 5.0)]
        wd = [pr.WageDetermination("laborer", 26.0, 5.0)]
        r = pr.build_report(tc, wd)["rows"][0]
        self.assertEqual(r["flags"], [])

    def test_unknown_classification_does_not_set_underpaid(self):
        tc = [pr.Timecard("E", "zorb", "P", date(2026, 6, 27),
                          (8, 8, 8, 8, 8, 0, 0), 100.0, 50.0)]
        wd = [pr.WageDetermination("laborer", 1.0, 1.0)]
        r = pr.build_report(tc, wd)["rows"][0]
        self.assertEqual(r["flags"], ["unknown_classification"])
        self.assertNotIn("underpaid", r["flags"])


if __name__ == "__main__":
    unittest.main()
