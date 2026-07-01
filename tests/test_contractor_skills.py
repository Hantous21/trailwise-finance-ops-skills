from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/operations_cases.json").read_text(encoding="utf-8"))


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


daily = load("daily_field_report", "6_Contractor_Operations/daily-field-report/scripts/daily_field_report.py")
rfi = load("rfi_management", "6_Contractor_Operations/rfi-management/scripts/rfi_management.py")
submittal = load("submittal_tracker", "6_Contractor_Operations/submittal-tracker/scripts/submittal_tracker.py")
schedule = load("schedule_delay_analyzer", "6_Contractor_Operations/schedule-delay-analyzer/scripts/schedule_delay_analyzer.py")
data_quality = load("data_quality_check", "2_Trailwise_Methodology/data-quality-check/scripts/data_quality_check.py")


class DailyFieldReportTests(unittest.TestCase):
    def test_golden_labor_hours(self):
        case = FIXTURES["daily_field_report"]
        report = daily.DailyReport(
            case["project_id"], date.fromisoformat(case["report_date"]), "A. Rivera", "Clear",
            work=(daily.WorkEntry("Electrical", case["workers"], case["hours_per_worker"], "Installed conduit"),),
        )
        result = daily.summarize(report)
        self.assertEqual(result["labor_hours"], case["expected_labor_hours"])
        self.assertFalse(result["requires_review"])

    def test_delay_with_unknown_responsibility_requires_review(self):
        report = daily.DailyReport(
            "P1", date(2026, 7, 1), "A", "Rain",
            delays=(daily.DelayEvent("weather", "Lightning stand-down", "2"),),
        )
        reasons = daily.summarize(report)["review_reasons"]
        self.assertIn("delay_responsibility_unconfirmed", reasons)

    def test_impossible_shift_is_rejected(self):
        with self.assertRaises(ValueError):
            daily.WorkEntry("Concrete", 2, "20", "Placement", "5")

    def test_recordable_event_is_flagged(self):
        report = daily.DailyReport(
            "P1", date(2026, 7, 1), "A", "Clear",
            safety_events=(daily.SafetyEvent("Employee evaluated", "recordable"),),
        )
        self.assertIn("recordable_or_more_severe_safety_event", daily.summarize(report)["review_reasons"])


class RFIManagementTests(unittest.TestCase):
    def test_overdue_rfi_with_schedule_impact_is_critical(self):
        item = rfi.RFI("RFI-1", "Detail", date(2026, 6, 1), date(2026, 6, 8), estimated_schedule_days=3)
        result = rfi.triage(item, date(2026, 6, 10))
        self.assertEqual(result["priority"], "critical")
        self.assertEqual(result["days_overdue"], 2)

    def test_unknown_impact_is_not_treated_as_zero(self):
        item = rfi.RFI("RFI-1", "Detail", date(2026, 6, 1), date(2026, 7, 8))
        self.assertIn("impact_not_quantified", rfi.triage(item, date(2026, 6, 10))["reasons"])

    def test_closed_rfi_requires_answer_date(self):
        with self.assertRaises(ValueError):
            rfi.RFI("RFI-1", "Detail", date(2026, 6, 1), date(2026, 6, 8), status=rfi.RFIStatus.CLOSED)

    def test_portfolio_counts_overdue(self):
        items = [rfi.RFI("R1", "A", date(2026, 6, 1), date(2026, 6, 2))]
        self.assertEqual(rfi.portfolio(items, date(2026, 6, 3))["overdue"], 1)


class SubmittalTrackerTests(unittest.TestCase):
    def test_required_submission_subtracts_review_and_fabrication(self):
        item = submittal.Submittal("S1", "Steel", date(2026, 8, 1), 20, 10)
        self.assertEqual(item.required_submission_date, date(2026, 7, 2))

    def test_late_unsubmitted_item_is_critical(self):
        item = submittal.Submittal("S1", "Steel", date(2026, 8, 1), 20, 10)
        self.assertEqual(submittal.evaluate(item, date(2026, 7, 3))["risk"], "critical")

    def test_overdue_review_is_critical(self):
        item = submittal.Submittal(
            "S1", "Steel", date(2026, 9, 1), 20, 10,
            status=submittal.SubmittalStatus.UNDER_REVIEW, submitted_on=date(2026, 7, 1),
        )
        self.assertIn("review_overdue", submittal.evaluate(item, date(2026, 7, 12))["reasons"])

    def test_approved_requires_decision_date(self):
        with self.assertRaises(ValueError):
            submittal.Submittal("S1", "Steel", date(2026, 8, 1), 20, 10, status=submittal.SubmittalStatus.APPROVED)


class ScheduleDelayTests(unittest.TestCase):
    def activities(self):
        return [schedule.Activity(row["id"], row["duration"], tuple(row["predecessors"])) for row in FIXTURES["schedule"]["activities"]]

    def test_golden_critical_path_and_duration(self):
        result = schedule.analyze(self.activities())
        self.assertEqual(result["project_duration_days"], FIXTURES["schedule"]["baseline_duration"])
        self.assertEqual(result["critical_path"], ["A", "B"])

    def test_delay_uses_available_float_before_project_impact(self):
        case = FIXTURES["schedule"]
        result = schedule.simulate_delay(self.activities(), case["delayed_activity"], case["delay_days"])
        self.assertEqual(result["project_impact_days"], case["project_impact_days"])
        self.assertEqual(result["absorbed_by_float_days"], 3)

    def test_cycle_is_rejected(self):
        activities = [schedule.Activity("A", 1, ("B",)), schedule.Activity("B", 1, ("A",))]
        with self.assertRaisesRegex(ValueError, "cycle"):
            schedule.analyze(activities)

    def test_missing_predecessor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing predecessor"):
            schedule.analyze([schedule.Activity("A", 1, ("MISSING",))])


class DataQualityCheckTests(unittest.TestCase):
    def test_valid_file_returns_hash_and_zero_errors(self):
        schema = json.loads((ROOT / "tests/fixtures/data_quality_schema.json").read_text(encoding="utf-8"))
        report = data_quality.check_csv(ROOT / "tests/fixtures/data_quality_valid.csv", schema)
        self.assertTrue(report["valid"])
        self.assertEqual(len(report["sha256"]), 64)

    def test_nonfinite_decimal_is_rejected(self):
        schema = {"columns": {"amount": {"type": "decimal", "required": True}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text("amount\nNaN\n", encoding="utf-8")
            report = data_quality.check_csv(path, schema)
        self.assertEqual(report["errors"][0]["code"], "invalid_type")

    def test_reports_duplicate_invalid_and_blank_rows(self):
        schema = {
            "columns": {
                "invoice_id": {"type": "string", "required": True},
                "amount": {"type": "decimal", "required": True},
                "due_date": {"type": "date", "required": True},
            },
            "unique_keys": ["invoice_id"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text("invoice_id,amount,due_date\nA,10,2026-01-01\nA,bad,\n", encoding="utf-8")
            report = data_quality.check_csv(path, schema)
        self.assertFalse(report["valid"])
        self.assertEqual({item["code"] for item in report["errors"]}, {"invalid_type", "blank_required", "duplicate_key"})


if __name__ == "__main__":
    unittest.main()
