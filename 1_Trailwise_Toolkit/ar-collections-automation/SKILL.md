---
name: ar-collections-automation
description: Generate AR aging reports, tiered dunning emails, and late-payment predictions. Use when chasing overdue invoices manually, building a collections cadence, or reporting AR aging to management.
---

# AR Collections Automation

Use `scripts/ar_collections.py` for deterministic aging, dunning email generation, late-payment prediction, and activity logging. The engine does not send emails, modify source systems, or escalate accounts.

## Workflow

1. Load invoices into `CollectionsManager` from your data source (CSV, QuickBooks export, etc.).
2. Run `get_aging_report()` to bucket outstanding receivables by age.
3. Run `predict_late_payments()` to identify at-risk invoices based on client payment history.
4. For overdue invoices, use `DunningEmailGenerator` to generate stage-appropriate emails — **never auto-send**.
5. Log every contact in `CollectionsActivityLog` for audit trail.

```python
from datetime import date
from scripts.ar_collections import CollectionsManager, Invoice, DunningEmailGenerator, DunningStage

mgr = CollectionsManager()
mgr.add_invoice(Invoice("INV-001", "C001", "Acme Corp", date(2026, 5, 1), date(2026, 6, 1), 12500))
aging = mgr.get_aging_report()
predictions = mgr.predict_late_payments()
```

## Dunning Schedule

| Days Past Due | Stage | Tone | CC | Action |
|---------------|-------|------|-----|--------|
| 1-15 | Friendly | "Just a reminder!" | — | Send email, log activity |
| 16-45 | Firm | "Payment overdue" | Account manager | Send email, call if >$5K |
| 46-90 | Final Notice | "FINAL NOTICE" | Owner/principal | Send email + certified letter |
| 90+ | Escalated | "Sent to collections" | Owner + attorney | Send to collections agency |

## Controls

- **Never auto-send dunning emails** — generate for human review and manual sending.
- **Dispute hold stops dunning** — if a client disputes an invoice, halt all dunning activity and flag for PM review.
- **Dunning tier escalation** — each stage must be logged before advancing; never skip stages.
- **Minimum threshold** — don't spend $50 of effort collecting a $25 invoice. Set a floor.
- **Payment plan pauses dunning** — if a structured paydown plan is current, skip dunning.

## Edge Cases

1. **Partial payments** — Invoice stays open with reduced balance. Adjust dunning amount.
2. **Disputed invoices** — Put hold on dunning, flag for PM review.
3. **Payment plans** — Skip dunning if plan is current.
4. **Client bankruptcy** — Stop all dunning, write off or send to attorney.
5. **Repeat offenders** — Pays late every month but eventually pays. Adjust terms or require deposits.
6. **Credit memos** — Apply credit memos to outstanding invoices before dunning.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
