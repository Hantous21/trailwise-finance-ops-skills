---
name: retainage-tracker
description: Track retainage receivable, release milestones, and overdue releases across projects. Use when retainage lives in a spreadsheet, when you need to chase the owner for releases past substantial completion, or when preparing the receivables aging for the month-end close.
---

# Retainage Tracker

## Overview

Per-project retainage accounting. For each draw: verifies the withheld
amount matches the contract rate (within tolerance), tracks cumulative
withheld / released / outstanding, flags rate changes mid-project, and
flags releases overdue past substantial completion. Sums total outstanding
receivable across the portfolio.

## Workflow

1. **Export** retainage activity as CSV (see `fixtures/input/retainage_draws.csv`).
2. **Run** the script:
   ```bash
   python3 scripts/retainage_tracker.py \
       fixtures/input/retainage_draws.csv \
       --as-of 2026-07-01 \
       --json out.json
   ```
3. **Review** `out.json` — chase releases for any project with
   `release_overdue` or `over_release`.

## Flags (per project)

- `withholding_mismatch` — actual withheld differs from
  `gross_billed * pct / 100` by more than the tolerance.
- `over_release` — released > withheld on a project.
- `retainage_rate_change` — `retainage_pct` differs across a project's draws.
- `release_overdue` — outstanding > 0 past `release_due_days` from substantial completion.

## Controls

- Retainage is your money — carry it as a receivable with an owner and a date, not a memo item.
- Verify withheld amount against the contract rate on every draw; rate changes mid-project are a dispute magnet — flag them.
- The release clock starts at substantial completion, not final invoice. Know your state's statutory release deadline.
- Never net a release against new withholding on another project.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
