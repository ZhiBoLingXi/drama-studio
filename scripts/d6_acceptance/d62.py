"""D6-2 local acceptance: the D6-0 outline-layer artifacts moved into a project laid out as docs/d6/d6-2-decisions.md §1
says, then `season-check --outline` and the C4 author gate of `context-pack` run on it.

The project is built with `init-project` in a temporary directory; V (runs/pilot-v2, gitignored) is only read, and its
bytes are hashed before and after to prove it. Every move is listed with what was done to the file: `copy` means the
bytes are unchanged (only the path differs). Not bundled. Each row: name, command, ok, detail (and explanation when the
row is an explained difference).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
# (source in V, destination in the project) — the layout of d6-2-decisions.md §1
MOVES = [("r15/function-map-v1.2.json", "planning/function-map.json"),
         ("r15/ledger-ep000.v1.2.json", "planning/ledger/ledger-ep000.json"),
         ("r8/ledger-005.planned-delta.json", "planning/ledger/delta-ep005.planned.json"),
         ("r8/ledger-006A.planned-delta.json", "planning/ledger/delta-ep006A.planned.json"),
         ("r8/ledger-006B.planned-delta.json", "planning/ledger/delta-ep006B.planned.json"),
         ("r7/season-plan-v0.json", "planning/season-plan.json"),
         ("r8/episode-plan-005.json", "planning/episodes/episode-plan-005.json"),
         ("r8/episode-plan-006A.json", "planning/episodes/episode-plan-006A.json"),
         ("r8/episode-plan-006B.json", "planning/episodes/episode-plan-006B.json"),
         ("r15/decisions-merged.v2.json", "planning/decisions.json")]
# answer records and cold retells go to .drama/checks/<source folder>/ under their own names
CHECK_GLOBS = ["reality-check/RC-*.json", "r4/RC-*.json", "r4b/RC-*.json", "r5rc/RC-*.json", "r5rc/r2/RC-*.json",
               "r15/check-*.json", "r15/retell-*.json"]
NOT_RECORDS = {"reality-check/RC-A-index.json"}  # an index of the records, not an answer record
NEW_RULES = ("outline-season-assigned", "outline-ledger-delta", "outline-capacity", "outline-reality-refs", "outline-retell",
             "outline-decision-default", "outline-patch-cap")
# the old rules need a C4 run handoff, its snapshot, a review record and a save receipt; D6-0 wrote none of those
RUN_RULES = ("outline-run", "outline-segment", "outline-snapshot", "outline-characters", "outline-structure", "outline-previous",
             "outline-sequential", "outline-entry-state", "outline-review", "outline-saved")


def row(name, command, ok, **detail):
    return {"stream": "d62", "name": name, "command": command, "ok": bool(ok), **detail}


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout or proc.stderr)
    except ValueError:
        return proc.returncode, {"unparsed": (proc.stdout or proc.stderr)[-300:]}


def digest(V: Path) -> str:
    total = hashlib.sha256()
    for path in sorted(p for p in V.rglob("*") if p.is_file()):
        total.update(path.relative_to(V).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return total.hexdigest()


def build(V: Path, project: Path) -> list[dict]:
    """init-project, then the moves; returns the move log."""
    code, out = tool("init-project", project, "--title", "D6-2 验收（D6-0 集纲层产物）")
    if code != 0:
        raise RuntimeError(f"init-project failed: {out}")
    log = []
    for source, target in MOVES:
        (project / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(V / source, project / target)
        log.append({"from": f"pilot-v2/{source}", "to": target, "conversion": "copy"})
    for pattern in CHECK_GLOBS:
        for path in sorted(V.glob(pattern)):
            source = path.relative_to(V).as_posix()
            if source in NOT_RECORDS:
                continue
            target = Path(".drama/checks") / path.parent.relative_to(V) / path.name
            (project / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, project / target)
            log.append({"from": f"pilot-v2/{source}", "to": target.as_posix(), "conversion": "copy"})
    return log


def season_rows(project: Path) -> list[dict]:
    rows = []
    for span in ("5", "6", "5-6"):
        command = ["season-check", project, "--outline", span, "--allow-offline"]
        code, out = tool(*command)
        failures = out.get("failures", [])
        new = [f for f in failures if f["rule"] in NEW_RULES]
        other = [f for f in failures if f["rule"] not in NEW_RULES + RUN_RULES]
        per = {n: {k: v for k, v in entry.items() if k in ("episodePlans", "unverifiedRealityRefs")} for n, entry in out.get("perOutline", {}).items()}
        rows.append(row(f"season-check --outline {span}：集纲层七条", "drama_tools.py " + " ".join(map(str, command[:1] + ["<project>"] + command[2:])),
                        out.get("ruleSet") == "outline-layer" and not new and not other,
                        ruleSet=out.get("ruleSet"), newRuleFailures=new, otherFailures=other, perOutline=per))
        run_failures = [f for f in failures if f["rule"] in RUN_RULES]
        rows.append(row(f"season-check --outline {span}：旧规则（工位交接记录）", "同上", False, exitCode=code,
                        failuresByRule={r: sum(f["rule"] == r for f in run_failures) for r in sorted({f["rule"] for f in run_failures})},
                        explanation="D6-0 没有按工位走 C4 运行交接、快照、审读记录与保存回执，项目里没有 .drama/runs 等记录；"
                                    "outline-run 不过后其余旧规则对该集不再核。这是记录缺失，不是数据形态问题，也不是规则问题；"
                                    "旧规则按计划 §4.2「仍适用」保留，没有为验收补造交接记录"))
    return rows


def mutation_rows(project: Path, base: Path) -> list[dict]:
    """The new rules are not vacuous on this data: break one record at a time in a copy, exactly that rule fires."""
    rows = []

    def broken(name, change, rule, episodes):
        copy_dir = base / f"mut-{name}"
        shutil.copytree(project, copy_dir, symlinks=True)
        change(copy_dir)
        code, out = tool("season-check", copy_dir, "--outline", "5-6", "--allow-offline")
        fired = {f["rule"] for f in out.get("failures", []) if f["rule"] in NEW_RULES}
        scopes = sorted({f["scope"] for f in out.get("failures", []) if f["rule"] == rule})
        rows.append(row(f"变异：{name} → 只报 {rule}", f"season-check <copy> --outline 5-6 --allow-offline", fired == {rule} and scopes == episodes,
                        fired=sorted(fired), scopes=scopes))

    def edit(path, fn):
        doc = json.loads(path.read_text(encoding="utf-8"))
        fn(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    broken("删 006B 的计划冷读", lambda d: (d / ".drama/checks/r15/retell-plan-006B.json").unlink(), "outline-retell", ["集纲第6集"])
    broken("季编排去掉第5集", lambda d: edit(d / "planning/season-plan.json",
                                        lambda doc: doc.update(episodes=[e for e in doc["episodes"] if str(e.get("episode")).lstrip("0") not in ("5",)])),
           "outline-season-assigned", ["集纲第5集"])
    broken("005 的 capacity.status 改成 exceeds", lambda d: edit(d / "planning/episodes/episode-plan-005.json",
                                                                lambda doc: doc["capacity"].update(status="exceeds")), "outline-capacity", ["集纲第5集"])
    return rows


def pack_rows(project: Path, base: Path) -> list[dict]:
    """context-pack --role author for a C4 task on the moved project: the C4 checklist (season plan, ledger, function
    map) in the package or exit 2."""
    task = json.loads((ROOT / "skills/drama-studio/schemas/examples/task.json").read_text(encoding="utf-8"))
    task.update(taskId="task-ep007-plan", workstation="C4", goal="按季编排与底账写第7集分集计划", writeScope=[])
    task_path = base / "task-c4.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
    rows = []
    full = ["planning/season-plan.json", "planning/ledger/ledger-ep000.json", "planning/function-map.json"]  # the C4 checklist
    for name, files, expect in (("季编排、底账、功能地图都在包里", full, 0),
                                ("缺季编排", [f for f in full if "season" not in f], 2),
                                ("缺底账", [f for f in full if "ledger" not in f], 2),
                                ("缺功能地图", [f for f in full if "function" not in f], 2)):
        selection = base / f"sel-{expect}-{len(files)}-{name}.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": f, "revision": None}, "partition": "current_plan", "required": True, "reason": "D6-2 验收"}
            for f in files]}, ensure_ascii=False), encoding="utf-8")
        code, out = tool("context-pack", project, "--task", task_path, "--selection", selection, "--role", "author",
                         "--budget", 5_000_000, "--dry-run")
        rows.append(row(f"context-pack --role author（C4）：{name}", f"drama_tools.py context-pack <project> --task <C4> --selection {' '.join(files)} "
                        "--role author --budget 5000000 --dry-run", code == expect, exitCode=code, expected=expect,
                        errors=out.get("errors", [])[:2]))
    return rows


def run(V) -> list[dict]:
    V = Path(V).resolve()
    missing = [source for source, _ in MOVES if not (V / source).is_file()]
    if missing:
        return [{"skipped": True, "name": "D6-2 集纲层产物搬运", "reason": f"V 里缺：{missing}"}]
    before = digest(V)
    rows = []
    with tempfile.TemporaryDirectory() as base:
        base = Path(base)
        project = base / "outline-project"
        log = build(V, project)
        converted = [m for m in log if m["conversion"] != "copy"]
        rows.append(row("搬成项目记录形态（init-project＋d6-2-decisions §1 布局）", "init-project <tmp>; copy per MOVES/CHECK_GLOBS",
                        True, moved=len(log), planning=sum(m["to"].startswith("planning/") for m in log),
                        checks=sum(m["to"].startswith(".drama/checks/") for m in log), conversions=converted or "无：全部逐字节复制，只改路径",
                        moves=[m for m in log if m["to"].startswith("planning/")]))
        rows += season_rows(project) + mutation_rows(project, base) + pack_rows(project, base)
    after = digest(V)
    rows.append(row("V 未被改动", "sha256 of every file under V, before and after", before == after, before=before[:16], after=after[:16]))
    return rows


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    print(json.dumps(run(target), ensure_ascii=False, indent=2))
