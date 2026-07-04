"""Tests for budget-variance-tracker.

Verifies the CLI output matches the regenerated golden fixture and checks the
core alert-threshold and burn-rate forecasting logic directly.

The fixture at
``1_Trailwise_Toolkit/budget-variance-tracker/fixtures/expected/budget_summary.json``
was regenerated from the actual CLI output — the previous version had stale
alert levels (it ignored the CRITICAL forecast>110% trigger and the
>=90%/>=75% boundaries) and an incorrect ``total_forecast`` total.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL_DIR = ROOT / "1_Trailwise_Toolkit" / "budget-variance-tracker"
FIXTURE = json.loads(
    (SKILL_DIR / "fixtures" / "expected" / "budget_summary.json").read_text(encoding="utf-8")
)
INPUT_CSV = SKILL_DIR / "fixtures" / "input" / "budget_lines.csv"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


bvt = load("budget_variance_tracker",
           "1_Trailwise_Toolkit/budget-variance-tracker/scripts/budget_variance_tracker.py")


class BudgetVarianceCLITests(unittest.TestCase):
    """End-to-end: CLI output must match the regenerated golden fixture."""

    def test_cli_output_matches_fixture(self):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            rc = bvt.main([
                "--project", FIXTURE["project"],
                "--csv", str(INPUT_CSV),
                "--total-budget", str(int(FIXTURE["total_budget"])),
            ])
        finally:
            sys.stdout = old
        self.assertEqual(rc, 0)
        actual = json.loads(buf.getvalue())
        self.assertEqual(actual, FIXTURE)

    def test_summary_totals_match_fixture(self):
        tracker = bvt.BudgetVarianceTracker(FIXTURE["project"], FIXTURE["total_budget"])
        bvt.load_from_csv(tracker, str(INPUT_CSV))
        summary = tracker.get_summary()
        for key in ("total_budget", "total_spent_committed", "total_forecast",
                    "projected_variance", "projected_variance_pct",
                    "lines_over_budget", "over_budget_codes", "remaining_budget"):
            self.assertEqual(summary[key], FIXTURE[key], f"mismatch on {key}")

    def test_alert_levels_match_fixture(self):
        tracker = bvt.BudgetVarianceTracker(FIXTURE["project"], FIXTURE["total_budget"])
        bvt.load_from_csv(tracker, str(INPUT_CSV))
        actual = {a.cost_code: a.level.value for a in tracker.check_alerts()}
        expected = {a["cost_code"]: a["level"] for a in FIXTURE["alerts"]}
        self.assertEqual(actual, expected)


class BudgetVarianceLogicTests(unittest.TestCase):
    """Unit tests for threshold classification and burn-rate forecasting."""

    def _line(self, **kw):
        defaults = dict(cost_code="X", category="Materials", description="d",
                        budgeted_amount=10000, spent_to_date=0, committed=0,
                        percent_complete=0)
        defaults.update(kw)
        return bvt.BudgetLine(**defaults)

    def _level(self, line):
        tracker = bvt.BudgetVarianceTracker("t", 0)
        tracker.add_budget_line(line)
        return tracker.check_alerts()[0].level

    def test_forecast_uses_burn_rate(self):
        # spent 30000 to get 60% done -> projected 50000
        line = self._line(budgeted_amount=45000, spent_to_date=30000, committed=0, percent_complete=60)
        tracker = bvt.BudgetVarianceTracker("t", 0)
        self.assertEqual(tracker._forecast_final(line), 50000.0)

    def test_forecast_zero_complete_falls_back_to_committed(self):
        line = self._line(budgeted_amount=10000, spent_to_date=4000, committed=2000, percent_complete=0)
        tracker = bvt.BudgetVarianceTracker("t", 0)
        self.assertEqual(tracker._forecast_final(line), 6000.0)

    def test_critical_when_forecast_exceeds_110pct_budget(self):
        # forecast 50000 > 45000*1.10=49500 -> CRITICAL even though usage only 66.7%
        line = self._line(cost_code="05100", budgeted_amount=45000, spent_to_date=30000, committed=0, percent_complete=60)
        self.assertEqual(self._level(line), bvt.AlertLevel.CRITICAL)

    def test_critical_triggers_regardless_of_low_usage(self):
        # 18.2% usage but forecast 66666.67 > 55000*1.10=60500 -> CRITICAL
        line = self._line(cost_code="08100", budgeted_amount=55000, spent_to_date=10000, committed=0, percent_complete=15)
        self.assertEqual(self._level(line), bvt.AlertLevel.CRITICAL)

    def test_red_when_usage_at_or_above_95pct(self):
        line = self._line(budgeted_amount=22000, spent_to_date=20000, committed=5000, percent_complete=85)
        self.assertEqual(self._level(line), bvt.AlertLevel.RED)

    def test_orange_at_90pct_boundary(self):
        line = self._line(budgeted_amount=25000, spent_to_date=18000, committed=5000, percent_complete=75)
        self.assertEqual(self._level(line), bvt.AlertLevel.ORANGE)

    def test_green_below_75pct_yellow_threshold(self):
        # 71% usage is below the 75% yellow boundary -> GREEN (committed counts)
        line = self._line(cost_code="06200", budgeted_amount=38000, spent_to_date=15000, committed=12000, percent_complete=40)
        self.assertEqual(self._level(line), bvt.AlertLevel.GREEN)

    def test_yellow_at_75pct_boundary(self):
        # 75% usage, forecast stays under budget -> YELLOW (not red/critical)
        line = self._line(budgeted_amount=10000, spent_to_date=7500, committed=0, percent_complete=100)
        self.assertEqual(self._level(line), bvt.AlertLevel.YELLOW)

    def test_green_below_50pct(self):
        line = self._line(budgeted_amount=10000, spent_to_date=4000, committed=0, percent_complete=40)
        self.assertEqual(self._level(line), bvt.AlertLevel.GREEN)

    def test_zero_budget_guard(self):
        line = self._line(cost_code="Z", budgeted_amount=0, spent_to_date=500, committed=0, percent_complete=10)
        self.assertEqual(line.variance_pct, 0)
        tracker = bvt.BudgetVarianceTracker("t", 0)
        tracker.add_budget_line(line)
        # usage divides by zero-guarded amount -> 0 -> GREEN, no crash
        alerts = tracker.check_alerts()
        self.assertEqual(len(alerts), 1)


if __name__ == "__main__":
    unittest.main()
