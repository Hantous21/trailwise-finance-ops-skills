"""
Tests for tip-pool-calculator.

Goldens (from prompt, exact equality on cents):

Day 2026-06-05, pool 600.00, weighted 27.0:
  Alice 177.78, Ben 133.33, Cara 222.22, Dev 66.67 (sum = 600.00)

Day 2026-06-06, pool 660.00, weighted 25.5, Mia excluded:
  Alice 181.18, Ben 181.17, Cara 194.12, Eli 103.53 (sum = 660.00)
  Alice gets extra penny on alphabetical tie-break

Week totals: Alice 358.96, Ben 314.50, Cara 416.34, Dev 66.67, Eli 103.53
Grand total: 1,260.00

Boundary: manager exclusion warning; unknown role -> error exit.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = (
    REPO_ROOT
    / "7_Restaurant_Operations"
    / "tip-pool-calculator"
    / "scripts"
    / "tip_pool_calculator.py"
)
SHIFTS_CSV = (
    REPO_ROOT
    / "7_Restaurant_Operations"
    / "tip-pool-calculator"
    / "fixtures"
    / "input"
    / "shifts.csv"
)
TIPS_CSV = (
    REPO_ROOT
    / "7_Restaurant_Operations"
    / "tip-pool-calculator"
    / "fixtures"
    / "input"
    / "tips.csv"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "tip_pool_calculator_under_test", str(SCRIPT_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tip_pool_calculator_under_test"] = module
    spec.loader.exec_module(module)
    return module


m = _load_module()

DEFAULT_POINTS = m.DEFAULT_POINTS


@pytest.fixture(scope="module")
def results():
    shifts = m.load_shifts(SHIFTS_CSV)
    tips = m.load_tips(TIPS_CSV)
    return m.calculate(shifts, tips, dict(DEFAULT_POINTS))


def test_day_0605_pool(results):
    day = results[0]
    assert day.date == date(2026, 6, 5)
    assert day.pool == pytest.approx(600.00)

    payouts = day.payouts
    assert payouts["Alice"] == pytest.approx(177.78)
    assert payouts["Ben"] == pytest.approx(133.33)
    assert payouts["Cara"] == pytest.approx(222.22)
    assert payouts["Dev"] == pytest.approx(66.67)

    # Sum must equal pool exactly
    assert round(sum(payouts.values()), 2) == pytest.approx(600.00)


def test_day_0606_pool(results):
    day = results[1]
    assert day.date == date(2026, 6, 6)
    assert day.pool == pytest.approx(660.00)

    payouts = day.payouts
    assert payouts["Alice"] == pytest.approx(181.18)
    assert payouts["Ben"] == pytest.approx(181.17)
    assert payouts["Cara"] == pytest.approx(194.12)
    assert payouts["Eli"] == pytest.approx(103.53)

    # Alice and Ben have identical role and hours; Alice gets extra penny
    # (alphabetical tie-break). Assert explicitly.
    assert payouts["Alice"] > payouts["Ben"]

    # Sum equals pool exactly
    assert round(sum(payouts.values()), 2) == pytest.approx(660.00)


def test_day_0606_excluded(results):
    day = results[1]
    assert "Mia" in day.excluded
    assert any("manager" in w.lower() or "Mia" in w for w in day.warnings)


def test_week_totals(results):
    totals = m.week_totals(results)
    assert totals["Alice"] == pytest.approx(358.96)
    assert totals["Ben"] == pytest.approx(314.50)
    assert totals["Cara"] == pytest.approx(416.34)
    assert totals["Dev"] == pytest.approx(66.67)
    assert totals["Eli"] == pytest.approx(103.53)

    grand = sum(totals.values())
    assert grand == pytest.approx(1260.00)


def test_grand_total_exact():
    """Grand total must match 600 + 660 = 1260 exactly."""
    shifts = m.load_shifts(SHIFTS_CSV)
    tips = m.load_tips(TIPS_CSV)
    results = m.calculate(shifts, tips, dict(DEFAULT_POINTS))
    totals = m.week_totals(results)
    assert round(sum(totals.values()), 2) == 1260.00


def test_no_eligible_shifts_errors():
    """A tips.csv date with no eligible shifts is an error."""
    tips = [m.TipDay(date=date(2026, 7, 1), cash_tips=100.0, card_tips=200.0)]
    shifts: list = []
    with pytest.raises(SystemExit):
        m.calculate(shifts, tips, dict(DEFAULT_POINTS))


def test_unknown_role_errors():
    """An unknown role in shifts.csv should cause SystemExit."""
    shifts = [
        m.Shift(date=date(2026, 7, 1), employee="X", role="wizard", hours=8),
    ]
    tips = [m.TipDay(date=date(2026, 7, 1), cash_tips=100.0, card_tips=200.0)]
    with pytest.raises(SystemExit):
        m.calculate(shifts, tips, dict(DEFAULT_POINTS))


def test_penny_tie_break_alphabetical():
    """Two employees with identical weight: alphabetical tie-break for leftover penny."""
    shifts = [
        m.Shift(date=date(2026, 7, 1), employee="Zara", role="server", hours=8),
        m.Shift(date=date(2026, 7, 1), employee="Aaron", role="server", hours=8),
    ]
    tips = [m.TipDay(date=date(2026, 7, 1), cash_tips=0.0, card_tips=0.01)]
    results = m.calculate(shifts, tips, dict(DEFAULT_POINTS))
    payouts = results[0].payouts
    # Only 1 cent in pool; both get floor(0.005) = 0.00, 1 penny leftover.
    # Aaron is alphabetical before Zara -> Aaron gets the penny.
    assert payouts["Aaron"] == 0.01
    assert payouts["Zara"] == 0.00


def test_custom_points():
    """Custom role points override."""
    shifts = [
        m.Shift(date=date(2026, 7, 1), employee="A", role="server", hours=5),
        m.Shift(date=date(2026, 7, 1), employee="B", role="bartender", hours=5),
    ]
    tips = [m.TipDay(date=date(2026, 7, 1), cash_tips=100.00, card_tips=0.0)]
    # default: server=1.0, bartender=1.25 -> A gets 100 * 5/11.25, B gets 100 * 6.25/11.25
    custom = {"server": 1.0, "bartender": 2.0}
    results = m.calculate(shifts, tips, custom)
    payouts = results[0].payouts
    # A weight = 5, B weight = 10; total=15
    # A raw = 100 * 5/15 = 33.333..., B raw = 100 * 10/15 = 66.666...
    # floor: A=33.33, B=66.66, total=99.99, 1 penny leftover
    # remainders: A=0.0033..., B=0.0066... -> B gets penny
    assert payouts["A"] == 33.33
    assert payouts["B"] == 66.67
    assert round(sum(payouts.values()), 2) == 100.00