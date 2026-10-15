"""season-plan check: script checks (S) of a season plan (outline-layer design §7.2, §7.4).

Rules:
  capacity-fields      every episode has capacity {infoCount, pictureBeats, estimateSec, targetSec, status}
  action-when-exceeds  status "exceeds" needs action ∈ rearrange/split/drop_function and actionDetail;
                       「待定」/"pending" anywhere in capacity fails (an action must be chosen, §7.2)
  drop-not-default     a dropped line is never the system default: drop_function needs capacity.decisionRef
                       to a decided decision with humanWords; a referenced decision whose default option
                       loses function sentences (losesFunctions non-empty) fails
  threads-pay          every plant has payAt
  functions-covered    every selected function of the function map is in some episode or marked outOfScope
  splits               split parents have >= 2 children "<parent>A, B, ..." (splitFrom) and vice versa
  final-sequence       finalSequence estimateSec (and estimateSecBasisB) recomputed with the capacity
                       formula; more than 1 second off fails (arithmetic consistency, not a verdict)
  moves-reciprocal     infoItemsRough moved_out(to) has a moved_in/merged_in(from) in the target, and back
  decision-refs        decisions[] and pending[].decisionId exist in the given decision files

Episode ids may be integers or "number+letter" strings; they are compared as strings, never by
magnitude. Read-only; never goes online or calls a model. Exit codes: 0 no rule failed; 1 input
error; 2 a rule failed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

try:
    from . import capacity as C
    from . import ledger as L
except ImportError:  # run as a script
    import capacity as C
    import ledger as L

PENDING_WORDS = ("待定", "pending")
VALID_ACTIONS = {"rearrange", "split", "drop_function"}


def rule(items):
    blocking = [i for i in items if not i.startswith("（")]
    return {"status": "fail" if blocking else ("report" if items else "pass"), "items": items}


def check_capacity_fields(episodes):
    items = []
    for ep in episodes:
        cap = ep.get("capacity") or {}
        for f in ("infoCount", "pictureBeats", "estimateSec", "targetSec", "status"):
            if not L.is_nonempty(cap.get(f)) and cap.get(f) != 0:
                items.append(f"ep{ep.get('episode')}: capacity.{f} 缺失")
        if cap.get("status") not in (None, "fits", "exceeds"):
            items.append(f"ep{ep.get('episode')}: capacity.status={cap.get('status')!r} 不是 fits/exceeds")
    return rule(items)


def check_action_when_exceeds(episodes):
    items = []
    for ep in episodes:
        cap = ep.get("capacity") or {}
        if cap.get("status") == "exceeds":
            if cap.get("action") not in VALID_ACTIONS:
                items.append(f"ep{ep.get('episode')}: status=exceeds 但 action={cap.get('action')!r} 不在 {sorted(VALID_ACTIONS)}")
            if not L.is_nonempty(cap.get("actionDetail")):
                items.append(f"ep{ep.get('episode')}: status=exceeds 但 actionDetail 为空")
        text = json.dumps(cap, ensure_ascii=False)
        hits = [w for w in PENDING_WORDS if w in text]
        if hits:
            items.append(f"ep{ep.get('episode')}: capacity 里出现「{'、'.join(hits)}」，不许用待定代替选动作")
    return rule(items)


def loses_functions(option):
    value = (option or {}).get("losesFunctions")
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, str):
        return not value.startswith("not_evaluable")
    return False


def check_drop_not_default(doc, episodes, decisions):
    items = []
    if decisions is None:
        items.append("（未给 --decisions，删线是否为人定、引用决定的默认是否删功能未核）")
    for ep in episodes:
        cap = ep.get("capacity") or {}
        if cap.get("action") != "drop_function" or decisions is None:
            continue
        ref = cap.get("decisionRef")
        d = decisions.get(ref)
        if d is None:
            items.append(f"ep{ep.get('episode')}: action=drop_function 但 capacity.decisionRef={ref!r} 不是给定决定队列里的决定（删线只能由人定）")
        elif d.get("status") != "decided" or not L.is_nonempty(d.get("humanWords")):
            items.append(f"ep{ep.get('episode')}: action=drop_function 引用的 {ref} 还没有带 humanWords 的决定（删线不能按默认走）")
    if decisions is not None:
        refs = list(doc.get("decisions", []) or []) + [p.get("decisionId") for p in doc.get("pending", []) or []]
        for ref in dict.fromkeys(r for r in refs if r in decisions):
            d = decisions[ref]
            default = next((o for o in d.get("options", []) or [] if o.get("optionId") == d.get("default")), None)
            if loses_functions(default):
                items.append(f"{ref}: 默认选项 {d.get('default')!r} 带非空 losesFunctions，删功能不能是系统默认")
    return rule(items)


def check_threads(doc):
    return rule([f"plant {t.get('plantId')!r} 没有 payAt（没有回收位）" for t in doc.get("threads", []) or []
                 if not L.is_nonempty(t.get("payAt"))])


def check_functions_covered(episodes, function_map_doc):
    if function_map_doc is None:
        return rule(["（未给 --function-map，功能覆盖未核）"])
    assigned = {f for ep in episodes for f in ep.get("functions", []) or []}
    items = []
    for thread in function_map_doc.get("threads", []) or []:
        for fn in thread.get("functions", []) or []:
            if fn.get("status") == "selected" and fn.get("functionId") not in assigned and not L.is_nonempty(fn.get("outOfScope")):
                items.append(f"功能 {fn.get('functionId')!r} 已 selected，但季编排没有把它分到任何一集，也没有标 outOfScope")
    return rule(items)


def check_splits(episodes):
    items, children = [], {}
    for ep in episodes:
        if ep.get("role") != "split_child":
            continue
        if ep.get("splitFrom") is None:
            items.append(f"ep{ep.get('episode')}: role=split_child 但缺 splitFrom")
        else:
            children.setdefault(str(ep["splitFrom"]), []).append(str(ep.get("episode")))
    for ep in episodes:
        ep_id = str(ep.get("episode"))
        action = (ep.get("capacity") or {}).get("action")
        kids = children.get(ep_id, [])
        if action == "split":
            if len(kids) < 2:
                items.append(f"ep{ep_id}: capacity.action=split 但 splitFrom={ep_id} 的子集只有 {len(kids)} 个，至少要 2 个")
            letters = []
            for c in kids:
                m = re.fullmatch(rf"{re.escape(ep_id)}([A-Z])", c)
                if m:
                    letters.append(m.group(1))
                else:
                    items.append(f"ep{ep_id}: 子集 id {c!r} 不是「{ep_id}+字母」形态")
            letters.sort()
            if letters != [chr(ord("A") + i) for i in range(len(letters))]:
                items.append(f"ep{ep_id}: 子集字母不连续或不是从 A 开始：{letters}")
        elif kids:
            items.append(f"ep{ep_id}: 有 splitFrom={ep_id} 的子集 {kids}，但父集 capacity.action 不是 split（是 {action!r}）")
    return rule(items)


def check_final_sequence(doc, episodes, args):
    final = doc.get("finalSequence")
    if not isinstance(final, list) or not final:
        return rule(["（季编排没有 finalSequence，动作后集序列未核）"])
    if args.media is None or (args.corpus is None and args.exchange_median_sec is None):
        return rule(["（未给 --media 与 --corpus，finalSequence 的估时复算未核）"])
    basis, _ = C.outline_basis(args)
    by_id = {str(ep.get("episode")): ep for ep in episodes}
    items = []
    for item in final:
        iid = item.get("id")
        info, pics = C.number(item.get("infoCount")), C.number(item.get("pictureBeats"))
        if info is None or pics is None:
            items.append(f"finalSequence id={iid}: 缺 infoCount/pictureBeats，复算不了")
            continue
        stated = C.number(item.get("estimateSec"))
        recomputed = C.estimate(info, pics, basis)
        if stated is None:
            items.append(f"finalSequence id={iid}: 缺 estimateSec")
        elif abs(recomputed - stated) > 1.0:
            items.append(f"finalSequence id={iid}: estimateSec={stated} 与复算 {recomputed} 相差超过 1 秒"
                         f"（{info}×{basis['exchangeMedianSec']} + {pics}×{basis['pictureBeatSec']}）")
        stated_b, ep = C.number(item.get("estimateSecBasisB")), by_id.get(str(iid))
        if stated_b is not None and ep is not None:
            d, p, _ = C.carriers(C.season_items(ep, ("kept", "moved_in")))
            recomputed_b = C.estimate(d, p + pics, basis)
            if abs(recomputed_b - stated_b) > 1.0:
                items.append(f"finalSequence id={iid}: estimateSecBasisB={stated_b} 与复算 {recomputed_b} 相差超过 1 秒"
                             f"（台词承载 {d}，画面承载 {p}＋画面拍 {pics}）")
    return rule(items)


def check_moves_reciprocal(episodes):
    items = []
    by_id = {str(ep.get("episode")): ep for ep in episodes}
    for ep in episodes:
        here = str(ep.get("episode"))
        for item in ep.get("infoItemsRough", []) or []:
            status, iid = item.get("status"), item.get("id")
            if status == "moved_out":
                other, field, want, back = item.get("to"), "to", ("moved_in", "merged_in"), "from"
            elif status in ("moved_in", "merged_in"):
                other, field, want, back = item.get("from"), "from", ("moved_out",), "to"
            else:
                continue
            if not L.is_nonempty(other):
                items.append(f"ep{here}: infoItemsRough {iid} status={status} 但缺 {field}")
                continue
            target = by_id.get(str(other))
            if target is None:
                items.append(f"ep{here}: infoItemsRough {iid} 的 {field}={other!r} 不是存在的集")
            elif not [x for x in target.get("infoItemsRough") or [] if x.get("status") in want and str(x.get(back)) == here]:
                items.append(f"ep{here}: infoItemsRough {iid}（{status}）在 ep{other} 找不到 {back}={here} 的 {'/'.join(want)} 条目对应")
    return rule(items)


def check_decision_refs(doc, decisions):
    if decisions is None:
        return rule(["（未给 --decisions，decision 引用未核）"])
    items = [f"season-plan.decisions 引用的 {d!r} 在给定的决定队列文件里都找不到" for d in doc.get("decisions", []) or [] if d not in decisions]
    items += [f"season-plan.pending 引用的 decisionId {p.get('decisionId')!r} 在给定的决定队列文件里都找不到"
              for p in doc.get("pending", []) or [] if L.is_nonempty(p.get("decisionId")) and p.get("decisionId") not in decisions]
    return rule(items)


def run_season_plan_check(doc, args, function_map_doc=None, decisions=None):
    episodes = doc["episodes"]
    dup = sorted({str(e.get("episode")) for e in episodes if [str(x.get("episode")) for x in episodes].count(str(e.get("episode"))) > 1})
    rules = {
        "episode-ids-unique": rule([f"episode {d} 重复" for d in dup]),
        "capacity-fields": check_capacity_fields(episodes),
        "action-when-exceeds": check_action_when_exceeds(episodes),
        "drop-not-default": check_drop_not_default(doc, episodes, decisions),
        "threads-pay": check_threads(doc),
        "functions-covered": check_functions_covered(episodes, function_map_doc),
        "splits": check_splits(episodes),
        "final-sequence": check_final_sequence(doc, episodes, args),
        "moves-reciprocal": check_moves_reciprocal(episodes),
        "decision-refs": check_decision_refs(doc, decisions),
    }
    return rules, not any(r["status"] == "fail" for r in rules.values())


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog=prog, description="季编排（season-plan）S 核")
    ap.add_argument("season_plan")
    ap.add_argument("--function-map", default=None)
    ap.add_argument("--media", default=None)
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--exchange-median-sec", type=float, default=None)
    ap.add_argument("--format", default="live")
    ap.add_argument("--picture-beat-sec", type=float, default=None)
    ap.add_argument("--decisions", action="append", default=[], help="决定队列文件，可给多个")
    args = ap.parse_args(argv)
    try:
        doc = L.load_json(args.season_plan, "季编排")
        if not isinstance(doc, dict) or not isinstance(doc.get("episodes"), list) or not doc["episodes"]:
            raise L.InputError("季编排缺 episodes 数组或为空")
        function_map_doc = L.load_json(args.function_map, "功能地图") if args.function_map else None
        merged = L.merge_decision_docs([L.load_json(p, "决定队列") for p in args.decisions]) if args.decisions else None
        decisions = {d.get("id"): d for d in merged["entries"] if L.is_nonempty(d.get("id"))} if merged else None
        rules, passed = run_season_plan_check(doc, args, function_map_doc, decisions)
    except (L.InputError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    L.emit({"ok": True, "passed": passed, "rules": rules, "reproduceCommand": L.reproduce_command(__file__, argv)})
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
