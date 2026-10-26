"""Check coverage of a saved mali-story template detail, without judging its truth."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def run_reference_check(path, expected_episodes=None):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected a template detail JSON object")
    if "schemaVersion" in data:
        if data.get("ok") is not True:
            raise ValueError("The saved MCP operation did not succeed")
        data = data.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("template"), dict):
        raise ValueError("Expected GET template detail, not a list row or task status")
    template = data["template"]
    declared = template.get("episodesTotal")
    expected = expected_episodes if expected_episodes is not None else declared
    if type(expected) is not int or expected < 1:
        raise ValueError("Expected episode count must be a positive integer")
    content = data.get("content")
    rows = content.get("episodeOutlines") if isinstance(content, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Detail has no episodeOutlines array; coverage is unknown")
    issues = []
    if declared != expected:
        issues.append({"code": "declared_count_mismatch", "declared": declared, "expected": expected})
    indices = []
    outlines = set()
    evidence = set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("episodeIndex")) is not int or row["episodeIndex"] < 1:
            raise ValueError("Every episode row must have a positive integer episodeIndex")
        index = row["episodeIndex"]
        indices.append(index)
        outline = row.get("outlineMd")
        source = row.get("rawMd")
        has_outline = isinstance(outline, str) and bool(outline.strip())
        if has_outline:
            outlines.add(index)
        if isinstance(source, str) and source.strip():
            evidence.add(index)
        if "hasOutline" in row and row["hasOutline"] is not has_outline:
            issues.append({"code": "outline_flag_mismatch", "episode": index})
    duplicates = sorted(i for i, count in Counter(indices).items() if count > 1)
    if duplicates:
        issues.append({"code": "duplicate_indices", "episodes": duplicates})
    unexpected = sorted(i for i in set(indices) if i > expected)
    if unexpected:
        issues.append({"code": "unexpected_indices", "episodes": unexpected})
    # Only recognize explicit count declarations; do not guess counts from prose.
    for name, text in (("seriesOutlineMd", template.get("seriesOutlineMd")),
                       ("fullOutline", content.get("fullOutline"))):
        if not isinstance(text, str):
            continue
        for value in re.findall(r"(?m)^\s*(?:-\s*)?episodesTotal\s*:\s*(\d+)\s*$", text):
            if int(value) != expected:
                issues.append({"code": "summary_count_mismatch", "field": name, "declared": int(value), "expected": expected})
    missing_rows = [i for i in range(1, expected + 1) if i not in set(indices)]
    missing_outlines = [i for i in range(1, expected + 1) if i not in outlines]
    missing_evidence = [i for i in range(1, expected + 1) if i not in evidence]
    complete = not (issues or missing_rows or missing_outlines or missing_evidence)
    return {"ok": True, "schemaVersion": 1, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "template_id": template.get("id"), "template_version": template.get("version"),
            "service_status": template.get("status"), "expected_episodes": expected,
            "expected_source": "explicit_argument" if expected_episodes is not None else "template.episodesTotal",
            "scope": "declared_template_slots_only_not_original_series",
            "coverage_status": "consistent_present" if complete else "needs_review", "passed": None,
            "missing_rows": missing_rows, "missing_outlines": missing_outlines,
            "missing_raw_evidence": missing_evidence, "issues": issues,
            "source_video_verified": False, "semantic_review": "not_run",
            "limitations": ["Nonempty text may be truncated, inaccurate or misattributed",
                            "A template may cover only part of the original series",
                            "No character, timestamp, originality or creative-quality validation"]}
