"""Dependency-free repository validator for Trailwise skill packages."""

from __future__ import annotations

import json
import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("missing or malformed frontmatter")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            raise ValueError(f"malformed frontmatter line: {line}")
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        frontmatter = parse_frontmatter(path)
    except ValueError as exc:
        return [str(exc)]
    if set(frontmatter) != {"name", "description"}:
        errors.append(f"frontmatter keys must be name and description, got {sorted(frontmatter)}")
    name = frontmatter.get("name", "")
    if not NAME_RE.fullmatch(name):
        errors.append(f"invalid skill name: {name}")
    if path.parent.name != name:
        errors.append(f"folder {path.parent.name} does not match skill name {name}")
    description = frontmatter.get("description", "")
    if "Use when" not in description:
        errors.append("description must include trigger context beginning with 'Use when'")
    metadata = path.parent / "agents/openai.yaml"
    if not metadata.exists():
        errors.append("agents/openai.yaml is missing")
    else:
        metadata_text = metadata.read_text(encoding="utf-8")
        if f"${name}" not in metadata_text:
            errors.append("default_prompt must mention the skill by $name")
    if "TODO" in path.read_text(encoding="utf-8"):
        errors.append("SKILL.md contains TODO placeholders")
    return errors


def main() -> int:
    failures: list[str] = []
    skill_files = sorted(ROOT.rglob("SKILL.md"))
    for skill_file in skill_files:
        for error in validate_skill(skill_file):
            failures.append(f"{skill_file.relative_to(ROOT)}: {error}")
    for python_file in sorted(ROOT.rglob("*.py")):
        if "__pycache__" not in python_file.parts:
            try:
                ast.parse(python_file.read_text(encoding="utf-8"), filename=str(python_file))
            except SyntaxError as exc:
                failures.append(f"{python_file.relative_to(ROOT)}: {exc.msg}")
    for json_file in sorted(ROOT.rglob("*.json")):
        try:
            json.loads(json_file.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"{json_file.relative_to(ROOT)}: invalid JSON: {exc}")
    if failures:
        print("\n".join(f"ERROR {failure}" for failure in failures))
        return 1
    print(f"Validated {len(skill_files)} skills, Python syntax, and JSON assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
