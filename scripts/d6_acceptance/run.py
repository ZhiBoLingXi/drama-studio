"""D6-1/D6-2/D6-3 local acceptance, the single entry point: collect the stream segments (D6-2 adds d62: the outline-layer
artifacts moved into a project; D6-3 adds d63: the episode 6A dialogue-layer records; D6-4 adds d64: corpus and feedback), add the integration
checks, print one table.

    python3 -B scripts/d6_acceptance/run.py [V]

V is the private D6-0 run directory (default projects/qige-xiongdi/runs/pilot-v2, gitignored). When it does not exist,
every V-based row is skipped and says so. Reads V and the real projects under projects/; writes only into temporary
directories it removes (the 0.3.6 baseline extracted with `git archive` of the 0.3.6 commit, a merged ledger, a test install). Not bundled.

Every row: {stream, name, command, file, result, consistent, baseline, note}
  result      pass | fail | explained_difference | skipped
  consistent  yes | explained | no | n/a — agreement with the baseline (the D6-0 temp script, 0.3.6, or the module itself)
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
CHECKS = TOOL.parent
SEGMENTS = ("schemas", "ledger", "checks", "corpus", "d62", "d63", "d64")
BASELINE_0_3_6 = "6a0ab3e"  # feat(skill): ... 0.3.6 (#73); VERSION there is 0.3.6
PROJECTS = ("yuanxinsuo", "qige-xiongdi")  # real projects with 0.3.6-era records and no D6 records
LOCK_ARGS = ("--episodes 1-60", "--outline 1-60", "--episodes 1-10 --outline 1-60 --allow-offline", "--episodes 1-60 --revise",
             "--episodes 1-10 --skip-dialogue", "--episodes 1-60 --since 2026-10-01T00:00:00+08:00")


def load(name):
    spec = importlib.util.spec_from_file_location(f"d6_acceptance_{name}", Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(stream, name, command, file, result, consistent, baseline, note):
    return {"stream": stream, "name": name, "command": command, "file": file, "result": result,
            "consistent": consistent, "baseline": baseline, "note": note}


def files_in(command, V):
    """The V files a command names, relative to V's parent (pilot-v2/…, pilot-ep006/…)."""
    found = []
    for token in shlex.split(command or "") if isinstance(command, str) else []:
        path = Path(token) if os.path.isabs(token) else Path(V) / token
        if path.is_file() and path.resolve().is_relative_to(Path(V).parent.resolve()):
            found.append(str(path.resolve().relative_to(Path(V).parent.resolve())))
    return found


def normalize(stream, raw, V):
    """The four segments report in three shapes; map each to the common row."""
    if raw.get("skipped"):
        return row(stream, raw.get("name") or raw.get("object"), raw.get("command"), raw.get("file"), "skipped", "n/a", "none",
                   raw.get("reason"))
    if stream == "schemas":
        file = str(Path(raw["file"]).resolve().relative_to(Path(V).parent.resolve())) if Path(raw["file"]).resolve().is_relative_to(Path(V).parent.resolve()) else raw["file"]
        if raw["passed"]:
            return row(stream, f"contract-check {raw['object']}", raw["reproduceCommand"], file, "pass", "n/a", "none", raw["notEvaluated"] or None)
        legacy = raw["failedOnlyOnLegacyForms"]
        if not legacy and raw.get("explanation"):  # a real violation, explained against the D6-0 audit or a later file
            return row(stream, f"contract-check {raw['object']}", raw["reproduceCommand"], file, "explained_difference", "n/a", "none",
                       {"errors": raw["errors"][:3], **raw["explanation"]})
        return row(stream, f"contract-check {raw['object']}", raw["reproduceCommand"], file,
                   "explained_difference" if legacy else "fail", "n/a", "none",
                   ("只因 D6-0 的旧写法不过（schema 取规范写法）：" + ", ".join(raw["legacyForms"])) if legacy else raw["errors"][:3])
    if stream == "ledger":
        result = {"match": "pass", "explained_difference": "explained_difference", "mismatch": "fail", "skipped": "skipped"}[raw["result"]]
        consistent = {"match": "yes", "explained_difference": "explained", "mismatch": "no", "skipped": "n/a"}[raw["result"]]
        return row(stream, raw["name"], raw["command"], files_in(raw["command"], V), result, consistent, "D6-0 temp script", raw["detail"])
    note = raw.get("explanation") or {k: v for k, v in raw.items() if k not in ("stream", "name", "command", "ok", "exitCode")}
    if raw["ok"]:
        return row(stream, raw["name"], raw["command"], files_in(raw["command"], V), "pass", "yes", "D6-0 temp script", note)
    explained = bool(raw.get("explanation"))
    return row(stream, raw["name"], raw["command"], files_in(raw["command"], V), "explained_difference" if explained else "fail",
               "explained" if explained else "no", "D6-0 temp script", note)


def tool(*args, cwd=None):
    proc = subprocess.run(["python3", "-B", str(TOOL), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


# ---- stream E: integration ------------------------------------------------------------------------------------

def lock_rows():
    """season-check on the real 0.3.6-era projects: stdout and exit code equal 0.3.6 byte for byte (no new keys on legacy)."""
    projects = [ROOT / "projects" / name for name in PROJECTS if (ROOT / "projects" / name / ".drama").is_dir()]
    if not projects:
        return [row("E", "season-check legacy lock", None, None, "skipped", "n/a", "0.3.6", "projects/ 下没有真实项目")]
    rows = []
    with tempfile.TemporaryDirectory() as base:
        # main moved past 0.3.6 when the D6 work merged (PR #81), so the baseline is pinned to the 0.3.6 release commit
        archive = subprocess.run(f"git archive {BASELINE_0_3_6} skills/drama-studio | tar -x -C {shlex.quote(base)}", shell=True, cwd=ROOT,
                                 capture_output=True, text=True)
        old_tool = Path(base) / "skills/drama-studio/scripts/drama_tools.py"
        if archive.returncode != 0 or not old_tool.is_file():
            return [row("E", "season-check legacy lock", None, None, "skipped", "n/a", "0.3.6", f"取不到 0.3.6（{BASELINE_0_3_6}）：{archive.stderr[-200:]}")]
        for project in projects:
            for args in LOCK_ARGS:
                command = ["season-check", str(project), *args.split()]
                old = subprocess.run(["python3", "-B", str(old_tool), *command], capture_output=True, text=True)
                # D6-3: the three old dialogue rules run only with --legacy-dialogue; with it the output is 0.3.6's
                flagged = command + (["--legacy-dialogue"] if "--episodes" in args else [])
                code, out, err = tool(*flagged)
                same = out == old.stdout and code == old.returncode
                rows.append(row("E", f"season-check legacy lock {project.name} {args}" + (" --legacy-dialogue" if flagged != command else ""),
                                shlex.join(["python3", "-B", str(TOOL), *flagged]),
                                f"projects/{project.name}/.drama", "pass" if same else "fail", "yes" if same else "no", "0.3.6",
                                f"标准输出与 0.3.6 逐字节{'相同' if same else '不同'}（旧项目不加 ruleSet／episodeRuleSet），"
                                f"退出码 {code}（0.3.6 为 {old.returncode}）"))
                if flagged == command:
                    continue
                code, out, err = tool(*command)  # without the flag: the old three are gone and nothing new fails
                mine, theirs = json.loads(out), json.loads(old.stdout)
                key = lambda f: (f["scope"], f["rule"], f["message"])  # noqa: E731
                new = [f for f in mine["failures"] if key(f) not in {key(g) for g in theirs["failures"]}]
                gone = sorted({f["rule"] for f in theirs["failures"]} - {f["rule"] for f in mine["failures"]})
                old_three = {f["rule"] for f in mine["failures"]} & {"voice-card", "dialogue-pass", "dialogue-read"}
                ok = not new and not old_three and "episodeRuleSet" not in mine
                rows.append(row("E", f"season-check legacy no-flag {project.name} {args}", shlex.join(["python3", "-B", str(TOOL), *command]),
                                f"projects/{project.name}/.drama", "pass" if ok else "fail", "yes" if ok else "no", "0.3.6",
                                f"不带 --legacy-dialogue：没有新失败（{len(new)}），旧三条不出现（{sorted(old_three) or '无'}），"
                                f"比 0.3.6 少的规则 {gone or '无'}；失败 {len(mine['failures'])} 条（0.3.6 为 {len(theirs['failures'])}）"))
    return rows


def wiring_rows(V):
    """drama_tools subcommands print what the module prints, with reproduceCommand rewritten; rerunning it gives the same."""
    media, corpus = "../pilot-ep006/media-profile-v0.json", "../pilot-ep006/corpus/exchanges.jsonl"
    cases = [
        (["capacity", "text"], "capacity.py", ["text"], ["r12/ep-006A.g2.md", "--media", media]),
        (["capacity", "episode"], "capacity.py", ["episode"], ["r8/episode-plan-006A.json", "--media", media, "--corpus", corpus]),
        (["ledger", "replay"], "ledger.py", ["replay"], ["r15/ledger-ep000.v1.2.json", "--at", "6B", "--track", "planned",
                                                         "--delta", "r8/ledger-005.planned-delta.json", "--delta", "r8/ledger-006A.planned-delta.json",
                                                         "--delta", "r8/ledger-006B.planned-delta.json"]),
        (["function-map", "topics"], "function_map.py", ["topics"], ["r15/function-map-v1.2.json"]),
        (["decision", "check"], "decision.py", ["check"], ["r15/decisions-merged.v2.json"]),
        (["retell-check"], "retell_check.py", [], ["r15/retell-plan-006A.json", "--plan", "r8/episode-plan-006A.json"]),
        (["answers-consistency"], "consistency.py", [], ["r13/check-ep006A-g1-a.json", "r13/check-ep006A-g1-b.json"]),
        (["dup-check"], "dup_check.py", [], ["--list-hits", "--k", "8", "--new", "r12/ep-006A.g1.md", "--source-dialogue-plan",
                                              "r11/dialogue-plan-ep006A-v2.1.json"]),
    ]
    rows = []
    for words, script, sub, args in cases:
        direct = subprocess.run(["python3", "-B", str(CHECKS / script), *sub, *args], capture_output=True, text=True, cwd=V)
        code, out, err = tool(*words, *args, cwd=V)
        name = "drama_tools " + " ".join(words)
        try:
            mine, theirs = json.loads(out), json.loads(direct.stdout)
            command = mine.pop("reproduceCommand")
            theirs.pop("reproduceCommand", None)
            again = subprocess.run(shlex.split(command), capture_output=True, text=True)
            # the rerun names files by absolute path; outputs that echo their input paths differ only by that prefix
            rerun = json.loads(again.stdout.replace(str(Path(V).resolve()) + "/", "").replace(str(Path(V).parent.resolve()) + "/", "../"))
            rerun.pop("reproduceCommand")
        except (ValueError, KeyError) as error:
            rows.append(row("E", name, None, files_in(" ".join(args), V), "fail", "no", "module CLI", f"{type(error).__name__}: {error} {err[-200:]}"))
            continue
        same = mine == theirs and code == direct.returncode and rerun == mine
        rows.append(row("E", name, command, files_in(command, V), "pass" if same else "fail", "yes" if same else "no", "module CLI",
                        f"输出与模块直接运行相同（reproduceCommand 除外）、退出码 {code}；按 reproduceCommand 复跑结果相同"
                        if same else "drama_tools 输出与模块直接运行或复跑不同"))
    return rows


def merge_rows(V):
    parts = sorted(glob.glob(str(Path(V) / "ledger/ledger-ep000.part-*.json")))
    with tempfile.TemporaryDirectory() as base:
        out = Path(base) / "merged.json"
        code, stdout, err = tool("ledger", "merge", *parts, "--out", out, cwd=V)
        merged = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {"entries": []}
    real = json.loads((Path(V) / "ledger/ledger-ep000.json").read_text(encoding="utf-8"))
    same = sorted(e["id"] for e in merged["entries"]) == sorted(e["id"] for e in real["entries"])
    return [row("E", "ledger merge three parts", f"drama_tools.py ledger merge {' '.join(Path(p).name for p in parts)} --out <tmp>",
                [str(Path(p).relative_to(Path(V).parent)) for p in parts] + ["pilot-v2/ledger/ledger-ep000.json"],
                "pass" if same and code == 0 else "fail", "yes" if same else "no", "D6-0 merged ledger-ep000.json",
                f"合并得 {len(merged['entries'])} 条，与 D6-0 合并稿 {len(real['entries'])} 条的 id 集合{'相同' if same else '不同'}")]


def context_rows(V, schema_rows):
    """contract-check with --records on the real function map agrees with stream A's in-process run with full context."""
    records = sorted({p for pattern in ("reality-check/RC-*.json", "r4/RC-*.json", "r4b/RC-*.json", "r5rc/RC-B*.json", "r5rc/r2/RC-*.json",
                                        "r13/check-*.json", "r15/check-*.json") for p in glob.glob(str(Path(V) / pattern))}
                     - {str(Path(V) / "reality-check/RC-A-index.json")})
    code, out, err = tool("contract-check", "function-map", "r15/function-map-v1.2.json", "--records", *records, "--defects", *records,
                          "--cards", "knowledge/cards", cwd=V)
    mine = json.loads(out or err)
    theirs = next((r for r in schema_rows if r.get("file", "").endswith("r15/function-map-v1.2.json")), None)
    same = theirs is not None and mine.get("passed") == theirs.get("passed") and mine.get("errors", [])[:8] == theirs.get("errors")
    return [row("E", "contract-check function-map with --records/--defects/--cards", "drama_tools.py contract-check function-map "
                "r15/function-map-v1.2.json --records <63 records> --defects <same> --cards knowledge/cards", ["pilot-v2/r15/function-map-v1.2.json"],
                "pass" if same else "fail", "yes" if same else "no", "stream A in-process context",
                f"命令行上下文参数接通：文件本身 passed={mine.get('passed')}（判定见流 A 那一行），notEvaluated={mine.get('notEvaluated')}，"
                f"错误与流 A 带全上下文的结果{'一致' if same else '不一致'}")]


def release_rows():
    rows = []
    proc = subprocess.run(["python3", "-B", "scripts/validate.py"], capture_output=True, text=True, cwd=ROOT)
    errors = json.loads(proc.stdout or "{}").get("errors", [])
    known = [e for e in errors if e.startswith("Missing link: docs/") and "mali-story/_doc" in e]
    rows.append(row("E", "validate.py", "python3 -B scripts/validate.py", None, "pass" if len(known) == len(errors) else "fail",
                    "n/a", "none", f"{len(errors)} 条错误，全部是 docs/ 里指向 mali-story 仓库的既有外链（{len(known)} 条）；随包检查通过"
                    if len(known) == len(errors) else errors[:5]))
    proc = subprocess.run(["python3", "-B", "-m", "unittest", "tests.test_skill_routing"], capture_output=True, text=True, cwd=ROOT)
    rows.append(row("E", "test_skill_routing", "python3 -B -m unittest tests.test_skill_routing", None,
                    "pass" if proc.returncode == 0 else "fail", "n/a", "none", proc.stderr.strip().splitlines()[-1]))
    with tempfile.TemporaryDirectory() as base:
        steps = []
        for step in ("install", "verify"):
            proc = subprocess.run(["python3", "-B", "scripts/install.py", step, "--host", "claude-code", "--skills-dir", base],
                                  capture_output=True, text=True, cwd=ROOT)
            steps.append((step, proc.returncode, json.loads(proc.stdout or "{}")))
        installed = Path(base) / "drama-studio/scripts/drama_tools.py"
        smoke = subprocess.run(["python3", "-B", str(installed), "corpus", "segment", "--help"], capture_output=True, text=True)
    plan = subprocess.run(["python3", "-B", "scripts/install.py", "plan", "--host", "claude-code"], capture_output=True, text=True, cwd=ROOT)
    ok = all(code == 0 and doc.get("ok") for _, code, doc in steps) and smoke.returncode == 0 and plan.returncode == 0
    rows.append(row("E", "install plan / install --skills-dir <tmp> / verify", "python3 -B scripts/install.py {plan,install,verify} --host claude-code",
                    None, "pass" if ok else "fail", "n/a", "none",
                    f"plan: {json.loads(plan.stdout).get('action')}（只读，未动 ~/.claude/skills）；install: {steps[0][2].get('action')} "
                    f"{steps[0][2].get('version')}；verify: {steps[1][2].get('files_verified')} 个文件；装好的 corpus segment --help 退出码 {smoke.returncode}"))
    return rows


# ---- §4.2 acceptance items ------------------------------------------------------------------------------------

def requirement(item, rows, match):
    hits = [r for r in rows if match(r)]
    bad = [r["name"] + " " + str(r["file"]) for r in hits if r["result"] == "fail"]
    status = "not_covered" if not hits else ("met" if not bad else "not_met")
    return {"item": item, "status": status, "rows": len(hits),
            "explained": sum(r["result"] == "explained_difference" for r in hits), "failing": bad[:12]}


def requirements(rows):
    names = lambda *keys: (lambda r: any(k in (r["name"] or "") for k in keys))
    files = lambda pattern, kind=None: (lambda r: (kind is None or (r["name"] or "").endswith(kind)) and any(
        glob.fnmatch.fnmatch(f, pattern) for f in ([r["file"]] if isinstance(r["file"], str) else r["file"] or [])))
    return [
        requirement("function-map-v1（r15/function-map-v1.2.json）", rows, lambda r: "function-map-v1.2" in json.dumps(r["file"])),
        requirement("49＋14 份第一轮回答记录（reality-check／r4／r4b 的 RC-*）：contract-check answers", rows,
                    lambda r: r["name"] == "contract-check answers" and any(f"pilot-v2/{d}/RC-" in r["file"] for d in ("reality-check", "r4", "r4b"))),
        requirement("同上：check-answers", rows, names("check-answers reality-check old records")),
        requirement("三段底账与合并后的 ledger-ep000＋三集 delta", rows,
                    lambda r: "ledger merge three parts" in r["name"] or "ledger-ep000" in json.dumps(r["file"]) or "-delta" in json.dumps(r["file"])),
        requirement("ledger replay 从 ep000 重放到 6B", rows, names("ledger-replay-ep000-to-6B", "drama_tools ledger replay")),
        requirement("season-plan-v0", rows, lambda r: "season-plan-v0" in json.dumps(r["file"])),
        requirement("三份 episode-plan", rows, lambda r: "episode-plan-00" in json.dumps(r["file"])),
        requirement("对话表 v2.1", rows, lambda r: "dialogue-plan-ep006A-v2.1" in json.dumps(r["file"])),
        requirement("retell（计划三份、正文 g1-a／g1-b／g2）", rows, names("retell-check", "contract-check retell-record")),
        requirement("check 记录（对话问题单回答）", rows, names("check-answers g1", "consistency g1", "drama_tools answers-consistency")),
        requirement("capacity 对 006A 分集计划与 g2 正文与临时脚本 ±1 秒", rows, names("capacity-episode-006A", "capacity-text-g2")),
        requirement("season-check 对《渊心锁》与本项目旧记录与 0.3.6 逐字节一致（--episodes 带 --legacy-dialogue）", rows, names("season-check legacy lock")),
        requirement("D6-3：不带 --legacy-dialogue 时旧三条不出现、无新失败", rows, names("season-check legacy no-flag")),
        requirement("validate.py 随包检查；test_skill_routing；install verify", rows, names("validate.py", "test_skill_routing", "install plan")),
        requirement("D6-2：season-check --outline 对搬成项目记录形态的 D6-0 产物（集纲层七条）", rows,
                    lambda r: r["stream"] == "d62" and ("集纲层七条" in r["name"] or "变异" in r["name"] or "旧规则" in r["name"])),
        requirement("D6-2：context-pack --role author（C4）缺季编排、底账或功能地图退出码 2", rows, names("context-pack --role author（C4）")),
        requirement("D6-2：搬运只读 V、不改 V", rows, names("搬成项目记录形态", "V 未被改动")),
        requirement("D6-3：season-check --episodes 对搬成项目记录形态的 D6-0 第 6A 集记录（台词层规则）", rows,
                    lambda r: r["stream"] == "d63" and ("台词层规则" in r["name"] or "变异" in r["name"] or "旧规则" in r["name"]
                                                       or "不出现旧三条" in r["name"] or "重跑转换" in r["name"])),
        requirement("D6-4：corpus agree／defaults／fetch 在小样本与编造台账上可复算", rows,
                    lambda r: r["stream"] == "d64" and r["name"].startswith("corpus")),
        requirement("D6-4：feedback-ingest 对三处反馈各跑一次，派生物都带 fromNotes，原文件不动", rows,
                    lambda r: r["stream"] == "d64" and (r["name"].startswith("feedback-ingest") or "原文件" in r["name"])),
        requirement("D6-3：修订单扫描；C5b 装包要对话表过 contract-check", rows,
                    lambda r: r["stream"] == "d63" and ("revision-list" in r["name"] or "C5b" in r["name"] or "plan-text-map" in r["name"])),
    ]


def run(V) -> dict:
    V = Path(V).resolve()
    rows, schema_raw = [], []
    if V.is_dir():
        for name in SEGMENTS:
            try:
                raw = load(name).run(V)
            except Exception as error:  # a broken segment is a row, not a crash of the whole table
                rows.append(row(name, f"{name} segment", None, None, "fail", "no", "none", f"{type(error).__name__}: {error}"))
                continue
            schema_raw = raw if name == "schemas" else schema_raw
            rows += [normalize(name, r, V) for r in raw]
        for part in (wiring_rows, merge_rows):
            rows += part(V)
        rows += context_rows(V, schema_raw)
    else:
        rows.append(row("E", "V-based rows", None, str(V), "skipped", "n/a", "none", f"{V} 不存在；本地验收要 D6-0 的私有产物"))
    rows += lock_rows() + release_rows()
    summary = {}
    for r in rows:
        summary.setdefault(r["stream"], {}).setdefault(r["result"], 0)
        summary[r["stream"]][r["result"]] += 1
    return {"V": str(V), "summary": summary,
            "unexplained": [{"stream": r["stream"], "name": r["name"], "file": r["file"], "note": r["note"]} for r in rows if r["result"] == "fail"],
            "requirements": requirements(rows), "rows": rows}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    print(json.dumps(run(target), ensure_ascii=False, indent=2))
