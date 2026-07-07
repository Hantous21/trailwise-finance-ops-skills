from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "1_Trailwise_Toolkit/wip-schedule-generator/fixtures/input/wip_jobs.csv"
EXPECTED = ROOT / "1_Trailwise_Toolkit/wip-schedule-generator/fixtures/expected/wip_jobs.json"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


wip = load("wip_schedule_generator", "1_Trailwise_Toolkit/wip-schedule-generator/scripts/wip_schedule_generator.py")


def _by_job(report: dict) -> dict[str, dict]:
    return {row["job_number"]: row for row in report["jobs"]}


class WIPGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture_output(self):
        report = wip.run(wip.load_jobs(FIXTURE))
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["job_count"], 4)
        self.assertEqual(report["summary"]["jobs_flagged"], 3)
        self.assertEqual(report["summary"]["total_overbilled"], 42500.0)
        self.assertEqual(report["summary"]["total_underbilled"], 95000.0)
        self.assertEqual(report["summary"]["total_earned"], 1057500.0)
        self.assertEqual(report["summary"]["total_billed"], 1005000.0)

        jobs = _by_job(report)

        j101 = jobs["J-101"]
        self.assertEqual(j101["revised_contract"], 525000.0)
        self.assertEqual(j101["percent_complete"], 0.5)
        self.assertEqual(j101["earned_revenue"], 262500.0)
        self.assertEqual(j101["over_under"], 37500.0)
        self.assertEqual(j101["flags"], [])

        j102 = jobs["J-102"]
        self.assertEqual(j102["revised_contract"], 300000.0)
        self.assertEqual(j102["percent_complete"], 0.75)
        self.assertEqual(j102["earned_revenue"], 225000.0)
        self.assertEqual(j102["over_under"], -75000.0)
        self.assertEqual(j102["flags"], ["underbilled_above_threshold"])

        j103 = jobs["J-103"]
        self.assertEqual(j103["revised_contract"], 840000.0)
        self.assertEqual(j103["percent_complete"], 0.5)
        self.assertEqual(j103["earned_revenue"], 420000.0)
        self.assertEqual(j103["over_under"], -20000.0)
        self.assertEqual(j103["flags"], ["cost_overrun"])
        self.assertEqual(j103["estimated_gross_profit"], -60000.0)

        j104 = jobs["J-104"]
        self.assertEqual(j104["revised_contract"], 150000.0)
        self.assertEqual(j104["raw_percent_complete"], 1.05)
        self.assertEqual(j104["percent_complete"], 1.0)
        self.assertEqual(j104["earned_revenue"], 150000.0)
        self.assertEqual(j104["over_under"], 5000.0)
        self.assertEqual(
            sorted(j104["flags"]),
            ["billed_over_contract", "percent_complete_over_100"],
        )

        # golden file comparison (after stripping as_of which is today's date)
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(golden["summary"].pop("as_of"), report["summary"].pop("as_of"))
        self.assertEqual(report, golden)


class WIPEdgeCases(unittest.TestCase):
    def test_zero_estimated_total_cost_raises(self):
        job = wip.WIPJob("J-1", "x", 100.0, 0.0, 0.0, 50.0, 0.0)
        with self.assertRaisesRegex(ValueError, "estimated_total_cost"):
            wip.evaluate(job)

    def test_negative_estimated_total_cost_raises(self):
        with self.assertRaisesRegex(ValueError, "estimated_total_cost"):
            wip.WIPJob("J-1", "x", 100.0, 0.0, -10.0, 5.0, 0.0)

    def test_zero_estimated_total_cost_raises_from_evaluate(self):
        with self.assertRaisesRegex(ValueError, "estimated_total_cost"):
            wip.evaluate(wip.WIPJob("J-1", "x", 100.0, 0.0, 0.0, 5.0, 0.0))

    def test_empty_csv_returns_empty_report(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.csv"
            p.write_text("job_number,job_name,contract_amount,approved_change_orders,estimated_total_cost,cost_to_date,billed_to_date\n",
                         encoding="utf-8")
            report = wip.run(wip.load_jobs(p))
        self.assertEqual(report["jobs"], [])
        self.assertEqual(report["summary"]["job_count"], 0)
        self.assertEqual(report["summary"]["jobs_flagged"], 0)
        self.assertEqual(report["summary"]["total_overbilled"], 0.0)
        self.assertEqual(report["summary"]["total_underbilled"], 0.0)

    def test_underbilling_threshold_boundary(self):
        # Build a job where earned = 50000 exactly, billed controls over_under.
        # cost_to_date / estimated = 0.05 -> earned = 50000 (no rounding noise).
        # billed 25000.00 -> over_under -25000.00 -> not flagged (threshold is strict >).
        job = wip.WIPJob("J", "x", 1000000.0, 0.0, 1000000.0, 50000.0, 25000.0)
        result = wip.evaluate(job)
        self.assertEqual(result["over_under"], -25000.0)
        self.assertNotIn("underbilled_above_threshold", result["flags"])
        # billed 24999.99 -> over_under -25000.01 -> flagged.
        job2 = wip.WIPJob("J", "x", 1000000.0, 0.0, 1000000.0, 50000.0, 24999.99)
        result2 = wip.evaluate(job2)
        self.assertEqual(result2["over_under"], -25000.01)
        self.assertIn("underbilled_above_threshold", result2["flags"])


if __name__ == "__main__":
    unittest.main()
