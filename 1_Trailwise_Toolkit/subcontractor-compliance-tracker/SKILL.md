---
name: "subcontractor-compliance-tracker"
description: "Track subcontractor insurance, licenses, and lien waivers. Auto-remind subs before expiration, flag non-compliant vendors, replace the 'master spreadsheet' with a dashboard."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "📋"
    category: "compliance"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
    implemented_in: "FieldOS"
---

# Subcontractor Compliance Tracker

## Overview

Track subcontractor compliance documents (COIs, licenses, lien waivers, W9s, contracts) with automated expiration reminders. Replace the "master spreadsheet" with a structured system that sends email alerts before documents expire and flags non-compliant vendors.

## The Problem This Solves

> "My boss has me managing all the subcontractor compliance (COIs, licenses, lien waivers) on a massive 'master spreadsheet.' I'm basically spending my entire day chasing subs over email to get their new COI before one expires. This feels completely insane and incredibly high-risk."
> — r/ConstructionManagers (46 comments)

**Current state:** One person's entire job is chasing COI renewals via email, tracked on a spreadsheet. One missed expiration = uninsured subcontractor on site = massive liability.

**After this skill:** Dashboard shows what's active, expiring, expired, and missing. Automated emails go out 30/15/5 days before expiry. The coordinator reviews for 15 minutes/day instead of chasing all day.

## Capabilities

- Track COIs, trade licenses, lien waivers, W9s, and contracts per subcontractor
- Auto-calculate status from expiration dates (active, expiring soon, expired, missing)
- Automated email reminders at 30, 15, and 5 days before expiry
- CSV import from existing Excel tracker (one-click migration)
- CSV export for reporting and backup
- Dashboard with summary counts and color-coded status
- Payment hold flag for non-compliant subs
- Multi-project and org-level views

## Data Model

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional
from enum import Enum
from uuid import UUID, uuid4

class DocumentType(Enum):
    COI = "coi"                    # Certificate of Insurance
    LICENSE = "license"            # Trade license
    LIEN_WAIVER = "lien_waiver"   # Conditional/unconditional
    W9 = "w9"                      # Tax form
    CONTRACT = "contract"          # Subcontract agreement

class ComplianceStatus(Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"    # Within 30 days
    EXPIRED = "expired"
    MISSING = "missing"                # No document on file
    PENDING_RENEWAL = "pending_renewal" # Sub notified, awaiting response

@dataclass
class Subcontractor:
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    project_id: Optional[UUID] = None  # None = firm-wide
    company_name: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    trade: str = ""  # "Plumbing", "Electrical", "Concrete"
    is_active: bool = True

@dataclass
class ComplianceDocument:
    id: UUID = field(default_factory=uuid4)
    subcontractor_id: UUID = field(default_factory=uuid4)
    document_type: DocumentType = DocumentType.COI
    file_path: Optional[str] = None
    status: ComplianceStatus = ComplianceStatus.MISSING
    issued_date: Optional[date] = None
    expiration_date: Optional[date] = None
    policy_number: str = ""        # For COIs
    coverage_amount: Optional[float] = None  # For COIs
    notes: str = ""

    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.expiration_date:
            return None
        return (self.expiration_date - date.today()).days

    def update_status(self, expiring_threshold_days: int = 30):
        """Auto-calculate status from expiration date."""
        if not self.expiration_date:
            self.status = ComplianceStatus.MISSING
            return

        days = self.days_until_expiry
        if days is None:
            self.status = ComplianceStatus.MISSING
        elif days < 0:
            self.status = ComplianceStatus.EXPIRED
        elif days <= expiring_threshold_days:
            self.status = ComplianceStatus.EXPIRING_SOON
        else:
            self.status = ComplianceStatus.ACTIVE
```

## Compliance Manager

```python
class ComplianceManager:
    """Manage subcontractor compliance across projects."""

    def __init__(self, expiring_threshold_days: int = 30,
                 reminder_schedule: List[int] = None):
        self.threshold = expiring_threshold_days
        self.reminder_schedule = reminder_schedule or [30, 15, 5]
        self.subs: Dict[UUID, Subcontractor] = {}
        self.docs: Dict[UUID, ComplianceDocument] = {}

    def add_subcontractor(self, sub: Subcontractor) -> UUID:
        self.subs[sub.id] = sub
        return sub.id

    def add_document(self, doc: ComplianceDocument):
        doc.update_status(self.threshold)
        self.docs[doc.id] = doc

    def get_dashboard_summary(self) -> Dict:
        """Get summary counts for dashboard."""
        counts = {s.value: 0 for s in ComplianceStatus}
        for doc in self.docs.values():
            counts[doc.status.value] += 1

        expiring_this_week = sum(
            1 for d in self.docs.values()
            if d.days_until_expiry is not None and 0 <= d.days_until_expiry <= 7
        )

        return {
            "total_documents": len(self.docs),
            "active": counts["active"],
            "expiring_soon": counts["expiring_soon"],
            "expired": counts["expired"],
            "missing": counts["missing"],
            "pending_renewal": counts["pending_renewal"],
            "expiring_this_week": expiring_this_week,
            "total_subcontractors": len(self.subs),
        }

    def get_expiring_documents(self, days: int = 30) -> List[ComplianceDocument]:
        """Get documents expiring within N days."""
        threshold_date = date.today() + timedelta(days=days)
        return [
            d for d in self.docs.values()
            if d.expiration_date
            and date.today() <= d.expiration_date <= threshold_date
        ]

    def get_non_compliant_subs(self) -> List[Dict]:
        """Get subs with expired or missing documents."""
        result = []
        for doc in self.docs.values():
            if doc.status in (ComplianceStatus.EXPIRED, ComplianceStatus.MISSING):
                sub = self.subs.get(doc.subcontractor_id)
                if sub and sub.is_active:
                    result.append({
                        "subcontractor": sub.company_name,
                        "trade": sub.trade,
                        "document_type": doc.document_type.value,
                        "status": doc.status.value,
                        "expiration_date": doc.expiration_date.isoformat() if doc.expiration_date else None,
                        "days_expired": abs(doc.days_until_expiry) if doc.days_until_expiry and doc.days_until_expiry < 0 else None,
                        "contact_email": sub.contact_email,
                    })
        return result

    def get_compliance_report(self) -> Dict:
        """Full report for export."""
        rows = []
        for doc in self.docs.values():
            sub = self.subs.get(doc.subcontractor_id)
            if not sub:
                continue
            rows.append({
                "company_name": sub.company_name,
                "trade": sub.trade,
                "contact_name": sub.contact_name,
                "contact_email": sub.contact_email,
                "document_type": doc.document_type.value,
                "status": doc.status.value,
                "issued_date": doc.issued_date.isoformat() if doc.issued_date else "",
                "expiration_date": doc.expiration_date.isoformat() if doc.expiration_date else "",
                "days_until_expiry": doc.days_until_expiry,
                "policy_number": doc.policy_number,
                "notes": doc.notes,
            })

        return {
            "summary": self.get_dashboard_summary(),
            "non_compliant": self.get_non_compliant_subs(),
            "full_report": rows,
        }
```

## CSV Import

```python
import pandas as pd

def import_from_csv(file_path: str, manager: ComplianceManager) -> Dict:
    """Import subs and documents from existing Excel tracker."""
    df = pd.read_csv(file_path)

    required_cols = ["company_name", "trade"]
    optional_cols = ["contact_name", "contact_email", "contact_phone",
                     "document_type", "expiration_date", "policy_number", "notes"]

    # Group by company_name to avoid duplicate subs
    subs_created = 0
    docs_created = 0
    sub_cache = {}  # company_name → Subcontractor

    for _, row in df.iterrows():
        name = str(row.get("company_name", "")).strip()
        if not name:
            continue

        if name not in sub_cache:
            sub = Subcontractor(
                company_name=name,
                contact_name=str(row.get("contact_name", "")).strip(),
                contact_email=str(row.get("contact_email", "")).strip(),
                contact_phone=str(row.get("contact_phone", "")).strip(),
                trade=str(row.get("trade", "")).strip(),
            )
            manager.add_subcontractor(sub)
            sub_cache[name] = sub
            subs_created += 1

        sub = sub_cache[name]

        # Create document if type and expiration exist
        doc_type_str = str(row.get("document_type", "")).strip().lower()
        if doc_type_str and doc_type_str in [dt.value for dt in DocumentType]:
            exp_str = str(row.get("expiration_date", "")).strip()
            try:
                exp_date = pd.to_datetime(exp_str).date() if exp_str else None
            except Exception:
                exp_date = None

            doc = ComplianceDocument(
                subcontractor_id=sub.id,
                document_type=DocumentType(doc_type_str),
                expiration_date=exp_date,
                policy_number=str(row.get("policy_number", "")).strip(),
                notes=str(row.get("notes", "")).strip(),
            )
            manager.add_document(doc)
            docs_created += 1

    return {
        "subcontractors_imported": subs_created,
        "documents_imported": docs_created,
        "expiring_within_30_days": len(manager.get_expiring_documents(30)),
        "non_compliant": len(manager.get_non_compliant_subs()),
    }
```

## Email Reminder System

```python
def generate_reminder_email(sub: Subcontractor, doc: ComplianceDocument,
                            days: int, pm_name: str, pm_email: str) -> Dict:
    """Generate reminder email content."""
    subject = f"Action Required: {doc.document_type.value.upper()} expiring in {days} days"

    body = f"""Hi {sub.contact_name or sub.company_name},

Your {doc.document_type.value.upper()} for {sub.company_name} expires on {doc.expiration_date} (in {days} days).

Please renew and send the updated document to {pm_email}.

Document details:
- Type: {doc.document_type.value.upper()}
- Policy number: {doc.policy_number or 'N/A'}
- Expiration: {doc.expiration_date}

If you have questions, contact {pm_name}.

Thank you,
{pm_name}
"""

    return {
        "to": sub.contact_email,
        "subject": subject,
        "body_text": body,
        "subcontractor": sub.company_name,
        "document_type": doc.document_type.value,
        "days_until_expiry": days,
    }
```

## Reminder Schedule

| When | Who gets emailed | Dashboard action |
|------|------------------|-----------------|
| 30 days before | Sub contractor | Status → `EXPIRING_SOON` |
| 15 days before | Sub + CC project manager | No change |
| 5 days before | Sub + CC PM | Status → `PENDING_RENEWAL` |
| 0 days (expired) | PM only | Status → `EXPIRED`, payment hold flag |

## CSV Format (for import from existing tracker)

```csv
company_name,contact_name,contact_email,contact_phone,trade,document_type,expiration_date,policy_number,notes
Acme Plumbing,John Smith,john@acmeplumb.com,555-0100,Plumbing,coi,2026-08-15,POL-12345,Renews annually
Acme Plumbing,John Smith,john@acmeplumb.com,555-0100,Plumbing,license,2026-12-31,LIC-789,Master plumber
Bright Electric,Sarah Lee,sarah@brightelec.com,555-0200,Electrical,coi,2026-07-01,POL-67890,
Carter Concrete,Mike Carter,mike@carterconcrete.com,555-0300,Concrete,coi,,,
```

## Edge Cases

1. **No expiration date** — Some documents (W9s, contracts) don't expire. Status stays `ACTIVE` with `expiration_date = None`.
2. **Sub with no docs** — Sub exists in system but has zero compliance documents. All document types show `MISSING`.
3. **Multiple projects** — Same sub works on 3 projects. One COI covers all (org-level) or per-project (rare). Phase 1: org-level.
4. **Email bounce** — Sub's email is wrong. Log the bounce, flag on dashboard for manual follow-up.
5. **Renewed early** — Sub sends new COI 40 days before old one expires. Update the record, reset status to `ACTIVE`, cancel pending reminders.
6. **Bulk import duplicates** — CSV has same sub listed 3 times with different docs. Group by company_name, create one sub, attach all docs.

## Integration Points

- **FieldOS** — Implemented as a native module (see `docs/compliance-tracker-spec.md`)
- **n8n** — Alternative: build as n8n workflow reading from Google Sheets
- **QuickBooks** — Future: block payment approval for non-compliant subs
- **Procore** — Future: pull subcontractor list from Procore API
- **Trailwise SaaS** — Managed version with dashboard ($49/mo)

## Real-World Migration Path

1. **Day 1:** Export existing Excel tracker to CSV
2. **Day 1:** Import CSV → system creates all subs + docs, calculates statuses
3. **Day 1:** Dashboard shows current state (likely scary — lots of expired/missing)
4. **Day 2-7:** Clean up data, add missing docs, verify emails
5. **Day 8:** Turn on automated reminders
6. **Day 30+:** Coordinator reviews dashboard 15 min/day instead of chasing all day


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
