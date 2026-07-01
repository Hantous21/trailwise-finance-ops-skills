"""Stress, property, and fuzz tests for submittal-tracker. Seed: 20260701."""
from __future__ import annotations
import importlib.util, sys, time, unittest
from datetime import date, timedelta
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

sub_mod = load("submittal_tracker", "6_Contractor_Operations/submittal-tracker/scripts/submittal_tracker.py")
Submittal = sub_mod.Submittal
SubmittalStatus = sub_mod.SubmittalStatus
SEED = 20260701

class SubmittalLoadTests(unittest.TestCase):
    def test_25k_mixed_submittals(self):
        rng = Random(SEED)
        statuses = list(SubmittalStatus)
        items = []
        for i in range(25_000):
            req_site = date(2026, 8, 1) + timedelta(days=rng.randint(0, 120))
            fab = rng.randint(5, 30)
            rev = rng.randint(5, 20)
            st = rng.choice(statuses)
            sub_on = req_site - timedelta(days=rng.randint(fab, fab+rev+5)) if st not in {SubmittalStatus.NOT_SUBMITTED} else None
            dec_on = sub_on + timedelta(days=rng.randint(1, rev)) if st in {SubmittalStatus.APPROVED, SubmittalStatus.REJECTED} and sub_on else None
            items.append(Submittal(f"S-{i}", f"Item {i}", req_site, fab, rev, st, sub_on, dec_on, rng.randint(0, 3)))
        start = time.perf_counter()
        results = [sub_mod.evaluate(s, date(2026, 7, 1)) for s in items]
        elapsed = time.perf_counter() - start
        self.assertEqual(len(results), 25_000)
        self.assertLess(elapsed, 5.0, f"25K took {elapsed:.3f}s")
        risks = {r["risk"] for r in results}
        self.assertGreater(len(risks), 1)

class SubmittalPropertyTests(unittest.TestCase):
    def test_required_submission_subtracts_lead_and_review(self):
        s = Submittal("S1", "Steel", date(2026, 8, 1), 20, 10)
        self.assertEqual(s.required_submission_date, date(2026, 7, 2))

    def test_negative_lead_rejected(self):
        with self.assertRaises(ValueError):
            Submittal("S1", "Steel", date(2026, 8, 1), -1, 10)

    def test_negative_review_rejected(self):
        with self.assertRaises(ValueError):
            Submittal("S1", "Steel", date(2026, 8, 1), 10, -1)

    def test_negative_revision_rejected(self):
        with self.assertRaises(ValueError):
            Submittal("S1", "Steel", date(2026, 8, 1), 10, 10, revision=-1)

    def test_submitted_requires_submitted_on(self):
        for st in [SubmittalStatus.SUBMITTED, SubmittalStatus.UNDER_REVIEW]:
            with self.assertRaises(ValueError):
                Submittal("S1", "Steel", date(2026, 8, 1), 10, 10, status=st)

    def test_approved_requires_decided_on(self):
        with self.assertRaises(ValueError):
            Submittal("S1", "Steel", date(2026, 8, 1), 10, 10, status=SubmittalStatus.APPROVED)
        with self.assertRaises(ValueError):
            Submittal("S1", "Steel", date(2026, 8, 1), 10, 10, status=SubmittalStatus.REJECTED)

    def test_decided_before_submitted_rejected(self):
        with self.assertRaises(ValueError):
            Submittal("S1", "Steel", date(2026, 8, 1), 10, 10,
                       status=SubmittalStatus.APPROVED, submitted_on=date(2026, 7, 10), decided_on=date(2026, 7, 5))

    def test_approved_is_complete(self):
        s = Submittal("S1", "Steel", date(2026, 8, 1), 10, 10,
                       status=SubmittalStatus.APPROVED, submitted_on=date(2026, 6, 1), decided_on=date(2026, 6, 10))
        self.assertEqual(sub_mod.evaluate(s, date(2026, 7, 1))["risk"], "complete")

    def test_late_unsubmitted_is_critical(self):
        s = Submittal("S1", "Steel", date(2026, 8, 1), 20, 10)
        self.assertEqual(sub_mod.evaluate(s, date(2026, 7, 3))["risk"], "critical")

    def test_overdue_review_is_critical(self):
        s = Submittal("S1", "Steel", date(2026, 9, 1), 20, 10,
                       status=SubmittalStatus.UNDER_REVIEW, submitted_on=date(2026, 7, 1))
        self.assertIn("review_overdue", sub_mod.evaluate(s, date(2026, 7, 12))["reasons"])

    def test_material_on_site_without_approval_is_critical(self):
        s = Submittal("S1", "Steel", date(2026, 6, 1), 10, 10)
        result = sub_mod.evaluate(s, date(2026, 7, 1))
        self.assertEqual(result["risk"], "critical")
        self.assertIn("material_required_on_site_without_approval", result["reasons"])

    def test_revise_resubmit_at_boundary(self):
        s = Submittal("S1", "Steel", date(2026, 8, 1), 20, 10,
                       status=SubmittalStatus.REVISE_RESUBMIT, submitted_on=date(2026, 6, 1))
        # required_submission = 8/1 - 30 = 7/2
        self.assertEqual(sub_mod.evaluate(s, date(2026, 7, 2))["risk"], "critical")
        self.assertEqual(sub_mod.evaluate(s, date(2026, 7, 1))["risk"], "high")

    def test_submission_due_within_7_days(self):
        s = Submittal("S1", "Steel", date(2026, 8, 1), 20, 10)
        # required_submission = 7/2, so 7 days before = 6/25
        result = sub_mod.evaluate(s, date(2026, 6, 26))
        self.assertIn("submission_due_within_seven_days", result["reasons"])

    def test_empty_number_rejected(self):
        with self.assertRaises(ValueError):
            Submittal("", "Steel", date(2026, 8, 1), 10, 10)

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            Submittal("S1", "", date(2026, 8, 1), 10, 10)

    def test_explicit_date_determines_result(self):
        s = Submittal("S1", "Steel", date(2026, 8, 1), 20, 10)
        r1 = sub_mod.evaluate(s, date(2026, 7, 1))
        r2 = sub_mod.evaluate(s, date(2026, 7, 1))
        self.assertEqual(r1, r2)

    def test_approved_overrides_on_site_check(self):
        s = Submittal("S1", "Steel", date(2026, 6, 1), 10, 10,
                       status=SubmittalStatus.APPROVED, submitted_on=date(2026, 4, 1), decided_on=date(2026, 4, 15))
        result = sub_mod.evaluate(s, date(2026, 7, 1))
        self.assertEqual(result["risk"], "complete")
        self.assertNotIn("material_required_on_site_without_approval", result["reasons"])

class SubmittalFuzzTests(unittest.TestCase):
    def test_fuzz_1k_valid(self):
        rng = Random(SEED + 50)
        for i in range(1_000):
            req_site = date(2026, 9, 1) + timedelta(days=rng.randint(0, 90))
            fab = rng.randint(5, 30)
            rev = rng.randint(5, 20)
            s = Submittal(f"S{i}", f"Item {i}", req_site, fab, rev)
            result = sub_mod.evaluate(s, date(2026, 7, 1))
            self.assertIn(result["risk"], ["normal", "high", "critical"])

    def test_fuzz_invalid_negatives(self):
        rng = Random(SEED + 60)
        for _ in range(1_000):
            with self.assertRaises(ValueError):
                Submittal("S1", "Item", date(2026, 8, 1), -rng.randint(1, 10), 10)

if __name__ == "__main__":
    unittest.main()
