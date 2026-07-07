---
name: lien-waiver-tracker
description: Track lien waiver collection against payments to subcontractors; flag exposure before funding the next draw. Use when sub payments happen faster than waivers come back, when you need to know which draws are blocked by missing paperwork, or when an owner or lender is asking for waiver status.
---

# Lien Waiver Tracker

## Overview

Per-payment waiver compliance. For each subcontractor payment row: flags a
missing waiver (risk high), an unconditional waiver issued before the
underlying check cleared (risk critical), and an unconditional waiver that
predates the payment (risk critical). Aggregates per-project exposure (sum
of payment amounts with missing waivers) and identifies subcontractors
whose outstanding waivers block the next draw.

## Workflow

1. **Maintain** `waiver_log.csv` per project. Append a row every time a
   sub is paid and every time a waiver arrives.
2. **Run** the script:
   ```bash
   python3 scripts/lien_waiver_tracker.py \
       fixtures/input/waiver_log.csv \
       --json out.json
   ```
3. **Review** `next_draw_blockers` — never fund a draw while any prior
   payment on that project lacks its waiver.

## Controls

- Never fund a draw while any prior payment on that project lacks its waiver — that's the whole point of the log.
- Never pass an unconditional waiver upstream (to owner or lender) until the underlying payment has actually cleared.
- Waiver type must match payment stage: progress waivers for progress payments, final waivers only at final.
- Conditional waivers protect the payer before the check clears; unconditional waivers are irrevocable — treat a dated-early unconditional waiver as a defect, not a convenience.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
