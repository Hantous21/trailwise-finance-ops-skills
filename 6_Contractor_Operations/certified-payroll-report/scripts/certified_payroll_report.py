"""WH-347-style certified payroll with Davis-Bacon compliance check."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


OT_THRESHOLD = 40
COMPLIANCE_TOLERANCE = 0.01
DAY_FIELDS = (
    "hours_mon", "hours_tue", "hours_wed", "hours_thu",
    "hours_fri", "hours_sat", "hours_sun",
)


@dataclass(frozen=True)
class Timecard:
    employee: str
    classification: str
    project: str
    week_ending: date
    hours: tuple[int, ...]  # 7 day columns
    base_rate: float
    fringe_rate: float

    def __post_init__(self) -> None:
        if not self.employee.strip():
            raise ValueError("employee is required")
        if not self.classification.strip():
            raise ValueError("classification is required")
        if len(self.hours) != 7:
            raise ValueError("timecard must have 7 day columns")
        for h in self.hours:
            if h < 0:
                raise ValueError(f"hours cannot be negative for {self.employee}")
        if self.base_rate < 0 or self.fringe_rate < 0:
            raise ValueError(f"rates cannot be negative for {self.employee}")

    @property
    def total_hours(self) -> int:
        return sum(self.hours)

    @property
    def ot_hours(self) -> int:
        return max(0, self.total_hours - OT_THRESHOLD)

    @property
    def st_hours(self) -> int:
        return min(self.total_hours, OT_THRESHOLD)


@dataclass(frozen=True)
class WageDetermination:
    classification: str
    prevailing_base_rate: float
    prevailing_fringe_rate: float

    def __post_init__(self) -> None:
        if not self.classification.strip():
            raise ValueError("classification is required")
        if self.prevailing_base_rate < 0 or self.prevailing_fringe_rate < 0:
            raise ValueError("prevailing rates cannot be negative")


def build_report(
    timecards: list[Timecard],
    determinations: list[WageDetermination],
) -> dict[str, object]:
    by_class: dict[str, WageDetermination] = {d.classification: d for d in determinations}
    rows: list[dict[str, object]] = []
    total_gross = 0.0
    exception_count = 0

    for tc in timecards:
        total = tc.total_hours
        ot = tc.ot_hours
        st = tc.st_hours
        # OT premium on base rate only; fringe on ALL hours straight.
        gross = round(st * tc.base_rate + ot * tc.base_rate * 1.5 + total * tc.fringe_rate, 2)
        total_gross += gross

        flags: list[str] = []
        risks: list[str] = []
        restitution = 0.0
        shortfall_per_hour = 0.0

        if tc.classification not in by_class:
            flags.append("unknown_classification")
            risks.append("review")
            exception_count += 1
        else:
            d = by_class[tc.classification]
            paid_total = tc.base_rate + tc.fringe_rate
            prevailing_total = d.prevailing_base_rate + d.prevailing_fringe_rate
            if paid_total < prevailing_total - COMPLIANCE_TOLERANCE:
                shortfall_per_hour = round(prevailing_total - paid_total, 2)
                restitution = round(shortfall_per_hour * total, 2)
                flags.append("underpaid")
                risks.append("high")
                exception_count += 1

        row = {
            "employee": tc.employee,
            "classification": tc.classification,
            "project": tc.project,
            "week_ending": tc.week_ending.isoformat(),
            "hours_mon": tc.hours[0], "hours_tue": tc.hours[1], "hours_wed": tc.hours[2],
            "hours_thu": tc.hours[3], "hours_fri": tc.hours[4], "hours_sat": tc.hours[5],
            "hours_sun": tc.hours[6],
            "total_hours": total,
            "ot_hours": ot,
            "st_hours": st,
            "base_rate": round(tc.base_rate, 2),
            "fringe_rate": round(tc.fringe_rate, 2),
            "gross": gross,
            "flags": flags,
            "risks": risks,
            "restitution": restitution,
        }
        rows.append(row)

    return {
        "row_count": len(rows),
        "total_gross": round(total_gross, 2),
        "exception_count": exception_count,
        "rows": rows,
    }


REQUIRED_TC = (
    "employee", "classification", "project", "week_ending",
    *DAY_FIELDS, "base_rate", "fringe_rate",
)
REQUIRED_WD = ("classification", "prevailing_base_rate", "prevailing_fringe_rate")


def load_timecards(path: Path) -> list[Timecard]:
    out: list[Timecard] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return out
        missing = [c for c in REQUIRED_TC if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if not (row.get("employee") or "").strip():
                continue
            try:
                out.append(Timecard(
                    employee=(row["employee"] or "").strip(),
                    classification=(row["classification"] or "").strip(),
                    project=(row["project"] or "").strip(),
                    week_ending=date.fromisoformat((row["week_ending"] or "").strip()),
                    hours=tuple(int(row[d]) for d in DAY_FIELDS),
                    base_rate=float(row["base_rate"]),
                    fringe_rate=float(row["fringe_rate"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return out


def load_determination(path: Path) -> list[WageDetermination]:
    out: list[WageDetermination] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return out
        missing = [c for c in REQUIRED_WD if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if not (row.get("classification") or "").strip():
                continue
            try:
                out.append(WageDetermination(
                    classification=(row["classification"] or "").strip(),
                    prevailing_base_rate=float(row["prevailing_base_rate"]),
                    prevailing_fringe_rate=float(row["prevailing_fringe_rate"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WH-347 certified payroll + Davis-Bacon check.")
    parser.add_argument("timecards", type=Path)
    parser.add_argument("determination", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_report(load_timecards(args.timecards), load_determination(args.determination))
    if args.json_path is not None:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Certified payroll: {report['row_count']} rows, "
          f"total gross {report['total_gross']:.2f}, "
          f"exceptions {report['exception_count']}")
    for r in report["rows"]:  # type: ignore[union-attr]
        flags = ",".join(r["flags"]) if r["flags"] else "-"
        print(f"  {r['employee']} ({r['classification']}) "
              f"hrs={r['total_hours']} ot={r['ot_hours']} "
              f"gross={r['gross']:.2f} flags={flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
