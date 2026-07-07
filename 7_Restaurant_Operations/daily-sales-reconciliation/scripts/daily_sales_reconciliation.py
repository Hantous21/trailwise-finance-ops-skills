"""
Daily POS-to-bank deposit reconciliation for restaurants.

Matches each POS day to the bank deposits dated `date + deposit_lag_days`
(default 1) — i.e. the cash and card deposits that should have landed
the day after the sale. Flags:
  - cash_short / cash_over (variance beyond tolerance, default $5)
  - missing_deposit (no cash deposit at the lag date)
  - missing_settlement (no card deposit at the lag date)
  - fee_out_of_band (card-processor fee % outside [1.5, 4.0])

Usage:
    python3 scripts/daily_sales_reconciliation.py \\
        fixtures/input/pos_daily.csv \\
        fixtures/input/bank_deposits.csv \\
        --json reconciliation.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class POSDay:
    date: date
    gross_sales: float
    sales_tax: float
    comps: float
    cash_collected: float
    card_collected: float


@dataclass
class Deposit:
    deposit_date: date
    type: str  # "cash" or "card"
    amount: float


@dataclass
class DayReconciliation:
    date: date
    lag_date: date
    cash_collected: float
    card_collected: float
    cash_deposit: Optional[float]
    card_deposit: Optional[float]
    cash_variance: Optional[float]
    card_fee_pct: Optional[float]
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "date": self.date.isoformat(),
            "lag_date": self.lag_date.isoformat(),
            "cash_collected": round(self.cash_collected, 2),
            "card_collected": round(self.card_collected, 2),
            "cash_deposit": (None if self.cash_deposit is None
                             else round(self.cash_deposit, 2)),
            "card_deposit": (None if self.card_deposit is None
                             else round(self.card_deposit, 2)),
            "cash_variance": (None if self.cash_variance is None
                              else round(self.cash_variance, 2)),
            "card_fee_pct": (None if self.card_fee_pct is None
                             else round(self.card_fee_pct, 2)),
            "flags": list(self.flags),
        }


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _parse_amount(s: str) -> float:
    return float(s.strip() or "0")


def load_pos(csv_path: Path) -> List[POSDay]:
    out: List[POSDay] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                POSDay(
                    date=_parse_date(row["date"]),
                    gross_sales=_parse_amount(row["gross_sales"]),
                    sales_tax=_parse_amount(row["sales_tax"]),
                    comps=_parse_amount(row["comps"]),
                    cash_collected=_parse_amount(row["cash_collected"]),
                    card_collected=_parse_amount(row["card_collected"]),
                )
            )
    return out


def load_deposits(csv_path: Path) -> List[Deposit]:
    out: List[Deposit] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row["type"].strip().lower()
            if t not in ("cash", "card"):
                raise ValueError(f"unknown deposit type: {t!r}")
            out.append(
                Deposit(
                    deposit_date=_parse_date(row["deposit_date"]),
                    type=t,
                    amount=_parse_amount(row["amount"]),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def reconcile(
    pos: List[POSDay],
    deposits: List[Deposit],
    deposit_lag_days: int = 1,
    cash_tolerance: float = 5.00,
    fee_low: float = 1.5,
    fee_high: float = 4.0,
) -> List[DayReconciliation]:
    by_date_type: Dict[tuple, List[Deposit]] = {}
    for d in deposits:
        by_date_type.setdefault((d.deposit_date, d.type), []).append(d)

    def _sum_for(day: date, type_: str) -> Optional[float]:
        items = by_date_type.get((day, type_), [])
        if not items:
            return None
        return sum(d.amount for d in items)

    results: List[DayReconciliation] = []
    for p in pos:
        lag = p.date + timedelta(days=deposit_lag_days)
        cash_dep = _sum_for(lag, "cash")
        card_dep = _sum_for(lag, "card")

        cash_var: Optional[float] = None
        if cash_dep is not None:
            cash_var = round(cash_dep - p.cash_collected, 2)
        card_fee: Optional[float] = None
        if card_dep is not None and p.card_collected > 0:
            card_fee = round((p.card_collected - card_dep) / p.card_collected * 100, 2)

        flags: List[str] = []
        if cash_dep is None:
            flags.append("missing_deposit")
        else:
            if cash_var is not None and cash_var < -cash_tolerance:
                flags.append("cash_short")
            elif cash_var is not None and cash_var > cash_tolerance:
                flags.append("cash_over")
        if card_dep is None:
            flags.append("missing_settlement")
        else:
            if card_fee is not None and (card_fee < fee_low or card_fee > fee_high):
                flags.append("fee_out_of_band")

        results.append(
            DayReconciliation(
                date=p.date,
                lag_date=lag,
                cash_collected=p.cash_collected,
                card_collected=p.card_collected,
                cash_deposit=cash_dep,
                card_deposit=card_dep,
                cash_variance=cash_var,
                card_fee_pct=card_fee,
                flags=flags,
            )
        )
    return results


def summarize(results: List[DayReconciliation]) -> Dict[str, object]:
    matched_cash_variance = round(
        sum(r.cash_variance for r in results
            if r.cash_variance is not None and "missing_deposit" not in r.flags),
        2,
    )
    missing_deposit_amount = round(
        sum(r.cash_collected for r in results if "missing_deposit" in r.flags),
        2,
    )
    days_flagged = sum(1 for r in results if r.flags)
    flag_count = sum(len(r.flags) for r in results)
    return {
        "matched_cash_variance": matched_cash_variance,
        "missing_deposit_amount": missing_deposit_amount,
        "days_flagged": days_flagged,
        "flag_count": flag_count,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pos_csv", help="Path to pos_daily.csv")
    parser.add_argument("deposits_csv", help="Path to bank_deposits.csv")
    parser.add_argument("--json", default=None, help="Optional JSON report path")
    parser.add_argument("--deposit-lag-days", type=int, default=1)
    parser.add_argument("--cash-tolerance", type=float, default=5.00)
    parser.add_argument("--fee-low", type=float, default=1.5)
    parser.add_argument("--fee-high", type=float, default=4.0)
    args = parser.parse_args(argv)

    pos = load_pos(Path(args.pos_csv))
    deposits = load_deposits(Path(args.deposits_csv))
    results = reconcile(
        pos, deposits,
        deposit_lag_days=args.deposit_lag_days,
        cash_tolerance=args.cash_tolerance,
        fee_low=args.fee_low,
        fee_high=args.fee_high,
    )
    summary = summarize(results)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "days": [r.to_dict() for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"Daily reconciliation ({len(results)} day(s)):")
    for r in results:
        flag_str = " [" + ", ".join(r.flags) + "]" if r.flags else " [clean]"
        var = (f"variance {r.cash_variance:+.2f}" if r.cash_variance is not None
               else "no deposit")
        fee = (f"fee {r.card_fee_pct:.2f}%" if r.card_fee_pct is not None
               else "no settlement")
        print(f"  {r.date.isoformat()} (lag {r.lag_date.isoformat()}): "
              f"cash {var}; card {fee}{flag_str}")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
