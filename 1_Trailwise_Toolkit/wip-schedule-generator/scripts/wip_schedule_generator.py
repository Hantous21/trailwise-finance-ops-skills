"""Deterministic cost-to-cost WIP schedule with over/under billing flags."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WIPJob:
    job_number: str
    job_name: str
    contract_amount: float
    approved_change_orders: float
    estimated_total_cost: float
    cost_to_date: float
    billed_to_date: float

    def __post_init__(self) -> None:
        if not self.job_number.strip():
            raise ValueError("job_number is required")
        for field in (
            "contract_amount",
            "approved_change_orders",
            "estimated_total_cost",
            "cost_to_date",
            "billed_to_date",
        ):
            if getattr(self, field) < 0:
                raise ValueError(f"{field} cannot be negative for {self.job_number}")


def evaluate(
    job: WIPJob,
    underbilling_alert_amount: float = 25000.0,
    underbilling_alert_pct: float = 5.0,
) -> dict[str, object]:
    if job.estimated_total_cost <= 0:
        raise ValueError(
            f"estimated_total_cost must be > 0 for {job.job_number} "
            f"(got {job.estimated_total_cost})"
        )

    revised_contract = round(job.contract_amount + job.approved_change_orders, 2)
    raw_percent = job.cost_to_date / job.estimated_total_cost
    percent_complete = min(round(raw_percent, 6), 1.0)
    earned_revenue = round(percent_complete * revised_contract, 2)
    over_under = round(job.billed_to_date - earned_revenue, 2)
    estimated_gross_profit = round(revised_contract - job.estimated_total_cost, 2)
    gross_profit_pct = (
        round(estimated_gross_profit / revised_contract * 100, 2)
        if revised_contract > 0
        else 0.0
    )
    remaining_to_bill = round(revised_contract - job.billed_to_date, 2)

    flags: list[str] = []
    if raw_percent > 1.0:
        flags.append("percent_complete_over_100")
    if job.estimated_total_cost > revised_contract:
        flags.append("cost_overrun")
    if job.billed_to_date > revised_contract:
        flags.append("billed_over_contract")
    if over_under < 0:
        under_amt = abs(over_under)
        under_pct = (under_amt / revised_contract * 100) if revised_contract > 0 else 0.0
        if under_amt > underbilling_alert_amount or under_pct > underbilling_alert_pct:
            flags.append("underbilled_above_threshold")

    return {
        "job_number": job.job_number,
        "job_name": job.job_name,
        "contract_amount": round(job.contract_amount, 2),
        "approved_change_orders": round(job.approved_change_orders, 2),
        "revised_contract": revised_contract,
        "estimated_total_cost": round(job.estimated_total_cost, 2),
        "cost_to_date": round(job.cost_to_date, 2),
        "billed_to_date": round(job.billed_to_date, 2),
        "raw_percent_complete": round(raw_percent, 6),
        "percent_complete": percent_complete,
        "earned_revenue": earned_revenue,
        "over_under": over_under,
        "estimated_gross_profit": estimated_gross_profit,
        "gross_profit_pct": gross_profit_pct,
        "remaining_to_bill": remaining_to_bill,
        "flags": flags,
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    total_overbilled = 0.0
    total_underbilled = 0.0
    total_earned = 0.0
    total_billed = 0.0
    jobs_flagged = 0
    for row in rows:
        ou = float(row["over_under"])  # type: ignore[arg-type]
        if ou > 0:
            total_overbilled += ou
        elif ou < 0:
            total_underbilled += abs(ou)
        total_earned += float(row["earned_revenue"])  # type: ignore[arg-type]
        total_billed += float(row["billed_to_date"])  # type: ignore[arg-type]
        if row["flags"]:
            jobs_flagged += 1
    return {
        "job_count": len(rows),
        "jobs_flagged": jobs_flagged,
        "total_overbilled": round(total_overbilled, 2),
        "total_underbilled": round(total_underbilled, 2),
        "total_earned": round(total_earned, 2),
        "total_billed": round(total_billed, 2),
        "as_of": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# CSV / I/O
# ---------------------------------------------------------------------------


REQUIRED_COLUMNS = (
    "job_number",
    "job_name",
    "contract_amount",
    "approved_change_orders",
    "estimated_total_cost",
    "cost_to_date",
    "billed_to_date",
)


def load_jobs(path: Path) -> list[WIPJob]:
    jobs: list[WIPJob] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return jobs
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if not any((row.get(c) or "").strip() for c in REQUIRED_COLUMNS):
                continue
            try:
                jobs.append(
                    WIPJob(
                        job_number=(row["job_number"] or "").strip(),
                        job_name=(row["job_name"] or "").strip(),
                        contract_amount=float(row["contract_amount"]),
                        approved_change_orders=float(row["approved_change_orders"]),
                        estimated_total_cost=float(row["estimated_total_cost"]),
                        cost_to_date=float(row["cost_to_date"]),
                        billed_to_date=float(row["billed_to_date"]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return jobs


def run(
    jobs: Iterable[WIPJob],
    underbilling_alert_amount: float = 25000.0,
    underbilling_alert_pct: float = 5.0,
) -> dict[str, object]:
    rows = [evaluate(j, underbilling_alert_amount, underbilling_alert_pct) for j in jobs]
    return {"jobs": rows, "summary": summarize(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a WIP schedule (cost-to-cost).")
    parser.add_argument("input", type=Path, help="CSV of jobs")
    parser.add_argument("--json", dest="json_path", type=Path, default=None,
                        help="Write the full report to this JSON file")
    parser.add_argument("--underbilling-alert-amount", type=float, default=25000.0)
    parser.add_argument("--underbilling-alert-pct", type=float, default=5.0)
    args = parser.parse_args(argv)

    jobs = load_jobs(args.input)
    report = run(jobs, args.underbilling_alert_amount, args.underbilling_alert_pct)

    if args.json_path is not None:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["summary"]
    print(f"WIP schedule: {summary['job_count']} jobs, "
          f"{summary['jobs_flagged']} flagged")
    print(f"  total earned:   {summary['total_earned']:>12.2f}")
    print(f"  total billed:   {summary['total_billed']:>12.2f}")
    print(f"  total overbilled:  {summary['total_overbilled']:>10.2f}")
    print(f"  total underbilled: {summary['total_underbilled']:>10.2f}")
    for row in report["jobs"]:  # type: ignore[union-attr]
        flags = ",".join(row["flags"]) if row["flags"] else "-"
        print(f"  {row['job_number']}  pct={float(row['percent_complete']):.2%} "
              f"earned={float(row['earned_revenue']):>10.2f} "
              f"over_under={float(row['over_under']):>+10.2f}  flags={flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
