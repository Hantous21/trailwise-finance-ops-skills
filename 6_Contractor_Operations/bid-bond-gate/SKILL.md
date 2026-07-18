---
name: bid-bond-gate
description: Run a contractor bid/no-bid gate that weighs bonding capacity hangover, cash timing after award, crew reality, and contract landmines — not only win probability. Use when running bid board, when ITBs arrive late, when backlog already strains labor, or when lust for a logo job would hurt capacity or cash. Complements change-order-tracker and wip-schedule-generator which start after award.
---

# Bid / Bond Gate

Winning is easy; surviving the job is the product. Run a **gate score** so the board can **kill lust-bids** that destroy capacity, cash, or reputation before they enter backlog.

**Leading words:** capacity hangover · cash shape after win · kill lust-bids · contract landmines

Distinct from post-award tools (`change-order-tracker`, `wip-schedule-generator`, `retainage-tracker`): this skill decides whether to **pursue at all**.

## Workflow

1. **Export pursuits** as CSV (see `fixtures/input/bids.csv`) with
   capacity strain, mobilization cash, weekly burn, landmines, contract_known.
2. **Run** the gate:
   ```bash
   python3 scripts/bid_bond_gate.py fixtures/input/bids.csv \
       --cash-on-hand 120000 --json out.json
   ```
3. **Read hard rules** — NO-BID on capacity_strain≥5 or buffer_weeks_after_mob<2.
   BID-WITH-CONDITIONS when contract unknown, landmines≥2, strain≥4,
   high pursuit tax, or political override. Else BID.
4. **Write mitigations** for condition verdicts (bond strategy, partner, markup,
   volume limit) — named mitigation beats hope.
5. **Gate blue card for bid board** — one-paragraph why; **kill lust-bids**.

## Controls

- Do not fabricate bond "pre-approval"; note "confirm with surety" as a step.
- If contract form unknown, verdict max is **BID-WITH-CONDITIONS**, never clean BID.
- Political "we need the logo" is an executive override — label it and cost it.
- No encouraging underpriced buy-ins to "get friendly with GC."

## Deliverables

1. Engine report (`out.json`)
2. Capacity hangover score + mitigation notes
3. Cash-shape-after-win buffer weeks
4. Landmine reasons list
5. Gate verdict card for bid board

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — pursue work that leaves you bondable.
