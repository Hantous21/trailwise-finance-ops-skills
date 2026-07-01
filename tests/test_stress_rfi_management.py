"""Stress, property, and fuzz tests for rfi-management. Seed: 20260701."""
from __future__ import annotations
import importlib.util, sys, time, unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

rfi_mod = load("rfi_management", "6_Contractor_Operations/rfi-management/scripts/rfi_management.py")
RFI = rfi_mod.RFI
RFIStatus = rfi_mod.RFIStatus
SEED = 20260701

class RFILoadTests(unittest.TestCase):
    def test_25k_mixed_rfis(self):
        rng = Random(SEED)
        statuses = [RFIStatus.OPEN, RFIStatus.ANSWERED, RFIStatus.CLOSED, RFIStatus.VOID]
        rfis = []
        for i in range(25_000):
            sub = date(2026, 5, 1) + timedelta(days=rng.randint(0, 40))
            req = sub + timedelta(days=rng.randint(1, 14))
            st = rng.choice(statuses)
            cost = Decimal(str(rng.randint(0, 50000))) if rng.random() > 0.3 else None
            sched = rng.randint(0, 10) if rng.random() > 0.3 else None
            answered = (req + timedelta(days=rng.randint(0, 5))) if st in {RFIStatus.ANSWERED, RFIStatus.CLOSED} else None
            rfis.append(RFI(f"RFI-{i}", f"Detail {i}", sub, req, st, cost, sched, answered))
        start = time.perf_counter()
        result = rfi_mod.portfolio(rfis, date(2026, 7, 15))
        elapsed = time.perf_counter() - start
        self.assertEqual(result["total"], 25_000)
        self.assertLess(elapsed, 5.0, f"25K RFIs took {elapsed:.3f}s")
        self.assertGreater(result["overdue"], 0)
        self.assertGreater(result["critical"], 0)

    def test_25k_all_open_no_impact(self):
        rfis = [RFI(f"R{i}", f"Sub {i}", date(2026, 6, 1), date(2026, 6, 8)) for i in range(25_000)]
        start = time.perf_counter()
        result = rfi_mod.portfolio(rfis, date(2026, 7, 1))
        elapsed = time.perf_counter() - start
        self.assertEqual(result["overdue"], 25_000)
        self.assertEqual(result["critical"], 0)  # no impact data
        self.assertLess(elapsed, 5.0)

class RFIPropertyTests(unittest.TestCase):
    def test_required_by_before_submitted_rejected(self):
        for _ in range(100):
            with self.assertRaises(ValueError):
                RFI("R1", "Sub", date(2026, 6, 10), date(2026, 6, 1))

    def test_negative_schedule_days_rejected(self):
        for _ in range(100):
            with self.assertRaises(ValueError):
                RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), estimated_schedule_days=-1)

    def test_nonfinite_cost_rejected(self):
        for v in ["Infinity", "NaN", "inf"]:
            with self.assertRaises(ValueError):
                RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), estimated_cost_impact=Decimal(v))

    def test_answered_requires_answered_on(self):
        for st in [RFIStatus.ANSWERED, RFIStatus.CLOSED]:
            with self.assertRaises(ValueError):
                RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), status=st)

    def test_answered_on_before_submitted_rejected(self):
        with self.assertRaises(ValueError):
            RFI("R1", "Sub", date(2026, 6, 10), date(2026, 6, 15), status=RFIStatus.ANSWERED, answered_on=date(2026, 6, 5))

    def test_as_of_before_submitted_rejected(self):
        with self.assertRaises(ValueError):
            rfi_mod.triage(RFI("R1", "Sub", date(2026, 7, 1), date(2026, 7, 8)), date(2026, 6, 1))

    def test_closed_rfi_never_overdue(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), status=RFIStatus.CLOSED, answered_on=date(2026, 6, 5))
        result = rfi_mod.triage(rfi, date(2026, 7, 15))
        self.assertEqual(result["priority"], "complete")
        self.assertEqual(result["days_overdue"], 0)

    def test_void_rfi_never_overdue(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), status=RFIStatus.VOID)
        result = rfi_mod.triage(rfi, date(2026, 7, 15))
        self.assertEqual(result["priority"], "complete")
        self.assertEqual(result["days_overdue"], 0)

    def test_unknown_impact_not_treated_as_zero(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8))
        result = rfi_mod.triage(rfi, date(2026, 6, 10))
        self.assertIn("impact_not_quantified", result["reasons"])

    def test_known_impact_does_not_flag_unknown(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), estimated_cost_impact=Decimal("5000"), estimated_schedule_days=3)
        result = rfi_mod.triage(rfi, date(2026, 6, 10))
        self.assertNotIn("impact_not_quantified", result["reasons"])

    def test_overdue_with_impact_is_critical(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), estimated_schedule_days=3)
        result = rfi_mod.triage(rfi, date(2026, 6, 10))
        self.assertEqual(result["priority"], "critical")

    def test_overdue_without_impact_is_high(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8))
        result = rfi_mod.triage(rfi, date(2026, 6, 10))
        self.assertEqual(result["priority"], "high")

    def test_due_soon_is_medium(self):
        rfi = RFI("R1", "Sub", date(2026, 7, 1), date(2026, 7, 8))
        result = rfi_mod.triage(rfi, date(2026, 7, 3))
        self.assertEqual(result["priority"], "medium")

    def test_far_from_due_is_normal(self):
        rfi = RFI("R1", "Sub", date(2026, 7, 1), date(2026, 7, 30))
        result = rfi_mod.triage(rfi, date(2026, 7, 3))
        self.assertEqual(result["priority"], "normal")

    def test_explicit_date_determines_result(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), estimated_schedule_days=3)
        r1 = rfi_mod.triage(rfi, date(2026, 6, 10))
        r2 = rfi_mod.triage(rfi, date(2026, 6, 10))
        self.assertEqual(r1, r2)

    def test_empty_number_rejected(self):
        with self.assertRaises(ValueError):
            RFI("", "Sub", date(2026, 6, 1), date(2026, 6, 8))
        with self.assertRaises(ValueError):
            RFI("  ", "Sub", date(2026, 6, 1), date(2026, 6, 8))

    def test_empty_subject_rejected(self):
        with self.assertRaises(ValueError):
            RFI("R1", "", date(2026, 6, 1), date(2026, 6, 8))

    def test_answered_rfi_age_uses_answered_on(self):
        rfi = RFI("R1", "Sub", date(2026, 6, 1), date(2026, 6, 8), status=RFIStatus.ANSWERED, answered_on=date(2026, 6, 5))
        result = rfi_mod.triage(rfi, date(2026, 7, 15))
        self.assertEqual(result["age_days"], 4)  # answered_on - submitted_on

class RFIFuzzTests(unittest.TestCase):
    def test_fuzz_1k_valid_rfis(self):
        rng = Random(SEED + 50)
        for i in range(1_000):
            sub = date(2026, 1, 1) + timedelta(days=rng.randint(0, 180))
            req = sub + timedelta(days=rng.randint(1, 30))
            rfi = RFI(f"RFI-{i}", f"Subject {i}", sub, req)
            result = rfi_mod.triage(rfi, date(2026, 7, 1))
            self.assertGreaterEqual(result["days_overdue"], 0)
            self.assertIn(result["priority"], ["normal", "medium", "high", "critical"])

    def test_fuzz_invalid_dates(self):
        rng = Random(SEED + 60)
        for _ in range(1_000):
            sub = date(2026, 6, 1) + timedelta(days=rng.randint(1, 30))
            req = sub - timedelta(days=rng.randint(1, 10))
            with self.assertRaises(ValueError):
                RFI("R1", "Sub", sub, req)

if __name__ == "__main__":
    unittest.main()
