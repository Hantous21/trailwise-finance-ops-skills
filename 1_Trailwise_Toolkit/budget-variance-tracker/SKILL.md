---
name: "budget-variance-tracker"
description: "Track budget vs actual costs in real-time. Flag overruns, forecast final costs, and trigger alerts when thresholds are breached."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "📊"
    category: "budget-management"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
---

# Budget Variance Tracker

## Overview

Compare budgeted costs against actual spending in real-time. Flag cost overruns before they happen, forecast final project costs using burn rate analysis, and trigger alerts when budget thresholds are breached.

## When to Use

- Budget tracking happens in Excel, updated monthly (always stale)
- Overruns discovered at month-end close (too late to act)
- No early warning system for budget breaches
- Multiple projects with separate budgets, no consolidated view

## Capabilities

- Budget vs actual comparison by cost code
- Variance percentage and dollar amount
- Burn rate analysis (spend velocity)
- Final cost forecast (based on burn rate + remaining work)
- Threshold-based alerts (50%, 75%, 90%, 100% of budget)
- Multi-project consolidation
- Trend analysis (is spending accelerating or decelerating?)

## Quick Start

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional
from enum import Enum

class AlertLevel(Enum):
    GREEN = "green"    # Under 50% of budget used, on track
    YELLOW = "yellow"  # 50-75% used, monitor
    ORANGE = "orange"  # 75-90% used, action recommended
    RED = "red"        # 90%+ used or forecast exceeds budget
    CRITICAL = "critical"  # Over budget

@dataclass
class BudgetLine:
    cost_code: str          # e.g., "04000 - Concrete"
    category: str           # e.g., "Materials", "Labor", "Subcontract"
    description: str
    budgeted_amount: float
    spent_to_date: float
    committed: float        # POs/contracts signed but not yet invoiced
    percent_complete: float # 0-100, work progress

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
```

## Variance Tracker

```python
class BudgetVarianceTracker:
    """Track budget vs actual with forecasting and alerts."""

    def __init__(self, project_name: str, total_budget: float,
                 thresholds: Dict = None):
        self.project_name = project_name
        self.total_budget = total_budget
        self.lines: Dict[str, BudgetLine] = {}
        self.thresholds = thresholds or {
            "green": 0.50,
            "yellow": 0.75,
            "orange": 0.90,
            "red": 0.95
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
                msg = f"FORECAST OVER BUDGET: {code} projected at ${forecast:,.0f} "
                      f"vs budget ${line.budgeted_amount:,.0f}"
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
                variance=line.variance
            ))

        return alerts

    def _forecast_final(self, line: BudgetLine) -> float:
        """Forecast final cost based on burn rate and % complete."""
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
            "remaining_budget": round(total_budgeted - total_spent, 2)
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
                if line.percent_complete > 0 else 0
        }
```

## Input Data Format

### Budget (Excel/CSV)
```csv
cost_code,category,description,budgeted_amount,spent_to_date,committed,percent_complete
04000,Materials,Concrete - Foundation,25000,18000,5000,75
05100,Labor,Steel Erection,45000,30000,0,60
06200,Subcontract,Plumbing Rough-in,38000,15000,12000,40
```

## Alert Integration

Feed alerts to n8n for notification routing:
- **GREEN** → Weekly digest email
- **YELLOW** → Daily dashboard update
- **ORANGE** → Slack/Teams ping to project manager
- **RED** → Email + SMS to finance director
- **CRITICAL** → Escalation to ownership

## Edge Cases

1. **Zero-budget lines** — Cost codes with no budget but actual spending (unbudgeted work)
2. **Negative variance at 10% complete** — Early-stage overrun, high uncertainty in forecast
3. **Committed but not spent** — Large PO signed, no invoice yet (committed cost)
4. **Cost code reclassification** — Item moved from 04000 to 04100 mid-project
5. **Contingency drawdown** — Moving money from contingency to specific cost codes
