"""plan-check: script checks (S) of one episode plan against its entry ledger revision.

Covers the S parts of the episode-plan field table (outline-layer design §4): required fields,
episode and functions assigned by the season plan, self-contained `events.scenes[].beats[]`,
`exit.closingEvent` on the last beat, presence against the timeline ledger (report only),
`infoLedger` facts, the plan's `ledgerDelta` (applies, single object chain, knowledge monotonic,
patch cap, supportedBy resolves), speaker-knows by beat, reality refs, threads (ordered by the
season plan's finalSequence, never by comparing raw episode ids), capacity status and pending
decisions. Passing proves the structure and the ledger bookkeeping only; whether a move is
motivated, a reason holds or a fact is really needed is model work (M) and is not judged here.

speaker-knows: a beat whose quote says a fact (`saysFact`: a factId or a ledger knowledge id)
needs the speaker to know it by then. A factId is matched by ledger ids only — the speaker's own
`knownByInStoryRefs[]` item plus the fact's `ledgerRef[]` entries that are about the speaker —
never by text; a fact with no such id is listed under notEvaluable. Known means one of: (a) known
before the scene (ledger at plan entry plus this plan's writes, judged by beat timing as
`ledger knows --episode-plan` does); (b) told earlier in the scene: an earlier beat of the scene
said the same thing with the speaker present, or the ledger times the speaker knowing it at an
earlier beat of this scene (or at this beat marked 「之前」); (c) the
speaker is the actor: this scene writes a knowledge entry of the same id for the speaker with how
「自己做的」/「在场」, timed no later than the beat. (b) and (c) are listed as exemptions.

Read-only; never goes online or calls a model. Exit codes: 0 no rule failed; 1 input error;
2 a rule failed.
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    from . import ledger as L
except ImportError:  # run as a script
    import ledger as L

REQUIRED_FIELDS = ["episode", "title", "entry", "functions", "events", "moves", "infoLedger", "ledgerDelta", "exit", "capacity"]
SELF_ACTOR_HOW_MARKERS = ("自己做的", "在场")
LEDGER_ID_PREFIX = "L-"


def result(items, blocking=None):
    """fail when a blocking item exists; items starting with "（" are notes (report only)."""
    blocking = [i for i in items if not (isinstance(i, str) and i.startswith("（"))] if blocking is None else blocking
    return {"status": "fail" if blocking else ("report" if items else "pass"), "items": items}


def check_required_fields(plan):
    return result([f"缺或为空: {f}" for f in REQUIRED_FIELDS if not L.is_nonempty(plan.get(f))])


def season_episode(season_doc, episode):
    for ep in (season_doc or {}).get("episodes", []) or []:
        if str(ep.get("episode")) == str(episode):
            return ep
    return None


def collect_scene_beat_ids(plan):
    scene_ids, beat_ids = set(), set()
    for sc in (plan.get("events") or {}).get("scenes", []) or []:
        if L.is_nonempty(sc.get("sceneId")):
            scene_ids.add(sc["sceneId"])
        for b in sc.get("beats", []) or []:
            if L.is_nonempty(b.get("beatId")):
                beat_ids.add(b["beatId"])
    return scene_ids, beat_ids


def check_functions_assigned(plan, function_map_doc, season_doc):
    items = []
    all_ids = L.collect_function_ids(function_map_doc) if function_map_doc else None
    season_ep = season_episode(season_doc, plan.get("episode"))
    season_ids = set(season_ep.get("functions", []) or []) if season_ep else None
    for f in plan.get("functions", []) or []:
        fid = f.get("functionId") if isinstance(f, dict) else f
        if not L.is_nonempty(fid):
            items.append("functions[] 里有一项缺 functionId")
            continue
        if all_ids is not None and fid not in all_ids:
            items.append(f"functionId {fid!r} 不在功能地图里")
        if season_ids is not None and fid not in season_ids:
            items.append(f"functionId {fid!r} 季编排没有把它分到第 {plan.get('episode')} 集")
    if all_ids is None:
        items.append("（未给 --function-map，functionId 存在性未核）")
    if season_ids is None:
        items.append("（未给 --season 或季编排里没有本集，分配关系未核）")
    return result(items)


def check_events_well_formed(plan):
    """Every scene has sceneId, time, place, present[]; every beat has a unique beatId and text."""
    scenes = (plan.get("events") or {}).get("scenes")
    if not L.is_nonempty(scenes):
        return result(["events.scenes 为空"])
    items, seen_scenes, seen_beats = [], set(), set()
    for i, sc in enumerate(scenes):
        sid = sc.get("sceneId")
        where = f"scenes[{i}]({sid})"
        if not L.is_nonempty(sid):
            items.append(f"{where}: 缺 sceneId")
        elif sid in seen_scenes:
            items.append(f"{where}: sceneId 重复")
        seen_scenes.add(sid)
        for f in ("time", "place"):
            if not L.is_nonempty(sc.get(f)):
                items.append(f"{where}: 缺 {f}")
        if not isinstance(sc.get("present"), list) or not sc.get("present"):
            items.append(f"{where}: present 为空或不是数组")
        beats = sc.get("beats")
        if not L.is_nonempty(beats):
            items.append(f"{where}: beats 为空")
            continue
        for j, b in enumerate(beats):
            bid = b.get("beatId")
            if not L.is_nonempty(bid):
                items.append(f"{where}/beats[{j}]: 缺 beatId")
            elif bid in seen_beats:
                items.append(f"{where}/beats[{j}]: beatId {bid!r} 重复")
            seen_beats.add(bid)
            if not L.is_nonempty(b.get("text")):
                items.append(f"{where}/beats[{j}]({bid}): 缺 text")
    return result(items)


def check_closing_event(plan):
    scenes = (plan.get("events") or {}).get("scenes") or []
    if not scenes or not (scenes[-1].get("beats") or []):
        return result(["events 最后一场没有 beats，无法核 closingEvent"])
    expected = scenes[-1]["beats"][-1].get("beatId")
    actual = ((plan.get("exit") or {}).get("closingEvent") or {}).get("beatRef")
    if actual != expected:
        return result([f"exit.closingEvent.beatRef={actual!r}，应为最后一场最后一拍 {expected!r}"])
    return result([])


def check_info_ledger(plan, beat_ids):
    """Every info item has knownByInStory and facts; every fact has a unique factId, text, a
    carrierBeat that is a beat of this plan, and keywords (retell-check matches on them)."""
    items, seen = [], set()
    for i, info in enumerate(plan.get("infoLedger", []) or []):
        where = f"infoLedger[{i}]({info.get('infoId')})"
        if not L.is_nonempty(info.get("knownByInStory")):
            items.append(f"{where}: knownByInStory 为空")
        facts = info.get("facts")
        if not L.is_nonempty(facts):
            items.append(f"{where}: facts 为空")
            continue
        for j, fact in enumerate(facts):
            fid = fact.get("factId")
            fwhere = f"{where}/facts[{j}]({fid})"
            if not L.is_nonempty(fid):
                items.append(f"{fwhere}: 缺 factId")
            elif fid in seen:
                items.append(f"{fwhere}: factId 重复")
            seen.add(fid)
            if not L.is_nonempty(fact.get("text")):
                items.append(f"{fwhere}: 缺 text")
            carrier = fact.get("carrierBeat")
            if not L.is_nonempty(carrier):
                items.append(f"{fwhere}: 缺 carrierBeat")
            elif carrier not in beat_ids:
                items.append(f"{fwhere}: carrierBeat={carrier!r} 不是本集存在的 beatId")
            if not L.is_nonempty(fact.get("keywords")):
                items.append(f"{fwhere}: keywords 为空（retell-check 要用它核复述）")
    return result(items)


def check_ledger_delta(plan, entries_by_id, scene_ids, beat_ids):
    delta = plan.get("ledgerDelta")
    if not L.is_nonempty(delta) or not isinstance(delta, dict):
        return result(["ledgerDelta 为空"])
    delta = dict(delta)
    delta.setdefault("episode", plan.get("episode"))
    delta.setdefault("track", "planned")
    items = []
    for name, rule in (("delta-applies", L.rule_delta_applies(entries_by_id, [delta])),
                       ("object-single-chain", L.rule_object_single_chain(entries_by_id, [delta])),
                       ("knowledge-monotonic", L.rule_knowledge_monotonic(entries_by_id, [delta])),
                       ("patch-cap", L.rule_patch_cap(entries_by_id, [delta]))):
        items.extend(f"[{name}] {it}" for it in rule["items"])
    for i, w in enumerate(delta.get("writes", []) or []):
        supported = w.get("supportedBy")
        if not L.is_nonempty(supported):
            items.append(f"writes[{i}]({w.get('entryId')}): supportedBy 为空")
        elif supported not in scene_ids and supported not in beat_ids:
            items.append(f"writes[{i}]({w.get('entryId')}): supportedBy={supported!r} 不是本集存在的 sceneId/beatId")
    for rid in delta.get("reads", []) or []:
        if rid not in entries_by_id:
            items.append(f"reads 引用的 id {rid!r} 不存在")
    return result(items)


def entry_is_about(entry, person):
    """Whether a ledger entry records something this person knows or sees."""
    kind = (entry or {}).get("kind")
    if kind == "knowledge":
        return entry.get("who") == person
    if kind == "object":
        return person in (entry.get("visibleTo") or [])
    if kind == "timeline":
        return person in (entry.get("knownTo") or [])
    return False


def fact_ledger_ids(fact, info, person, entries_by_id):
    """Ledger ids that stand for a fact for one person: the person's own knownByInStoryRefs item(s)
    plus those fact.ledgerRef entries that are about this person (another person's knowledge entry
    says nothing about the speaker). Names in knownByInStory are not ids and are never matched."""
    ids = set()
    for item in info.get("knownByInStoryRefs", []) or []:
        if isinstance(item, dict) and item.get("who") == person and item.get("ledgerRef"):
            r = item["ledgerRef"]
            ids.update(r if isinstance(r, list) else [r])
    ref = fact.get("ledgerRef")
    for r in (ref if isinstance(ref, list) else [ref]) if ref else []:
        if entry_is_about(entries_by_id.get(r), person):
            ids.add(r)
    return ids


BEFORE_MARKER = "之前"  # "ep5 5-2.b2 之前": known by that beat, not learnt at it


def timed_in_scene_by(entry, person, scene_id, beat_num):
    """The ledger times this person knowing the entry (or one of its parts) at an earlier beat of
    this scene, or at this beat marked 「之前」."""
    kind = (entry or {}).get("kind")
    if kind == "knowledge":
        parts = L.since_value_parts(entry.get("since"))
    elif kind in ("object", "timeline"):
        parts = L.person_since_parts(entry.get("visibleToSince" if kind == "object" else "knownToSince"), person)
    else:
        parts = None
    for _, beat in parts or []:
        scene, num = L.parse_beat_ref(beat)
        if scene == scene_id and num is not None and beat_num is not None and (
                num < beat_num or (num == beat_num and BEFORE_MARKER in str(beat))):
            return True
    return False


def self_writes_by_scene(plan):
    """{(sceneId, who): {entryId: beatNum|None}}: knowledge writes for `who` whose how says the person
    did it or was there, placed by `since` (or the write's supportedBy when since has no beat)."""
    idx = {}
    for w in (plan.get("ledgerDelta") or {}).get("writes", []) or []:
        change = w.get("change") or {}
        target, who, how = L.write_target_id(w), change.get("who"), str(change.get("how") or "")
        if not (target and who) or not any(m in how for m in SELF_ACTOR_HOW_MARKERS):
            continue
        scene, num = L.parse_beat_ref(change.get("since") if isinstance(change.get("since"), str) else None)
        if scene is None:
            supported = w.get("supportedBy") or ""
            scene, num = L.parse_beat_ref(supported)
            if scene is None and supported:
                scene = supported.split(".")[0]
        if scene:
            idx.setdefault((scene, who), {})[target] = num
    return idx


def check_speaker_knows(plan, entries_by_id):
    fact_index = {}
    for info in plan.get("infoLedger", []) or []:
        for fact in info.get("facts", []) or []:
            if L.is_nonempty(fact.get("factId")):
                fact_index[fact["factId"]] = (info, fact)
    scenes = (plan.get("events") or {}).get("scenes") or []
    order = {sc.get("sceneId"): i for i, sc in enumerate(scenes)}
    self_writes = self_writes_by_scene(plan)
    states, _, _ = L.scene_states(entries_by_id, plan)
    items, not_evaluable, exemptions = [], [], []
    for sc, working, touched in states:
        sid = sc.get("sceneId")
        present = sc.get("present") or []
        prior_cache, heard = {}, {}
        for b in sc.get("beats", []) or []:
            says = b.get("saysFact")
            if not says:
                continue
            speaker, bid = b.get("who"), b.get("beatId")
            _, beat_num = L.parse_beat_ref(bid)
            for ref in says if isinstance(says, list) else [says]:
                where = f"{bid}（{speaker} 说 {ref}）"
                if ref in fact_index:
                    ids = fact_ledger_ids(fact_index[ref][1], fact_index[ref][0], speaker, working)
                elif isinstance(ref, str) and ref.startswith(LEDGER_ID_PREFIX) and ref in working:
                    ids = {ref}
                else:
                    items.append(f"{where}: {ref!r} 既不是本集 infoLedger 的 factId，也不是底账里的条目")
                    continue
                if not ids:
                    not_evaluable.append({"beat": bid, "speaker": speaker, "ref": ref,
                                          "why": f"knownByInStoryRefs 没有 {speaker!r} 的底账 id，fact.ledgerRef 里也没有记他知情的条目；不按文本猜"})
                    continue
                if speaker not in prior_cache:
                    prior_cache[speaker] = {k.get("entryId") for k in L.knows_scene_aware(working, speaker, order, sid, touched)["knows"]}
                if ids & prior_cache[speaker]:
                    continue
                basis = None
                if ref in heard.get(speaker, set()):
                    basis = "told_earlier_in_scene"
                elif any(timed_in_scene_by(working.get(i), speaker, sid, beat_num) for i in ids):
                    basis = "within_scene_beat"
                else:
                    own = self_writes.get((sid, speaker), {})
                    matched = ids & set(own)
                    if matched and any(beat_num is None or own[m] is None or own[m] <= beat_num for m in matched):
                        basis = "same_scene_actor"
                if basis:
                    exemptions.append({"beat": bid, "speaker": speaker, "ref": ref, "ledgerIds": sorted(ids), "basis": basis})
                else:
                    items.append(f"{where}: 对应底账 id {sorted(ids)}；场前不知道，本场更早没人告诉他，"
                                 f"本场也没有他作为行动者、拍号不晚于此的同 id 知识写入——speaker-not-knows")
            for person in present:
                heard.setdefault(person, set()).update(says if isinstance(says, list) else [says])
    out = result(items)
    out.update({"notEvaluable": not_evaluable, "exemptions": exemptions})
    return out


def check_reality_refs(plan, entries_by_id):
    """Every ref exists; unverified ones are counted (report); contested must be zero."""
    refs = plan.get("realityRefs", []) or []
    missing = [r for r in refs if r not in entries_by_id]
    unverified = [r for r in refs if r in entries_by_id and entries_by_id[r].get("status") == "unverified"]
    contested = [r for r in refs if r in entries_by_id and entries_by_id[r].get("status") == "contested"]
    return {"status": "fail" if missing or contested else "pass",
            "items": {"missing": missing, "unverifiedCount": len(unverified), "unverifiedIds": unverified, "contestedIds": contested}}


def build_episode_order(season_doc):
    """{str(id): newEpisodeNo} from the season plan's finalSequence (the sequence after actions)."""
    return {str(r.get("id")): r.get("newEpisodeNo") for r in (season_doc or {}).get("finalSequence", []) or []}


def check_threads(plan, season_doc):
    """Each pay's plant exists in the season plan and is planted before this episode; each plant has a
    pay position. Order comes from finalSequence; an end missing from it (out of scope) is noted, not
    guessed."""
    threads = plan.get("threads") or {}
    items = []
    season_threads = {t.get("plantId"): t for t in (season_doc or {}).get("threads", []) or []}
    order = build_episode_order(season_doc)
    here = order.get(str(plan.get("episode")))
    for pay in threads.get("pays", []) or []:
        t = season_threads.get(pay)
        if season_doc is None:
            items.append(f"（未给 --season，pay {pay} 的埋设位未核）")
        elif t is None:
            items.append(f"pay {pay!r} 在季编排 threads 里找不到对应的 plant")
        else:
            at = order.get(str(t.get("plantedAt")))
            if at is None or here is None:
                items.append(f"（pay {pay!r} 的 plantedAt={t.get('plantedAt')!r} 或本集在季编排 finalSequence 里查不到新集号，先后未核）")
            elif at >= here:
                items.append(f"pay {pay!r} 的 plantedAt={t.get('plantedAt')} 不在本集（{plan.get('episode')}）之前")
    for plant in threads.get("plants", []) or []:
        pid = plant.get("plantId")
        if season_doc is None:
            items.append(f"（未给 --season，plant {pid} 的回收位未核）")
            continue
        t = season_threads.get(pid)
        if t is None or not L.is_nonempty(t.get("payAt")):
            items.append(f"plant {pid!r} 在季编排 threads 里没有回收位（payAt）")
    return result(items)


def decision_index(decisions_doc):
    return {d.get("id"): d for d in (decisions_doc or {}).get("entries", []) or []}


def check_capacity(plan, decisions_doc):
    """Fields present; status is fits or proposal:<id> whose decision exists with a default. The
    estimate is never compared with the target here (numbers are not judges)."""
    cap = plan.get("capacity") or {}
    items = [f"capacity.{f} 缺失" for f in ("infoCount", "sceneCount", "estimateSec", "targetSec", "status")
             if not L.is_nonempty(cap.get(f)) and cap.get(f) != 0]
    status = cap.get("status")
    if isinstance(status, str) and status.startswith("proposal:"):
        pid = status.split(":", 1)[1]
        entries = decision_index(decisions_doc)
        if decisions_doc is None:
            items.append(f"（未给 --decisions，proposal {pid} 的 default 未核）")
        elif pid not in entries:
            items.append(f"capacity.status 引用的决定 {pid!r} 在决定队列里不存在")
        elif not L.is_nonempty(entries[pid].get("default")):
            items.append(f"决定 {pid!r} 没有 default，不能作为 capacity 的默认走法")
    elif status != "fits" and L.is_nonempty(status):
        items.append(f"capacity.status={status!r} 不是 fits 或 proposal:<id>")
    return result(items)


def check_pending(plan, decisions_doc):
    items = []
    entries = decision_index(decisions_doc)
    for i, p in enumerate(plan.get("pending", []) or []):
        did = p.get("decisionId")
        if not L.is_nonempty(did):
            items.append(f"pending[{i}]: 缺 decisionId")
            continue
        if decisions_doc is None:
            items.append(f"（未给 --decisions，pending[{i}]（{did}）未核）")
        elif did not in entries:
            items.append(f"pending[{i}]: decisionId {did!r} 在决定队列里不存在")
        elif not L.is_nonempty(entries[did].get("default")):
            items.append(f"pending[{i}]: 决定 {did!r} 没有 default")
        if not L.is_nonempty(p.get("defaultUsed")):
            items.append(f"pending[{i}]: 缺 defaultUsed（本集采用的默认走法）")
    return result(items)


def check_summary(plan):
    """Derived summary text should appear in events (coarse literal check; report only)."""
    summary = plan.get("summary")
    if not L.is_nonempty(summary):
        return {"status": "report", "items": ["（无 summary，可选字段）"]}
    events_text = json.dumps(plan.get("events"), ensure_ascii=False)
    items = [f"summary.{k} 的内容在 events 里找不到字面出现（粗核，不拦）：{v[:40]}"
             for k, v in (summary.items() if isinstance(summary, dict) else []) if isinstance(v, str) and v and v not in events_text]
    return {"status": "report", "items": items}


def run_plan_check(plan, entries_by_id, season_doc=None, function_map_doc=None, decisions_doc=None):
    scene_ids, beat_ids = collect_scene_beat_ids(plan)
    in_season = season_doc is None or season_episode(season_doc, plan.get("episode")) is not None
    rules = {
        "required-fields": check_required_fields(plan),
        "episode-matches-season": result([] if in_season else [f"第 {plan.get('episode')} 集不在季编排 episodes 里"]),
        "functions-assigned": check_functions_assigned(plan, function_map_doc, season_doc),
        "events-well-formed": check_events_well_formed(plan),
        "closing-event": check_closing_event(plan),
        "presence-vs-timeline": {"status": "report", "items": L.presence_vs_timeline(entries_by_id, (plan.get("events") or {}).get("scenes"))},
        "info-ledger": check_info_ledger(plan, beat_ids),
        "ledger-delta": check_ledger_delta(plan, entries_by_id, scene_ids, beat_ids),
        "speaker-knows": check_speaker_knows(plan, entries_by_id),
        "reality-refs": check_reality_refs(plan, entries_by_id),
        "threads": check_threads(plan, season_doc),
        "capacity": check_capacity(plan, decisions_doc),
        "pending": check_pending(plan, decisions_doc),
        "summary": check_summary(plan),
    }
    return rules, not any(r["status"] == "fail" for r in rules.values())


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog=prog, description="分集计划（episode-plan）S 核")
    ap.add_argument("episode_plan")
    ap.add_argument("--ledger", required=True, help="入口修订（entry.ledgerRev 对应的底账文件）")
    ap.add_argument("--season", default=None)
    ap.add_argument("--function-map", default=None)
    ap.add_argument("--decisions", action="append", default=[], help="决定队列文件，可给多个")
    args = ap.parse_args(argv)
    try:
        plan = L.load_json(args.episode_plan, "分集计划")
        if not isinstance(plan, dict):
            raise L.InputError("分集计划不是 JSON 对象")
        _, entries_by_id, _ = L.load_ledger(args.ledger)
        season_doc = L.load_json(args.season, "季编排") if args.season else None
        function_map_doc = L.load_json(args.function_map, "功能地图") if args.function_map else None
        decisions_doc = L.merge_decision_docs([L.load_json(p, "决定队列") for p in args.decisions]) if args.decisions else None
    except (L.InputError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    rules, passed = run_plan_check(plan, entries_by_id, season_doc, function_map_doc, decisions_doc)
    L.emit({"ok": True, "passed": passed, "episode": plan.get("episode"), "rules": rules,
            "reproduceCommand": L.reproduce_command(__file__, argv)})
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
