"""Daypart labor % gate: covers drive bodies, cut before OT.

CSV columns:
  business_date, daypart, covers, covers_plan, sales, scheduled_hours,
  actual_hours, wage_rate, skeleton_hours, target_labor_pct

labor_cost = actual_hours * wage_rate
labor_pct  = labor_cost / sales * 100  (missing if sales <= 0)

Actions per row:
  ok
  add_body          — covers > plan * 1.15 and hours near skeleton
  cut_before_ot     — labor_pct > target and covers < plan
  under_skeleton    — actual_hours < skeleton_hours
  over_target       — labor_pct > target_labor_pct

Usage:
  python3 scripts/labor_percent_guard.py fixtures/input/dayparts.csv --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_float(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    return float(value) if value else default


def load_dayparts(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "business_date": parse_date(row["business_date"]),
                    "daypart": (row.get("daypart") or "").strip().lower(),
                    "covers": parse_float(row.get("covers", "0")),
                    "covers_plan": parse_float(row.get("covers_plan", "0")),
                    "sales": parse_float(row.get("sales", "0")),
                    "scheduled_hours": parse_float(row.get("scheduled_hours", "0")),
                    "actual_hours": parse_float(row.get("actual_hours", "0")),
                    "wage_rate": parse_float(row.get("wage_rate", "0")),
                    "skeleton_hours": parse_float(row.get("skeleton_hours", "0")),
                    "target_labor_pct": parse_float(row.get("target_labor_pct", "30"), 30.0),
                }
            )
    return rows


def evaluate_row(row: dict) -> dict:
    labor_cost = round(row["actual_hours"] * row["wage_rate"], 2)
    labor_pct = (
        round(labor_cost / row["sales"] * 100.0, 2) if row["sales"] > 0 else None
    )
    flags: List[str] = []
    action = "ok"

    if row["actual_hours"] + 1e-9 < row["skeleton_hours"]:
        flags.append("under_skeleton")
        action = "under_skeleton"

    if labor_pct is not None and labor_pct > row["target_labor_pct"]:
        flags.append("over_target")
        if row["covers_plan"] > 0 and row["covers"] < row["covers_plan"]:
            flags.append("cut_before_ot")
            action = "cut_before_ot"
        elif action == "ok":
            action = "over_target"

    # Cover surge needs bodies even when skeleton hours are missing —
    # don't lose the signal under under_skeleton precedence.
    if (
        row["covers_plan"] > 0
        and row["covers"] > row["covers_plan"] * 1.15
        and row["actual_hours"] <= max(row["skeleton_hours"], 1.0) * 1.1
    ):
        flags.append("add_body")
        if action in {"ok", "under_skeleton"}:
            action = "add_body"

    return {
        "business_date": row["business_date"].isoformat(),
        "daypart": row["daypart"],
        "covers": row["covers"],
        "covers_plan": row["covers_plan"],
        "sales": row["sales"],
        "scheduled_hours": row["scheduled_hours"],
        "actual_hours": row["actual_hours"],
        "skeleton_hours": row["skeleton_hours"],
        "wage_rate": row["wage_rate"],
        "labor_cost": labor_cost,
        "labor_pct": labor_pct,
        "target_labor_pct": row["target_labor_pct"],
        "flags": flags,
        "action": action,
    }


def evaluate(rows: List[dict]) -> dict:
    results = [evaluate_row(row) for row in rows]
    action_counts: dict = {}
    for row in results:
        action_counts[row["action"]] = action_counts.get(row["action"], 0) + 1
    return {
        "leading_words": [
            "skeleton first",
            "flex list not hero list",
            "cut before OT",
            "covers drive bodies",
        ],
        "action_counts": action_counts,
        "dayparts": results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    report = evaluate(load_dayparts(args.csv_path))
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
