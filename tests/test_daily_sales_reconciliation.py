"""
Tests for daily-sales-reconciliation.

Expected numbers (asserted exactly):
- 06-01 clean (cash 0 variance; fee 2.50)
- 06-02 cash_short -50.00; fee 2.15 ok
- 06-03 missing_deposit (no cash at 06-04); fee 5.00 -> fee_out_of_band
- 06-04 cash_over +30.00; fee 2.00 ok
- Summary: matched_cash_variance -20.00; missing_deposit_amount 780.00;
           days_flagged 3; flag_count 4

Boundary tests: variance exactly +/- 5.00 -> no flag; fee exactly 1.5 or 4.0 -> no flag.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = (
    REPO_ROOT
    / "7_Restaurant_Operations"
    / "daily-sales-reconciliation"
    / "scripts"
    / "daily_sales_reconciliation.py"
)
INPUT_DIR = REPO_ROOT / "7_Restaurant_Operations" / "daily-sales-reconciliation" / "fixtures" / "input"
POS_CSV = INPUT_DIR / "pos_daily.csv"
DEPOSITS_CSV = INPUT_DIR / "bank_deposits.csv"
EXPECTED_DIR = REPO_ROOT / "7_Restaurant_Operations" / "daily-sales-reconciliation" / "fixtures" / "expected"
EXPECTED_JSON = EXPECTED_DIR / "reconciliation.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("daily_sales_reconciliation_under_test", str(SCRIPT_PATH))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["daily_sales_reconciliation_under_test"] = module
    spec.loader.exec_module(module)
    return module


m = _load_module()


@pytest.fixture(scope="module")
def results():
    pos = m.load_pos(POS_CSV)
    deposits = m.load_deposits(DEPOSITS_CSV)
    return m.reconcile(pos, deposits)


def test_june_1_clean(results):
    day = next(r for r in results if r.date == date(2026, 6, 1))
    assert day.cash_variance == pytest.approx(0.00, abs=0.01)
    assert day.card_fee_pct == pytest.approx(2.50, abs=0.01)
    assert day.flags == []


def test_june_2_cash_short_minus_50(results):
    day = next(r for r in results if r.date == date(2026, 6, 2))
    assert day.cash_variance == pytest.approx(-50.00, abs=0.01)
    assert day.card_fee_pct == pytest.approx(2.15, abs=0.01)
    assert "cash_short" in day.flags
    assert "fee_out_of_band" not in day.flags


def test_june_3_missing_deposit_and_fee_out_of_band(results):
    day = next(r for r in results if r.date == date(2026, 6, 3))
    assert day.cash_deposit is None
    assert "missing_deposit" in day.flags
    assert day.card_fee_pct == pytest.approx(5.00, abs=0.01)
    assert "fee_out_of_band" in day.flags


def test_june_4_cash_over_plus_30(results):
    day = next(r for r in results if r.date == date(2026, 6, 4))
    assert day.cash_variance == pytest.approx(+30.00, abs=0.01)
    assert day.card_fee_pct == pytest.approx(2.00, abs=0.01)
    assert "cash_over" in day.flags


def test_summary_numbers(results):
    summary = m.summarize(results)
    assert summary["matched_cash_variance"] == pytest.approx(-20.00, abs=0.01)
    assert summary["missing_deposit_amount"] == pytest.approx(780.00, abs=0.01)
    assert summary["days_flagged"] == 3
    assert summary["flag_count"] == 4


def test_variance_boundary_no_flag_at_exact_tolerance():
    """Variance exactly +5.00 or -5.00 must NOT flag (strict > tolerance)."""
    # Include a card deposit too so missing_settlement does not fire.
    pos = [m.POSDay(date(2026, 6, 1), 0, 0, 0, cash_collected=100.0, card_collected=100.0)]
    base_deposits = [m.Deposit(date(2026, 6, 2), "card", 98.00)]  # 2% fee, in band

    # +5.00 variance -> not flagged as cash_over
    results = m.reconcile(pos, base_deposits + [m.Deposit(date(2026, 6, 2), "cash", 105.0)],
                          cash_tolerance=5.00)
    assert "cash_over" not in results[0].flags
    assert "cash_short" not in results[0].flags

    # -5.00 variance -> not flagged as cash_short
    results2 = m.reconcile(pos, base_deposits + [m.Deposit(date(2026, 6, 2), "cash", 95.0)],
                           cash_tolerance=5.00)
    assert "cash_over" not in results2[0].flags
    assert "cash_short" not in results2[0].flags

    # Just past tolerance -> flagged
    results3 = m.reconcile(pos, base_deposits + [m.Deposit(date(2026, 6, 2), "cash", 105.01)],
                           cash_tolerance=5.00)
    assert "cash_over" in results3[0].flags


def test_fee_band_boundary():
    """Fee exactly 1.50% or 4.00% must NOT flag; 1.49 or 4.01 must."""
    pos = [m.POSDay(date(2026, 6, 1), 0, 0, 0, cash_collected=0.0, card_collected=100.0)]

    # 1.50% fee -> in band (no flag)
    dep_150 = [m.Deposit(date(2026, 6, 2), "card", 98.50)]
    r1 = m.reconcile(pos, dep_150)
    assert "fee_out_of_band" not in r1[0].flags

    # 4.00% fee -> in band (no flag)
    dep_400 = [m.Deposit(date(2026, 6, 2), "card", 96.00)]
    r2 = m.reconcile(pos, dep_400)
    assert "fee_out_of_band" not in r2[0].flags

    # 4.01% fee -> out of band
    dep_401 = [m.Deposit(date(2026, 6, 2), "card", 95.99)]
    r3 = m.reconcile(pos, dep_401)
    assert "fee_out_of_band" in r3[0].flags

    # 1.49% fee -> out of band
    dep_149 = [m.Deposit(date(2026, 6, 2), "card", 98.51)]
    r4 = m.reconcile(pos, dep_149)
    assert "fee_out_of_band" in r4[0].flags


def test_empty_inputs_no_crash():
    assert m.reconcile([], []) == []
    summary = m.summarize([])
    assert summary == {
        "matched_cash_variance": 0.0,
        "missing_deposit_amount": 0.0,
        "days_flagged": 0,
        "flag_count": 0,
    }


def test_unknown_deposit_type_raises():
    # Write a temp CSV with a bogus type
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("deposit_date,type,amount\n2026-06-02,bogus,100.00\n")
        path = Path(f.name)
    try:
        with pytest.raises(ValueError):
            m.load_deposits(path)
    finally:
        path.unlink()
