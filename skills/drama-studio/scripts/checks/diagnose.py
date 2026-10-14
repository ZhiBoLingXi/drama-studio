"""dialogue-diagnose：正文的诊断信号（台词方案 §3.3、§5.2；实施计划 §2.2 #7）。

只提示去看哪儿：输出信号＋位置＋（能对上对话表时）所在话题与处境；不出结论、不拦截，不与任何区间比。
每条信号标 `signalQuality`：`structural`（按行、说话人、对话表结构直接数出来的）或 `low`（关键词、标点或
触发线估出来的，修正点 #89）。缺输入的信号整条记 notEvaluable，不按文本猜。

信号：QUESTION_UNANSWERED、IMPERATIVE_CHAIN、ONE_BREATH（只用正文）；INFO_IN_ACTION_ONLY（要分集计划）；
INFO_REPEATED（要分集计划与对话表）；MONOLOGUE_FALLBACK（要对话表与分集计划）；ADDRESSEE_JUMP、
ONE_ITEM_PER_LINE_MISMATCH（要对话表与对照表）；OBJECT_MISSING（要冷读复述，本命令不读，永远 notEvaluable）；
UNCHANGED_ACROSS_REVISIONS（要 `--compare-with`，按场号字面相等比，对不上的场跳过并列出）。

退出码：0；1 输入错误。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.text_lines import abspath, han_only, load_json, load_text, parse_lines, reproduce_command, run_cli, strip_parens

QUESTION_RE = re.compile(r"[？?]")
SENTENCE_SPLIT_RE = re.compile(r"[。！!？?]")
MULTI_ACTION_CONNECTORS = ("再", "又", "然后", "并", "接着")
# 下面几个数只是识别信号的触发线（方案只给了定性描述），不是质量门槛。
MIN_SENTENCE_HAN_CHARS = 3
IMPERATIVE_MAX_CHARS = 12
IMPERATIVE_MIN_RUN = 3
ONE_BREATH_MIN_RUN = 2


def group_by_scene(parsed):
    order, scenes = [], {}
    for row in parsed:
        if row["sceneId"] is None:
            continue
        if row["sceneId"] not in scenes:
            order.append(row["sceneId"])
        scenes.setdefault(row["sceneId"], []).append(row)
    return order, scenes


def speaker_runs(rows):
    runs = []
    for row in rows:
        if runs and runs[-1][-1]["speaker"] == row["speaker"]:
            runs[-1].append(row)
        else:
            runs.append([row])
    return runs


def scene_dialogue(scenes, sid):
    return [r for r in scenes[sid] if r["kind"] == "dialogue"]


def signal(code, quality, **fields):
    return {"code": code, "signalQuality": quality, **fields}


def question_unanswered(order, scenes):
    out = []
    for sid in order:
        rows = scene_dialogue(scenes, sid)
        for i, row in enumerate(rows):
            if not QUESTION_RE.search(strip_parens(row["content"])):
                continue
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            if nxt is None or nxt["speaker"] == row["speaker"]:
                out.append(signal("QUESTION_UNANSWERED", "structural", scene=sid, line=row["line"], speaker=row["speaker"],
                                  lineText=row["raw"], detail="之后没有对白了" if nxt is None else f"下一条对白（第 {nxt['line']} 行）还是同一个人说的"))
    return out


def imperative_chain(order, scenes):
    out = []
    for sid in order:
        for run in speaker_runs(scene_dialogue(scenes, sid)):
            short = [r for r in run if len(han_only(strip_parens(r["content"]))) <= IMPERATIVE_MAX_CHARS
                     and not QUESTION_RE.search(r["content"] or "")]
            if len(run) >= IMPERATIVE_MIN_RUN and len(short) == len(run):
                out.append(signal("IMPERATIVE_CHAIN", "low", scene=sid, line=run[0]["line"], speaker=run[0]["speaker"],
                                  lines=[r["line"] for r in run],
                                  detail=f"连续 {len(run)} 条短句（各 ≤{IMPERATIVE_MAX_CHARS} 字、非问句），中间没人接；触发线不是门槛"))
    return out


def one_breath(order, scenes):
    return [signal("ONE_BREATH", "structural", scene=sid, line=run[0]["line"], speaker=run[0]["speaker"],
                   lines=[r["line"] for r in run], detail=f"连说 {len(run)} 条，中间没人接（只看说话人，不看信息条数）")
            for sid in order for run in speaker_runs(scene_dialogue(scenes, sid)) if len(run) >= ONE_BREATH_MIN_RUN]


def collect_facts(episode_plan):
    return {f["factId"]: {"infoId": info.get("infoId"), "keywords": f.get("keywords") or []}
            for info in episode_plan.get("infoLedger") or [] for f in info.get("facts") or [] if f.get("factId")}


def info_in_action_only(parsed, facts):
    actions = [r for r in parsed if r["kind"] == "action"]
    spoken = "".join(r["content"] or "" for r in parsed if r["kind"] == "dialogue")
    out = []
    for fid, fact in facts.items():
        keywords = [kw for kw in fact["keywords"] if kw]
        hits = [r["line"] for r in actions if any(kw in (r["content"] or "") for kw in keywords)]
        if keywords and hits and not any(kw in spoken for kw in keywords):
            out.append(signal("INFO_IN_ACTION_ONLY", "low", factId=fid, infoId=fact["infoId"], lines=hits, keywords=keywords,
                              detail="关键词只在 △ 行出现，没在任何对白行出现（关键词口径，同义改写会漏）"))
    return out


def info_repeated(dplan):
    seen, ordinal = {}, 0
    for scene in dplan.get("scenes") or []:
        for topic in scene.get("topics") or []:
            ordinal += 1
            for fid in sorted({fid for ex in topic.get("exchanges") or [] for fid in ex.get("carries") or []}):
                seen.setdefault(fid, []).append((scene.get("sceneId"), topic.get("topicId"), ordinal, topic.get("situation")))
    return [signal("INFO_REPEATED", "structural", factId=fid, scene=sid, topic=tid, occurrence=n, totalOccurrences=len(found),
                   topicOrdinalInEpisode=ordinal, situation=situation,
                   detail=f"第 {ordinal} 个话题（{sid}/{tid}）第 {n}/{len(found)} 次出口；重说要有处境理由")
            for fid, found in seen.items() if len(found) >= 2
            for n, (sid, tid, ordinal, situation) in enumerate(found, start=1)]


def monologue_fallback(parsed, facts, dplan):
    permitted = {fid for scene in dplan.get("scenes") or []
                 for holder in [scene, *(scene.get("topics") or [])]
                 for m in holder.get("monologues") or [] for fid in m.get("carries") or []}
    os_rows = [r for r in parsed if r["kind"] == "dialogue" and "OS" in (r["state"] or "")]
    out = []
    for fid, fact in facts.items():
        hits = [r["line"] for r in os_rows if any(kw and kw in (r["content"] or "") for kw in fact["keywords"])]
        if hits and fid not in permitted:
            out.append(signal("MONOLOGUE_FALLBACK", "low", factId=fid, lines=hits,
                              detail="关键词出现在 OS 行，对话表 monologues[] 没有这个 fact 的独白许可"))
    return out


def line_exchange_index(dplan, ptmap, parsed):
    exchanges = {}
    for scene in dplan.get("scenes") or []:
        for topic in scene.get("topics") or []:
            for ex in topic.get("exchanges") or []:
                if ex.get("exchangeId"):
                    exchanges[ex["exchangeId"]] = {**ex, "sceneId": scene.get("sceneId"), "topicId": topic.get("topicId"),
                                                   "situation": topic.get("situation")}
    rows = {r["line"]: r for r in parsed}
    index = {}
    for exid, numbers in (ptmap.get("exchangeToLines") or {}).items():
        if exid in exchanges:
            for number in numbers:
                index[number] = {**exchanges[exid], "lineContent": (rows.get(number) or {}).get("content")}
    return index


def addressee_jump(order, scenes, index):
    out = []
    for sid in order:
        rows = [r for r in scene_dialogue(scenes, sid) if r["line"] in index]
        last = {}
        for row in rows:
            ex = index[row["line"]]
            prev = last.get(row["speaker"])
            to = ex.get("addressee")
            if prev and to and prev["addressee"] and to != prev["addressee"]:
                answered = any(r["speaker"] == prev["addressee"] for r in rows if prev["line"] < r["line"] < row["line"])
                if not answered:
                    out.append(signal("ADDRESSEE_JUMP", "structural", scene=sid, line=row["line"], speaker=row["speaker"],
                                      topic=ex["topicId"], situation=ex["situation"], **{"from": prev["addressee"], "to": to},
                                      detail=f"对象从 {prev['addressee']!r} 换成 {to!r}（第 {prev['line']}→{row['line']} 行），中间原对象没应答"))
            last[row["speaker"]] = {"line": row["line"], "addressee": to}
    return out


def one_item_per_line_mismatch(index):
    out = []
    for number, ex in sorted(index.items()):
        content = ex.get("lineContent")
        if not ex.get("oneItemPerLine") or content is None:
            continue
        sentences = [s for s in SENTENCE_SPLIT_RE.split(strip_parens(content)) if len(han_only(s)) >= MIN_SENTENCE_HAN_CHARS]
        connectors = sum(1 for word in MULTI_ACTION_CONNECTORS if word in content)
        if len(sentences) >= 2 or connectors:
            out.append(signal("ONE_ITEM_PER_LINE_MISMATCH", "low", line=number, exchangeId=ex.get("exchangeId"),
                              topic=ex["topicId"], situation=ex["situation"], lineText=content,
                              sentenceCount=len(sentences), connectorHits=connectors,
                              detail="标了 oneItemPerLine，这行按句末标点估有多句或命中连接词——没有词性标注，不是真数动词"))
    return out


def speaker_change_stats(parsed):
    order, scenes = group_by_scene(parsed)
    return {sid: sum(1 for a, b in zip(rows, rows[1:]) if a["speaker"] != b["speaker"])
            for sid in order for rows in [scene_dialogue(scenes, sid)]}


def unchanged_across_revisions(name, parsed, others):
    out, skipped = [], []
    stats = speaker_change_stats(parsed)
    for other_name, other_parsed in others:
        other = speaker_change_stats(other_parsed)
        skipped.append({"pair": [name, other_name], "aOnlyScenes": sorted(set(stats) - set(other)),
                        "bOnlyScenes": sorted(set(other) - set(stats))})
        out += [signal("UNCHANGED_ACROSS_REVISIONS", "structural", scene=sid, pair=[name, other_name], speakerChanges=stats[sid],
                       detail=f"两版场 {sid} 换人次数都是 {stats[sid]}（改稿可能没碰对话结构）")
                for sid in sorted(set(stats) & set(other)) if stats[sid] == other[sid]]
    return out, skipped


def not_evaluable(code, why):
    return {"code": code, "status": "not_evaluable", "why": why}


def run_diagnose(text_path, plan_text_map=None, dialogue_plan=None, episode_plan=None, compare_with=None) -> dict:
    parsed = parse_lines(load_text(text_path))
    ptmap = load_json(plan_text_map, "对照表") if plan_text_map else None
    dplan = load_json(dialogue_plan, "对话表") if dialogue_plan else None
    eplan = load_json(episode_plan, "分集计划") if episode_plan else None
    order, scenes = group_by_scene(parsed)
    signals = question_unanswered(order, scenes) + imperative_chain(order, scenes) + one_breath(order, scenes)
    missing = [not_evaluable("OBJECT_MISSING", "要冷读复述对每句宾语是否写「不明」；本命令不读复述，不按文本猜")]
    facts = collect_facts(eplan) if eplan is not None else None
    if facts is not None:
        signals += info_in_action_only(parsed, facts)
    else:
        missing.append(not_evaluable("INFO_IN_ACTION_ONLY", "没给 --episode-plan"))
    if dplan is not None:
        signals += info_repeated(dplan)
    else:
        missing.append(not_evaluable("INFO_REPEATED", "没给 --dialogue-plan"))
    if dplan is not None and facts is not None:
        signals += monologue_fallback(parsed, facts, dplan)
    else:
        missing.append(not_evaluable("MONOLOGUE_FALLBACK", "没给 --dialogue-plan 与 --episode-plan"))
    if dplan is not None and ptmap is not None:
        index = line_exchange_index(dplan, ptmap, parsed)
        signals += addressee_jump(order, scenes, index) + one_item_per_line_mismatch(index)
    else:
        missing += [not_evaluable(code, "没给 --dialogue-plan 与 --plan-text-map")
                    for code in ("ADDRESSEE_JUMP", "ONE_ITEM_PER_LINE_MISMATCH")]
    out = {"ok": True, "passed": None, "textFile": str(text_path)}
    if compare_with:
        found, skipped = unchanged_across_revisions(str(text_path), parsed,
                                                    [(str(p), parse_lines(load_text(p))) for p in compare_with])
        signals += found
        out["unchangedAcrossRevisionsSkippedScenes"] = skipped
    else:
        missing.append(not_evaluable("UNCHANGED_ACROSS_REVISIONS", "没给 --compare-with"))
    counts = {}
    for item in signals:
        counts[item["code"]] = counts.get(item["code"], 0) + 1
    out.update(signalCounts=counts, signals=signals, notEvaluable=missing,
               note="诊断信号只提示去看哪儿，不出结论、不拦截、不与任何区间比")
    return out


def _main(argv):
    parser = argparse.ArgumentParser(description="正文诊断信号：信号＋位置＋处境；不判区间、不拦截")
    parser.add_argument("text")
    parser.add_argument("--plan-text-map")
    parser.add_argument("--dialogue-plan")
    parser.add_argument("--episode-plan")
    parser.add_argument("--compare-with", nargs="+", help="另几版正文：按场号比换人次数")
    args = parser.parse_args(argv)
    result = run_diagnose(args.text, args.plan_text_map, args.dialogue_plan, args.episode_plan, args.compare_with)
    command = [abspath(args.text)]
    for flag, value in (("--plan-text-map", args.plan_text_map), ("--dialogue-plan", args.dialogue_plan),
                        ("--episode-plan", args.episode_plan)):
        if value:
            command += [flag, abspath(value)]
    if args.compare_with:
        command += ["--compare-with", *[abspath(p) for p in args.compare_with]]
    result["reproduceCommand"] = reproduce_command("diagnose", command)
    return result, 0


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
