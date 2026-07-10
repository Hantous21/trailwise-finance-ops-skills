---
name: subcontractor-compliance-tracker
description: Track subcontractor insurance, licenses, and lien waivers with expiry reminders. Use when managing COIs in a master spreadsheet, flagging non-compliant subs, or preparing for an audit.
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

## 1099-NEC Payment Tracking

The compliance tracker also tracks contractor payments for 1099-NEC filing. See `references/1099-contractor-management.md` for full threshold tables, penalty schedules, and year-end checklists.

```python
from scripts.subcontractor_compliance import ContractorPayment
from decimal import Decimal
from datetime import date

mgr.add_payment(ContractorPayment(
    subcontractor_id=sub.id,
    amount=Decimal("1500"),
    payment_date=date(2026, 3, 15),
    payment_method="ach",  # ach, check, credit_card, paypal, venmo, square, stripe
    invoice_ref="INV-2026-0042",
))

report = mgr.get_1099_report(tax_year=2026)
# Returns: per-contractor YTD totals, threshold %, filing status (FILE_1099 / APPROACHING / BELOW),
# W-9 on file flag, payment count. Excludes credit card / 3rd-party payments (reported on 1099-K).
```

Key rules built into the engine:
- **2026 threshold: $2,000** (was $600 in 2025). `get_1099_threshold(year)` returns the correct amount.
- **Card payments excluded** — credit_card, paypal, venmo, square, stripe are reported on 1099-K, not 1099-NEC.
- **W-9 on file** — checked by document existence (W-9s don't expire). `contractors_missing_w9` in the report flags anyone above threshold without a W-9.
- **APPROACHING_THRESHOLD** — flagged at 80% of threshold so you can request W-9s early.
- **Decimal arithmetic** — no float for money. Uses `Decimal` with `ROUND_HALF_UP`.
- **Monthly close integration** — run `get_1099_report()` during month-end close Step 7 to check contractor YTD totals.

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
