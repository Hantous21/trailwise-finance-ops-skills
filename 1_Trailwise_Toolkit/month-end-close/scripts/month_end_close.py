"""Month-end close checklist, accrual, variance, and roll-forward controls.

This module extracts the inline reference implementation that previously lived in
SKILL.md. It is intentionally dependency-free (stdlib only) so the close process
can be exercised without pandas/openpyxl.

Public API:
    CloseTaskStatus, TaskCategory, CloseTask, ClosePeriod, AccrualEntry,
    VarianceItem, MonthEndCloseManager, AccrualGenerator, VarianceAnalyzer,
    RollForwardManager
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class CloseTaskStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    OVERDUE = "overdue"


class TaskCategory(Enum):
    RECONCILIATION = "reconciliation"
    ACCRUALS = "accruals"
    VARIANCE = "variance"
    ROLL_FORWARD = "roll_forward"
    REPORTING = "reporting"
    REVIEW = "review"


@dataclass
class CloseTask:
    id: str
    name: str
    category: TaskCategory
    owner: str
    due_day: int  # Business day of month (e.g., 3 = 3rd business day)
    status: CloseTaskStatus = CloseTaskStatus.NOT_STARTED
    completed_at: Optional[date] = None
    completed_by: Optional[str] = None
    notes: str = ""
    dependencies: List[str] = field(default_factory=list)  # Task IDs that must complete first


@dataclass
class ClosePeriod:
    period: str  # "2026-06"
    start_date: date
    end_date: date
    tasks: List[CloseTask] = field(default_factory=list)
    is_closed: bool = False
    closed_at: Optional[date] = None


@dataclass
class AccrualEntry:
    account: str
    description: str
    debit: float = 0
    credit: float = 0
    is_reversing: bool = True  # Will be reversed next period
    based_on: str = ""  # What data drove this estimate


@dataclass
class VarianceItem:
    account: str
    description: str
    actual: float
    budget: float
    prior_month: float
    variance_vs_budget: float
    variance_vs_prior: float
    variance_pct: float
    is_material: bool
    explanation: str = ""


class MonthEndCloseManager:
    """Manage the recurring month-end close process."""

    DEFAULT_TASKS = [
        # Reconciliations
        ("Bank reconciliation - Operating", TaskCategory.RECONCILIATION, "Bookkeeper", 2, []),
        ("Bank reconciliation - Payroll", TaskCategory.RECONCILIATION, "Bookkeeper", 2, []),
        ("Credit card reconciliation", TaskCategory.RECONCILIATION, "Bookkeeper", 3, []),
        ("AP aging reconciliation", TaskCategory.RECONCILIATION, "AP Clerk", 3, []),
        ("AR aging reconciliation", TaskCategory.RECONCILIATION, "AR Clerk", 3, []),
        ("Inventory reconciliation", TaskCategory.RECONCILIATION, "Warehouse", 4, []),
        ("Fixed asset reconciliation", TaskCategory.RECONCILIATION, "Accountant", 4, []),

        # Accruals
        ("Accrue unpaid invoices", TaskCategory.ACCRUALS, "Accountant", 3, ["Bank reconciliation - Operating"]),
        ("Accrue payroll & benefits", TaskCategory.ACCRUALS, "Accountant", 3, ["Bank reconciliation - Payroll"]),
        ("Accrue utilities & subscriptions", TaskCategory.ACCRUALS, "Accountant", 4, []),
        ("Accrue project costs (WIP)", TaskCategory.ACCRUALS, "Project Accountant", 4, ["Inventory reconciliation"]),

        # Variance analysis
        ("Budget vs actual variance", TaskCategory.VARIANCE, "Controller", 4, ["Accrue unpaid invoices", "Accrue payroll & benefits"]),
        ("Prior month comparison", TaskCategory.VARIANCE, "Controller", 4, []),
        ("Explain material variances", TaskCategory.VARIANCE, "Controller", 5, ["Budget vs actual variance"]),

        # Roll-forwards
        ("Update prepaid amortization", TaskCategory.ROLL_FORWARD, "Accountant", 4, []),
        ("Update fixed asset depreciation", TaskCategory.ROLL_FORWARD, "Accountant", 4, []),
        ("Update AR allowance for doubtful accounts", TaskCategory.ROLL_FORWARD, "Accountant", 5, ["AR aging reconciliation"]),
        ("Update WIP schedule", TaskCategory.ROLL_FORWARD, "Project Accountant", 5, ["Accrue project costs (WIP)"]),

        # Reporting
        ("Generate financial statements", TaskCategory.REPORTING, "Controller", 5, ["Update prepaid amortization", "Update fixed asset depreciation"]),
        ("Generate project profitability report", TaskCategory.REPORTING, "Project Accountant", 5, []),
        ("Generate cash flow statement", TaskCategory.REPORTING, "Controller", 6, ["Generate financial statements"]),

        # Review & sign-off
        ("Controller review & sign-off", TaskCategory.REVIEW, "Controller", 6, ["Generate financial statements", "Explain material variances"]),
        ("CFO/Owner review & close", TaskCategory.REVIEW, "CFO", 7, ["Controller review & sign-off"]),
    ]

    def __init__(self):
        self.tasks: Dict[str, CloseTask] = {}

    def generate_checklist(self, period: str, start_date: date,
                           end_date: date) -> ClosePeriod:
        """Generate a close checklist for a new period."""
        period_obj = ClosePeriod(period=period, start_date=start_date, end_date=end_date)

        for i, (name, category, owner, due_day, deps) in enumerate(self.DEFAULT_TASKS):
            task = CloseTask(
                id=f"{period}-T{i+1:02d}",
                name=name,
                category=category,
                owner=owner,
                due_day=due_day,
                dependencies=[f"{period}-T{j+1:02d}" for j, _ in enumerate(self.DEFAULT_TASKS) if self.DEFAULT_TASKS[j][0] in deps],
            )
            self.tasks[task.id] = task
            period_obj.tasks.append(task)

        return period_obj

    def update_task_status(self, task_id: str, status: CloseTaskStatus,
                           completed_by: str = "", notes: str = ""):
        """Update a task's status and log completion."""
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            if status == CloseTaskStatus.APPROVED:
                task.completed_at = date.today()
                task.completed_by = completed_by
            task.notes = notes

    def check_overdue(self, current_business_day: int):
        """Mark tasks as overdue if past due day."""
        for task in self.tasks.values():
            if task.status not in (CloseTaskStatus.APPROVED,):
                if task.due_day < current_business_day:
                    task.status = CloseTaskStatus.OVERDUE

    def get_progress(self, period: str) -> Dict:
        """Get close progress dashboard."""
        period_tasks = [t for t in self.tasks.values() if t.id.startswith(period)]
        total = len(period_tasks)
        completed = sum(1 for t in period_tasks if t.status == CloseTaskStatus.APPROVED)
        in_progress = sum(1 for t in period_tasks if t.status in (CloseTaskStatus.IN_PROGRESS, CloseTaskStatus.READY_FOR_REVIEW))
        not_started = sum(1 for t in period_tasks if t.status == CloseTaskStatus.NOT_STARTED)
        overdue = sum(1 for t in period_tasks if t.status == CloseTaskStatus.OVERDUE)

        return {
            "period": period,
            "total_tasks": total,
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
            "overdue": overdue,
            "pct_complete": round(completed / total * 100, 1) if total else 0,
            "next_tasks": [
                {"name": t.name, "owner": t.owner, "due_day": t.due_day}
                for t in period_tasks
                if t.status == CloseTaskStatus.NOT_STARTED
                and all(self.tasks.get(dep, CloseTask(status=CloseTaskStatus.APPROVED)).status == CloseTaskStatus.APPROVED
                        for dep in t.dependencies)
            ][:5]
        }


class AccrualGenerator:
    """Suggest accrual entries based on historical patterns."""

    def __init__(self, materiality_threshold: float = 500.0):
        self.threshold = materiality_threshold

    def suggest_accruals(self, period: str, historical_data: Dict) -> List[AccrualEntry]:
        """Generate suggested accrual entries from prior 3-month averages."""
        entries = []

        # Unpaid invoices (from AP aging)
        unpaid = historical_data.get("unpaid_invoices", [])
        total_unpaid = sum(i["amount"] for i in unpaid if i.get("received_not_invoiced"))
        if total_unpaid > self.threshold:
            entries.append(AccrualEntry(
                account="Expense (various)",
                description=f"Accrue goods received not invoiced - {period}",
                debit=total_unpaid,
                credit=0,
                based_on=f"{len(unpaid)} unmatched receipts totaling ${total_unpaid:,.2f}"
            ))
            entries.append(AccrualEntry(
                account="Accounts Payable (accrued)",
                description=f"Offsetting credit for GRNI accrual - {period}",
                debit=0,
                credit=total_unpaid,
                based_on="Matching credit for above debit"
            ))

        # Payroll accrual (days worked but not yet paid)
        payroll_days = historical_data.get("unpaid_payroll_days", 0)
        daily_payroll = historical_data.get("daily_payroll_cost", 0)
        payroll_accrual = payroll_days * daily_payroll
        if payroll_accrual > self.threshold:
            entries.append(AccrualEntry(
                account="Payroll Expense",
                description=f"Accrue payroll for {payroll_days} unpaid days - {period}",
                debit=payroll_accrual,
                credit=0,
                based_on=f"{payroll_days} days × ${daily_payroll:,.2f}/day"
            ))
            entries.append(AccrualEntry(
                account="Accrued Payroll",
                description=f"Offsetting credit for payroll accrual - {period}",
                debit=0,
                credit=payroll_accrual,
                based_on="Matching credit"
            ))

        # Utilities (average of prior 3 months)
        utilities_avg = historical_data.get("utilities_3mo_avg", 0)
        if utilities_avg > self.threshold:
            entries.append(AccrualEntry(
                account="Utilities Expense",
                description=f"Accrue utilities (3-mo average) - {period}",
                debit=utilities_avg,
                credit=0,
                based_on=f"3-month average: ${utilities_avg:,.2f}"
            ))
            entries.append(AccrualEntry(
                account="Accrued Expenses",
                description=f"Offsetting credit for utilities accrual - {period}",
                debit=0,
                credit=utilities_avg,
                based_on="3-month average estimate"
            ))

        return entries


class VarianceAnalyzer:
    """Analyze actual vs budget vs prior month with materiality filtering."""

    def __init__(self, materiality_pct: float = 5.0, materiality_amount: float = 1000.0):
        self.materiality_pct = materiality_pct
        self.materiality_amount = materiality_amount

    def analyze(self, accounts: List[Dict]) -> List[VarianceItem]:
        """Run variance analysis on account-level data."""
        results = []

        for acct in accounts:
            actual = acct.get("actual", 0)
            budget = acct.get("budget", 0)
            prior = acct.get("prior_month", 0)

            var_budget = actual - budget
            var_prior = actual - prior

            var_pct = (var_budget / budget * 100) if budget else 0

            is_material = (
                abs(var_pct) >= self.materiality_pct or
                abs(var_budget) >= self.materiality_amount
            )

            results.append(VarianceItem(
                account=acct["account"],
                description=acct.get("description", ""),
                actual=actual,
                budget=budget,
                prior_month=prior,
                variance_vs_budget=var_budget,
                variance_vs_prior=var_prior,
                variance_pct=round(var_pct, 1),
                is_material=is_material,
                explanation=""  # Filled in by controller
            ))

        # Sort: material first, then by absolute variance descending
        results.sort(key=lambda x: (not x.is_material, -abs(x.variance_vs_budget)))
        return results

    def generate_explanation_template(self, item: VarianceItem) -> str:
        """Generate a template explanation for a material variance."""
        direction = "favorable" if item.variance_vs_budget > 0 else "unfavorable"
        return (
            f"Variance: ${item.variance_vs_budget:,.2f} ({item.variance_pct}%) {direction}. "
            f"Actual ${item.actual:,.2f} vs Budget ${item.budget:,.2f}. "
            f"Prior month was ${item.prior_month:,.2f}. "
            f"Explanation: [INSERT REASON]"
        )


class RollForwardManager:
    """Update recurring roll-forward schedules."""

    def update_prepaid_amortization(self, prepaid_schedule: List[Dict],
                                     current_period: str) -> List[Dict]:
        """Amortize one month of prepaids."""
        results = []
        for item in prepaid_schedule:
            monthly_amort = item["total_amount"] / item["amortization_months"]
            new_balance = item["remaining_balance"] - monthly_amort

            results.append({
                "account": item["account"],
                "description": item["description"],
                "monthly_amortization": round(monthly_amort, 2),
                "previous_balance": item["remaining_balance"],
                "new_balance": round(max(new_balance, 0), 2),
                "period": current_period,
                "months_remaining": max(item.get("months_remaining", 0) - 1, 0),
            })

        return results

    def update_ar_allowance(self, aging_buckets: Dict[str, float],
                            allowance_rates: Dict[str, float] = None) -> Dict:
        """Calculate AR allowance based on aging buckets."""
        rates = allowance_rates or {
            "current": 0.005,      # 0.5%
            "1_30": 0.02,          # 2%
            "31_60": 0.05,         # 5%
            "61_90": 0.10,         # 10%
            "90_plus": 0.25,       # 25%
        }

        required_allowance = 0
        breakdown = {}

        for bucket, rate in rates.items():
            balance = aging_buckets.get(bucket, 0)
            allowance = balance * rate
            breakdown[bucket] = {
                "balance": balance,
                "rate": rate,
                "allowance": round(allowance, 2)
            }
            required_allowance += allowance

        return {
            "total_required_allowance": round(required_allowance, 2),
            "breakdown": breakdown,
            "current_allowance": aging_buckets.get("current_allowance", 0),
            "adjustment_needed": round(required_allowance - aging_buckets.get("current_allowance", 0), 2)
        }


__all__ = [
    "CloseTaskStatus",
    "TaskCategory",
    "CloseTask",
    "ClosePeriod",
    "AccrualEntry",
    "VarianceItem",
    "MonthEndCloseManager",
    "AccrualGenerator",
    "VarianceAnalyzer",
    "RollForwardManager",
]
