"""
Tests for ar-aging-excel.

Buckets must tie to ar-collections-automation's committed goldens
(1_Trailwise_Toolkit/ar-collections-automation/fixtures/expected/ar_aging_summary.json)
to the penny. If your bucketing disagrees, your edges are wrong — fix them,
do not touch the goldens.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "4_Trailwise_Documents" / "ar-aging-excel" / "scripts" / "ar_aging_excel.py"
INPUT_CSV = REPO_ROOT / "4_Trailwise_Documents" / "ar-aging-excel" / "fixtures" / "input" / "invoices.csv"
EXPECTED_DIR = REPO_ROOT / "4_Trailwise_Documents" / "ar-aging-excel" / "fixtures" / "expected"
EXPECTED_XLSX = EXPECTED_DIR / "ar_aging_2026-06-30.xlsx"

GOLDEN_PATH = (
    REPO_ROOT
    / "1_Trailwise_Toolkit"
    / "ar-collections-automation"
    / "fixtures"
    / "expected"
    / "ar_aging_summary.json"
)

# Locked as-of per the plan (the date the ar-collections goldens were generated on)
AS_OF = "2026-06-30"

EXPECTED_BUCKETS = {
    "current": 25000.0,
    "31_60": 18000.0,
    "61_90": 16000.0,
    "90_plus": 22000.0,
}
EXPECTED_TOTAL = 81000.0
EXPECTED_OPEN_INVOICE_COUNT = 4


def _load_module():
    spec = importlib.util.spec_from_file_location("ar_aging_excel_under_test", str(SCRIPT_PATH))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules so dataclass introspection (Python 3.14 +
    # `from __future__ import annotations`) can find the module's namespace.
    sys.modules["ar_aging_excel_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def workbook_path():
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    rc = subprocess.call(
        [sys.executable, str(SCRIPT_PATH), str(INPUT_CSV),
         "--as-of", AS_OF, "--out", str(EXPECTED_XLSX)],
        cwd=str(REPO_ROOT),
    )
    assert rc == 0
    return EXPECTED_XLSX


def _load_workbook(path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    return openpyxl.load_workbook(path)


def test_golden_ar_collections_totals_match_buckets():
    """The ar-collections goldens are the source of truth for the bucket amounts."""
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert golden["aging_summary"]["current"] == pytest.approx(25000)
    assert golden["aging_summary"]["31_60"] == pytest.approx(18000)
    assert golden["aging_summary"]["61_90"] == pytest.approx(16000)
    assert golden["aging_summary"]["90_plus"] == pytest.approx(22000)
    assert golden["total_outstanding"] == pytest.approx(81000)


def test_module_aggregates_match_goldens():
    """The in-process aggregate() must produce the same numbers as the goldens."""
    m = _load_module()
    invoices = m.load_invoices(INPUT_CSV)
    agg = m.aggregate(invoices, date(2026, 6, 30))
    assert agg["bucket_totals"] == EXPECTED_BUCKETS
    assert agg["total_outstanding"] == EXPECTED_TOTAL
    assert len(agg["detail"]) == EXPECTED_OPEN_INVOICE_COUNT


def test_workbook_summary_sheet_buckets(workbook_path):
    wb = _load_workbook(workbook_path)
    assert "Aging Summary" in wb.sheetnames
    ws = wb["Aging Summary"]
    # The buckets are listed in BUCKET_ORDER starting at row 5, column C is amount.
    summary_amounts = {row[0].value: row[2].value for row in ws.iter_rows(min_row=5, max_row=8, max_col=3)}
    label_map = {
        "Current (0-30)": "current",
        "31-60 days": "31_60",
        "61-90 days": "61_90",
        "90+ days": "90_plus",
    }
    actual = {label_map[k]: v for k, v in summary_amounts.items()}
    assert actual == EXPECTED_BUCKETS
    # Total row at row 9
    total = ws.cell(row=9, column=3).value
    assert total == pytest.approx(EXPECTED_TOTAL, abs=0.01)


def test_workbook_detail_row_count(workbook_path):
    wb = _load_workbook(workbook_path)
    assert "Invoice Detail" in wb.sheetnames
    ws = wb["Invoice Detail"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    # Detail rows = open invoice count (paid invoices are excluded)
    assert len(rows) == EXPECTED_OPEN_INVOICE_COUNT
    # All rows should have a non-empty invoice ID
    for row in rows:
        assert row[0], f"Missing invoice ID: {row}"


def test_workbook_has_chart_on_summary_sheet(workbook_path):
    wb = _load_workbook(workbook_path)
    ws = wb["Aging Summary"]
    assert len(ws._charts) >= 1, "No chart attached to the Aging Summary sheet"


def test_bucket_edge_boundaries():
    """Spot-check the bucketing edges (1-30 current, 31-60, 61-90, 90+)."""
    m = _load_module()
    from datetime import date as _d
    as_of = _d(2026, 6, 30)
    # dpd 30 → current; 31 → 31_60
    inv_30 = m.Invoice("x", "c", "C", as_of, as_of, 100.0, 0.0, "open")
    assert inv_30.bucket(as_of) == "current"
    inv_31 = m.Invoice("x", "c", "C", as_of, as_of, 100.0, 0.0, "open")
    # Need to construct dpd=31 via a different due_date
    inv_31_obj = m.Invoice(
        "x", "c", "C",
        invoice_date=as_of, due_date=_d(2026, 5, 30),  # 31 days before as_of
        amount=100.0, amount_paid=0.0, status="open",
    )
    assert inv_31_obj.days_past_due(as_of) == 31
    assert inv_31_obj.bucket(as_of) == "31_60"
    inv_60 = m.Invoice("x", "c", "C", as_of, _d(2026, 5, 1), 100.0, 0.0, "open")
    assert inv_60.days_past_due(as_of) == 60
    assert inv_60.bucket(as_of) == "31_60"
    inv_61 = m.Invoice("x", "c", "C", as_of, _d(2026, 4, 30), 100.0, 0.0, "open")
    assert inv_61.days_past_due(as_of) == 61
    assert inv_61.bucket(as_of) == "61_90"
    inv_90 = m.Invoice("x", "c", "C", as_of, _d(2026, 4, 1), 100.0, 0.0, "open")
    assert inv_90.days_past_due(as_of) == 90
    assert inv_90.bucket(as_of) == "61_90"
    inv_91 = m.Invoice("x", "c", "C", as_of, _d(2026, 3, 31), 100.0, 0.0, "open")
    assert inv_91.days_past_due(as_of) == 91
    assert inv_91.bucket(as_of) == "90_plus"


def test_paid_invoice_excluded_from_detail(workbook_path):
    wb = _load_workbook(workbook_path)
    ws = wb["Invoice Detail"]
    ids = {row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]}
    # INV-1001 is paid; should NOT be in the detail
    assert "INV-1001" not in ids
    assert "INV-1005" not in ids
    # Open ones should be
    for inv in ("INV-1002", "INV-1003", "INV-1004", "INV-1006"):
        assert inv in ids
