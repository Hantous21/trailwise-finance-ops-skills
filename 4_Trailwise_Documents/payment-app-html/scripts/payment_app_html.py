"""
Render a structured G702/G703 pay app as a self-contained, print-ready HTML document.

Reads {"g702": {...}, "g703": [...]} (the canonical output of
payment-app-generator) and writes ONE print-first HTML file:
  - All CSS inline in a single <style> block
  - Zero external resources (no CDN fonts, no images, no <link>)
  - One footer link to trailwiseai.com (the only http(s) reference)
  - Monochrome, no background colors (printer-friendly)
  - @media print sets page margins; no backgrounds

Usage:
    python3 scripts/payment_app_html.py fixtures/input/pay_app.json --out pay_app.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Money / label formatting
# ---------------------------------------------------------------------------

_MONEY_FIELDS = {
    "original_contract_sum",
    "net_change_orders",
    "contract_sum_to_date",
    "total_completed_stored",
    "retainage",
    "total_earnings_less_retainage",
    "less_previous_payments",
    "current_amount_due",
    "balance_to_finish",
    "scheduled_value",
    "change_orders",
    "total_scheduled",
    "previous_completed",
    "current_completed",
    "total_completed",
    "stored_materials",
    "total_completed_stored",
    "retainage_held",
    "less_retainage",
    "amount",
}


def _fmt_money(value: Any) -> str:
    if value is None:
        return ""
    try:
        return "${:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return str(value)


def _labelize(key: str) -> str:
    return key.replace("_", " ").strip().title()


# ---------------------------------------------------------------------------
# HTML building
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  color: #000;
  background: #fff;
  font-family: "Times New Roman", Georgia, serif;
  font-size: 12pt;
  line-height: 1.35;
}
.page {
  max-width: 8.5in;
  margin: 0 auto;
  padding: 0.5in 0.6in;
}
h1, h2, h3 {
  font-family: Arial, Helvetica, sans-serif;
  margin: 0 0 0.3em 0;
}
h1 { font-size: 18pt; border-bottom: 2px solid #000; padding-bottom: 4pt; }
h2 { font-size: 13pt; margin-top: 1.2em; border-bottom: 1px solid #444; padding-bottom: 2pt; }
h3 { font-size: 11pt; }
.header { margin-bottom: 1em; }
.header dl { margin: 0; }
.header dt { font-weight: bold; display: inline-block; min-width: 9em; }
.header dd { display: inline; margin: 0; }
.header dd::after { content: ""; display: block; margin-bottom: 2pt; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5em 0 1em 0;
  font-size: 10pt;
}
th, td {
  border: 1px solid #000;
  padding: 3pt 5pt;
  text-align: left;
  vertical-align: top;
}
th {
  background: #eee;
  font-weight: bold;
}
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.totals { font-weight: bold; }
.signatures {
  display: flex;
  gap: 2em;
  margin-top: 2em;
  page-break-inside: avoid;
}
.signature-block {
  flex: 1 1 0;
  border-top: 1px solid #000;
  padding-top: 4pt;
  min-height: 1.6in;
}
.signature-block .label { font-weight: bold; }
.signature-block .line { margin-top: 1.4in; border-top: 1px solid #000; padding-top: 2pt; }
.footer {
  margin-top: 2em;
  padding-top: 0.5em;
  border-top: 1px solid #888;
  font-size: 9pt;
  text-align: center;
  color: #444;
}
@media print {
  body { font-size: 10pt; }
  .page { padding: 0.4in; }
  th { background: #ddd !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  thead { display: table-header-group; }
  tr, .signature-block, table { page-break-inside: avoid; }
}
"""


def _render_header(g702: Dict[str, Any]) -> str:
    project = html.escape(str(g702.get("project", "")))
    app_num = g702.get("application_number", "")
    period = g702.get("period_to", "")
    contractor = html.escape(str(g702.get("contractor", "")))
    owner = html.escape(str(g702.get("owner", "")))
    architect = html.escape(str(g702.get("architect", "")))
    contract_date = g702.get("contract_date", "")

    rows = [
        ("Project", project),
        ("Application No.", str(app_num)),
        ("Period To", str(period)),
        ("Contract Date", str(contract_date)),
        ("Contractor", contractor),
        ("Owner", owner),
        ("Architect", architect),
    ]
    dl = "\n".join(
        f"      <dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
        for k, v in rows if v
    )
    return (
        "    <div class=\"header\">\n"
        "      <h1>AIA G702 / G703 &mdash; Application and Certificate for Payment</h1>\n"
        f"      <dl>\n{dl}\n      </dl>\n"
        "    </div>"
    )


def _render_g702(g702: Dict[str, Any]) -> str:
    rows = []
    skip = {"application_number", "period_to", "project", "contractor",
            "owner", "architect", "contract_date", "change_orders", "percent_complete"}
    pct = g702.get("percent_complete")
    for key, val in g702.items():
        if key in skip:
            continue
        if key in _MONEY_FIELDS:
            display = _fmt_money(val)
            cls = "num"
        else:
            display = html.escape(str(val))
            cls = ""
        rows.append(
            f"      <tr><th scope=\"row\">{html.escape(_labelize(key))}</th>"
            f"<td class=\"{cls}\">{display}</td></tr>"
        )
    pct_row = ""
    if pct is not None:
        pct_row = (
            "      <tr><th scope=\"row\">Percent Complete</th>"
            f"<td class=\"num\">{pct:.2f}%</td></tr>"
        )
    cos = g702.get("change_orders") or []
    co_section = ""
    if cos:
        co_rows = []
        for co in cos:
            co_rows.append(
                "        <tr>"
                f"<td>{html.escape(str(co.get('co_number', '')))}</td>"
                f"<td>{html.escape(str(co.get('description', '')))}</td>"
                f"<td class=\"num\">{_fmt_money(co.get('amount'))}</td>"
                f"<td>{html.escape(str(co.get('approved')))}</td>"
                "</tr>"
            )
        co_section = (
            "      <h3>Change Orders (Approved)</h3>\n"
            "      <table>\n"
            "        <thead><tr>"
            "<th>CO #</th><th>Description</th><th class=\"num\">Amount</th><th>Approved</th>"
            "</tr></thead>\n"
            "        <tbody>\n"
            + "\n".join(co_rows) + "\n"
            "        </tbody>\n"
            "      </table>"
        )
    return (
        "    <h2>G702 &mdash; Summary</h2>\n"
        "    <table>\n"
        "      <thead><tr><th>Item</th><th class=\"num\">Value</th></tr></thead>\n"
        "      <tbody>\n"
        + "\n".join(rows) + "\n"
        + (pct_row + "\n" if pct_row else "")
        + "      </tbody>\n"
        "    </table>\n"
        + co_section
    )


def _render_g703(g703_rows: List[Dict[str, Any]]) -> str:
    headers = [
        ("line", "Line"),
        ("description", "Description"),
        ("scheduled_value", "Scheduled Value"),
        ("change_orders", "COs"),
        ("total_scheduled", "Total Scheduled"),
        ("previous_completed", "Previous Completed"),
        ("current_completed", "This Period"),
        ("total_completed", "Total Completed"),
        ("stored_materials", "Stored Materials"),
        ("total_completed_stored", "Completed & Stored"),
        ("retainage_pct", "Retain %"),
        ("retainage_held", "Retainage"),
        ("less_retainage", "Less Retainage"),
        ("completed_pct", "% Complete"),
    ]
    head = "".join(
        _th_cell(label, _is_money_col(k)) for k, label in headers
    )

    body_rows: List[str] = []
    for r in g703_rows:
        # Skip the generator's TOTAL row — the G703 continuation sheet in our
        # output is exactly one row per SOV line, with no summary row.
        if str(r.get("line", "")) == "TOTAL":
            continue
        cells = []
        for k, _ in headers:
            val = r.get(k, "")
            if _is_money_col(k):
                cells.append(_td_cell_money(val))
            elif k == "completed_pct":
                cells.append(_td_cell_pct(val))
            else:
                cells.append(_td_cell_text(val))
        body_rows.append("        <tr>" + "".join(cells) + "</tr>")

    return (
        "    <h2>G703 &mdash; Continuation Sheet</h2>\n"
        "    <table>\n"
        f"      <thead><tr>{head}</tr></thead>\n"
        "      <tbody>\n"
        + "\n".join(body_rows) + "\n"
        + "      </tbody>\n"
        "    </table>"
    )


def _is_money_col(key: str) -> bool:
    return key in _MONEY_FIELDS


def _th_cell(label: str, money: bool) -> str:
    cls = ' class="num"' if money else ''
    return f"<th{cls}>{html.escape(label)}</th>"


def _td_cell_text(val: Any) -> str:
    return f"<td>{html.escape(str(val))}</td>"


def _td_cell_money(val: Any) -> str:
    return f"<td class=\"num\">{_fmt_money(val)}</td>"


def _td_cell_pct(val: Any) -> str:
    try:
        return f"<td class=\"num\">{float(val):.2f}%</td>"
    except (TypeError, ValueError):
        return f"<td class=\"num\">{html.escape(str(val))}</td>"


def _render_signatures() -> str:
    return (
        "    <div class=\"signatures\">\n"
        "      <div class=\"signature-block\">\n"
        "        <div class=\"label\">Contractor</div>\n"
        "        <div class=\"line\">Name &amp; Date</div>\n"
        "      </div>\n"
        "      <div class=\"signature-block\">\n"
        "        <div class=\"label\">Architect</div>\n"
        "        <div class=\"line\">Name &amp; Date</div>\n"
        "      </div>\n"
        "    </div>"
    )


def render_html(payload: Dict[str, Any]) -> str:
    g702 = payload.get("g702", {}) or {}
    g703 = payload.get("g703", []) or []

    head = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Pay Application "
        f"{html.escape(str(g702.get('application_number', '')))}"
        " &mdash; "
        f"{html.escape(str(g702.get('project', '')))}"
        "</title>\n"
        f"  <style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "  <div class=\"page\">"
    )
    tail = (
        "    <div class=\"footer\">\n"
        "      Generated by Trailwise &middot; "
        "<a href=\"https://trailwiseai.com\">trailwiseai.com</a>\n"
        "    </div>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )
    return (
        head + "\n"
        + _render_header(g702) + "\n"
        + _render_g702(g702) + "\n"
        + _render_g703(g703) + "\n"
        + _render_signatures() + "\n"
        + tail
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Path to pay_app.json (g702 + g703 payload)")
    parser.add_argument("--out", required=True, help="Output HTML file path")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.out)
    if not in_path.exists():
        print(f"error: input not found: {in_path}", file=sys.stderr)
        return 2

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    html_doc = render_html(payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")

    g702 = payload.get("g702", {})
    print(f"Rendered pay app #{g702.get('application_number', '?')} "
          f"for {g702.get('project', '?')}: {out_path}")
    print(f"  current_amount_due = {_fmt_money(g702.get('current_amount_due'))}")
    print(f"  balance_to_finish  = {_fmt_money(g702.get('balance_to_finish'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
