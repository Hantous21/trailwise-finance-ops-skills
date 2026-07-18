"""Rank repeated customer intents by staff time × risk for a killlist.

Score = volume * minutes_per_answer * wrong_answer_risk
Higher score = higher kill priority.

CSV columns:
  intent, example, volume, minutes_per_answer, wrong_answer_risk (1-5),
  current_home, gap (yes/no), tag (pre-sale|post-sale|logistics|billing|complaint|edge-case)

Usage:
  python3 scripts/repeat_question_killlist.py fixtures/input/intents.csv --top 10 --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List, Optional

VALID_TAGS = {
    "pre-sale",
    "post-sale",
    "logistics",
    "billing",
    "complaint",
    "edge-case",
}


def parse_float(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    return float(value) if value else default


def is_yes(value: str) -> bool:
    return (value or "").strip().lower() in {"y", "yes", "true", "1"}


def load_intents(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            tag = (row.get("tag") or "post-sale").strip().lower()
            if tag not in VALID_TAGS:
                tag = "post-sale"
            risk = parse_float(row.get("wrong_answer_risk", "1"), 1.0)
            risk = max(1.0, min(5.0, risk))
            volume = parse_float(row.get("volume", "0"))
            minutes = parse_float(row.get("minutes_per_answer", "0"))
            rows.append(
                {
                    "intent": (row.get("intent") or "").strip(),
                    "example": (row.get("example") or "").strip(),
                    "volume": volume,
                    "minutes_per_answer": minutes,
                    "wrong_answer_risk": risk,
                    "current_home": (row.get("current_home") or "").strip(),
                    "gap": is_yes(row.get("gap", "yes")),
                    "tag": tag,
                    "score": round(volume * minutes * risk, 2),
                }
            )
    return rows


def evaluate(rows: List[dict], top: int = 10) -> dict:
    prepared: List[dict] = []
    for row in rows:
        item = dict(row)
        volume = float(item.get("volume") or 0.0)
        minutes = float(item.get("minutes_per_answer") or 0.0)
        risk = max(1.0, min(5.0, float(item.get("wrong_answer_risk") or 1.0)))
        item["volume"] = volume
        item["minutes_per_answer"] = minutes
        item["wrong_answer_risk"] = risk
        item["score"] = round(volume * minutes * risk, 2)
        item["intent"] = str(item.get("intent") or "")
        item.setdefault("example", "")
        item.setdefault("current_home", "")
        item.setdefault("gap", True)
        item.setdefault("tag", "post-sale")
        prepared.append(item)

    ranked = sorted(
        prepared,
        key=lambda r: (-r["score"], -r["volume"], r["intent"].lower()),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    killlist = ranked[: max(top, 0)]
    hours_saved_if_deflected = round(
        sum(r["volume"] * r["minutes_per_answer"] for r in killlist) / 60.0, 2
    )
    return {
        "count": len(ranked),
        "top_n": top,
        "hours_in_top_if_answered_live": hours_saved_if_deflected,
        "killlist": killlist,
        "all_ranked": ranked,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    report = evaluate(load_intents(args.csv_path), top=args.top)
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
