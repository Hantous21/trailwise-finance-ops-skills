---
name: payment-app-generator
description: Generate AIA G702/G703 payment applications with completed work, retainage, and current amount due. Use when preparing monthly pay apps, checking continuation sheet math, or exporting structured pay-app data.
---

# Payment Application Generator (AIA G702/G703)

## Overview

Generate AIA-style payment applications from a project schedule of values. Calculate percent complete, retainage, previous payments, and current amount due. Produces both the G702 (summary) and G703 (continuation sheet) data structures. Reference implementation lives in `scripts/payment_app.py`.

## Workflow

1. Collect the schedule of values (CSV) and approved change orders for the billing period.
2. Build `ScheduleOfValuesLine` rows from the CSV; set `previous_completed` from the prior app and `current_completed` from this period's field reports.
3. Construct a `PaymentApplication` with project, contractor, owner, architect, contract date, period-to date, and original contract sum.
4. Run `G702Generator().generate(app)` for the G702 summary and `.generate_g703(app)` for the G703 continuation rows.
5. Export the result to CSV or hand to a PDF renderer (reportlab) for the signed AIA form.
6. For multi-period projects, use `PaymentAppHistory.create_next_app()` to carry forward prior totals automatically.
7. Human review and signature before anything goes to the owner/GC.

## Controls

- **Never auto-submit to client** — generate the app for human review first; a signed copy is the legal record.
- **Verify quantities** — AI-extracted % complete must be validated against field reports before billing.
- **Retainage is legal money** — wrong retainage calculation = contract dispute; double-check the `retainage_pct` per line and on the summary.
- **Line 7 defaults to a derivation from G703 previous-completed (assumes constant retainage, no prior stored materials)** — pass `previous_certificates` explicitly when you have the prior certificate.
- **Store signed copies** — every pay app should have a PDF + approval signature on file.

## CSV Input Format

Schedule of Values:

```csv
line_no,description,scheduled_value,scheduled_value_co,previous_completed,current_completed,stored_materials,retainage_pct
1,02200 - Site Work,45000,0,45000,0,0,10
2,03300 - Cast-in-Place Concrete,85000,5000,60000,15000,0,10
3,04200 - Steel Erection,120000,0,80000,20000,5000,10
```

Change Orders:

```csv
co_number,description,amount,approved,approved_date
CO-001,Additional concrete for foundation revision,5000,yes,2026-05-15
CO-002,Steel grade upgrade,8000,yes,2026-06-01
CO-003,Delete redundant partition,-3000,no,
```

## G702 Output Example

```
AIA G702 — APPLICATION AND CERTIFICATE FOR PAYMENT
Application No: 3              Period To: 2026-06-30
Project: Riverside Office Building
Contractor: Trailwise Construction   Owner: Riverside Development LLC
Architect: Smith & Associates

Original Contract Sum:        $340,000.00
Net Change Orders:             +$13,000.00
Contract Sum to Date:          $353,000.00
Total Completed & Stored:      $252,000.00
Less Retainage (10%):         -$25,200.00
Total Earned Less Retainage:  $226,800.00
Less Previous Payments:      -$162,000.00
────────────────────────────────────────────
CURRENT AMOUNT DUE:            $64,800.00
────────────────────────────────────────────
Balance to Finish:            $101,000.00
Percent Complete:              71.39%
```

## Edge Cases (Reference)

1. **First pay app** — No previous payments; `previous_payments = 0`, `app_number = 1`.
2. **Retainage release** — Final pay app releases all retainage; set `retainage_pct = 0` on the final app.
3. **Stored materials** — Delivered but not installed; counted in completed+stored, not in % complete.
4. **Negative change orders** — Deductions reduce contract sum; `scheduled_value_co` may be negative.
5. **Overbilling correction** — If the prior period was overbilled, the current period can be negative; flag for review.
6. **Joint check** — Multiple payees; G702 has fields for joint payee.
7. **Sales tax** — Some states require tax as a separate line; check local requirements.
8. **Final waiver** — Final pay app requires an unconditional lien waiver; link to lien-waiver-manager.

Run `python3 scripts/payment_app.py` to import the reference classes and generate a pay app from your CSV inputs.
