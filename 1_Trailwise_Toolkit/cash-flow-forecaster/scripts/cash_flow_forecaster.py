"""Cash Flow Forecaster — projection engine extracted from SKILL.md.

Provides weekly cash flow projection, S-curve generation, shortfall
prediction, and scenario modeling (early-payment discount).
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class CashFlowDirection(Enum):
    INFLOW = "inflow"    # Money coming in (client payments, draws)
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
            "confidence": confidence,
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
            source="client",
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
            source="vendor",
        ))

    def forecast(self, weeks: int = 8) -> List[CashPosition]:
        """Generate weekly cash flow forecast."""
        positions: List[CashPosition] = []
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
                    source=rec["source"],
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
                events=week_events,
            ))

        return positions

    def predict_shortfalls(self, weeks: int = 8) -> List[Dict]:
        """Predict weeks where cash balance goes negative."""
        positions = self.forecast(weeks)
        shortfalls: List[Dict] = []

        for pos in positions:
            if pos.closing_balance < 0:
                shortfalls.append({
                    "week_of": pos.date.isoformat(),
                    "deficit": round(abs(pos.closing_balance), 2),
                    "inflows": pos.inflows,
                    "outflows": pos.outflows,
                    "recommendation": self._shortfall_recommendation(pos),
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
                    source=e.source,
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
            "net_benefit": "Positive" if len(new_shortfalls) < len(self.predict_shortfalls(weeks)) else "Negative",
        }

    def get_burn_rate(self, weeks: int = 4) -> float:
        """Calculate average weekly cash outflow."""
        positions = self.forecast(weeks)
        return sum(p.outflows for p in positions) / weeks


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
            "balance": round(p.closing_balance, 2),
        })
    return {
        "opening_balance": positions[0].opening_balance,
        "closing_balance": positions[-1].closing_balance,
        "peak_balance": max(p.closing_balance for p in positions),
        "trough_balance": min(p.closing_balance for p in positions),
        "data_points": cumulative,
    }


def load_events_from_csv(csv_path: Path) -> List[CashEvent]:
    """Load cash events from a CSV file.

    The CSV columns are: date,amount,direction,description,confidence,source.
    Outflow amounts are stored as negative values in the file; the direction
    column already encodes the sign, so the magnitude is what we store on the
    CashEvent (amount >= 0).
    """
    events: List[CashEvent] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row or not row.get("date"):
                continue
            events.append(CashEvent(
                date=date.fromisoformat(row["date"]),
                amount=abs(float(row["amount"])),
                direction=CashFlowDirection(row["direction"]),
                description=row["description"],
                confidence=float(row.get("confidence", 1.0) or 1.0),
                source=row.get("source", ""),
            ))
    return events


def run_forecast(
    as_of: Optional[date] = None,
    opening_balance: float = 50000,
    weeks: int = 4,
    csv_path: Optional[Path] = None,
) -> Dict:
    """Run the full forecast pipeline against a CSV of cash events.

    ``as_of`` pins the reference date so output is deterministic. When omitted
    it defaults to ``date.today()``. The forecast window starts the day after
    ``as_of`` (so an ``as_of`` of 2026-06-30 projects from 2026-07-01).
    """
    if as_of is None:
        as_of = date.today()
    if csv_path is None:
        csv_path = (
            Path(__file__).resolve().parent.parent
            / "fixtures" / "input" / "cash_events.csv"
        )

    start_date = as_of + timedelta(days=1)
    events = load_events_from_csv(csv_path)

    forecaster = CashFlowForecaster(opening_balance, start_date)
    for e in events:
        forecaster.add_event(e)

    positions = forecaster.forecast(weeks=weeks)
    shortfalls = forecaster.predict_shortfalls(weeks=weeks)
    burn_rate = forecaster.get_burn_rate(weeks=weeks)

    weekly_positions = [
        {
            "week": p.date.isoformat(),
            "inflows": round(p.inflows, 2),
            "outflows": round(p.outflows, 2),
            "net": round(p.net_change, 2),
            "closing": round(p.closing_balance, 2),
        }
        for p in positions
    ]

    return {
        "opening_balance": round(opening_balance, 2),
        "start_date": start_date.isoformat(),
        "weeks_projected": weeks,
        "closing_balance": round(positions[-1].closing_balance, 2),
        "peak_balance": round(max(p.closing_balance for p in positions), 2),
        "trough_balance": round(min(p.closing_balance for p in positions), 2),
        "shortfalls": shortfalls,
        "weekly_positions": weekly_positions,
        "burn_rate": round(burn_rate, 2),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project cash flow from a CSV of cash events.",
    )
    parser.add_argument(
        "--input", "-i", type=Path,
        default=None,
        help="Path to cash_events.csv (defaults to the skill fixtures input).",
    )
    parser.add_argument(
        "--output", "-o", type=Path,
        default=None,
        help="Path to write the forecast JSON (defaults to stdout).",
    )
    parser.add_argument(
        "--as-of", type=str, default=None,
        help="Reference date YYYY-MM-DD (defaults to today).",
    )
    parser.add_argument(
        "--opening-balance", type=float, default=50000.0,
        help="Opening cash balance (default 50000).",
    )
    parser.add_argument(
        "--weeks", type=int, default=4,
        help="Number of weeks to project (default 4).",
    )
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    result = run_forecast(
        as_of=as_of,
        opening_balance=args.opening_balance,
        weeks=args.weeks,
        csv_path=args.input,
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

