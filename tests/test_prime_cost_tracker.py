"""
Tests for prime-cost-tracker.

Goldens (from prompt, tolerance $0.01 / 0.01pt):

| week       | food_cogs | bev_cogs | total_labor | prime_cost | prime_pct | status | wow_delta |
|------------|-----------|----------|-------------|------------|-----------|--------|-----------|
| 2026-06-07 | 11,200.00 | 3,200.00 | 9,200.00    | 23,600.00  | 59.00     | ok     | null      |
| 2026-06-14 | 11,400.00 | 3,040.00 | 8,360.00    | 22,800.00  | 60.00     | ok     | +1.00     |
| 2026-06-21 | 11,700.00 | 2,880.00 | 8,640.00    | 23,220.00  | 64.50     | watch  | +4.50     |
| 2026-06-28 | 11,900.00 | 2,720.00 | 8,500.00    | 23,120.00  | 68.00     | over   | +3.50     |

Period: prime_pct 62.66 · status watch · rising_trend true · warnings []
Boundary: prime_pct exactly 60.00 -> ok; exactly 65.00 -> watch.
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
    / "prime-cost-tracker"
    / "scripts"
    / "prime_cost_tracker.py"
)
FIXTURE_CSV = (
    REPO_ROOT
    / "7_Restaurant_Operations"
    / "prime-cost-tracker"
    / "fixtures"
    / "input"
    / "weekly_pnl.csv"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "prime_cost_tracker_under_test", str(SCRIPT_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["prime_cost_tracker_under_test"] = module
    spec.loader.exec_module(module)
    return module


m = _load_module()


@pytest.fixture(scope="module")
def results():
    weeks = m.load_pnl(FIXTURE_CSV)
    return m.track_prime_cost(weeks)


def test_week_0607(results):
    r = results[0]
    assert r.week_ending == date(2026, 6, 7)
    assert r.food_cogs == pytest.approx(11200.00, abs=0.01)
    assert r.bev_cogs == pytest.approx(3200.00, abs=0.01)
    assert r.total_labor == pytest.approx(9200.00, abs=0.01)
    assert r.prime_cost == pytest.approx(23600.00, abs=0.01)
    assert r.prime_pct == pytest.approx(59.00, abs=0.01)
    assert r.status == "ok"
    assert r.wow_delta is None


def test_week_0614(results):
    r = results[1]
    assert r.week_ending == date(2026, 6, 14)
    assert r.food_cogs == pytest.approx(11400.00, abs=0.01)
    assert r.bev_cogs == pytest.approx(3040.00, abs=0.01)
    assert r.total_labor == pytest.approx(8360.00, abs=0.01)
    assert r.prime_cost == pytest.approx(22800.00, abs=0.01)
    assert r.prime_pct == pytest.approx(60.00, abs=0.01)
    assert r.status == "ok"
    assert r.wow_delta == pytest.approx(+1.00, abs=0.01)


def test_week_0621(results):
    r = results[2]
    assert r.week_ending == date(2026, 6, 21)
    assert r.food_cogs == pytest.approx(11700.00, abs=0.01)
    assert r.bev_cogs == pytest.approx(2880.00, abs=0.01)
    assert r.total_labor == pytest.approx(8640.00, abs=0.01)
    assert r.prime_cost == pytest.approx(23220.00, abs=0.01)
    assert r.prime_pct == pytest.approx(64.50, abs=0.01)
    assert r.status == "watch"
    assert r.wow_delta == pytest.approx(+4.50, abs=0.01)


def test_week_0628(results):
    r = results[3]
    assert r.week_ending == date(2026, 6, 28)
    assert r.food_cogs == pytest.approx(11900.00, abs=0.01)
    assert r.bev_cogs == pytest.approx(2720.00, abs=0.01)
    assert r.total_labor == pytest.approx(8500.00, abs=0.01)
    assert r.prime_cost == pytest.approx(23120.00, abs=0.01)
    assert r.prime_pct == pytest.approx(68.00, abs=0.01)
    assert r.status == "over"
    assert r.wow_delta == pytest.approx(+3.50, abs=0.01)


def test_period_summary(results):
    summary = m.summarize(results)
    assert summary["net_sales"] == pytest.approx(148000.00, abs=0.01)
    assert summary["food_cogs"] == pytest.approx(46200.00, abs=0.01)
    assert summary["food_pct"] == pytest.approx(31.22, abs=0.01)
    assert summary["bev_cogs"] == pytest.approx(11840.00, abs=0.01)
    assert summary["bev_pct"] == pytest.approx(8.00, abs=0.01)
    assert summary["total_labor"] == pytest.approx(34700.00, abs=0.01)
    assert summary["labor_pct"] == pytest.approx(23.45, abs=0.01)
    assert summary["prime_cost"] == pytest.approx(92740.00, abs=0.01)
    assert summary["prime_pct"] == pytest.approx(62.66, abs=0.01)
    assert summary["status"] == "watch"
    assert summary["rising_trend"] is True
    assert summary["warnings"] == []


def test_hardcoded_summary():
    """Quick manual check: the handoff says prime_pct 62.66, rising_trend true."""
    weeks = m.load_pnl(FIXTURE_CSV)
    results = m.track_prime_cost(weeks)
    summary = m.summarize(results)
    assert summary["prime_pct"] == pytest.approx(62.66, abs=0.01)
    assert summary["rising_trend"] is True
    assert summary["warnings"] == []


def test_boundary_60_ok():
    """prime_pct exactly 60.00 -> ok."""
    pw = m.PNLWeek(
        week_ending=date(2026, 7, 5),
        net_sales=10000.00,
        food_purchases=5000.00,
        food_inv_begin=1000.00,
        food_inv_end=1000.00,
        bev_purchases=800.00,
        bev_inv_begin=200.00,
        bev_inv_end=200.00,
        labor_foh=0.0,
        labor_boh=0.0,
        labor_salaried=0.0,
        payroll_taxes_benefits=0.0,
    )
    # food_cogs = 5000+1000-1000 = 5000; bev_cogs = 800+200-200 = 800
    # labor = 0; prime = 5800; net_sales = 10000; prime_pct = 58.00 -> ok
    # Let's tweak numbers so prime_pct = 60.00 exactly:
    # food_cogs=5000, bev_cogs=0, labor=1000. prime=6000. net_sales=10000 -> 60.00
    pw.food_purchases = 5000.0
    pw.food_inv_begin = 1000.0
    pw.food_inv_end = 1000.0
    pw.bev_purchases = 0.0
    pw.bev_inv_begin = 0.0
    pw.bev_inv_end = 0.0
    pw.labor_foh = 500.0
    pw.labor_boh = 500.0
    results = m.track_prime_cost([pw])
    assert results[0].prime_pct == pytest.approx(60.00, abs=0.01)
    assert results[0].status == "ok"


def test_boundary_65_watch():
    """prime_pct exactly 65.00 -> watch."""
    pw = m.PNLWeek(
        week_ending=date(2026, 7, 12),
        net_sales=10000.00,
        food_purchases=5000.00,
        food_inv_begin=1000.00,
        food_inv_end=1000.00,
        bev_purchases=0.0,
        bev_inv_begin=0.0,
        bev_inv_end=0.0,
        labor_foh=750.00,
        labor_boh=750.00,
        labor_salaried=0.0,
        payroll_taxes_benefits=0.0,
    )
    # food_cogs = 5000; labor = 1500; prime = 6500; pct = 65.00
    results = m.track_prime_cost([pw])
    assert results[0].prime_pct == pytest.approx(65.00, abs=0.01)
    assert results[0].status == "watch"


def test_inventory_continuity_warning():
    """Discontinuous inventory should produce warnings."""
    w1 = m.PNLWeek(
        week_ending=date(2026, 7, 5),
        net_sales=10000.00,
        food_purchases=1000.0,
        food_inv_begin=500.0,
        food_inv_end=400.0,
        bev_purchases=0.0,
        bev_inv_begin=0.0,
        bev_inv_end=0.0,
        labor_foh=0.0, labor_boh=0.0, labor_salaried=0.0, payroll_taxes_benefits=0.0,
    )
    w2 = m.PNLWeek(
        week_ending=date(2026, 7, 12),
        net_sales=10000.00,
        food_purchases=1000.0,
        food_inv_begin=500.0,  # should be 400.0
        food_inv_end=350.0,
        bev_purchases=0.0,
        bev_inv_begin=0.0,
        bev_inv_end=0.0,
        labor_foh=0.0, labor_boh=0.0, labor_salaried=0.0, payroll_taxes_benefits=0.0,
    )
    results = m.track_prime_cost([w1, w2])
    all_warnings = []
    for r in results:
        all_warnings.extend(r.warnings)
    assert len(all_warnings) == 1
    assert "food inventory discontinuity" in all_warnings[0]


def test_empty_inputs_no_crash():
    assert m.track_prime_cost([]) == []
    summary = m.summarize([])
    assert summary["net_sales"] == 0.0
    assert summary["status"] == "ok"