---
name: "budget-variance-tracker"
description: "Track budget vs actual costs in real-time. Flag overruns, forecast final costs via burn-rate projection, and trigger alerts when thresholds are breached."
homepage: "https://trailwiseai.com"
disable-model-invocation: true
metadata:
  trailwise:
    emoji: "📊"
    category: "budget-management"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
---

# Budget Variance Tracker

## Overview

Compare budgeted costs against actual spending in real-time. Flag cost overruns
before they happen, forecast final project costs using burn-rate analysis, and
trigger alerts when budget thresholds are breached. All logic lives in
`scripts/budget_variance_tracker.py` — import `BudgetVarianceTracker` and run.

## Workflow

1. **Export** budget data to CSV (columns: `cost_code,category,description,budgeted_amount,spent_to_date,committed,percent_complete`).
2. **Load** the CSV via `load_from_csv(tracker, path)` or construct `BudgetLine` objects directly.
3. **Forecast** final costs with `tracker.get_summary()` — projected total derives from burn-rate projection (see Controls).
4. **Alert** by running `tracker.check_alerts()` — returns a `BudgetAlert` per cost code with level and message.
5. **Drill down** on any flagged code with `tracker.get_cost_code_detail(code)` for variance, burn rate, and forecast breakdown.
6. **Route** alerts by level (see Alert Routing table) — GREEN to weekly digest, RED to SMS, CRITICAL to ownership escalation.

## Controls

- **burn-rate projection**: `spent / %complete = projected total` — the core forecasting concept. If you've spent $30k to get 60% done, projected total is $50k. Treat forecasts below 20% complete as low-confidence.
- **Committed cost**: `spent_to_date + committed` (POs/contracts signed but not yet invoiced) — alert thresholds key off total committed, not just spent.
- **Threshold defaults**: 50 / 75 / 90 / 95% of budget — adjustable per project via the `thresholds` dict.
- **CRITICAL trigger**: forecast exceeds 110% of budgeted amount — escalates regardless of current usage.
- **Zero-budget guard**: lines with `budgeted_amount == 0` return 0% variance; flag separately as unbudgeted work.

## Alert Thresholds (Reference)

| Level | Usage of budget | Meaning |
|-------|-----------------|---------|
| GREEN | < 50% | On track |
| YELLOW | 50–75% | Monitor |
| ORANGE | 75–90% | Action recommended |
| RED | 90–95%+ or forecast > budget | Over threshold |
| CRITICAL | Forecast > 110% of budget | Escalate to ownership |

## Alert Routing (Reference)

| Level | Channel |
|-------|---------|
| GREEN | Weekly digest email |
| YELLOW | Daily dashboard update |
| ORANGE | Slack/Teams ping to project manager |
| RED | Email + SMS to finance director |
| CRITICAL | Escalation to ownership |

## Edge Cases

1. **Zero-budget lines** — cost codes with no budget but actual spending (unbudgeted work); flag separately.
2. **Negative variance at 10% complete** — early-stage overrun, high uncertainty in burn-rate forecast.
3. **Committed but not spent** — large PO signed, no invoice yet; counts toward total committed.
4. **Cost code reclassification** — item moved from 04000 to 04100 mid-project; reconcile both codes.
5. **Contingency drawdown** — moving money from contingency to specific cost codes; track as a transfer, not new spend.

All code lives in `scripts/budget_variance_tracker.py` — import `BudgetVarianceTracker` and run.
