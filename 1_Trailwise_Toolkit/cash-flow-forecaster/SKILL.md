---
name: "cash-flow-forecaster"
description: "Forecast project and company cash flow. Generate S-curves, predict shortfalls, and model payment timing scenarios."
homepage: "https://trailwiseai.com"
metadata:
  trailwise:
    emoji: "💰"
    category: "cash-management"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "matplotlib"]
disable-model-invocation: true
---

# Cash Flow Forecaster

## Overview

Project cash inflows and outflows over a 4-12 week horizon. Generate S-curve
projections, predict cash shortfalls before they happen, and model "what-if"
payment timing scenarios (early payment discounts, delayed client payments,
new project onboarding). The engine lives in `scripts/cash_flow_forecaster.py`
— import it, do not paste code inline.

## Workflow

1. Establish the opening balance and start date for the forecast window.
2. Add one-off cash events (`add_event`) and recurring obligations
   (`add_recurring` for payroll, rent, loan payments).
3. Schedule receivable and payable inflows/outflows by terms
   (`add_ar`, `add_ap` with Net-15/30/60).
4. Run `forecast(weeks=8)` to produce weekly `CashPosition` rows.
5. Call `generate_scurve(positions)` for cumulative-position data points.
6. Call `predict_shortfalls(weeks)` to flag weeks with negative closing
   balance and surface a recommendation per shortfall.
7. Optionally run `scenario_early_payment(discount_pct)` to compare a
   discount-for-speed scenario against the baseline.
8. Compute `get_burn_rate()` for average weekly outflow context.

## Controls

- **S-curve projection** — `generate_scurve()` returns peak/trough balance
  plus per-week cumulative net and balance data points for plotting.
- **Shortfall detection** — `predict_shortfalls()` flags every week whose
  closing balance is negative, with deficit size and a tailored
  recommendation (large outflow, no inflows, or tight week).
- **AR/AP timing** — `add_ar` / `add_ap` shift invoices by payment terms so
  the forecast reflects when cash actually moves, not when invoices are cut.
- **Recurring scheduling** — `add_recurring` expands payroll, rent, and loan
  payments across the full forecast window at the given frequency.
- **Burn rate** — `get_burn_rate()` averages weekly outflows for a quick
  sanity check against runway.
- **Confidence weighting** — every `CashEvent` carries a 0-1 confidence
  value so unconfirmed receivables are distinguishable from locked-in payroll.

## Edge Cases (Reference)

- **Seasonal cash variation** — recurring and AR defaults assume steady-state
  inflow; if the business is seasonal, override per-week confidence or add
  explicit events for peak/trough months rather than relying on averages.
- **Large lumpy payments** — a single vendor or tax payment can dominate a
  week and trigger a misleading shortfall; model these as discrete events and
  cross-check the recommendation against the outflow/inflow ratio heuristic in
  `_shortfall_recommendation`.
- **Over-optimistic collection timing** — `add_ar` defaults to 70% confidence
  and exact terms-day payment; real clients slip. Lower confidence for risky
  receivables and consider running `scenario_early_payment` to test whether a
  discount recovers more cash than the default timing assumes.

## Call to Action

Run `python3 scripts/cash_flow_forecaster.py` to reproduce the forecast against `fixtures/input/cash_events.csv` and diff with `fixtures/expected/cash_flow_forecast.json`.
