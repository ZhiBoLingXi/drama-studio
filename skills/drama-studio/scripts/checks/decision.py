"""decision: the decision queue — things that wait for a person while the flow goes on by default.

  add <queue> --from-handoff <run-handoff.json>   register the handoff's changeProposals that need
        a decision; each must name its `default` (an optionId of its own `options[]`, or apply/keep
        when it gives none) — one without a default refuses the whole add and nothing is written
  add <queue> --entry <entry.json>                 register one prepared entry
  list <queue> [--status pending|decided]
  decide <queue> --id <id> --option <optionId> --human-words <the person's own words>
        only a record carrying the person's words is accepted; the tool never decides
  check <queue>                                    the queue rules below

check: unique ids; kind ∈ setting_conflict / premise / license / capacity / upstream_change / other;
optionIds unique per entry; default names an existing option; the default option loses no function
sentence (losesFunctions empty, or a "not_evaluable..." placeholder for an unchecked out-of-scope
option) — the system never deletes a function by default; status ∈ pending / decided; a decided
entry has humanWords and its chosen option exists.

add and decide write only the named queue file (created by add when missing). Never goes online
or calls a model. Exit codes: 0 completed / rules hold; 1 input error; 2 refused or a rule failed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from . import ledger as L
except ImportError:  # run as a script
    import ledger as L

SCHEMA = "drama-studio/decision-queue/v0"
KINDS = ("setting_conflict", "premise", "license", "capacity", "upstream_change", "other")
STATUSES = ("pending", "decided")
SYNTH_OPTIONS = ("apply", "keep")


def loses_functions_ok(value):
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.startswith("not_evaluable")
    return False


def entry_errors(entry, where):
    errors = []
    eid = entry.get("id")
    if not L.is_nonempty(eid):
        errors.append(f"{where}: 缺 id")
    if entry.get("kind") not in KINDS:
        errors.append(f"{where}({eid}): kind={entry.get('kind')!r} 不在词表 {list(KINDS)} 内")
    options = entry.get("options") or []
    option_ids = []
    for i, opt in enumerate(options):
        oid = (opt or {}).get("optionId")
        if not L.is_nonempty(oid):
            errors.append(f"{where}({eid})/options[{i}]: 缺 optionId")
        elif oid in option_ids:
            errors.append(f"{where}({eid})/options[{i}]: optionId {oid!r} 重复")
        option_ids.append(oid)
    default = entry.get("default")
    if not L.is_nonempty(default):
        errors.append(f"{where}({eid}): default 为空")
    elif default not in option_ids:
        errors.append(f"{where}({eid}): default={default!r} 不在 options 的 optionId 里")
    elif not loses_functions_ok(options[option_ids.index(default)].get("losesFunctions")):
        errors.append(f"{where}({eid}): default 选项 {default!r} 的 losesFunctions 非空，默认走法不能让功能句落空")
    status = entry.get("status", "pending")
    if status not in STATUSES:
        errors.append(f"{where}({eid}): status={status!r} 不是 pending/decided")
    if status == "decided":
        if not L.is_nonempty(entry.get("humanWords")):
            errors.append(f"{where}({eid}): status=decided 但没有 humanWords（只认人的原话）")
        if entry.get("decision") not in option_ids:
            errors.append(f"{where}({eid}): status=decided 但 decision={entry.get('decision')!r} 不在 options 里")
    return errors


def queue_errors(doc):
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise L.InputError("决定队列缺 entries 数组")
    errors, seen = [], set()
    for i, entry in enumerate(entries):
        where = f"entries[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: 不是对象")
            continue
        if L.is_nonempty(entry.get("id")):
            if entry["id"] in seen:
                errors.append(f"{where}: id {entry['id']!r} 重复")
            seen.add(entry["id"])
        errors.extend(entry_errors(entry, where))
    return errors


def load_queue(path, create=False):
    if create and not os.path.exists(path):
        return {"schemaVersion": SCHEMA, "entries": []}
    doc = L.load_json(path, "决定队列")
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        raise L.InputError(f"决定队列缺 entries 数组：{path}")
    return doc


def refs_to_affects(refs):
    out = []
    for ref in refs or []:
        if isinstance(ref, dict):
            out.append(ref.get("id") or ref.get("path") or json.dumps(ref, ensure_ascii=False))
        elif L.is_nonempty(ref):
            out.append(ref)
    return out


def entries_from_handoff(handoff, existing_ids):
    """(entries, refused, skipped). A proposal must carry `default`; without its own options it gets
    apply (= proposedChange) / keep, and default must be one of those."""
    run_id = handoff.get("runId") or "run"
    entries, refused, skipped = [], [], []
    taken = set(existing_ids)
    for i, prop in enumerate(handoff.get("changeProposals") or []):
        where = f"changeProposals[{i}]"
        if not isinstance(prop, dict):
            refused.append(f"{where}: 不是对象")
            continue
        if prop.get("needsDecision") is False:
            skipped.append(f"{where}: needsDecision=false，不进决定队列")
            continue
        options = prop.get("options")
        if not L.is_nonempty(options):
            options = [{"optionId": "apply", "text": prop.get("proposedChange")}, {"optionId": "keep", "text": "保持现状"}]
        missing = [f for f in ("default", "defaultReason", "problem") if not L.is_nonempty(prop.get(f))]
        if missing:
            refused.append(f"{where}: 缺 {missing}（提出决定的人必须给默认走法和理由）")
            continue
        eid = prop.get("decisionId") or f"DQ-{run_id}-{i + 1}"
        if eid in taken:
            refused.append(f"{where}: id {eid!r} 已在队列里")
            continue
        taken.add(eid)
        entry = {"id": eid, "kind": prop.get("kind") or "upstream_change",
                 "raisedAt": {"layer": prop.get("targetLayer"), "runId": handoff.get("runId"), "workstation": handoff.get("workstation")},
                 "question": prop.get("problem"), "options": options, "default": prop["default"],
                 "defaultReason": prop.get("defaultReason"), "affects": refs_to_affects(prop.get("affected")),
                 "evidence": prop.get("evidence"), "unknownScope": prop.get("unknownScope"), "status": "pending", "humanWords": None}
        problems = entry_errors(entry, where)
        if problems:
            refused.extend(problems)
            taken.discard(eid)
        else:
            entries.append(entry)
    return entries, refused, skipped


def cmd_add(args):
    doc = load_queue(args.queue, create=True)
    existing = [e.get("id") for e in doc["entries"]]
    if args.from_handoff:
        new, refused, skipped = entries_from_handoff(L.load_json(args.from_handoff, "run-handoff"), existing)
    else:
        entry = L.load_json(args.entry, "决定条目")
        if not isinstance(entry, dict):
            raise L.InputError("决定条目不是 JSON 对象")
        entry = dict({"status": "pending", "humanWords": None}, **entry)
        refused = entry_errors(entry, "entry") + ([f"entry: id {entry.get('id')!r} 已在队列里"] if entry.get("id") in existing else []) \
            + [f"entry: 缺 {f}" for f in ("question", "defaultReason") if not L.is_nonempty(entry.get(f))]
        new, skipped = ([] if refused else [entry]), []
    if refused:
        L.emit({"ok": True, "passed": False, "added": [], "refused": refused, "skipped": skipped, "written": False,
                "reproduceCommand": args.reproduce})
        return 2
    doc["entries"].extend(new)
    if new:
        L.write_json(args.queue, doc)
    L.emit({"ok": True, "passed": True, "added": [e["id"] for e in new], "refused": [], "skipped": skipped, "written": bool(new),
            "reproduceCommand": args.reproduce})
    return 0


def cmd_list(args):
    doc = load_queue(args.queue)
    rows = [{"id": e.get("id"), "kind": e.get("kind"), "status": e.get("status", "pending"), "question": e.get("question"),
             "default": e.get("default"), "decision": e.get("decision"), "affects": e.get("affects", [])}
            for e in doc["entries"] if args.status is None or e.get("status", "pending") == args.status]
    L.emit({"ok": True, "total": len(doc["entries"]), "listed": len(rows), "entries": rows, "reproduceCommand": args.reproduce})
    return 0


def cmd_decide(args):
    doc = load_queue(args.queue)
    refused = []
    if not L.is_nonempty(args.human_words):
        refused.append("没有 --human-words：只接受带人的原话的决定记录")
    entry = next((e for e in doc["entries"] if e.get("id") == args.id), None)
    if entry is None:
        refused.append(f"队列里没有 {args.id!r}")
    elif args.option not in [o.get("optionId") for o in entry.get("options") or []]:
        refused.append(f"{args.id}: {args.option!r} 不在 options 里")
    elif entry.get("status") == "decided":
        refused.append(f"{args.id}: 已经 decided（{entry.get('decision')}），不覆盖；改主意请另记一条")
    if refused:
        L.emit({"ok": True, "passed": False, "refused": refused, "written": False, "reproduceCommand": args.reproduce})
        return 2
    entry.update({"status": "decided", "decision": args.option, "humanWords": args.human_words,
                  "decidedBy": args.decided_by, "decidedAt": args.decided_at})
    L.write_json(args.queue, doc)
    L.emit({"ok": True, "passed": True, "decided": args.id, "decision": args.option, "written": True,
            "affects": entry.get("affects", []), "reproduceCommand": args.reproduce})
    return 0


def cmd_check(args):
    doc = load_queue(args.queue)
    errors = queue_errors(doc)
    L.emit({"ok": True, "passed": not errors, "total": len(doc["entries"]), "errors": errors, "reproduceCommand": args.reproduce})
    return 0 if not errors else 2


def build_parser(prog=None):
    ap = argparse.ArgumentParser(prog=prog, description="决定队列：add / list / decide / check")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("queue")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-handoff")
    src.add_argument("--entry")
    p.set_defaults(func=cmd_add)
    p = sub.add_parser("list")
    p.add_argument("queue")
    p.add_argument("--status", choices=STATUSES, default=None)
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("decide")
    p.add_argument("queue")
    p.add_argument("--id", required=True)
    p.add_argument("--option", required=True)
    p.add_argument("--human-words", required=True, help="人的原话（主创怎么说的就怎么记）")
    p.add_argument("--decided-by", default=None)
    p.add_argument("--decided-at", default=None)
    p.set_defaults(func=cmd_decide)
    p = sub.add_parser("check")
    p.add_argument("queue")
    p.set_defaults(func=cmd_check)
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
