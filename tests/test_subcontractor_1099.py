"""Tests for 1099-NEC payment tracking additions to subcontractor_compliance.py.

Covers: threshold function, ContractorPayment dataclass, get_1099_report
(card exclusion, W-9 status, approaching threshold, cross-year isolation, empty report).
"""
import sys
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
    "1_Trailwise_Toolkit", "subcontractor-compliance-tracker", "scripts"))

from subcontractor_compliance import (
    ComplianceManager, Subcontractor, ComplianceDocument,
    DocumentType, ComplianceStatus, ContractorPayment,
    get_1099_threshold, THRESHOLD_2025, THRESHOLD_2026,
)


# ── Threshold function ──────────────────────────────────────

class TestThreshold:
    def test_2025_is_600(self):
        assert get_1099_threshold(2025) == Decimal("600")

    def test_2026_is_2000(self):
        assert get_1099_threshold(2026) == Decimal("2000")

    def test_2027_stays_2000(self):
        assert get_1099_threshold(2027) == Decimal("2000")

    def test_constants_match(self):
        assert THRESHOLD_2025 == Decimal("600")
        assert THRESHOLD_2026 == Decimal("2000")

    def test_returns_decimal_not_float(self):
        assert isinstance(get_1099_threshold(2026), Decimal)


# ── ContractorPayment dataclass ──────────────────────────────

class TestContractorPayment:
    def test_amount_is_decimal(self):
        pay = ContractorPayment(amount=Decimal("100"))
        assert isinstance(pay.amount, Decimal)

    def test_default_payment_method(self):
        pay = ContractorPayment()
        assert pay.payment_method == "ach"

    def test_default_amount_is_zero(self):
        pay = ContractorPayment()
        assert pay.amount == Decimal("0")


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def three_subs():
    """Manager with 3 subs, W-9 for s1 only, varied payments."""
    mgr = ComplianceManager()
    s1 = Subcontractor(company_name="Acme Plumbing", trade="Plumbing")
    s2 = Subcontractor(company_name="Bob Electrical", trade="Electrical")
    s3 = Subcontractor(company_name="Carol HVAC", trade="HVAC")
    for s in (s1, s2, s3):
        mgr.add_subcontractor(s)
    mgr.add_document(ComplianceDocument(
        subcontractor_id=s1.id, document_type=DocumentType.W9,
    ))
    # s1: $2300 reportable (ACH+check), $300 credit_card excluded
    mgr.add_payment(ContractorPayment(subcontractor_id=s1.id, amount=Decimal("1500"), payment_date=date(2026, 3, 15), payment_method="ach"))
    mgr.add_payment(ContractorPayment(subcontractor_id=s1.id, amount=Decimal("800"), payment_date=date(2026, 6, 20), payment_method="check"))
    mgr.add_payment(ContractorPayment(subcontractor_id=s1.id, amount=Decimal("300"), payment_date=date(2026, 7, 1), payment_method="credit_card"))
    # s2: $2200, no W-9
    mgr.add_payment(ContractorPayment(subcontractor_id=s2.id, amount=Decimal("2200"), payment_date=date(2026, 4, 10), payment_method="ach"))
    # s3: $1600 (approaching at 80%)
    mgr.add_payment(ContractorPayment(subcontractor_id=s3.id, amount=Decimal("1600"), payment_date=date(2026, 5, 5), payment_method="ach"))
    return mgr, s1, s2, s3


# ── get_1099_report ─────────────────────────────────────────

class TestReport2026:
    def test_tax_year(self, three_subs):
        mgr, *_ = three_subs
        report = mgr.get_1099_report(2026)
        assert report["tax_year"] == 2026

    def test_threshold_is_2000(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        assert report["filing_threshold"] == "2000"

    def test_three_contractors_paid(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        assert report["total_contractors_paid"] == 3

    def test_two_require_1099(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        assert report["contractors_requiring_1099"] == 2

    def test_one_approaching(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        assert report["contractors_approaching"] == 1

    def test_one_missing_w9(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        assert report["contractors_missing_w9"] == 1

    def test_contractors_sorted_by_ytd_desc(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        names = [c["company_name"] for c in report["contractors"]]
        assert names == ["Acme Plumbing", "Bob Electrical", "Carol HVAC"]

    def test_acme_ytd_excludes_credit_card(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        acme = [c for c in report["contractors"] if c["company_name"] == "Acme Plumbing"][0]
        assert acme["ytd_paid"] == "2300.00"
        assert acme["payment_count"] == 2

    def test_acme_w9_on_file(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        acme = [c for c in report["contractors"] if c["company_name"] == "Acme Plumbing"][0]
        assert acme["w9_on_file"] is True

    def test_bob_w9_missing(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        bob = [c for c in report["contractors"] if c["company_name"] == "Bob Electrical"][0]
        assert bob["w9_on_file"] is False

    def test_bob_files_1099(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        bob = [c for c in report["contractors"] if c["company_name"] == "Bob Electrical"][0]
        assert bob["filing_status"] == "FILE_1099"

    def test_carol_approaching(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        carol = [c for c in report["contractors"] if c["company_name"] == "Carol HVAC"][0]
        assert carol["filing_status"] == "APPROACHING_THRESHOLD"

    def test_carol_threshold_pct(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        carol = [c for c in report["contractors"] if c["company_name"] == "Carol HVAC"][0]
        assert carol["threshold_pct"] == "80.0"

    def test_ytd_has_two_decimal_places(self, three_subs):
        report = three_subs[0].get_1099_report(2026)
        for c in report["contractors"]:
            parts = c["ytd_paid"].split(".")
            assert len(parts) == 2 and len(parts[1]) == 2


# ── Cross-year isolation ────────────────────────────────────

class TestCrossYear:
    def test_2025_payment_excluded_from_2026(self, three_subs):
        mgr, _, _, s3 = three_subs
        mgr.add_payment(ContractorPayment(
            subcontractor_id=s3.id, amount=Decimal("500"),
            payment_date=date(2025, 12, 15), payment_method="ach",
        ))
        report = mgr.get_1099_report(2026)
        carol = [c for c in report["contractors"] if c["company_name"] == "Carol HVAC"][0]
        assert carol["ytd_paid"] == "1600.00"

    def test_2025_report_uses_600_threshold(self, three_subs):
        mgr, _, _, s3 = three_subs
        mgr.add_payment(ContractorPayment(
            subcontractor_id=s3.id, amount=Decimal("500"),
            payment_date=date(2025, 12, 15), payment_method="ach",
        ))
        report = mgr.get_1099_report(2025)
        assert report["filing_threshold"] == "600"
        carol = [c for c in report["contractors"] if c["company_name"] == "Carol HVAC"][0]
        assert carol["ytd_paid"] == "500.00"
        # $500 is 83% of $600 threshold → APPROACHING_THRESHOLD (80%+)
        assert carol["filing_status"] == "APPROACHING_THRESHOLD"


# ── Card / 3rd-party exclusion ───────────────────────────────

class TestCardExclusion:
    @pytest.mark.parametrize("method", ["credit_card", "paypal", "venmo", "square", "stripe"])
    def test_card_methods_excluded(self, method):
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Test")
        mgr.add_subcontractor(sub)
        mgr.add_payment(ContractorPayment(
            subcontractor_id=sub.id, amount=Decimal("10000"),
            payment_date=date(2026, 1, 1), payment_method=method,
        ))
        report = mgr.get_1099_report(2026)
        assert report["total_contractors_paid"] == 0

    def test_ach_not_excluded(self):
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Test")
        mgr.add_subcontractor(sub)
        mgr.add_payment(ContractorPayment(
            subcontractor_id=sub.id, amount=Decimal("5000"),
            payment_date=date(2026, 1, 1), payment_method="ach",
        ))
        report = mgr.get_1099_report(2026)
        assert report["total_contractors_paid"] == 1

    def test_check_not_excluded(self):
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Test")
        mgr.add_subcontractor(sub)
        mgr.add_payment(ContractorPayment(
            subcontractor_id=sub.id, amount=Decimal("5000"),
            payment_date=date(2026, 1, 1), payment_method="check",
        ))
        report = mgr.get_1099_report(2026)
        assert report["total_contractors_paid"] == 1


# ── Edge cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_report(self):
        report = ComplianceManager().get_1099_report(2026)
        assert report["total_contractors_paid"] == 0
        assert report["contractors_requiring_1099"] == 0
        assert report["contractors"] == []

    def test_default_year_is_current(self):
        from datetime import date as _date
        report = ComplianceManager().get_1099_report()
        assert report["tax_year"] == _date.today().year

    def test_w9_without_expiration_still_on_file(self):
        """W-9s don't expire — on-file should check existence, not status."""
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Sub")
        mgr.add_subcontractor(sub)
        w9 = ComplianceDocument(subcontractor_id=sub.id, document_type=DocumentType.W9)
        mgr.add_document(w9)
        # W-9 status will be MISSING (no expiration date) but should still count as on file
        assert w9.status == ComplianceStatus.MISSING
        mgr.add_payment(ContractorPayment(
            subcontractor_id=sub.id, amount=Decimal("3000"),
            payment_date=date(2026, 1, 1), payment_method="ach",
        ))
        report = mgr.get_1099_report(2026)
        contractor = report["contractors"][0]
        assert contractor["w9_on_file"] is True

    def test_below_threshold_not_listed_as_approaching(self):
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Small")
        mgr.add_subcontractor(sub)
        mgr.add_payment(ContractorPayment(
            subcontractor_id=sub.id, amount=Decimal("500"),
            payment_date=date(2026, 1, 1), payment_method="ach",
        ))
        report = mgr.get_1099_report(2026)
        contractor = report["contractors"][0]
        assert contractor["filing_status"] == "BELOW_THRESHOLD"

    def test_exact_threshold_triggers_filing(self):
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Exact")
        mgr.add_subcontractor(sub)
        mgr.add_payment(ContractorPayment(
            subcontractor_id=sub.id, amount=Decimal("2000"),
            payment_date=date(2026, 1, 1), payment_method="ach",
        ))
        report = mgr.get_1099_report(2026)
        contractor = report["contractors"][0]
        assert contractor["filing_status"] == "FILE_1099"

    def test_decimal_no_float_contamination(self):
        mgr = ComplianceManager()
        sub = Subcontractor(company_name="Dec")
        mgr.add_subcontractor(sub)
        # Three payments that would produce float rounding issues
        for amt in (Decimal("666.67"), Decimal("666.67"), Decimal("666.66")):
            mgr.add_payment(ContractorPayment(
                subcontractor_id=sub.id, amount=amt,
                payment_date=date(2026, 1, 1), payment_method="ach",
            ))
        report = mgr.get_1099_report(2026)
        contractor = report["contractors"][0]
        assert contractor["ytd_paid"] == "2000.00"
