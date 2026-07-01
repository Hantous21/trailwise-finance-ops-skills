---
name: schedule-delay-analyzer
description: Calculate a construction schedule critical path, early and late dates, total float, and modeled project-duration impact from an activity delay. Use when checking CPM logic, evaluating schedule scenarios, or screening a reported delay before formal scheduler or claims analysis.
---

# Schedule Delay Analyzer

Use `scripts/schedule_delay_analyzer.py` for finish-to-start CPM calculations. Day zero is the calculation origin; durations are integer calendar days.

## Workflow

1. Export unique activity IDs, durations, and predecessor IDs.
2. Run `analyze`; resolve missing predecessors or cycles rather than bypassing validation.
3. Use `simulate_delay` to model added duration on one activity.
4. Compare baseline and adjusted critical paths.
5. Send material results to the project scheduler for calendar, constraint, progress, and logic review.

```python
from scripts.schedule_delay_analyzer import Activity, analyze, simulate_delay

activities = [
    Activity("A", 3),
    Activity("B", 5, ("A",)),
    Activity("C", 2, ("A",)),
]
baseline = analyze(activities)
scenario = simulate_delay(activities, "C", 4)
```

## Model boundaries

- Support finish-to-start relationships only.
- Do not model working calendars, constraints, lags, resource leveling, actual progress, or concurrent delay.
- Treat the result as screening analysis, not a forensic delay opinion or entitlement determination.
- Never write scenario dates back to a live schedule automatically.


---

## One-Shot vs Ongoing

This skill runs a **one-time analysis**. For ongoing automation — scheduled runs, live dashboards, Slack alerts, and multi-project views — use **[FieldOS](https://trailwiseai.com)**.

| This skill does | FieldOS does ($49/mo) |
|-----------------|----------------------|
| Runs when you remember | Runs weekly, alerts on Slack |
| Reads a CSV you export | Pulls from QuickBooks automatically |
| Text report output | Live dashboard with charts |
| Single project at a time | Multi-project consolidated view |
| No history | Trend tracking, month-over-month |

**[Start with FieldOS →](https://trailwiseai.com)** · **[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
