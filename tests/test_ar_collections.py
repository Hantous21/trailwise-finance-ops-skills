from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "1_Trailwise_Toolkit/ar-collections-automation"
EXPECTED = json.loads(
    (SKILL_DIR / "fixtures/expected/ar_aging_summary.json").read_text(encoding="utf-8")
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ar = load(
    "ar_collections",
    "1_Trailwise_Toolkit/ar-collections-automation/scripts/ar_collections.py",
)


def _manager(as_of: date = date(2026, 6, 30)) -> ar.CollectionsManager:
    return ar.CollectionsManager.from_csv(
        SKILL_DIR / "fixtures/input/invoices.csv", as_of=as_of
    )


class ARCollectionsDashboardTests(unittest.TestCase):
    def test_dashboard_matches_golden_fixture(self):
        mgr = _manager()
        dash = mgr.get_collections_dashboard()
        self.assertEqual(dash["total_outstanding"], EXPECTED["total_outstanding"])
        self.assertEqual(dash["overdue_amount"], EXPECTED["overdue_amount"])
        self.assertEqual(dash["aging_summary"], EXPECTED["aging_summary"])
        self.assertEqual(dash["at_risk_count"], EXPECTED["at_risk_count"])
        self.assertEqual(dash["dunning_stages"], EXPECTED["dunning_stages"])
        self.assertEqual(dash["top_risk_clients"], EXPECTED["top_risk_clients"])

    def test_dunning_stages_present_and_correct(self):
        stages = _manager().get_dunning_stages()
        # All open/partial invoices appear; paid invoices are excluded
        ids = [s["invoice"] for s in stages]
        self.assertEqual(ids, ["INV-1002", "INV-1003", "INV-1004", "INV-1006"])
        by_inv = {s["invoice"]: s for s in stages}
        self.assertEqual(by_inv["INV-1002"]["stage"], "none")
        self.assertEqual(by_inv["INV-1003"]["stage"], "final")
        self.assertEqual(by_inv["INV-1004"]["stage"], "final")
        self.assertEqual(by_inv["INV-1006"]["stage"], "escalated")
        # Partial payment surfaces the remaining balance
        self.assertEqual(by_inv["INV-1004"]["balance"], 16000)
        self.assertNotIn("balance", by_inv["INV-1002"])


class ARCollectionsAsOfTests(unittest.TestCase):
    def test_as_of_controls_days_past_due_deterministically(self):
        inv = ar.Invoice(
            "INV-X", "C1", "Client", date(2026, 1, 1), date(2026, 6, 1), 1000,
            as_of=date(2026, 6, 30),
        )
        self.assertEqual(inv.days_past_due, 29)
        self.assertEqual(inv.dunning_stage, ar.DunningStage.FIRM)
        self.assertEqual(inv.aging_bucket, ar.AgingBucket.CURRENT)

    def test_as_of_propagates_from_manager_to_invoices(self):
        mgr = ar.CollectionsManager(as_of=date(2026, 6, 30))
        inv = ar.Invoice(
            "INV-Y", "C1", "Client", date(2026, 3, 1), date(2026, 3, 15), 5000,
        )
        mgr.add_invoice(inv)
        # 2026-06-30 - 2026-03-15 = 107 days past due
        self.assertEqual(inv.days_past_due, 107)
        self.assertEqual(inv.dunning_stage, ar.DunningStage.ESCALATED)
        self.assertEqual(inv.aging_bucket, ar.AgingBucket.BUCKET_90_PLUS)

    def test_different_as_of_changes_buckets(self):
        early = ar.CollectionsManager.from_csv(
            SKILL_DIR / "fixtures/input/invoices.csv", as_of=date(2026, 6, 1)
        )
        late = _manager(as_of=date(2026, 6, 30))
        early_aging = early.get_aging_report()
        late_aging = late.get_aging_report()
        # On 2026-06-01: INV-1002 (0 dpd) and INV-1003 (17 dpd) are both
        # within the 0-30 day current bucket, totalling 43000.
        self.assertEqual(early_aging["by_bucket"]["current"]["amount"], 43000)
        # By 2026-06-30, more invoices have aged into later buckets
        self.assertGreater(late_aging["overdue_amount"], early_aging["overdue_amount"])


if __name__ == "__main__":
    unittest.main()
