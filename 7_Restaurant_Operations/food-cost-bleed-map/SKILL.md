---
name: food-cost-bleed-map
description: Find where a restaurant is bleeding food cost — waste, over-portion, voids, shrink signals, recipe drift — and produce a ranked 14-day cut plan. Use when COGS is above target, margins thin despite volume, prep waste feels random, or inventory variance is unexplained. Complements prime-cost-tracker (weekly band) and vendor-price-creep-detector (unit prices) by root-causing the plate and station level.
---

# Food Cost Bleed Map

Food cost rarely "just is." It **bleeds**. Build a **bleed map** from messy exports and a **14-day cut plan** that does not wreck guest quality.

**Leading words:** bleed line · theoretical vs actual · plate photograph memory · no phantom inventory

Distinct from `prime-cost-tracker` (aggregate weekly %) and `vendor-price-creep-detector` (vendor invoice unit prices): this skill attributes the gap to stations, items, waste, portion, and voids.

## Workflow

1. **Export** sales + recipes (+ optional waste) CSVs — see `fixtures/input/`.
2. **Run** the engine:
   ```bash
   python3 scripts/food_cost_bleed_map.py \
       --sales fixtures/input/sales.csv \
       --recipes fixtures/input/recipes.csv \
       --waste fixtures/input/waste.csv \
       --json out.json
   ```
3. **Review theoretical vs actual** — bleed = actual_cogs − units × recipe_unit_cost.
   Missing recipe → `wrong_recipe` bucket. Do not invent plate costs.
4. **Focus the top 5 culprits** — Pareto by bleed $. Use **plate photograph memory** with kitchen leads for portion check.
5. **14-day cut plan** — one control per guilty station: scale, scoop, par, batch, 86 floor. Daily mini-count only on the problem category (**no phantom inventory**).

## Controls

- Do not accuse staff of theft without chain-of-evidence; use "shrink signals."
- Never recommend unsafe undercooking or illegal food reuse.
- Protect identity dishes — cut waste, not the dish, without chef sign-off.
- Ranges when data dirty; inventing inventory to close the gap is forbidden.

## Deliverables

1. Engine report (`out.json`)
2. Bleed map by bucket + $
3. Top 5 guilty items/stations
4. 14-day cut plan
5. Daily mini-count protocol (problem category only)

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — restaurant ops systems that protect plate quality and margin.
