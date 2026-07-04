---
name: "change-order-tracker"
description: "Classify, cost, and track construction change orders. Calculate cumulative impact on the contract sum, flag severity, and generate dispute documentation packets."
homepage: "https://trailwiseai.com"
disable model invocation: true
metadata:
  trailwise:
    emoji: "📝"
    category: "construction-billing"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas"]
---

# Change Order Tracker

## Overview

Track construction change orders from initiation through approval. Classifies CO
type from the description, calculates cost + schedule impact, scores severity, and
produces a cumulative impact report against the original contract sum. Generates a
dispute documentation packet when an invoice or sub invoice doesn't match approved
scope. All logic lives in `scripts/change_order_tracker.py` — import
`ChangeOrderManager` and run.

## Workflow

1. **Export** change orders to CSV (columns: `id,project_id,title,description,initiated_by,responsibility,status,submitted_date,approved_date,labor,materials,equipment,subcontractor,overhead,profit,direct_days,ripple_days,critical_path_affected,affected_cost_codes`).
2. **Load** the CSV via `manager.load_csv(path)` — each row is classified by keyword and severity-scored on ingest.
3. **Review** the cumulative impact with `manager.cumulative_impact()` — approved COs adjust the contract sum; pending COs are totaled separately.
4. **Flag** any CO whose severity is `major` or `critical`, or where cumulative approved cost exceeds 10% of the original contract — these warrant PM escalation before the next pay app.
5. **Generate** a dispute packet with `manager.generate_dispute_packet(co_id)` when an invoice doesn't match approved scope — returns a markdown draft for human review.
6. **Route** approved COs to `payment-app-generator` (G702 contract sum modifications) and `budget-variance-tracker` (update `scheduled_value_co` lines).

## Controls

- **Never auto-approve.** COs require explicit human sign-off; this skill only reports status from the CSV.
- **Never auto-modify the budget.** Flag affected cost codes and let the PM update the budget — do not write to budget lines directly.
- **Never auto-post to accounting.** Generate the journal entry / dispute packet for review only.
- **Negative COs need documented reason.** Deductions without justification are disputes waiting to happen — severity is forced to `minor` but the dispute packet must capture the rationale.
- **Dispute packets are drafts.** A human reviews every packet before it goes to the client or attorney — never send generated markdown unreviewed.
- **Classification is keyword-based and deterministic.** `classify_description` matches the first keyword group that hits; the default is `scope_change`. Override the assigned type manually when the description is ambiguous.
- **Severity is the higher of cost-based or schedule-based.** See the Severity Scoring table; the manager picks whichever axis scores worse.

## Classification Rules (Reference)

Keyword-based mapping (deterministic, testable):

| Keywords | Type |
|----------|------|
| design, drawing, specification, revision | design_change |
| owner, client, request, want, need | owner_request |
| site, field, condition, unforeseen, soil, weather | field_condition |
| code, regulation, compliance, AHJ, inspector | code_compliance |
| value, alternative, savings, VE, optimize | value_engineering |
| error, omission, mistake, missing, forgot | error_omission |
| (default — no keyword match) | scope_change |

## Severity Scoring (Reference)

Severity is the higher of cost-based or schedule-based:

| Cost % of Contract | Schedule Days | Severity |
|-------------------|---------------|----------|
| < 1% | < 7 | minor |
| 1–5% | 7–30 | moderate |
| 5–10% | 30–90 | major |
| > 10% | > 90 | critical |

## Edge Cases

1. **Negative CO (deduction)** — reduces the contract sum; severity forced to `minor`, but the dispute packet must document the reason.
2. **Schedule-only CO** — severity is driven by schedule days; cost is `$0`.
3. **Unapproved CO** — excluded from the cumulative approved total; counted only in pending.
4. **Duplicate CO number** — `add_change_order` raises `ValueError`; load halts until the duplicate is resolved.
5. **CO with zero cost and zero schedule** — `minor` by default.

All code lives in `scripts/change_order_tracker.py` — import `ChangeOrderManager` and run.
