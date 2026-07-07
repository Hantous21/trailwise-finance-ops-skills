"""Deterministic rule-based transaction allocation to jobs and cost codes."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VALID_FIELDS = {"vendor", "description"}


@dataclass(frozen=True)
class Rule:
    priority: int
    match_field: str
    pattern: str
    job_number: str
    cost_code: str
    order: int  # file order for tie-break

    def __post_init__(self) -> None:
        if self.match_field not in VALID_FIELDS:
            raise ValueError(
                f"unknown match_field {self.match_field!r}; must be one of {sorted(VALID_FIELDS)}"
            )
        if not self.pattern.strip():
            raise ValueError("pattern cannot be empty")
        if not self.job_number.strip() or not self.cost_code.strip():
            raise ValueError("job_number and cost_code are required")


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    date: str
    vendor: str
    description: str
    amount: float
    account: str

    def __post_init__(self) -> None:
        if not self.txn_id.strip():
            raise ValueError("txn_id is required")
        if self.amount < 0:
            raise ValueError(f"amount cannot be negative for {self.txn_id}")


def load_rules(path: Path) -> list[Rule]:
    rules: list[Rule] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return rules
        required = ("priority", "match_field", "pattern", "job_number", "cost_code")
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for order, row in enumerate(reader):
            if not any((row.get(c) or "").strip() for c in required):
                continue
            try:
                rules.append(Rule(
                    priority=int(row["priority"]),
                    match_field=(row["match_field"] or "").strip(),
                    pattern=(row["pattern"] or "").strip(),
                    job_number=(row["job_number"] or "").strip(),
                    cost_code=(row["cost_code"] or "").strip(),
                    order=order,
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: rule {row}: {exc}") from exc
    rules.sort(key=lambda r: (r.priority, r.order))
    return rules


def load_transactions(path: Path) -> list[Transaction]:
    txns: list[Transaction] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return txns
        required = ("txn_id", "date", "vendor", "description", "amount", "account")
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if not any((row.get(c) or "").strip() for c in required):
                continue
            try:
                txns.append(Transaction(
                    txn_id=(row["txn_id"] or "").strip(),
                    date=(row["date"] or "").strip(),
                    vendor=(row["vendor"] or "").strip(),
                    description=(row["description"] or "").strip(),
                    amount=float(row["amount"]),
                    account=(row["account"] or "").strip(),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return txns


def _match(rule: Rule, txn: Transaction) -> bool:
    haystack = (getattr(txn, rule.match_field) or "").lower()
    return rule.pattern.lower() in haystack


def allocate(
    transactions: Iterable[Transaction],
    rules: list[Rule],
) -> dict[str, object]:
    rules = sorted(rules, key=lambda r: (r.priority, r.order))
    rows: list[dict[str, object]] = []
    allocated_count = 0
    unallocated_count = 0
    review_queue: list[dict[str, object]] = []
    by_job: dict[str, float] = defaultdict(float)

    for txn in transactions:
        matched: Rule | None = None
        for rule in rules:
            if _match(rule, txn):
                matched = rule
                break
        if matched is None:
            unallocated_count += 1
            row = {
                "txn_id": txn.txn_id,
                "date": txn.date,
                "vendor": txn.vendor,
                "description": txn.description,
                "amount": round(txn.amount, 2),
                "account": txn.account,
                "job_number": None,
                "cost_code": None,
                "rule_priority": None,
                "status": "unallocated",
            }
            review_queue.append(row)
        else:
            allocated_count += 1
            by_job[matched.job_number] += txn.amount
            row = {
                "txn_id": txn.txn_id,
                "date": txn.date,
                "vendor": txn.vendor,
                "description": txn.description,
                "amount": round(txn.amount, 2),
                "account": txn.account,
                "job_number": matched.job_number,
                "cost_code": matched.cost_code,
                "rule_priority": matched.priority,
                "status": "allocated",
            }
        rows.append(row)

    total = allocated_count + unallocated_count
    allocated_pct = (allocated_count / total * 100) if total else 0.0
    return {
        "transaction_count": total,
        "allocated_count": allocated_count,
        "unallocated_count": unallocated_count,
        "allocated_pct": round(allocated_pct, 2),
        "by_job": {k: round(v, 2) for k, v in sorted(by_job.items())},
        "review_queue": review_queue,
        "review_queue_total": round(sum(t["amount"] for t in review_queue), 2),  # type: ignore[arg-type]
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Allocate transactions to jobs via rules.")
    parser.add_argument("transactions", type=Path)
    parser.add_argument("rules", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, default=None)
    parser.add_argument("--min-allocated-pct", type=float, default=0.0,
                        help="Exit 1 if allocated %% is below this (default 0)")
    args = parser.parse_args(argv)

    txns = load_transactions(args.transactions)
    rules = load_rules(args.rules)
    report = allocate(txns, rules)

    if args.json_path is not None:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Allocated {report['allocated_count']}/{report['transaction_count']} "
          f"({report['allocated_pct']}%); review queue {report['unallocated_count']} "
          f"(${report['review_queue_total']:.2f})")
    for job, total in report["by_job"].items():  # type: ignore[union-attr]
        print(f"  {job}: {total:.2f}")
    if report["allocated_pct"] < args.min_allocated_pct:  # type: ignore[operator]
        print(f"FAIL: allocated_pct {report['allocated_pct']} < min {args.min_allocated_pct}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
