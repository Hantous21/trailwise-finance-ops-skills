---
name: data-source-audit
description: Audit all financial data sources in a company. Use when you lack a complete inventory of where financial data lives, when data is scattered across Excel, email, accounting software, and PDFs, or when planning automation but not knowing where to start.
homepage: https://trailwise.com
disable model invocation: true
metadata:
  trailwise:
    emoji: "🔍"
    category: "data-assessment"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
---

# Data Source Audit

Before automating anything, know what data you have, where it lives, and how it flows (or doesn't). This skill inventories every financial data source, maps the flows between them, and ranks manual touch points for automation.

## Steps

1. **Inventory** — For each source, record name, location, format, frequency, owner, what it contains, integration possibility, volume, and a 1–5 quality score.
2. **Map Flows** — Trace how data moves between sources. Each arrow is a manual touch point and a candidate for automation.
3. **Identify Silos** — Flag sources that hold data no other system reaches, require manual export/import, lack an API, or are owned by one person who "just knows how it works."
4. **Score** — Rank manual, error-prone, high-frequency flows first; assign a suggested downstream skill to each opportunity.

Run the scorer once the audit JSON is assembled:

```bash
python scripts/data_source_audit.py audit.json --output report.json
```

The audit JSON needs two arrays — `sources` and `flows` — using the field names defined in `scripts/data_source_audit.py`.

## Controls

- Each arrow is a manual touch point — count it, don't hand-wave it.
- Treat "owned by one person" as a silo risk even when the data is technically accessible.
- Never infer an integration path the owner has not confirmed; mark `integration_possible: false` until proven.
- Record quality scores before ranking so a noisy but automatable source does not crowd out a clean one.
- Preserve the owner and frequency for every flow — prioritization depends on both.

## Edge Cases

- **Paper-only records** — inventory them; do not score automation until digitized.
- **Shared spreadsheets with no clear owner** — assign "unknown" and treat as a silo.
- **Sources with overlapping data** — note the overlap; the higher-quality source wins the integration path.
- **Email attachments as a data source** — inventory the mailbox, not the attachment, to avoid double-counting.

Ready to start the audit? Begin at Step 1 with whichever system the CFO or controller trusts most.
