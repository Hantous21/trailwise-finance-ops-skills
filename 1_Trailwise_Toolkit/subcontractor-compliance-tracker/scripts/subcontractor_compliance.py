"""Subcontractor Compliance Tracker — deterministic engine for compliance status, reminders, and reporting.

This module provides the data models and logic for tracking subcontractor
compliance documents (COIs, licenses, lien waivers, W9s, contracts).
The SKILL.md file contains the workflow and controls; this file contains
the implementation.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional
from enum import Enum
from uuid import UUID, uuid4


# 1099-NEC filing thresholds by tax year
THRESHOLD_2025 = Decimal("600")
THRESHOLD_2026 = Decimal("2000")


def get_1099_threshold(year: int) -> Decimal:
    """Return the 1099-NEC filing threshold for a given tax year."""
    if year >= 2026:
        return THRESHOLD_2026
    return THRESHOLD_2025


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

    def days_until_expiry(self, as_of: Optional[date] = None) -> Optional[int]:
        if not self.expiration_date:
            return None
        ref = as_of or date.today()
        return (self.expiration_date - ref).days

    def update_status(self, expiring_threshold_days: int = 30, as_of: Optional[date] = None):
        """Auto-calculate status from expiration date."""
        if not self.expiration_date:
            self.status = ComplianceStatus.MISSING
            return

        days = self.days_until_expiry(as_of=as_of)
        if days is None:
            self.status = ComplianceStatus.MISSING
        elif days < 0:
            self.status = ComplianceStatus.EXPIRED
        elif days <= expiring_threshold_days:
            self.status = ComplianceStatus.EXPIRING_SOON
        else:
            self.status = ComplianceStatus.ACTIVE


@dataclass
class ContractorPayment:
    """A payment to a subcontractor — tracked for 1099-NEC purposes."""
    id: UUID = field(default_factory=uuid4)
    subcontractor_id: UUID = field(default_factory=uuid4)
    payment_date: date = field(default_factory=date.today)
    amount: Decimal = field(default_factory=lambda: Decimal("0"))
    payment_method: str = "ach"  # ach, check, credit_card, paypal, venmo
    invoice_ref: str = ""
    notes: str = ""


class ComplianceManager:
    """Manage subcontractor compliance across projects."""

    def __init__(self, expiring_threshold_days: int = 30,
                 reminder_schedule: List[int] = None,
                 as_of: Optional[date] = None):
        self.threshold = expiring_threshold_days
        self.reminder_schedule = reminder_schedule or [30, 15, 5]
        self.as_of = as_of
        self.subs: Dict[UUID, Subcontractor] = {}
        self.docs: Dict[UUID, ComplianceDocument] = {}
        self.payments: List[ContractorPayment] = []

    def _ref_date(self) -> date:
        return self.as_of or date.today()

    def refresh_statuses(self):
        """Recompute every document against as_of / today."""
        for doc in self.docs.values():
            doc.update_status(self.threshold, as_of=self.as_of)

    def add_subcontractor(self, sub: Subcontractor) -> UUID:
        self.subs[sub.id] = sub
        return sub.id

    def add_document(self, doc: ComplianceDocument):
        doc.update_status(self.threshold, as_of=self.as_of)
        self.docs[doc.id] = doc

    def add_payment(self, payment: ContractorPayment):
        """Record a contractor payment for 1099 tracking."""
        self.payments.append(payment)

    def get_1099_report(self, tax_year: int = None) -> Dict:
        """Generate YTD payment summary with 1099-NEC threshold flags.

        Excludes credit card / 3rd-party network payments (reported on 1099-K).
        Returns per-contractor totals with filing status.
        """
        if tax_year is None:
            tax_year = date.today().year

        threshold = get_1099_threshold(tax_year)
        # Payment methods reported on 1099-K, not 1099-NEC
        card_methods = {"credit_card", "paypal", "venmo", "square", "stripe"}

        # Accumulate YTD payments per contractor
        ytd: Dict[UUID, Decimal] = {}
        for p in self.payments:
            if p.payment_date.year != tax_year:
                continue
            if p.payment_method in card_methods:
                continue  # reported on 1099-K
            ytd[p.subcontractor_id] = ytd.get(p.subcontractor_id, Decimal("0")) + p.amount

        contractors = []
        for sub_id, total in sorted(ytd.items(), key=lambda x: -x[1]):
            sub = self.subs.get(sub_id)
            if not sub:
                continue

            # Check W-9 status — W-9s don't expire, so check existence (not status)
            w9_on_file = any(
                d.document_type == DocumentType.W9
                for d in self.docs.values()
                if d.subcontractor_id == sub_id
            )

            total_dec = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            threshold_pct = (total_dec / threshold * Decimal("100")).quantize(Decimal("0.1"))

            if total_dec >= threshold:
                status = "FILE_1099"
            elif total_dec >= threshold * Decimal("0.8"):
                status = "APPROACHING_THRESHOLD"
            else:
                status = "BELOW_THRESHOLD"

            contractors.append({
                "company_name": sub.company_name,
                "trade": sub.trade,
                "ytd_paid": str(total_dec),
                "threshold": str(threshold),
                "threshold_pct": str(threshold_pct),
                "filing_status": status,
                "w9_on_file": w9_on_file,
                "payment_count": sum(
                    1 for p in self.payments
                    if p.subcontractor_id == sub_id
                    and p.payment_date.year == tax_year
                    and p.payment_method not in card_methods
                ),
            })

        return {
            "tax_year": tax_year,
            "filing_threshold": str(threshold),
            "total_contractors_paid": len(ytd),
            "contractors_requiring_1099": sum(1 for c in contractors if c["filing_status"] == "FILE_1099"),
            "contractors_approaching": sum(1 for c in contractors if c["filing_status"] == "APPROACHING_THRESHOLD"),
            "contractors_missing_w9": sum(1 for c in contractors if c["filing_status"] == "FILE_1099" and not c["w9_on_file"]),
            "contractors": contractors,
        }

    def get_dashboard_summary(self) -> Dict:
        """Get summary counts for dashboard."""
        self.refresh_statuses()
        counts = {s.value: 0 for s in ComplianceStatus}
        for doc in self.docs.values():
            counts[doc.status.value] += 1

        expiring_this_week = sum(
            1 for d in self.docs.values()
            if (days := d.days_until_expiry(self.as_of)) is not None and 0 <= days <= 7
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
        ref = self._ref_date()
        threshold_date = ref + timedelta(days=days)
        return [
            d for d in self.docs.values()
            if d.expiration_date
            and ref <= d.expiration_date <= threshold_date
        ]

    def get_non_compliant_subs(self) -> List[Dict]:
        """Get subs with expired or missing documents."""
        self.refresh_statuses()
        result = []
        for doc in self.docs.values():
            if doc.status in (ComplianceStatus.EXPIRED, ComplianceStatus.MISSING):
                sub = self.subs.get(doc.subcontractor_id)
                if sub and sub.is_active:
                    days = doc.days_until_expiry(self.as_of)
                    result.append({
                        "subcontractor": sub.company_name,
                        "trade": sub.trade,
                        "document_type": doc.document_type.value,
                        "status": doc.status.value,
                        "expiration_date": doc.expiration_date.isoformat() if doc.expiration_date else None,
                        "days_expired": abs(days) if days is not None and days < 0 else None,
                        "contact_email": sub.contact_email,
                    })
        return result

    def get_compliance_report(self) -> Dict:
        """Full report for export."""
        self.refresh_statuses()
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
                "days_until_expiry": doc.days_until_expiry(self.as_of),
                "policy_number": doc.policy_number,
                "notes": doc.notes,
            })

        return {
            "summary": self.get_dashboard_summary(),
            "non_compliant": self.get_non_compliant_subs(),
            "full_report": rows,
        }


def import_from_csv(file_path: str, manager: ComplianceManager) -> Dict:
    """Import subs and documents from existing Excel tracker."""
    import pandas as pd

    df = pd.read_csv(file_path)

    # Group by company_name to avoid duplicate subs
    subs_created = 0
    docs_created = 0
    sub_cache: Dict[str, Subcontractor] = {}  # company_name -> Subcontractor

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
            raw_exp = row.get("expiration_date", "")
            exp_date = None
            # pandas reads empty cells as NaN; guard against NaN/NaT/empty strings
            if raw_exp is not None and not (isinstance(raw_exp, float) and pd.isna(raw_exp)):
                exp_str = str(raw_exp).strip()
                if exp_str and exp_str.lower() not in ("nan", "nat", "none", ""):
                    try:
                        parsed = pd.to_datetime(exp_str)
                        exp_date = parsed.date() if not pd.isna(parsed) else None
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
