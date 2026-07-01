"""Stress, property, and fuzz tests for daily-field-report.

Seed: 20260701
All fixtures generated in-memory — no large files committed.
"""
from __future__ import annotations

import importlib.util
import sys
import time
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


daily = load("daily_field_report", "6_Contractor_Operations/daily-field-report/scripts/daily_field_report.py")

SEED = 20260701
TRADES = ["Electrical", "Plumbing", "HVAC", "Concrete", "Framing", "Roofing", "Drywall", "Painting", "Steel", "Excavation"]
SEVERITIES = ["observation", "first_aid", "recordable", "lost_time", "critical"]
DELAY_CATEGORIES = ["weather", "material_shortage", "equipment_failure", "labor_shortage", "permitting", "design_conflict"]


class DailyFieldReportLoadTests(unittest.TestCase):
    """Volume: 10,000 work/delay records."""

    def test_10k_work_entries(self):
        rng = Random(SEED)
        entries = tuple(
            daily.WorkEntry(
                rng.choice(TRADES), rng.randint(1, 20), str(rng.randint(1, 10)),
                f"Work item {i}", str(rng.randint(0, 4)),
            )
            for i in range(10_000)
        )
        report = daily.DailyReport("P-LARGE", date(2026, 7, 1), "Tester", "Clear", work=entries)

        start = time.perf_counter()
        result = daily.summarize(report)
        elapsed = time.perf_counter() - start

        self.assertEqual(len(result["work"]), 10_000)
        self.assertGreater(Decimal(result["labor_hours"]), Decimal("0"))
        self.assertLess(elapsed, 5.0, f"10K entries took {elapsed:.3f}s — expected <5s")
        # workers_reported should be sum of all workers
        expected_workers = sum(e.workers for e in entries)
        self.assertEqual(result["workers_reported"], expected_workers)

    def test_10k_delay_records(self):
        rng = Random(SEED + 1)
        delays = tuple(
            daily.DelayEvent(
                rng.choice(DELAY_CATEGORIES), f"Delay {i}", str(rng.randint(1, 8)),
                "unknown" if i % 3 == 0 else "GC",
            )
            for i in range(10_000)
        )
        report = daily.DailyReport("P-DELAYS", date(2026, 7, 1), "Tester", "Rain", delays=delays)

        start = time.perf_counter()
        result = daily.summarize(report)
        elapsed = time.perf_counter() - start

        self.assertEqual(len(result["delays"]), 10_000)
        self.assertIn("delay_responsibility_unconfirmed", result["review_reasons"])
        self.assertLess(elapsed, 5.0, f"10K delays took {elapsed:.3f}s — expected <5s")

    def test_mixed_10k_work_and_delay(self):
        rng = Random(SEED + 2)
        entries = tuple(
            daily.WorkEntry(rng.choice(TRADES), rng.randint(1, 15), str(rng.randint(1, 8)), f"Work {i}")
            for i in range(5_000)
        )
        delays = tuple(
            daily.DelayEvent(rng.choice(DELAY_CATEGORIES), f"Delay {i}", str(rng.randint(1, 4)))
            for i in range(5_000)
        )
        report = daily.DailyReport("P-MIX", date(2026, 7, 1), "Tester", "Overcast", work=entries, delays=delays)

        start = time.perf_counter()
        result = daily.summarize(report)
        elapsed = time.perf_counter() - start

        self.assertEqual(len(result["work"]), 5_000)
        self.assertEqual(len(result["delays"]), 5_000)
        self.assertLess(elapsed, 5.0, f"5K+5K took {elapsed:.3f}s")

    def test_empty_report(self):
        report = daily.DailyReport("P-EMPTY", date(2026, 7, 1), "Tester", "Clear")
        result = daily.summarize(report)
        self.assertIn("no_work_entries", result["review_reasons"])
        self.assertEqual(result["labor_hours"], "0")
        self.assertEqual(result["delay_hours"], "0")

    def test_zero_workers(self):
        entry = daily.WorkEntry("Electrical", 0, "8", "No one showed up")
        report = daily.DailyReport("P-ZERO", date(2026, 7, 1), "Tester", "Clear", work=(entry,))
        result = daily.summarize(report)
        self.assertEqual(result["labor_hours"], "0")
        self.assertEqual(result["workers_reported"], 0)


class DailyFieldReportPropertyTests(unittest.TestCase):
    """Seeded property tests: 1,000 valid and invalid cases."""

    def test_no_negative_workers(self):
        for _ in range(1_000):
            with self.assertRaises(ValueError):
                daily.WorkEntry("Electrical", -1, "8", "Negative workers")

    def test_no_negative_hours(self):
        rng = Random(SEED + 10)
        for _ in range(1_000):
            with self.assertRaises(ValueError):
                daily.WorkEntry("Electrical", 1, str(-rng.randint(1, 100)), "Negative hours")

    def test_no_negative_overtime(self):
        for _ in range(1_000):
            with self.assertRaises(ValueError):
                daily.WorkEntry("Electrical", 1, "8", "Work", str(-1))

    def test_no_shift_over_24h(self):
        rng = Random(SEED + 20)
        for _ in range(1_000):
            regular = rng.randint(13, 23)
            overtime = 25 - regular + rng.randint(0, 5)
            with self.assertRaises(ValueError):
                daily.WorkEntry("Electrical", 1, str(regular), "Work", str(overtime))

    def test_no_nonfinite_values(self):
        for val in ["Infinity", "NaN", "inf"]:
            with self.assertRaises(ValueError):
                daily.WorkEntry("Electrical", 1, val, "Work")
            with self.assertRaises(ValueError):
                daily.DelayEvent("weather", "Rain", val)

    def test_no_negative_delay_hours(self):
        for _ in range(1_000):
            with self.assertRaises(ValueError):
                daily.DelayEvent("weather", "Rain", "-2.5")

    def test_empty_trade_rejected(self):
        for _ in range(100):
            with self.assertRaises(ValueError):
                daily.WorkEntry("", 1, "8", "Work")
            with self.assertRaises(ValueError):
                daily.WorkEntry("   ", 1, "8", "Work")

    def test_empty_description_rejected(self):
        for _ in range(100):
            with self.assertRaises(ValueError):
                daily.WorkEntry("Electrical", 1, "8", "")
            with self.assertRaises(ValueError):
                daily.DelayEvent("weather", "", "2")

    def test_invalid_severity_rejected(self):
        for bad in ["", "unknown", "minor", "major", "critical_injury", "RECORDABLE"]:
            with self.assertRaises(ValueError):
                daily.SafetyEvent("Incident", bad)

    def test_valid_severities_accepted(self):
        for sev in SEVERITIES:
            event = daily.SafetyEvent("Incident description", sev)
            self.assertEqual(event.severity, sev)

    def test_explicit_date_determines_output(self):
        entry = daily.WorkEntry("Electrical", 4, "8", "Wiring")
        r1 = daily.summarize(daily.DailyReport("P1", date(2026, 7, 1), "A", "Clear", work=(entry,)))
        r2 = daily.summarize(daily.DailyReport("P1", date(2026, 7, 1), "A", "Clear", work=(entry,)))
        self.assertEqual(r1, r2)

    def test_recordable_always_flags_review(self):
        for sev in ["recordable", "lost_time", "critical"]:
            report = daily.DailyReport("P1", date(2026, 7, 1), "A", "Clear",
                                       safety_events=(daily.SafetyEvent("Incident", sev),))
            self.assertIn("recordable_or_more_severe_safety_event", daily.summarize(report)["review_reasons"])

    def test_observation_and_first_aid_do_not_flag(self):
        for sev in ["observation", "first_aid"]:
            report = daily.DailyReport("P1", date(2026, 7, 1), "A", "Clear",
                                       work=(daily.WorkEntry("Electrical", 1, "8", "Work"),),
                                       safety_events=(daily.SafetyEvent("Note", sev),))
            self.assertNotIn("recordable_or_more_severe_safety_event", daily.summarize(report)["review_reasons"])

    def test_unknown_responsibility_flags_review(self):
        report = daily.DailyReport("P1", date(2026, 7, 1), "A", "Rain",
                                   work=(daily.WorkEntry("Electrical", 1, "8", "Work"),),
                                   delays=(daily.DelayEvent("weather", "Rain delay", "3", "unknown"),))
        self.assertIn("delay_responsibility_unconfirmed", daily.summarize(report)["review_reasons"])

    def test_known_responsibility_does_not_flag(self):
        report = daily.DailyReport("P1", date(2026, 7, 1), "A", "Rain",
                                   work=(daily.WorkEntry("Electrical", 1, "8", "Work"),),
                                   delays=(daily.DelayEvent("weather", "Rain delay", "3", "GC"),))
        self.assertNotIn("delay_responsibility_unconfirmed", daily.summarize(report)["review_reasons"])

    def test_labor_hours_exact_calculation(self):
        rng = Random(SEED + 30)
        for _ in range(1_000):
            workers = rng.randint(1, 20)
            regular = Decimal(str(rng.randint(1, 10)))
            overtime = Decimal(str(rng.randint(0, 4)))
            entry = daily.WorkEntry("Electrical", workers, str(regular), "Work", str(overtime))
            expected = Decimal(workers) * (regular + overtime)
            self.assertEqual(entry.labor_hours, expected)

    def test_overtime_defaults_to_zero(self):
        entry = daily.WorkEntry("Electrical", 2, "8", "Work")
        self.assertEqual(entry.labor_hours, Decimal("16"))

    def test_unique_trade_count(self):
        entries = (
            daily.WorkEntry("Electrical", 2, "8", "A"),
            daily.WorkEntry("Plumbing", 1, "8", "B"),
            daily.WorkEntry("Electrical", 3, "8", "C"),
        )
        report = daily.DailyReport("P1", date(2026, 7, 1), "A", "Clear", work=entries)
        result = daily.summarize(report)
        self.assertEqual(result["trade_count"], 2)

    def test_required_fields_enforced(self):
        for bad in [("", "prep", "weather"), ("proj", "", "weather"), ("proj", "prep", "")]:
            with self.assertRaises(ValueError):
                daily.DailyReport(bad[0], date(2026, 7, 1), bad[1], bad[2])

    def test_no_invented_facts_in_output(self):
        """Output should only contain provided data, no fabricated weather/progress."""
        report = daily.DailyReport("P1", date(2026, 7, 1), "A", "Clear, 72F",
                                    work=(daily.WorkEntry("Electrical", 2, "8", "Conduit"),))
        result = daily.summarize(report)
        self.assertEqual(result["weather_observed"], "Clear, 72F")
        self.assertNotIn("weather_summary", result)
        self.assertNotIn("progress_assessment", result)

    def test_24h_shift_boundary(self):
        """Exactly 24h should be accepted (boundary)."""
        entry = daily.WorkEntry("Electrical", 1, "16", "Work", "8")
        self.assertEqual(entry.labor_hours, Decimal("24"))

    def test_24h_plus_1_rejected(self):
        """25h should be rejected (boundary+1)."""
        with self.assertRaises(ValueError):
            daily.WorkEntry("Electrical", 1, "16", "Work", "9")


class DailyFieldReportFuzzTests(unittest.TestCase):
    """Fuzz: random valid and invalid combinations."""

    def test_fuzz_valid_reports(self):
        rng = Random(SEED + 100)
        for i in range(1_000):
            n_work = rng.randint(0, 10)
            n_delays = rng.randint(0, 5)
            n_safety = rng.randint(0, 3)
            entries = tuple(
                daily.WorkEntry(
                    rng.choice(TRADES), rng.randint(0, 20), str(rng.randint(0, 12)),
                    f"Work {j}", str(rng.randint(0, 4)),
                )
                for j in range(n_work)
            )
            delays = tuple(
                daily.DelayEvent(
                    rng.choice(DELAY_CATEGORIES), f"Delay {j}", str(rng.randint(0, 8)),
                    rng.choice(["unknown", "GC", "Sub", "Owner", "Architect"]),
                )
                for j in range(n_delays)
            )
            safety = tuple(
                daily.SafetyEvent(f"Event {j}", rng.choice(SEVERITIES))
                for j in range(n_safety)
            )
            report = daily.DailyReport(f"P{i}", date(2026, 7, 1), f"User{i}", "Variable", work=entries, delays=delays, safety_events=safety)
            result = daily.summarize(report)
            # Invariants
            self.assertEqual(result["project_id"], f"P{i}")
            self.assertGreaterEqual(Decimal(result["labor_hours"]), Decimal("0"))
            self.assertGreaterEqual(Decimal(result["delay_hours"]), Decimal("0"))
            self.assertEqual(result["safety_event_count"], n_safety)

    def test_fuzz_invalid_inputs_rejected(self):
        rng = Random(SEED + 200)
        for _ in range(1_000):
            bad_workers = -rng.randint(1, 100)
            with self.assertRaises(ValueError):
                daily.WorkEntry(rng.choice(TRADES), bad_workers, "8", "Work")


if __name__ == "__main__":
    unittest.main()
