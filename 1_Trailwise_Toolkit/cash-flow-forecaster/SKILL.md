---
name: "cash-flow-forecaster"
description: "Forecast project and company cash flow. Generate S-curves, predict shortfalls, and model payment timing scenarios."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "💰"
    category: "cash-management"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "matplotlib"]
---

# Cash Flow Forecaster

## Overview

Project cash inflows and outflows over time. Generate S-curve projections, predict cash shortfalls before they happen, and model "what-if" payment timing scenarios (early payment discounts, delayed client payments, etc.).

## When to Use

- Cash flow is managed by checking the bank balance
- No projection beyond "what's due this week"
- Can't model the impact of a delayed client payment
- No visibility into whether you can take on a new project

## Capabilities

- Weekly/monthly cash flow projection (4-12 weeks out)
- S-curve generation (cumulative cash position over time)
- Accounts receivable timing (client payment terms: Net-15, Net-30, Net-60)
- Accounts payable timing (vendor payment terms)
- Shortfall prediction (when cash goes negative)
- Scenario modeling (early payment discount, delayed payment, new project)
- Burn rate calculation (weekly cash outflow average)

## Quick Start

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional
from enum import Enum

class CashFlowDirection(Enum):
    INFLOW = "inflow"   # Money coming in (client payments, draws)
    OUTFLOW = "outflow"  # Money going out (vendor payments, payroll, overhead)

@dataclass
class CashEvent:
    date: date
    amount: float
    direction: CashFlowDirection
    description: str
    confidence: float = 1.0  # 0-1, 1=confirmed, 0.5=expected but unconfirmed
    source: str = ""         # "client", "vendor", "payroll", "overhead"

@dataclass
class CashPosition:
    date: date
    opening_balance: float
    inflows: float
    outflows: float
    net_change: float
    closing_balance: float
    events: List[CashEvent] = field(default_factory=list)
```

## Cash Flow Engine

```python
class CashFlowForecaster:
    """Project cash flow and predict shortfalls."""

    def __init__(self, opening_balance: float, start_date: date):
        self.opening_balance = opening_balance
        self.start_date = start_date
        self.events: List[CashEvent] = []
        self.recurring: List[Dict] = []  # Recurring events (payroll, rent, etc.)

    def add_event(self, event: CashEvent):
        self.events.append(event)

    def add_recurring(self, description: str, amount: float,
                      direction: CashFlowDirection, frequency_days: int,
                      source: str = "", confidence: float = 0.9):
        """Add a recurring cash event (payroll, rent, loan payments)."""
        self.recurring.append({
            "description": description,
            "amount": amount,
            "direction": direction,
            "frequency_days": frequency_days,
            "source": source,
            "confidence": confidence
        })

    def add_ar(self, invoice_amount: float, invoice_date: date,
               payment_terms_days: int = 30, confidence: float = 0.7):
        """Schedule an accounts receivable inflow based on payment terms."""
        expected_payment = invoice_date + timedelta(days=payment_terms_days)
        self.add_event(CashEvent(
            date=expected_payment,
            amount=invoice_amount,
            direction=CashFlowDirection.INFLOW,
            description=f"AR payment (invoiced {invoice_date})",
            confidence=confidence,
            source="client"
        ))

    def add_ap(self, invoice_amount: float, invoice_date: date,
               payment_terms_days: int = 30, confidence: float = 0.9):
        """Schedule an accounts payable outflow based on payment terms."""
        expected_payment = invoice_date + timedelta(days=payment_terms_days)
        self.add_event(CashEvent(
            date=expected_payment,
            amount=invoice_amount,
            direction=CashFlowDirection.OUTFLOW,
            description=f"AP payment (invoiced {invoice_date})",
            confidence=confidence,
            source="vendor"
        ))

    def forecast(self, weeks: int = 8) -> List[CashPosition]:
        """Generate weekly cash flow forecast."""
        positions = []
        balance = self.opening_balance

        # Expand recurring events into concrete events
        all_events = list(self.events)
        for rec in self.recurring:
            current = self.start_date
            while current <= self.start_date + timedelta(weeks=weeks):
                all_events.append(CashEvent(
                    date=current,
                    amount=rec["amount"],
                    direction=rec["direction"],
                    description=rec["description"],
                    confidence=rec["confidence"],
                    source=rec["source"]
                ))
                current += timedelta(days=rec["frequency_days"])

        # Group events by week
        for week in range(weeks):
            week_start = self.start_date + timedelta(weeks=week)
            week_end = week_start + timedelta(days=6)

            week_events = [e for e in all_events if week_start <= e.date <= week_end]

            inflows = sum(e.amount for e in week_events if e.direction == CashFlowDirection.INFLOW)
            outflows = sum(e.amount for e in week_events if e.direction == CashFlowDirection.OUTFLOW)
            net = inflows - outflows

            opening = balance
            balance += net

            positions.append(CashPosition(
                date=week_start,
                opening_balance=opening,
                inflows=inflows,
                outflows=outflows,
                net_change=net,
                closing_balance=balance,
                events=week_events
            ))

        return positions

    def predict_shortfalls(self, weeks: int = 8) -> List[Dict]:
        """Predict weeks where cash balance goes negative."""
        positions = self.forecast(weeks)
        shortfalls = []

        for pos in positions:
            if pos.closing_balance < 0:
                shortfalls.append({
                    "week_of": pos.date.isoformat(),
                    "deficit": round(abs(pos.closing_balance), 2),
                    "inflows": pos.inflows,
                    "outflows": pos.outflows,
                    "recommendation": self._shortfall_recommendation(pos)
                })

        return shortfalls

    def _shortfall_recommendation(self, pos: CashPosition) -> str:
        """Generate actionable recommendation for a shortfall week."""
        if pos.outflows > pos.inflows * 2:
            return "Large outflow week — negotiate vendor payment terms or delay non-critical AP"
        elif pos.inflows == 0:
            return "No inflows scheduled — follow up on overdue AR or request client draw"
        else:
            return "Tight week — consider line of credit draw or expedite client payment"

    def scenario_early_payment(self, discount_pct: float, weeks: int = 8) -> Dict:
        """Model the impact of offering early payment discounts to clients."""
        positions = self.forecast(weeks)
        original_total = sum(p.inflows for p in positions)

        # Move inflows 2 weeks earlier, reduce by discount
        adjusted_events = []
        for e in self.events:
            if e.direction == CashFlowDirection.INFLOW:
                adjusted_events.append(CashEvent(
                    date=e.date - timedelta(weeks=2),
                    amount=e.amount * (1 - discount_pct / 100),
                    direction=e.direction,
                    description=f"{e.description} (early payment, {discount_pct}% discount)",
                    confidence=0.85,
                    source=e.source
                ))
            else:
                adjusted_events.append(e)

        # Re-forecast with adjusted events
        original_events = self.events
        self.events = adjusted_events
        new_positions = self.forecast(weeks)
        self.events = original_events

        new_total = sum(p.inflows for p in new_positions)
        new_shortfalls = self.predict_shortfalls(weeks)

        return {
            "scenario": f"Early payment at {discount_pct}% discount",
            "original_inflows": round(original_total, 2),
            "adjusted_inflows": round(new_total, 2),
            "discount_cost": round(original_total - new_total, 2),
            "original_shortfalls": len(self.predict_shortfalls(weeks)),
            "adjusted_shortfalls": len(new_shortfalls),
            "net_benefit": "Positive" if len(new_shortfalls) < len(self.predict_shortfalls(weeks)) else "Negative"
        }

    def get_burn_rate(self, weeks: int = 4) -> float:
        """Calculate average weekly cash outflow."""
        positions = self.forecast(weeks)
        return sum(p.outflows for p in positions) / weeks
```

## S-Curve Generation

```python
def generate_scurve(positions: List[CashPosition]) -> Dict:
    """Generate S-curve data for visualization."""
    cumulative = []
    running = 0
    for p in positions:
        running += p.net_change
        cumulative.append({
            "date": p.date.isoformat(),
            "weekly_net": round(p.net_change, 2),
            "cumulative": round(running, 2),
            "balance": round(p.closing_balance, 2)
        })
    return {
        "opening_balance": positions[0].opening_balance,
        "closing_balance": positions[-1].closing_balance,
        "peak_balance": max(p.closing_balance for p in positions),
        "trough_balance": min(p.closing_balance for p in positions),
        "data_points": cumulative
    }
```

## Integration

- **QuickBooks** — Pull AR/AP aging directly
- **Bank API** — Real-time opening balance
- **n8n** — Weekly forecast email + Slack alert on predicted shortfall
- **Trailwise SaaS** — Dashboard with interactive S-curve ($49/mo)


---

## One-Shot vs Ongoing

This skill runs a **one-time analysis**. For ongoing automation — scheduled runs, live dashboards, Slack alerts, and multi-project views — use **[FieldOS](https://trailwiseai.com)**.

| This skill does | FieldOS does ($49/mo) |
|-----------------|----------------------|
| Runs when you remember | Runs weekly, alerts on Slack |
| Reads a CSV you export | Pulls from QuickBooks automatically |
| Text report output | Live dashboard with charts |
| Single project at a time | Multi-project consolidated view |
| No history | Trend tracking, month-over-month |

**[Start with FieldOS →](https://trailwiseai.com)** · **[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
