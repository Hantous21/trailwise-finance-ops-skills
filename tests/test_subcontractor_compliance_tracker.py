from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "1_Trailwise_Toolkit/subcontractor-compliance-tracker"
INPUT_CSV = SKILL_DIR / "fixtures/input/compliance_tracker.csv"
EXPECTED = json.loads(
    (SKILL_DIR / "fixtures/expected/compliance_summary.json").read_text(encoding="utf-8")
)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


comp = load(
    "subcontractor_compliance",
    "1_Trailwise_Toolkit/subcontractor-compliance-tracker/scripts/subcontractor_compliance.py",
)


def build_manager() -> comp.ComplianceManager:
    """Import the input fixture into a fresh ComplianceManager."""
    mgr = comp.ComplianceManager()  # default threshold=30, reminders [30,15,5]
    comp.import_from_csv(str(INPUT_CSV), mgr)
    return mgr


def expected_status(exp_str: str, today: date = date.today(), threshold: int = 30) -> str:
    """Independently derive the expected compliance status for a doc."""
    if not exp_str:
        return "missing"
    exp = date.fromisoformat(exp_str)
    days = (exp - today).days
    if days < 0:
        return "expired"
    if days <= threshold:
        return "expiring_soon"
    return "active"


def input_rows():
    """Parse the input CSV independently (no pandas) for expected-state checks."""
    import csv

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class ComplianceGoldenFixtureTests(unittest.TestCase):
    """Compare the report against the regenerated golden fixture (stable fields)."""

    def test_summary_stable_counts_match_fixture(self):
        summary = build_manager().get_dashboard_summary()
        # total_documents / total_subcontractors never drift with the clock
        self.assertEqual(summary["total_documents"], EXPECTED["summary"]["total_documents"])
        self.assertEqual(summary["total_subcontractors"],
                         EXPECTED["summary"]["total_subcontractors"])

    def test_full_report_stable_fields_match_fixture(self):
        report = build_manager().get_compliance_report()
        actual = report["full_report"]
        expected = EXPECTED["full_report"]
        self.assertEqual(len(actual), len(expected))
        # Compare the fields that do not depend on today's date
        stable_keys = (
            "company_name", "trade", "contact_name", "contact_email",
            "document_type", "issued_date", "expiration_date",
            "policy_number", "notes",
        )
        for got, want in zip(actual, expected):
            for k in stable_keys:
                self.assertEqual(got[k], want[k], f"mismatch on {k}: {got[k]!r} vs {want[k]!r}")

    def test_non_compliant_stable_fields_match_fixture(self):
        report = build_manager().get_compliance_report()
        actual = report["non_compliant"]
        expected = EXPECTED["non_compliant"]
        self.assertEqual(len(actual), len(expected))
        actual_by = {(r["subcontractor"], r["document_type"]): r for r in actual}
        for want in expected:
            key = (want["subcontractor"], want["document_type"])
            self.assertIn(key, actual_by)
            got = actual_by[key]
            for k in ("trade", "status", "expiration_date", "contact_email"):
                self.assertEqual(got[k], want[k], f"{key} mismatch on {k}")


class ComplianceStatusLogicTests(unittest.TestCase):
    """Independently verify the script's status logic against today's date."""

    def test_summary_status_counts_match_independent_computation(self):
        summary = build_manager().get_dashboard_summary()
        rows = input_rows()
        counts = {"active": 0, "expiring_soon": 0, "expired": 0,
                  "missing": 0, "pending_renewal": 0}
        for r in rows:
            if not r["document_type"]:
                continue
            st = expected_status(r["expiration_date"])
            counts[st] += 1
        for k, v in counts.items():
            self.assertEqual(summary[k], v, f"status {k}: {summary[k]} vs expected {v}")

    def test_summary_counts_sum_to_total_documents(self):
        summary = build_manager().get_dashboard_summary()
        counted = (summary["active"] + summary["expiring_soon"] + summary["expired"]
                   + summary["missing"] + summary["pending_renewal"])
        self.assertEqual(counted, summary["total_documents"])

    def test_expired_docs_flagged_in_non_compliant(self):
        today = date.today()
        report = build_manager().get_compliance_report()
        non_comp = {(r["subcontractor"], r["document_type"]) for r in report["non_compliant"]}
        for r in input_rows():
            if not r["expiration_date"]:
                continue
            if date.fromisoformat(r["expiration_date"]) < today:
                self.assertIn((r["company_name"], r["document_type"]), non_comp)

    def test_missing_docs_flagged_in_non_compliant(self):
        report = build_manager().get_compliance_report()
        non_comp = {(r["subcontractor"], r["document_type"]) for r in report["non_compliant"]}
        for r in input_rows():
            if not r["document_type"]:
                continue
            if not r["expiration_date"]:
                self.assertIn((r["company_name"], r["document_type"]), non_comp)

    def test_expiring_soon_excluded_from_non_compliant(self):
        report = build_manager().get_compliance_report()
        for r in report["non_compliant"]:
            self.assertIn(r["status"], ("expired", "missing"),
                          f"expiring_soon should not appear in non_compliant: {r}")

    def test_days_expired_recomputed_correctly(self):
        today = date.today()
        report = build_manager().get_compliance_report()
        for r in report["non_compliant"]:
            if r["status"] == "expired":
                exp = date.fromisoformat(r["expiration_date"])
                self.assertEqual(r["days_expired"], (today - exp).days)
            else:
                self.assertIsNone(r["days_expired"])


class ComplianceReminderCadenceTests(unittest.TestCase):
    """Verify the 30/15/5 reminder cadence and threshold boundaries."""

    def test_default_reminder_schedule_is_30_15_5(self):
        mgr = comp.ComplianceManager()
        self.assertEqual(mgr.reminder_schedule, [30, 15, 5])

    def test_threshold_30_controls_expiring_soon_boundary(self):
        # 31 days out -> active, 30 days out -> expiring_soon
        today = date.today()
        sub = comp.Subcontractor(company_name="T", trade="t", is_active=True)
        just_out = comp.ComplianceDocument(
            subcontractor_id=sub.id,
            document_type=comp.DocumentType.COI,
            expiration_date=today + timedelta(days=31),
        )
        at_edge = comp.ComplianceDocument(
            subcontractor_id=sub.id,
            document_type=comp.DocumentType.LICENSE,
            expiration_date=today + timedelta(days=30),
        )
        mgr = comp.ComplianceManager()
        mgr.add_subcontractor(sub)
        mgr.add_document(just_out)
        mgr.add_document(at_edge)
        self.assertEqual(just_out.status, comp.ComplianceStatus.ACTIVE)
        self.assertEqual(at_edge.status, comp.ComplianceStatus.EXPIRING_SOON)

    def test_reminder_email_subject_carries_cadence_day(self):
        sub = comp.Subcontractor(
            company_name="SubCo", contact_name="Pat", contact_email="pat@sub.co", trade="t"
        )
        doc = comp.ComplianceDocument(
            subcontractor_id=sub.id,
            document_type=comp.DocumentType.COI,
            expiration_date=date.today().replace(year=date.today().year + 1),
            policy_number="P1",
        )
        for days in (30, 15, 5):
            email = comp.generate_reminder_email(sub, doc, days, "PM", "pm@firm.com")
            self.assertEqual(email["days_until_expiry"], days)
            self.assertIn(f"{days} days", email["subject"])
            self.assertEqual(email["to"], "pat@sub.co")
            self.assertEqual(email["subcontractor"], "SubCo")

    def test_missing_doc_has_no_reminder_target(self):
        # A missing doc has no expiration date; reminder generation should not be
        # applicable — the manager surfaces it in non_compliant instead.
        doc = comp.ComplianceDocument(
            subcontractor_id=uuid4(),
            document_type=comp.DocumentType.COI,
            expiration_date=None,
        )
        doc.update_status()
        self.assertEqual(doc.status, comp.ComplianceStatus.MISSING)
        self.assertIsNone(doc.days_until_expiry)


if __name__ == "__main__":
    unittest.main()
