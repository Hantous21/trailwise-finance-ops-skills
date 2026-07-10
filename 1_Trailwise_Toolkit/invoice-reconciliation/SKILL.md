---
name: invoice-reconciliation
description: Use when matching vendor invoices to purchase orders and goods receipts — flag price/quantity variances, unmatched invoices, and route approvals within tolerance.
---

# Invoice Reconciliation

## Overview

Match vendor invoices to purchase orders (POs) and goods receipt records; flag price and quantity variances, unmatched invoices, and route each invoice to an approval action within configurable tolerances. The reconciliation engine lives in `scripts/invoice_reconciliation.py`; this document describes how to run it and what to watch for.

## File Organization (Pre-Reconciliation)

Before reconciling invoices against POs, you often need to organize a chaotic folder
of PDFs, images, and downloads into a clean filing system. Use
`scripts/invoice_file_organizer.py` for this.

```bash
# Dry run first — see what would happen
python3 scripts/invoice_file_organizer.py /path/to/messy/folder --dry-run

# Organize (copies files, preserves originals)
python3 scripts/invoice_file_organizer.py /path/to/messy/folder --output /path/to/organized

# Move instead of copy (use with caution)
python3 scripts/invoice_file_organizer.py /path/to/messy/folder --move
```

**What it does:**
1. Scans for PDFs, images, and documents (recursive)
2. Extracts vendor, date, invoice number, amount from text content + filename
3. Identifies construction document types (AIA G702/G703, change orders, submittals, COIs, lien waivers, W-9s)
4. Renames files: `YYYY-MM-DD Vendor - Invoice - Description.ext`
5. Sorts into: `Year/Category/Vendor/` folder structure
6. Detects duplicates via SHA-256 hash
7. Flags files needing manual review (missing vendor/date)
8. Generates `invoice-summary.csv` for accounting import

**Construction document categories recognized:**

| Pattern | Category | Doc Type |
|---------|----------|----------|
| G702, application for payment | Pay Applications | aia_g702 |
| G703, schedule of values | Pay Applications | aia_g703 |
| Change order, CO#, directive | Change Orders | change_order |
| Submittal, transmittal | Submittals | submittal |
| Certificate of Insurance, COI, ACORD 25 | Insurance | coi |
| Lien waiver, conditional/unconditional | Legal | lien_waiver |
| W-9, taxpayer, TIN | Tax Forms | w9 |

**Controls:**
- **Copies by default** — originals are preserved unless `--move` is passed.
- **Dry run first** — always run with `--dry-run` before organizing to preview.
- **Review queue** — files where vendor or date can't be extracted are flagged, not silently misfiled.
- **Dedup by hash** — exact duplicate files (same SHA-256) are skipped and reported.
- **No OCR built in** — the organizer uses text content passed from the calling agent (which has vision/OCR). Binary files with no extractable text fall back to filename clues + file modification date.

## Reconciliation (Three-Way Match)

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
