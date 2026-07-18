---
name: cash-weather-report
description: Produce a plain-English 30-day cash weather report from messy AR/AP, bank balances, and known obligations. Use when cash surprises hit, payroll is stressful, the owner asks "can I afford this?", books lag reality, or spend decisions are made on gut not runway. Complements cash-flow-forecaster (S-curve/script engine) with a founder-facing weather narrative and decision cards.
---

# Cash Weather Report

Profit ≠ cash. SMBs get blindsided by **timing**, not loss. Turn imperfect exports into a **cash weather report** (sunny / cloudy / storm windows) with a **risk radar** and **no fake precision**.

**Leading words:** cash weather · storm window · known vs hoped money · no fake precision

Distinct from `cash-flow-forecaster`: that skill builds quantitative S-curve forecasts from structured events; this skill produces a plain-English decision memo when data is dirty and the owner needs a go/no-go on a live choice.

## Workflow

1. **Export events** as CSV (see `fixtures/input/events.csv`):
   `date,amount,lane,label` with lanes
   `confirmed | near_certain | hoped | committed | flexible`.
2. **Run** the engine:
   ```bash
   python3 scripts/cash_weather_report.py fixtures/input/events.csv \
       --opening 50000 --fixed-weekly 8000 --as-of 2026-07-01 --json out.json
   ```
3. **Review weather** — Sunny, Cloudy, or Storm week by week. **Known vs hoped money** never mix: hoped never enters the base balance.
4. **Risk radar (top 5)** — for storm or cloudy weeks: trigger, early signal, pre-commit action (collect / delay / cut / finance).
5. **Decision cards** — for the live choice (hire / buy / campaign): do now / do if X clears / defer. Attach cash test under base + stressed case.

## Controls

- **No fake precision** — ranges / bands beat fake point forecasts when data is dirty.
- Never restate accounting profit as available cash.
- Do not recommend illegal tax delay or payroll bounce.
- If inputs conflict, prefer bank certainty over invoice optimism.
- `--fixed-weekly` must be > 0 (operating burn for buffer math).

## Deliverables

1. Engine weather report (`out.json`)
2. Storm window dates (if any)
3. Risk radar (≤5)
4. Decision card for the live choice
5. Next data hygiene step (single export to keep running)

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — cash systems for founder-led businesses.
