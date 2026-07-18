"""30-day cash weather from bank balance + scheduled cash events.

CSV columns:
  date (YYYY-MM-DD), amount (+in / -out), lane, label

Lanes:
  confirmed, near_certain, hoped, committed, flexible

Weather bands (per week of fixed cover after base balance):
  sunny  > 4 weeks fixed cover and no load-bearing hoped inflow
  cloudy 2-4 weeks OR hoped inflow >= one week of fixed costs
  storm  base balance < safety floor (default 2 weeks fixed)

Usage:
  python3 scripts/cash_weather_report.py fixtures/input/events.csv \
      --opening 50000 --fixed-weekly 8000 --as-of 2026-07-01 --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

LANES = {"confirmed", "near_certain", "hoped", "committed", "flexible"}


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def load_events(path: Path) -> List[dict]:
    events: List[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            lane = (row.get("lane") or "hoped").strip().lower()
            if lane not in LANES:
                lane = "hoped"
            events.append(
                {
                    "date": parse_date(row["date"]),
                    "amount": float(row["amount"]),
                    "lane": lane,
                    "label": (row.get("label") or "").strip(),
                }
            )
    return events


def week_ends(as_of: date, days: int = 30) -> List[date]:
    end = as_of + timedelta(days=days)
    ends: List[date] = []
    cursor = as_of
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=6), end)
        ends.append(chunk_end)
        cursor = chunk_end + timedelta(days=1)
    return ends


def evaluate(
    events: List[dict],
    opening: float,
    fixed_weekly: float,
    as_of: date,
    safety_weeks: float = 2.0,
    days: int = 30,
) -> dict:
    if fixed_weekly <= 0:
        raise ValueError("fixed_weekly must be > 0")

    safety_floor = fixed_weekly * safety_weeks
    bal_base = opening
    bal_stress = opening
    weeks_out: List[dict] = []
    storm_windows: List[dict] = []
    ends = week_ends(as_of, days)

    for index, week_end in enumerate(ends):
        week_start = as_of if index == 0 else ends[index - 1] + timedelta(days=1)
        base_delta = 0.0
        stress_delta = 0.0
        hoped_inflow = 0.0
        labels: List[str] = []

        for event in events:
            if not (week_start <= event["date"] <= week_end):
                continue
            labels.append(event["label"] or event["lane"])
            amount = event["amount"]
            lane = event["lane"]
            if lane in {"confirmed", "committed"}:
                base_delta += amount
                stress_delta += amount
            elif lane == "near_certain":
                base_delta += amount
                stress_delta += amount * (0.5 if amount > 0 else 1.0)
            elif lane == "hoped":
                if amount > 0:
                    hoped_inflow += amount
            elif lane == "flexible":
                if amount < 0:
                    base_delta += amount
                    stress_delta += amount * 0.5
                else:
                    base_delta += amount
                    stress_delta += amount

        # Model operating burn when not already encoded in events.
        base_delta -= fixed_weekly
        stress_delta -= fixed_weekly
        bal_base += base_delta
        bal_stress += stress_delta
        cover_weeks = bal_base / fixed_weekly

        if bal_base < safety_floor:
            weather = "storm"
            storm_windows.append(
                {
                    "week_ending": week_end.isoformat(),
                    "base_balance": round(bal_base, 2),
                }
            )
        elif cover_weeks < 4 or hoped_inflow >= fixed_weekly:
            weather = "cloudy"
        else:
            weather = "sunny"

        weeks_out.append(
            {
                "week_ending": week_end.isoformat(),
                "base_delta": round(base_delta, 2),
                "base_balance": round(bal_base, 2),
                "stress_balance": round(bal_stress, 2),
                "hoped_inflow": round(hoped_inflow, 2),
                "weeks_of_fixed_cover": round(cover_weeks, 2),
                "weather": weather,
                "labels": labels,
            }
        )

    rank = {"sunny": 0, "cloudy": 1, "storm": 2}
    overall = "sunny"
    for week in weeks_out:
        if rank[week["weather"]] > rank[overall]:
            overall = week["weather"]

    return {
        "as_of": as_of.isoformat(),
        "opening": opening,
        "fixed_weekly": fixed_weekly,
        "safety_floor": round(safety_floor, 2),
        "overall_weather": overall,
        "storm_windows": storm_windows,
        "weeks": weeks_out,
        "closing_base": round(bal_base, 2),
        "closing_stress": round(bal_stress, 2),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--opening", type=float, required=True)
    parser.add_argument("--fixed-weekly", type=float, required=True)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--safety-weeks", type=float, default=2.0)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    report = evaluate(
        load_events(args.csv_path),
        args.opening,
        args.fixed_weekly,
        as_of,
        args.safety_weeks,
    )
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
