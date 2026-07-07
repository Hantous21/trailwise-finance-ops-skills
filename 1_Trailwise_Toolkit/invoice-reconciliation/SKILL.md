---
name: invoice-reconciliation
description: Use when matching vendor invoices to purchase orders and goods receipts — flag price/quantity variances, unmatched invoices, and route approvals within tolerance.
---

# Invoice Reconciliation

## Overview

Match vendor invoices to purchase orders (POs) and goods receipt records; flag price and quantity variances, unmatched invoices, and route each invoice to an approval action within configurable tolerances. The reconciliation engine lives in `scripts/invoice_reconciliation.py`; this document describes how to run it and what to watch for.

## When to Use

- You receive 20+ vendor invoices per week matched manually in Excel or QuickBooks.
- Discrepancies (wrong quantity, wrong price) are caught too late.
- Approval routing happens over email with no audit trail.

## Workflow

1. **Load inputs** — export invoices, POs, and goods receipts to CSV (see fixtures for column schemas).
2. **Run the engine** — `python3 scripts/invoice_reconciliation.py <invoices.csv> <pos.csv> <receipts.csv>`. Import `InvoiceReconciler` directly for batch/programmatic use.
3. **Three-way match** — for each invoice line, the engine looks up the PO line by SKU, then the matching receipt line by SKU, and compares invoiced qty against received qty (falling back to PO qty when no receipt line exists).
4. **Classify** — each invoice becomes `matched`, `price_variance`, `qty_variance`, `partial_match`, or `unmatched`.
5. **Route** — `auto_approve` (within tolerance and under the dollar threshold), `review`, `reject` (>10% price variance), `escalate` (above 10× threshold), else `review`.
6. **Report** — `generate_report()` returns a summary dict exportable to Excel/CSV/JSON.

## Controls

- **three-way match: invoice ↔ PO ↔ receipt** — reconcile each line against the PO price and the received quantity; never treat an invoice as matched without confirming both.
- **tolerance gating** — price variance default 2%, quantity variance default 5%; only deviations exceeding tolerance become variances.
- **auto-approval ceiling** — `auto_approve_threshold` (default $500); matched invoices above it still require `review`.
- **unmatched handling** — invoices with no PO return `unmatched` and route to `review`; never auto-approve them.
- **receipt lookup by SKU** — when a receipt is provided, look up its line item by SKU before using `qty_received`; fall back to the PO `qty` only when no receipt line matches (this is the fix for the prior `NameError` on `receipt_item`).

## Configuration

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `price_tolerance_pct` | 2.0 | Allowed price variance % |
| `qty_tolerance_pct` | 5.0 | Allowed quantity variance % |
| `auto_approve_threshold` | 500.0 | Max $ for auto-approval |

## Edge Cases (Reference)

1. **Split POs** — invoice covers items from multiple POs (batch matcher keys POs by vendor; extend for multi-PO matching).
2. **Partial receipts** — PO for 100, only 90 received, vendor invoices 100 → flagged as qty variance.
3. **Backordered items** — PO exists but item not yet received → falls back to PO qty.
4. **Vendor name mismatches** — "Acme Supply Co." vs "Acme Supply Co., Inc." normalize before matching.
5. **Rounding differences** — $0.01 variances stay under tolerance.
6. **Tax handling** — invoice includes tax, PO doesn't (or vice versa); reconcile on pre-tax line totals.
7. **Credit memos** — negative amounts applied against the original invoice.

## Input Schemas

Invoices CSV: `invoice_number,vendor,invoice_date,due_date,sku,description,qty,unit_price,total`
POs CSV: `po_number,vendor,po_date,sku,description,qty,unit_price,total`
Receipts CSV: `receipt_number,po_number,received_date,sku,qty_received`

---

Run `python3 scripts/invoice_reconciliation.py --help` and reconcile against `fixtures/input/` to verify before relying on the output.
