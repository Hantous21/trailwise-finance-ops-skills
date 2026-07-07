---
name: wip-schedule-generator
description: Build a cost-to-cost WIP schedule with over/under billing flags per job. Use when preparing the monthly WIP report for bonding, banks, or owners, or when investigating why a job's billings don't match its cost-to-date.
---

# WIP Schedule Generator

## Overview

Cost-to-cost (percentage-of-completion) work-in-progress schedule. For each
job: revised contract, percent complete, earned revenue, over/under billing,
and flags for underbilling above threshold, cost overruns, percent complete
above 100, and billings above the revised contract. Aggregates total
overbilled, total underbilled, total earned, total billed, and the count of
flagged jobs across the schedule.

## Workflow

1. **Export** the job roster as CSV (see `fixtures/input/wip_jobs.csv`).
2. **Run** the script:
   ```bash
   python3 scripts/wip_schedule_generator.py \
       fixtures/input/wip_jobs.csv \
       --json out.json
   ```
3. **Review** `out.json` — every flag warrants a comment on the WIP cover page.

## Flags (per job)

- `underbilled_above_threshold` — underbilling magnitude exceeds the
  configured dollar amount OR percentage threshold (defaults: $25,000 / 5%).
- `cost_overrun` — estimated total cost > revised contract.
- `percent_complete_over_100` — raw cost-to-cost > 100% (estimate stale).
- `billed_over_contract` — billings > revised contract.

## Controls

- Earned revenue = percent complete × revised contract, cost-to-cost method only; never book revenue off billings.
- Underbillings are a red flag, not an asset — usually unapproved change orders or job borrowing. Investigate before the bank does.
- Never report percent complete above 100 — cap it and flag the estimate as stale.
- The WIP schedule drives bonding capacity; run it monthly, not at renewal.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
