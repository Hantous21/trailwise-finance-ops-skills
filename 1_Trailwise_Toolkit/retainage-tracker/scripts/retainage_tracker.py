"""Deterministic retainage receivable and release-milestone tracker."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


VALID_TOLERANCE = 1.00
DEFAULT_RELEASE_DUE_DAYS = 45


@dataclass(frozen=True)
class Draw:
    project: str
    draw_number: int
    invoice_date: date
    gross_billed: float
    retainage_pct: float
    retainage_withheld: float
    retainage_released: float
    substantial_completion_date: date | None

    def __post_init__(self) -> None:
        if not self.project.strip():
            raise ValueError("project is required")
        if self.draw_number < 1:
            raise ValueError("draw_number must be >= 1")
        for f in ("gross_billed", "retainage_withheld", "retainage_released"):
            if getattr(self, f) < 0:
                raise ValueError(f"{f} cannot be negative for {self.project} draw {self.draw_number}")
        if not 0 <= self.retainage_pct <= 100:
            raise ValueError(
                f"retainage_pct must be between 0 and 100 for {self.project} draw {self.draw_number}"
            )


def evaluate(
    draws: list[Draw],
    as_of: date,
    tolerance: float = VALID_TOLERANCE,
    release_due_days: int = DEFAULT_RELEASE_DUE_DAYS,
) -> dict[str, object]:
    by_project: dict[str, list[Draw]] = defaultdict(list)
    for d in draws:
        by_project[d.project].append(d)

    projects_out: list[dict[str, object]] = []
    total_outstanding = 0.0
    for project, project_draws in by_project.items():
        project_draws.sort(key=lambda d: d.draw_number)
        row_flags: list[str] = []
        rows_out: list[dict[str, object]] = []
        total_withheld = 0.0
        total_released = 0.0
        pcts: set[float] = set()
        completion: date | None = None
        for d in project_draws:
            expected = round(d.gross_billed * d.retainage_pct / 100, 2)
            if abs(d.retainage_withheld - expected) > tolerance:
                row_flags.append("withholding_mismatch")
            total_withheld += d.retainage_withheld
            total_released += d.retainage_released
            pcts.add(d.retainage_pct)
            if d.substantial_completion_date is not None and completion is None:
                completion = d.substantial_completion_date
            rows_out.append({
                "draw_number": d.draw_number,
                "invoice_date": d.invoice_date.isoformat(),
                "gross_billed": round(d.gross_billed, 2),
                "retainage_pct": d.retainage_pct,
                "expected_withheld": expected,
                "retainage_withheld": round(d.retainage_withheld, 2),
                "retainage_released": round(d.retainage_released, 2),
            })

        if len(pcts) > 1:
            row_flags.append("retainage_rate_change")
        outstanding = round(total_withheld - total_released, 2)
        if total_released > total_withheld:
            row_flags.append("over_release")
        days_since_completion: int | None = None
        if completion is not None and outstanding > 0:
            days_since_completion = (as_of - completion).days
            if days_since_completion > release_due_days:
                row_flags.append("release_overdue")

        if outstanding > 0:
            total_outstanding += outstanding

        projects_out.append({
            "project": project,
            "draw_count": len(project_draws),
            "total_withheld": round(total_withheld, 2),
            "total_released": round(total_released, 2),
            "outstanding": outstanding,
            "substantial_completion_date": completion.isoformat() if completion else None,
            "days_since_completion": days_since_completion,
            "flags": row_flags,
            "draws": rows_out,
        })

    return {
        "as_of": as_of.isoformat(),
        "project_count": len(projects_out),
        "total_outstanding_receivable": round(total_outstanding, 2),
        "projects": projects_out,
    }


REQUIRED_COLUMNS = (
    "project", "draw_number", "invoice_date", "gross_billed", "retainage_pct",
    "retainage_withheld", "retainage_released", "substantial_completion_date",
)


def _parse_date_or_none(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    return date.fromisoformat(s)


def load_draws(path: Path) -> list[Draw]:
    draws: list[Draw] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return draws
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if not any((row.get(c) or "").strip() for c in REQUIRED_COLUMNS):
                continue
            try:
                draws.append(Draw(
                    project=(row["project"] or "").strip(),
                    draw_number=int(row["draw_number"]),
                    invoice_date=date.fromisoformat((row["invoice_date"] or "").strip()),
                    gross_billed=float(row["gross_billed"]),
                    retainage_pct=float(row["retainage_pct"]),
                    retainage_withheld=float(row["retainage_withheld"]),
                    retainage_released=float(row["retainage_released"]),
                    substantial_completion_date=_parse_date_or_none(row["substantial_completion_date"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return draws


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retainage receivable tracker.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--as-of", dest="as_of", type=str, default=None,
                        help="As-of date YYYY-MM-DD (default: today)")
    parser.add_argument("--json", dest="json_path", type=Path, default=None)
    parser.add_argument("--tolerance", type=float, default=VALID_TOLERANCE)
    parser.add_argument("--release-due-days", type=int, default=DEFAULT_RELEASE_DUE_DAYS)
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    report = evaluate(load_draws(args.input), as_of, args.tolerance, args.release_due_days)
    if args.json_path is not None:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Retainage as of {report['as_of']}: "
          f"{report['project_count']} projects, "
          f"outstanding {report['total_outstanding_receivable']:.2f}")
    for p in report["projects"]:  # type: ignore[union-attr]
        flags = ",".join(p["flags"]) if p["flags"] else "-"
        days = p["days_since_completion"]
        days_s = f"{days}d" if days is not None else "-"
        print(f"  {p['project']}: outstanding={p['outstanding']:.2f} "
              f"days_since_completion={days_s} flags={flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
