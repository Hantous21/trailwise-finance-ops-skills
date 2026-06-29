---
name: "data-source-audit"
description: "Audit all financial data sources in a company. Map data flows, identify silos, and create a data inventory for automation planning."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "🔍"
    category: "data-assessment"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
---

# Data Source Audit

## Overview

Before automating anything, you need to know what data you have, where it lives, and how it flows (or doesn't). This skill audits all financial data sources in a company and creates a structured inventory.

## When to Use

- You don't have a complete list of where financial data lives
- Data is scattered across Excel, email, accounting software, and PDFs
- You're planning automation but don't know where to start
- Someone asked "where does this number come from?" and no one knew

## The Audit Framework

### Step 1: Inventory All Data Sources

For each source, record:

```python
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum

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
```

### Step 2: Map Data Flows

Trace how data moves between sources:

```
Client Invoice (PDF in email)
    → Manual download
    → Manual entry into QuickBooks
    → Manual copy to project budget Excel
    → Manual reconciliation at month-end
```

Each arrow is a **manual touch point** — a candidate for automation.

### Step 3: Identify Silos

A data silo is a source that:
- Contains data no other system has access to
- Requires manual export/import to share data
- Has no API or integration path
- Is owned by one person who "just knows how it works"

### Step 4: Score and Prioritize

```python
class AuditReport:
    def __init__(self, sources: List[DataSource], flows: List[DataFlow]):
        self.sources = sources
        self.flows = flows

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
                    "suggested_skill": self._suggest_skill(flow)
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
```

## Output

The audit produces:
1. **Data Inventory** — Complete list of all financial data sources
2. **Flow Map** — How data moves (or doesn't) between sources
3. **Silo Report** — Which sources are isolated
4. **Automation Priorities** — Ranked list of manual flows to automate first

## Real-World Example

**Company audit findings:**
- QuickBooks (structured, API available) — owned by bookkeeper
- Project budget Excel (structured, no integration) — owned by PM, silo
- Invoice PDFs in email (unstructured, no automation) — owned by AP clerk
- Bank statements (semi-structured, bank API available) — owned by CFO
- Subcontractor contracts in Dropbox (unstructured) — owned by project admin

**Top automation opportunity:** Invoice PDFs → QuickBooks entry (manual, daily, error-prone, 3 manual steps)
→ **Suggested skill:** `invoice-reconciliation` with OCR integration
