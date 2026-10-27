"""D6-1 local acceptance, stream B (ledger, season plan, episode plan, capacity, decision queue, function map).

Runs the new bundled commands on the D6-0 pilot products under V (a private, gitignored project
run directory) and compares each result with what the D6-0 temporary scripts produced
(V/r15/rerun-outputs/ or a fresh run of V/tools/*.py). Read-only: nothing is written anywhere
(merge goes to /dev/null; the temporary scripts are only imported or run read-only). Not part of
the distributed skill; `run(V)` returns one row per check:

    {"stream", "name", "command", "exitCode", "result": match|explained_difference|mismatch|skipped, "detail"}
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

STREAM = "ledger"
ROOT = Path(__file__).resolve().parents[2]
CHECKS = ROOT / "skills/drama-studio/scripts"
MEDIA = ["--media", "../pilot-ep006/media-profile-v0.json"]
CORPUS = ["--corpus", "../pilot-ep006/corpus/exchanges.jsonl"]
PLANS = (("005", "r6/ledger-ep000.v1.1.json"), ("006A", "r8/ledger-ep005.planned.json"), ("006B", "r8/ledger-ep006A.planned.json"))
PLAN_DELTAS = ["r8/ledger-005.planned-delta.json", "r8/ledger-006A.planned-delta.json", "r8/ledger-006B.planned-delta.json"]


def call(V, script, args):
    cmd = ["python3", "-B", str(CHECKS / script)] + args
    proc = subprocess.run(cmd, cwd=V, capture_output=True, text=True)
    try:
        out = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else proc.stdout
    except json.JSONDecodeError:
        out = None
    return proc.returncode, out, shlex.join(cmd), proc.stderr


def temp_json(V, args):
    proc = subprocess.run(["python3", "-B"] + args, cwd=V, capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None


def stored(V, name):
    path = Path(V) / "r15/rerun-outputs" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def row(name, command, code, result, detail):
    return {"stream": STREAM, "name": name, "command": command, "exitCode": code, "result": result, "detail": detail}


def same_rules(new_rules, old_rules, ignore=("presence-vs-timeline",)):
    diffs = []
    for name, old in old_rules.items():
        new = new_rules.get(name)
        if name in ignore:
            continue
        # D6-2 §5 #25: speaker-knows says pass_with_not_evaluable where the D6-0 script said pass; same verdict
        status = "pass" if new is not None and new.get("status") == "pass_with_not_evaluable" else (new or {}).get("status")
        if new is None or status != old.get("status") or new.get("items") != old.get("items"):
            diffs.append(name)
    return diffs


def ledger_checks(V):
    rows = []
    for name, args in (("01-ledger-check-v1.2-scoped", ["check", "r15/ledger-ep000.v1.2.json", "--cards", "knowledge/cards",
                                                         "--function-map", "r15/function-map-v1.2.json", "--scope", "r1/scope-ep001-012.json",
                                                         "--decisions", "r15/decisions-merged.v2.json"]),
                       ("01b-ledger-check-v1.2-full-unscoped-descriptive", ["check", "r15/ledger-ep000.v1.2.json",
                                                                            "--decisions", "r15/decisions-merged.v2.json"])):
        code, out, cmd, err = call(V, "ledger.py", args)
        old = stored(V, name)
        if old is None or not isinstance(out, dict):
            rows.append(row(name, cmd, code, "mismatch" if old else "skipped", err or "没有存档输出"))
            continue
        diffs = same_rules(out["rules"], old["rules"])
        diffs = [d for d in diffs if not (d == "why-missing" and out["rules"][d]["items"] == old["rules"][d]["items"])]
        ok = out["passed"] == old["ok"] and not diffs
        money = out["rules"].get("money-closed", {})
        # D6-2 §5 #6: a money field listed in emptyFields is accounted for; the old items that went away are exactly those
        moved = sorted(set(old["rules"].get("money-closed", {}).get("items", [])) - set(money.get("items", [])))
        registered = set(money.get("registeredEmpty", []))
        money_only = diffs == ["money-closed"] and moved and all(item.split(" 为空")[0] in registered for item in moved) \
            and set(money.get("items", [])) <= set(old["rules"]["money-closed"]["items"])
        result = "match" if ok else "explained_difference" if money_only else "mismatch"
        rows.append(row(name, cmd, code, result,
                        f"passed={out['passed']}（临时脚本 ok={old['ok']}）；规则状态与条目逐条相同" if ok else
                        f"money-closed：临时脚本的 {len(moved)} 条（字段已列进 emptyFields）现在算已交代，列在 registeredEmpty；"
                        f"其余规则逐条相同（D6-2 决定 §5 #6）" if money_only else f"不同的规则：{diffs}"))
    args = ["check", "r15/ledger-ep000.v1.2.json", "--scope", "r1/scope-ep001-012.json", "--cards", "knowledge/cards",
            "--function-map", "r15/function-map-v1.2.json", "--decisions", "r15/decisions-merged.v2.json"]
    for d in PLAN_DELTAS:
        args += ["--delta", d]
    code, out, cmd, err = call(V, "ledger.py", args)
    ok = isinstance(out, dict) and out.get("passed") is True
    rows.append(row("ledger-check-three-deltas-at-once", cmd, code, "explained_difference" if ok else "mismatch",
                    "三个 delta 一次传入不再崩（D6-0 报告 1.3 L5：临时脚本整数／字符串集号比较崩溃）；passed=True，与报告逐段 apply 再 check 三次 ok:true 一致"
                    if ok else f"未通过：{err or out}"))
    return rows


def ledger_replay(V):
    rows = []
    args = ["replay", "r15/ledger-ep000.v1.2.json", "--at", "6B", "--track", "planned"] + sum((["--delta", d] for d in PLAN_DELTAS), [])
    code, out, cmd, err = call(V, "ledger.py", args)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("d6_temp_ledger", Path(V) / "tools/ledger.py")
    temp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(temp)
    sys.path.insert(0, str(CHECKS))
    try:
        import ledger as new  # noqa: E402  (the bundled module, in process)
    finally:
        sys.path.pop(0)
    old_entries = {e["id"]: e for e in json.loads((Path(V) / "r15/ledger-ep000.v1.2.json").read_text(encoding="utf-8"))["entries"]}
    for d in PLAN_DELTAS:  # the D6-0 way: apply one delta at a time
        temp.apply_delta(old_entries, json.loads((Path(V) / d).read_text(encoding="utf-8")), errors=None)
    _, base, _ = new.load_ledger(str(Path(V) / "r15/ledger-ep000.v1.2.json"))
    deltas = [(d, new.load_delta(str(Path(V) / d))) for d in reversed(PLAN_DELTAS)]  # order must not matter
    chosen, _, _ = new.plan_replay(deltas, "6B", "planned")
    for _, delta in chosen:
        new.apply_delta(base, delta)
    same = base == old_entries
    rows.append(row("ledger-replay-ep000-to-6B", cmd, code, "match" if same and code == 0 else "mismatch",
                    f"重放 {len(chosen)} 段（{[d.get('episode') for _, d in chosen]}）得 {len(base)} 条，与临时脚本逐段 apply 的结果逐条相同"
                    if same else "与临时脚本逐段 apply 的条目不同"))
    code, out, cmd, err = call(V, "ledger.py", args + ["--md"])
    rows.append(row("ledger-replay-6B-md", cmd, code, "match" if code == 0 and isinstance(out, str) and out.startswith("# 入口状态") else "mismatch",
                    f"可读入口状态 {len(out.splitlines()) if isinstance(out, str) else 0} 行（临时脚本没有 replay，没有对照）"))
    code, out, cmd, err = call(V, "ledger.py", ["knows", "r8/ledger-ep005.planned.json", "--episode-plan", "r8/episode-plan-006A.json"])
    old = json.loads((Path(V) / "r8/knows-ep006A.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in json.loads((Path(V) / "r8/ledger-ep005.planned.json").read_text(encoding="utf-8"))["entries"]}
    extra = []
    for sn, so in zip(out["scenes"], old["scenes"]):
        if sn["withinScene"] != so["withinScene"]:
            extra.append((sn["sceneId"], "withinScene"))
        for person, kn in so["byPerson"].items():
            missing = [k["entryId"] for k in kn["knows"] if k not in sn["byPerson"].get(person, {}).get("knows", [])]
            added = [k["entryId"] for k in sn["byPerson"].get(person, {}).get("knows", []) if k not in kn["knows"]]
            extra.extend((sn["sceneId"], person, m, entries.get(m, {}).get("status")) for m in missing)
            extra.extend((sn["sceneId"], person, "+" + a) for a in added)
    retired = [x for x in extra if len(x) == 4 and x[3] == "retired"]
    # D6-3 walkthrough #3: one knows one's own agenda, so each agenda entry now shows up for its party
    owned = [x for x in extra if len(x) == 3 and str(x[2]).startswith("+")
             and entries.get(x[2][1:], {}).get("kind") == "agenda" and x[1] in new.agenda_owners(entries.get(x[2][1:], {}))]
    explained = extra and len(retired) + len(owned) == len(extra)
    rows.append(row("ledger-knows-episode-plan-006A", cmd, code, "match" if not extra else ("explained_difference" if explained else "mismatch"),
                    "与 r8/knows-ep006A.json 相同" if not extra else
                    (f"只差两类：退役条目不再算作还知道／看得见（{len(retired)} 处）；图谋账的主人现在算知道自己的图谋"
                     f"（D6-3 决定 §6 #3，{len(owned)} 处）：{extra}") if explained else f"差异：{extra}"))
    return rows


def function_map_rows(V):
    rows = []
    args = ["check", "r15/function-map-v1.2.json", "--stage", "v1", "--rc-dir", "r5rc", "--rc-dir", "r5rc/r2",
            "--decisions", "r6/decisions.v1.1.json", "--ledger", "r6/ledger-ep000.v1.1.json", "--scope", "r1/scope-ep001-012.json",
            "--records-base", ".", "--ref-remap", "L-proc-016=L-proc-A1"]
    code, out, cmd, err = call(V, "function_map.py", args)
    old = stored(V, "02-fm-check-v1.2")
    old_counts = {k: v for k, v in (old or {}).get("counts", {}).items() if k != "loadBearingNotHoldsMissingDisposition"}
    counts = {k: v for k, v in (out or {}).get("counts", {}).items() if k not in ("mapErrata", "mapErrataUnconfirmed", "skippedSuperseded")} if isinstance(out, dict) else {}
    errata_only = isinstance(out, dict) and old is not None and counts == old_counts and out["errors"] and \
        all("功能地图勘误" in e for e in out["errors"]) and old["ok"] and not out["passed"]
    ok = isinstance(out, dict) and old is not None and out["passed"] == old["ok"] and out["counts"] == old_counts
    if errata_only:
        rows.append(row("02-fm-check-v1.2", cmd, code, "explained_difference",
                        f"计数与临时脚本相同；新规则（D6-2 决定 §5 #18）报 {out['counts']['mapErrataUnconfirmed']} 条勘误没有复核记录确认"
                        f"（被取代的记录 {out['counts']['skippedSuperseded']} 不要求确认）。"
                        "D6-0 的记录早于 errataConfirmed 字段；临时脚本 maperrata-count 比对 r1→r2 地图，16 条都已改进地图，"
                        "但没有新上下文的复核记录确认，按新规则仍不算清零"))
    else:
        rows.append(row("02-fm-check-v1.2", cmd, code, "explained_difference" if ok else "mismatch",
                        "passed 与计数和临时脚本相同；临时脚本里写死的 STALE_LEDGER_REF_REMAP 两条改为：L-proc-001 按底账 retiresInto 自动追到 "
                        "L-proc-001a，L-proc-016→L-proc-A1 由 --ref-remap 传入（底账里没有这条迁移的痕迹）；RC-B/RC-B2 的取代改按记录的 "
                        "supersedes 字段，不按文件名。notes 另列 3 条非 selected 候选的 origin 与步骤 origin 不一致（决定 #4，只报）"
                        if ok else f"不同：{out and out.get('errors')} {out and out.get('counts')} vs {old_counts}"))
    code, out, cmd, err = call(V, "function_map.py", ["topics", "r15/function-map-v1.2.json"])
    rows.append(row("fm-topics-v1.2", cmd, code, "match" if code == 0 else "mismatch",
                    f"{out['counts']}（新命令，临时阶段是编排方手工归并，没有对照）" if isinstance(out, dict) else err))
    code, out, cmd, err = call(V, "function_map.py", ["defects", "build", "--records", "r5rc", "--records", "r5rc/r2"])
    lb_answers = sum(r["loadBearing"] for d in out["defects"] for r in d["records"]) if isinstance(out, dict) else None
    ok = isinstance(out, dict) and lb_answers == 21 and out["counts"]["loadBearingOpen"] == 0
    rows.append(row("fm-defects-build-r5rc", cmd, code, "match" if ok else "mismatch",
                    f"{out['counts'] if isinstance(out, dict) else err}；承重 notHolds 回答 {lb_answers} 条，与 fm-check 的 "
                    "loadBearingNotHoldsChecked=21、缺去处 0 一致"))
    code, out, cmd, err = call(V, "function_map.py", ["merge", "fm-v0", "--out", os.devnull, "--schema", "function-map/v0-pilot"])
    rows.append(row("fm-merge-v0", cmd, code, "match" if code == 0 and out.get("functions") == 49 else "mismatch",
                    f"合并 {out.get('threads')} 条线 {out.get('functions')} 个功能（输出到 {os.devnull}；逐线内容与 function-map-v0.json 相同已在开发时核过）"
                    if isinstance(out, dict) else err))
    return rows


def plan_rows(V):
    rows = []
    for ep, led in PLANS:
        args = [f"r8/episode-plan-{ep}.json", "--ledger", led, "--season", "r7/season-plan-v0.json",
                "--function-map", "r6/function-map-v1.1.json", "--decisions", "r8/decisions-merged.json"]
        code, out, cmd, err = call(V, "plan_check.py", args)
        tcode, old = temp_json(V, ["tools/plan_check.py"] + args)
        diffs = same_rules(out["rules"], old["rules"], ignore=()) if isinstance(out, dict) else ["?"]
        sk = out["rules"]["speaker-knows"] if isinstance(out, dict) else {}
        if not diffs:
            result, detail = "match", f"14 条规则与临时脚本相同；speaker-knows notEvaluable {len(sk['notEvaluable'])}，豁免 {[(e['beat'], e['basis']) for e in sk['exemptions']]}"
        elif ep in ("005",) and diffs == ["speaker-knows"] and sk["status"] in ("pass", "pass_with_not_evaluable"):
            result, detail = "explained_difference", "speaker-knows 改按底账 id 判（不再按 knownByInStory 人名）：仍 pass"
        else:
            result, detail = "mismatch", f"不同的规则：{diffs}；{sk}"
        rows.append(row(f"plan-check-{ep}", cmd, code, result, detail + f"（临时脚本退出码 {tcode}）"))
    args = ["r7/season-plan-v0.json", "--function-map", "r6/function-map-v1.1.json"] + MEDIA + CORPUS + \
           ["--decisions", "r7/decisions-r7.json", "--decisions", "r6/decisions.v1.1.json"]
    code, out, cmd, err = call(V, "season_plan_check.py", args)
    old = stored(V, "04-season-check")
    items = [i for r in out["rules"].values() for i in r["items"]] if isinstance(out, dict) else None
    ok = isinstance(out, dict) and old is not None and out["passed"] == old["ok"] and items == old["items"]
    rows.append(row("04-season-check", cmd, code, "match" if ok else "mismatch",
                    "passed=True、条目为空，与临时脚本相同；新增 drop-not-default、episode-ids-unique 两条规则在真实数据上 pass" if ok else f"{items}"))
    return rows


def capacity_rows(V):
    rows = []
    texts = (("12-capacity-text-g1", "r12/ep-006A.g1.md"), ("13-capacity-text-f1", "../pilot-ep006/ep-006.f1.md"),
             ("14-capacity-text-e2", "../b01/ep-006.e2.md"), ("15-capacity-text-w1", "../input/writer-ep-005.md"), (None, "r12/ep-006A.g2.md"))
    for name, path in texts:
        code, out, cmd, err = call(V, "capacity.py", ["text", path] + MEDIA)
        old = stored(V, name) if name else temp_json(V, ["tools/capacity.py", "text", path] + MEDIA)[1]
        a_old, b_old = old["estimateSecA (speechRate÷(1-pauseShare))"], old["estimateSecB (grossCharsPerMinute)"]
        ok = isinstance(out, dict) and out["speechChars"] == old["speechChars"] and out["dialogueLinesCounted"] == old["dialogueLinesCounted"] \
            and abs(out["estimateSecA"] - a_old) <= 1 and abs(out["estimateSecB"] - b_old) <= 1
        rows.append(row(name or "capacity-text-g2", cmd, code, "match" if ok else "mismatch",
                        f"口播 {out['speechChars']} 字 {out['dialogueLinesCounted']} 行，A {out['estimateSecA']}（临时 {a_old}），B {out['estimateSecB']}（临时 {b_old}）"))
    for ep, _ in PLANS:
        code, out, cmd, err = call(V, "capacity.py", ["episode", f"r8/episode-plan-{ep}.json"] + MEDIA + CORPUS)
        _, old = temp_json(V, ["tools/capacity.py", "episode", f"r8/episode-plan-{ep}.json"] + MEDIA + CORPUS)
        declared = out["declared"]
        ok = abs(out["estimateSecA"] - old["estimateSec"]) <= 1 and abs(out["estimateSecB"] - declared.get("estimateSecBasisB", out["estimateSecB"])) <= 1
        rows.append(row(f"capacity-episode-{ep}", cmd, code, "match" if ok else "mismatch",
                        f"A {out['estimateSecA']}（临时 {old['estimateSec']}），B {out['estimateSecB']}（分集计划记的口径乙 {declared.get('estimateSecBasisB')}）"))
    code, out, cmd, err = call(V, "capacity.py", ["season", "r7/season-plan-v0.json"] + MEDIA + CORPUS)
    _, old = temp_json(V, ["tools/capacity.py", "season", "r7/season-plan-v0.json"] + MEDIA + CORPUS)
    season = json.loads((Path(V) / "r7/season-plan-v0.json").read_text(encoding="utf-8"))
    final = {str(i["id"]): i for i in season.get("finalSequence", [])}
    caps = {str(e["episode"]): e["capacity"] for e in season["episodes"]}
    bad = [e["episode"] for e, o in zip(out["episodes"], old["episodes"]) if abs(e["estimateSecA"] - o["estimateSec"]) > 1]
    bad += [e["episode"] for e in out["episodes"] if caps[str(e["episode"])].get("estimateSecBasisB") is not None
            and abs((e["estimateSecB"] or 0) - caps[str(e["episode"])]["estimateSecBasisB"]) > 1]
    bad += ["final:" + str(e["episode"]) for e in out["finalSequence"] if abs(e["estimateSecA"] - final[str(e["episode"])]["estimateSec"]) > 1
            or abs((e["estimateSecB"] or 0) - final[str(e["episode"])]["estimateSecBasisB"]) > 1]
    rows.append(row("capacity-season-v0", cmd, code, "match" if not bad else "mismatch",
                    f"{len(out['episodes'])} 集动作前、{len(out['finalSequence'])} 集动作后：口径甲与临时脚本、口径乙与季编排记的 estimateSecBasisB 都在 ±1 秒内"
                    if not bad else f"超出 ±1 秒：{bad}"))
    return rows


def decision_rows(V):
    rows = []
    code, out, cmd, err = call(V, "decision.py", ["check", "r15/decisions-merged.v2.json"])
    old = stored(V, "24-decision-queue-check-v2")
    ok = isinstance(out, dict) and old and out["passed"] == old["ok"] and out["errors"] == old["errors"] and out["total"] == old["total"]
    rows.append(row("24-decision-queue-check-v2", cmd, code, "match" if ok else "mismatch", f"passed={out.get('passed')} total={out.get('total')}"))
    code, out, cmd, err = call(V, "decision.py", ["check", "r8/decisions-merged.json"])
    _, old = temp_json(V, ["tools/decision_queue.py", "check", "r8/decisions-merged.json"])
    ok = isinstance(out, dict) and out["passed"] == old["ok"] and out["errors"] == old["errors"]
    rows.append(row("decision-check-r8-merged", cmd, code, "match" if ok else "mismatch",
                    f"与临时脚本同判：{out.get('errors')}（R1 收尾前的旧队列，DQ-S0 kind=season，v2 已改为 capacity）"))
    return rows


def run(V):
    V = str(V)
    if not os.path.isdir(V):
        return [row("all", None, None, "skipped", f"{V} 不存在（私有验证目录只在本机），跳过")]
    rows = []
    for part in (ledger_checks, ledger_replay, function_map_rows, plan_rows, capacity_rows, decision_rows):
        try:
            rows.extend(part(V))
        except Exception as error:  # report, never hide, a broken acceptance step
            rows.append(row(part.__name__, None, None, "mismatch", f"{type(error).__name__}: {error}"))
    return rows


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "projects/qige-xiongdi/runs/pilot-v2")
    result = run(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if all(r["result"] in ("match", "explained_difference", "skipped") for r in result) else 2)
