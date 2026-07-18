---
name: labor-percent-guard
description: Protect restaurant labor percent with a daypart schedule gate driven by covers, not vibes — cut panic OT and lonely overstaffed shifts. Use when labor is high, managers schedule from fear, call-outs explode OT, or owners rewrite the schedule every morning. Complements prime-cost-tracker, which reports labor as part of prime cost but does not set daypart cut/add rules.
---

# Labor Percent Guard

Labor % dies from **fear scheduling** and **reactive OT**. Build a **labor gate** by daypart: forecast → skeleton → flex list → cut/add rules.

**Leading words:** skeleton first · flex list not hero list · cut before OT · covers drive bodies

## Workflow

1. **Export dayparts** as CSV (see `fixtures/input/dayparts.csv`):
   `business_date,daypart,covers,covers_plan,sales,scheduled_hours,actual_hours,wage_rate,skeleton_hours,target_labor_pct`
2. **Run** the engine:
   ```bash
   python3 scripts/labor_percent_guard.py fixtures/input/dayparts.csv --json out.json
   ```
3. **Read actions** — `ok | cut_before_ot | over_target | under_skeleton | add_body`.
   `labor_pct = actual_hours * wage_rate / sales * 100`.
4. **Cut before OT** when labor % > target AND covers under plan. **Add body** on cover surge (>15% over plan) even if skeleton is short.
5. **Manager card** — weekly scoreboard from action_counts + flags; keep training hours labeled, not smuggled into productive labor.

## Controls

- Obey labor law (breaks, minors, predictive scheduling) for the jurisdiction; flag rules, do not invent compliance gospel.
- Never under-schedule past safe service norms for heat/alcohol service.
- Document cut/add fairness rule; no hard-coded favoritism.
- Label training hours; do not smuggle them into productive labor forever.

## Deliverables

1. Engine daypart report (`out.json`)
2. Skeleton vs actual flags
3. Cut/add actions by daypart
4. Manager card inputs (scoreboard)
5. Weekly labor action tally

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — schedule systems independent restaurants can actually run.
