from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TXNS = ROOT / "1_Trailwise_Toolkit/job-cost-allocator/fixtures/input/transactions.csv"
RULES = ROOT / "1_Trailwise_Toolkit/job-cost-allocator/fixtures/input/allocation_rules.csv"
EXPECTED = ROOT / "1_Trailwise_Toolkit/job-cost-allocator/fixtures/expected/allocations.json"
SCRIPT = ROOT / "1_Trailwise_Toolkit/job-cost-allocator/scripts/job_cost_allocator.py"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


alloc = load("job_cost_allocator", "1_Trailwise_Toolkit/job-cost-allocator/scripts/job_cost_allocator.py")


def _by_id(report: dict) -> dict[str, dict]:
    return {r["txn_id"]: r for r in report["rows"]}


class AllocatorGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture_output(self):
        txns = alloc.load_transactions(TXNS)
        rules = alloc.load_rules(RULES)
        report = alloc.allocate(txns, rules)
        rows = _by_id(report)

        self.assertEqual(rows["T1"]["job_number"], "J-101")
        self.assertEqual(rows["T1"]["cost_code"], "22-100")
        self.assertEqual(rows["T2"]["job_number"], "J-101")
        self.assertEqual(rows["T2"]["cost_code"], "01-500")
        self.assertEqual(rows["T3"]["job_number"], "J-103")
        self.assertEqual(rows["T3"]["cost_code"], "03-200")
        self.assertEqual(rows["T4"]["job_number"], "OVERHEAD")
        self.assertEqual(rows["T4"]["cost_code"], "00-300")
        # T5: vendor ferguson (p1) beats description rebar (p3) — precedence test
        self.assertEqual(rows["T5"]["job_number"], "J-101")
        self.assertEqual(rows["T5"]["cost_code"], "22-100")
        self.assertEqual(rows["T5"]["rule_priority"], 1)
        # T6, T7: unallocated
        self.assertEqual(rows["T6"]["status"], "unallocated")
        self.assertEqual(rows["T7"]["status"], "unallocated")
        # T8: vendor sunbelt (p2) beats description fuel (p4)
        self.assertEqual(rows["T8"]["job_number"], "J-101")
        self.assertEqual(rows["T8"]["cost_code"], "01-500")
        self.assertEqual(rows["T8"]["rule_priority"], 2)

        self.assertEqual(report["allocated_count"], 6)
        self.assertEqual(report["unallocated_count"], 2)
        self.assertEqual(report["allocated_pct"], 75.0)
        self.assertEqual(report["by_job"], {"J-101": 5520.0, "J-103": 4200.0, "OVERHEAD": 180.0})
        self.assertEqual(report["review_queue_total"], 1760.0)

        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)

    def test_min_allocated_pct_90_exits_1(self):
        # CLI: --min-allocated-pct 90 with 75% allocation -> exit 1
        r = subprocess.run(
            ["python3", str(SCRIPT), str(TXNS), str(RULES), "--min-allocated-pct", "90"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL", r.stderr)

    def test_default_min_zero_exits_0(self):
        r = subprocess.run(
            ["python3", str(SCRIPT), str(TXNS), str(RULES)],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0)


class AllocatorEdgeCases(unittest.TestCase):
    def test_empty_rules_everything_unallocated(self):
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "rules.csv"
            rules.write_text("priority,match_field,pattern,job_number,cost_code\n", encoding="utf-8")
            txns = alloc.load_transactions(TXNS)
            r = alloc.load_rules(rules)
            report = alloc.allocate(txns, r)
        self.assertEqual(report["allocated_count"], 0)
        self.assertEqual(report["unallocated_count"], 8)
        self.assertEqual(report["allocated_pct"], 0.0)
        self.assertEqual(report["by_job"], {})

    def test_unknown_match_field_raises(self):
        with self.assertRaisesRegex(ValueError, "unknown match_field"):
            alloc.Rule(1, "narrative", "x", "J-1", "00-100", order=0)

    def test_idempotent(self):
        # Re-running the same input must produce the same output (byte-for-byte per plan).
        txns1 = alloc.load_transactions(TXNS)
        rules1 = alloc.load_rules(RULES)
        a = alloc.allocate(txns1, rules1)
        txns2 = alloc.load_transactions(TXNS)
        rules2 = alloc.load_rules(RULES)
        b = alloc.allocate(txns2, rules2)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
