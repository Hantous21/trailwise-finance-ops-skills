---
name: daily-sales-reconciliation
description: Tie out daily POS sales to bank deposits — cash variances, missing deposits, and card-processor fee drift. Use when the daily deposit doesn't match the Z-report, when reconciliation happens monthly instead of daily, or when card fees creep without anyone noticing.
---

# Daily Sales Reconciliation

## Overview

Tie each POS day's cash and card totals to the bank deposits dated
`date + deposit_lag_days` (default 1). Flags four conditions per day:

- **`missing_deposit`** — no cash deposit landed at the lag date.
- **`cash_short`** / **`cash_over`** — variance beyond tolerance (default $5).
- **`missing_settlement`** — no card deposit landed at the lag date.
- **`fee_out_of_band`** — card processor fee % outside [1.5, 4.0].

Pure Python, no third-party dependencies. Money rounded to 2dp at output
boundaries.

## Workflow

1. Export the POS Z-report as `pos_daily.csv` (date, gross_sales,
   sales_tax, comps, cash_collected, card_collected).
2. Export the bank deposits as `bank_deposits.csv` (deposit_date, type,
   amount) where type ∈ {`cash`, `card`}.
3. Run the script:
   ```bash
   python3 scripts/daily_sales_reconciliation.py \
       pos_daily.csv bank_deposits.csv \
       --json reconciliation.json
   ```
4. Review the JSON — every flag is a same-day action item. A missing
   Wednesday deposit is findable Thursday and gone by the 30th.
5. Escalate `cash_short` after one occurrence, treat as a control failure
   after three — name a person per drawer.

## Controls

- **Reconcile daily, not at month-end** — a missing Wednesday deposit is
  findable Thursday and gone by the 30th.
- **A cash short is a coaching conversation after one and a control
  failure after three** — name a person per drawer.
- **Fee drift compounds** — anything out of band goes to the processor
  statement, not a shrug.
- **Never book POS totals to the ledger without the deposit tie-out.**

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
