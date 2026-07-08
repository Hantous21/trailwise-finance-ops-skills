"""Weekly prime-cost tracker from a simple P&L export.

Prime cost = food COGS + beverage COGS + total labor.
True COGS = purchases + beginning_inventory - ending_inventory.
Benchmark band: prime_pct <= 60.00 -> ok; 60.00 < prime_pct <= 65.00 -> watch;
prime_pct > 65.00 -> over.

Usage:
    python3 scripts/prime_cost_tracker.py weekly_pnl.csv --json report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Dict


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PNLWeek:
    week_ending: date
    net_sales: float
    food_purchases: float
    food_inv_begin: float
    food_inv_end: float
    bev_purchases: float
    bev_inv_begin: float
    bev_inv_end: float
    labor_foh: float
    labor_boh: float
    labor_salaried: float
    payroll_taxes_benefits: float


@dataclass
class WeekResult:
    week_ending: date
    net_sales: float
    food_cogs: float
    bev_cogs: float
    total_labor: float
    prime_cost: float
    food_pct: float
    bev_pct: float
    labor_pct: float
    prime_pct: float
    status: str
    wow_delta: Optional[float]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "week_ending": self.week_ending.isoformat(),
            "net_sales": round(self.net_sales, 2),
            "food_cogs": round(self.food_cogs, 2),
            "bev_cogs": round(self.bev_cogs, 2),
            "total_labor": round(self.total_labor, 2),
            "prime_cost": round(self.prime_cost, 2),
            "food_pct": round(self.food_pct, 2),
            "bev_pct": round(self.bev_pct, 2),
            "labor_pct": round(self.labor_pct, 2),
            "prime_pct": round(self.prime_pct, 2),
            "status": self.status,
            "wow_delta": None if self.wow_delta is None else round(self.wow_delta, 2),
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _parse_amount(s: str) -> float:
    return float(s.strip() or "0")


def load_pnl(csv_path: Path) -> List[PNLWeek]:
    out: List[PNLWeek] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                PNLWeek(
                    week_ending=_parse_date(row["week_ending"]),
                    net_sales=_parse_amount(row["net_sales"]),
                    food_purchases=_parse_amount(row["food_purchases"]),
                    food_inv_begin=_parse_amount(row["food_inv_begin"]),
                    food_inv_end=_parse_amount(row["food_inv_end"]),
                    bev_purchases=_parse_amount(row["bev_purchases"]),
                    bev_inv_begin=_parse_amount(row["bev_inv_begin"]),
                    bev_inv_end=_parse_amount(row["bev_inv_end"]),
                    labor_foh=_parse_amount(row["labor_foh"]),
                    labor_boh=_parse_amount(row["labor_boh"]),
                    labor_salaried=_parse_amount(row["labor_salaried"]),
                    payroll_taxes_benefits=_parse_amount(row["payroll_taxes_benefits"]),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _status(prime_pct: float) -> str:
    if prime_pct <= 60.00:
        return "ok"
    elif prime_pct <= 65.00:
        return "watch"
    else:
        return "over"


def track_prime_cost(weeks: List[PNLWeek]) -> List[WeekResult]:
    results: List[WeekResult] = []
    prev_food_inv_end: Optional[float] = None
    prev_bev_inv_end: Optional[float] = None

    for w in weeks:
        warnings: List[str] = []
        food_cogs = w.food_purchases + w.food_inv_begin - w.food_inv_end
        bev_cogs = w.bev_purchases + w.bev_inv_begin - w.bev_inv_end
        total_labor = w.labor_foh + w.labor_boh + w.labor_salaried + w.payroll_taxes_benefits
        prime_cost = food_cogs + bev_cogs + total_labor

        food_pct = (food_cogs / w.net_sales) * 100
        bev_pct = (bev_cogs / w.net_sales) * 100
        labor_pct = (total_labor / w.net_sales) * 100
        prime_pct = (prime_cost / w.net_sales) * 100

        status = _status(prime_pct)

        # Inventory continuity check
        if prev_food_inv_end is not None and abs(w.food_inv_begin - prev_food_inv_end) > 0.001:
            warnings.append(
                f"food inventory discontinuity: week ending {w.week_ending.isoformat()} "
                f"begin {w.food_inv_begin:.2f} != prior end {prev_food_inv_end:.2f}"
            )
        if prev_bev_inv_end is not None and abs(w.bev_inv_begin - prev_bev_inv_end) > 0.001:
            warnings.append(
                f"bev inventory discontinuity: week ending {w.week_ending.isoformat()} "
                f"begin {w.bev_inv_begin:.2f} != prior end {prev_bev_inv_end:.2f}"
            )

        prev_food_inv_end = w.food_inv_end
        prev_bev_inv_end = w.bev_inv_end

        results.append(
            WeekResult(
                week_ending=w.week_ending,
                net_sales=w.net_sales,
                food_cogs=food_cogs,
                bev_cogs=bev_cogs,
                total_labor=total_labor,
                prime_cost=prime_cost,
                food_pct=food_pct,
                bev_pct=bev_pct,
                labor_pct=labor_pct,
                prime_pct=prime_pct,
                status=status,
                wow_delta=None,
                warnings=warnings,
            )
        )

    # Compute WoW deltas after all weeks processed
    for i in range(1, len(results)):
        results[i].wow_delta = results[i].prime_pct - results[i - 1].prime_pct

    return results


def summarize(results: List[WeekResult]) -> Dict[str, object]:
    total_sales = sum(r.net_sales for r in results)
    total_food = sum(r.food_cogs for r in results)
    total_bev = sum(r.bev_cogs for r in results)
    total_labor = sum(r.total_labor for r in results)
    total_prime = sum(r.prime_cost for r in results)

    period_prime_pct = (total_prime / total_sales) * 100 if total_sales > 0 else 0.0
    period_status = _status(period_prime_pct)

    wow_deltas = [r.wow_delta for r in results if r.wow_delta is not None]
    if len(wow_deltas) >= 3:
        rising_trend = all(d > 0 for d in wow_deltas[-3:])
    else:
        rising_trend = False

    all_warnings: List[str] = []
    for r in results:
        all_warnings.extend(r.warnings)

    return {
        "net_sales": round(total_sales, 2),
        "food_cogs": round(total_food, 2),
        "bev_cogs": round(total_bev, 2),
        "total_labor": round(total_labor, 2),
        "prime_cost": round(total_prime, 2),
        "food_pct": round((total_food / total_sales) * 100, 2) if total_sales > 0 else 0.0,
        "bev_pct": round((total_bev / total_sales) * 100, 2) if total_sales > 0 else 0.0,
        "labor_pct": round((total_labor / total_sales) * 100, 2) if total_sales > 0 else 0.0,
        "prime_pct": round(period_prime_pct, 2),
        "status": period_status,
        "rising_trend": rising_trend,
        "warnings": all_warnings,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pnl_csv", help="Path to weekly_pnl.csv")
    parser.add_argument("--json", default=None, help="Optional JSON report path")
    args = parser.parse_args(argv)

    weeks = load_pnl(Path(args.pnl_csv))
    results = track_prime_cost(weeks)
    summary = summarize(results)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "weeks": [r.to_dict() for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"Prime cost tracker ({len(results)} week(s)):")
    for r in results:
        delta_str = f"  wow {r.wow_delta:+.2f}" if r.wow_delta is not None else ""
        print(
            f"  {r.week_ending.isoformat()}: sales ${r.net_sales:,.2f}  "
            f"food ${r.food_cogs:,.2f} ({r.food_pct:.2f}%)  "
            f"bev ${r.bev_cogs:,.2f} ({r.bev_pct:.2f}%)  "
            f"labor ${r.total_labor:,.2f} ({r.labor_pct:.2f}%)  "
            f"prime {r.prime_pct:.2f}% [{r.status}]{delta_str}"
        )
    print(f"Period: prime {summary['prime_pct']:.2f}% [{summary['status']}]"
          f"  rising_trend: {summary['rising_trend']}")
    if summary["warnings"]:
        for w in summary["warnings"]:
            print(f"  WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())