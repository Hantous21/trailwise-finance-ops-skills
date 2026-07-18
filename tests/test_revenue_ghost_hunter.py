from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    "8_SMB_Operations/revenue-ghost-hunter/scripts/revenue_ghost_hunter.py"
)
INPUT = ROOT / "8_SMB_Operations/revenue-ghost-hunter/fixtures/input/ghosts.csv"
EXPECTED = (
    ROOT
    / "8_SMB_Operations/revenue-ghost-hunter/fixtures/expected/ghosts_report.json"
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ghosts = load("revenue_ghost_hunter", SCRIPT)
AS_OF = date(2026, 7, 1)


class GhostHunterGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture(self):
        report = ghosts.evaluate(ghosts.load_ghosts(INPUT), AS_OF)
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)

    def test_hard_no_excluded_from_dollars_and_size_scale(self):
        report = ghosts.evaluate(ghosts.load_ghosts(INPUT), AS_OF)
        ranked = {row["who"]: row for row in report["ranked"]}
        self.assertEqual(ranked["Hard No Inc"]["queue"], "do-not-chase")
        self.assertEqual(ranked["Acme Roofing"]["components"]["size"], 30.0)
        self.assertEqual(report["dollars_at_risk"], 22000.0)
        self.assertEqual(report["queue_counts"]["hot"], 1)
        self.assertEqual(report["queue_counts"]["warm"], 2)
        self.assertEqual(report["queue_counts"]["cold"], 1)
        self.assertEqual(report["queue_counts"]["do-not-chase"], 1)


class GhostHunterEdgeCases(unittest.TestCase):
    def test_queue_thresholds(self):
        max_amount = 1000.0
        hot = ghosts.Ghost(
            "H", "o", 1000, None, AS_OF, "e", "noop", "", 10, 10, 0
        )
        # force valid status
        hot.status_guess = "no-response"
        scored = ghosts.score_ghost(hot, AS_OF, max_amount)
        self.assertEqual(scored.queue, "hot")
        self.assertGreaterEqual(scored.score, 70)

        cold = ghosts.Ghost(
            "C", "o", 100, AS_OF, date(2026, 1, 1), "e", "no-response", "", 0, 0, 10
        )
        scored_c = ghosts.score_ghost(cold, AS_OF, max_amount)
        self.assertEqual(scored_c.queue, "cold")


if __name__ == "__main__":
    unittest.main()
