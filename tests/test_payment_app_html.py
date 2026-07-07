"""
Tests for payment-app-html: print-ready G702/G703 renderer.

The HTML must:
- contain <!DOCTYPE html>
- contain $126,000.00 and $492,000.00 (current amount due / balance to finish)
- have exactly 3 G703 data rows
- reference http(s) only in the single trailwiseai.com footer link
- parse cleanly with html.parser
"""

from __future__ import annotations

import html.parser
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "4_Trailwise_Documents" / "payment-app-html" / "scripts" / "payment_app_html.py"
INPUT_PATH = REPO_ROOT / "4_Trailwise_Documents" / "payment-app-html" / "fixtures" / "input" / "pay_app.json"
EXPECTED_DIR = REPO_ROOT / "4_Trailwise_Documents" / "payment-app-html" / "fixtures" / "expected"
EXPECTED_HTML = EXPECTED_DIR / "pay_app.html"


def _load_module():
    spec = importlib.util.spec_from_file_location("payment_app_html_under_test", str(SCRIPT_PATH))
    assert spec is not None and spec.loader is not None, f"Could not load spec for {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["payment_app_html_under_test"] = module
    spec.loader.exec_module(module)
    return module


m = _load_module()


@pytest.fixture(scope="module")
def html_text() -> str:
    """Render the canonical pay_app.json to HTML (idempotent — file is also committed)."""
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    rc = subprocess.call(
        [sys.executable, str(SCRIPT_PATH), str(INPUT_PATH), "--out", str(EXPECTED_HTML)],
        cwd=str(REPO_ROOT),
    )
    assert rc == 0, f"payment_app_html.py exited {rc}"
    return EXPECTED_HTML.read_text(encoding="utf-8")


def test_output_is_self_contained_doctype(html_text: str):
    assert "<!DOCTYPE html>" in html_text


def test_output_contains_current_amount_due(html_text: str):
    assert "$126,000.00" in html_text


def test_output_contains_balance_to_finish(html_text: str):
    assert "$492,000.00" in html_text


def test_g703_has_exactly_three_data_rows(html_text: str):
    """
    G703 table has exactly 3 data rows (lines 1, 2, 3). The plan's tests say
    'G703 table has exactly 3 data rows' — we read that as data rows excluding
    any TOTAL/summary row.
    """
    # Find the G703 heading and the table that follows it.
    g703_idx = html_text.find("G703 &mdash; Continuation Sheet")
    assert g703_idx >= 0, "G703 heading not found"
    after = html_text[g703_idx:]
    table_match = re.search(r"<table>(.*?)</table>", after, re.DOTALL)
    assert table_match, "G703 table not found"
    section = table_match.group(1)
    tbody = re.search(r"<tbody>(.*?)</tbody>", section, re.DOTALL)
    assert tbody, "G703 tbody not found"
    body = tbody.group(1)
    rows = re.findall(r"<tr>", body)
    # Plan spec: exactly 3 data rows. With no totals row counted, that is 3.
    assert len(rows) == 3, f"Expected 3 G703 data rows, got {len(rows)}"


def test_no_external_resources_except_footer_link(html_text: str):
    """
    Only allowed http(s) reference is the single trailwiseai.com footer link.
    No CDN fonts, no images, no <link rel="stylesheet"> to external URLs.
    """
    matches = re.findall(r'(?:src|href)=["\']https?://[^"\']+["\']', html_text)
    # Remove the single allowed trailwiseai.com footer link
    offending = [m for m in matches if "trailwiseai.com" not in m]
    assert offending == [], f"Found external resources: {offending}"
    # And there should be exactly ONE trailwiseai.com reference
    tw_links = [m for m in matches if "trailwiseai.com" in m]
    assert len(tw_links) == 1, f"Expected 1 trailwiseai.com link, got {len(tw_links)}"


def test_html_parses_cleanly(html_text: str):
    """html.parser must consume the document without errors."""
    parsed = []

    class Sink(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            parsed.append((tag, dict(attrs)))

    p = Sink()
    p.feed(html_text)
    p.close()
    # Basic structural sanity: at least the document body and a table
    tags = {t for t, _ in parsed}
    assert "body" in tags
    assert "table" in tags
    assert "h1" in tags


def test_no_dollar_amount_drifted(html_text: str):
    """
    Cross-check: the rendered HTML's money formatting uses the same numbers the
    live code produces. Confirms the rendering path doesn't truncate, round, or
    swap digits.
    """
    payload_module = _load_module()  # not needed for math, but a load check
    import json
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    g702 = payload["g702"]
    expected_current = "${:,.2f}".format(g702["current_amount_due"])
    expected_balance = "${:,.2f}".format(g702["balance_to_finish"])
    assert expected_current in html_text
    assert expected_balance in html_text


def test_signatures_blocks_present(html_text: str):
    assert "Contractor" in html_text
    assert "Architect" in html_text
