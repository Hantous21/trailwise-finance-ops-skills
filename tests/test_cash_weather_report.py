from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "8_SMB_Operations/cash-weather-report/scripts/cash_weather_report.py"
INPUT = ROOT / "8_SMB_Operations/cash-weather-report/fixtures/input/events.csv"
EXPECTED = (
    ROOT
    / "8_SMB_Operations/cash-weather-report/fixtures/expected/weather_report.json"
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


weather = load("cash_weather_report", SCRIPT)
AS_OF = date(2026, 7, 1)


class CashWeatherGoldenTests(unittest.TestCase):
    def test_golden_matches_fixture(self):
        report = weather.evaluate(
            weather.load_events(INPUT), 50000.0, 8000.0, AS_OF
        )
        golden = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(report, golden)
        self.assertEqual(report["overall_weather"], "cloudy")
        self.assertEqual(report["storm_windows"], [])


class CashWeatherEdgeCases(unittest.TestCase):
    def test_storm_when_balance_below_safety_floor(self):
        events = [
            {
                "date": date(2026, 7, 2),
                "amount": -30000.0,
                "lane": "committed",
                "label": "big pay",
            }
        ]
        report = weather.evaluate(events, opening=20000.0, fixed_weekly=8000.0, as_of=AS_OF)
        self.assertEqual(report["weeks"][0]["weather"], "storm")
        self.assertTrue(report["storm_windows"])

    def test_hoped_makes_cloudy_even_with_high_cover(self):
        events = [
            {
                "date": date(2026, 7, 3),
                "amount": 9000.0,
                "lane": "hoped",
                "label": "maybe",
            }
        ]
        report = weather.evaluate(events, opening=100000.0, fixed_weekly=8000.0, as_of=AS_OF)
        self.assertEqual(report["weeks"][0]["weather"], "cloudy")
        self.assertEqual(report["weeks"][0]["hoped_inflow"], 9000.0)

    def test_fixed_weekly_must_be_positive(self):
        with self.assertRaises(ValueError):
            weather.evaluate([], opening=1.0, fixed_weekly=0.0, as_of=AS_OF)


if __name__ == "__main__":
    unittest.main()
