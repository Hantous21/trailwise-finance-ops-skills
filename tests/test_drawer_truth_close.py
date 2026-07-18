from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "7_Restaurant_Operations/drawer-truth-close/scripts/drawer_truth_close.py"
INPUT = ROOT / "7_Restaurant_Operations/drawer-truth-close/fixtures/input/closes.csv"
EXPECTED = (
    ROOT
    / "7_Restaurant_Operations/drawer-truth-close/fixtures/expected/closes_report.json"
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


drawer = load("drawer_truth_close", SCRIPT)


class DrawerTruthGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture(self):
        report = drawer.evaluate(drawer.load_closes(INPUT))
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)
        self.assertEqual(report["action_counts"]["ok"], 1)
        self.assertEqual(report["action_counts"]["recount"], 1)
        self.assertEqual(report["action_counts"]["dual_count"], 1)
        self.assertEqual(report["action_counts"]["escalate"], 1)

    def test_default_thresholds_replace_placeholders(self):
        self.assertEqual(drawer.DEFAULT_RECOUNT_MAX, 5.0)
        self.assertEqual(drawer.DEFAULT_DUAL_COUNT_MIN, 20.0)
        self.assertEqual(drawer.DEFAULT_ESCALATE_MIN, 50.0)


class DrawerTruthEdgeCases(unittest.TestCase):
    def test_classify_action_boundaries(self):
        self.assertEqual(drawer.classify_action(5.0), "ok")
        self.assertEqual(drawer.classify_action(5.01), "recount")
        self.assertEqual(drawer.classify_action(20.0), "dual_count")
        self.assertEqual(drawer.classify_action(50.0), "escalate")

    def test_unassigned_owner_flagged(self):
        report = drawer.evaluate(drawer.load_closes(INPUT))
        unassigned = [d for d in report["drawers"] if d["owner"] == "UNASSIGNED"]
        self.assertEqual(len(unassigned), 1)
        self.assertTrue(unassigned[0]["owner_required"])


if __name__ == "__main__":
    unittest.main()
