---
name: drawer-truth-close
description: Run a restaurant end-of-night close that actually matches — cash, cards, tips, voids, comps, deposits — without the morning mystery. Use when drawer variance is chronic, tip-outs fight, managers skip the checklist, or theft versus error is impossible to separate. Complements daily-sales-reconciliation (POS day to bank deposit) and tip-pool-calculator (role-weighted split math) with the physical drawer spine and variance ownership.
---

# Drawer Truth Close

The night close is a **truth ritual**, not a race to clock out. Build a **close spine** so variances have owners and tip math is transparent.

**Leading words:** cash lane first · variance has an owner · tip math public · close is a spine

Distinct from `daily-sales-reconciliation` (POS totals vs bank days later) and `tip-pool-calculator` (penny-exact pool allocation engine): this skill defines the **sequence and ownership of the physical close**.

## Workflow

1. **Export closes** as CSV (see `fixtures/input/closes.csv`):
   `business_date,drawer_id,expected_cash,counted_cash,expected_card,pos_card,voids,comps,tip_pool,net_sales,owner`
2. **Run** the engine:
   ```bash
   python3 scripts/drawer_truth_close.py fixtures/input/closes.csv --json out.json
   ```
3. **Apply thresholds** (defaults replace old $X/$Y):
   - `|variance| <= $5` → ok
   - `> $5 and < $20` → recount
   - `>= $20` → dual_count
   - `>= $50` → escalate (owner required)
4. **Cash lane first** — spine: stop sales → tip rules → count → POS Z → deposit → photo/log. Skips break the match.
5. **Morning packet** — every drawer: sales, comps, voids, variance, **named owner**, action. Never `"misc"`.

## Controls

- Dual count for large cash — no "trust me."
- Cameras/policy only if already lawful and disclosed.
- Never coach skimming or under-reporting sales for tax.
- Separate tip ownership from house funds when law requires.
- `UNASSIGNED` owner always flags `owner_required`.

## Deliverables

1. Engine report (`out.json`) + ordered close spine
2. Variance actions (ok/recount/dual_count/escalate)
3. Tip math accountability on packet
4. Void/comp freeze rule (post-spine manager code)
5. GM/owner morning packet rows

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — cash discipline without soul-crushing night audits.
