"""End-of-night drawer variance spine with fixed dollar thresholds.

Defaults (replace previous $X / $Y placeholders):
  recount_max_abs = 5.00   — |variance| <= this: OK / free re-count self-service
  dual_count_min  = 20.00  — |variance| >= this: manager dual count required
  escalate_min    = 50.00  — |variance| >= this: escalate + named owner required

Between recount_max and dual_count: recount with second person preferred.
Action ladder:
  ok | recount | dual_count | escalate

CSV columns:
  business_date, drawer_id, expected_cash, counted_cash,
  expected_card, pos_card, voids, comps, tip_pool, net_sales, owner

Usage:
  python3 scripts/drawer_truth_close.py fixtures/input/closes.csv --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional


DEFAULT_RECOUNT_MAX = 5.0
DEFAULT_DUAL_COUNT_MIN = 20.0
DEFAULT_ESCALATE_MIN = 50.0


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_float(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    return float(value) if value else default


@dataclass
class DrawerClose:
    business_date: date
    drawer_id: str
    expected_cash: float
    counted_cash: float
    expected_card: float
    pos_card: float
    voids: float
    comps: float
    tip_pool: float
    net_sales: float
    owner: str

    @property
    def cash_variance(self) -> float:
        return round(self.counted_cash - self.expected_cash, 2)

    @property
    def card_variance(self) -> float:
        return round(self.pos_card - self.expected_card, 2)


def classify_action(
    abs_variance: float,
    recount_max: float = DEFAULT_RECOUNT_MAX,
    dual_min: float = DEFAULT_DUAL_COUNT_MIN,
    escalate_min: float = DEFAULT_ESCALATE_MIN,
) -> str:
    if abs_variance <= recount_max:
        return "ok"
    if abs_variance >= escalate_min:
        return "escalate"
    if abs_variance >= dual_min:
        return "dual_count"
    return "recount"


def classify_variance_class(cash_var: float, voids: float, comps: float) -> str:
    """Lightweight primary class for morning packet language."""
    abs_v = abs(cash_var)
    if abs_v <= DEFAULT_RECOUNT_MAX:
        return "in_tolerance"
    if voids > 0 and abs_v <= voids:
        return "mis_ring"
    if comps > 0 and abs_v <= comps:
        return "comp_related"
    if cash_var < 0:
        return "short"
    return "over"


def load_closes(path: Path) -> List[DrawerClose]:
    rows: List[DrawerClose] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                DrawerClose(
                    business_date=parse_date(row["business_date"]),
                    drawer_id=(row.get("drawer_id") or "").strip(),
                    expected_cash=parse_float(row.get("expected_cash", "0")),
                    counted_cash=parse_float(row.get("counted_cash", "0")),
                    expected_card=parse_float(row.get("expected_card", "0")),
                    pos_card=parse_float(row.get("pos_card", "0")),
                    voids=parse_float(row.get("voids", "0")),
                    comps=parse_float(row.get("comps", "0")),
                    tip_pool=parse_float(row.get("tip_pool", "0")),
                    net_sales=parse_float(row.get("net_sales", "0")),
                    owner=(row.get("owner") or "").strip() or "UNASSIGNED",
                )
            )
    return rows


def evaluate(
    closes: List[DrawerClose],
    recount_max: float = DEFAULT_RECOUNT_MAX,
    dual_min: float = DEFAULT_DUAL_COUNT_MIN,
    escalate_min: float = DEFAULT_ESCALATE_MIN,
) -> dict:
    spine = [
        "stop_sales",
        "apply_tip_rules",
        "count_drawer",
        "pos_z",
        "deposit_bag",
        "photo_log",
    ]
    results = []
    for row in closes:
        cash_var = row.cash_variance
        action = classify_action(abs(cash_var), recount_max, dual_min, escalate_min)
        variance_class = classify_variance_class(cash_var, row.voids, row.comps)
        owner_required = action in {"dual_count", "escalate"} or row.owner == "UNASSIGNED"
        results.append(
            {
                "business_date": row.business_date.isoformat(),
                "drawer_id": row.drawer_id,
                "expected_cash": row.expected_cash,
                "counted_cash": row.counted_cash,
                "cash_variance": cash_var,
                "card_variance": row.card_variance,
                "voids": row.voids,
                "comps": row.comps,
                "tip_pool": row.tip_pool,
                "net_sales": row.net_sales,
                "owner": row.owner,
                "action": action,
                "variance_class": variance_class,
                "owner_required": owner_required,
                "morning_packet": {
                    "sales": row.net_sales,
                    "comps": row.comps,
                    "voids": row.voids,
                    "cash_variance": cash_var,
                    "owner": row.owner if row.owner != "UNASSIGNED" else None,
                    "action": action,
                },
            }
        )

    action_counts = {"ok": 0, "recount": 0, "dual_count": 0, "escalate": 0}
    for row in results:
        action_counts[row["action"]] += 1

    return {
        "thresholds": {
            "recount_max_abs": recount_max,
            "dual_count_min": dual_min,
            "escalate_min": escalate_min,
        },
        "close_spine": spine,
        "action_counts": action_counts,
        "drawers": results,
        "unassigned_owner_count": sum(1 for r in results if r["owner"] == "UNASSIGNED"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--recount-max", type=float, default=DEFAULT_RECOUNT_MAX)
    parser.add_argument("--dual-count-min", type=float, default=DEFAULT_DUAL_COUNT_MIN)
    parser.add_argument("--escalate-min", type=float, default=DEFAULT_ESCALATE_MIN)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    report = evaluate(
        load_closes(args.csv_path),
        args.recount_max,
        args.dual_count_min,
        args.escalate_min,
    )
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
