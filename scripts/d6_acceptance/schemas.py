"""D6-1 local acceptance, stream A (schemas and contracts): contract-check every real D6-0 artifact.

Reads only the private validation directory V (runs/pilot-v2, gitignored) and writes nothing. Not bundled.
Each row says whether the file passes, and when it fails, whether it fails only because of a legacy
D6-0 form (the schema takes the canonical form; contract-check names the legacy one).
"""
from __future__ import annotations

import glob
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("contract_check", ROOT / "skills/drama-studio/scripts/checks/contract_check.py")
contracts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(contracts)

# object -> glob patterns relative to V ("E/" means the sibling pilot-ep006 directory)
TARGETS = {
    "function-map": ["function-map-v0.json", "r6/function-map-v1.1.json", "r15/function-map-v1.2.json"],
    "ledger-entry": ["ledger/ledger-ep000.json", "r6/ledger-ep000.v1.1.json", "r15/ledger-ep000.v1.2.json"],
    "ledger-delta": ["r8/ledger-*-delta*.json"],
    "question-set": ["questions/*.json"],
    "answers": ["reality-check/RC-*.json", "r4/RC-*.json", "r4b/RC-*.json", "r5rc/RC-B*.json", "r5rc/r2/RC-*.json",
                "r13/check-*.json", "r15/check-*.json"],
    "season-plan": ["r7/season-plan-v0.json"],
    "episode-plan": ["r8/episode-plan-*.json"],
    "decision-queue": ["r6/decisions.v1.1.json", "r7/decisions-r7.json", "r15/decisions-merged.v2.json"],
    "media-profile": ["E/media-profile-v0.json"],
    "dialogue-exchange": ["E/corpus/exchanges.jsonl"],
    "corpus-manifest": ["E/corpus/manifest.json"],
    "contrast-pair": ["E/contrast-pairs.jsonl"],
    "dialogue-plan": ["r11/dialogue-plan-ep006A-v2.1.json"],
    "dialogue-target": ["r11/dialogue-target-v0.1.json"],
    "retell-record": ["r9/retell-plan-*.json", "r13/retell-ep*.json", "r15/retell-*.json"],
    "plan-text-consistency": ["r13/plan-text-consistency-g1.json"],
    "defect-register": ["reality-check/defects-A.json", "r1/defects-v2.json"],
    "knowledge-card": ["knowledge/cards/*.json"],
}
# Files that match a glob but are not instances of the object (summaries, indexes).
NOT_INSTANCES = {"reality-check/RC-A-index.json"}


def _files(V: Path, patterns) -> list[Path]:
    found = []
    for pattern in patterns:
        base = V.parent / "pilot-ep006" if pattern.startswith("E/") else V
        found += sorted(Path(p) for p in glob.glob(str(base / pattern.removeprefix("E/"))))
    return [p for p in found if not (p.is_relative_to(V) and str(p.relative_to(V)) in NOT_INSTANCES)]


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _context(V: Path) -> dict:
    """Cross-file context the single-file contract-check cannot see: records, defect kinds, card coverage."""
    records, kinds = {}, {}
    for path in _files(V, TARGETS["answers"]):
        doc = _load(path)
        if not isinstance(doc, dict) or "checkId" not in doc or "answers" not in doc:
            continue
        records[doc["checkId"]] = doc
        for answer in doc["answers"]:
            key = answer.get("defectKey")
            if key:
                kinds.setdefault(key, set()).update(answer.get("defectKind") or answer.get("kind") or [])
    cards = {}
    for path in _files(V, TARGETS["knowledge-card"]):
        doc = _load(path)
        if isinstance(doc, dict) and "cardId" in doc and doc.get("coverage"):
            cards[doc["cardId"]] = doc["coverage"]
    return {"records": records, "defectKinds": {k: sorted(v) for k, v in kinds.items()}, "cards": cards}


def _find(items, key, value):
    return next((item for item in items or [] if isinstance(item, dict) and item.get(key) == value), None)


def _explain(V: Path, rel: str, result: dict, doc) -> dict | None:
    """Why a real violation is expected, checked against the audit or later file (read here, not remembered).

    Returns None when the evidence is not where it should be, so the row stays unexplained.
    """
    def ok(cls, text, *evidence):
        return {"class": cls, "text": text, "evidence": [{"file": f, "found": found} for f, found in evidence]}

    name = Path(rel).name
    if rel.startswith("reality-check/RC-P"):
        summary_file = "reality-check/RC-P2-summary.json" if name.startswith("RC-P2-") else "reality-check/RC-P-summary.json"
        summary = _load(V / summary_file) or {}
        entry = _find(summary.get("perPremise"), "checkId", doc["checkId"])
        load_bearing = entry and (entry.get("notHoldsLoadBearing") or 0)
        if entry and entry.get("outcome") == "fail" and load_bearing:
            return ok("audited_noncompliant_at_the_time",
                      f"前提第 {'二' if name.startswith('RC-P2-') else '一'}轮：该轮汇总判 {doc['checkId']} outcome fail、承重 notHolds {load_bearing} 条；"
                      "当时还没有 disposition 字段，这一轮的前提后来被 premises-v3／v4 取代",
                      (summary_file, f"perPremise[{doc['checkId']}].outcome=fail, notHoldsLoadBearing={load_bearing}"))
        return None
    if rel.startswith(("r4/RC-P3-", "r4b/RC-P4-")):
        normalized = json.loads(json.dumps(doc))
        contracts.LEGACY["answers"](normalized, set())  # legacy forms are named elsewhere; explain what remains
        remaining = contracts.check_contract("answers", normalized)
        if any(not e.startswith("answers[") for e in remaining):
            return None
        failing = [int(e.split("[", 1)[1].split("]", 1)[0]) for e in remaining]
        audited = [i for i in failing if (doc["answers"][i].get("disposition") or {}).get("audit") == "noncompliant"]
        if not failing or audited != failing:
            return None
        if rel.startswith("r4/"):
            audit = (_load(V / "r4/license-audit.json") or {}).get("summary", {})
            if not audit.get("noncompliant"):
                return None
            return ok("audited_noncompliant_at_the_time",
                      f"R4（premises-v3）：{len(failing)} 条承重 notHolds 在记录里已标 audit: noncompliant（没有合法去处），license-audit 列出 {len(audit['noncompliant'])} 项不合规",
                      (rel, f"answers{failing}.disposition.audit=noncompliant"),
                      ("r4/license-audit.json", f"summary.noncompliant has {len(audit['noncompliant'])} items"))
        counts = (_load(V / "r4b/r4b-summary.json") or {}).get("complianceCounts", {})
        registrations = _load(V / "r5rc/registrations-audit.json") or {}
        if not counts.get("unregisteredLoadBearing") or not registrations.get("registrations"):
            return None
        return ok("audited_noncompliant_at_the_time",
                  f"R4b（premises-v4，最后一轮不再换实现）：{len(failing)} 条承重 notHolds 记录里已标 audit: noncompliant；"
                  f"r4b 汇总报 unregisteredLoadBearing={counts['unregisteredLoadBearing']}，随后由 R5 登记并经 registrations-audit 核过",
                  (rel, f"answers{failing}.disposition.audit=noncompliant"),
                  ("r4b/r4b-summary.json", f"complianceCounts.unregisteredLoadBearing={counts['unregisteredLoadBearing']}"),
                  ("r5rc/registrations-audit.json", f"registrations: {len(registrations['registrations'])} items"))
    if rel == "r5rc/RC-B-F-gift-3.json":
        newer = _load(V / "r5rc/r2/RC-B2-F-gift-3.json") or {}
        if newer.get("supersedes") == rel:
            return ok("superseded", "已被 r5rc/r2/RC-B2-F-gift-3.json 取代（它的 supersedes 指向本文件）",
                      ("r5rc/r2/RC-B2-F-gift-3.json", f"supersedes={rel}"))
        return None
    if rel == "r6/ledger-ep000.v1.1.json":
        missing = [e.split()[1].rstrip(":") for e in result["errors"] if "retiring a user-given entry" in e]
        later = _load(V / "r15/ledger-ep000.v1.2.json") or {}
        fixed = [_find(later.get("entries"), "id", entry_id) for entry_id in missing]
        if missing and len(missing) == len(result["errors"]) and all(f and (f.get("retiredBy") or f.get("decisionRef") or f.get("retiresInto")) for f in fixed) \
                and contracts.run_contract_check("ledger-entry", str(V / "r15/ledger-ep000.v1.2.json"), _context(V))["passed"]:
            return ok("fixed_in_later_version", f"{missing} 退役缺引用，v1.2 已补 retiredBy，且 v1.2 整份通过 contract-check ledger-entry",
                      ("r15/ledger-ep000.v1.2.json", f"{missing[0]}.retiredBy={fixed[0]['retiredBy']}; contract-check passed"))
        return None
    if rel == "r7/decisions-r7.json":
        wrong = [e for e in doc["entries"] if e.get("kind") == "season"]
        merged = _load(V / "r15/decisions-merged.v2.json") or {}
        fixed = [_find(merged.get("entries"), "id", e["id"]) for e in wrong]
        if wrong and len(result["errors"]) == len(wrong) and all(f and f["kind"] != "season" for f in fixed):
            return ok("fixed_in_later_version", f"{[e['id'] for e in wrong]} 的 kind: season 不在词表；decisions-merged.v2 已改为 {fixed[0]['kind']}",
                      ("r15/decisions-merged.v2.json", f"{wrong[0]['id']}.kind={fixed[0]['kind']}"))
    return None


def run(V) -> list[dict]:
    V = Path(V)
    if not V.is_dir():
        return [{"stream": "schemas", "skipped": True, "reason": f"{V} does not exist; local acceptance needs the private D6-0 artifacts"}]
    context = _context(V)
    rows = []
    for name, patterns in TARGETS.items():
        for path in _files(V, patterns):
            doc = _load(path)
            if path.suffix != ".jsonl" and (not isinstance(doc, dict) or doc.get("schema", "").endswith("summary/v0-pilot")):
                rows.append({"stream": "schemas", "object": name, "file": str(path), "skipped": True,
                             "reason": "not an instance of the object (summary or index)"})
                continue
            result = contracts.run_contract_check(name, str(path), context)
            row = {"stream": "schemas", "object": name, "file": str(path), "passed": result["passed"],
                   "errorCount": len(result["errors"]), "errors": result["errors"][:8],
                   "legacyForms": result["legacyForms"], "failedOnlyOnLegacyForms": result["failedOnlyOnLegacyForms"],
                   "notEvaluated": result["notEvaluated"], "reproduceCommand": result["reproduceCommand"]}
            if not result["passed"] and not result["failedOnlyOnLegacyForms"]:
                explanation = _explain(V, str(path.relative_to(V)) if path.is_relative_to(V) else str(path), result, doc)
                if explanation:
                    row["explanation"] = explanation
            rows.append(row)
    for data in sorted((ROOT / "skills/drama-studio/schemas/data").glob("*-questions.json")):
        result = contracts.run_contract_check("question-set", str(data))
        rows.append({"stream": "schemas", "object": "question-set", "file": str(data), "passed": result["passed"],
                     "errorCount": len(result["errors"]), "errors": result["errors"], "legacyForms": [],
                     "failedOnlyOnLegacyForms": False, "notEvaluated": [], "reproduceCommand": result["reproduceCommand"]})
    return rows


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    print(json.dumps(run(target), ensure_ascii=False, indent=2))
