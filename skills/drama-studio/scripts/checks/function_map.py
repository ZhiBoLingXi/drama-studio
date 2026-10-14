"""function-map: check, merge, topics, and `defects build` from answer records.

  check <function-map> --stage v0|v1 --rc-dir <dir>... [--decisions F]... [--ledger F]
        [--records-base DIR] [--scope F] [--ref-remap OLD=NEW]...
      Structure (both stages): unique functionId; candidates have a unique candidateId, steps and
      ledgerDeps with kind and claim; rejected needs rejectedBecause; a selected function has exactly
      one selected candidate; dropped needs droppedCost; candidate status ∈ candidate/selected/rejected.
      v0: a selected candidate's inquiryRef names a reality-check record (checkId) that is not
      outcome fail and has no notHolds; open functions are allowed.
      v1 (outline-layer design v1.2 §2.2, §6.4): open functions only out of scope; a selected
      candidate has empty losesFunctions, deps with depId and assertion ∈ stated/required_unstated/
      absence, origin no less "user" than its steps' origins (d6-1 decision #4), a reality-check
      record (inquiryRef, else the record whose target.id is the candidate), and every closes[] item's
      confirmedBy ("path#record") resolves to a record item of that defect with verdict confirmed;
      every load-bearing notHolds answer in the (non-superseded) records has a disposition whose
      reference exists in the right state: decision(_queue) -> a decision with a default;
      license(_pending) -> a ledger entry license_pending/accepted_license (a retired entry is followed
      through retiresInto; --ref-remap maps an id moved without a retiresInto trail); confirmed(_gone)
      / retires_with -> a non-empty ref; leaves_open is not a place for a load-bearing gap.
      Records supersede others through their `supersedes` field (a path or checkId).
  merge <T-*.json files or dirs>... --out F    one map from per-thread files (no content change)
  topics <function-map> [--include-rejected]   retrieval topics merged from ledgerDeps of kind procedure
      and of assertion required_unstated (d6-1 decision #6), with the functions, candidates and
      episodes depending on each; merges only — never searches or goes online
  defects build --records <dir|file>... [--out F]   gap register generated from answer records:
      notHolds grouped by defectKey, with loadBearing, records and disposition (d6-1 decision #9: the
      answer record's disposition is the single source; the register is never hand-written)

Passing proves structure and references only; whether a gap is load-bearing, an answer holds or a
card says what it is cited for is model work. Never goes online or calls a model. Exit codes: 0
completed / rules hold; 1 input error; 2 a rule failed or a merge was refused.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

try:
    from . import ledger as L
except ImportError:  # run as a script
    import ledger as L

FUNCTION_STATUSES = ("open", "selected", "dropped")
CANDIDATE_STATUSES = ("candidate", "selected", "rejected")
ASSERTIONS = ("stated", "required_unstated", "absence")
ORIGIN_RANK = {"user_given": 3, "user_given_modified": 2, "derived_from_text": 1, "designed": 0}
# d6-1 decision #9 vocabulary; the D6-0 records wrote decision_queue / license_pending / confirmed / retires_with.
DISPOSITION_TO = {"decision": "decision", "decision_queue": "decision", "license": "license", "license_pending": "license",
                  "confirmed_gone": "confirmed_gone", "confirmed": "confirmed_gone", "retires_with": "confirmed_gone",
                  "leaves_open": "leaves_open"}
LOAD_BEARING_BASIS = ("stated_in_record", "has_downstream", "function_sentence_step")
LEDGER_ID_RE = re.compile(r"L-[A-Za-z]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
DQ_ID_RE = re.compile(r"DQ-[A-Za-z0-9-]+")
SCHEMA = "drama-studio/function-map/v0"
DEFECTS_SCHEMA = "drama-studio/defect-register/v0"


def json_files(paths):
    out = []
    for p in paths or []:
        if os.path.isdir(p):
            out.extend(sorted(glob.glob(os.path.join(p, "*.json"))))
        elif os.path.isfile(p):
            out.append(p)
        else:
            raise L.InputError(f"找不到记录目录或文件：{p}")
    return out


def load_records(paths):
    """{checkId: (doc, path)} of every JSON file with a checkId, and the set of superseded checkIds."""
    records = {}
    for path in json_files(paths):
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue  # a malformed record is check-answers' business, not this command's
        if isinstance(doc, dict) and L.is_nonempty(doc.get("checkId")):
            records[doc["checkId"]] = (doc, path)
    stems = {os.path.splitext(os.path.basename(p))[0]: cid for cid, (_, p) in records.items()}
    superseded_by = {}
    for cid, (doc, _) in records.items():
        sup = doc.get("supersedes")
        for ref in (sup if isinstance(sup, list) else [sup]) if sup else []:
            stem = os.path.splitext(os.path.basename(str(ref)))[0]
            old = ref if ref in records else stems.get(stem)
            if old and old != cid:
                superseded_by[old] = cid
    return records, superseded_by


def current(check_id, superseded_by):
    seen = set()
    while check_id in superseded_by and check_id not in seen:
        seen.add(check_id)
        check_id = superseded_by[check_id]
    return check_id


def target_matches(target_id, candidate_id):
    if not isinstance(target_id, str) or not isinstance(candidate_id, str):
        return False
    if target_id == candidate_id:
        return True
    rest = target_id[len(candidate_id):] if target_id.startswith(candidate_id) else None
    return bool(rest) and not re.match(r"[A-Za-z0-9.\-]", rest[0])


def find_record(cand, records, superseded_by):
    refs = cand.get("inquiryRef")
    for ref in (refs if isinstance(refs, list) else [refs]) if refs else []:
        if ref in records:
            return records[current(ref, superseded_by)][0]
    for cid, (doc, _) in records.items():
        target = doc.get("target") or {}
        if cid not in superseded_by and target.get("kind") == "candidate" and target_matches(target.get("id"), cand.get("candidateId")):
            return doc
    return None


def resolve_confirmed_by(confirmed_by, defect_id, base):
    """None when "path#record" resolves to an item of this defect with verdict confirmed; else why not.
    The record part may itself contain "#", so the split is at the first one only."""
    if "#" not in confirmed_by:
        return f"confirmedBy={confirmed_by!r} 不是「路径#record」形态"
    rel, record = confirmed_by.split("#", 1)
    full = os.path.join(base, rel)
    try:
        with open(full, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return f"confirmedBy 指的文件 {rel!r} 找不到（基准 {base!r}）"
    except (OSError, json.JSONDecodeError) as e:
        return f"confirmedBy 指的文件 {rel!r} 读不了：{e}"
    items = doc.get("items") if isinstance(doc.get("items"), list) else doc.get("closes")
    if not isinstance(items, list):
        return f"{rel!r} 既没有 items[] 也没有 closes[]"
    for it in items:
        if it.get("record") == record and (it.get("defectId") or it.get("defect")) == defect_id:
            return None if it.get("verdict") == "confirmed" else f"{rel}#{record}（{defect_id}）的 verdict 是 {it.get('verdict')!r}，不是 confirmed"
    return f"在 {rel!r} 里找不到 record={record!r} 且 defectId={defect_id!r} 的条目"


def disposition_error(item, decisions, ledger_by_id, remap):
    disp = item.get("disposition")
    where = f"{item['checkId']}#q{item.get('q')}（{item.get('defectKey')}）"
    if not isinstance(disp, dict) or not L.is_nonempty(disp.get("to")):
        return f"{where}: 承重 notHolds 没有 disposition 或 to 为空"
    to = DISPOSITION_TO.get(disp["to"])
    if to is None:
        return f"{where}: disposition.to={disp['to']!r} 不是已知去处"
    if to == "leaves_open":
        return f"{where}: 承重缺口不能 leaves_open（只有确认消失、戏剧假定、带默认的决定三个去处）"
    ref = disp.get("ref")
    if not L.is_nonempty(ref):
        return f"{where}: to={disp['to']} 但 ref 为空"
    refs = ref if isinstance(ref, list) else [ref]
    if to == "decision" and decisions is not None:
        for r in refs:
            m = DQ_ID_RE.search(str(r))
            did = m.group(0) if m else r
            if did not in decisions:
                return f"{where}: ref 里的决定 {did!r} 在 --decisions 里不存在"
            if not L.is_nonempty(decisions[did].get("default")):
                return f"{where}: 决定 {did!r} 没有 default"
    if to == "license" and ledger_by_id is not None:
        for r in refs:
            m = LEDGER_ID_RE.search(str(r))
            if not m:
                return f"{where}: ref={r!r} 里提不出底账 id"
            lid = remap.get(m.group(0), m.group(0))
            entry = ledger_by_id.get(lid)
            if entry is None:
                return f"{where}: 底账 id {m.group(0)!r}（映射后 {lid!r}）不存在"
            followed = [entry] + ([ledger_by_id.get(x) for x in entry.get("retiresInto") or []] if entry.get("status") == "retired" else [])
            if not any(e and e.get("status") in ("license_pending", "accepted_license") for e in followed):
                return f"{where}: 底账 {lid!r} status={entry.get('status')!r}，不是 license_pending/accepted_license（retiresInto 也不是）"
    return None


def load_function_scope(path):
    doc = L.load_json(path, "范围文件")
    if isinstance(doc, list):
        return {x if isinstance(x, str) else (x or {}).get("functionId") for x in doc} - {None}
    return {x if isinstance(x, str) else (x or {}).get("functionId") for x in (doc or {}).get("functionsOutOfScope", []) or []} - {None}


def run_check(doc, args):
    if not isinstance(doc, dict) or not isinstance(doc.get("threads"), list):
        raise L.InputError("功能地图缺 threads 数组")
    records, superseded_by = load_records(args.rc_dir)
    decisions_doc = L.merge_decision_docs([L.load_json(p, "决定队列") for p in args.decisions]) if args.decisions else None
    decisions = {d.get("id"): d for d in decisions_doc["entries"]} if decisions_doc else None
    ledger_by_id = L.load_ledger(args.ledger)[1] if args.ledger else None
    remap = {}
    for spec in args.ref_remap or []:
        old, sep, new = spec.partition("=")
        if not sep or not old or not new:
            raise L.InputError(f"--ref-remap 要写成 OLD=NEW：{spec!r}")
        remap[old.strip()] = new.strip()
    out_of_scope = load_function_scope(args.scope) if args.scope else set()
    v1 = args.stage == "v1"
    errors, notes, seen = [], [], {}
    counts = dict.fromkeys(("functions", "functionsSelected", "functionsDropped", "functionsOpen", "functionsOutOfScope",
                            "candidates", "candidatesSelected", "candidatesRejected"), 0)
    for thread in doc["threads"]:
        tid = thread.get("threadId", "<无 threadId>")
        for fn in thread.get("functions", []) or []:
            counts["functions"] += 1
            fid = fn.get("functionId")
            where = f"{tid}/{fid or '<无 functionId>'}"
            if not L.is_nonempty(fid):
                errors.append(f"{where}: 缺 functionId")
            elif fid in seen:
                errors.append(f"{where}: functionId 重复，已在 {seen[fid]} 出现过")
            else:
                seen[fid] = where
            status = fn.get("status")
            if status in FUNCTION_STATUSES:
                counts["functions" + status.capitalize()] += 1
            else:
                errors.append(f"{where}: status={status!r} 不是 open/selected/dropped 之一")
            if status == "dropped" and not L.is_nonempty(fn.get("droppedCost")):
                errors.append(f"{where}: status=dropped 但 droppedCost 为空")
            oos = bool(fn.get("outOfScope")) or fid in out_of_scope
            counts["functionsOutOfScope"] += oos
            if v1 and status == "open" and not oos:
                errors.append(f"{where}: --stage v1 下范围内功能不能仍是 open")
            selected, cand_ids = [], set()
            for cand in fn.get("candidates") or []:
                counts["candidates"] += 1
                cid = cand.get("candidateId")
                cwhere = f"{where}/{cid or '<无 candidateId>'}"
                if not L.is_nonempty(cid):
                    errors.append(f"{cwhere}: 缺 candidateId")
                elif cid in cand_ids:
                    errors.append(f"{cwhere}: candidateId 在本功能内重复")
                cand_ids.add(cid)
                if not L.is_nonempty(cand.get("steps")):
                    errors.append(f"{cwhere}: steps 为空")
                for j, dep in enumerate(cand.get("ledgerDeps") or []):
                    for f in ("kind", "claim"):
                        if not L.is_nonempty(dep.get(f)):
                            errors.append(f"{cwhere}/ledgerDeps[{j}]: {f} 为空")
                cstatus = cand.get("status")
                if cstatus not in CANDIDATE_STATUSES:
                    errors.append(f"{cwhere}: status={cstatus!r} 不是 candidate/selected/rejected 之一")
                if cstatus == "rejected":
                    counts["candidatesRejected"] += 1
                    if not L.is_nonempty(cand.get("rejectedBecause")):
                        errors.append(f"{cwhere}: status=rejected 但 rejectedBecause 为空")
                origin_note = origin_problem(cand)
                if origin_note:
                    (errors if v1 and cstatus == "selected" else notes).append(f"{cwhere}: {origin_note}")
                if cstatus != "selected":
                    continue
                counts["candidatesSelected"] += 1
                selected.append(cid)
                errors.extend(check_selected(cand, cwhere, fid, records, superseded_by, args, v1))
            if status == "selected" and len(selected) != 1:
                errors.append(f"{where}: status=selected 要求恰有一个 selected 候选，实际 {len(selected)} 个（{selected}）")
    if v1:
        checked = 0
        for cid, (rec, path) in records.items():
            if cid in superseded_by:
                continue
            for a in rec.get("answers", []) or []:
                if a.get("holds") == "notHolds" and a.get("loadBearing"):
                    checked += 1
                    err = disposition_error(dict(a, checkId=cid), decisions, ledger_by_id, remap)
                    if err:
                        errors.append(err)
        counts["loadBearingNotHoldsChecked"] = checked
        counts["supersededCheckIds"] = sorted(superseded_by)
        if decisions is None or ledger_by_id is None:
            notes.append("未给 --decisions 或 --ledger：disposition 对应那半的引用存在性与状态未核，只核了 to 与 ref 非空")
    return errors, notes, counts


def origin_problem(cand):
    step_origins = {s.get("origin") for s in cand.get("steps") or [] if isinstance(s, dict) and s.get("origin")}
    ranked = [o for o in step_origins if o in ORIGIN_RANK]
    if not ranked:
        return None
    top = max(ranked, key=ORIGIN_RANK.get)
    if ORIGIN_RANK.get(cand.get("origin"), -1) < ORIGIN_RANK[top]:
        return f"候选 origin={cand.get('origin')!r}，但步骤里有 {top!r}（候选级取步骤里最「用户」的那个，d6-1 决定 #4）"
    return None


def check_selected(cand, cwhere, fid, records, superseded_by, args, v1):
    errors = []
    if not v1:
        ref = cand.get("inquiryRef")
        if not L.is_nonempty(ref):
            return [f"{cwhere}: status=selected 但 inquiryRef 为空"]
        rec = records.get(ref if isinstance(ref, str) else None)
        if rec is None:
            return [f"{cwhere}: inquiryRef={ref!r} 在 --rc-dir 下找不到对应 checkId 的记录"]
        if rec[0].get("outcome") == "fail":
            errors.append(f"{cwhere}: 引用的追问单记录 outcome=fail，不能 selected")
        errors.extend(f"{cwhere}: 引用的追问单记录 answers[{k}] holds=notHolds（q={a.get('q')}），不能 selected"
                      for k, a in enumerate(rec[0].get("answers", []) or []) if a.get("holds") == "notHolds")
        return errors
    if L.is_nonempty(cand.get("losesFunctions")):
        errors.append(f"{cwhere}: status=selected 但 losesFunctions 非空，不能被系统标 selected")
    for j, dep in enumerate(cand.get("ledgerDeps") or []):
        if not L.is_nonempty(dep.get("depId")):
            errors.append(f"{cwhere}/ledgerDeps[{j}]: selected 候选的 depId 为空")
        if dep.get("assertion") not in ASSERTIONS:
            errors.append(f"{cwhere}/ledgerDeps[{j}]: assertion={dep.get('assertion')!r} 不在 {list(ASSERTIONS)}")
    if find_record(cand, records, superseded_by) is None:
        errors.append(f"{cwhere}: 找不到这个候选的追问单记录（inquiryRef 为空或不在 --rc-dir，target.id 也对不上）")
    for k, item in enumerate(cand.get("closes") or []):
        dwhere = f"{cwhere}/closes[{k}]"
        if not L.is_nonempty(item.get("defectId")):
            errors.append(f"{dwhere}: 缺 defectId")
        if not L.is_nonempty(item.get("confirmedBy")):
            errors.append(f"{dwhere}: 缺 confirmedBy（写作方的自报不作证据）")
        elif L.is_nonempty(item.get("defectId")):
            err = resolve_confirmed_by(item["confirmedBy"], item["defectId"], args.records_base)
            if err:
                errors.append(f"{dwhere}({item['defectId']}): {err}")
    return errors


def cmd_check(args):
    doc = L.load_json(args.function_map, "功能地图")
    errors, notes, counts = run_check(doc, args)
    L.emit({"ok": True, "passed": not errors, "stage": args.stage, "errors": errors, "notes": notes, "counts": counts,
            "reproduceCommand": args.reproduce})
    return 0 if not errors else 2


def cmd_merge(args):
    files = []
    for p in args.inputs:
        files.extend(sorted(glob.glob(os.path.join(p, "T-*.json"))) if os.path.isdir(p) else [p])
    if not files:
        raise L.InputError("没有找到任何线文件（T-*.json）")
    threads, sources, refused, fn_seen = [], [], [], {}
    for path in files:
        doc = L.load_json(path, "线功能地图")
        if not isinstance(doc, dict) or not L.is_nonempty(doc.get("threadId")):
            raise L.InputError(f"{path} 不是带 threadId 的线功能地图")
        threads.append(doc)
        sources.append({"threadId": doc["threadId"], "file": os.path.basename(path)})
        for fn in doc.get("functions", []) or []:
            fid = fn.get("functionId")
            if fid in fn_seen:
                refused.append(f"functionId {fid!r} 同时出现在 {fn_seen[fid]} 与 {os.path.basename(path)}")
            fn_seen[fid] = os.path.basename(path)
    tids = [t["threadId"] for t in threads]
    refused += [f"threadId {t!r} 重复" for t in sorted({t for t in tids if tids.count(t) > 1})]
    if refused:
        L.emit({"ok": True, "passed": False, "refused": refused, "written": False, "reproduceCommand": args.reproduce})
        return 2
    order = sorted(range(len(threads)), key=lambda i: threads[i]["threadId"])
    out = {**({"schema": args.schema} if args.schema else {"schemaVersion": SCHEMA}), "revision": args.revision, "sources": [sources[i] for i in order],
           "threads": [threads[i] for i in order]}
    L.write_json(args.out, out)
    L.emit({"ok": True, "passed": True, "out": args.out, "threads": len(threads), "functions": len(fn_seen), "written": True,
            "reproduceCommand": args.reproduce})
    return 0


def episodes_of(fn):
    eps = fn.get("episodesInScope")
    return list(eps if isinstance(eps, list) else fn.get("currentEpisodes") or [])


def cmd_topics(args):
    doc = L.load_json(args.function_map, "功能地图")
    topics, index = [], {}
    for thread, fn, cand in L.iter_candidates(doc):
        if cand.get("status") == "rejected" and not args.include_rejected:
            continue
        for dep in cand.get("ledgerDeps") or []:
            if dep.get("kind") != "procedure" and dep.get("assertion") != "required_unstated":
                continue
            key = ("entry", dep["entryId"]) if L.is_nonempty(dep.get("entryId")) else ("claim", L.normalize_title(dep.get("claim")))
            topic = index.get(key)
            if topic is None:
                topic = {"topicId": f"Q-{len(topics) + 1:03d}", "entryId": dep.get("entryId"), "kinds": [], "assertions": [],
                         "claims": [], "depIds": [], "functions": [], "candidates": [], "episodes": []}
                index[key] = topic
                topics.append(topic)
            for field, value in (("kinds", dep.get("kind")), ("assertions", dep.get("assertion") or "unmarked"),
                                 ("claims", dep.get("claim")), ("depIds", dep.get("depId")),
                                 ("functions", fn.get("functionId")), ("candidates", cand.get("candidateId"))):
                if L.is_nonempty(value) and value not in topic[field]:
                    topic[field].append(value)
            for ep in episodes_of(fn):
                if ep not in topic["episodes"]:
                    topic["episodes"].append(ep)
    for t in topics:
        t["episodes"].sort(key=lambda e: L.ep_key(e) or (10 ** 9, str(e)))
    L.emit({"ok": True, "topics": topics, "counts": {"topics": len(topics), "fromEntry": sum(1 for t in topics if t["entryId"]),
                                                       "fromClaimOnly": sum(1 for t in topics if not t["entryId"])},
            "note": "只归并，不检索；同一底账条目归一题，没有 entryId 的按断言文字归并", "reproduceCommand": args.reproduce})
    return 0


def normalize_disposition(disp):
    if not isinstance(disp, dict) or not L.is_nonempty(disp.get("to")):
        return None
    return {"to": DISPOSITION_TO.get(disp["to"], disp["to"]), "rawTo": disp["to"], "ref": disp.get("ref"),
            **{k: disp[k] for k in ("decision", "default", "status", "via") if k in disp}}


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def cmd_defects_build(args):
    """Register shape follows schemas/defect-register: defectId (the answers' defectKey, else
    checkId#q), title (first landsOn), loadBearing, loadBearingBasis (enum values only; free-text
    reasons go to loadBearingWhy), records, disposition (one object when the records agree, "open"
    when a load-bearing gap has none, "conflicting" plus dispositions[] when they disagree)."""
    records, superseded_by = load_records(args.records)
    defects, order = {}, []
    for cid, (rec, path) in sorted(records.items()):
        if cid in superseded_by:
            continue
        for a in rec.get("answers", []) or []:
            if a.get("holds") != "notHolds":
                continue
            key = a.get("defectKey") or f"{cid}#q{a.get('q')}"
            d = defects.get(key)
            if d is None:
                d = defects[key] = {"defectId": key, "title": a.get("landsOn") or key, "defectKind": [], "loadBearing": False,
                                    "loadBearingBasis": [], "loadBearingWhy": [], "dispositions": [], "records": []}
                order.append(key)
            for kind in as_list(a.get("defectKind")):
                if kind not in d["defectKind"]:
                    d["defectKind"].append(kind)
            if a.get("loadBearing"):
                d["loadBearing"] = True
                for basis in as_list(a.get("loadBearingBasis")) + as_list(a.get("loadBearingWhy")):
                    slot = d["loadBearingBasis"] if basis in LOAD_BEARING_BASIS else d["loadBearingWhy"]
                    if L.is_nonempty(basis) and basis not in slot:
                        slot.append(basis)
            disp = normalize_disposition(a.get("disposition"))
            if disp and disp not in d["dispositions"]:
                d["dispositions"].append(disp)
            d["records"].append({"checkId": cid, "q": a.get("q"), "landsOn": a.get("landsOn"), "loadBearing": bool(a.get("loadBearing")),
                                 "inheritedFrom": a.get("inheritedFrom"), "patch": a.get("patch"), "file": os.path.basename(path)})
    out_defects = []
    for key in order:
        d = defects[key]
        dispositions = d.pop("dispositions")
        if len({x["to"] for x in dispositions}) > 1:
            d["disposition"], d["dispositions"] = "conflicting", dispositions
        elif dispositions:
            d["disposition"] = dispositions[0] if len(dispositions) == 1 else dict(dispositions[0], alsoRegisteredAs=dispositions[1:])
        else:
            d["disposition"] = "open" if d["loadBearing"] else {"to": "leaves_open", "ref": None}
        d["loadBearingWhy"] = "；".join(d["loadBearingWhy"]) or None
        out_defects.append(d)
    counts = {"defects": len(out_defects), "loadBearing": sum(d["loadBearing"] for d in out_defects),
              "loadBearingOpen": sum(d["disposition"] == "open" for d in out_defects),
              "conflictingDispositions": sum(d["disposition"] == "conflicting" for d in out_defects),
              "notHoldsAnswers": sum(len(d["records"]) for d in out_defects), "supersededCheckIds": sorted(superseded_by)}
    register = {"schemaVersion": DEFECTS_SCHEMA, "generatedBy": "function-map defects build", "basedOn": sorted(records),
                "defects": out_defects, "counts": counts}
    if args.out:
        L.write_json(args.out, register)
    L.emit({"ok": True, "out": args.out, **({"counts": counts} if args.out else register), "reproduceCommand": args.reproduce})
    return 0


def build_parser(prog=None):
    ap = argparse.ArgumentParser(prog=prog, description="功能地图：check / merge / topics / defects build")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("function_map")
    p.add_argument("--stage", choices=("v0", "v1"), default="v0")
    p.add_argument("--rc-dir", "--rc-extra-dir", dest="rc_dir", action="append", default=[], help="追问单回答记录目录，可给多个")
    p.add_argument("--decisions", action="append", default=[])
    p.add_argument("--ledger", default=None)
    p.add_argument("--records-base", default=".", help="closes[].confirmedBy 相对路径的基准目录")
    p.add_argument("--scope", default=None, help="范围文件（functionsOutOfScope[]）或 functionId 列表")
    p.add_argument("--ref-remap", action="append", default=[], help="OLD=NEW：disposition 引用的旧底账 id 换成新 id 再核")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("merge")
    p.add_argument("inputs", nargs="+", help="线文件或目录（目录取 T-*.json）")
    p.add_argument("--out", required=True)
    p.add_argument("--revision", default="v0")
    p.add_argument("--schema", default=None, help="沿用旧产物的 schema 标记（如 function-map/v0-pilot）；不给就写 schemaVersion")
    p.set_defaults(func=cmd_merge)
    p = sub.add_parser("topics")
    p.add_argument("function_map")
    p.add_argument("--include-rejected", action="store_true")
    p.set_defaults(func=cmd_topics)
    p = sub.add_parser("defects")
    dsub = p.add_subparsers(dest="defects_cmd", required=True)
    b = dsub.add_parser("build")
    b.add_argument("--records", action="append", required=True, help="回答记录目录或文件，可给多个")
    b.add_argument("--out", default=None)
    b.set_defaults(func=cmd_defects_build)
    return ap


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser(prog).parse_args(argv)
    args.reproduce = L.reproduce_command(__file__, argv)
    try:
        return args.func(args)
    except (L.InputError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
