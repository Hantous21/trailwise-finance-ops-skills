---
name: daily-field-report
description: Compile contractor daily field reports with labor hours, completed work, observed weather, delays, visitors, notes, and safety-event review flags. Use when preparing, validating, or summarizing superintendent daily logs and field reports from structured project facts.
---

# Daily Field Report

Use `scripts/daily_field_report.py` to calculate report totals and review flags. Record observations supplied by the project team; do not manufacture weather, progress, responsibility, or safety facts.

## Workflow

1. Confirm project ID, report date, preparer, and observed weather.
2. Create a `WorkEntry` for each trade and a `DelayEvent` for each distinct delay.
3. Record safety events using the controlled severity values.
4. Run `summarize` and preserve its review reasons with the source records.
5. Have the superintendent review the report before distribution or system entry.

```python
from datetime import date
from scripts.daily_field_report import DailyReport, WorkEntry, summarize

report = DailyReport(
    "P-100", date(2026, 7, 1), "A. Rivera", "Clear, observed at 7:00 AM",
    work=(WorkEntry("Electrical", 4, "8", "Installed level-two conduit"),),
)
result = summarize(report)
```

## Controls

- Use an explicit report date; never infer it from the runtime clock.
- Label responsibility as unknown until a named reviewer confirms it.
- Treat worker totals as reported trade assignments, not a unique headcount across shifts.
- Escalate recordable, lost-time, and critical safety events outside this reporting script.
- Do not use the output to assign contractual liability or approve timecards.


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
