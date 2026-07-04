"""Financial data-source audit: inventory sources, map flows, surface silos, score automation opportunities."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional


class DataType(Enum):
    STRUCTURED = "structured"        # Excel, CSV, SQL, QuickBooks exports
    SEMI_STRUCTURED = "semi"         # JSON, XML, bank CSV with mixed formats
    UNSTRUCTURED = "unstructured"    # PDF invoices, email, scanned receipts


class DataLocation(Enum):
    ACCOUNTING_SYSTEM = "accounting"  # QuickBooks, Xero, Sage
    SPREADSHEET = "spreadsheet"       # Excel, Google Sheets
    EMAIL = "email"                   # Gmail, Outlook attachments
    FILE_SHARE = "file_share"        # Shared drive, Dropbox, Google Drive
    ERP = "erp"                       # SAP, Oracle, custom ERP
    BANK_PORTAL = "bank"             # Bank website, bank API
    PROJECT_MGMT = "project_mgmt"    # Procore, BuilderTrend, Asana
    PAPER = "paper"                  # Physical paper (yes, still)


@dataclass
class DataSource:
    name: str                          # "QuickBooks Online"
    location: DataLocation
    data_type: DataType
    format: str                        # "CSV export", "API", "PDF", "Excel"
    frequency: str                     # "daily", "weekly", "monthly", "ad hoc"
    owner: str                         # Who controls this data
    contains: List[str]                # ["invoices", "payments", "AR aging", "budget"]
    integration_possible: bool         # Can it be automated?
    integration_method: str            # "API", "CSV export", "OCR", "manual entry"
    volume: str                        # "50 invoices/week", "1 budget/month"
    quality_score: int                 # 1-5, subjective assessment
    notes: str = ""


@dataclass
class DataFlow:
    from_source: str
    to_source: str
    data_type: str           # What data moves
    method: str              # "manual copy", "CSV export/import", "API", "email"
    frequency: str           # How often
    latency: str             # "real-time", "daily", "weekly", "monthly"
    manual_steps: int        # Number of human touches
    error_prone: bool        # Does this flow frequently cause errors?


class AuditReport:
    """Aggregate sources and flows, surface silos, and rank automation opportunities."""

    def __init__(self, sources: List[DataSource], flows: List[DataFlow]):
        self.sources = sources
        self.flows = flows

    def silos(self) -> List[DataSource]:
        """A silo holds data no other system reaches and lacks an integration path."""
        return [
            s for s in self.sources
            if not s.integration_possible
            and s.integration_method.lower() in {"manual entry", "none", ""}
        ]

    def automation_opportunities(self) -> List[Dict]:
        """Find the highest-impact automation targets."""
        opportunities = []
        for flow in self.flows:
            if flow.method == "manual copy" and flow.error_prone:
                opportunities.append({
                    "flow": f"{flow.from_source} → {flow.to_source}",
                    "data": flow.data_type,
                    "current_method": flow.method,
                    "frequency": flow.frequency,
                    "manual_steps": flow.manual_steps,
                    "impact": "high" if flow.frequency in ["daily", "weekly"] else "medium",
                    "suggested_skill": self._suggest_skill(flow),
                })
        # Sort by impact (high first)
        opportunities.sort(key=lambda x: 0 if x["impact"] == "high" else 1)
        return opportunities

    def _suggest_skill(self, flow: DataFlow) -> str:
        if "invoice" in flow.data_type.lower():
            return "invoice-reconciliation"
        if "budget" in flow.data_type.lower():
            return "budget-variance-tracker"
        if "payment" in flow.data_type.lower():
            return "n8n-payment-reminders"
        if "report" in flow.data_type.lower():
            return "n8n-recurring-reports"
        return "data-quality-check"


def load_audit(path: Path) -> AuditReport:
    """Load sources and flows from a JSON file produced during the audit."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = [
        DataSource(
            name=s["name"],
            location=DataLocation(s["location"]),
            data_type=DataType(s["data_type"]),
            format=s["format"],
            frequency=s["frequency"],
            owner=s["owner"],
            contains=s.get("contains", []),
            integration_possible=bool(s["integration_possible"]),
            integration_method=s["integration_method"],
            volume=s["volume"],
            quality_score=int(s["quality_score"]),
            notes=s.get("notes", ""),
        )
        for s in data.get("sources", [])
    ]
    flows = [DataFlow(**f) for f in data.get("flows", [])]
    return AuditReport(sources, flows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit financial data sources and rank automation opportunities.")
    parser.add_argument("audit", type=Path, help="JSON file with 'sources' and 'flows' arrays.")
    parser.add_argument("--output", type=Path, help="Write the report to a file instead of stdout.")
    args = parser.parse_args()

    report = load_audit(args.audit)
    result = {
        "sources": [asdict(s) | {"location": s.location.value, "data_type": s.data_type.value} for s in report.sources],
        "flows": [asdict(f) for f in report.flows],
        "silos": [s.name for s in report.silos()],
        "automation_opportunities": report.automation_opportunities(),
    }
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
