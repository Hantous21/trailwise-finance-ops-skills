from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "1_Trailwise_Toolkit" / "cash-flow-forecaster"
EXPECTED = json.loads(
    (SKILL_DIR / "fixtures" / "expected" / "cash_flow_forecast.json").read_text(
        encoding="utf-8"
    )
)
INPUT_CSV = SKILL_DIR / "fixtures" / "input" / "cash_events.csv"

PINNED_AS_OF = date(2026, 6, 30)
DEFAULT_OPENING = 50000.0
DEFAULT_WEEKS = 4


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


cff = load(
    "cash_flow_forecaster",
    "1_Trailwise_Toolkit/cash-flow-forecaster/scripts/cash_flow_forecaster.py",
)


def _run(as_of: date = PINNED_AS_OF, **kwargs):
    return cff.run_forecast(
        as_of=as_of,
        opening_balance=kwargs.pop("opening_balance", DEFAULT_OPENING),
        weeks=kwargs.pop("weeks", DEFAULT_WEEKS),
        csv_path=kwargs.pop("csv_path", INPUT_CSV),
    )


class GoldenFixtureTests(unittest.TestCase):
    def test_forecast_matches_expected_fixture(self):
        result = _run()
        self.assertEqual(result, EXPECTED)

    def test_start_date_is_day_after_as_of(self):
        result = _run()
        self.assertEqual(result["start_date"], "2026-07-01")
        self.assertEqual(
            date.fromisoformat(result["start_date"]),
            PINNED_AS_OF + timedelta(days=1),
        )

    def test_weekly_positions_count_matches_weeks(self):
        result = _run(weeks=4)
        self.assertEqual(len(result["weekly_positions"]), 4)
        self.assertEqual(result["weeks_projected"], 4)

    def test_as_of_is_deterministic_across_real_dates(self):
        """Pinning as_of must produce identical output regardless of today."""
        a = cff.run_forecast(
            as_of=PINNED_AS_OF, opening_balance=DEFAULT_OPENING,
            weeks=DEFAULT_WEEKS, csv_path=INPUT_CSV,
        )
        b = cff.run_forecast(
            as_of=PINNED_AS_OF, opening_balance=DEFAULT_OPENING,
            weeks=DEFAULT_WEEKS, csv_path=INPUT_CSV,
        )
        self.assertEqual(a, b)


class BalancePropertyTests(unittest.TestCase):
    def test_no_negative_balances_for_default_fixture(self):
        result = _run()
        closings = [w["closing"] for w in result["weekly_positions"]]
        for c in closings:
            self.assertGreaterEqual(c, 0, f"closing balance {c} is negative")
        self.assertEqual(result["shortfalls"], [])

    def test_peak_and_trough_match_weekly_closings(self):
        result = _run()
        closings = [w["closing"] for w in result["weekly_positions"]]
        self.assertEqual(result["peak_balance"], max(closings))
        self.assertEqual(result["trough_balance"], min(closings))

    def test_closing_balance_equals_last_weekly_closing(self):
        result = _run()
        self.assertEqual(
            result["closing_balance"],
            result["weekly_positions"][-1]["closing"],
        )

    def test_net_equals_inflows_minus_outflows(self):
        result = _run()
        for w in result["weekly_positions"]:
            self.assertAlmostEqual(
                w["net"], round(w["inflows"] - w["outflows"], 2), places=2
            )

    def test_running_balance_is_contiguous(self):
        result = _run()
        prev_closing = result["opening_balance"]
        for w in result["weekly_positions"]:
            self.assertAlmostEqual(
                w["closing"], round(prev_closing + w["net"], 2), places=2
            )
            prev_closing = w["closing"]

    def test_burn_rate_is_average_weekly_outflow(self):
        result = _run()
        outflows = [w["outflows"] for w in result["weekly_positions"]]
        self.assertEqual(
            result["burn_rate"],
            round(sum(outflows) / len(outflows), 2),
        )


class ShortfallDetectionTests(unittest.TestCase):
    def test_no_shortfalls_when_balance_stays_positive(self):
        result = _run(opening_balance=DEFAULT_OPENING)
        self.assertEqual(result["shortfalls"], [])

    def test_shortfall_detected_when_opening_balance_too_low(self):
        # With a tiny opening balance the first heavy outflow week goes negative.
        result = _run(opening_balance=5000)
        self.assertGreater(len(result["shortfalls"]), 0)
        first = result["shortfalls"][0]
        self.assertEqual(first["week_of"], "2026-07-01")
        self.assertGreater(first["deficit"], 0)
        self.assertIn("recommendation", first)

    def test_shortfall_recommendation_for_no_inflow_week(self):
        # Week of 2026-07-01 has zero inflows and heavy outflows. The engine
        # checks outflows > inflows*2 first, so this lands in the
        # "Large outflow" recommendation branch (0*2 == 0, outflows > 0).
        result = _run(opening_balance=5000)
        week_one = next(
            s for s in result["shortfalls"] if s["week_of"] == "2026-07-01"
        )
        self.assertEqual(week_one["inflows"], 0)
        self.assertGreater(week_one["outflows"], 0)
        self.assertIn("Large outflow", week_one["recommendation"])

    def test_shortfall_recommendation_tight_week_branch(self):
        # Construct a scenario where outflows <= inflows*2 but inflows > 0:
        # a "tight week". Add a small inflow in a high-outflow week via a
        # custom CSV on disk.
        import tempfile

        tmp = Path(tempfile.mkdtemp()) / "events.csv"
        tmp.write_text(
            "date,amount,direction,description,confidence,source\n"
            "2026-07-01,-8000,outflow,Payroll,1.0,payroll\n"
            "2026-07-01,4000,inflow,Partial client,0.8,client\n",
            encoding="utf-8",
        )
        result = _run(opening_balance=3000, csv_path=tmp)
        # week 0: inflows=4000, outflows=8000 -> 8000 > 4000*2? no (8000==8000)
        # so falls through to "Tight week" (inflows != 0).
        week_one = result["shortfalls"][0]
        self.assertGreater(week_one["inflows"], 0)
        self.assertLessEqual(week_one["outflows"], week_one["inflows"] * 2)
        self.assertIn("Tight week", week_one["recommendation"])


    def test_shortfall_deficit_is_absolute_closing(self):
        result = _run(opening_balance=5000)
        weekly = {w["week"]: w for w in result["weekly_positions"]}
        for s in result["shortfalls"]:
            self.assertEqual(
                s["deficit"], round(abs(weekly[s["week_of"]]["closing"]), 2)
            )

    def test_high_opening_balance_yields_zero_shortfalls(self):
        result = _run(opening_balance=1_000_000)
        self.assertEqual(result["shortfalls"], [])

    def test_all_shortfall_closings_are_negative(self):
        result = _run(opening_balance=5000)
        weekly = {w["week"]: w for w in result["weekly_positions"]}
        for s in result["shortfalls"]:
            self.assertLess(weekly[s["week_of"]]["closing"], 0)


class CsvLoaderTests(unittest.TestCase):
    def test_loader_treats_outflow_amounts_as_magnitudes(self):
        events = cff.load_events_from_csv(INPUT_CSV)
        for e in events:
            self.assertGreaterEqual(e.amount, 0)
        payroll = [e for e in events if e.source == "payroll"]
        self.assertTrue(payroll)
        self.assertEqual(payroll[0].amount, 8000)

    def test_loader_parses_direction_enum(self):
        events = cff.load_events_from_csv(INPUT_CSV)
        inflows = [e for e in events if e.direction == cff.CashFlowDirection.INFLOW]
        outflows = [e for e in events if e.direction == cff.CashFlowDirection.OUTFLOW]
        self.assertTrue(inflows)
        self.assertTrue(outflows)


class CLITests(unittest.TestCase):
    def test_cli_with_pinned_as_of_matches_fixture(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cff.main([
                "--as-of", "2026-06-30",
                "--input", str(INPUT_CSV),
                "--weeks", str(DEFAULT_WEEKS),
                "--opening-balance", str(DEFAULT_OPENING),
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload, EXPECTED)


if __name__ == "__main__":
    unittest.main()
