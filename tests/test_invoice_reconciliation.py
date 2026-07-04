"""Tests for invoice-reconciliation skill: three-way match (invoice ↔ PO ↔ receipt)."""
import json
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "1_Trailwise_Toolkit" / "invoice-reconciliation"
sys.path.insert(0, str(SKILL_DIR))

from scripts.invoice_reconciliation import (
    InvoiceReconciler, load_invoices, load_purchase_orders, load_goods_receipts,
    MatchStatus, ApprovalAction,
)


def _result_to_dict(result):
    return {
        "invoice_number": result.invoice_number,
        "po_number": result.po_number,
        "match_status": result.match_status.value if hasattr(result.match_status, "value") else str(result.match_status),
        "approval_action": result.approval_action.value if hasattr(result.approval_action, "value") else str(result.approval_action),
        "price_variance": result.price_variance,
        "qty_variance": result.qty_variance,
        "notes": result.notes,
    }


class TestGoldenFixture:
    """Output against fixtures/input must match fixtures/expected exactly."""

    def test_reconciliation_matches_golden_fixture(self):
        inv = load_invoices(str(SKILL_DIR / "fixtures/input/invoices.csv"))
        pos = load_purchase_orders(str(SKILL_DIR / "fixtures/input/purchase_orders.csv"))
        grs = load_goods_receipts(str(SKILL_DIR / "fixtures/input/goods_receipts.csv"))

        invoice = inv[0]
        po = pos[invoice.vendor]
        gr = grs.get(po.po_number)

        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(invoice, po, gr)
        actual = _result_to_dict(result)

        with open(SKILL_DIR / "fixtures/expected/reconciliation_result.json") as f:
            expected = json.load(f)

        assert actual == expected, f"Actual: {actual}\nExpected: {expected}"


class TestThreeWayMatch:
    """Property tests for the three-way match: invoice ↔ PO ↔ receipt."""

    def _make_basic(self):
        """Load fixture data once."""
        inv = load_invoices(str(SKILL_DIR / "fixtures/input/invoices.csv"))
        pos = load_purchase_orders(str(SKILL_DIR / "fixtures/input/purchase_orders.csv"))
        grs = load_goods_receipts(str(SKILL_DIR / "fixtures/input/goods_receipts.csv"))
        return inv[0], pos[inv[0].vendor], grs.get(pos[inv[0].vendor].po_number)

    def test_matched_invoice_has_zero_variance(self):
        inv, po, gr = self._make_basic()
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, gr)
        assert result.price_variance == 0
        assert result.qty_variance == 0
        assert result.match_status == MatchStatus.MATCHED

    def test_approval_action_is_review_for_matched(self):
        inv, po, gr = self._make_basic()
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, gr)
        assert result.approval_action == ApprovalAction.REVIEW

    def test_no_notes_on_perfect_match(self):
        inv, po, gr = self._make_basic()
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, gr)
        assert result.notes == []

    def test_price_variance_detected_when_exceeds_tolerance(self):
        """SKU-100: PO price $28.00, invoice price $28.50 = 1.8% variance.
        Default 2% tolerance → not flagged. But at 1% tolerance it should flag."""
        inv, po, gr = self._make_basic()
        reconciler = InvoiceReconciler(price_tolerance_pct=1.0)
        result = reconciler.reconcile(inv, po, gr)
        assert result.price_variance > 0
        assert any("price" in n.lower() for n in result.notes)

    def test_missing_receipt_still_reconciles(self):
        """Without a goods receipt, the match should still proceed (two-way)."""
        inv, po, _ = self._make_basic()
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, None)
        assert result.invoice_number == "INV-001"
        # Should still get a result, possibly with notes about missing receipt

    def test_qty_variance_detected_when_receipt_qty_differs(self):
        """If receipt shows fewer units than invoiced, qty_variance should be non-zero."""
        inv, po, gr = self._make_basic()
        # Tamper with receipt to show fewer units
        gr.line_items[0]["qty_received"] = 40  # 10 less than invoiced
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, gr)
        assert result.qty_variance != 0

    def test_match_status_value_is_string(self):
        inv, po, gr = self._make_basic()
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, gr)
        assert isinstance(result.match_status.value, str)

    def test_result_has_all_required_fields(self):
        inv, po, gr = self._make_basic()
        reconciler = InvoiceReconciler()
        result = reconciler.reconcile(inv, po, gr)
        for field in ("invoice_number", "po_number", "match_status",
                      "approval_action", "price_variance", "qty_variance", "notes"):
            assert hasattr(result, field), f"Missing field: {field}"
