---
name: "invoice-reconciliation"
description: "Match vendor invoices to purchase orders and receipts. Flag discrepancies, automate approval routing, and generate reconciliation reports."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "🧾"
    category: "accounts-payable"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
---

# Invoice Reconciliation

## Overview

Automatically match vendor invoices to purchase orders (POs) and goods receipt records. Flag quantity discrepancies, price variances, and unmatched invoices. Generate a reconciliation report for review and approval.

## When to Use

- You receive 20+ vendor invoices per week
- Invoices are matched manually against POs in Excel or QuickBooks
- Discrepancies (wrong quantity, wrong price) are caught too late
- Approval routing happens over email (slow, no audit trail)

## Capabilities

- Three-way match: Invoice ↔ PO ↔ Goods Receipt
- Two-way match: Invoice ↔ PO (when no receipt is tracked)
- Price variance detection (invoice price vs PO price)
- Quantity variance detection (invoiced qty vs received qty)
- Unmatched invoice detection (no corresponding PO)
- Tolerance-based auto-approval (within variance threshold)
- Reconciliation report generation (Excel/CSV)

## Quick Start

```python
from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Optional, Tuple
from enum import Enum

class MatchStatus(Enum):
    MATCHED = "matched"              # Three-way match within tolerance
    PRICE_VARIANCE = "price_variance"  # Price difference exceeds tolerance
    QTY_VARIANCE = "qty_variance"     # Quantity difference exceeds tolerance
    UNMATCHED = "unmatched"          # No corresponding PO found
    PARTIAL_MATCH = "partial_match"  # PO exists but line items don't align

class ApprovalAction(Enum):
    AUTO_APPROVE = "auto_approve"   # Within tolerance, no action needed
    REVIEW = "review"               # Variance detected, needs human review
    REJECT = "reject"               # Discrepancy too large, return to vendor
    ESCALATE = "escalate"           # Above authority threshold, escalate

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
    qty_variance: float    # absolute quantity difference
    notes: List[str] = field(default_factory=list)
```

## Reconciliation Engine

```python
class InvoiceReconciler:
    """Match invoices to POs and goods receipts with tolerance-based approval."""

    def __init__(self, price_tolerance_pct: float = 2.0, qty_tolerance_pct: float = 5.0,
                 auto_approve_threshold: float = 500.0):
        """
        Args:
            price_tolerance_pct: Allowed price variance percentage (default 2%)
            qty_tolerance_pct: Allowed quantity variance percentage (default 5%)
            auto_approve_threshold: Max dollar amount for auto-approval (default $500)
        """
        self.price_tolerance_pct = price_tolerance_pct
        self.qty_tolerance_pct = qty_tolerance_pct
        self.auto_approve_threshold = auto_approve_threshold

    def reconcile(self, invoice: Invoice, po: Optional[PurchaseOrder] = None,
                  receipt: Optional[GoodsReceipt] = None) -> ReconciliationResult:
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
                notes=["No matching PO found for this invoice"]
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
            price_pct = abs(price_diff) / po_item["unit_price"] * 100 if po_item["unit_price"] else 0
            if price_pct > self.price_tolerance_pct:
                price_variances.append(price_diff)
                notes.append(
                    f"Price variance: {inv_item['sku']} invoiced ${inv_item['unit_price']:.2f} "
                    f"vs PO ${po_item['unit_price']:.2f} ({price_pct:.1f}% diff)"
                )

            # Quantity check (against receipt if available)
            expected_qty = receipt_item["qty_received"] if receipt else po_item["qty"]
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
            notes=notes
        )

    def reconcile_batch(self, invoices: List[Invoice],
                        pos: Dict[str, PurchaseOrder],
                        receipts: Dict[str, GoodsReceipt]) -> List[ReconciliationResult]:
        """Reconcile multiple invoices against PO and receipt databases."""
        results = []
        for inv in invoices:
            po = pos.get(inv.vendor)  # Simplified — real matching by PO number
            receipt = receipts.get(po.po_number) if po else None
            results.append(self.reconcile(inv, po, receipt))
        return results

    def generate_report(self, results: List[ReconciliationResult]) -> Dict:
        """Generate summary report for finance team review."""
        from collections import Counter

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
            "results": [self._result_to_dict(r) for r in results]
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
            "notes": r.notes
        }
```

## Input Data Formats

### Invoices (CSV/Excel)
```csv
invoice_number,vendor,invoice_date,due_date,sku,description,qty,unit_price,total
INV-001,Acme Supply,2026-06-15,2026-07-15,SKU-100,Plywood 4x8,50,28.50,1425.00
INV-001,Acme Supply,2026-06-15,2026-07-15,SKU-200,Drywall Sheet,100,12.00,1200.00
```

### Purchase Orders (CSV/Excel)
```csv
po_number,vendor,po_date,sku,description,qty,unit_price,total
PO-2026-045,Acme Supply,2026-06-01,SKU-100,Plywood 4x8,50,28.00,1400.00
PO-2026-045,Acme Supply,2026-06-01,SKU-200,Drywall Sheet,100,12.00,1200.00
```

## Edge Cases to Handle

1. **Split POs** — Invoice covers items from multiple POs
2. **Partial receipts** — PO for 100, only 90 received, vendor invoices 100
3. **Backordered items** — PO exists but item not yet received
4. **Vendor name mismatches** — "Acme Supply Co." vs "Acme Supply Co., Inc."
5. **Rounding differences** — $0.01 variances on every line item
6. **Tax handling** — Invoice includes tax, PO doesn't (or vice versa)
7. **Credit memos** — Negative amounts, apply against original invoice

## Output

The reconciliation report is a dictionary that can be exported to:
- Excel (pandas `to_excel`)
- CSV (pandas `to_csv`)
- JSON (for API integration)
- Email alert (via n8n workflow)

## Integration Points

- **QuickBooks Online API** — Pull PO and invoice data directly
- **n8n workflow** — Auto-trigger on new invoice email
- **Slack/Teams** — Send review queue notifications
- **Trailwise SaaS** — Managed version with dashboard ($49/mo)


---

## One-Shot vs Ongoing

This skill runs a **one-time analysis**. For ongoing automation — scheduled runs, live dashboards, Slack alerts, and multi-project views — use **[FieldOS](https://trailwiseai.com)**.

| This skill does | FieldOS does ($49/mo) |
|-----------------|----------------------|
| Runs when you remember | Runs weekly, alerts on Slack |
| Reads a CSV you export | Pulls from QuickBooks automatically |
| Text report output | Live dashboard with charts |
| Single project at a time | Multi-project consolidated view |
| No history | Trend tracking, month-over-month |

**[Start with FieldOS →](https://trailwiseai.com)** · **[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
