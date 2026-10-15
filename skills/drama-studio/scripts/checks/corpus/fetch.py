"""`corpus fetch` -- bookkeeping for reading corpus episodes from mali-story (plan §4.5; D6-4 decisions §1).

The script never goes online: the agent calls the mali-story tools and saves each response; this command keeps the
ledger around those calls so a read can be planned, resumed after a break, checked against the snapshot it was planned
for, and watched for charges.

  plan    <templates.json> --out <ledger.json> [--series 3] [--episodes-per-series 10]
          a ledger for the pilot read: the first N series, M episodes each (sorted), each with its expected
          snapshotId when the template listing gave one. Never overwrites a ledger.
  record  <ledger.json> --template T --episode N --response <saved response.json> [--tool NAME]
          one call: ok, or failed when the response is missing/unreadable or carries an error; the snapshotId the
          response reports is compared with the expected one (snapshot_mismatch). Appends; attempts are counted.
  budget  <ledger.json> --label before|after|<any> --reading <saved get_shared_creation_budget response>
          [--receipts <saved list_shared_creation_budget_receipts response>]
          a budget reading and the receipt ids seen at that moment. Appends.
  resume  <ledger.json>   the break list: items not yet read, failed ones to retry (fewer than --max-attempts), and
                          ones given up on. Read-only.
  verify  <ledger.json>   billing between the first and the last reading -- deduction_seen (credits went down or a
                          new receipt id appeared), no_change_seen (both readable and equal), or unconfirmed (a
                          reading is missing, unconfigured or null) -- plus snapshot mismatches and call counts. The
                          observation block (calls, readings, receipt ids) is what docs/d6 may carry. Read-only.

Exit codes: 0 done; 1 input error (or a ledger that would be overwritten); 2 verify saw a deduction or a snapshot
mismatch (stop and record; the read must not go on to the whole library).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys

SCHEMA = "drama-studio/corpus-fetch-ledger/v0"
MAX_ATTEMPTS = 3


class InputError(ValueError):
    pass


def _load(path, what):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise InputError(f"找不到{what}：{path}") from None
    except ValueError as error:
        raise InputError(f"{what}不是合法 JSON：{path}: {error}") from None


def _write(path, doc):
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)


def _ledger(path):
    doc = _load(path, "取用台账")
    if not isinstance(doc, dict) or doc.get("schemaVersion") != SCHEMA:
        raise InputError(f"{path} 不是 {SCHEMA} 台账")
    return doc


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _find(value, *keys):
    """The first of keys found in value or one level down (MCP responses wrap payloads in data/result)."""
    if not isinstance(value, dict):
        return None
    for key in keys:
        if key in value:
            return value[key]
    for wrapper in ("data", "result", "structuredContent"):
        inner = value.get(wrapper)
        if isinstance(inner, dict):
            found = _find(inner, *keys)
            if found is not None:
                return found
    return None


def cmd_plan(args):
    if os.path.exists(args.out):
        raise InputError(f"{args.out} 已存在；台账只追加，不重建")
    templates = _load(args.templates, "模板清单")
    templates = templates.get("templates") if isinstance(templates, dict) else templates
    if not isinstance(templates, list) or not templates:
        raise InputError("模板清单要是数组（或 {templates: [...]}），每项 {templateId, episodes 或 episodesTotal}")
    items = []
    for template in templates[:args.series]:
        episodes = template.get("episodes") or list(range(1, int(template.get("episodesTotal") or 0) + 1))
        snapshots = template.get("snapshotIds") or {}
        for episode in sorted(int(e) for e in episodes)[:args.episodes_per_series]:
            items.append({"templateId": template["templateId"], "episodeIndex": episode,
                          "expectedSnapshotId": snapshots.get(str(episode)) or template.get("snapshotId")})
    doc = {"schemaVersion": SCHEMA, "createdAt": _now(),
           "plan": {"series": min(args.series, len(templates)), "episodesPerSeries": args.episodes_per_series, "items": items,
                    "rule": "先取 3 部各 10 集，看预算与回执；有扣费迹象即停并记录，计费未确认前不取全库（计划 §4.5）"},
           "calls": [], "budget": []}
    _write(args.out, doc)
    return {"ok": True, "ledger": args.out, "items": len(items)}, 0


def cmd_record(args):
    doc = _ledger(args.ledger)
    item = next((i for i in doc["plan"]["items"] if i["templateId"] == args.template and i["episodeIndex"] == args.episode), None)
    if item is None:
        raise InputError(f"台账的取用计划里没有 {args.template} 第 {args.episode} 集")
    try:
        with open(args.response, "rb") as handle:
            data = handle.read()
        response = json.loads(data.decode("utf-8"))
        error = _find(response, "error", "errorCode")
        outcome = "failed" if error else "ok"
    except (OSError, ValueError):
        data, response, error, outcome = b"", None, "response missing or unreadable", "failed"
    observed = _find(response, "snapshotId", "snapshot_id") if response is not None else None
    expected = item.get("expectedSnapshotId")
    attempt = 1 + sum(c["templateId"] == args.template and c["episodeIndex"] == args.episode for c in doc["calls"])
    call = {"callId": f"C{len(doc['calls']) + 1:04d}", "at": _now(), "tool": args.tool, "templateId": args.template,
            "episodeIndex": args.episode, "attempt": attempt, "outcome": outcome, "error": str(error) if error else None,
            "snapshotId": observed, "expectedSnapshotId": expected,
            "snapshotCheck": "not_evaluable" if not expected or outcome != "ok" else ("match" if observed == expected else "snapshot_mismatch"),
            "responseSha256": "sha256:" + hashlib.sha256(data).hexdigest() if data else None}
    doc["calls"].append(call)
    _write(args.ledger, doc)
    return {"ok": True, "call": call}, 0


def _receipt_ids(response):
    found = _find(response, "receipts", "items")
    return sorted({str(r.get("receiptId") or r.get("id")) for r in found if isinstance(r, dict) and (r.get("receiptId") or r.get("id"))}) \
        if isinstance(found, list) else []


def cmd_budget(args):
    doc = _ledger(args.ledger)
    reading = _load(args.reading, "预算读数")
    receipts = _load(args.receipts, "回执列表") if args.receipts else None
    credits = _find(reading, "availableCredits")
    entry = {"label": args.label, "at": _now(), "budgetMode": _find(reading, "budgetMode"),
             "availableCredits": credits if isinstance(credits, (int, float)) and not isinstance(credits, bool) else None,
             "receiptIds": _receipt_ids(receipts) if receipts is not None else None,
             "readingSha256": "sha256:" + hashlib.sha256(json.dumps(reading, sort_keys=True).encode("utf-8")).hexdigest()}
    doc["budget"].append(entry)
    _write(args.ledger, doc)
    return {"ok": True, "reading": entry}, 0


def _status(doc, max_attempts):
    pending, retry, given_up, done = [], [], [], []
    for item in doc["plan"]["items"]:
        calls = [c for c in doc["calls"] if c["templateId"] == item["templateId"] and c["episodeIndex"] == item["episodeIndex"]]
        key = {"templateId": item["templateId"], "episodeIndex": item["episodeIndex"]}
        if any(c["outcome"] == "ok" for c in calls):
            done.append(key)
        elif not calls:
            pending.append(key)
        elif len(calls) < max_attempts:
            retry.append(dict(key, attempts=len(calls)))
        else:
            given_up.append(dict(key, attempts=len(calls)))
    return pending, retry, given_up, done


def cmd_resume(args):
    doc = _ledger(args.ledger)
    pending, retry, given_up, done = _status(doc, args.max_attempts)
    return {"ok": True, "done": len(done), "pending": pending, "retry": retry, "givenUp": given_up,
            "next": (pending + retry)[:1]}, 0


def billing(readings):
    """deduction_seen | no_change_seen | unconfirmed, between the first and the last budget reading."""
    if len(readings) < 2:
        return "unconfirmed", "要有取用前、取用后两次预算读数"
    first, last = readings[0], readings[-1]
    new_receipts = sorted(set(last.get("receiptIds") or []) - set(first.get("receiptIds") or []))
    a, b = first.get("availableCredits"), last.get("availableCredits")
    if new_receipts or (a is not None and b is not None and b < a):
        return "deduction_seen", f"可用额度 {a} → {b}，新回执 {new_receipts}"
    if a is None or b is None or "unconfigured" in (first.get("budgetMode"), last.get("budgetMode")):
        return "unconfirmed", f"预算读数不可比（budgetMode {first.get('budgetMode')} → {last.get('budgetMode')}，额度 {a} → {b}）；看不出扣费，也不能证明没扣"
    return "no_change_seen", f"可用额度 {a} → {b}，没有新回执"


def cmd_verify(args):
    doc = _ledger(args.ledger)
    pending, retry, given_up, done = _status(doc, args.max_attempts)
    state, why = billing(doc["budget"])
    mismatches = [c for c in doc["calls"] if c["snapshotCheck"] == "snapshot_mismatch"]
    receipts = sorted({r for reading in doc["budget"] for r in reading.get("receiptIds") or []})
    result = {"ok": True, "passed": state != "deduction_seen" and not mismatches, "billing": state, "billingWhy": why,
              "snapshotMismatches": [{k: c[k] for k in ("callId", "templateId", "episodeIndex", "expectedSnapshotId", "snapshotId")}
                                     for c in mismatches],
              "observation": {"calls": len(doc["calls"]), "callsOk": sum(c["outcome"] == "ok" for c in doc["calls"]),
                              "callsFailed": sum(c["outcome"] == "failed" for c in doc["calls"]),
                              "budgetReadings": [{k: r.get(k) for k in ("label", "budgetMode", "availableCredits")} for r in doc["budget"]],
                              "receiptIds": receipts},
              "items": {"planned": len(doc["plan"]["items"]), "done": len(done), "pending": len(pending), "retry": len(retry),
                        "givenUp": len(given_up)},
              "stop": "有扣费迹象或快照不符：停，记录，不取全库" if state == "deduction_seen" or mismatches else None}
    return result, 0 if result["passed"] else 2


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog=prog, description="语料取用记账：计划、断点、快照核对、预算与回执比对；不联网")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("templates")
    p.add_argument("--out", required=True)
    p.add_argument("--series", type=int, default=3)
    p.add_argument("--episodes-per-series", type=int, default=10)
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser("record")
    p.add_argument("ledger")
    p.add_argument("--template", required=True)
    p.add_argument("--episode", type=int, required=True)
    p.add_argument("--response", required=True)
    p.add_argument("--tool", default="get_deconstruction_evidence")
    p.set_defaults(func=cmd_record)
    p = sub.add_parser("budget")
    p.add_argument("ledger")
    p.add_argument("--label", required=True)
    p.add_argument("--reading", required=True)
    p.add_argument("--receipts")
    p.set_defaults(func=cmd_budget)
    for name, func in (("resume", cmd_resume), ("verify", cmd_verify)):
        p = sub.add_parser(name)
        p.add_argument("ledger")
        p.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        result, code = args.func(args)
    except (InputError, OSError, KeyError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
