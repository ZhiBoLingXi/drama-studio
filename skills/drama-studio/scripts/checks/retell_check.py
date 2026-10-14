"""retell-check：冷读复述对分集计划 infoLedger 每个 fact 与 exit.closingEvent 的覆盖。

供人看的报告，不是关口：退出码 0（不论 retold／partial／missing），1 输入错误。

判法（修正点 #82）：优先按 factRefs——记录顶层的 `factRefs[]`、读者在事件上注明的
`events[].factRefs[]`，或标注者另给的 `--factrefs` 文件（`facts[].{factId, status, retellRefs}`）；脚本核引用存在（factId 在计划里、
retellRefs 指向复述里真有的 order）。关键词子串命中只作旁证，标 `signalQuality: low`：
复述常是同义改写，关键词不中不等于没复述到。

`--plan` 是对话表时，只核对话表 infoLedger 引用到的 fact，keywords 回 `--episode-plan` 取。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.text_lines import InputError, abspath, is_nonempty, load_json, reproduce_command, run_cli

TARGET_KINDS = {"episode_plan_events", "episode_text"}
STATUSES = ("retold", "partial", "missing")
TOKEN_SPLIT_RE = re.compile(r"[，。、！？\s]+")


def collect_facts(episode_plan: dict) -> list[dict]:
    return [{"infoId": info.get("infoId"), "factId": fact.get("factId"), "text": fact.get("text"),
             "keywords": fact.get("keywords") or []}
            for info in episode_plan.get("infoLedger") or [] for fact in info.get("facts") or []]


def select_dialogue_plan_facts(dialogue_plan: dict, episode_plan: dict, notes: list) -> list[dict]:
    facts = {f["factId"]: f for f in collect_facts(episode_plan)}
    selected = []
    for entry in dialogue_plan.get("infoLedger") or []:
        fid = entry.get("factId")
        if fid in facts:
            selected.append(facts[fid])
        elif fid:
            notes.append(f"对话表引用的 factId {fid!r} 在分集计划 infoLedger 里找不到")
    return selected


def retell_text(retell: dict) -> str:
    parts = [ev.get(k) for ev in retell.get("events") or [] for k in ("what", "why", "sourceLine")]
    parts.append(retell.get("stopsAt"))
    return "\n".join(p for p in parts if isinstance(p, str))


def keyword_evidence(fact: dict, text: str) -> dict:
    keywords = fact["keywords"]
    hit = [kw for kw in keywords if kw and kw in text]
    status = None if not keywords else "retold" if len(hit) == len(keywords) else "partial" if hit else "missing"
    return {"status": status, "hit": hit, "miss": [kw for kw in keywords if kw not in hit], "signalQuality": "low"}


def collect_fact_refs(retell: dict, annotation: dict | None, plan_ids: set, notes: list) -> dict | None:
    """{factId: {"status": 标注的状态或 None, "retellRefs": [order]}}；两处都没有引用时返回 None。"""
    orders = {ev.get("order") for ev in retell.get("events") or []}
    refs = {}
    found = False
    for ev in retell.get("events") or []:
        if "factRefs" not in ev:
            continue
        found = True
        for fid in ev.get("factRefs") or []:
            refs.setdefault(fid, {"status": None, "retellRefs": [], "source": "events.factRefs"})["retellRefs"].append(ev.get("order"))
    if annotation is not None:
        found = True
        for item in annotation.get("facts") or []:
            fid = item.get("factId")
            entry = refs.setdefault(fid, {"status": None, "retellRefs": [], "source": "--factrefs"})
            entry["source"] = "--factrefs"
            if item.get("status") in STATUSES:
                entry["status"] = item["status"]
            elif item.get("status") is not None:
                notes.append(f"factrefs 里 {fid!r} 的 status={item.get('status')!r} 不在 {list(STATUSES)}，按引用判")
            entry["retellRefs"] = sorted(set(entry["retellRefs"]) | set(item.get("retellRefs") or []), key=str)
    if not found:
        return None
    for fid, entry in refs.items():
        if fid not in plan_ids:
            notes.append(f"factRefs 引用的 {fid!r} 不在本次核对的 fact 里")
        dangling = [o for o in entry["retellRefs"] if o not in orders]
        if dangling:
            notes.append(f"{fid!r} 的 retellRefs {dangling} 在复述 events[].order 里找不到")
    return refs


def check_closing_event(episode_plan: dict, retell: dict) -> dict:
    """closingEvent：beatRef 那一拍的文字切出的词是否出现在 stopsAt 里（启发式，信号质量低）。"""
    beat_ref = ((episode_plan.get("exit") or {}).get("closingEvent") or {}).get("beatRef")
    if not beat_ref:
        return {"status": "no_closing_event", "beatRef": None}
    beat_text = next((b.get("text") for sc in (episode_plan.get("events") or {}).get("scenes") or []
                      for b in sc.get("beats") or [] if b.get("beatId") == beat_ref), None)
    if beat_text is None:
        return {"status": "beatRef_not_found", "beatRef": beat_ref}
    stops_at = retell.get("stopsAt") or ""
    hit = [t for t in TOKEN_SPLIT_RE.split(beat_text) if len(t) >= 2 and t in stops_at]
    # a cold reader retells in their own words: also count the beat's two-character pieces found in stopsAt (D6-2 §5 #24)
    pairs = [part[i:i + 2] for part in TOKEN_SPLIT_RE.split(beat_text) for i in range(len(part) - 1)]
    shared = [pair for pair in pairs if pair in stops_at]
    retold = bool(hit) or (pairs and len(shared) * 2 >= len(pairs))
    return {"status": "retold" if retold else "partial" if stops_at else "missing", "beatRef": beat_ref,
            "beatText": beat_text, "stopsAt": stops_at, "tokensHit": hit,
            "pairsShared": f"{len(shared)}/{len(pairs)}", "signalQuality": "low"}


def run_retell_check(retell_path, plan_path, episode_plan_path=None, factrefs_path=None) -> dict:
    retell = load_json(retell_path, "复述记录")
    plan = load_json(plan_path, "计划")
    annotation = load_json(factrefs_path, "factRefs 标注") if factrefs_path else None
    if isinstance(retell.get("factRefs"), list):
        # 记录自带的顶层 factRefs[]（与标注文件同形：factId、status、retellRefs）；两处都有时合并
        annotation = {"facts": retell["factRefs"] + list((annotation or {}).get("facts") or [])}
    notes = []
    if "dialogue-plan" in str(plan.get("schema") or "") or "scenes" in plan and "events" not in plan:
        if not episode_plan_path:
            raise InputError("--plan 是对话表时必须给 --episode-plan（keywords 与 closingEvent 在分集计划里）")
        episode_plan = load_json(episode_plan_path, "分集计划")
        facts = select_dialogue_plan_facts(plan, episode_plan, notes)
    else:
        episode_plan = plan
        facts = collect_facts(plan)
    target = retell.get("target") if isinstance(retell.get("target"), dict) else {}
    if target.get("kind") not in TARGET_KINDS:
        notes.append(f"target.kind={target.get('kind')!r} 不在 {sorted(TARGET_KINDS)}")
    scope = retell.get("readingScope")
    # one item: the target kind itself, or the one file the reader read (D6-2 §5 #24: a file path is not a second item)
    if scope is not None and (not isinstance(scope, list) or len(scope) != 1
                              or (scope[0] in TARGET_KINDS and scope[0] != target.get("kind"))):
        notes.append(f"readingScope={scope!r} 应只有一项（target.kind 或读的那一个文件）且与 target.kind 一致")
    if not is_nonempty(retell.get("promptVersion")):
        notes.append("记录没有 promptVersion（冷读用的提示词版本）；版本不同的两次冷读不直接比")
    text = retell_text(retell)
    refs = collect_fact_refs(retell, annotation, {f["factId"] for f in facts}, notes)
    counts = dict.fromkeys(STATUSES, 0)
    rows = []
    for fact in facts:
        evidence = keyword_evidence(fact, text)
        if refs is not None:
            ref = refs.get(fact["factId"])
            status = (ref["status"] or "retold") if ref and (ref["status"] or ref["retellRefs"]) else "missing"
            row = {"status": status, "basis": "factRefs", "retellRefs": ref["retellRefs"] if ref else []}
        else:
            status = evidence["status"] or "missing"
            row = {"status": status, "basis": "keywords", "signalQuality": "low"}
            if evidence["status"] is None:
                row["note"] = "fact 没有 keywords，也没有 factRefs，核不了"
        counts[status] += 1
        rows.append({"infoId": fact["infoId"], "factId": fact["factId"], "text": fact["text"], **row,
                     "keywordEvidence": evidence})
    if refs is None:
        notes.append("复述没有 factRefs，也没给 --factrefs：状态按关键词子串判，信号质量低（同义改写会判 partial／missing）")
    return {"ok": True, "passed": None, "target": retell.get("target"), "promptVersion": retell.get("promptVersion"),
            "basis": "factRefs" if refs is not None else "keywords", "facts": rows, "counts": counts,
            "closingEvent": check_closing_event(episode_plan, retell), "notes": notes}


def _main(argv):
    parser = argparse.ArgumentParser(description="冷读复述对 infoLedger facts 与 closingEvent 的覆盖；供人看，不拦")
    parser.add_argument("retell")
    parser.add_argument("--plan", required=True, help="分集计划或对话表")
    parser.add_argument("--episode-plan", help="--plan 是对话表时必给")
    parser.add_argument("--factrefs", help="标注者另给的 factRefs 文件（facts[].factId/status/retellRefs）")
    args = parser.parse_args(argv)
    result = run_retell_check(args.retell, args.plan, args.episode_plan, args.factrefs)
    command = [abspath(args.retell), "--plan", abspath(args.plan)]
    for flag, value in (("--episode-plan", args.episode_plan), ("--factrefs", args.factrefs)):
        if value:
            command += [flag, abspath(value)]
    result["reproduceCommand"] = reproduce_command("retell_check", command)
    return result, 0


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
