---
name: prime-cost-tracker
description: Track weekly prime cost (food + beverage COGS + labor) against the 60/65 benchmark band from a simple P&L export. Use when prime cost is only computed at month-end, when food cost is creeping and nobody can say which week it started, or when the owner wants one number that says whether the restaurant made money on operations.
---

# Prime Cost Tracker

## Overview

Weekly prime-cost tracking from a simple P&L export. Prime cost = food COGS
+ beverage COGS + total labor. **True COGS**, not purchases:
`COGS = purchases + beginning_inventory − ending_inventory`.

Benchmark band: `prime_pct ≤ 60.00` → `ok`; `60.00 < prime_pct ≤ 65.00` →
`watch`; `> 65.00` → `over`. Each week reports status and a week-over-week
delta so you see the trend before it becomes a crisis.

## Workflow

1. Export the weekly P&L as `weekly_pnl.csv` (week_ending, net_sales,
   food_purchases, food_inv_begin, food_inv_end, bev_purchases,
   bev_inv_begin, bev_inv_end, labor_foh, labor_boh, labor_salaried,
   payroll_taxes_benefits).
2. Run the script:
   ```bash
   python3 scripts/prime_cost_tracker.py weekly_pnl.csv --json report.json
   ```
3. Review the report — every week's status tells you whether you made money
   on operations. WoW delta direction matters more than any single reading.
4. A watch week triggers a menu and schedule conversation. An over week
   triggers a stop-everything audit of purchasing and the schedule.

## Controls

- Prime cost is a **weekly** number — monthly prime cost tells you what you
  already lost.
- Use **true COGS** (count inventory) — purchases-only "food cost" swings
  ±5 points on delivery timing and hides theft.
- **A watch week is a menu/schedule conversation** — don't wait.
- **An over week is a stop-everything audit** of purchasing and the
  schedule.
- Every point of prime cost on $700K/yr of revenue is ~$7,000/yr.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.