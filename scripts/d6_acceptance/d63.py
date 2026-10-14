"""D6-3 local acceptance: the D6-0 dialogue-layer records of episode 6A moved into a project laid out as
docs/d6/d6-3-decisions.md §3 says, then `season-check --episodes 6`, the revision-list scan and the C5 package gates.

The project is built with `init-project` in a temporary directory; V (runs/pilot-v2, gitignored) is only read, and its
bytes are hashed before and after. Every move is listed with what was done to the file: `copy` keeps the bytes; `rerun`
means the D6-0 record came from a temporary script whose output the formal command cannot recognise, so the formal
command was run on the same inputs and its output saved instead (its result is compared with the D6-0 record in the
same row). Nothing is written that D6-0 did not have. Not bundled. Each row: name, command, ok, detail (and
explanation when the row is an explained difference).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
COPIES = [("r11/dialogue-plan-ep006A-v2.1.json", "planning/dialogue/dialogue-plan-006A.json"),
          ("r11/dialogue-target-v0.1.json", "planning/dialogue-target.json"),
          ("r12/ep-006A.g1.md", "runs/ep006A/ep-006A.g1.md"),
          ("r12/ep-006A.g2.md", "runs/ep006A/ep-006A.g2.md"),
          ("r15/retell-ep006A-g1-a.json", ".drama/checks/retell-ep006A-g1-a.json"),
          ("r15/retell-ep006A-g1-b.json", ".drama/checks/retell-ep006A-g1-b.json"),
          ("r15/retell-ep006A-g2.json", ".drama/checks/retell-ep006A-g2.json"),
          ("r15/check-ep006A-g1-a.json", ".drama/checks/check-ep006A-g1-a.json"),
          ("r15/check-ep006A-g1-b.json", ".drama/checks/check-ep006A-g1-b.json"),
          ("r15/check-ep006A-g2-b-delta.json", ".drama/checks/check-ep006A-g2-b-delta.json"),
          ("r15/check-ep006A-g2-b-rv5.json", ".drama/checks/check-ep006A-g2-b-rv5.json"),
          ("r13/revision-list-g1.json", ".drama/checks/revision-list-g1.json")]
# (D6-0 record made by a temporary script, formal command on the same inputs, output in the project, what to compare)
RERUNS = [("r13/plan-text-consistency-g1.json",
           ["plan-text-consistency", "{V}/r12/plan-text-map-ep006A-v2.json", "--dialogue-plan", "{V}/r11/dialogue-plan-ep006A-v2.json",
            "--episode-plan", "{V}/r8/episode-plan-006A.json"], ".drama/checks/plan-text-consistency-ep006A-g1.json", "rules"),
          ("r15/consistency-g1-a-b.json",
           ["answers-consistency", ".drama/checks/check-ep006A-g1-a.json", ".drama/checks/check-ep006A-g1-b.json"],
           ".drama/checks/consistency-ep006A-g1-a-b.json", "counts"),
          ("r13/dup-check-8char-g1.json",
           ["dup-check", "--list-hits", "--k", "8", "--new", "runs/ep006A/ep-006A.g1.md", "--source-dialogue-plan", "{V}/r11/dialogue-plan-ep006A-v2.json",
            "--exclude-verbatim", "{V}/r12/plan-text-map-ep006A-v2.json"], ".drama/checks/dup8-ep006A-g1.json", "hitCount"),
          ("r13/dup-check-13char-g1.json",
           ["dup-check", "--list-hits", "--k", "13", "--new", "runs/ep006A/ep-006A.g1.md", "--source-corpus-jsonl", "{V}/../pilot-ep006/corpus/exchanges.jsonl",
            "--exclude-verbatim", "{V}/r12/plan-text-map-ep006A-v2.json"], ".drama/checks/dup13-ep006A-g1.json", "hitCount"),
          ("r13/genre-scan-g1.json", ["corpus", "lexicon", "runs/ep006A/ep-006A.g1.md", "--project-genre", "现实"],
           ".drama/checks/genre-ep006A-g1.json", "hitCount")]
DIALOGUE_RULES = ("dialogue-plan", "target-ref", "plan-text-align", "cold-retell", "situation-check", "consistency-record",
                  "retell-after-revise", "constraint-origin", "no-numeric-dialogue-constraint", "fixlist-no-lines", "dup-two-tier",
                  "genre-lexicon")


def row(name, command, ok, **detail):
    return {"stream": "d63", "name": name, "command": command, "ok": bool(ok), **detail}


def tool(*args, cwd=None):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    try:
        return proc.returncode, json.loads(proc.stdout or proc.stderr), proc.stdout
    except ValueError:
        return proc.returncode, {"unparsed": (proc.stdout or proc.stderr)[-300:]}, proc.stdout


def digest(V: Path) -> str:
    total = hashlib.sha256()
    for path in sorted(p for p in V.rglob("*") if p.is_file()):
        total.update(path.relative_to(V).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return total.hexdigest()


def build(V: Path, project: Path) -> tuple[list[dict], list[dict]]:
    tool("init-project", project, "--title", "D6-3 验收（D6-0 第 6A 集台词层记录）")
    log, rows = [], []
    for source, target in COPIES:
        (project / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(V / source, project / target)
        log.append({"from": f"pilot-v2/{source}", "to": target, "conversion": "copy"})
    for source, args, target, field in RERUNS:
        args = [a.replace("{V}", str(V)) for a in args]
        code, out, text = tool(*args, cwd=project)
        (project / target).write_text(text, encoding="utf-8")
        old = json.loads((V / source).read_text(encoding="utf-8"))
        if field == "rules":
            same = {k: (r.get("status"), len(r.get("items") or [])) for k, r in (out.get("rules") or {}).items() if k in old["rules"]} == \
                   {k: (r.get("status"), len(r.get("items") or [])) for k, r in old["rules"].items()}
        else:
            same = out.get(field) == old.get(field)
        log.append({"from": f"pilot-v2/{source}", "to": target, "conversion": "rerun",
                    "why": "D6-0 临时脚本的输出，正式命令认不出（reproduceCommand 指向临时脚本，或没有集号字段）；按相同输入用正式命令重跑"})
        rows.append(row(f"重跑转换 {Path(source).name} → {Path(target).name}", "drama_tools.py " + " ".join(args[:2]) + " …",
                        same and code in (0, 2), exitCode=code, compared=field, sameAsD60=same))
    return log, rows


def season_rows(project: Path) -> list[dict]:
    command = ["season-check", project, "--episodes", "6"]
    code, out, _ = tool(*command)
    failures = out.get("failures", [])
    layer = [f for f in failures if f["rule"] in DIALOGUE_RULES]
    other = [f for f in failures if f["rule"] not in DIALOGUE_RULES]
    listed = out.get("dialogueLayerRules", {})
    rows = [row("season-check --episodes 6：台词层规则", "drama_tools.py season-check <project> --episodes 6",
                out.get("episodeRuleSet") == "dialogue-layer" and not layer,
                episodeRuleSet=out.get("episodeRuleSet"), layerFailures=layer,
                rules={k: v["status"] for k, v in listed.items()}),
            row("season-check --episodes 6：旧规则（工位交接记录）", "同上", False, exitCode=code,
                failuresByRule={r: sum(f["rule"] == r for f in other) for r in sorted({f["rule"] for f in other})},
                notEvaluated=[k for k, v in listed.items() if v["status"] == "not_evaluated"],
                explanation="D6-0 没有按工位留 C1–C5 运行交接（upstream、c4、author 不过），所以按运行判的台词层规则"
                            "（retell-after-revise、constraint-origin、no-numeric-dialogue-constraint）在这里 not_evaluated。"
                            "这是记录缺失，不是数据形态问题也不是规则问题；没有补造交接"),
            row("season-check --episodes 6：不出现旧三条", "同上",
                not {f["rule"] for f in failures} & {"voice-card", "dialogue-pass", "dialogue-read"} and "legacyDialogueRules" in out,
                legacyDialogueRules=out.get("legacyDialogueRules"))]
    return rows


def mutation_rows(project: Path, base: Path) -> list[dict]:
    """Each dialogue-layer rule that judged a record here is not vacuous: remove or break one record in a copy."""
    rows = []

    def broken(name, change, rule):
        copy_dir = base / f"mut-{name}"
        shutil.copytree(project, copy_dir, symlinks=True)
        change(copy_dir)
        code, out, _ = tool("season-check", copy_dir, "--episodes", "6")
        fired = {f["rule"] for f in out.get("failures", []) if f["rule"] in DIALOGUE_RULES}
        rows.append(row(f"变异：{name} → 只报 {rule}", "season-check <copy> --episodes 6", fired == {rule}, fired=sorted(fired)))

    def edit(path, fn):
        doc = json.loads(path.read_text(encoding="utf-8"))
        fn(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    broken("删正文冷读复述", lambda d: [p.unlink() for p in (d / ".drama/checks").glob("retell-ep006A-*.json")], "cold-retell")
    broken("删设计依据一致性", lambda d: (d / ".drama/checks/plan-text-consistency-ep006A-g1.json").unlink(), "plan-text-align")
    broken("删两份处境核对的一致性记录", lambda d: (d / ".drama/checks/consistency-ep006A-g1-a-b.json").unlink(), "consistency-record")
    broken("删 13 字档命中记录", lambda d: (d / ".drama/checks/dup13-ep006A-g1.json").unlink(), "dup-two-tier")
    broken("修订单写进一句台词", lambda d: edit(d / ".drama/checks/revision-list-g1.json",
                                       lambda doc: doc["items"][0].update(action="改成：\n闻栀：别碰开关，跟我出去。")), "fixlist-no-lines")
    broken("对话表不引台词目标", lambda d: edit(d / "planning/dialogue/dialogue-plan-006A.json",
                                       lambda doc: doc.update(basedOn={k: v for k, v in (doc.get("basedOn") or {}).items()
                                                                        if k not in ("target", "dialogueTarget")})), "target-ref")
    return rows


def gate_rows(V: Path, project: Path, base: Path) -> list[dict]:
    """contract-check revision-list on the D6-0 list and plan-text-map on its two maps (read in V, not copied); the C5b
    package needs a dialogue plan passing contract-check."""
    rows = []
    code, out, _ = tool("contract-check", "revision-list", project / ".drama/checks/revision-list-g1.json")
    rows.append(row("contract-check revision-list（D6-0 第 6A 集修订单）", "drama_tools.py contract-check revision-list <revision-list-g1>",
                    code == 0, exitCode=code, errors=out.get("errors"), legacyForms=out.get("legacyForms")))
    for name in ("r12/plan-text-map-ep006A-v2.json", "r12/plan-text-map-ep006A-v2.g2.json"):
        code, out, _ = tool("contract-check", "plan-text-map", V / name)
        rows.append(row(f"contract-check plan-text-map（D6-0 {Path(name).name}）", f"drama_tools.py contract-check plan-text-map <{name}>",
                        code == 0, exitCode=code, errors=out.get("errors"), legacyForms=out.get("legacyForms")))
    task = json.loads((ROOT / "skills/drama-studio/schemas/examples/task.json").read_text(encoding="utf-8"))
    task.update(taskId="task-ep006A-c5b", layer="C5b", writeScope=[], dialogueTarget={"targetId": "pilot", "revision": "v0.1"})
    task_path = base / "task-c5b.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
    broken_plan = json.loads((project / "planning/dialogue/dialogue-plan-006A.json").read_text(encoding="utf-8"))
    broken_plan.pop("infoLedger", None)
    (project / "planning/dialogue/dialogue-plan-006A.broken.json").write_text(json.dumps(broken_plan, ensure_ascii=False), encoding="utf-8")
    for name, plan, expect in (("对话表过 contract-check", "planning/dialogue/dialogue-plan-006A.json", 0),
                               ("对话表不过 contract-check（去掉 infoLedger）", "planning/dialogue/dialogue-plan-006A.broken.json", 2)):
        selection = base / f"sel-c5b-{expect}.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": plan, "revision": None}, "partition": "current_plan", "required": True, "reason": "D6-3 验收"}]},
            ensure_ascii=False), encoding="utf-8")
        code, out, _ = tool("context-pack", project, "--task", task_path, "--selection", selection, "--role", "author",
                            "--budget", 2_000_000, "--dry-run")
        rows.append(row(f"context-pack --role author（C5b）：{name}", "drama_tools.py context-pack <project> --role author …（task.layer C5b）",
                        code == expect, exitCode=code, expected=expect, errors=(out.get("errors") or [])[:1]))
    (project / "planning/dialogue/dialogue-plan-006A.broken.json").unlink()
    # samples straight from the dialogue plan's exemplars (D6-3 ruling): masked records only, at most 2 masked lines a topic
    selection = base / "sel-c5b-samples.json"
    selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
        {"ref": {"kind": "local_file", "id": "planning/dialogue/dialogue-plan-006A.json", "revision": None}, "partition": "current_plan",
         "required": True, "reason": "D6-3 验收"}]}, ensure_ascii=False), encoding="utf-8")
    plan_path = project / "planning/dialogue/dialogue-plan-006A.json"
    code, out, _ = tool("context-pack", project, "--task", task_path, "--selection", selection, "--role", "author", "--budget", 2_000_000,
                        "--dry-run", "--exemplars", plan_path)
    samples = out.get("samples") or {}
    packed = [i for i in out.get("items", []) if i["ref"].startswith("sample")]
    capped = all(n <= 2 for n in (samples.get("maskedLinesPerTopic") or {}).values())
    rows.append(row("context-pack --role author（C5b）--exemplars <第 6A 集对话表 v2.1>", "drama_tools.py context-pack <project> --role author "
                    "--exemplars planning/dialogue/dialogue-plan-006A.json --dry-run", code == 0 and packed and capped
                    and all(i["partition"] == "samples" for i in packed), exitCode=code, packed=len(packed),
                    omittedForQuoteCap=samples.get("omittedForQuoteCap"), maskedLinesPerTopic=samples.get("maskedLinesPerTopic"),
                    unresolved=samples.get("unresolved"), errors=(out.get("errors") or [])[:1]))
    return rows


def run(V) -> list[dict]:
    V = Path(V).resolve()
    missing = [source for source, _ in COPIES if not (V / source).is_file()] + [s for s, *_ in RERUNS if not (V / s).is_file()]
    if missing:
        return [{"skipped": True, "name": "D6-3 台词层记录搬运", "reason": f"V 里缺：{missing}"}]
    before = digest(V)
    rows = []
    with tempfile.TemporaryDirectory() as base:
        base = Path(base)
        project = base / "dialogue-project"
        log, rerun_rows = build(V, project)
        rows.append(row("搬成项目记录形态（init-project＋d6-3-decisions §3 布局）", "init-project <tmp>; copy per COPIES, rerun per RERUNS",
                        True, moved=len(log), copies=sum(m["conversion"] == "copy" for m in log),
                        reruns=sum(m["conversion"] == "rerun" for m in log), moves=log))
        rows += rerun_rows + season_rows(project) + mutation_rows(project, base) + gate_rows(V, project, base)
    after = digest(V)
    rows.append(row("V 未被改动", "sha256 of every file under V, before and after", before == after, before=before[:16], after=after[:16]))
    return rows


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    print(json.dumps(run(target), ensure_ascii=False, indent=2))
