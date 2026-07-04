"""Change order tracker — classify, cost, and track construction change orders.

Extracted from the change-order-tracker SKILL.md.  Provides data classes for
change orders, a ``ChangeOrderManager`` engine that classifies CO type from
description, scores severity, computes cumulative impact on the contract sum,
and generates dispute documentation packets.  A small CSV-driven CLI emits a
cumulative-impact + dispute JSON blob.

Usage::

    from change_order_tracker import ChangeOrderManager, ChangeOrder, COType
    manager = ChangeOrderManager(contract_sum=500000)
    manager.load_csv("change_orders.csv")
    report = manager.cumulative_impact()
    print(report)

CLI::

    python3 scripts/change_order_tracker.py \\
        --contract-sum 500000 \\
        --csv change_orders.csv
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class COType(Enum):
    DESIGN_CHANGE = "design_change"
    OWNER_REQUEST = "owner_request"
    FIELD_CONDITION = "field_condition"
    CODE_COMPLIANCE = "code_compliance"
    VALUE_ENGINEERING = "value_engineering"
    ERROR_OMISSION = "error_omission"
    SCOPE_CHANGE = "scope_change"


class COStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class Severity(Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CostBreakdown:
    labor: float = 0
    materials: float = 0
    equipment: float = 0
    subcontractor: float = 0
    overhead: float = 0
    profit: float = 0

    @property
    def total(self) -> float:
        return (self.labor + self.materials + self.equipment
                + self.subcontractor + self.overhead + self.profit)


@dataclass
class ScheduleImpact:
    direct_days: int = 0
    ripple_days: int = 0
    critical_path_affected: bool = False
    affected_activities: List[str] = field(default_factory=list)

    @property
    def total_days(self) -> int:
        return self.direct_days + self.ripple_days


@dataclass
class ChangeOrder:
    id: str
    project_id: str
    title: str
    description: str
    co_type: COType
    initiated_by: str
    responsibility: str  # owner, contractor, shared
    status: COStatus
    submitted_date: str  # ISO date
    approved_date: Optional[str] = None
    implemented_date: Optional[str] = None
    cost_breakdown: CostBreakdown = field(default_factory=CostBreakdown)
    schedule_impact: ScheduleImpact = field(default_factory=ScheduleImpact)
    affected_cost_codes: List[str] = field(default_factory=list)
    supporting_docs: List[str] = field(default_factory=list)
    approvals: List[dict] = field(default_factory=list)
    severity: Optional[Severity] = None  # assigned by manager.score_severity

    @property
    def total_cost(self) -> float:
        return self.cost_breakdown.total


# ---------------------------------------------------------------------------
# Classification — keyword-based mapping (deterministic, testable)
# ---------------------------------------------------------------------------

CLASSIFICATION_KEYWORDS: List[tuple] = [
    (["design", "drawing", "specification", "revision"], COType.DESIGN_CHANGE),
    (["owner", "client", "request", "want", "need"], COType.OWNER_REQUEST),
    (["site", "field", "condition", "unforeseen", "soil", "weather"], COType.FIELD_CONDITION),
    (["code", "regulation", "compliance", "ahj", "inspector"], COType.CODE_COMPLIANCE),
    (["value", "alternative", "savings", "ve", "optimize"], COType.VALUE_ENGINEERING),
    (["error", "omission", "mistake", "missing", "forgot"], COType.ERROR_OMISSION),
]


def classify_description(description: str) -> COType:
    """Classify a CO type from its description using keyword matching.

    Returns ``COType.SCOPE_CHANGE`` when no keywords match (default).
    """
    text = description.lower()
    for keywords, co_type in CLASSIFICATION_KEYWORDS:
        if any(kw in text for kw in keywords):
            return co_type
    return COType.SCOPE_CHANGE


# ---------------------------------------------------------------------------
# Severity scoring — higher of cost-based or schedule-based
# ---------------------------------------------------------------------------

def _cost_severity(cost_pct: float) -> Severity:
    if cost_pct > 10:
        return Severity.CRITICAL
    if cost_pct > 5:
        return Severity.MAJOR
    if cost_pct >= 1:
        return Severity.MODERATE
    return Severity.MINOR


def _schedule_severity(days: int) -> Severity:
    if days > 90:
        return Severity.CRITICAL
    if days > 30:
        return Severity.MAJOR
    if days >= 7:
        return Severity.MODERATE
    return Severity.MINOR


_SEVERITY_RANK = {
    Severity.MINOR: 0,
    Severity.MODERATE: 1,
    Severity.MAJOR: 2,
    Severity.CRITICAL: 3,
}


def score_severity(co: ChangeOrder, contract_sum: float) -> Severity:
    """Score severity as the higher of cost-based or schedule-based.

    Edge cases:
      * Negative CO (deduction) — severity is MINOR regardless of magnitude.
      * CO with zero cost and zero schedule — MINOR by default.
    """
    if co.total_cost < 0:
        return Severity.MINOR

    if co.total_cost == 0 and co.schedule_impact.total_days == 0:
        return Severity.MINOR

    cost_pct = (co.total_cost / contract_sum * 100) if contract_sum > 0 else 0
    cost_sev = _cost_severity(cost_pct)
    sched_sev = _schedule_severity(co.schedule_impact.total_days)

    return cost_sev if _SEVERITY_RANK[cost_sev] >= _SEVERITY_RANK[sched_sev] else sched_sev


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ChangeOrderManager:
    """Classify, cost, and track change orders against a contract sum."""

    def __init__(self, contract_sum: float):
        self.contract_sum = contract_sum
        self.orders: Dict[str, ChangeOrder] = {}

    # -- loading -----------------------------------------------------------

    def add_change_order(self, co: ChangeOrder) -> None:
        if co.id in self.orders:
            raise ValueError(f"Duplicate CO number: {co.id}")
        if co.co_type is None:
            co.co_type = classify_description(co.description)
        co.severity = score_severity(co, self.contract_sum)
        self.orders[co.id] = co

    def load_csv(self, csv_path: str) -> None:
        """Load change orders from CSV.

        Expected columns: id,project_id,title,description,initiated_by,
        responsibility,status,submitted_date,approved_date,labor,materials,
        equipment,subcontractor,overhead,profit,direct_days,ripple_days,
        critical_path_affected,affected_cost_codes
        """
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                co_type = classify_description(row["description"])
                status = COStatus(row["status"])
                cost = CostBreakdown(
                    labor=float(row.get("labor") or 0),
                    materials=float(row.get("materials") or 0),
                    equipment=float(row.get("equipment") or 0),
                    subcontractor=float(row.get("subcontractor") or 0),
                    overhead=float(row.get("overhead") or 0),
                    profit=float(row.get("profit") or 0),
                )
                sched = ScheduleImpact(
                    direct_days=int(row.get("direct_days") or 0),
                    ripple_days=int(row.get("ripple_days") or 0),
                    critical_path_affected=(row.get("critical_path_affected", "false").lower() == "true"),
                )
                codes = [c.strip() for c in (row.get("affected_cost_codes") or "").split(",") if c.strip()]
                co = ChangeOrder(
                    id=row["id"],
                    project_id=row["project_id"],
                    title=row["title"],
                    description=row["description"],
                    co_type=co_type,
                    initiated_by=row["initiated_by"],
                    responsibility=row["responsibility"],
                    status=status,
                    submitted_date=row["submitted_date"],
                    approved_date=row.get("approved_date") or None,
                    implemented_date=row.get("implemented_date") or None,
                    cost_breakdown=cost,
                    schedule_impact=sched,
                    affected_cost_codes=codes,
                )
                self.add_change_order(co)

    # -- reports -----------------------------------------------------------

    def cumulative_impact(self) -> Dict:
        """Compute cumulative approved + pending CO totals vs original contract."""
        approved = [co for co in self.orders.values() if co.status in (COStatus.APPROVED, COStatus.IMPLEMENTED)]
        pending = [co for co in self.orders.values()
                   if co.status in (COStatus.SUBMITTED, COStatus.UNDER_REVIEW, COStatus.DRAFT)]

        approved_total = sum(co.total_cost for co in approved)
        pending_total = sum(co.total_cost for co in pending)
        current_contract_sum = self.contract_sum + approved_total

        cost_over = approved_total > self.contract_sum * 0.10  # >10% of contract
        schedule_total = sum(co.schedule_impact.total_days for co in approved)

        critical = [co for co in approved if co.severity == Severity.CRITICAL]
        major = [co for co in approved if co.severity == Severity.MAJOR]

        return {
            "original_contract_sum": self.contract_sum,
            "approved_co_count": len(approved),
            "approved_co_total": round(approved_total, 2),
            "pending_co_count": len(pending),
            "pending_co_total": round(pending_total, 2),
            "current_contract_sum": round(current_contract_sum, 2),
            "pct_change": round((approved_total / self.contract_sum) * 100, 2) if self.contract_sum else 0,
            "schedule_days_added": schedule_total,
            "critical_path_affected": any(co.schedule_impact.critical_path_affected for co in approved),
            "cost_over_10pct_threshold": cost_over,
            "critical_severity_count": len(critical),
            "major_severity_count": len(major),
            "critical_co_ids": [co.id for co in critical],
            "major_co_ids": [co.id for co in major],
        }

    def generate_dispute_packet(self, co_id: str) -> str:
        """Generate a markdown dispute documentation packet for a CO.

        Dispute packets are drafts — a human reviews before sending to client
        or attorney.
        """
        co = self.orders.get(co_id)
        if not co:
            return f"ERROR: CO {co_id} not found."

        cb = co.cost_breakdown
        si = co.schedule_impact
        sev = co.severity.value if co.severity else "unknown"

        lines = [
            "# Change Order Dispute Packet",
            "",
            f"**{co.id} — {co.title}**",
            f"- Type: {co.co_type.value}",
            f"- Status: {co.status.value}",
            f"- Submitted: {co.submitted_date}",
            f"- Approved: {co.approved_date or 'N/A'}",
            f"- Total Cost: ${co.total_cost:,.2f}",
            f"- Schedule Impact: {si.total_days} days",
            f"- Severity: {sev}",
            "",
            "## Cost Breakdown",
            "| Item | Amount |",
            "|------|--------|",
            f"| Labor | ${cb.labor:,.2f} |",
            f"| Materials | ${cb.materials:,.2f} |",
            f"| Equipment | ${cb.equipment:,.2f} |",
            f"| Subcontractor | ${cb.subcontractor:,.2f} |",
            f"| Overhead | ${cb.overhead:,.2f} |",
            f"| Profit | ${cb.profit:,.2f} |",
            f"| **Total** | **${cb.total:,.2f}** |",
            "",
            "## Approval Trail",
            "| Approver | Action | Date | Comments |",
            "|----------|--------|------|----------|",
        ]
        if co.approvals:
            for a in co.approvals:
                lines.append(
                    f"| {a.get('approver','')} | {a.get('action','')} | "
                    f"{a.get('date','')} | {a.get('comments','')} |"
                )
        else:
            lines.append("| (no approvals recorded) | | | |")

        lines += [
            "",
            "## Evidence",
        ]
        if co.supporting_docs:
            for doc in co.supporting_docs:
                lines.append(f"- {doc}")
        else:
            lines.append("- (no supporting documents attached)")
        lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Change order tracker")
    parser.add_argument("--contract-sum", type=float, required=True,
                        help="Original contract sum")
    parser.add_argument("--csv", required=True, help="Path to change orders CSV")
    parser.add_argument("--dispute", default=None,
                        help="CO id to generate a dispute packet for")
    args = parser.parse_args(argv)

    manager = ChangeOrderManager(contract_sum=args.contract_sum)
    manager.load_csv(args.csv)

    output: Dict
    if args.dispute:
        output = {
            "dispute_packet": manager.generate_dispute_packet(args.dispute),
        }
    else:
        output = manager.cumulative_impact()
        output["orders"] = [
            {
                "id": co.id,
                "title": co.title,
                "type": co.co_type.value,
                "status": co.status.value,
                "total_cost": co.total_cost,
                "severity": co.severity.value if co.severity else None,
            }
            for co in manager.orders.values()
        ]

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
