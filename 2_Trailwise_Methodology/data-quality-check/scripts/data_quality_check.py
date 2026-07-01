"""Read-only CSV schema and data-quality validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def parse_value(value: str, kind: str) -> None:
    if kind == "string":
        return
    if kind == "decimal":
        if not Decimal(value).is_finite():
            raise ValueError("decimal must be finite")
        return
    if kind == "integer":
        int(value)
        return
    if kind == "date":
        date.fromisoformat(value)
        return
    raise ValueError(f"unsupported type: {kind}")


def check_csv(path: Path, schema: dict[str, object]) -> dict[str, object]:
    columns = schema.get("columns", {})
    if not isinstance(columns, dict) or not columns:
        raise ValueError("schema.columns must be a non-empty object")
    unique_keys = schema.get("unique_keys", [])
    unknown_unique_keys = sorted(set(unique_keys) - set(columns))
    if unknown_unique_keys:
        raise ValueError(f"unique_keys reference unknown columns: {', '.join(unknown_unique_keys)}")
    errors: list[dict[str, object]] = []
    seen: set[tuple[str, ...]] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        actual = reader.fieldnames or []
        missing = sorted(set(columns) - set(actual))
        unexpected = sorted(set(actual) - set(columns))
        for column in missing:
            errors.append({"row": 1, "column": column, "code": "missing_column"})
        for column in unexpected:
            errors.append({"row": 1, "column": column, "code": "unexpected_column"})
        row_count = 0
        for row_number, row in enumerate(reader, 2):
            row_count += 1
            for column, rule in columns.items():
                rule = rule or {}
                value = (row.get(column) or "").strip()
                if not value:
                    if rule.get("required", False):
                        errors.append({"row": row_number, "column": column, "code": "blank_required"})
                    continue
                try:
                    parse_value(value, rule.get("type", "string"))
                except (ValueError, InvalidOperation):
                    errors.append({"row": row_number, "column": column, "code": "invalid_type", "value": value})
            if unique_keys:
                key = tuple((row.get(column) or "").strip().casefold() for column in unique_keys)
                if key in seen:
                    errors.append({"row": row_number, "column": ",".join(unique_keys), "code": "duplicate_key"})
                else:
                    seen.add(key)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"file": path.name, "sha256": digest, "rows": row_count, "error_count": len(errors), "valid": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check_csv(args.input, json.loads(args.schema.read_text(encoding="utf-8")))
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
