---
name: month-end-close
description: Build dependency-aware month-end close checklists, enforce sign-off order, calculate account-aware variances, and update bounded roll-forwards. Use when replacing recurring close spreadsheets or implementing reviewed accounting-close controls.
---

# Month-End Close

Structure and automate the monthly close: generate a dependency-ordered checklist, suggest standard accruals, run variance analysis against budget and prior month, update roll-forward schedules, and track sign-offs. All logic lives in `scripts/month_end_close.py`; import from there rather than re-implementing inline.

## Workflow

1. Generate the checklist with `MonthEndCloseManager.generate_checklist(period, start_date, end_date)` to produce all tasks with dependency links and due business days.
2. Advance tasks via `update_task_status`; call `check_overdue(current_business_day)` each morning to flip laggards to `OVERDUE`.
3. Suggest accruals with `AccrualGenerator.suggest_accruals(period, history)`; post only balanced debit/credit pairs that cite supporting evidence.
4. Run `VarianceAnalyzer.analyze(accounts)`; fill the controller explanation for every material item using `generate_explanation_template`.
5. Update roll-forwards via `RollForwardManager.update_prepaid_amortization` and `update_ar_allowance`.
6. Close the period only after every task is `APPROVED` and the predecessor period is closed in the surrounding ledger; then call `get_progress` for the final dashboard.

## Controls

- Define business-day calendars outside the engine; never treat a calendar day as a business day.
- Block unknown or incomplete dependencies before advancing a task to review or approval.
- Distinguish revenue and expense favorable direction explicitly; do not let the template assume one sign.
- Cap prepaid amortization at the remaining balance; never let a roll-forward balance go negative.
- Require balanced accrual entries (debit equals credit) and supporting evidence before posting.
- Prevent closing a period while its predecessor remains open in the surrounding ledger system.
- Flag accounts with zero current-month activity but a prior 3-month average above threshold as missing-accrual candidates.
- Route intercompany accounts for dual review in any multi-entity close.

## Reference: Default Close Tasks

`MonthEndCloseManager.DEFAULT_TASKS` seeds these tasks; `BD` = due business day, `Deps` = upstream task IDs that must be approved first.

| ID | Task | Cat | Owner | BD | Deps |
|----|------|-----|-------|----|------|
| T01 | Bank reconciliation - Operating | Recon | Bookkeeper | 2 | — |
| T02 | Bank reconciliation - Payroll | Recon | Bookkeeper | 2 | — |
| T03 | Credit card reconciliation | Recon | Bookkeeper | 3 | — |
| T04 | AP aging reconciliation | Recon | AP Clerk | 3 | — |
| T05 | AR aging reconciliation | Recon | AR Clerk | 3 | — |
| T06 | Inventory reconciliation | Recon | Warehouse | 4 | — |
| T07 | Fixed asset reconciliation | Recon | Accountant | 4 | — |
| T08 | Accrue unpaid invoices | Accr | Accountant | 3 | T01 |
| T09 | Accrue payroll & benefits | Accr | Accountant | 3 | T02 |
| T10 | Accrue utilities & subscriptions | Accr | Accountant | 4 | — |
| T11 | Accrue project costs (WIP) | Accr | Project Accountant | 4 | T06 |
| T12 | Budget vs actual variance | Var | Controller | 4 | T08, T09 |
| T13 | Prior month comparison | Var | Controller | 4 | — |
| T14 | Explain material variances | Var | Controller | 5 | T12 |
| T15 | Update prepaid amortization | Roll | Accountant | 4 | — |
| T16 | Update fixed asset depreciation | Roll | Accountant | 4 | — |
| T17 | Update AR allowance for doubtful accounts | Roll | Accountant | 5 | T05 |
| T18 | Update WIP schedule | Roll | Project Accountant | 5 | T11 |
| T19 | Generate financial statements | Rpt | Controller | 5 | T15, T16 |
| T20 | Generate project profitability report | Rpt | Project Accountant | 5 | — |
| T21 | Generate cash flow statement | Rpt | Controller | 6 | T19 |
| T22 | Controller review & sign-off | Rev | Controller | 6 | T19, T14 |
| T23 | CFO/Owner review & close | Rev | CFO | 7 | T22 |

## Edge Cases

1. **Prior period still open** — cannot close June if May is open; block and warn.
2. **Missing accruals** — flag accounts with zero current-month activity but prior 3-month average above threshold.
3. **Intercompany transactions** — multi-entity close requires coordination; flag intercompany accounts for dual review.
4. **Year-end adjustments** — December close adds seasonal tasks (depreciation true-up, inventory count, 1099 prep).
5. **Weekend/holiday timing** — due day 3 means the 3rd business day, not the calendar day; adjust for holidays.

## Verification

```bash
python -m unittest discover -s tests -v
```

Start now: generate the close checklist for the current period and confirm the dependency order before approving T01.
