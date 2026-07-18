"""Bid/no-bid gate for contractor pursuits.

CSV columns (one row per chase):
  name, contract_value, pursuit_hours, expected_margin_pct, capacity_strain (1-5),
  mobilization_cash, weeks_to_first_pay, weekly_fixed_burn, landmine_count,
  contract_known (yes/no), political_override (yes/no)

Rules (first hard fail wins for NO-BID; conditions stack further):
  NO-BID if capacity_strain >= 5
  NO-BID if buffer_weeks_after_mob < 2
    buffer = (cash_on_hand - mobilization_cash) / weekly_fixed_burn
  BID-WITH-CONDITIONS if contract_known=no OR landmine_count >= 2 OR capacity_strain >= 4
    OR pursuit_tax / expected_margin > 0.5 OR political_override
  else BID

  pursuit_tax = pursuit_hours * 150

Usage:
  python3 scripts/bid_bond_gate.py fixtures/input/bids.csv --cash-on-hand 120000 --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional


def parse_float(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    return float(value) if value else default


def parse_int(value: str, default: int = 0) -> int:
    value = (value or "").strip()
    return int(float(value)) if value else default


def is_yes(value: str) -> bool:
    return (value or "").strip().lower() in {"y", "yes", "true", "1"}


def evaluate_row(row: Dict[str, str], cash_on_hand: float) -> dict:
    name = (row.get("name") or "").strip()
    value = parse_float(row.get("contract_value", "0"))
    hours = parse_float(row.get("pursuit_hours", "0"))
    margin_pct = parse_float(row.get("expected_margin_pct", "0"))
    strain = max(1, min(5, parse_int(row.get("capacity_strain", "1"), 1)))
    mobilization = parse_float(row.get("mobilization_cash", "0"))
    burn = parse_float(row.get("weekly_fixed_burn", "0"))
    landmines = parse_int(row.get("landmine_count", "0"))
    contract_known = is_yes(row.get("contract_known", "yes"))
    political = is_yes(row.get("political_override", "no"))

    expected_margin = value * (margin_pct / 100.0)
    pursuit_tax = hours * 150.0
    tax_ratio = (
        pursuit_tax / expected_margin if expected_margin > 0 else float("inf")
    )
    post_mob = cash_on_hand - mobilization
    buffer_weeks = post_mob / burn if burn > 0 else 99.0

    reasons: List[str] = []
    verdict = "BID"

    if strain >= 5:
        verdict = "NO-BID"
        reasons.append("capacity_strain>=5 (capacity hangover)")
    if buffer_weeks < 2.0:
        verdict = "NO-BID"
        reasons.append(f"cash storm buffer_weeks={buffer_weeks:.2f}")

    needs_conditions = (
        (not contract_known)
        or landmines >= 2
        or strain >= 4
        or tax_ratio > 0.5
        or political
    )
    if needs_conditions and verdict == "BID":
        verdict = "BID-WITH-CONDITIONS"
    if needs_conditions:
        if not contract_known:
            reasons.append("contract form unknown")
        if landmines >= 2:
            reasons.append(f"landmine_count={landmines}")
        if strain >= 4 and strain < 5:
            reasons.append(f"capacity_strain={strain}")
        if tax_ratio > 0.5 and tax_ratio != float("inf"):
            reasons.append(f"pursuit_tax_ratio={tax_ratio:.2f}")
        if tax_ratio == float("inf"):
            reasons.append("expected margin is zero/negative")
        if political:
            reasons.append("political override labeled (not clean BID)")

    if not reasons:
        reasons.append("clear capacity, cash, and landmines")

    return {
        "name": name,
        "verdict": verdict,
        "contract_value": value,
        "expected_margin_dollars": round(expected_margin, 2),
        "pursuit_tax": round(pursuit_tax, 2),
        "pursuit_tax_ratio": None if tax_ratio == float("inf") else round(tax_ratio, 3),
        "capacity_strain": strain,
        "buffer_weeks_after_mob": round(buffer_weeks, 2),
        "landmine_count": landmines,
        "contract_known": contract_known,
        "political_override": political,
        "reasons": reasons,
    }


def evaluate(rows: List[Dict[str, str]], cash_on_hand: float) -> dict:
    pursuits = [evaluate_row(row, cash_on_hand) for row in rows]
    counts = {"BID": 0, "BID-WITH-CONDITIONS": 0, "NO-BID": 0}
    for pursuit in pursuits:
        counts[pursuit["verdict"]] += 1
    return {
        "cash_on_hand": cash_on_hand,
        "counts": counts,
        "pursuits": pursuits,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--cash-on-hand", type=float, required=True)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    with args.csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    report = evaluate(rows, args.cash_on_hand)
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
