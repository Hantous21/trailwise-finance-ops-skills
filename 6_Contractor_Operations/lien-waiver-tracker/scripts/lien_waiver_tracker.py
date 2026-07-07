"""Deterministic lien waiver collection and draw-funding exposure tracker."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


VALID_TYPES = {
    "conditional_progress",
    "unconditional_progress",
    "conditional_final",
    "unconditional_final",
}


@dataclass(frozen=True)
class WaiverRow:
    project: str
    subcontractor: str
    draw_number: int
    payment_amount: float
    payment_date: date | None
    payment_cleared: str  # "Y" / "N"
    waiver_type: str
    waiver_received: str  # "Y" / "N"
    waiver_date: date | None

    def __post_init__(self) -> None:
        if not self.project.strip() or not self.subcontractor.strip():
            raise ValueError("project and subcontractor are required")
        if self.draw_number < 1:
            raise ValueError("draw_number must be >= 1")
        if self.payment_amount < 0:
            raise ValueError("payment_amount cannot be negative")
        if self.payment_cleared not in {"Y", "N"}:
            raise ValueError(f"payment_cleared must be Y or N (got {self.payment_cleared!r})")
        if self.waiver_received not in {"Y", "N"}:
            raise ValueError(f"waiver_received must be Y or N (got {self.waiver_received!r})")
        if self.waiver_type not in VALID_TYPES:
            raise ValueError(
                f"unknown waiver_type {self.waiver_type!r}; must be one of {sorted(VALID_TYPES)}"
            )


def evaluate(rows: list[WaiverRow]) -> dict[str, object]:
    by_project: dict[str, list[WaiverRow]] = defaultdict(list)
    for r in rows:
        by_project[r.project].append(r)

    projects_out: list[dict[str, object]] = []
    total_exposure = 0.0
    total_critical_reasons = 0

    for project, project_rows in by_project.items():
        project_rows.sort(key=lambda r: (r.draw_number, r.subcontractor))
        row_out: list[dict[str, object]] = []
        exposure = 0.0
        blockers: list[tuple[str, int]] = []
        seen_missing: set[tuple[str, int]] = set()
        for r in project_rows:
            flags: list[str] = []
            risks: list[str] = []
            if r.payment_date is not None and r.waiver_received == "N":
                flags.append("missing_waiver")
                risks.append("high")
                exposure += r.payment_amount
                key = (r.subcontractor, r.draw_number)
                if key not in seen_missing:
                    blockers.append(key)
                    seen_missing.add(key)
            if r.waiver_type.startswith("unconditional") and r.payment_cleared == "N":
                flags.append("unconditional_before_cleared")
                risks.append("critical")
                total_critical_reasons += 1
            if (
                r.waiver_type.startswith("unconditional")
                and r.waiver_date is not None
                and r.payment_date is not None
                and r.waiver_date < r.payment_date
            ):
                flags.append("waiver_predates_payment")
                risks.append("critical")
                total_critical_reasons += 1
            row_out.append({
                "subcontractor": r.subcontractor,
                "draw_number": r.draw_number,
                "payment_amount": round(r.payment_amount, 2),
                "payment_date": r.payment_date.isoformat() if r.payment_date else None,
                "payment_cleared": r.payment_cleared,
                "waiver_type": r.waiver_type,
                "waiver_received": r.waiver_received,
                "waiver_date": r.waiver_date.isoformat() if r.waiver_date else None,
                "flags": flags,
                "risks": risks,
            })

        total_exposure += exposure
        projects_out.append({
            "project": project,
            "exposure": round(exposure, 2),
            "next_draw_blockers": [
                {"subcontractor": s, "draw_number": d} for s, d in sorted(blockers)
            ],
            "rows": row_out,
        })

    return {
        "project_count": len(projects_out),
        "total_exposure": round(total_exposure, 2),
        "critical_reason_count": total_critical_reasons,
        "projects": projects_out,
    }


REQUIRED_COLUMNS = (
    "project", "subcontractor", "draw_number", "payment_amount", "payment_date",
    "payment_cleared", "waiver_type", "waiver_received", "waiver_date",
)


def _date_or_none(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    return date.fromisoformat(s)


def load_rows(path: Path) -> list[WaiverRow]:
    rows: list[WaiverRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return rows
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if not any((row.get(c) or "").strip() for c in REQUIRED_COLUMNS):
                continue
            try:
                rows.append(WaiverRow(
                    project=(row["project"] or "").strip(),
                    subcontractor=(row["subcontractor"] or "").strip(),
                    draw_number=int(row["draw_number"]),
                    payment_amount=float(row["payment_amount"]),
                    payment_date=_date_or_none(row["payment_date"]),
                    payment_cleared=(row["payment_cleared"] or "").strip(),
                    waiver_type=(row["waiver_type"] or "").strip(),
                    waiver_received=(row["waiver_received"] or "").strip(),
                    waiver_date=_date_or_none(row["waiver_date"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lien waiver tracker and draw funding exposure.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, default=None)
    args = parser.parse_args(argv)

    report = evaluate(load_rows(args.input))
    if args.json_path is not None:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Waiver tracker: {report['project_count']} projects, "
          f"total exposure {report['total_exposure']:.2f}, "
          f"critical reasons {report['critical_reason_count']}")
    for p in report["projects"]:  # type: ignore[union-attr]
        blocker_str = ",".join(
            f"{b['subcontractor']}#{b['draw_number']}" for b in p["next_draw_blockers"]
        ) or "-"
        print(f"  {p['project']}: exposure={p['exposure']:.2f} blockers=[{blocker_str}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
