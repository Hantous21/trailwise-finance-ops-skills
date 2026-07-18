"""Score pre-invoice revenue ghosts and segment hot/warm/cold queues.

CSV columns:
  who, offer, amount, first_sent, last_touch, channel, status_guess, blocker,
  reply_warmth (0-10), product_fit (0-10), effort_to_restart (0-10, higher=harder)

Scoring (0-100):
  size 0-30 (relative to portfolio max amount)
  recency 0-25 (from last_touch vs as_of)
  reply_warmth 0-20 (warmth * 2)
  product_fit 0-15 (fit * 1.5)
  effort 0-10 (10 - effort_to_restart)

Queues: hot >=70, warm 40-69, cold <40, do-not-chase if status_guess=internal-hard-no

Usage:
  python3 scripts/revenue_ghost_hunter.py fixtures/input/ghosts.csv --as-of 2026-07-01 --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

VALID_STATUS = {
    "no-response",
    "price-stall",
    "competitor",
    "timing",
    "internal-hard-no",
    "unclear",
}
DO_NOT_CHASE = {"internal-hard-no"}


def parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value or value.lower() in {"nan", "none", "nat"}:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_float(value: str, default: float = 0.0) -> float:
    value = (value or "").strip()
    if not value or value.lower() in {"nan", "none"}:
        return default
    return float(value)


@dataclass
class Ghost:
    who: str
    offer: str
    amount: float
    first_sent: Optional[date]
    last_touch: Optional[date]
    channel: str
    status_guess: str
    blocker: str
    reply_warmth: float
    product_fit: float
    effort_to_restart: float
    score: float = 0.0
    queue: str = ""
    do_not_chase: bool = False
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["first_sent"] = self.first_sent.isoformat() if self.first_sent else None
        d["last_touch"] = self.last_touch.isoformat() if self.last_touch else None
        return d


def recency_points(days_since: Optional[int]) -> float:
    if days_since is None:
        return 5.0
    if days_since <= 7:
        return 25.0
    if days_since <= 14:
        return 20.0
    if days_since <= 30:
        return 15.0
    if days_since <= 60:
        return 8.0
    return 2.0


def size_points(amount: float, max_amount: float) -> float:
    if max_amount <= 0:
        return 0.0
    return 30.0 * min(max(amount, 0.0) / max_amount, 1.0)


def score_ghost(ghost: Ghost, as_of: date, max_amount: float) -> Ghost:
    ghost.do_not_chase = ghost.status_guess in DO_NOT_CHASE
    if ghost.do_not_chase:
        ghost.score = 0.0
        ghost.queue = "do-not-chase"
        ghost.components = {
            "size": 0.0,
            "recency": 0.0,
            "warmth": 0.0,
            "fit": 0.0,
            "effort": 0.0,
        }
        return ghost

    days_since = None
    if ghost.last_touch is not None:
        days_since = (as_of - ghost.last_touch).days

    size = size_points(ghost.amount, max_amount)
    recency = recency_points(days_since)
    warmth = max(0.0, min(10.0, ghost.reply_warmth)) * 2.0
    fit = max(0.0, min(10.0, ghost.product_fit)) * 1.5
    effort = max(0.0, 10.0 - max(0.0, min(10.0, ghost.effort_to_restart)))
    ghost.score = round(size + recency + warmth + fit + effort, 1)
    ghost.components = {
        "size": round(size, 1),
        "recency": round(recency, 1),
        "warmth": round(warmth, 1),
        "fit": round(fit, 1),
        "effort": round(effort, 1),
    }
    if ghost.score >= 70:
        ghost.queue = "hot"
    elif ghost.score >= 40:
        ghost.queue = "warm"
    else:
        ghost.queue = "cold"
    return ghost


def load_ghosts(path: Path) -> List[Ghost]:
    ghosts: List[Ghost] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            status = (row.get("status_guess") or "unclear").strip().lower()
            if status not in VALID_STATUS:
                status = "unclear"
            ghosts.append(
                Ghost(
                    who=(row.get("who") or "").strip(),
                    offer=(row.get("offer") or "").strip(),
                    amount=parse_float(row.get("amount", "0")),
                    first_sent=parse_date(row.get("first_sent", "")),
                    last_touch=parse_date(row.get("last_touch", "")),
                    channel=(row.get("channel") or "").strip(),
                    status_guess=status,
                    blocker=(row.get("blocker") or "").strip(),
                    reply_warmth=parse_float(row.get("reply_warmth", "0")),
                    product_fit=parse_float(row.get("product_fit", "5"), 5.0),
                    effort_to_restart=parse_float(row.get("effort_to_restart", "5"), 5.0),
                )
            )
    return ghosts


def evaluate(ghosts: List[Ghost], as_of: date) -> dict:
    chaseable_amounts = [
        g.amount for g in ghosts if g.status_guess not in DO_NOT_CHASE
    ]
    max_amount = max(chaseable_amounts, default=0.0)
    scored = [score_ghost(g, as_of, max_amount) for g in ghosts]
    scored.sort(key=lambda g: (-g.score, g.who.lower()))
    queues = {"hot": [], "warm": [], "cold": [], "do-not-chase": []}
    for ghost in scored:
        queues[ghost.queue].append(ghost.to_dict())
    chaseable = [g for g in scored if not g.do_not_chase]
    return {
        "as_of": as_of.isoformat(),
        "count": len(scored),
        "dollars_at_risk": round(sum(g.amount for g in chaseable), 2),
        "queue_counts": {key: len(value) for key, value in queues.items()},
        "queues": queues,
        "ranked": [g.to_dict() for g in scored],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    report = evaluate(load_ghosts(args.csv_path), as_of)
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
