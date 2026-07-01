"""Deterministic RFI aging and priority classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class RFIStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"
    VOID = "void"


@dataclass(frozen=True)
class RFI:
    number: str
    subject: str
    submitted_on: date
    required_by: date
    status: RFIStatus = RFIStatus.OPEN
    estimated_cost_impact: Decimal | None = None
    estimated_schedule_days: int | None = None
    answered_on: date | None = None

    def __post_init__(self) -> None:
        if not self.number.strip() or not self.subject.strip():
            raise ValueError("RFI number and subject are required")
        if self.required_by < self.submitted_on:
            raise ValueError("required_by cannot precede submitted_on")
        if self.estimated_cost_impact is not None:
            value = Decimal(str(self.estimated_cost_impact))
            if not value.is_finite():
                raise ValueError("estimated cost impact must be finite")
            object.__setattr__(self, "estimated_cost_impact", value)
        if self.estimated_schedule_days is not None and self.estimated_schedule_days < 0:
            raise ValueError("estimated schedule impact cannot be negative")
        if self.status in {RFIStatus.ANSWERED, RFIStatus.CLOSED} and self.answered_on is None:
            raise ValueError("answered_on is required for answered or closed RFIs")
        if self.answered_on is not None and self.answered_on < self.submitted_on:
            raise ValueError("answered_on cannot precede submitted_on")


def triage(rfi: RFI, as_of: date) -> dict[str, object]:
    """Classify one RFI without sending notices or modifying its status."""
    if as_of < rfi.submitted_on:
        raise ValueError("as_of cannot precede submitted_on")
    terminal = rfi.status in {RFIStatus.ANSWERED, RFIStatus.CLOSED, RFIStatus.VOID}
    age_days = ((rfi.answered_on or as_of) - rfi.submitted_on).days
    days_overdue = 0 if terminal else max((as_of - rfi.required_by).days, 0)
    due_in_days = None if terminal else (rfi.required_by - as_of).days
    unknown_impact = rfi.estimated_cost_impact is None or rfi.estimated_schedule_days is None

    if terminal:
        priority = "complete"
    elif days_overdue > 0 and ((rfi.estimated_schedule_days or 0) > 0 or (rfi.estimated_cost_impact or 0) > 0):
        priority = "critical"
    elif days_overdue > 0 or (due_in_days is not None and due_in_days <= 2):
        priority = "high"
    elif due_in_days is not None and due_in_days <= 7:
        priority = "medium"
    else:
        priority = "normal"

    reasons: list[str] = []
    if days_overdue:
        reasons.append("response_overdue")
    if unknown_impact and not terminal:
        reasons.append("impact_not_quantified")
    if (rfi.estimated_schedule_days or 0) > 0:
        reasons.append("schedule_impact_reported")
    if (rfi.estimated_cost_impact or 0) > 0:
        reasons.append("cost_impact_reported")
    return {
        "number": rfi.number,
        "status": rfi.status.value,
        "age_days": age_days,
        "days_overdue": days_overdue,
        "due_in_days": due_in_days,
        "priority": priority,
        "requires_review": not terminal and (priority in {"critical", "high"} or unknown_impact),
        "reasons": reasons,
    }


def portfolio(rfis: list[RFI], as_of: date) -> dict[str, object]:
    rows = [triage(rfi, as_of) for rfi in rfis]
    return {
        "as_of": as_of.isoformat(),
        "total": len(rows),
        "open": sum(row["status"] == RFIStatus.OPEN.value for row in rows),
        "overdue": sum(int(row["days_overdue"]) > 0 for row in rows),
        "critical": sum(row["priority"] == "critical" for row in rows),
        "rows": rows,
    }
