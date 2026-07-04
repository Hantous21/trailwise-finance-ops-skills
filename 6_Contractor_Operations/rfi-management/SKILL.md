---
name: rfi-management
description: Track construction RFIs, calculate aging and overdue days, surface unquantified cost or schedule impacts, and prioritize response review. Use when building an RFI log, preparing an overdue report, or triaging open RFIs against required response dates.
---

# RFI Management

Use `scripts/rfi_management.py` for deterministic RFI aging and portfolio summaries. The engine does not send notices, answer RFIs, or change statuses.

## Workflow

1. Normalize RFI number, subject, submission date, required response date, and status.
2. Record cost and schedule impacts as estimates; preserve `None` when unknown.
3. Supply an explicit `as_of` date to `triage` or `portfolio`.
4. Review critical, high-priority, and unquantified-impact items with the project team.
5. Update the source system only through an authenticated, audited workflow.

```python
from datetime import date
from scripts.rfi_management import RFI, triage

rfi = RFI("RFI-42", "Beam penetration detail", date(2026, 6, 20), date(2026, 6, 27))
result = triage(rfi, date(2026, 7, 1))
```

## Controls

- Never treat an unanswered impact field as zero.
- Do not infer responsibility, entitlement, or compensability from lateness.
- Require an answer date for answered and closed RFIs.
- Preserve the source document and status history with exported summaries.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
