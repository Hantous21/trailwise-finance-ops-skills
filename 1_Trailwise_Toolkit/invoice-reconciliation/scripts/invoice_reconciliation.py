#!/usr/bin/env python3
"""Invoice reconciliation engine.

Match vendor invoices to purchase orders (POs) and goods receipt records.
Flag quantity/price variances, unmatched invoices, and route approvals
within configurable tolerances. Extracted from the invoice-reconciliation
SKILL.md to keep the skill body minimal.

Usage:
    from invoice_reconciliation import InvoiceReconciler, Invoice, ...
    # or run as a CLI against fixture CSVs (see ``main``).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class MatchStatus(Enum):
    MATCHED = "matched"               # Three-way match within tolerance
    PRICE_VARIANCE = "price_variance"  # Price difference exceeds tolerance
    QTY_VARIANCE = "qty_variance"      # Quantity difference exceeds tolerance
    UNMATCHED = "unmatched"           # No corresponding PO found
    PARTIAL_MATCH = "partial_match"   # PO exists but line items don't align


class ApprovalAction(Enum):
    AUTO_APPROVE = "auto_approve"    # Within tolerance, no action needed
    REVIEW = "review"                # Variance detected, needs human review
    REJECT = "reject"                # Discrepancy too large, return to vendor
    ESCALATE = "escalate"            # Above authority threshold, escalate


@dataclass
class PurchaseOrder:
    po_number: str
    vendor: str
    line_items: List[Dict]  # [{"sku": "...", "description": "...", "qty": 10, "unit_price": 50.00, "total": 500.00}]
    po_date: date
    total: float
    status: str  # "open", "closed", "partial"


@dataclass
class GoodsReceipt:
    receipt_number: str
    po_number: str
    received_date: date
    line_items: List[Dict]  # [{"sku": "...", "qty_received": 9}]
    total_received: float


@dataclass
class Invoice:
    invoice_number: str
    vendor: str
    invoice_date: date
    due_date: date
    line_items: List[Dict]  # [{"sku": "...", "description": "...", "qty": 10, "unit_price": 52.00, "total": 520.00}]
    subtotal: float
    tax: float
    total: float


@dataclass
class ReconciliationResult:
    invoice_number: str
    po_number: Optional[str]
    match_status: MatchStatus
    approval_action: ApprovalAction
    price_variance: float  # absolute dollar amount
    qty_variance: float     # absolute quantity difference
    notes: List[str] = field(default_factory=list)


class InvoiceReconciler:
    """Match invoices to POs and goods receipts with tolerance-based approval."""

    def __init__(
        self,
        price_tolerance_pct: float = 2.0,
        qty_tolerance_pct: float = 5.0,
        auto_approve_threshold: float = 500.0,
    ):
        """
        Args:
            price_tolerance_pct: Allowed price variance percentage (default 2%)
            qty_tolerance_pct: Allowed quantity variance percentage (default 5%)
            auto_approve_threshold: Max dollar amount for auto-approval (default $500)
        """
        self.price_tolerance_pct = price_tolerance_pct
        self.qty_tolerance_pct = qty_tolerance_pct
        self.auto_approve_threshold = auto_approve_threshold

    def reconcile(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder] = None,
        receipt: Optional[GoodsReceipt] = None,
    ) -> ReconciliationResult:
        """Reconcile a single invoice against PO and receipt."""

        # No PO found — unmatched
        if po is None:
            return ReconciliationResult(
                invoice_number=invoice.invoice_number,
                po_number=None,
                match_status=MatchStatus.UNMATCHED,
                approval_action=ApprovalAction.REVIEW,
                price_variance=0,
                qty_variance=0,
                notes=["No matching PO found for this invoice"],
            )

        # Match line items by SKU
        price_variances = []
        qty_variances = []
        notes = []

        for inv_item in invoice.line_items:
            po_item = self._find_line_item(po.line_items, inv_item["sku"])

            if po_item is None:
                notes.append(f"Sku {inv_item['sku']} not found on PO {po.po_number}")
                continue

            # Price check
            price_diff = inv_item["unit_price"] - po_item["unit_price"]
            price_pct = (
                abs(price_diff) / po_item["unit_price"] * 100
                if po_item["unit_price"]
                else 0
            )
            if price_pct > self.price_tolerance_pct:
                price_variances.append(price_diff)
                notes.append(
                    f"Price variance: {inv_item['sku']} invoiced ${inv_item['unit_price']:.2f} "
                    f"vs PO ${po_item['unit_price']:.2f} ({price_pct:.1f}% diff)"
                )

            # Quantity check (against receipt if available, else PO quantity).
            # Look up the matching receipt line item by SKU so the received
            # quantity is only used when a corresponding receipt entry exists.
            receipt_item = (
                self._find_line_item(receipt.line_items, inv_item["sku"])
                if receipt is not None
                else None
            )
            expected_qty = (
                receipt_item["qty_received"]
                if receipt_item is not None
                else po_item["qty"]
            )
            qty_diff = inv_item["qty"] - expected_qty
            qty_pct = abs(qty_diff) / expected_qty * 100 if expected_qty else 0
            if qty_pct > self.qty_tolerance_pct:
                qty_variances.append(qty_diff)
                notes.append(
                    f"Quantity variance: {inv_item['sku']} invoiced {inv_item['qty']} "
                    f"vs expected {expected_qty} ({qty_pct:.1f}% diff)"
                )

        total_price_variance = sum(price_variances)
        total_qty_variance = sum(abs(v) for v in qty_variances)

        # Determine match status
        if not price_variances and not qty_variances:
            match_status = MatchStatus.MATCHED
        elif price_variances and qty_variances:
            match_status = MatchStatus.PARTIAL_MATCH
        elif price_variances:
            match_status = MatchStatus.PRICE_VARIANCE
        else:
            match_status = MatchStatus.QTY_VARIANCE

        # Determine approval action
        if match_status == MatchStatus.MATCHED and invoice.total <= self.auto_approve_threshold:
            action = ApprovalAction.AUTO_APPROVE
        elif abs(total_price_variance) > invoice.subtotal * 0.10:
            action = ApprovalAction.REJECT
        elif invoice.total > self.auto_approve_threshold * 10:
            action = ApprovalAction.ESCALATE
        else:
            action = ApprovalAction.REVIEW

        return ReconciliationResult(
            invoice_number=invoice.invoice_number,
            po_number=po.po_number,
            match_status=match_status,
            approval_action=action,
            price_variance=total_price_variance,
            qty_variance=total_qty_variance,
            notes=notes,
        )

    def reconcile_batch(
        self,
        invoices: List[Invoice],
        pos: Dict[str, PurchaseOrder],
        receipts: Dict[str, GoodsReceipt],
    ) -> List[ReconciliationResult]:
        """Reconcile multiple invoices against PO and receipt databases."""
        results = []
        for inv in invoices:
            po = pos.get(inv.vendor)  # Simplified — real matching by PO number
            receipt = receipts.get(po.po_number) if po else None
            results.append(self.reconcile(inv, po, receipt))
        return results

    def generate_report(self, results: List[ReconciliationResult]) -> Dict:
        """Generate summary report for finance team review."""
        status_counts = Counter(r.match_status.value for r in results)
        action_counts = Counter(r.approval_action.value for r in results)
        total_variance = sum(r.price_variance for r in results)

        return {
            "total_invoices": len(results),
            "matched": status_counts.get("matched", 0),
            "variances_found": sum(1 for r in results if r.match_status != MatchStatus.MATCHED),
            "unmatched": status_counts.get("unmatched", 0),
            "auto_approved": action_counts.get("auto_approve", 0),
            "need_review": action_counts.get("review", 0),
            "rejected": action_counts.get("reject", 0),
            "escalated": action_counts.get("escalate", 0),
            "total_price_variance": round(total_variance, 2),
            "results": [self._result_to_dict(r) for r in results],
        }

    def _find_line_item(self, items: List[Dict], sku: str) -> Optional[Dict]:
        for item in items:
            if item.get("sku") == sku:
                return item
        return None

    def _result_to_dict(self, r: ReconciliationResult) -> Dict:
        return {
            "invoice": r.invoice_number,
            "po": r.po_number,
            "status": r.match_status.value,
            "action": r.approval_action.value,
            "price_variance": round(r.price_variance, 2),
            "qty_variance": r.qty_variance,
            "notes": r.notes,
        }


# --- CSV loaders & CLI -----------------------------------------------------

def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def load_invoices(path: str) -> List[Invoice]:
    """Load invoices from CSV. One row per invoice line item; rows sharing an
    invoice_number are grouped into a single Invoice."""
    grouped: Dict[str, Invoice] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            num = row["invoice_number"]
            line = {
                "sku": row["sku"],
                "description": row.get("description", ""),
                "qty": float(row["qty"]),
                "unit_price": float(row["unit_price"]),
                "total": float(row["total"]),
            }
            if num in grouped:
                grouped[num].line_items.append(line)
                grouped[num].subtotal += line["total"]
                grouped[num].total += line["total"]
            else:
                grouped[num] = Invoice(
                    invoice_number=num,
                    vendor=row["vendor"],
                    invoice_date=_parse_date(row["invoice_date"]),
                    due_date=_parse_date(row["due_date"]),
                    line_items=[line],
                    subtotal=line["total"],
                    tax=0.0,
                    total=line["total"],
                )
    return list(grouped.values())


def load_purchase_orders(path: str) -> Dict[str, PurchaseOrder]:
    """Load POs from CSV, grouping rows by po_number. Returns a dict keyed by
    ``vendor`` to match ``InvoiceReconciler.reconcile_batch`` (which looks up
    POs via ``pos.get(invoice.vendor)`` — simplified matching, see SKILL.md)."""
    by_po: Dict[str, PurchaseOrder] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            num = row["po_number"]
            line = {
                "sku": row["sku"],
                "description": row.get("description", ""),
                "qty": float(row["qty"]),
                "unit_price": float(row["unit_price"]),
                "total": float(row["total"]),
            }
            if num in by_po:
                by_po[num].line_items.append(line)
                by_po[num].total += line["total"]
            else:
                by_po[num] = PurchaseOrder(
                    po_number=num,
                    vendor=row["vendor"],
                    line_items=[line],
                    po_date=_parse_date(row["po_date"]),
                    total=line["total"],
                    status="open",
                )
    # Key by vendor to match the reconcile_batch lookup contract.
    return {po.vendor: po for po in by_po.values()}


def load_goods_receipts(path: str) -> Dict[str, GoodsReceipt]:
    grouped: Dict[str, GoodsReceipt] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            num = row["receipt_number"]
            line = {"sku": row["sku"], "qty_received": float(row["qty_received"])}
            if num in grouped:
                grouped[num].line_items.append(line)
                grouped[num].total_received += line["qty_received"]
            else:
                grouped[num] = GoodsReceipt(
                    receipt_number=num,
                    po_number=row["po_number"],
                    received_date=_parse_date(row["received_date"]),
                    line_items=[line],
                    total_received=line["qty_received"],
                )
    # Index by PO number for lookup by reconcile_batch.
    return {gr.po_number: gr for gr in grouped.values()}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: reconcile fixtures and print JSON result for the first invoice.

    Usage:
        python3 scripts/invoice_reconciliation.py \
            fixtures/input/invoices.csv \
            fixtures/input/purchase_orders.csv \
            fixtures/input/goods_receipts.csv
    """
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 3:
        print(
            "usage: invoice_reconciliation.py <invoices.csv> <pos.csv> <receipts.csv>",
            file=sys.stderr,
        )
        return 2

    invoices_path, pos_path, receipts_path = argv[0], argv[1], argv[2]
    invoices = load_invoices(invoices_path)
    pos = load_purchase_orders(pos_path)
    receipts = load_goods_receipts(receipts_path)

    reconciler = InvoiceReconciler()
    results = reconciler.reconcile_batch(invoices, pos, receipts)
    if not results:
        print("[]")
        return 0

    first = results[0]
    print(
        json.dumps(
            {
                "invoice_number": first.invoice_number,
                "po_number": first.po_number,
                "match_status": first.match_status.value,
                "approval_action": first.approval_action.value,
                "price_variance": round(first.price_variance, 2),
                "qty_variance": first.qty_variance,
                "notes": first.notes,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
