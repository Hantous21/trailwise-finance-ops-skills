"""Root-cause food-cost bleed by item from sales + recipe + waste inputs.

CSVs:
  sales.csv: item,units_sold,actual_cogs
  recipes.csv: item,recipe_unit_cost
  waste.csv (optional): item,waste_cost,bucket
    bucket one of: portion_drift,prep_waste,spoilage,shrink,wrong_recipe,
                   discount_comp,vendor_price,menu_engineering,other

Bleed:
  theoretical = units_sold * recipe_unit_cost
  actual = actual_cogs
  bleed = actual - theoretical
  bleed_pct = bleed / theoretical * 100 (if theoretical > 0)

Top culprits ranked by bleed dollars. Bucket rolls waste rows when present,
else unclassified.

Usage:
  python3 scripts/food_cost_bleed_map.py \
      --sales fixtures/input/sales.csv \
      --recipes fixtures/input/recipes.csv \
      --waste fixtures/input/waste.csv \
      --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

VALID_BUCKETS = {
    "portion_drift",
    "prep_waste",
    "spoilage",
    "shrink",
    "wrong_recipe",
    "discount_comp",
    "vendor_price",
    "menu_engineering",
    "other",
}


def parse_float(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    return float(value) if value else default


def load_map(path: Path, key: str, value_key: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get(key) or "").strip()
            if not name:
                continue
            out[name] = out.get(name, 0.0) + parse_float(row.get(value_key, "0"))
    return out


def load_sales(path: Path) -> Dict[str, dict]:
    sales: Dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item = (row.get("item") or "").strip()
            if not item:
                continue
            current = sales.setdefault(item, {"units_sold": 0.0, "actual_cogs": 0.0})
            current["units_sold"] += parse_float(row.get("units_sold", "0"))
            current["actual_cogs"] += parse_float(row.get("actual_cogs", "0"))
    return sales


def load_waste(path: Optional[Path]) -> Dict[str, dict]:
    waste: Dict[str, dict] = defaultdict(lambda: {"waste_cost": 0.0, "buckets": defaultdict(float)})
    if path is None or not path.exists():
        return waste
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item = (row.get("item") or "").strip()
            if not item:
                continue
            bucket = (row.get("bucket") or "other").strip().lower()
            if bucket not in VALID_BUCKETS:
                bucket = "other"
            amount = parse_float(row.get("waste_cost", "0"))
            waste[item]["waste_cost"] += amount
            waste[item]["buckets"][bucket] += amount
    return waste


def evaluate(sales_path: Path, recipes_path: Path, waste_path: Optional[Path] = None) -> dict:
    sales = load_sales(sales_path)
    recipes = load_map(recipes_path, "item", "recipe_unit_cost")
    waste = load_waste(waste_path)

    items: List[dict] = []
    theoretical_total = 0.0
    actual_total = 0.0
    for item, data in sales.items():
        units = data["units_sold"]
        actual = data["actual_cogs"]
        unit_cost = recipes.get(item)
        if unit_cost is None:
            theoretical = 0.0
            missing_recipe = True
        else:
            theoretical = units * unit_cost
            missing_recipe = False
        bleed = actual - theoretical
        bleed_pct = (bleed / theoretical * 100.0) if theoretical > 0 else None
        item_waste = waste.get(item, {"waste_cost": 0.0, "buckets": {}})
        buckets = dict(item_waste.get("buckets", {}))
        primary_bucket = "unclassified"
        if buckets:
            primary_bucket = max(buckets.items(), key=lambda kv: kv[1])[0]
        elif missing_recipe:
            primary_bucket = "wrong_recipe"
        theoretical_total += theoretical
        actual_total += actual
        items.append(
            {
                "item": item,
                "units_sold": units,
                "recipe_unit_cost": unit_cost,
                "theoretical_cogs": round(theoretical, 2),
                "actual_cogs": round(actual, 2),
                "bleed": round(bleed, 2),
                "bleed_pct": None if bleed_pct is None else round(bleed_pct, 2),
                "waste_cost": round(float(item_waste.get("waste_cost", 0.0)), 2),
                "primary_bucket": primary_bucket,
                "missing_recipe": missing_recipe,
            }
        )

    items.sort(key=lambda row: row["bleed"], reverse=True)
    bucket_totals: Dict[str, float] = defaultdict(float)
    for row in items:
        bucket_totals[row["primary_bucket"]] += row["bleed"]

    total_bleed = actual_total - theoretical_total
    return {
        "theoretical_total": round(theoretical_total, 2),
        "actual_total": round(actual_total, 2),
        "bleed_total": round(total_bleed, 2),
        "bleed_pct_total": round(total_bleed / theoretical_total * 100.0, 2)
        if theoretical_total > 0
        else None,
        "top_culprits": items[:5],
        "items": items,
        "bucket_totals": {
            key: round(value, 2)
            for key, value in sorted(bucket_totals.items(), key=lambda kv: -kv[1])
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sales", type=Path, required=True)
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--waste", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    report = evaluate(args.sales, args.recipes, args.waste)
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
