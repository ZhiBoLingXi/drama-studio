"""dialogue-plan 的 S 项核对（台词方案 §6.1；实施计划 §2.1 #11、§2.4）。

规则（fail 的条目都带位置与原样片段，便于分辨误判）：
1. info-ledger：对话表 infoLedger 的 factId 都在分集计划里、分集计划每个 fact 都被引用；
   每条 `carriedBy` 有 `exchangeIds[]`（每个 id 都在对话表里）或 `pictureReason`。
2. topics-segments：话题有 `situation`；每段 `between` 是说话的两个人（不是区间），两人不同，
   有 `closer`；`exchanges[].segmentId` 在本话题段里；各段的交换按 segments 顺序排开、不交错。
   `between` 里的人不在本场 participants 只记 notes（电话那头等画外对象）。
3. speaker-knows：说话人承载的 fact 按底账 id（`fact.ledgerRef` ＋ `knownByInStoryRefs` 里该人的
   id）核，满足任一条就算知道：(a) knows 文件场前已知；(b) 场内按拍（交换 `beatRef`，没有就退回
   `fact.carrierBeat`）在这一拍或之前已知；(c) 本场更早的交换告诉过他；(d) 分集计划 ledgerDelta
   里同 id、归他、落在本场、`how` 含「自己做的／在场」的自写入（拍号可比时不晚于交换）。没有可用 id 的
   记 notEvaluable，不按文本猜。
   listener-knows 只报：`situation.listenerKnows.initial.knows` 里的 id 应是 knows 文件该人场前已知的，
   `narrowedOut` 只能去掉 initial 里有的；listenerKnows 是一句话时退回文本粗核并标 textHeuristicFallback。
4. addressee：没有对象的交换与独白有 `whyNoAddressee`。
5. exemplars：`source ∈ corpus / human / project`；corpus 的 `maskedLines` 合计不超过 2 句；话题没有正例
   须标 `no_exemplar`。
6. no-quota-fields：不得有 `estimates`，也不得有「名字像数量配额、值是数字」的字段。
7. change-proposals：每条有 `targetLayer` 与非空 `default`。

退出码：0 全部通过；1 输入错误；2 有 fail 规则。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.text_lines import abspath, is_nonempty, load_json, reproduce_command, run_cli

EXEMPLAR_SOURCES = {"corpus", "human", "project"}
FORBIDDEN_KEYS = {"estimates", "voicedLines", "speechChars"}
QUOTA_KEY_RE = re.compile(r"(?:[Cc]ount|数)$")
BEAT_REF_RE = re.compile(r"([0-9A-Za-z]+(?:-[0-9A-Za-z]+)?)\.b(\d+)")
LEDGER_ID_RE = re.compile(r"L-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
SENTENCE_END_RE = re.compile(r"[。！？!?]")
SELF_ACTOR_HOW = ("自己做的", "在场")
NEGATION_RE = re.compile(r"不|没|未")


def parse_beat_ref(text):
    """返回 (sceneId, 拍号)；`ep6A 6A-1.b3`、`ep006A 6A-1.b3`、`6A-1.b3` 都认，解析不出返回 (None, None)。"""
    match = BEAT_REF_RE.search(str(text or ""))
    return (match.group(1), int(match.group(2))) if match else (None, None)


def as_list(value) -> list:
    return value if isinstance(value, list) else [] if value is None else [value]


def iter_topics(dplan):
    for scene in dplan.get("scenes") or []:
        for topic in scene.get("topics") or []:
            yield scene, topic


def check_info_ledger(dplan, episode_facts):
    items = []
    exchange_ids = {ex.get("exchangeId") for _, topic in iter_topics(dplan) for ex in topic.get("exchanges") or []}
    referenced = set()
    for i, entry in enumerate(dplan.get("infoLedger") or []):
        fid = entry.get("factId")
        where = f"infoLedger[{i}](factId={fid!r})"
        if not is_nonempty(fid):
            items.append(f"infoLedger[{i}]: 缺 factId")
            continue
        if fid not in episode_facts:
            items.append(f"{where}: 分集计划 infoLedger 里没有这个 factId")
        else:
            referenced.add(fid)
            if is_nonempty(entry.get("infoId")) and entry["infoId"] != episode_facts[fid]["infoId"]:
                items.append(f"{where}: infoId={entry['infoId']!r}，分集计划里它属于 {episode_facts[fid]['infoId']!r}")
        carried = entry.get("carriedBy") if isinstance(entry.get("carriedBy"), dict) else {}
        ids = carried.get("exchangeIds")
        if ids is not None and not isinstance(ids, list):
            items.append(f"{where}: carriedBy.exchangeIds 应是数组，实际 {ids!r}")
            ids = None
        if not ids and not is_nonempty(carried.get("pictureReason")):
            items.append(f"{where}: carriedBy 既没有 exchangeIds 也没有 pictureReason")
        dangling = [x for x in ids or [] if x not in exchange_ids]
        if dangling:
            items.append(f"{where}: carriedBy.exchangeIds 里 {dangling} 在对话表里找不到")
    missing = sorted(set(episode_facts) - referenced)
    if missing:
        items.append(f"分集计划的 fact 没有被对话表 infoLedger 引用：{missing}")
    return {"status": "fail" if items else "pass", "items": items}


def check_topics_segments(dplan):
    items, notes = [], []
    for scene, topic in iter_topics(dplan):
        where = f"{scene.get('sceneId')}/{topic.get('topicId')}"
        participants = set(scene.get("participants") or [])
        if not is_nonempty(topic.get("situation")):
            items.append(f"{where}: situation 为空")
        segments = topic.get("segments")
        if not is_nonempty(segments):
            items.append(f"{where}: segments 为空")
            continue
        segment_ids = set()
        for i, segment in enumerate(segments):
            swhere = f"{where}/segments[{i}]"
            segment_ids.add(segment.get("segmentId"))
            between = segment.get("between")
            if not (isinstance(between, list) and len(between) == 2):
                items.append(f"{swhere}: between 应是说话的两个人，实际 {between!r}")
            else:
                if between[0] == between[1]:
                    items.append(f"{swhere}: between 两人相同（{between[0]!r}），没有对象")
                notes.extend(f"{swhere}: between 里的 {p!r} 不在本场 participants {sorted(participants)}（可能是电话等画外对象）"
                             for p in between if participants and p not in participants)
            if not is_nonempty(segment.get("closer")):
                items.append(f"{swhere}: closer 为空")
        first, last = {}, {}
        for j, ex in enumerate(topic.get("exchanges") or []):
            sid = ex.get("segmentId")
            if sid and sid not in segment_ids:
                items.append(f"{where}/exchanges[{j}]({ex.get('exchangeId')}): segmentId={sid!r} 在本话题 segments 里找不到")
            if sid:
                first.setdefault(sid, j)
                last[sid] = j
        prev = None
        for segment in segments:
            sid = segment.get("segmentId")
            if sid not in first:
                continue
            if prev is not None and first[sid] <= last[prev]:
                items.append(f"{where}: 段 {sid!r} 的第一个交换（exchanges[{first[sid]}]）排在上一段 {prev!r} 的最后一个交换"
                             f"（exchanges[{last[prev]}]）之前，交换顺序与 segments 顺序不一致")
            prev = sid
    return {"status": "fail" if items else "pass", "items": items, "notes": notes}


def build_knows_index(knows_doc):
    """(场, 人) → 场前已知的 id 与文本；场 → {拍号: [{entryId, who}]}。"""
    index, within = {}, {}
    for scene in knows_doc.get("scenes") or []:
        sid = scene.get("sceneId")
        for person, kn in (scene.get("byPerson") or {}).items():
            index[(sid, person)] = {"knownIds": {k.get("entryId") for k in kn.get("knows") or [] if k.get("entryId")},
                                    "notKnows": [t for t in kn.get("notKnows") or [] if isinstance(t, str)]}
        within[sid] = {}
        for item in scene.get("withinScene") or []:
            _, beat = parse_beat_ref(item.get("beatId"))
            if beat is not None:
                within[sid].setdefault(beat, []).extend(item.get("newlyKnown") or [])
    return index, within


def fact_ledger_ids(fact, info, person):
    ids = set(as_list(fact.get("ledgerRef")))
    for item in info.get("knownByInStoryRefs") or []:
        if isinstance(item, dict) and item.get("who") == person:
            ids.update(as_list(item.get("ledgerRef")))
    return {i for i in ids if i}


def build_self_writes(episode_plan):
    """(场, 人) → {条目 id: 拍号}：分集计划里 how 含「自己做的／在场」的知识写入。"""
    index = {}
    for write in (episode_plan.get("ledgerDelta") or {}).get("writes") or []:
        change = write.get("change") or {}
        entry_id = change.get("id") if write.get("entryId") == "new" else write.get("entryId")
        scene, beat = parse_beat_ref(change.get("since") if isinstance(change.get("since"), str) else None)
        if scene is None:
            scene, beat = parse_beat_ref(write.get("supportedBy"))
        if entry_id and change.get("who") and scene and any(m in str(change.get("how") or "") for m in SELF_ACTOR_HOW):
            index.setdefault((scene, change["who"]), {})[entry_id] = beat
    return index


def check_speaker_knows(dplan, episode_plan, knows_index, within_index):
    facts = {f.get("factId"): (info, f) for info in episode_plan.get("infoLedger") or []
             for f in info.get("facts") or [] if f.get("factId")}
    self_writes = build_self_writes(episode_plan)
    items, not_evaluable, self_exempt, within_exempt = [], [], [], []
    for scene in dplan.get("scenes") or []:
        sid = scene.get("sceneId")
        told = {}
        for topic in scene.get("topics") or []:
            for i, ex in enumerate(topic.get("exchanges") or []):
                speaker, addressee = ex.get("speaker"), ex.get("addressee")
                where = f"{sid}/{topic.get('topicId')}/exchanges[{i}]({ex.get('exchangeId')})"
                for fid in ex.get("carries") or []:
                    if fid not in facts:
                        items.append(f"{where}: carries 的 factId {fid!r} 不在分集计划里")
                        continue
                    info, fact = facts[fid]
                    ids = fact_ledger_ids(fact, info, speaker)
                    if not ids:
                        not_evaluable.append({"exchange": where, "speaker": speaker, "factId": fid,
                                              "why": "fact 没有 ledgerRef，knownByInStoryRefs 里也没有这个人的 id；不按文本猜"})
                    else:
                        prior = bool(ids & knows_index.get((sid, speaker), {}).get("knownIds", set()))
                        earlier = fid in told.get(speaker, set())
                        ex_scene, ex_beat = parse_beat_ref(ex.get("beatRef") or fact.get("carrierBeat"))
                        in_scene = ex_scene == sid and ex_beat is not None
                        within = in_scene and any(
                            n.get("entryId") in ids and n.get("who") == speaker
                            for beat, newly in within_index.get(sid, {}).items() if beat <= ex_beat for n in newly)
                        actor = False
                        if not (prior or earlier or within):
                            own = self_writes.get((sid, speaker), {})
                            matched = ids & set(own)
                            actor = bool(matched) and (not in_scene or any(own[m] is None or own[m] <= ex_beat for m in matched))
                            if actor:
                                self_exempt.append({"exchange": where, "speaker": speaker, "factId": fid,
                                                    "matchedIds": sorted(matched), "basis": "same_scene_actor"})
                        elif within and not (prior or earlier):
                            within_exempt.append({"exchange": where, "speaker": speaker, "factId": fid,
                                                  "basis": "within_scene_beat"})
                        if not (prior or earlier or within or actor):
                            items.append(f"{where}: {speaker!r} 说出 {fid}（底账 id {sorted(ids)}），场前不知道、场内按拍查不到、"
                                         f"本场更早没人告诉他、也不是他本场自己做的——speaker-not-knows；sketch：{ex.get('sketch')!r}")
                    if addressee:
                        told.setdefault(addressee, set()).add(fid)
                    told.setdefault(speaker, set()).add(fid)
    return {"status": "fail" if items else "pass", "items": items, "notEvaluable": not_evaluable,
            "selfActorExemptions": self_exempt, "withinSceneExemptions": within_exempt}


def check_listener_knows(dplan, knows_index):
    items, fallback = [], False
    for scene, topic in iter_topics(dplan):
        sid = scene.get("sceneId")
        where = f"{sid}/{topic.get('topicId')}"
        situation = topic.get("situation") if isinstance(topic.get("situation"), dict) else {}
        listener_knows = situation.get("listenerKnows")
        if isinstance(listener_knows, dict):
            listener = situation.get("listener")
            entry = knows_index.get((sid, listener))
            initial = listener_knows.get("initial") if isinstance(listener_knows.get("initial"), dict) else {}
            claimed = {m for text in initial.get("knows") or [] for m in LEDGER_ID_RE.findall(str(text))}
            if entry is not None:
                extra = sorted(claimed - entry["knownIds"])
                if extra:
                    items.append(f"{where}: listenerKnows.initial 里 {listener!r} 知道 {extra}，knows 文件该场场前没有（只能收窄，不能相反）")
            for out in listener_knows.get("narrowedOut") or []:
                ids = LEDGER_ID_RE.findall(str((out or {}).get("entryId")))
                if ids and ids[0] not in claimed:
                    items.append(f"{where}: narrowedOut 去掉的 {ids[0]} 不在 initial.knows 里")
        elif isinstance(listener_knows, str) and listener_knows:
            for person in scene.get("participants") or []:
                for fact_text in (knows_index.get((sid, person)) or {}).get("notKnows", []):
                    pos = listener_knows.find(fact_text) if fact_text else -1
                    if pos >= 0 and not NEGATION_RE.search(listener_knows[max(0, pos - 6):pos]):
                        fallback = True
                        items.append(f"{where}: listenerKnows 提到「{fact_text}」，knows 文件里 {person!r} 本场不知道这件事（文本粗核）")
    return {"status": "report", "items": items, "textHeuristicFallback": fallback,
            "signalQuality": "low" if fallback else "id"}


def check_addressee(dplan):
    items = []
    for scene in dplan.get("scenes") or []:
        sid = scene.get("sceneId")
        items += [f"{sid}/monologues[{i}]({m.get('who')}): 缺 whyNoAddressee"
                  for i, m in enumerate(scene.get("monologues") or []) if not is_nonempty(m.get("whyNoAddressee"))]
        for topic in scene.get("topics") or []:
            items += [f"{sid}/{topic.get('topicId')}/exchanges[{i}]({ex.get('exchangeId')}): 没有 addressee，也没有 whyNoAddressee"
                      for i, ex in enumerate(topic.get("exchanges") or [])
                      if not is_nonempty(ex.get("addressee")) and not is_nonempty(ex.get("whyNoAddressee"))]
    return {"status": "fail" if items else "pass", "items": items}


def count_sentences(text: str) -> int:
    return len([part for part in SENTENCE_END_RE.split(text) if part.strip()])


def check_exemplars(dplan):
    items = []
    for scene, topic in iter_topics(dplan):
        where = f"{scene.get('sceneId')}/{topic.get('topicId')}"
        exemplars = topic.get("exemplars") if isinstance(topic.get("exemplars"), dict) else {}
        positives = exemplars.get("positives") or []
        if not positives and not exemplars.get("no_exemplar"):
            items.append(f"{where}: exemplars.positives 为空，也没有标 no_exemplar")
        for j, positive in enumerate(positives):
            pwhere = f"{where}/exemplars.positives[{j}]"
            source = positive.get("source")
            if source not in EXEMPLAR_SOURCES:
                items.append(f"{pwhere}: source={source!r} 不在 {sorted(EXEMPLAR_SOURCES)}")
            if source == "corpus":
                lines = positive.get("maskedLines")
                if not isinstance(lines, list) or not lines:
                    items.append(f"{pwhere}: source=corpus 但没有 maskedLines（遮蔽原句）")
                elif count_sentences("".join(map(str, lines))) > 2:
                    items.append(f"{pwhere}: 遮蔽原句 {count_sentences(''.join(map(str, lines)))} 句，超过 2 句：{lines!r}")
    return {"status": "fail" if items else "pass", "items": items}


def scan_quota_keys(obj, path=""):
    items = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else key
            if key in FORBIDDEN_KEYS:
                items.append(f"{here}: 出现禁止的字段 {key!r}（对话表无估时与配额）")
            elif QUOTA_KEY_RE.search(key) and isinstance(value, (int, float)) and not isinstance(value, bool):
                items.append(f"{here}: 字段名像数量配额（{key}={value}），数字不当裁判")
            items += scan_quota_keys(value, here)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            items += scan_quota_keys(value, f"{path}[{i}]")
    return items


def check_change_proposals(dplan):
    items = []
    for i, proposal in enumerate(dplan.get("changeProposals") or []):
        where = f"changeProposals[{i}]({proposal.get('id')})"
        if not is_nonempty(proposal.get("targetLayer")):
            items.append(f"{where}: 缺 targetLayer")
        if not is_nonempty(proposal.get("default")):
            items.append(f"{where}: 缺非空 default（流程按默认走法继续）")
    return {"status": "fail" if items else "pass", "items": items}


def run_dialogue_plan_check(dialogue_plan_path, episode_plan_path, knows_path) -> dict:
    dplan = load_json(dialogue_plan_path, "对话表")
    episode_plan = load_json(episode_plan_path, "分集计划")
    knows_index, within_index = build_knows_index(load_json(knows_path, "knows 导出"))
    episode_facts = {f.get("factId"): {"infoId": info.get("infoId")} for info in episode_plan.get("infoLedger") or []
                     for f in info.get("facts") or [] if f.get("factId")}
    quota = scan_quota_keys(dplan)
    rules = {
        "info-ledger": check_info_ledger(dplan, episode_facts),
        "topics-segments": check_topics_segments(dplan),
        "listener-knows": check_listener_knows(dplan, knows_index),
        "speaker-knows": check_speaker_knows(dplan, episode_plan, knows_index, within_index),
        "addressee": check_addressee(dplan),
        "exemplars": check_exemplars(dplan),
        "no-quota-fields": {"status": "fail" if quota else "pass", "items": quota},
        "change-proposals": check_change_proposals(dplan),
    }
    return {"ok": True, "passed": not any(r["status"] == "fail" for r in rules.values()), "rules": rules}


def _main(argv):
    parser = argparse.ArgumentParser(description="核对话表（dialogue-plan）的 S 项")
    parser.add_argument("dialogue_plan")
    parser.add_argument("--episode-plan", required=True)
    parser.add_argument("--knows", required=True, help="ledger knows 的导出（按场、按人，含 withinScene）")
    args = parser.parse_args(argv)
    result = run_dialogue_plan_check(args.dialogue_plan, args.episode_plan, args.knows)
    result["reproduceCommand"] = reproduce_command("dialogue_plan_check", [
        abspath(args.dialogue_plan), "--episode-plan", abspath(args.episode_plan), "--knows", abspath(args.knows)])
    return result, (0 if result["passed"] else 2)


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
