"""plan-text-consistency：对照表（plan-text-map）落到正文行之后，与对话表脚本能核的那半是否一致。

只核 S 项（台词方案 §8.4），不判「走法像不像」：
1. speaker-sequence（fail）：对话表每个交换的 `speaker` 与对照表 `exchangeToLines` 指到的正文行说话人一致。
2. topic-boundary（fail）：每段在对照表里有且只有一行 `closerOf`；同一话题内段的 closerOf 行号按 segments 顺序递增。
3. interrupted-by（报）：被打断的交换写 `interruptedAt`（D6-3），话题的 `interruptedBy.by` 写谁打断：该交换之后正文下一条对白
   是打断者的（没写打断者时，只要不是被打断的人接着说）；被打断的人不必说完。旧写法 `interruptedBy.at`／`atExchange`
   里取得出交换 id 时同样核，取不出的记 notEvaluable。
4. carries-keywords（报，signalQuality: low）：带 `carries` 的对白行里，分集计划 fact 的 keywords 缺了哪些——
   keywords 是书面概括、对白是口语，缺的只是「同义改写候选」（修正点 #89）。
另列 `verbatimFrom` 行（逐字采用的人工句，不算「问题不在了」的证据）。

退出码：0 硬规则都过；1 输入错误；2 有硬规则 fail。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.text_lines import InputError, abspath, load_json, load_text, parse_lines, reproduce_command, run_cli

EXCHANGE_ID_RE = re.compile(r"X-[A-Za-z0-9]+-\d+")


def iter_topics(dplan):
    for scene in dplan.get("scenes") or []:
        for topic in scene.get("topics") or []:
            yield scene.get("sceneId"), topic


def resolve_text(ptmap: dict, map_path, text_path=None) -> Path:
    if text_path:
        return Path(text_path)
    declared = ptmap.get("text")
    if not declared:
        raise InputError("对照表缺 text 字段，用 --text 指定正文")
    base = Path(map_path).resolve().parent
    for candidate in (Path(declared), base / declared, base.parent / declared, base / Path(declared).name):
        if candidate.is_file():
            return candidate
    raise InputError(f"对照表的 text={declared!r} 找不到对应文件，用 --text 指定")


def check_speaker_sequence(dplan, ptmap, rows):
    items = []
    lines = ptmap.get("exchangeToLines") or {}
    for sid, topic in iter_topics(dplan):
        for ex in topic.get("exchanges") or []:
            exid, speaker = ex.get("exchangeId"), ex.get("speaker")
            if not exid or not speaker:
                continue
            where = f"{sid}/{topic.get('topicId')}/{exid}"
            if not lines.get(exid):
                items.append(f"{where}: 对照表 exchangeToLines 里没有这个交换")
                continue
            for number in lines[exid]:
                row = rows.get(number)
                if row is None:
                    items.append(f"{where}: 对照表指向的第 {number} 行在正文里不存在")
                elif row["kind"] != "dialogue":
                    items.append(f"{where}: 正文第 {number} 行不是对白行（{row['kind']}）：{row['raw']!r}")
                elif row["speaker"] != speaker:
                    items.append(f"{where}: 对话表说话人 {speaker!r}，正文第 {number} 行是 {row['speaker']!r}：{row['raw']!r}")
    return {"status": "fail" if items else "pass", "items": items}


def check_topic_boundary(dplan, ptmap):
    items = []
    closers = {}
    for entry in ptmap.get("lineToPlan") or []:
        if entry.get("closerOf"):
            closers.setdefault(entry["closerOf"], []).append(entry.get("line"))
    for sid, topic in iter_topics(dplan):
        where = f"{sid}/{topic.get('topicId')}"
        previous = None
        for segment in topic.get("segments") or []:
            seg_id = segment.get("segmentId")
            found = closers.get(seg_id) if seg_id else None
            if seg_id and not found:
                items.append(f"{where}: 段 {seg_id!r} 在对照表里没有任何一行标 closerOf")
            elif seg_id and len(found) > 1:
                items.append(f"{where}: 段 {seg_id!r} 被 {len(found)} 行标了 closerOf：{found}")
            if not found:
                previous = None
                continue
            line = min(found)
            if previous and line <= previous[1]:
                items.append(f"{where}: 段 {seg_id!r} 的 closerOf（第 {line} 行）没有晚于上一段 {previous[0]!r}（第 {previous[1]} 行）")
            previous = (seg_id, line)
    return {"status": "fail" if items else "pass", "items": items}


def check_interrupted_by(dplan, ptmap, parsed):
    """Where a topic is interrupted. D6-3: the interrupted exchange carries interruptedAt (its own exchangeId, or the
    exchange the cut lands on); the topic's interruptedBy names who cuts in (`by`, older `who`). The first dialogue line
    after that exchange's lines is the interrupter's when one is named, else anyone but the interrupted speaker; the
    interrupted speaker is not expected to finish. Older plans with only interruptedBy.at (or atExchange) are read the
    same way."""
    items, not_evaluable = [], []
    lines = ptmap.get("exchangeToLines") or {}
    dialogue = [r for r in parsed if r["kind"] == "dialogue"]
    for sid, topic in iter_topics(dplan):
        interrupt = topic.get("interruptedBy") if isinstance(topic.get("interruptedBy"), dict) else {}
        who = interrupt.get("by") or interrupt.get("who")
        exchanges = [ex for ex in topic.get("exchanges") or [] if isinstance(ex, dict)]
        marked = [ex for ex in exchanges if ex.get("interruptedAt")]
        points = []
        for ex in marked:
            match = EXCHANGE_ID_RE.search(str(ex["interruptedAt"]))
            points.append((f"{sid}/{topic.get('topicId')}/{ex.get('exchangeId')}", match.group(0) if match else ex.get("exchangeId")))
        if not marked and interrupt:
            match = EXCHANGE_ID_RE.search(str(interrupt.get("at") or interrupt.get("atExchange") or ""))
            if not match:
                not_evaluable.append({"topic": f"{sid}/{topic.get('topicId')}", "interruptedBy": interrupt,
                                      "why": "没有交换写 interruptedAt，interruptedBy 里也取不出交换 id，不按文本猜"})
                continue
            points.append((f"{sid}/{topic.get('topicId')}", match.group(0)))
        speakers = {ex.get("exchangeId"): ex.get("speaker") for ex in exchanges}
        for where, target in points:
            if not lines.get(target):
                not_evaluable.append({"at": where, "interrupted": target, "why": f"{target} 在对照表里没有行号"})
                continue
            anchor = max(lines[target])
            after = [r for r in dialogue if r["line"] > anchor]
            if not after:
                items.append(f"{where}: {target} 被打断（第 {anchor} 行），之后正文没有对白了")
            elif who and after[0]["speaker"] != who:
                items.append(f"{where}: {target} 被 {who!r} 打断，第 {anchor} 行之后第一条对白（第 {after[0]['line']} 行）"
                             f"是 {after[0]['speaker']!r}")
            elif not who and after[0]["speaker"] == speakers.get(target):
                items.append(f"{where}: {target} 被打断，但第 {anchor} 行之后接着说的还是 {after[0]['speaker']!r}")
    return {"status": "report", "items": items, "notEvaluable": not_evaluable}


def check_carries_keywords(ptmap, rows, facts):
    items = []
    deviations = " ".join(f"{d.get('where', '')} {d.get('what', '')} {d.get('why', '')}" for d in ptmap.get("deviations") or [])
    for entry in ptmap.get("lineToPlan") or []:
        if entry.get("kind") != "dialogue" or not entry.get("carries"):
            continue
        row = rows.get(entry.get("line"))
        content = (row or {}).get("content") or entry.get("text") or ""
        for fid in entry["carries"]:
            missing = [kw for kw in (facts.get(fid) or {}).get("keywords") or [] if kw and kw not in content]
            if missing:
                items.append({"line": entry.get("line"), "factId": fid, "missingKeywords": missing,
                              "lineText": row["raw"] if row else entry.get("text"), "verbatimFrom": entry.get("verbatimFrom"),
                              "notedInDeviations": fid in deviations or any(kw in deviations for kw in missing),
                              "label": "同义改写候选（不判违规）"})
    return {"status": "report", "signalQuality": "low", "items": items}


def run_plan_text_consistency(map_path, dialogue_plan_path, episode_plan_path, text_path=None) -> dict:
    ptmap = load_json(map_path, "对照表")
    dplan = load_json(dialogue_plan_path, "对话表")
    episode_plan = load_json(episode_plan_path, "分集计划")
    text_file = resolve_text(ptmap, map_path, text_path)
    parsed = parse_lines(load_text(text_file))
    rows = {r["line"]: r for r in parsed}
    facts = {f.get("factId"): f for info in episode_plan.get("infoLedger") or [] for f in info.get("facts") or []}
    rules = {
        "speaker-sequence": check_speaker_sequence(dplan, ptmap, rows),
        "topic-boundary": check_topic_boundary(dplan, ptmap),
        "interrupted-by": check_interrupted_by(dplan, ptmap, parsed),
        "carries-keywords": check_carries_keywords(ptmap, rows, facts),
    }
    return {"ok": True, "passed": not any(r["status"] == "fail" for r in rules.values()), "textFile": str(text_file),
            "rules": rules, "verbatimFrom": ptmap.get("verbatimFrom") or []}


def _main(argv):
    parser = argparse.ArgumentParser(description="核对照表与对话表的 S 项一致性（说话人序列、段边界、打断位置、关键词同义候选）")
    parser.add_argument("plan_text_map")
    parser.add_argument("--dialogue-plan", required=True)
    parser.add_argument("--episode-plan", required=True, help="carries 的 keywords 在分集计划里")
    parser.add_argument("--text", help="正文；不给时按对照表的 text 字段找")
    args = parser.parse_args(argv)
    result = run_plan_text_consistency(args.plan_text_map, args.dialogue_plan, args.episode_plan, args.text)
    command = [abspath(args.plan_text_map), "--dialogue-plan", abspath(args.dialogue_plan),
               "--episode-plan", abspath(args.episode_plan), "--text", abspath(result["textFile"])]
    result["reproduceCommand"] = reproduce_command("plan_text_consistency", command)
    return result, (0 if result["passed"] else 2)


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
