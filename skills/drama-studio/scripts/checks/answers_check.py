"""check-answers：核问题单回答记录（追问单 reality-check、对话问题单 dialogue-check）的格式。

只核格式，不核答案对不对。核什么（实施计划 §2.2 #4；d6-1-decisions #7、#8、#9）：
- 问题单里每一问（或任务声明的问题子集）至少一条回答；未问的不要求（修正点 #73）；
- 每答有落点（追问单 `landsOn`，对话问题单 `quoteRef`）、四态之一、非空 `reason`；
- `outcome` 与回答分布一致；`informational` 问不参与；
- 记录有 `promptVersion`；
- 追问单：`loadBearing: true` 的 `notHolds` 带 `loadBearingBasis`（枚举）与 `loadBearingWhy`，
  并带 `disposition`（`to` 枚举＋`ref`）；给了 `--decisions`／`--ledger`／`--records` 时核引用存在。
只报不拦：`defectKind` 含 `missing` 而无 `searchScope`；覆盖报告（`--function-map`，只算步骤与
procedure／object／money 类依赖）；`--cross` 多份记录同一落点三态是否一致。

退出码：0 格式全对；1 输入错误；2 有格式错误。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.text_lines import InputError, abspath, is_nonempty, load_json, reproduce_command, run_cli

DATA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "data"
DEFAULT_STATES = ["holds", "notHolds", "not_evaluable", "n/a"]
OUTCOMES = {"pass", "fail", "fail_inherited", "pass_with_unverified"}
LOAD_BEARING_BASIS = {"stated_in_record", "has_downstream", "function_sentence_step"}
DISPOSITION_TO = {"confirmed_gone", "license", "decision", "leaves_open"}
LICENSE_STATUSES = {"license_pending", "accepted_license"}
COVERAGE_DEP_KINDS = {"procedure", "object", "money"}
LANDING_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)+")


def record_kind(doc: dict, questions: dict | None = None) -> str:
    schema = str(doc.get("schema") or "")
    for kind in ("reality-check", "dialogue-check"):
        if schema.startswith(kind) or (questions or {}).get("id", "").startswith(kind):
            return kind
    if any("quoteRef" in a for a in doc.get("answers") or [] if isinstance(a, dict)):
        return "dialogue-check"
    return "reality-check"


def lands_on_field(kind: str) -> str:
    return "quoteRef" if kind == "dialogue-check" else "landsOn"


def landing_key(answer: dict):
    """对齐用的落点：对话问题单取 quoteRef.line；追问单取 landsOn 开头的 id（步骤、依赖、
    底账 id），取不出 id 时用 landsOn 原文。"""
    ref = answer.get("quoteRef")
    if isinstance(ref, dict) and "line" in ref:
        return "line", ref["line"]
    text = str(answer.get("landsOn") or "").strip()
    match = LANDING_ID_RE.match(text)
    return ("landsOnId", match.group(0)) if match else ("landsOn", text)


def find_question_set(version: str) -> Path | None:
    if not DATA_DIR.is_dir():
        return None
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            doc = load_json(path, "问题单")
        except InputError:
            continue
        if isinstance(doc, dict) and f"{doc.get('id')}@{doc.get('version')}" == version:
            return path
    return None


def asked_subset(doc: dict, cli_subset):
    if cli_subset is not None:
        return set(cli_subset), "--questions-subset"
    for key in ("askedSubset", "scopeOfQuestions"):
        value = doc.get(key)
        if isinstance(value, list) and value and all(isinstance(q, int) for q in value):
            return set(value), key
    return None, None


def expected_outcome(answers: list, informational: set) -> set:
    counted = [a for a in answers if isinstance(a, dict) and a.get("q") not in informational]
    not_holds = [a for a in counted if a.get("holds") == "notHolds"]
    if not_holds:
        return {"fail", "fail_inherited"} if all(is_nonempty(a.get("inheritedFrom")) for a in not_holds) else {"fail"}
    if any(a.get("holds") == "not_evaluable" for a in counted):
        return {"pass_with_unverified"}
    return {"pass"}


def load_ref_sources(decisions, ledger, records) -> dict:
    sources = {}
    if decisions:
        doc = load_json(decisions, "决定队列")
        sources["decision"] = {e.get("id") for e in doc.get("entries", []) or [] if isinstance(e, dict)}
    if ledger:
        doc = load_json(ledger, "底账")
        sources["license"] = {e.get("id") for e in doc.get("entries", []) or []
                              if isinstance(e, dict) and e.get("status") in LICENSE_STATUSES}
    if records:
        ids = set()
        for path in records:
            doc = load_json(path, "核对记录")
            if isinstance(doc, dict) and doc.get("checkId"):
                ids.add(doc["checkId"])
        sources["confirmed_gone"] = ids
    return sources


def check_disposition(answer: dict, where: str, ref_sources: dict, errors: list, unresolved: list) -> None:
    disposition = answer.get("disposition")
    if not isinstance(disposition, dict):
        errors.append(f"{where}: 承重的 notHolds 没有 disposition（去处：{sorted(DISPOSITION_TO)}）")
        return
    to = disposition.get("to")
    if to not in DISPOSITION_TO:
        errors.append(f"{where}: disposition.to={to!r} 不在 {sorted(DISPOSITION_TO)}")
        return
    ref = disposition.get("ref")
    if to == "leaves_open":
        return
    if not is_nonempty(ref):
        errors.append(f"{where}: disposition.to={to!r} 没有 ref（确认消失的核对记录、戏剧假定条目或决定队列条目）")
        return
    known = ref_sources.get(to)
    if known is None:
        unresolved.append({"where": where, "to": to, "ref": ref})
        return
    for one in ref if isinstance(ref, list) else [ref]:
        if str(one).split("#")[0] not in known:
            errors.append(f"{where}: disposition.ref={one!r} 在给定的{to}来源里找不到")


def check_record(doc: dict, questions: dict, subset_cli=None, ref_sources=None) -> dict:
    ref_sources = ref_sources or {}
    errors, reports, unresolved = [], [], []
    kind = record_kind(doc, questions)
    field = lands_on_field(kind)
    states = questions.get("answerStates") or DEFAULT_STATES
    question_ids = {q.get("q") for q in questions.get("questions", []) if isinstance(q, dict)}
    informational = {q.get("q") for q in questions.get("questions", [])
                     if isinstance(q, dict) and q.get("answerKind") == "informational"}
    for key in ("questionsVersion", "answers", "outcome"):
        if key not in doc:
            errors.append(f"记录缺顶层字段 {key!r}")
    version = f"{questions.get('id')}@{questions.get('version')}"
    if doc.get("questionsVersion") != version:
        errors.append(f"questionsVersion 应为 {version!r}，实际 {doc.get('questionsVersion')!r}")
    if not is_nonempty(doc.get("promptVersion")):
        errors.append("记录没有 promptVersion（答题用的提示词与问题单版本）")
    answers = doc.get("answers") if isinstance(doc.get("answers"), list) else []
    counts = {state: 0 for state in states}
    answered = set()
    for i, answer in enumerate(answers):
        where = f"answers[{i}]"
        if not isinstance(answer, dict):
            errors.append(f"{where}: 不是对象")
            continue
        q = answer.get("q")
        where = f"answers[{i}](q={q})"
        answered.add(q)
        if q not in question_ids:
            errors.append(f"{where}: 不在问题单 {version} 的问题范围内")
        if not is_nonempty(answer.get(field)):
            errors.append(f"{where}: 落点 {field} 为空或缺失")
        holds = answer.get("holds")
        if holds not in states:
            errors.append(f"{where}: holds={holds!r} 不在 {states}")
        else:
            counts[holds] += 1
        if not is_nonempty(answer.get("reason")):
            errors.append(f"{where}: reason 为空或缺失")
        kinds = answer.get("defectKind") or []
        if "missing" in kinds and not is_nonempty(answer.get("searchScope")):
            reports.append({"rule": "missing-without-search-scope", "where": where,
                            "detail": "defectKind 含 missing（材料没写），没有 searchScope 说明查了哪些材料（只报不拦）"})
        if kind == "reality-check" and answer.get("loadBearing") is True and holds == "notHolds":
            if answer.get("loadBearingBasis") not in LOAD_BEARING_BASIS:
                basis = str(answer.get("loadBearingBasis"))
                errors.append(f"{where}: 承重的 notHolds 的 loadBearingBasis={basis[:30]!r}"
                              f"{'…' if len(basis) > 30 else ''} 不在 {sorted(LOAD_BEARING_BASIS)}")
            if not is_nonempty(answer.get("loadBearingWhy")):
                errors.append(f"{where}: 承重的 notHolds 缺 loadBearingWhy")
            check_disposition(answer, where, ref_sources, errors, unresolved)
    subset, subset_source = asked_subset(doc, subset_cli)
    required = (subset & question_ids) if subset else question_ids
    missing = sorted(q for q in required - answered if q is not None)
    if missing:
        errors.append(f"以下问题一条回答都没有：{missing}")
    allowed = expected_outcome(answers, informational)
    outcome = doc.get("outcome")
    if outcome not in OUTCOMES:
        errors.append(f"outcome={outcome!r} 不在 {sorted(OUTCOMES)}")
    elif outcome not in allowed:
        errors.append(f"outcome={outcome!r} 与回答分布不一致，应为 {sorted(allowed)}（informational 问 {sorted(informational)} 不计）")
    return {"kind": kind, "checkId": doc.get("checkId"), "landsOnField": field, "counts": counts,
            "askedSubset": sorted(subset) if subset else None, "askedSubsetSource": subset_source,
            "informationalQuestions": sorted(informational), "errors": errors, "reports": reports,
            "dispositionRefsNotChecked": unresolved}


def find_candidate(function_map: dict, candidate_id: str):
    functions = list(function_map.get("functions") or [])
    for thread in function_map.get("threads") or []:
        functions.extend(thread.get("functions") or [])
    for function in functions:
        for candidate in function.get("candidates") or []:
            if candidate.get("candidateId") == candidate_id:
                return candidate
    return None


def coverage_report(doc: dict, function_map: dict | None) -> dict:
    """每个步骤与 procedure／object／money 类依赖是否至少被一条回答落到（只报不拦）。"""
    if function_map is None:
        return {"status": "not_evaluable", "why": "没给 --function-map"}
    target = doc.get("target") if isinstance(doc.get("target"), dict) else {}
    if target.get("kind") != "candidate":
        return {"status": "not_applicable", "why": f"target.kind={target.get('kind')!r}，覆盖只对候选算"}
    candidate = find_candidate(function_map, target.get("id"))
    if candidate is None:
        return {"status": "not_evaluable", "why": f"功能地图里找不到候选 {target.get('id')!r}"}
    items = [("step", s.get("stepId")) for s in candidate.get("steps") or [] if s.get("stepId")]
    items += [("dep", d.get("depId")) for d in candidate.get("ledgerDeps") or []
              if d.get("depId") and d.get("kind") in COVERAGE_DEP_KINDS]
    texts = [str(a.get("landsOn") or "") for a in doc.get("answers") or [] if isinstance(a, dict)]
    uncovered = [{"kind": k, "id": i} for k, i in items if not any(i in t for t in texts)]
    return {"status": "report", "candidateId": target.get("id"), "itemsCounted": len(items),
            "uncovered": uncovered, "note": "只算步骤与 procedure／object／money 类依赖；按 landsOn 里出现该 id 判落到"}


def cross_report(records: list[tuple[str, dict]]) -> dict:
    """多份记录里同一 (问, 落点) 的三态是否一致（只报不拦）。"""
    seen = {}
    for name, doc in records:
        for answer in doc.get("answers") or []:
            if not isinstance(answer, dict) or answer.get("holds") == "n/a":
                continue
            align_by, key = landing_key(answer)
            seen.setdefault((answer.get("q"), align_by, str(key)), []).append(
                {"record": doc.get("checkId") or name, "holds": answer.get("holds")})
    rows = [{"q": q, "alignBy": by, "landing": key, "answers": found}
            for (q, by, key), found in sorted(seen.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2]))
            if len({f["record"] for f in found}) > 1 and len({f["holds"] for f in found}) > 1]
    return {"status": "report", "inconsistent": rows,
            "note": "同一落点在不同记录里三态不同只是提示去看；两份都可能错，一致也可能一起错"}


def run_answers_check(paths, questions_path=None, subset=None, function_map_path=None, cross=False,
                      decisions=None, ledger=None, ref_records=None) -> dict:
    docs = []
    for path in paths:
        doc = load_json(path, "回答记录")
        if not isinstance(doc, dict):
            raise InputError(f"回答记录不是 JSON 对象：{path}")
        docs.append((str(path), doc))
    question_cache = {}
    if questions_path:
        explicit = load_json(questions_path, "问题单")
        if not isinstance(explicit, dict) or not isinstance(explicit.get("questions"), list):
            raise InputError(f"问题单缺 questions：{questions_path}")
    function_map = load_json(function_map_path, "功能地图") if function_map_path else None
    ref_sources = load_ref_sources(decisions, ledger, ref_records)
    results = []
    for path, doc in docs:
        if questions_path:
            questions, source = explicit, abspath(questions_path)
        else:
            version = doc.get("questionsVersion")
            found = find_question_set(str(version))
            if found is None:
                raise InputError(f"{path}: 找不到 questionsVersion={version!r} 对应的问题单（用 --questions 指定）")
            questions = question_cache.setdefault(found, load_json(found, "问题单"))
            source = str(found)
        result = check_record(doc, questions, subset, ref_sources)
        result.update(file=path, questionSet=source, coverage=coverage_report(doc, function_map))
        results.append(result)
    passed = not any(r["errors"] for r in results)
    out = {"ok": True, "passed": passed, "records": results}
    if cross:
        out["cross"] = cross_report(docs)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="核问题单回答记录的格式；不核答案对不对")
    parser.add_argument("answers", nargs="+", help="回答记录（reality-check 或 dialogue-check）")
    parser.add_argument("--questions", help="问题单；不给时按 questionsVersion 在 schemas/data/ 里找")
    parser.add_argument("--questions-subset", help="本轮只问的题号，逗号分隔，如 1,2,4（记录里的 askedSubset 同义）")
    parser.add_argument("--function-map", help="功能地图：出覆盖报告")
    parser.add_argument("--cross", action="store_true", help="多份记录同一落点三态是否一致（只报不拦）")
    parser.add_argument("--decisions", help="决定队列：核 disposition.to=decision 的引用")
    parser.add_argument("--ledger", help="底账：核 disposition.to=license 的引用（条目状态须是戏剧假定）")
    parser.add_argument("--records", nargs="+", help="核对记录：核 disposition.to=confirmed_gone 的引用")
    return parser


def _main(argv):
    args = build_parser().parse_args(argv)
    subset = None
    if args.questions_subset:
        try:
            subset = [int(q) for q in args.questions_subset.split(",") if q.strip()]
        except ValueError:
            raise InputError(f"--questions-subset 只接受逗号分隔的题号：{args.questions_subset!r}") from None
    result = run_answers_check(args.answers, args.questions, subset, args.function_map, args.cross,
                               args.decisions, args.ledger, args.records)
    command = [abspath(p) for p in args.answers]
    for flag, value in (("--questions", args.questions), ("--questions-subset", args.questions_subset),
                        ("--function-map", args.function_map), ("--decisions", args.decisions),
                        ("--ledger", args.ledger)):
        if value:
            command += [flag, value if flag == "--questions-subset" else abspath(value)]
    if args.records:
        command += ["--records", *[abspath(p) for p in args.records]]
    if args.cross:
        command.append("--cross")
    result["reproduceCommand"] = reproduce_command("answers_check", command)
    return result, (0 if result["passed"] else 2)


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
