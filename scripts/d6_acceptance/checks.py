"""D6-1 local acceptance, stream C (answers, retell, consistency, dialogue plan, plan-text, diagnose, dup hits,
speech volume, feedback-ingest).

Runs each formal command as a CLI on the real D6-0 artifacts in V (runs/pilot-v2, gitignored) and compares with the
D6-0 temp scripts' recorded outputs (V/r15/rerun-outputs) or live temp-script runs. Reads only; writes nothing.
Not bundled. Each row: name, command, ok (matches the temp script or the expected new-rule outcome), detail.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ROOT / "skills/drama-studio/scripts"
PY = [sys.executable, "-B"]


def cli(module, *args, cwd):
    command = [*PY, str(CHECKS / f"{module}.py"), *map(str, args)]
    run = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    try:
        out = json.loads(run.stdout) if run.stdout.strip() else json.loads(run.stderr)
    except json.JSONDecodeError:
        out = {"unparsed": (run.stdout or run.stderr)[:500]}
    return run.returncode, out, " ".join(command[2:])


def old(V, name):
    return json.loads((V / "r15/rerun-outputs" / f"{name}.json").read_text(encoding="utf-8"))


def row(name, command, ok, **detail):
    return {"stream": "C", "name": name, "command": command, "ok": bool(ok), **detail}


def acceptance_answers(V):
    rows = []
    questions = V / "questions/dialogue-check-questions-v1.json"
    for tag, name in (("g1-a", "10-check-answers-g1-a"), ("g1-b", "11-check-answers-g1-b")):
        code, out, cmd = cli("answers_check", f"r15/check-ep006A-{tag}.json", "--questions", questions, cwd=V)
        rec, ref = out["records"][0], old(V, name)
        same = rec["errors"] == ref["errors"] and [rec["counts"][k] for k in ("holds", "notHolds", "not_evaluable", "n/a")] == \
            [ref["counts"][k] for k in ("holds", "notHolds", "not_evaluable", "na")]
        rows.append(row(f"check-answers {tag}", cmd, same and code == 0, exitCode=code, counts=rec["counts"]))
    # 追问单旧记录（无 promptVersion）：新旧两条规则并排，新规则多报的按类别归档
    files = sorted(set(sum((glob.glob(str(V / p)) for p in ("reality-check/RC-*.json", "r4/RC-*.json", "r4b/RC-*.json",
                                                              "r5rc/RC-*.json", "r5rc/r2/RC-*.json")), [])))
    files = [f for f in files if "answers" in json.loads(Path(f).read_text(encoding="utf-8"))]
    rq = V / "questions/reality-check-questions-v1.json"
    code, out, cmd = cli("answers_check", *files, "--questions", rq, "--function-map", "r15/function-map-v1.2.json",
                         "--cross", cwd=V)
    temp_errors = 0
    for f in files:
        run = subprocess.run([*PY, str(V / "tools/check_answers.py"), f, "--questions", str(rq)], capture_output=True, text=True)
        temp_errors += len(json.loads(run.stdout)["errors"]) if run.stdout.strip() else 0
    kinds = {}
    for rec in out["records"]:
        for error in rec["errors"]:
            key = ("promptVersion" if "promptVersion" in error else "loadBearingBasis" if "loadBearingBasis" in error
                   else "loadBearingWhy" if "loadBearingWhy" in error else "disposition" if "disposition" in error
                   else "missing-question" if "一条回答都没有" in error else "outcome" if "outcome" in error else "other")
            kinds[key] = kinds.get(key, 0) + 1
    explained = not kinds.get("other") and not kinds.get("missing-question") and not kinds.get("outcome")
    rows.append(row("check-answers reality-check old records", f"{cmd[:200]} … ({len(files)} files)", explained and code == 2,
                    exitCode=code, records=len(files), tempScriptErrors=temp_errors, newRuleErrorsByKind=kinds,
                    recordsFailing=sum(bool(r["errors"]) for r in out["records"]),
                    missingWithoutSearchScope=sum(len(r["reports"]) for r in out["records"]),
                    coverageUncovered=sum(len(r["coverage"].get("uncovered", [])) for r in out["records"]),
                    crossInconsistent=len(out["cross"]["inconsistent"]),
                    explanation="旧记录全无 promptVersion；loadBearingBasis 是自由文本、disposition.to 用 decision_queue／"
                                "license_pending，新枚举（决定 #8、#9）下都报；问题子集按 scopeOfQuestions 认"))
    return rows


def acceptance_retell(V):
    rows = []
    summary = {f["file"]: f["counts"] for f in json.loads((V / "r15/factrefs-summary.json").read_text(encoding="utf-8"))["files"]}
    cases = [("06-retell-check-005", "retell-plan-005", "005"), ("07-retell-check-006A", "retell-plan-006A", "006A"),
             ("08-retell-check-g1-a", "retell-ep006A-g1-a", "006A"), ("09-retell-check-g1-b", "retell-ep006A-g1-b", "006A"),
             (None, "retell-ep006A-g2", "006A"), (None, "retell-plan-006B", "006B")]
    for name, record, ep in cases:
        plan = f"r8/episode-plan-{ep}.json"
        code, out, cmd = cli("retell_check", f"r15/{record}.json", "--plan", plan, cwd=V)
        if name:
            ref = old(V, name)
            facts_same = [f["status"] for f in out["facts"]] == [f["status"] for f in ref["facts"]]
            same = facts_same and out["closingEvent"]["status"] == ref["closingEvent"]["status"]
            # D6-2 §5 #24: the closing beat also counts its shared two-character pieces; a paraphrased stop the D6-0
            # script read as partial is retold now
            paraphrase = facts_same and (ref["closingEvent"]["status"], out["closingEvent"]["status"]) == ("partial", "retold")
            rows.append(row(f"retell-check {record} (keywords)", cmd, same and code == 0, counts=out["counts"],
                            **({"explanation": f"收尾拍：临时脚本 partial，现在 retold（复述换了说法，两字片段共有 "
                                                f"{out['closingEvent'].get('pairsShared')}；D6-2 决定 §5 #24）"} if paraphrase and not same else {})))
        code, out, cmd = cli("retell_check", f"r15/{record}.json", "--plan", plan, "--factrefs", f"r15/factrefs-{record}.json", cwd=V)
        expected = summary.get(f"factrefs-{record}.json")
        rows.append(row(f"retell-check {record} (factRefs)", cmd, out.get("counts") == expected and code == 0,
                        counts=out.get("counts"), factrefsSummary=expected, notes=out.get("notes")))
    return rows


def acceptance_rest(V):
    rows = []
    code, out, cmd = cli("consistency", "r13/check-ep006A-g1-a.json", "r13/check-ep006A-g1-b.json", cwd=V)
    ref = old(V, "18-consistency-g1-a-b")
    rows.append(row("consistency g1 a/b", cmd, out["counts"] == ref["counts"] and code == 0, counts=out["counts"], notes=out["notes"]))

    code, out, cmd = cli("dialogue_plan_check", "r11/dialogue-plan-ep006A-v2.1.json", "--episode-plan", "r8/episode-plan-006A.json",
                         "--knows", "r8/knows-ep006A.json", cwd=V)
    ref = old(V, "05-dialogue-check-g1-v2.1")
    shape = lambda rules: {k: (r["status"], {kk: len(v) for kk, v in r.items() if isinstance(v, list)}) for k, r in rules.items()}  # noqa: E731
    rows.append(row("dialogue-plan check v2.1", cmd, shape(out["rules"]) == shape(ref["rules"]) and code == 0, exitCode=code))

    code, out, cmd = cli("plan_text_consistency", "r12/plan-text-map-ep006A-v2.json", "--dialogue-plan", "r11/dialogue-plan-ep006A-v2.json",
                         "--episode-plan", "r8/episode-plan-006A.json", cwd=V)
    ref = old(V, "25-plan-text-consistency-g1")
    same = all(out["rules"][k]["status"] == ref["rules"][k]["status"] and len(out["rules"][k]["items"]) == len(ref["rules"][k]["items"])
               for k in ref["rules"])
    rows.append(row("plan-text-consistency g1", cmd, same and code == 0, exitCode=code))

    for name, args in (("19-diagnose-g1", ["r12/ep-006A.g1.md", "--plan-text-map", "r12/plan-text-map-ep006A-v2.json",
                                           "--dialogue-plan", "r11/dialogue-plan-ep006A-v2.json", "--episode-plan", "r8/episode-plan-006A.json"]),
                       ("20-diagnose-f1-vs-e2", ["../pilot-ep006/ep-006.f1.md", "--compare-with", "../b01/ep-006.e2.md"]),
                       ("21-diagnose-e2", ["../b01/ep-006.e2.md"]), ("22-diagnose-w1", ["../input/writer-ep-005.md"])):
        code, out, cmd = cli("diagnose", *args, cwd=V)
        rows.append(row(f"diagnose {name[3:]}", cmd, out["signalCounts"] == old(V, name)["signalCounts"] and code == 0,
                        signalCounts=out["signalCounts"]))

    for name, args in (("16-dup-check-8char", ["--k", 8, "--source-dialogue-plan", "r11/dialogue-plan-ep006A-v2.json"]),
                       ("17-dup-check-13char", ["--k", 13, "--source-corpus-jsonl", "../pilot-ep006/corpus/exchanges.jsonl"])):
        code, out, cmd = cli("dup_check", "--new", "r12/ep-006A.g1.md", "--list-hits", *args,
                             "--exclude-verbatim", "r12/plan-text-map-ep006A-v2.json", cwd=V)
        ref = old(V, name)
        rows.append(row(f"dup-check --list-hits {name[3:]}", cmd,
                        (out["hits"], out["verbatimHits"], out["sourceHanChars"]) == (ref["hits"], ref["verbatimHits"], ref["sourceHanChars"]),
                        hitCount=out["hitCount"]))

    for name, text in (("12-capacity-text-g1", "r12/ep-006A.g1.md"), ("13-capacity-text-f1", "../pilot-ep006/ep-006.f1.md"),
                       ("14-capacity-text-e2", "../b01/ep-006.e2.md"), ("15-capacity-text-w1", "../input/writer-ep-005.md")):
        probe = ("import json,sys; sys.path.insert(0, sys.argv[1]); from checks.episode_check import run_episode_check; "
                 "print(json.dumps(run_episode_check(sys.argv[2], speech=True), ensure_ascii=False))")
        command = [*PY, "-c", probe, str(CHECKS.parent), text]
        run = subprocess.run(command, cwd=V, capture_output=True, text=True)
        try:
            speech = [e["speech"]["speech_chars"] for e in json.loads(run.stdout)["episodes"]]
            error = None
        except (json.JSONDecodeError, KeyError) as exc:
            speech, error = None, (run.stderr or str(exc))[-300:]
        expected = old(V, name)["speechChars"]
        result = row(f"episode-check speech {name[3:]}", f"run_episode_check({text!r}, speech=True)",
                     speech == [expected], speechChars=speech, capacityTextSpeechChars=expected, error=error)
        if speech is None:
            result["explanation"] = ("episode-check 的集标题正则只认数字集号（「# 第6A集」不认），整份报输入错误；"
                                     "这是旧行为，本流不改。口播量本身见 text_lines.speech_chars，与 capacity text 同口径")
        rows.append(result)

    code, out, cmd = cli("feedback_ingest", "../input/feedback/feishu-d610-with-comments.json", "--text", "../b01/ep-006.e2.md", cwd=V)
    levels = [n["level"] for n in out["writerNotes"]]
    expected = ["info_carriage", "info_carriage", "line", "topic", "topic", "line", "info_carriage"]
    rows.append(row("feedback-ingest 7 comments", cmd, levels == expected and code == 0, levels=levels,
                    explanation="对照台词方案 §9.2：c1、c2、c7 信息承载；c4、c5 话题／来回；c3、c6 句",
                    drafts=len(out["derivedDrafts"])))
    return rows


def run(V) -> list[dict]:
    V = Path(V)
    if not V.is_dir():
        return [{"stream": "C", "name": "skipped", "ok": True, "detail": f"{V} 不存在，跳过本地验收"}]
    return acceptance_answers(V) + acceptance_retell(V) + acceptance_rest(V)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    result = run(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["ok"] for r in result) else 2)
