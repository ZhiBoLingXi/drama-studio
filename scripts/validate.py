#!/usr/bin/env python3
"""Validate repository syntax, local documentation links and skill contents offline."""
import ast
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from install import inventory, SOURCE

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    checked = 0
    for path in sorted(ROOT.rglob("*")):
        if any(part in {".git", "dist", "__pycache__", "projects", ".venv"} for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                checked += 1
            except SyntaxError as error:
                failures.append(str(error))
        if path.suffix != ".md":
            continue
        content = path.read_text(encoding="utf-8")
        checked += 1
        if sum(line.startswith("```") for line in content.splitlines()) % 2:
            failures.append(f"Unclosed code fence: {path.relative_to(ROOT)}")
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            if re.match(r"[a-z]+:", link) or link.startswith("#"):
                continue
            target = link.split("#", 1)[0]
            if target and not (path.parent / target).exists():
                failures.append(f"Missing link: {path.relative_to(ROOT)} -> {link}")
    files = inventory(SOURCE)
    frontmatter = (SOURCE / "SKILL.md").read_text(encoding="utf-8").split("---", 2)
    if len(frontmatter) != 3 or "name: drama-studio" not in frontmatter[1] or "description:" not in frontmatter[1]:
        failures.append("Invalid SKILL.md frontmatter")
    for name in files:
        path = SOURCE / name
        if path.suffix not in {".md", ".py"}:
            failures.append(f"Unexpected bundled file: {name}")
        if "/Users/" in path.read_text(encoding="utf-8"):
            failures.append(f"Personal absolute path in bundle: {name}")
    result = {"ok": not failures, "checked_files": checked, "bundle_files": len(files), "errors": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
