"""Budget variance tracker — compare budgeted costs to actual spending, forecast
final costs via burn-rate projection, and trigger threshold-based alerts.

Extracted from the budget-variance-tracker SKILL.md.  Provides data classes for
budget lines and alerts, a ``BudgetVarianceTracker`` engine with burn-rate
forecasting, and a small CSV-driven CLI that emits a summary+alerts JSON blob.

Usage::

    from budget_variance_tracker import BudgetVarianceTracker, BudgetLine
    tracker = BudgetVarianceTracker("Riverside Office Building", 185000)
    tracker.add_budget_line(BudgetLine(...))
    summary = tracker.get_summary()
    alerts  = tracker.check_alerts()

CLI::

    python3 scripts/budget_variance_tracker.py \\
        --project "Riverside Office Building" \\
        --csv fixtures/input/budget_lines.csv
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class AlertLevel(Enum):
    GREEN = "green"        # Under 50% of budget used, on track
    YELLOW = "yellow"     # 50-75% used, monitor
    ORANGE = "orange"     # 75-90% used, action recommended
    RED = "red"           # 90%+ used or forecast exceeds budget
    CRITICAL = "critical" # Over budget (forecast > 110% of budget)


@dataclass
class BudgetLine:
    cost_code: str            # e.g., "04000 - Concrete"
    category: str             # e.g., "Materials", "Labor", "Subcontract"
    description: str
    budgeted_amount: float
    spent_to_date: float
    committed: float          # POs/contracts signed but not yet invoiced
    percent_complete: float   # 0-100, work progress

    @property
    def total_committed(self) -> float:
        return self.spent_to_date + self.committed

    @property
    def remaining_budget(self) -> float:
        return self.budgeted_amount - self.total_committed

    @property
    def variance(self) -> float:
        return self.budgeted_amount - self.total_committed

    @property
    def variance_pct(self) -> float:
        if self.budgeted_amount == 0:
            return 0
        return (self.variance / self.budgeted_amount) * 100


@dataclass
class BudgetAlert:
    cost_code: str
    description: str
    level: AlertLevel
    message: str
    budgeted: float
    spent: float
    forecast: float
    variance: float


class BudgetVarianceTracker:
    """Track budget vs actual with forecasting and alerts."""

    def __init__(self, project_name: str, total_budget: float,
                 thresholds: Optional[Dict] = None):
        self.project_name = project_name
        self.total_budget = total_budget
        self.lines: Dict[str, BudgetLine] = {}
        self.thresholds = thresholds or {
            "green": 0.50,
            "yellow": 0.75,
            "orange": 0.90,
            "red": 0.95,
        }

    def add_budget_line(self, line: BudgetLine):
        self.lines[line.cost_code] = line

    def check_alerts(self) -> List[BudgetAlert]:
        """Check all budget lines for threshold breaches."""
        alerts = []

        for code, line in self.lines.items():
            usage = line.total_committed / line.budgeted_amount if line.budgeted_amount else 0
            forecast = self._forecast_final(line)

            # Determine alert level
            if forecast > line.budgeted_amount * 1.10:
                level = AlertLevel.CRITICAL
                msg = (f"FORECAST OVER BUDGET: {code} projected at ${forecast:,.0f} "
                       f"vs budget ${line.budgeted_amount:,.0f}")
            elif usage >= self.thresholds["red"] or forecast > line.budgeted_amount:
                level = AlertLevel.RED
                msg = f"OVER THRESHOLD: {code} at {usage*100:.0f}% of budget"
            elif usage >= self.thresholds["orange"]:
                level = AlertLevel.ORANGE
                msg = f"APPROACHING LIMIT: {code} at {usage*100:.0f}% of budget"
            elif usage >= self.thresholds["yellow"]:
                level = AlertLevel.YELLOW
                msg = f"MONITOR: {code} at {usage*100:.0f}% of budget"
            else:
                level = AlertLevel.GREEN
                msg = f"On track: {code} at {usage*100:.0f}% of budget"

            alerts.append(BudgetAlert(
                cost_code=code,
                description=line.description,
                level=level,
                message=msg,
                budgeted=line.budgeted_amount,
                spent=line.total_committed,
                forecast=forecast,
                variance=line.variance,
            ))

        return alerts

    def _forecast_final(self, line: BudgetLine) -> float:
        """Forecast final cost based on burn rate and % complete.

        burn-rate projection: spent / %complete = projected total
        """
        if line.percent_complete <= 0:
            return line.total_committed

        # If we've spent X to get Y% done, total = X / Y%
        burn_rate = line.spent_to_date / (line.percent_complete / 100)
        return burn_rate

    def get_summary(self) -> Dict:
        """Get project-wide budget summary."""
        total_budgeted = sum(l.budgeted_amount for l in self.lines.values())
        total_spent = sum(l.total_committed for l in self.lines.values())
        total_forecast = sum(self._forecast_final(l) for l in self.lines.values())

        over_budget = [l for l in self.lines.values() if l.variance < 0]

        return {
            "project": self.project_name,
            "total_budget": total_budgeted,
            "total_spent_committed": total_spent,
            "total_forecast": round(total_forecast, 2),
            "projected_variance": round(total_budgeted - total_forecast, 2),
            "projected_variance_pct": round((total_budgeted - total_forecast) / total_budgeted * 100, 1)
                if total_budgeted else 0,
            "lines_over_budget": len(over_budget),
            "over_budget_codes": [l.cost_code for l in over_budget],
            "remaining_budget": round(total_budgeted - total_spent, 2),
        }

    def get_cost_code_detail(self, cost_code: str) -> Dict:
        """Get detailed breakdown for a specific cost code."""
        line = self.lines.get(cost_code)
        if not line:
            return {"error": f"Cost code {cost_code} not found"}

        forecast = self._forecast_final(line)

        return {
            "cost_code": line.cost_code,
            "category": line.category,
            "description": line.description,
            "budgeted": line.budgeted_amount,
            "spent_to_date": line.spent_to_date,
            "committed": line.committed,
            "total_committed": line.total_committed,
            "remaining": line.remaining_budget,
            "variance": line.variance,
            "variance_pct": round(line.variance_pct, 1),
            "percent_complete": line.percent_complete,
            "forecast_final": round(forecast, 2),
            "forecast_variance": round(line.budgeted_amount - forecast, 2),
            "burn_rate": round(line.spent_to_date / (line.percent_complete / 100), 2)
                if line.percent_complete > 0 else 0,
        }


# ---------------------------------------------------------------------------
# CSV loading + CLI
# ---------------------------------------------------------------------------

def load_from_csv(tracker: BudgetVarianceTracker, csv_path: str) -> None:
    """Load budget lines from a CSV file into the tracker.

    Expected columns: cost_code,category,description,budgeted_amount,
    spent_to_date,committed,percent_complete
    """
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            tracker.add_budget_line(BudgetLine(
                cost_code=row["cost_code"],
                category=row["category"],
                description=row["description"],
                budgeted_amount=float(row["budgeted_amount"]),
                spent_to_date=float(row["spent_to_date"]),
                committed=float(row["committed"]),
                percent_complete=float(row["percent_complete"]),
            ))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Budget variance tracker")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--csv", required=True, help="Path to budget lines CSV")
    parser.add_argument("--total-budget", type=float, default=None,
                        help="Total project budget (defaults to sum of lines)")
    args = parser.parse_args(argv)

    tracker = BudgetVarianceTracker(args.project, args.total_budget or 0)
    load_from_csv(tracker, args.csv)
    if args.total_budget is None:
        tracker.total_budget = sum(l.budgeted_amount for l in tracker.lines.values())

    summary = tracker.get_summary()
    summary["alerts"] = [
        {
            "cost_code": a.cost_code,
            "level": a.level.value,
            "message": a.message,
        }
        for a in tracker.check_alerts()
    ]

    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
