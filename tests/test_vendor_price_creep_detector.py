"""
Tests for vendor-price-creep-detector.

Goldens (from prompt):

| vendor / item                  | baseline | latest | creep_pct | flags                     | excess_cost_to_date |
|--------------------------------|----------|--------|-----------|---------------------------|---------------------|
| Sysco / Chicken Breast 40lb... | 96.00    | 106.00 | 10.42     | price_creep ONLY          | 117.00              |
| US Foods / Mozzarella 5lb      | 18.50    | 22.75  | 22.97     | price_creep AND price_spike | 25.50            |
| Sysco / Tomatoes 25lb          | 24.00    | 24.00  | 0.00      | none                      | -1.50               |
| US Foods / Fryer Oil 35lb      | 40.00    | 42.00  | 5.00      | none (5.00 not > 5.0)     | 4.00                |
| Sysco / Truffle Oil 500ml      | --       | --     | --        | insufficient_history      | excluded            |

Summary: items_tracked 5, items_flagged 2, excess_cost_flagged 142.50, excess_cost_all 145.00.
Boundary: consecutive jump exactly 10.00% -> NO spike flag.
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
    / "vendor-price-creep-detector"
    / "scripts"
    / "vendor_price_creep.py"
)
FIXTURE_CSV = (
    REPO_ROOT
    / "7_Restaurant_Operations"
    / "vendor-price-creep-detector"
    / "fixtures"
    / "input"
    / "purchase_history.csv"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "vendor_price_creep_under_test", str(SCRIPT_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["vendor_price_creep_under_test"] = module
    spec.loader.exec_module(module)
    return module


m = _load_module()


@pytest.fixture(scope="module")
def results():
    purchases = m.load_purchases(FIXTURE_CSV)
    return m.detect_creep(purchases)


def _by_vendor_item(results, vendor, item):
    for r in results:
        if r.vendor == vendor and r.item == item:
            return r
    raise AssertionError(f"not found: {vendor} / {item}")


def test_chicken_breast(results):
    r = _by_vendor_item(results, "Sysco", "Chicken Breast 40lb case")
    assert r.insufficient_history is False
    assert r.baseline_price == pytest.approx(96.00, abs=0.01)
    assert r.latest_price == pytest.approx(106.00, abs=0.01)
    assert r.creep_pct == pytest.approx(10.42, abs=0.01)
    assert r.flags == ["price_creep"]
    # No spike: max single jump is (106-104)/104 = 1.92% or (104-101)/101 = 2.97%
    assert r.excess_cost_to_date == pytest.approx(117.00, abs=0.01)


def test_mozzarella(results):
    r = _by_vendor_item(results, "US Foods", "Mozzarella 5lb")
    assert r.insufficient_history is False
    assert r.baseline_price == pytest.approx(18.50, abs=0.01)
    assert r.latest_price == pytest.approx(22.75, abs=0.01)
    assert r.creep_pct == pytest.approx(22.97, abs=0.01)
    assert "price_creep" in r.flags
    assert "price_spike" in r.flags
    assert r.excess_cost_to_date == pytest.approx(25.50, abs=0.01)


def test_tomatoes(results):
    r = _by_vendor_item(results, "Sysco", "Tomatoes 25lb")
    assert r.baseline_price == pytest.approx(24.00, abs=0.01)
    assert r.latest_price == pytest.approx(24.00, abs=0.01)
    assert r.creep_pct == pytest.approx(0.00, abs=0.01)
    assert r.flags == []
    assert r.excess_cost_to_date == pytest.approx(-1.50, abs=0.01)


def test_fryer_oil(results):
    r = _by_vendor_item(results, "US Foods", "Fryer Oil 35lb")
    assert r.baseline_price == pytest.approx(40.00, abs=0.01)
    assert r.latest_price == pytest.approx(42.00, abs=0.01)
    assert r.creep_pct == pytest.approx(5.00, abs=0.01)
    # 5.00 is NOT > 5.0 — boundary
    assert r.flags == []
    assert r.excess_cost_to_date == pytest.approx(4.00, abs=0.01)


def test_truffle_oil(results):
    r = _by_vendor_item(results, "Sysco", "Truffle Oil 500ml")
    assert r.insufficient_history is True
    assert r.flags == []
    assert r.excess_cost_to_date is None


def test_summary(results):
    summary = m.summarize(results)
    assert summary["items_tracked"] == 5
    assert summary["items_flagged"] == 2
    assert summary["excess_cost_flagged"] == pytest.approx(142.50, abs=0.01)
    assert summary["excess_cost_all"] == pytest.approx(145.00, abs=0.01)


def test_boundary_spike_exact_10_no_flag():
    """A consecutive jump of exactly 10.00% -> NO spike flag (strict > threshold)."""
    purchases = [
        m.Purchase(date=date(2026, 1, 1), vendor="V", item="X",
                    quantity=1, unit="ea", unit_price=100.00),
        m.Purchase(date=date(2026, 1, 8), vendor="V", item="X",
                    quantity=1, unit="ea", unit_price=110.00),
    ]
    # Jump = (110-100)/100 * 100 = 10.00% -> exactly 10.0, not > 10.0
    results = m.detect_creep(purchases, creep_threshold=20.0, spike_threshold=10.0)
    assert len(results) == 1
    assert "price_spike" not in results[0].flags
    # creep_pct = (110-100)/100 * 100 = 10.00
    assert results[0].creep_pct == pytest.approx(10.00, abs=0.01)
    # creep_threshold is 20.0, so no creep flag either
    assert results[0].flags == []


def test_boundary_spike_just_above_10():
    """A consecutive jump of exactly 10.01% -> spike flag."""
    purchases = [
        m.Purchase(date=date(2026, 1, 1), vendor="V", item="X",
                    quantity=1, unit="ea", unit_price=100.00),
        m.Purchase(date=date(2026, 1, 8), vendor="V", item="X",
                    quantity=1, unit="ea", unit_price=110.01),
    ]
    results = m.detect_creep(purchases, spike_threshold=10.0)
    assert "price_spike" in results[0].flags


def test_empty_inputs():
    assert m.detect_creep([]) == []
    summary = m.summarize([])
    assert summary["items_tracked"] == 0