from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "6_Contractor_Operations/bid-bond-gate/scripts/bid_bond_gate.py"
INPUT = ROOT / "6_Contractor_Operations/bid-bond-gate/fixtures/input/bids.csv"
EXPECTED = (
    ROOT
    / "6_Contractor_Operations/bid-bond-gate/fixtures/expected/bids_report.json"
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


gate = load("bid_bond_gate", SCRIPT)


class BidBondGateGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture(self):
        with INPUT.open(newline="", encoding="utf-8") as handle:
            import csv

            rows = list(csv.DictReader(handle))
        report = gate.evaluate(rows, cash_on_hand=120000.0)
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)
        self.assertEqual(report["counts"]["BID"], 2)
        self.assertEqual(report["counts"]["NO-BID"], 1)
        self.assertEqual(report["counts"]["BID-WITH-CONDITIONS"], 1)


class BidBondGateEdgeCases(unittest.TestCase):
    def test_cash_storm_triggers_no_bid(self):
        row = {
            "name": "cash trap",
            "contract_value": "100000",
            "pursuit_hours": "10",
            "expected_margin_pct": "10",
            "capacity_strain": "2",
            "mobilization_cash": "90000",
            "weeks_to_first_pay": "4",
            "weekly_fixed_burn": "10000",
            "landmine_count": "0",
            "contract_known": "yes",
            "political_override": "no",
        }
        out = gate.evaluate_row(row, cash_on_hand=100000.0)
        # buffer = (100k-90k)/10k = 1 week -> NO-BID
        self.assertEqual(out["verdict"], "NO-BID")
        self.assertLess(out["buffer_weeks_after_mob"], 2.0)

    def test_unknown_contract_is_conditions_not_clean_bid(self):
        row = {
            "name": "mystery",
            "contract_value": "100000",
            "pursuit_hours": "5",
            "expected_margin_pct": "12",
            "capacity_strain": "2",
            "mobilization_cash": "10000",
            "weeks_to_first_pay": "3",
            "weekly_fixed_burn": "10000",
            "landmine_count": "0",
            "contract_known": "no",
            "political_override": "no",
        }
        out = gate.evaluate_row(row, cash_on_hand=200000.0)
        self.assertEqual(out["verdict"], "BID-WITH-CONDITIONS")


if __name__ == "__main__":
    unittest.main()
