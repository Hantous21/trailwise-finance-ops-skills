---
name: ar-aging-excel
description: Build an AR aging Excel workbook (summary + chart + invoice detail) from an invoice export. Use when the owner or CFO wants the aging as a spreadsheet they can forward, not a JSON report.
---

# AR Aging Excel

## Overview

Generates an AR aging workbook from a CSV invoice export. The workbook has
two sheets: **Aging Summary** (bucket totals, percent of outstanding, a
bar chart) and **Invoice Detail** (one row per open invoice). The bucket
math mirrors `ar-collections-automation` so the two reports agree to the
penny — same edges, same as-of date, same totals.

**Requires:** `openpyxl` (`pip install openpyxl`).

## Workflow

1. Export the invoice ledger as CSV with the same schema as
   `fixtures/input/invoices.csv` (`id, client_id, client_name, invoice_date,
   due_date, amount, amount_paid, status`).
2. Run the script:
   ```bash
   python3 scripts/ar_aging_excel.py \
       fixtures/input/invoices.csv \
       --as-of 2026-06-30 \
       --out ar_aging_2026-06-30.xlsx
   ```
3. Open the .xlsx in Excel / LibreOffice. The Aging Summary sheet shows the
   four bucket amounts, a percent-of-outstanding column, and a bar chart.
4. Forward the file as-is to the owner or CFO.

## Bucket edges (must match ar-collections-automation)

- `current` — 0 to 30 days past due
- `31_60` — 31 to 60 days
- `61_90` — 61 to 90 days
- `90_plus` — 91+ days
- `paid` — excluded from the report entirely

## Controls

- **Buckets must tie to `ar-collections-automation` to the penny** — two
  reports with different aging is worse than none. If the numbers drift,
  fix the bucketing, do not adjust the goldens.
- **The workbook is a snapshot** — stamp the as-of date on the summary
  sheet (cell A2). Use a new file per reporting date, do not edit in
  place.
- **Requires `openpyxl`** — `pip install openpyxl` is in the prerequisites.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
