"""Penny-exact daily tip pooling by role-weighted hours.

Every cent of the pool lands on exactly one person, deterministically.
Managers and owners are always excluded (federal rule).
Leftover pennies assigned by largest fractional remainder, ties broken
alphabetically by employee name.

Usage:
    python3 scripts/tip_pool_calculator.py shifts.csv tips.csv --json payout.json
    python3 scripts/tip_pool_calculator.py shifts.csv tips.csv \\
        --json payout.json --points points.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set


DEFAULT_POINTS: Dict[str, float] = {
    "server": 1.0,
    "bartender": 1.25,
    "busser": 0.5,
    "runner": 0.5,
    "host": 0.25,
}

EXCLUDED_ROLES: Set[str] = {"manager", "owner"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Shift:
    date: date
    employee: str
    role: str
    hours: float


@dataclass
class TipDay:
    date: date
    cash_tips: float
    card_tips: float

    @property
    def pool(self) -> float:
        return self.cash_tips + self.card_tips


@dataclass
class DayPayout:
    date: date
    pool: float
    payouts: Dict[str, float]  # employee -> payout
    excluded: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "date": self.date.isoformat(),
            "pool": round(self.pool, 2),
            "payouts": {emp: round(amt, 2) for emp, amt in sorted(self.payouts.items())},
            "excluded": sorted(self.excluded),
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _parse_amount(s: str) -> float:
    return float(s.strip() or "0")


def load_shifts(csv_path: Path) -> List[Shift]:
    out: List[Shift] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                Shift(
                    date=_parse_date(row["date"]),
                    employee=row["employee"].strip(),
                    role=row["role"].strip().lower(),
                    hours=_parse_amount(row["hours"]),
                )
            )
    return out


def load_tips(csv_path: Path) -> List[TipDay]:
    out: List[TipDay] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                TipDay(
                    date=_parse_date(row["date"]),
                    cash_tips=_parse_amount(row["cash_tips"]),
                    card_tips=_parse_amount(row["card_tips"]),
                )
            )
    return out


def load_points(json_path: Path) -> Dict[str, float]:
    if not json_path.exists():
        return dict(DEFAULT_POINTS)
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {k.lower(): float(v) for k, v in data.items()}


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _split_pennies(
    pool: float,
    raw_shares: Dict[str, float],
) -> Dict[str, float]:
    """Floor to cent, then hand out leftover pennies by largest fractional
    remainder, ties broken alphabetically by employee name."""
    # Floor to cent
    floored: Dict[str, float] = {}
    remainders: List[Tuple[str, float]] = []
    total_floored = 0.0

    for emp in sorted(raw_shares.keys()):
        raw = raw_shares[emp]
        f = int(raw * 100) / 100.0  # floor to cent
        floored[emp] = f
        total_floored += f
        remainders.append((emp, raw - f))

    pool_cents = round(pool * 100)
    floored_cents = round(total_floored * 100)
    pennies_to_allocate = pool_cents - floored_cents

    if pennies_to_allocate < 0:
        raise RuntimeError(
            f"Internal error: floored total ({floored_cents / 100:.2f}) "
            f"exceeds pool ({pool_cents / 100:.2f})"
        )

    # Sort by remainder descending, then by name alphabetically for ties
    remainders.sort(key=lambda x: (-x[1], x[0]))

    for i in range(pennies_to_allocate):
        emp = remainders[i][0]
        floored[emp] += 0.01

    return floored


def calculate(
    shifts: List[Shift],
    tips: List[TipDay],
    points: Dict[str, float],
) -> List[DayPayout]:
    tips_by_date: Dict[date, TipDay] = {t.date: t for t in tips}
    shifts_by_date: Dict[date, List[Shift]] = {}
    for s in shifts:
        shifts_by_date.setdefault(s.date, []).append(s)

    results: List[DayPayout] = []

    for day_date in sorted(tips_by_date.keys()):
        tip_day = tips_by_date[day_date]
        day_shifts = shifts_by_date.get(day_date, [])
        pool = tip_day.pool

        excluded: List[str] = []
        eligible: List[Shift] = []
        for s in day_shifts:
            if s.role in EXCLUDED_ROLES:
                excluded.append(s.employee)
            else:
                eligible.append(s)

        # Also check for unknown roles
        warnings: List[str] = []
        for s in day_shifts:
            if s.role not in EXCLUDED_ROLES and s.role not in points:
                print(f"ERROR: unknown role '{s.role}' for employee {s.employee} "
                      f"on {s.date.isoformat()}. Known roles: "
                      f"{sorted(points.keys())}. Excluded: {sorted(EXCLUDED_ROLES)}.",
                      file=sys.stderr)
                sys.exit(1)

        if excluded:
            warnings.append(
                f"{len(excluded)} excluded (manager/owner): "
                f"{', '.join(sorted(set(excluded)))}"
            )

        if not eligible:
            print(
                f"ERROR: no eligible shifts for {day_date.isoformat()} "
                f"but pool is ${pool:,.2f}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Weighted hours
        total_weight = 0.0
        raw_shares: Dict[str, float] = {}
        for s in eligible:
            w = s.hours * points[s.role]
            raw_shares[s.employee] = raw_shares.get(s.employee, 0.0) + w
            total_weight += w

        # Convert to dollar shares
        dollar_shares: Dict[str, float] = {}
        for emp, w in raw_shares.items():
            dollar_shares[emp] = (w / total_weight) * pool

        payouts = _split_pennies(pool, dollar_shares)

        # Assert pool ties out exactly
        total_paid = sum(payouts.values())
        if round(total_paid, 2) != round(pool, 2):
            print(
                f"FATAL: pool ${pool:,.2f} does not match payouts ${total_paid:,.2f} "
                f"for {day_date.isoformat()}",
                file=sys.stderr,
            )
            sys.exit(1)

        results.append(
            DayPayout(
                date=day_date,
                pool=pool,
                payouts=payouts,
                excluded=sorted(set(excluded)),
                warnings=warnings,
            )
        )

    return results


def week_totals(results: List[DayPayout]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for day in results:
        for emp, amt in day.payouts.items():
            totals[emp] = totals.get(emp, 0.0) + amt
    return totals


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("shifts_csv", help="Path to shifts.csv")
    parser.add_argument("tips_csv", help="Path to tips.csv")
    parser.add_argument("--json", default=None, help="Optional JSON payouts path")
    parser.add_argument("--points", default=None, help="Optional role points JSON override")
    args = parser.parse_args(argv)

    shifts = load_shifts(Path(args.shifts_csv))
    tips = load_tips(Path(args.tips_csv))
    points = load_points(Path(args.points)) if args.points else dict(DEFAULT_POINTS)

    results = calculate(shifts, tips, points)
    totals = week_totals(results)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "days": [r.to_dict() for r in results],
                    "week_totals": {emp: round(amt, 2) for emp, amt in sorted(totals.items())},
                    "grand_total": round(sum(totals.values()), 2),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    grand = sum(totals.values())
    print(f"Tip pool calculator: ${grand:,.2f} across {len(results)} day(s)")
    for r in results:
        print(f"  {r.date.isoformat()}: pool ${r.pool:,.2f} -> "
              f"{', '.join(f'{e} ${a:,.2f}' for e, a in sorted(r.payouts.items()))}")
        if r.warnings:
            for w in r.warnings:
                print(f"    WARNING: {w}")
    print("Week totals:")
    for emp, amt in sorted(totals.items()):
        print(f"  {emp}: ${amt:,.2f}")
    print(f"  GRAND TOTAL: ${grand:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())