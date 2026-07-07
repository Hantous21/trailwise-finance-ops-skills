---
name: "subcontractor-compliance-tracker"
description: "Track subcontractor insurance, licenses, and lien waivers. Auto-remind subs before expiration, flag non-compliant vendors, replace the 'master spreadsheet' with a dashboard."
homepage: "https://trailwiseai.com"
disable-model-invocation: true
metadata:
  trailwise:
    emoji: "📋"
    category: "compliance"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
---

# Subcontractor Compliance Tracker

Use `scripts/subcontractor_compliance.py` for deterministic status calculation, dashboard summaries, CSV import, and reminder email generation. The engine does not send emails, modify source systems, or place payment holds.

## Workflow

1. Import subs and documents from an existing tracker via `import_from_csv()`, or add them individually with `ComplianceManager.add_subcontractor()` and `add_document()`.
2. Run `get_dashboard_summary()` to see counts of active, expiring, expired, and missing documents.
3. Run `get_expiring_documents(30)` to list documents expiring within 30 days.
4. For each expiring doc, use `generate_reminder_email()` to produce email content — **never auto-send**.
5. Run `get_non_compliant_subs()` to flag subs with expired or missing documents for payment hold review.

```python
from scripts.subcontractor_compliance import (
    ComplianceManager, Subcontractor, ComplianceDocument,
    DocumentType, import_from_csv, generate_reminder_email,
)

mgr = ComplianceManager()
result = import_from_csv("compliance_tracker.csv", mgr)
summary = mgr.get_dashboard_summary()
non_compliant = mgr.get_non_compliant_subs()
```

## Reminder Schedule — 30-15-5 cadence

| Days before expiry | Recipient | Status transition |
|--------------------|-----------|-------------------|
| 30 | Subcontractor | `ACTIVE` → `EXPIRING_SOON` |
| 15 | Sub + CC project manager | No change |
| 5 | Sub + CC PM | → `PENDING_RENEWAL` |
| 0 (expired) | PM only | → `EXPIRED`, payment hold flag |

## Controls

- **30-15-5 cadence** — reminders fire at 30, 15, and 5 days before expiry; never skip a step.
- **Never auto-send reminder emails** — generate for human review and manual sending.
- **Payment hold requires human approval** — the engine flags non-compliant subs; a person places the hold.
- **Status is derived, not stored** — `update_status()` recalculates from `expiration_date` on every add; never hand-set status.
- **Org-level coverage is the default** — one COI covers all projects unless explicitly per-project.
- **Expired = uninsured on site** — treat any `EXPIRED` status as a stop-work trigger until renewed.

## CSV Format (reference)

Columns: `company_name,contact_name,contact_email,contact_phone,trade,document_type,expiration_date,policy_number,notes`. One row per document; repeat company rows for multiple docs.

## Edge Cases

1. **No expiration date** — W9s/contracts don't expire; status stays `MISSING` until a doc is on file.
2. **Sub with no docs** — all document types show `MISSING`.
3. **Multiple projects** — one org-level COI covers all (Phase 1).
4. **Email bounce** — log the bounce, flag for manual follow-up.
5. **Renewed early** — update the record; status resets to `ACTIVE`, cancel pending reminders.
6. **Bulk import duplicates** — group by `company_name`, create one sub, attach all docs.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
