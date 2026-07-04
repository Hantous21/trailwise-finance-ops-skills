"""
Payment Application Generator (AIA G702/G703)

Generates AIA-style payment applications from a project schedule of values.
Calculates percent complete, retainage, previous payments, and current
amount due. Produces both the G702 (summary) and G703 (continuation sheet)
data structures.

Usage:
    from payment_app import (
        PayAppStatus, ScheduleOfValuesLine, ChangeOrder,
        PaymentApplication, G702Generator, PaymentAppHistory,
    )

This module is reference material for the `payment-app-generator` skill.
See SKILL.md for workflow, controls, and edge cases.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class PayAppStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


@dataclass
class ScheduleOfValuesLine:
    """G703 line item -- one row of the schedule of values."""

    line_no: int
    description: str                    # "03300 - Cast-in-Place Concrete"
    scheduled_value: float              # Original contracted value for this line
    scheduled_value_co: float = 0       # Approved change orders affecting this line
    previous_completed: float = 0       # Completed in prior pay apps
    current_completed: float = 0        # Completed this period
    stored_materials: float = 0          # Materials on site, not yet installed
    retainage_pct: float = 10.0          # % held back (default 10%)

    @property
    def total_scheduled(self) -> float:
        return self.scheduled_value + self.scheduled_value_co

    @property
    def total_completed(self) -> float:
        return self.previous_completed + self.current_completed

    @property
    def completed_pct(self) -> float:
        if self.total_scheduled == 0:
            return 0
        return round((self.total_completed / self.total_scheduled) * 100, 2)

    @property
    def retainage_held(self) -> float:
        return (self.total_completed + self.stored_materials) * (self.retainage_pct / 100)

    @property
    def less_retainage(self) -> float:
        return (self.total_completed + self.stored_materials) - self.retainage_held

    @property
    def less_previous(self) -> float:
        """Amount due this period for this line (before retainage adjustment)."""
        return self.less_retainage - (self.previous_completed * (1 - self.retainage_pct / 100))

    def to_g703_row(self) -> Dict:
        """Export as G703 continuation sheet row."""
        return {
            "line": self.line_no,
            "description": self.description,
            "scheduled_value": round(self.scheduled_value, 2),
            "change_orders": round(self.scheduled_value_co, 2),
            "total_scheduled": round(self.total_scheduled, 2),
            "previous_completed": round(self.previous_completed, 2),
            "current_completed": round(self.current_completed, 2),
            "total_completed": round(self.total_completed, 2),
            "stored_materials": round(self.stored_materials, 2),
            "total_completed_stored": round(self.total_completed + self.stored_materials, 2),
            "retainage_pct": self.retainage_pct,
            "retainage_held": round(self.retainage_held, 2),
            "less_retainage": round(self.less_retainage, 2),
            "completed_pct": self.completed_pct,
        }


@dataclass
class ChangeOrder:
    co_number: str
    description: str
    amount: float                      # Positive = addition, negative = deduction
    approved: bool = True
    approved_date: Optional[date] = None


@dataclass
class PaymentApplication:
    """AIA G702/G703 payment application."""

    app_number: int                     # 1 = first pay app, 2 = second, etc.
    project_name: str
    contractor: str
    owner: str
    architect: str                      # Architect/engineer (often the reviewer)
    contract_date: date
    period_to: date                     # Billing period end date
    original_contract_sum: float
    lines: List[ScheduleOfValuesLine] = field(default_factory=list)
    change_orders: List[ChangeOrder] = field(default_factory=list)
    status: PayAppStatus = PayAppStatus.DRAFT
    retainage_pct: float = 10.0         # Default retainage if not per-line

    @property
    def approved_co_total(self) -> float:
        return sum(co.amount for co in self.change_orders if co.approved)

    @property
    def contract_sum_to_date(self) -> float:
        """Original contract + approved change orders."""
        return self.original_contract_sum + self.approved_co_total

    @property
    def total_completed_stored(self) -> float:
        """Sum of all completed work + stored materials."""
        return sum(l.total_completed + l.stored_materials for l in self.lines)

    @property
    def total_retainage(self) -> float:
        return sum(l.retainage_held for l in self.lines)

    @property
    def total_earnings_less_retainage(self) -> float:
        return self.total_completed_stored - self.total_retainage

    @property
    def previous_payments(self) -> float:
        """Sum of all previous pay app amounts (less retainage)."""
        if self.app_number <= 1:
            return 0
        return sum(l.previous_completed for l in self.lines) * (1 - self.retainage_pct / 100)

    @property
    def current_amount_due(self) -> float:
        """The number the owner writes a check for."""
        return self.total_earnings_less_retainage - self.previous_payments

    @property
    def balance_to_finish(self) -> float:
        """Remaining contract value including retainage."""
        return self.contract_sum_to_date - self.total_completed_stored

    @property
    def percent_complete(self) -> float:
        if self.contract_sum_to_date == 0:
            return 0
        return round((self.total_completed_stored / self.contract_sum_to_date) * 100, 2)


class G702Generator:
    """Generate AIA G702 summary sheet from payment application data."""

    def generate(self, app: PaymentApplication) -> Dict:
        """Produce G702 summary data."""
        return {
            "application_number": app.app_number,
            "period_to": app.period_to.isoformat(),
            "project": app.project_name,
            "contractor": app.contractor,
            "owner": app.owner,
            "architect": app.architect,
            "contract_date": app.contract_date.isoformat(),

            # G702 line items
            "original_contract_sum": round(app.original_contract_sum, 2),
            "net_change_orders": round(app.approved_co_total, 2),
            "contract_sum_to_date": round(app.contract_sum_to_date, 2),

            "total_completed_stored": round(app.total_completed_stored, 2),
            "retainage": round(app.total_retainage, 2),
            "total_earnings_less_retainage": round(app.total_earnings_less_retainage, 2),
            "less_previous_payments": round(app.previous_payments, 2),
            "current_amount_due": round(app.current_amount_due, 2),
            "balance_to_finish": round(app.balance_to_finish, 2),

            "percent_complete": app.percent_complete,

            # Change order summary
            "change_orders": [
                {
                    "co_number": co.co_number,
                    "description": co.description,
                    "amount": round(co.amount, 2),
                    "approved": co.approved,
                }
                for co in app.change_orders if co.approved
            ],
        }

    def generate_g703(self, app: PaymentApplication) -> List[Dict]:
        """Produce G703 continuation sheet (line items)."""
        rows = [line.to_g703_row() for line in app.lines]

        # Add totals row
        totals = {
            "line": "TOTAL",
            "description": "TOTAL CONTRACT",
            "scheduled_value": round(sum(l.scheduled_value for l in app.lines), 2),
            "change_orders": round(sum(l.scheduled_value_co for l in app.lines), 2),
            "total_scheduled": round(sum(l.total_scheduled for l in app.lines), 2),
            "previous_completed": round(sum(l.previous_completed for l in app.lines), 2),
            "current_completed": round(sum(l.current_completed for l in app.lines), 2),
            "total_completed": round(sum(l.total_completed for l in app.lines), 2),
            "stored_materials": round(sum(l.stored_materials for l in app.lines), 2),
            "total_completed_stored": round(app.total_completed_stored, 2),
            "retainage_pct": app.retainage_pct,
            "retainage_held": round(app.total_retainage, 2),
            "less_retainage": round(app.total_earnings_less_retainage, 2),
            "completed_pct": app.percent_complete,
        }
        rows.append(totals)
        return rows


class PaymentAppHistory:
    """Track pay apps across a project lifecycle."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.apps: List[PaymentApplication] = []

    def add_app(self, app: PaymentApplication):
        self.apps.append(app)
        self.apps.sort(key=lambda a: a.app_number)

    def get_latest(self) -> Optional[PaymentApplication]:
        return self.apps[-1] if self.apps else None

    def get_app(self, app_number: int) -> Optional[PaymentApplication]:
        for app in self.apps:
            if app.app_number == app_number:
                return app
        return None

    def get_project_summary(self) -> Dict:
        latest = self.get_latest()
        if not latest:
            return {"error": "No payment applications"}

        return {
            "project": self.project_name,
            "total_apps_submitted": len(self.apps),
            "original_contract": latest.original_contract_sum,
            "contract_to_date": latest.contract_sum_to_date,
            "total_billed_to_date": latest.total_earnings_less_retainage,
            "total_paid_to_date": latest.previous_payments + latest.current_amount_due,
            "retainage_held": latest.total_retainage,
            "balance_to_finish": latest.balance_to_finish,
            "percent_complete": latest.percent_complete,
            "apps": [
                {
                    "app_number": a.app_number,
                    "period_to": a.period_to.isoformat(),
                    "amount_due": round(a.current_amount_due, 2),
                    "status": a.status.value,
                }
                for a in self.apps
            ],
        }

    def create_next_app(
        self,
        lines: List[ScheduleOfValuesLine],
        period_to: date,
        current_completed: Dict[int, float],
        change_orders: Optional[List[ChangeOrder]] = None,
    ) -> PaymentApplication:
        """Create the next pay app, carrying forward previous totals."""
        latest = self.get_latest()
        app_number = (latest.app_number + 1) if latest else 1

        # Update lines with previous completed amounts
        for line in lines:
            if latest:
                prev_line = next(
                    (l for l in latest.lines if l.line_no == line.line_no), None
                )
                if prev_line:
                    line.previous_completed = prev_line.total_completed
            # Set current period completed
            line.current_completed = current_completed.get(line.line_no, 0)

        # Get contract info from latest or create new
        if latest:
            app = PaymentApplication(
                app_number=app_number,
                project_name=latest.project_name,
                contractor=latest.contractor,
                owner=latest.owner,
                architect=latest.architect,
                contract_date=latest.contract_date,
                period_to=period_to,
                original_contract_sum=latest.original_contract_sum,
                lines=lines,
                change_orders=change_orders or latest.change_orders,
                retainage_pct=latest.retainage_pct,
            )
        else:
            # First pay app -- need full contract info from caller
            raise ValueError(
                "No previous pay app found. Create first app with full contract data."
            )

        return app
