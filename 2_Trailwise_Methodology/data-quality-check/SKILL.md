---
name: data-quality-check
description: Validate finance CSV exports for required columns, blanks, duplicates, invalid dates, invalid decimals, and schema drift. Use when preparing reconciliation, forecasting, migration, reporting, or any automation that depends on spreadsheet or system-export data.
---

# Data Quality Check

Run `scripts/data_quality_check.py` before feeding finance exports into another skill.

## Workflow

1. Create a JSON schema listing columns, types, required fields, and unique keys.
2. Run the checker against the source CSV.
3. Stop downstream automation when the report contains errors.
4. Resolve or explicitly quarantine rejected rows.
5. Preserve the report with the source file hash and processing run.

```bash
python scripts/data_quality_check.py input.csv --schema schema.json --output quality-report.json
```

Supported types are `string`, `decimal`, `integer`, and ISO `date`. The checker never modifies the source file.

## Controls

- Treat unexpected or missing columns as schema drift.
- Declare business keys such as invoice number plus vendor as unique.
- Use numeric strings without currency symbols for deterministic decimal parsing.
- Keep row numbers in error reports for remediation.
- Review whether blanks mean unknown, zero, not applicable, or a true error.


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
