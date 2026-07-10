"""Tests for invoice_file_organizer.py.

Covers: date parsing, vendor normalization, construction doc detection,
metadata extraction, full pipeline (dry run, copy, move, dedup, CSV).
"""
import sys
import os
import csv
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
    "1_Trailwise_Toolkit", "invoice-reconciliation", "scripts"))

from invoice_file_organizer import (
    organize_invoices, extract_invoice_metadata, identify_construction_doc,
    build_filename, build_output_path, normalize_vendor, parse_date,
    file_hash, extract_from_filename, ExtractedInvoice,
    SUPPORTED_EXTENSIONS, CONSTRUCTION_DOC_PATTERNS,
)


# ── Date parsing ────────────────────────────────────────────

class TestParseDate:
    @pytest.mark.parametrize("raw,expected", [
        ("03/15/2026", "2026-03-15"),
        ("2026-03-15", "2026-03-15"),
        ("3/5/26", "2026-03-05"),
        ("12-31-2025", "2025-12-31"),
    ])
    def test_valid_formats(self, raw, expected):
        assert parse_date(raw) == expected

    @pytest.mark.parametrize("raw", ["not a date", "", None, "13/45/2026"])
    def test_invalid_returns_none(self, raw):
        assert parse_date(raw) is None


# ── Vendor normalization ────────────────────────────────────

class TestNormalizeVendor:
    @pytest.mark.parametrize("raw,expected", [
        ("home depot", "Home Depot"),
        ("amazon", "Amazon"),
        ("lowes", "Lowes"),
        ("ACME LLC", "Acme LLC"),
        ("Smith Inc", "Smith INC"),
        ("acme supply co.", "Acme Supply CO"),
        ("grainger", "Grainger"),
    ])
    def test_normalization(self, raw, expected):
        assert normalize_vendor(raw) == expected

    def test_strips_trailing_punctuation(self):
        assert normalize_vendor("Acme,") == "Acme"

    def test_preserves_uppercase_abbreviations(self):
        result = normalize_vendor("test corp")
        assert "CORP" in result


# ── Construction doc detection ──────────────────────────────

class TestConstructionDocDetection:
    @pytest.mark.parametrize("text,expected_type", [
        ("AIA G702 Application for Payment", "aia_g702"),
        ("G703 Schedule of Values", "aia_g703"),
        ("Change Order #005", "change_order"),
        ("ACORD 25 Certificate of Insurance", "coi"),
        ("Conditional Waiver on Progress Payment", "lien_waiver"),
        ("Unconditional Waiver and Release on Final Payment", "lien_waiver"),
        ("W-9 Request for Taxpayer Identification", "w9"),
        ("Submittal Transmittal", "submittal"),
    ])
    def test_detects_doc_type(self, text, expected_type):
        result = identify_construction_doc(text)
        assert result is not None
        assert result[0] == expected_type

    def test_returns_none_for_plain_invoice(self):
        assert identify_construction_doc("Invoice from Home Depot") is None

    def test_returns_category_and_description(self):
        result = identify_construction_doc("AIA G702 Application")
        assert result[1] == "Pay Applications"
        assert "G702" in result[2]

    def test_all_patterns_have_config(self):
        """Every CONSTRUCTION_DOC_PATTERNS entry has pattern, category, description."""
        for doc_type, config in CONSTRUCTION_DOC_PATTERNS.items():
            assert "pattern" in config, f"{doc_type} missing pattern"
            assert "category" in config, f"{doc_type} missing category"
            assert "description" in config, f"{doc_type} missing description"


# ── Metadata extraction ─────────────────────────────────────

class TestExtractMetadata:
    def test_standard_invoice(self):
        text = "Invoice #INV-2026-0042\nDate: 03/15/2026\nTotal: $1,500.00\nFrom: Acme Supply Co."
        inv = extract_invoice_metadata("/fake/invoice.pdf", text_content=text)
        assert inv.vendor == "Acme Supply CO"
        assert inv.date == "2026-03-15"
        assert inv.amount == "1,500.00"
        assert inv.invoice_number == "INV-2026-0042"
        assert inv.needs_review is False

    def test_g702_extraction(self):
        text = "AIA G702 Application and Certificate for Payment\nDate: 06/30/2026"
        inv = extract_invoice_metadata("/fake/g702.pdf", text_content=text)
        assert inv.category == "Pay Applications"
        assert inv.doc_type == "aia_g702"
        assert inv.date == "2026-06-30"

    def test_change_order_extraction(self):
        text = "Change Order #005\nDate: 06/20/2026\nTotal: $3,200.00\nFrom: Smith Construction LLC"
        inv = extract_invoice_metadata("/fake/co.pdf", text_content=text)
        assert inv.category == "Change Orders"
        assert inv.doc_type == "change_order"
        assert inv.vendor == "Smith Construction LLC"

    def test_coi_extraction(self):
        text = "ACORD 25 Certificate of Insurance\nDate: 01/15/2026\nFrom: ABC Insurance"
        inv = extract_invoice_metadata("/fake/coi.pdf", text_content=text)
        assert inv.category == "Insurance"
        assert inv.doc_type == "coi"

    def test_empty_content_flags_review(self):
        inv = extract_invoice_metadata("/fake/unknown.pdf", text_content="")
        assert inv.needs_review is True

    def test_nonexistent_file_no_crash(self):
        inv = extract_invoice_metadata("/nonexistent/path.pdf", text_content="")
        assert inv is not None

    def test_vendor_only_still_flags_date_missing(self):
        inv = extract_invoice_metadata("/fake/v.pdf", text_content="From: Acme Supply")
        assert inv.needs_review is True
        assert "date" in inv.review_reason.lower()


# ── Filename extraction fallback ────────────────────────────

class TestFilenameExtraction:
    def test_extracts_date_from_filename(self):
        clues = extract_from_filename("invoice_acme_2026-03-15.pdf")
        assert clues.get("date") == "2026-03-15"

    def test_extracts_vendor_from_filename(self):
        clues = extract_from_filename("invoice_acme_2026-03-15.pdf")
        assert "acme" in clues.get("vendor", "").lower()

    def test_no_date_in_filename(self):
        clues = extract_from_filename("invoice.pdf")
        assert "date" not in clues


# ── Build filename ──────────────────────────────────────────

class TestBuildFilename:
    def test_standard_format(self):
        inv = ExtractedInvoice(
            original_path="/t.pdf", vendor="Acme Supply",
            date="2026-03-15", description="Plumbing", doc_type="invoice",
        )
        assert build_filename(inv, ".pdf") == "2026-03-15 Acme Supply - Invoice - Plumbing.pdf"

    def test_unknown_vendor(self):
        inv = ExtractedInvoice(
            original_path="/t.pdf", vendor="Unknown",
            date="2026-01-01", description="Test", doc_type="invoice",
        )
        fname = build_filename(inv, ".pdf")
        assert "Unknown" in fname

    def test_strips_special_chars(self):
        inv = ExtractedInvoice(
            original_path="/t.pdf", vendor="Acme/Supply<>",
            date="2026-03-15", description="Test<>", doc_type="invoice",
        )
        fname = build_filename(inv, ".pdf")
        assert "/" not in fname
        assert "<" not in fname
        assert ">" not in fname


# ── Build output path ───────────────────────────────────────

class TestBuildOutputPath:
    def test_path_contains_year(self):
        inv = ExtractedInvoice(
            original_path="/t.pdf", vendor="Acme", date="2026-03-15",
            description="Test", category="Software", doc_type="invoice",
        )
        path = build_output_path(inv, Path("/tmp/organized"))
        assert "2026" in str(path)

    def test_path_contains_vendor(self):
        inv = ExtractedInvoice(
            original_path="/t.pdf", vendor="Acme Supply", date="2026-03-15",
            description="Test", category="Software", doc_type="invoice",
        )
        path = build_output_path(inv, Path("/tmp/organized"))
        assert "Acme Supply" in str(path)

    def test_path_contains_category(self):
        inv = ExtractedInvoice(
            original_path="/t.pdf", vendor="Acme", date="2026-03-15",
            description="Test", category="Pay Applications", doc_type="invoice",
        )
        path = build_output_path(inv, Path("/tmp/organized"))
        assert "Pay Applications" in str(path)


# ── Full pipeline ───────────────────────────────────────────

@pytest.fixture
def messy_dir():
    """Temp dir with test files, cleaned up after."""
    tmpdir = tempfile.mkdtemp(prefix="hermes-test-")
    files = {
        "invoice_acme_2026-03-15.pdf": b"fake pdf content 1",
        "IMG_2847.jpg": b"fake image content",
        "G702_payapp.pdf": b"fake g702 content",
        "duplicate1.pdf": b"same content",
        "duplicate2.pdf": b"same content",
        "ignored.docx": b"should be skipped",
    }
    for name, content in files.items():
        with open(os.path.join(tmpdir, name), "wb") as f:
            f.write(content)
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestOrganizePipeline:
    def test_dry_run_excludes_unsupported(self, messy_dir):
        result = organize_invoices(messy_dir, os.path.join(messy_dir, "out"), dry_run=True)
        assert result["total_files_found"] == 5  # excludes .docx

    def test_dry_run_finds_duplicate(self, messy_dir):
        result = organize_invoices(messy_dir, os.path.join(messy_dir, "out"), dry_run=True)
        assert result["duplicates_found"] == 1

    def test_dry_run_no_errors(self, messy_dir):
        result = organize_invoices(messy_dir, os.path.join(messy_dir, "out"), dry_run=True)
        assert result["errors"] == 0

    def test_dry_run_does_not_write_csv(self, messy_dir):
        result = organize_invoices(messy_dir, os.path.join(messy_dir, "out"), dry_run=True)
        assert "not written" in result["csv_path"]

    def test_copy_mode_preserves_originals(self, messy_dir):
        out = os.path.join(messy_dir, "out_copy")
        organize_invoices(messy_dir, out, dry_run=False)
        assert os.path.exists(os.path.join(messy_dir, "invoice_acme_2026-03-15.pdf"))

    def test_copy_mode_writes_csv(self, messy_dir):
        out = os.path.join(messy_dir, "out_csv")
        result = organize_invoices(messy_dir, out, dry_run=False)
        assert os.path.exists(result["csv_path"])

    def test_csv_header_correct(self, messy_dir):
        out = os.path.join(messy_dir, "out_header")
        result = organize_invoices(messy_dir, out, dry_run=False)
        with open(result["csv_path"]) as f:
            header = next(csv.reader(f))
        assert header == ["Date", "Vendor", "Invoice Number", "Description", "Amount", "Category", "File Path"]

    def test_csv_rows_after_dedup(self, messy_dir):
        out = os.path.join(messy_dir, "out_rows")
        result = organize_invoices(messy_dir, out, dry_run=False)
        with open(result["csv_path"]) as f:
            rows = list(csv.reader(f))
        # header + 4 data rows (5 files - 1 duplicate)
        assert len(rows) == 5

    def test_move_mode_removes_originals(self, messy_dir):
        out = os.path.join(messy_dir, "out_move")
        organize_invoices(messy_dir, out, move=True, dry_run=False)
        assert not os.path.exists(os.path.join(messy_dir, "invoice_acme_2026-03-15.pdf"))

    def test_organized_count_after_dedup(self, messy_dir):
        result = organize_invoices(messy_dir, os.path.join(messy_dir, "out_count"), dry_run=True)
        assert result["files_organized"] == 4  # 5 found - 1 duplicate


# ── File hash dedup ─────────────────────────────────────────

class TestFileHash:
    def test_identical_files_same_hash(self):
        tmpdir = tempfile.mkdtemp(prefix="hermes-test-")
        try:
            p1, p2 = os.path.join(tmpdir, "a.pdf"), os.path.join(tmpdir, "b.pdf")
            for p in (p1, p2):
                with open(p, "wb") as f:
                    f.write(b"identical")
            assert file_hash(p1) == file_hash(p2)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_different_files_different_hash(self):
        tmpdir = tempfile.mkdtemp(prefix="hermes-test-")
        try:
            p1, p2 = os.path.join(tmpdir, "a.pdf"), os.path.join(tmpdir, "b.pdf")
            with open(p1, "wb") as f: f.write(b"one")
            with open(p2, "wb") as f: f.write(b"two")
            assert file_hash(p1) != file_hash(p2)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── Supported extensions ────────────────────────────────────

class TestSupportedExtensions:
    @pytest.mark.parametrize("ext", [".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"])
    def test_supported(self, ext):
        assert ext in SUPPORTED_EXTENSIONS

    @pytest.mark.parametrize("ext", [".docx", ".xlsx", ".pptx", ".mp4", ".zip"])
    def test_unsupported(self, ext):
        assert ext not in SUPPORTED_EXTENSIONS
