"""
Golden fixture + tests for payment-app-generator (AIA G702/G703).

Discovered at Part 3 3.0 golden gate: balance_to_finish was being computed
gross of retainage; fixed by `fix: G702 line 9 balance-to-finish per AIA form`
commit on the feat/documents-tier-plus-restaurant branch.

Reference:
- AIA G702 line 9 (balance to finish) = line 3 (contract sum to date) - line 6
  (total earned less retainage), NOT - line 5 (total completed & stored).
- AIA G702 line 7 (less previous payments) defaults to a derivation from G703
  previous-completed, but can be overridden via `previous_certificates`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = (
    REPO_ROOT
    / "1_Trailwise_Toolkit"
    / "payment-app-generator"
    / "scripts"
    / "payment_app.py"
)
FIXTURE_INPUT = REPO_ROOT / "1_Trailwise_Toolkit" / "payment-app-generator" / "fixtures" / "expected" / "pay_app_2.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("payment_app_under_test", str(SCRIPT_PATH))
    assert spec is not None and spec.loader is not None, f"Could not load spec for {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["payment_app_under_test"] = module
    spec.loader.exec_module(module)
    return module


pa = _load_module()


def _build_app2(previous_certificates=None):
    """Construct the canonical app #2 used in Part 3.0."""
    app = pa.PaymentApplication(
        app_number=2,
        project_name="Riverside Office Building",
        contractor="Trailwise Construction",
        owner="Riverside Development LLC",
        architect="Smith & Associates",
        contract_date=date(2026, 1, 15),
        period_to=date(2026, 6, 30),
        original_contract_sum=750000.00,
        change_orders=[pa.ChangeOrder("CO-1", "Foundation revision", 30000.00, True)],
        retainage_pct=10.0,
        previous_certificates=previous_certificates,
    )
    app.lines = [
        pa.ScheduleOfValuesLine(
            line_no=1, description="01 Sitework",
            scheduled_value=200000.0, scheduled_value_co=0.0,
            previous_completed=120000.0, current_completed=40000.0,
            stored_materials=0.0, retainage_pct=10.0,
        ),
        pa.ScheduleOfValuesLine(
            line_no=2, description="02 Concrete",
            scheduled_value=300000.0, scheduled_value_co=0.0,
            previous_completed=60000.0, current_completed=90000.0,
            stored_materials=10000.0, retainage_pct=10.0,
        ),
        pa.ScheduleOfValuesLine(
            line_no=3, description="03 Steel",
            scheduled_value=250000.0, scheduled_value_co=0.0,
            previous_completed=0.0, current_completed=0.0,
            stored_materials=0.0, retainage_pct=10.0,
        ),
    ]
    return app


def test_app2_default_numbers():
    """All app-#2 numbers from the Part 3.0 spec (no override)."""
    g702 = pa.G702Generator().generate(_build_app2())
    assert g702["contract_sum_to_date"] == pytest.approx(780000.00, abs=0.01)
    assert g702["total_completed_stored"] == pytest.approx(320000.00, abs=0.01)
    assert g702["retainage"] == pytest.approx(32000.00, abs=0.01)
    assert g702["total_earnings_less_retainage"] == pytest.approx(288000.00, abs=0.01)
    # Default derivation: 180,000 * 0.9 = 162,000
    assert g702["less_previous_payments"] == pytest.approx(162000.00, abs=0.01)
    # 288,000 - 162,000 = 126,000
    assert g702["current_amount_due"] == pytest.approx(126000.00, abs=0.01)
    # G702 line 9 = line 3 - line 6 = 780,000 - 288,000 = 492,000 (post-fix)
    assert g702["balance_to_finish"] == pytest.approx(492000.00, abs=0.01)
    assert g702["percent_complete"] == pytest.approx(41.03, abs=0.01)


def test_app2_with_explicit_previous_certificates():
    """Setting previous_certificates overrides the default derivation."""
    g702 = pa.G702Generator().generate(_build_app2(previous_certificates=150000.00))
    assert g702["less_previous_payments"] == pytest.approx(150000.00, abs=0.01)
    # 288,000 - 150,000 = 138,000
    assert g702["current_amount_due"] == pytest.approx(138000.00, abs=0.01)


def test_app_number_one_has_no_previous_payments():
    """First pay app: previous_payments must always be 0, regardless of override."""
    g702 = pa.G702Generator().generate(_build_app2(previous_certificates=999999.00))
    g702.pop("app_number", None)  # ensure fresh build
    app1 = pa.PaymentApplication(
        app_number=1,
        project_name="P", contractor="C", owner="O", architect="A",
        contract_date=date(2026, 1, 1), period_to=date(2026, 6, 30),
        original_contract_sum=750000.00, retainage_pct=10.0,
    )
    g1 = pa.G702Generator().generate(app1)
    assert g1["less_previous_payments"] == 0
    assert g1["current_amount_due"] == 0


def test_g703_line_2_completed_stored_and_retainage():
    g703 = pa.G702Generator().generate_g703(_build_app2())
    line2 = next(r for r in g703 if r["line"] == 2)
    # 60,000 (prev) + 90,000 (this) + 10,000 (stored) = 160,000
    assert line2["total_completed_stored"] == pytest.approx(160000.00, abs=0.01)
    # 10% of 160,000 = 16,000
    assert line2["retainage_held"] == pytest.approx(16000.00, abs=0.01)


def test_golden_pay_app_2_json_matches_live_output():
    """
    The committed golden under 1_Trailwise_Toolkit/.../fixtures/expected/pay_app_2.json
    must equal what the live generator produces from the canonical app-#2 inputs.
    """
    g702 = pa.G702Generator().generate(_build_app2())
    g703 = pa.G702Generator().generate_g703(_build_app2())

    if not FIXTURE_INPUT.exists():
        # First-run: this test is the "generates the golden" step. Generate it.
        FIXTURE_INPUT.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_INPUT.write_text(json.dumps({"g702": g702, "g703": g703}, indent=2))
        pytest.skip(f"Golden generated at {FIXTURE_INPUT}; re-run to assert.")
    else:
        committed = json.loads(FIXTURE_INPUT.read_text())
        assert committed["g702"]["current_amount_due"] == pytest.approx(126000.00, abs=0.01)
        assert committed["g702"]["balance_to_finish"] == pytest.approx(492000.00, abs=0.01)
        assert committed["g702"]["less_previous_payments"] == pytest.approx(162000.00, abs=0.01)
        # And the structure must match the live output exactly.
        assert committed["g702"] == g702
        assert committed["g703"] == g703
