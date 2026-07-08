---
name: tip-pool-calculator
description: Split daily tip pools by role-weighted hours with penny-exact allocation — every cent of the pool lands on exactly one person, deterministically. Use when tip-outs are computed on a napkin, when two people with the same shift get different amounts with no explanation, or when managers are (illegally) in the pool.
---

# Tip Pool Calculator

## Overview

Penny-exact daily tip pooling by role-weighted hours. This is funds control:
the pool must tie out to the cent, every day, or trust dies.

Algorithm per day: `pool = cash_tips + card_tips`; each eligible shift's
weight = hours × role points; raw share = pool × weight / Σ weights;
**floor every share to the cent, then hand out the leftover pennies one at
a time in order of largest fractional remainder, ties broken alphabetically
by employee name**. Σ payouts MUST equal the pool exactly.

**Managers and owners are ALWAYS excluded** (federal tip-pooling rule). Their
hours never enter the weighting.

## Workflow

1. Export shifts as `shifts.csv` (date, employee, role, hours).
2. Export tip totals as `tips.csv` (date, cash_tips, card_tips).
3. Run the script:
   ```bash
   python3 scripts/tip_pool_calculator.py shifts.csv tips.csv --json payout.json
   ```
4. Optionally override role points with a JSON file:
   ```bash
   python3 scripts/tip_pool_calculator.py shifts.csv tips.csv \
       --json payout.json --points points.json
   ```
   Default points: `server: 1.0`, `bartender: 1.25`, `busser: 0.5`,
   `runner: 0.5`, `host: 0.25`.
5. Publish the payout JSON — it IS the audit trail.

## Controls

- **The pool must tie to the penny every day** — an "about right" tip-out is
  a wage claim waiting to happen.
- **Managers and owners NEVER take from the pool**, no exceptions (federal
  rule).
- **Publish the role weights** — a pool nobody can recompute is a pool nobody
  trusts.
- **Keep the daily payout JSON** — it IS the audit trail when a departed
  employee disputes a paycheck.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.