---
name: submittal-tracker
description: Calculate required construction submittal dates from review and fabrication lead times, monitor review deadlines, and flag material-on-site risk. Use when maintaining submittal logs, preparing look-ahead reports, or identifying late approvals and revise-resubmit exposure.
---

# Submittal Tracker

Use `scripts/submittal_tracker.py` to calculate timing risk. All durations are calendar days unless the caller converts an approved business-day calendar before constructing the inputs.

## Workflow

1. Confirm the required-on-site date and current revision.
2. Enter fabrication lead and review durations from approved project sources.
3. Record submission and decision dates appropriate to the current status.
4. Run `evaluate` using an explicit report date.
5. Route high and critical risks for project-team review; do not auto-approve or transmit.

```python
from datetime import date
from scripts.submittal_tracker import Submittal, evaluate

item = Submittal("SUB-17", "Roofing membrane", date(2026, 8, 15), 28, 14)
result = evaluate(item, date(2026, 7, 10))
```

## Controls

- Keep supplier lead time, design review time, and field need date traceable to sources.
- Recalculate after every revision or required-on-site date change.
- Do not interpret timing risk as contractual responsibility.
- Require a human decision before procurement, fabrication, or installation.


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
