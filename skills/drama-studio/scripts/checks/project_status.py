"""Rebuild the next step and mark stale execution dependencies from a project's local records.

`status` and `impact` only read `<project>/.drama/` (receipts, cache manifest, snapshots, runs): no writes, no lock
files, no network, no model, no chat history. Passing proves only what those files record. `status` repeats what the
records say is next; it does not judge whether that step is right. `stale` means a snapshot pins an older revision of
the target slot through a manifest entry whose slot a get record or a save receipt vouches for; `current` means no
recorded execution dependency points at an older revision of that slot. Content-level implicit dependencies are never
assessed, anything uncertain is `unknown`, and nothing here proves remote state or adoption.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .contract_check import check_contract
from .receipt import MANIFEST, area, contained, drama_dir, pending, slot_rank

NOTE = "current 只表示没有记录在案的执行依赖指向该 slot 的旧修订；内容层面的隐含依赖未评估。工具只读，不自动重跑运行，也不改写正文。"
OPEN_RUNS = ("planned", "running", "interrupted")
BASIS = {"unknown_receipt": "有结果未知、尚未对账的保存回执", "invalid_record": "有无效或损坏的本地记录",
         "latest_run": "最近一次运行记录的 nextAction", "no_runs": ".drama/runs/ 中没有有效的运行记录"}
WIDEN = "扩大阅读：本地记录无法判定，请重读该 slot 的最新修订和这份记录实际装入的材料，再决定是否重跑；不要当作未受影响。"


def _load(path: Path, drama: Path, contract: str, id_key: str) -> tuple[object, bytes | None, list[str]]:
    """Return (document, bytes, problems). A bad record is reported, never raised, so it cannot hide the others."""
    try:
        data = contained(path, drama).read_bytes()
        doc = json.loads(data.decode("utf-8"))
    except (OSError, ValueError) as error:
        return None, None, [f"{path.name} 无法读取或不是 UTF-8 JSON：{error}"]
    problems = [f"contract-check {contract}: {error}" for error in check_contract(contract, doc)]
    if not problems and doc[id_key] != path.stem:
        problems.append(f"文件名与 {id_key} {doc[id_key]!r} 不一致")
    return doc, data, problems


def _records(drama: Path, name: str, contract: str, id_key: str) -> list[dict]:
    folder = area(drama, name)
    items = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        doc, data, problems = _load(path, drama, contract, id_key)
        items.append({"id": path.stem, "path": f".drama/{name}/{path.name}", "file": path, "doc": doc, "data": data, "problems": problems})
    return items


def _snapshots(drama: Path) -> list[dict]:
    """Every snapshot with its integrity problems: contract-check, file name, and the .sha256 sidecar against the bytes."""
    items = _records(drama, "snapshots", "context-snapshot", "snapshotId")
    for item in items:
        if item["data"] is None:
            continue
        sidecar, digest = item["file"].with_suffix(".sha256"), hashlib.sha256(item["data"]).hexdigest()
        try:
            recorded = contained(sidecar, drama).read_text(encoding="utf-8").split()[:1] if sidecar.is_file() else None
        except (OSError, ValueError) as error:
            item["problems"].append(f"{sidecar.name} 无法读取：{error}")
            continue
        if recorded is None:
            item["problems"].append(f"缺少 {sidecar.name}，无法核对快照字节")
        elif recorded != [digest]:
            item["problems"].append(f"{sidecar.name} 记录的哈希与文件字节（{digest[:12]}…）不符：快照写入后被改动")
    return items


def _entries(drama: Path) -> list[dict]:
    path = contained(area(drama, "cache") / "manifest.json", drama)
    if not path.is_file():
        return []
    try:
        manifest = json.loads(path.read_bytes().decode("utf-8"))
    except ValueError as error:
        raise ValueError(f"cache manifest {path} 不是有效的 UTF-8 JSON（{error}）；无法判定任何依赖") from error
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != MANIFEST or not isinstance(manifest.get("entries"), list):
        raise ValueError(f"cache manifest {path} 不是 {MANIFEST} 对象；无法判定任何依赖")
    return [entry for entry in manifest["entries"] if isinstance(entry, dict)]


def _identity(entries: list[dict], artifact_id) -> tuple[tuple[str, int] | None, str | None]:
    """Return ((slot, revision), None) when the manifest pins one trusted slot and revision for the artifact, else (None, why)."""
    found = [entry for entry in entries if entry.get("artifactId") == artifact_id]
    if not found:
        return None, "manifest 中查不到该 artifactId，无法得知它属于哪个 slot"
    if len({(repr(entry.get("slot")), repr(entry.get("revision"))) for entry in found}) > 1:
        return None, "manifest 中该 artifactId 对应多个不同的 slot 或 revision"
    slot, revision = found[0].get("slot"), found[0].get("revision")
    if not isinstance(slot, str) or not slot or type(revision) is not int:
        return None, "manifest 条目没有有效的 slot 或整数 revision"
    if max(map(slot_rank, found)) == 0:  # host, or an entry written before slotSource existed
        return None, "manifest 条目的 slot 只是宿主声明（slotSource 为 host 或缺该字段）；用 get_story_artifact 响应重新缓存后才能判定"
    return (slot, revision), None


def judge_ref(ref, entries: list[dict], slot: str, revision: int) -> tuple[str, str | None]:
    """Classify one remote_artifact reference against the target slot revision; current only when trusted and clearly not older."""
    if not isinstance(ref, dict):
        return "unknown", "引用不是对象"
    identity, why = _identity(entries, ref.get("id"))
    if identity is None:
        return "unknown", why
    pinned = ref.get("revision")
    if type(pinned) is not int:
        return "unknown", "引用缺少整数 revision，无法判断新旧"
    if pinned != identity[1]:
        return "unknown", f"引用的 revision {pinned} 与 manifest 记录的 r{identity[1]} 不一致"
    if identity[0] == slot and pinned < revision:
        return "stale", f"引用了 slot {slot} 的旧修订 r{pinned}，目标修订为 r{revision}"
    return "current", None


def _verdict(result: dict, reasons: list[dict]) -> dict:
    status = next((name for name in ("stale", "unknown") if any(reason["status"] == name for reason in reasons)), "current")
    result.update(status=status, reasons=reasons)
    if status == "unknown":
        result["suggestion"] = WIDEN
    return result


def _judge_snapshot(item: dict, entries: list[dict], slot: str, revision: int) -> dict:
    result = {"snapshotId": item["id"], "path": item["path"]}
    if item["problems"]:
        return _verdict(result, [{"ref": None, "status": "unknown", "reason": "快照未通过完整性检查：" + problem} for problem in item["problems"]])
    reasons = []
    for index, packed in enumerate(item["doc"]["items"]):  # omitted entries never entered the context, so they are not dependencies
        ref = packed["ref"]
        if ref["kind"] != "remote_artifact":
            continue
        status, why = judge_ref(ref, entries, slot, revision)
        if status != "current":
            pinned = f"@r{ref['revision']}" if type(ref["revision"]) is int else ""
            reasons.append({"ref": f"items[{index}] {ref['id']}{pinned}", "status": status, "reason": why})
    return _verdict(result, reasons)


def _judge_run(item: dict, snapshots: dict[str, dict]) -> dict:
    result = {"runId": item["id"], "path": item["path"], "contextSnapshotId": None}
    if item["problems"]:
        return _verdict(result, [{"ref": None, "status": "unknown", "reason": "运行记录无效：" + problem} for problem in item["problems"]])
    result["contextSnapshotId"] = snapshot_id = item["doc"]["contextSnapshotId"]
    snapshot, ref = snapshots.get(snapshot_id), f"context_snapshot {snapshot_id}"
    if snapshot is None:
        return _verdict(result, [{"ref": ref, "status": "unknown", "reason": "所依赖的快照不在 .drama/snapshots/ 中"}])
    if snapshot["status"] == "current":
        return _verdict(result, [])
    return _verdict(result, [{"ref": ref, "status": snapshot["status"], "reason": f"所依赖的快照为 {snapshot['status']}"}, *snapshot["reasons"]])


def _count(items: list[dict]) -> dict:
    return {name: sum(item["status"] == name for item in items) for name in ("stale", "unknown", "current")}


def run_impact(project: str, slot: str | None = None, revision: int | None = None, artifact: str | None = None) -> dict:
    """Mark every snapshot and run stale, unknown or current against one slot revision. Read-only."""
    drama = drama_dir(project)
    if not ((artifact is None and slot is not None and revision is not None) or (artifact is not None and slot is None and revision is None)):
        raise ValueError("给出 --slot 与 --revision 两者，或只给 --artifact；两组互斥，也不能只给一半")
    if artifact is None and (type(revision) is not int or revision < 1):
        raise ValueError("--revision 必须是不小于 1 的整数")
    entries = _entries(drama)
    resolved = "--slot/--revision"
    if artifact is not None:
        identity, why = _identity(entries, artifact)
        if identity is None:
            raise ValueError(f"--artifact {artifact} 无法解析出可信的 slot 与 revision：{why}。"
                             "请用它的 get_story_artifact 响应重新缓存（receipt cache），或显式给出 --slot 与 --revision")
        (slot, revision), resolved = identity, f"--artifact {artifact}"
    snapshots = [_judge_snapshot(item, entries, slot, revision) for item in _snapshots(drama)]
    by_id = {item["snapshotId"]: item for item in snapshots}
    runs = [_judge_run(item, by_id) for item in _records(drama, "runs", "run-handoff", "runId")]
    return {"ok": True, "command": "impact", "project": str(drama.parent), "target": {"slot": slot, "revision": revision, "resolvedFrom": resolved},
            "snapshots": snapshots, "runs": runs, "summary": {"snapshots": _count(snapshots), "runs": _count(runs)},
            "note": NOTE, "read_only": True, "remote_verified": False}


def _run_summary(item: dict) -> dict:
    doc = item["doc"]
    modified = datetime.fromtimestamp(item["file"].stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return {"runId": doc["runId"], "path": item["path"], "taskId": doc["taskId"], "workstation": doc["workstation"],
            "contextSnapshotId": doc["contextSnapshotId"], "status": doc["status"], "unfinished": doc["unfinished"],
            "nextAction": doc["nextAction"], "modifiedAt": modified}


def _next_action(receipts: dict, invalid: list[dict], latest: dict | None) -> dict:
    """Unreconciled unknown saves first, then invalid records, then the latest run's own nextAction, then a hint."""
    if receipts["pending"]:
        first, total = receipts["pending"][0], len(receipts["pending"])
        text = (f"对账结果未知的保存回执 {first['requestId']}（slot {first['slot']}）：先用 list_story_artifacts 查该 slot 的新修订，"
                f"再用 get_story_artifact 核对 record.requestId，然后 receipt record … --reconciles {first['requestId']}；"
                "对账前不要换新 requestId 重试" + (f"（共 {total} 份未决回执）" if total > 1 else ""))
        return {"basis": "unknown_receipt", "text": text, "from": f".drama/receipts/{first['requestId']}.json"}
    if invalid:
        first = invalid[0]
        return {"basis": "invalid_record", "from": first["path"],
                "text": f"处理无效或损坏的记录 {first['path']}：{first['errors'][0]}（共 {len(invalid)} 项）；修复或移走之前不要把它们当作恢复依据"}
    if latest is not None:
        return {"basis": "latest_run", "text": latest["nextAction"], "from": latest["path"]}
    return {"basis": "no_runs", "from": None,
            "text": "尚无运行记录：先读取审批记录与本地绑定，确认当前任务后再开始工位运行，并把 run-handoff 写到 .drama/runs/<runId>.json"}


def run_status(project: str) -> dict:
    """Report unreconciled receipts, runs and snapshot integrity, and the next step they imply. Read-only."""
    drama = drama_dir(project)
    receipts = pending(project)
    invalid = [{"kind": "receipt", "path": Path(item["path"]).relative_to(drama.parent).as_posix(), "errors": item["errors"]}
               for item in receipts["invalid"]]
    snapshots = []
    for item in _snapshots(drama):
        doc = item["doc"] if isinstance(item["doc"], dict) else {}
        snapshots.append({"snapshotId": item["id"], "path": item["path"], "intact": not item["problems"],
                          "completeness": doc.get("completeness") if doc.get("completeness") in ("complete", "incomplete") else None,
                          "createdFor": doc.get("createdFor") if isinstance(doc.get("createdFor"), dict) else None, "problems": item["problems"]})
    records = _records(drama, "runs", "run-handoff", "runId")
    newest_first = sorted((item for item in records if not item["problems"]),
                          key=lambda item: (item["file"].stat().st_mtime_ns, item["id"]), reverse=True)
    runs = [_run_summary(item) for item in newest_first]
    invalid += [{"kind": "snapshot", "path": item["path"], "errors": item["problems"]} for item in snapshots if not item["intact"]]
    invalid += [{"kind": "run", "path": item["path"], "errors": item["problems"]} for item in records if item["problems"]]
    latest = runs[0] if runs else None
    return {"ok": True, "command": "status", "project": str(drama.parent), "nextAction": _next_action(receipts, invalid, latest),
            "receipts": {key: receipts[key] for key in ("pending", "read_only_unknown", "unreconcilable_unknown", "resolved_verified", "resolved_host_judged")},
            "runs": {"count": len(records), "recencyBasis": "file_mtime", "latest": latest,
                     "open": [run for run in runs if run["status"]["run"] in OPEN_RUNS or run["unfinished"]]},
            "snapshots": snapshots, "invalid": invalid,
            "note": "只读取 .drama/ 下的本地记录，不读聊天记录；不证明远端状态、采用或质量。最近运行按文件修改时间判定，复制或检出后可能不准。",
            "read_only": True, "remote_verified": False, "adoption_verified": False}


def _run_lines(label: str, run: dict) -> list[str]:
    lines = [f"- {label}：{run['runId']}（{run['workstation']}，{run['status']['run']}/{run['status']['goal']}，任务 {run['taskId']}，"
             f"快照 {run['contextSnapshotId']}，修改于 {run['modifiedAt']}）", f"    下一步：{run['nextAction']}"]
    return lines + ([f"    未完成：{'；'.join(run['unfinished'])}"] if run["unfinished"] else [])


def render_status(result: dict) -> str:
    """Human-readable status; the first line is the next action."""
    receipts, runs, action = result["receipts"], result["runs"], result["nextAction"]
    lines = ["下一步：" + action["text"],
             f"依据：{BASIS[action['basis']]}" + (f"（{action['from']}）" if action["from"] else "") + "。" + result["note"], "",
             f"未决回执（{len(receipts['pending'])}）"]
    for item in receipts["pending"]:
        lines.append(f"- {item['requestId']}：{item['operation']}，slot {item['slot']}，expectedRevision {item['expectedRevision']}；不可重试，先对账")
        for step in item["steps"]:
            call = step.get("command") or f"{step['tool']} {json.dumps(step['args'], ensure_ascii=False)}"
            lines.append("    " + call + (f"；核对 {step['check']}" if "check" in step else ""))
    others = receipts["read_only_unknown"] + receipts["unreconcilable_unknown"]
    if others:
        lines.append(f"其他结果未知的调用（{len(others)}，不是待对账的保存）")
        lines += [f"- {item['requestId']}：{item['operation']}；{item['note']}" for item in others]
    lines += ["", f"运行（{runs['count']} 份；最近一次按文件修改时间判定，recencyBasis: {runs['recencyBasis']}）"]
    if runs["latest"]:
        lines += _run_lines("最近", runs["latest"])
    for run in runs["open"]:
        if run["runId"] != runs["latest"]["runId"]:
            lines += _run_lines("未结束", run)
    lines += ["", f"快照（{len(result['snapshots'])}）"]
    for item in result["snapshots"]:
        lines.append(f"- {item['snapshotId']}：{'完好' if item['intact'] else '有问题'}，completeness: {item['completeness']}")
        lines += [f"    {problem}" for problem in item["problems"]]
    if result["invalid"]:
        lines += ["", f"无效或损坏的记录（{len(result['invalid'])}）"]
        lines += [f"- [{item['kind']}] {item['path']}：{'；'.join(item['errors'])}" for item in result["invalid"]]
    return "\n".join(lines)
