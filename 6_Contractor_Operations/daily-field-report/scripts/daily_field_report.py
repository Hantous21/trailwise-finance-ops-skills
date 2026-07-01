"""Deterministic, side-effect-free contractor daily report calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


def number(value: object) -> Decimal:
    parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    if not parsed.is_finite():
        raise ValueError("numeric values must be finite")
    return parsed


@dataclass(frozen=True)
class WorkEntry:
    trade: str
    workers: int
    hours_per_worker: Decimal
    description: str
    overtime_hours_per_worker: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        regular = number(self.hours_per_worker)
        overtime = number(self.overtime_hours_per_worker)
        object.__setattr__(self, "hours_per_worker", regular)
        object.__setattr__(self, "overtime_hours_per_worker", overtime)
        if not self.trade.strip() or not self.description.strip():
            raise ValueError("trade and description are required")
        if self.workers < 0 or regular < 0 or overtime < 0:
            raise ValueError("workers and hours cannot be negative")
        if regular + overtime > 24:
            raise ValueError("hours per worker cannot exceed 24 in one report day")

    @property
    def labor_hours(self) -> Decimal:
        return Decimal(self.workers) * (self.hours_per_worker + self.overtime_hours_per_worker)


@dataclass(frozen=True)
class DelayEvent:
    category: str
    description: str
    delay_hours: Decimal
    responsible_party: str = "unknown"

    def __post_init__(self) -> None:
        hours = number(self.delay_hours)
        object.__setattr__(self, "delay_hours", hours)
        if not self.category.strip() or not self.description.strip() or hours < 0:
            raise ValueError("delay category/description are required and hours cannot be negative")


@dataclass(frozen=True)
class SafetyEvent:
    description: str
    severity: str

    def __post_init__(self) -> None:
        allowed = {"observation", "first_aid", "recordable", "lost_time", "critical"}
        if not self.description.strip() or self.severity not in allowed:
            raise ValueError(f"severity must be one of {sorted(allowed)}")


@dataclass(frozen=True)
class DailyReport:
    project_id: str
    report_date: date
    prepared_by: str
    weather_observed: str
    work: tuple[WorkEntry, ...] = ()
    delays: tuple[DelayEvent, ...] = ()
    safety_events: tuple[SafetyEvent, ...] = ()
    visitors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.project_id.strip(), self.prepared_by.strip(), self.weather_observed.strip())):
            raise ValueError("project_id, prepared_by, and observed weather are required")


def summarize(report: DailyReport) -> dict[str, object]:
    """Return calculations and review flags without changing project records."""
    labor_hours = sum((entry.labor_hours for entry in report.work), Decimal("0"))
    delay_hours = sum((event.delay_hours for event in report.delays), Decimal("0"))
    unique_trades = sorted({entry.trade.strip() for entry in report.work})
    severe = [event for event in report.safety_events if event.severity in {"recordable", "lost_time", "critical"}]
    missing_responsibility = any(event.responsible_party.strip().casefold() == "unknown" for event in report.delays)
    review_reasons: list[str] = []
    if severe:
        review_reasons.append("recordable_or_more_severe_safety_event")
    if delay_hours > 0:
        review_reasons.append("delay_reported")
    if missing_responsibility:
        review_reasons.append("delay_responsibility_unconfirmed")
    if not report.work:
        review_reasons.append("no_work_entries")
    return {
        "project_id": report.project_id,
        "report_date": report.report_date.isoformat(),
        "prepared_by": report.prepared_by,
        "weather_observed": report.weather_observed,
        "trade_count": len(unique_trades),
        "workers_reported": sum(entry.workers for entry in report.work),
        "labor_hours": str(labor_hours),
        "delay_hours": str(delay_hours),
        "safety_event_count": len(report.safety_events),
        "requires_review": bool(review_reasons),
        "review_reasons": review_reasons,
        "work": [
            {
                "trade": entry.trade,
                "workers": entry.workers,
                "labor_hours": str(entry.labor_hours),
                "description": entry.description,
            }
            for entry in report.work
        ],
        "delays": [
            {
                "category": event.category,
                "description": event.description,
                "delay_hours": str(event.delay_hours),
                "responsible_party": event.responsible_party,
            }
            for event in report.delays
        ],
    }
