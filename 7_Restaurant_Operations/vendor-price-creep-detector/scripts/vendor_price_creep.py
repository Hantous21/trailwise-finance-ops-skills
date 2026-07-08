"""Detect vendor price creep from purchase history.

Per-(vendor, item) history: baseline price, latest price, creep %.
Flags price_creep when creep_pct > creep-threshold and price_spike when any
consecutive purchase-to-purchase jump exceeds spike-threshold %.

Usage:
    python3 scripts/vendor_price_creep.py purchase_history.csv \\
        --creep-threshold 5.0 --spike-threshold 10.0 --json report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Purchase:
    date: date
    vendor: str
    item: str
    quantity: float
    unit: str
    unit_price: float


@dataclass
class ItemResult:
    vendor: str
    item: str
    baseline_price: Optional[float] = None
    latest_price: Optional[float] = None
    creep_pct: Optional[float] = None
    flags: List[str] = field(default_factory=list)
    excess_cost_to_date: Optional[float] = None
    insufficient_history: bool = False
    purchases: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "vendor": self.vendor,
            "item": self.item,
            "baseline_price": (None if self.baseline_price is None
                               else round(self.baseline_price, 2)),
            "latest_price": (None if self.latest_price is None
                             else round(self.latest_price, 2)),
            "creep_pct": (None if self.creep_pct is None
                          else round(self.creep_pct, 2)),
            "flags": list(self.flags),
            "excess_cost_to_date": (None if self.excess_cost_to_date is None
                                    else round(self.excess_cost_to_date, 2)),
            "insufficient_history": self.insufficient_history,
            "purchases": self.purchases,
        }


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _parse_amount(s: str) -> float:
    return float(s.strip() or "0")


def load_purchases(csv_path: Path) -> List[Purchase]:
    out: List[Purchase] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                Purchase(
                    date=_parse_date(row["date"]),
                    vendor=row["vendor"].strip(),
                    item=row["item"].strip(),
                    quantity=_parse_amount(row["quantity"]),
                    unit=row["unit"].strip(),
                    unit_price=_parse_amount(row["unit_price"]),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def detect_creep(
    purchases: List[Purchase],
    creep_threshold: float = 5.0,
    spike_threshold: float = 10.0,
) -> List[ItemResult]:
    # Group by (vendor, item), sort by date
    groups: Dict[tuple, List[Purchase]] = {}
    for p in purchases:
        key = (p.vendor, p.item)
        groups.setdefault(key, []).append(p)

    for key in groups:
        groups[key].sort(key=lambda p: p.date)

    results: List[ItemResult] = []
    for (vendor, item), group in sorted(groups.items()):
        r = ItemResult(vendor=vendor, item=item, purchases=len(group))

        if len(group) < 2:
            r.insufficient_history = True
            results.append(r)
            continue

        baseline = group[0].unit_price
        latest = group[-1].unit_price
        r.baseline_price = baseline
        r.latest_price = latest
        r.creep_pct = ((latest - baseline) / baseline) * 100

        # Check price_creep: creep_pct strictly > threshold
        if r.creep_pct > creep_threshold:
            r.flags.append("price_creep")

        # Check price_spike: any consecutive jump strictly > spike_threshold
        for i in range(1, len(group)):
            prev_price = group[i - 1].unit_price
            curr_price = group[i].unit_price
            jump_pct = ((curr_price - prev_price) / prev_price) * 100
            if jump_pct > spike_threshold:
                r.flags.append("price_spike")
                break

        # Excess cost to date: sum over all purchases of (unit_price - baseline) * quantity
        excess = sum((p.unit_price - baseline) * p.quantity for p in group)
        r.excess_cost_to_date = excess

        results.append(r)

    return results


def summarize(results: List[ItemResult]) -> Dict[str, object]:
    items_tracked = len(results)
    items_flagged = sum(1 for r in results if r.flags)
    excess_cost_flagged = sum(
        r.excess_cost_to_date for r in results
        if r.flags and r.excess_cost_to_date is not None
    )
    excess_cost_all = sum(
        r.excess_cost_to_date for r in results
        if r.excess_cost_to_date is not None
    )
    return {
        "items_tracked": items_tracked,
        "items_flagged": items_flagged,
        "excess_cost_flagged": round(excess_cost_flagged, 2),
        "excess_cost_all": round(excess_cost_all, 2),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("purchase_csv", help="Path to purchase_history.csv")
    parser.add_argument("--creep-threshold", type=float, default=5.0)
    parser.add_argument("--spike-threshold", type=float, default=10.0)
    parser.add_argument("--json", default=None, help="Optional JSON report path")
    args = parser.parse_args(argv)

    purchases = load_purchases(Path(args.purchase_csv))
    results = detect_creep(
        purchases,
        creep_threshold=args.creep_threshold,
        spike_threshold=args.spike_threshold,
    )
    summary = summarize(results)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "items": [r.to_dict() for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"Vendor price creep detector ({len(results)} item(s)):")
    for r in results:
        if r.insufficient_history:
            print(f"  {r.vendor} / {r.item}: insufficient history ({r.purchases} purchase)")
        else:
            flags = f" [{', '.join(r.flags)}]" if r.flags else ""
            print(
                f"  {r.vendor} / {r.item}: "
                f"${r.baseline_price:,.2f} -> ${r.latest_price:,.2f} "
                f"({r.creep_pct:+.2f}%) "
                f"excess ${r.excess_cost_to_date:,.2f}{flags}"
            )
    print(f"Summary: {summary['items_tracked']} items tracked, "
          f"{summary['items_flagged']} flagged, "
          f"excess flagged ${summary['excess_cost_flagged']:,.2f}, "
          f"excess all ${summary['excess_cost_all']:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())