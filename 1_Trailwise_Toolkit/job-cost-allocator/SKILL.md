---
name: job-cost-allocator
description: Allocate raw transactions (QuickBooks/bank export) to jobs and cost codes via a rules file; unmatched transactions land in a review queue. Use when job-cost coding is manual, when transaction data is too messy for a straight mapping, or when you need a CI-able gate on allocation coverage.
---

# Job Cost Allocator

## Overview

Rule-based cost allocation. Loads an `allocation_rules.csv` (priority,
match field, pattern, job, cost code) and a `transactions.csv`; sorts rules
by priority; for each transaction, applies the first rule whose pattern
appears (case-insensitive substring) in the named field. Unmatched
transactions get `status: "unallocated"` and a per-row review queue. The
CLI exposes a `--min-allocated-pct` gate for CI.

## Workflow

1. **Maintain** `allocation_rules.csv` (priority, match_field, pattern,
   job_number, cost_code). Rules are sorted by priority ascending; first
   match wins; ties broken by file order.
2. **Run** the script:
   ```bash
   python3 scripts/job_cost_allocator.py \
       fixtures/input/transactions.csv \
       fixtures/input/allocation_rules.csv \
       --json out.json
   ```
3. **Review** the unallocated queue in `out.json` and add rules for any
   new vendors / descriptions that recur.

## Controls

- Never guess silently: no fuzzy matching, no "probably J-101". Unmatched lands in the review queue for a human.
- Rules are data, not code — the CSV is the audit trail for why a cost hit a job.
- Re-runs are idempotent: same inputs, same allocation, byte-for-byte.
- Watch the allocated % — below ~90% your job-cost reports (and your WIP schedule) are fiction.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
