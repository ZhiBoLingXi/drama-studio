"""The studio corpus folder: `<studio root>/corpus/`, where the studio root is the folder that holds STUDIO.md
(references/initialization.md). Plan §8 #1, confirmed by the lead 2026-10-15: the corpus cache may be studio-level.

A studio corpus holds mali-story template data only: a record there is `scope.level: studio` with
`origin.kind: mali_story_template`. Contrast pairs, writer notes and this project's negatives and human positives stay
project-level and never go here.
"""
from __future__ import annotations

from pathlib import Path

STUDIO_ORIGIN = "mali_story_template"


def studio_corpus_root(path) -> Path | None:
    """The studio corpus folder that path (resolved, symlinks followed) lies in, or None."""
    resolved = Path(path).expanduser().absolute().resolve()
    for folder in (resolved, *resolved.parents):
        if folder.name == "corpus" and (folder.parent / "STUDIO.md").is_file():
            return folder
    return None


def studio_corpus_dir(path) -> Path:
    """path itself as a studio corpus folder (an existing `corpus/` beside STUDIO.md), else ValueError."""
    resolved = Path(path).expanduser().absolute().resolve()
    if not resolved.is_dir() or studio_corpus_root(resolved) != resolved:
        raise ValueError(f"--studio-corpus must be an existing <studio root>/corpus/ folder, the studio root holding STUDIO.md: {path}")
    return resolved


def studio_row_problem(row) -> str | None:
    """Why a record may not sit in a studio corpus: it must be studio-level and come from a mali-story template."""
    if not isinstance(row, dict):
        return "不是对象"
    level = (row.get("scope") or {}).get("level") if isinstance(row.get("scope"), dict) else None
    origin = (row.get("origin") or {}).get("kind") if isinstance(row.get("origin"), dict) else None
    if level != "studio":
        return f"工作室语料里的记录要写 scope.level: studio（现在是 {level!r}）"
    if origin != STUDIO_ORIGIN:
        return f"工作室语料只收 origin.kind: {STUDIO_ORIGIN} 的记录（现在是 {origin!r}）；项目句子不进工作室语料"
    return None
