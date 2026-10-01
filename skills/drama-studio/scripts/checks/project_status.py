"""Rebuild the next step and mark stale execution dependencies from a project's local records.

`status` and `impact` only read `<project>/.drama/` (receipts, cache manifest, snapshots, runs): no writes, no lock
files, no network, no model, no chat history. Passing proves only what those files record. `status` repeats what the
records say is next and flags a run whose snapshot pins an older revision than the newest trusted one in the local
cache; it does not judge whether that step is right, and it never says the remote has nothing newer. `stale` means a
snapshot pins an older revision of the target slot through a manifest entry whose slot a get record or a save receipt
vouches for; `current` means no recorded execution dependency points at an older revision of that slot. Reference
kinds whose dependencies are not assessed, content-level implicit dependencies aside, are `unknown`; anything else
uncertain is `unknown` too, and nothing here proves remote state or adoption.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex

from .contract_check import check_contract
from .receipt import MANIFEST, area, contained, drama_dir, effective_entries, pending, slot_rank

NOTE = "current 只表示没有记录在案的执行依赖指向该 slot 的旧修订；内容层面的隐含依赖未评估。工具只读，不自动重跑运行，也不改写正文。"
LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"  # what str.splitlines splits on
MAX_DEPTH = 50  # context_snapshot references followed before giving up as unknown
OPEN_RUNS = ("planned", "running", "interrupted")
BASIS = {"unknown_receipt": "有结果未知、尚未对账的保存回执", "invalid_record": "有无效或损坏的本地记录",
         "stale_run": "最近一次运行的快照引用了旧修订，本地缓存已有更新的可信修订",
         "latest_run": "最近一次运行记录的 nextAction", "no_runs": ".drama/runs/ 中没有有效的运行记录"}
ADVICE = {"receipt": "回执只追加、不修改，这份不能当作恢复依据：由人确认它的来历后移出 .drama/receipts/，需要时用新的 requestId 重新记录对应的响应",
          "uncounted": "这份回执本身有效，只是它声称的对账没有被计入；回执只追加，不要改它：按原因重新对账，并用新的 requestId 记录正确的响应",
          "manifest": "manifest 只追加，工具不会修正它：由人核对并处理这个文件；在此之前 impact 以退出码 1 结束，各运行是否失效均为未知",
          "snapshot": "快照写入后不改，工具也不会覆盖它：不要沿用这份快照；由人移走损坏的文件后，用 context-pack 按同一任务与选材重新装包",
          "run": "运行记录由宿主写入：由宿主按报错改正或重写这份 run-handoff，在此之前不要把它当作恢复依据"}
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
    """Return ((slot, revision), None) when the manifest pins one trusted slot and revision for the artifact, else (None, why).

    The slot is the one its strongest-source entries state: a weaker entry naming another slot was corrected by them.
    """
    found = [entry for entry in entries if entry.get("artifactId") == artifact_id]
    if not found:
        return None, "manifest 中查不到该 artifactId，无法得知它属于哪个 slot"
    strongest = effective_entries(found)
    if len({repr(entry.get("revision")) for entry in found}) > 1 or len({repr(entry.get("slot")) for entry in strongest}) > 1:
        return None, "manifest 中该 artifactId 对应多个不同的 slot 或 revision"
    slot, revision = strongest[0].get("slot"), found[0].get("revision")
    if not isinstance(slot, str) or not slot or type(revision) is not int or revision < 1:
        return None, "manifest 条目没有有效的 slot 或不小于 1 的整数 revision"
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
    if type(pinned) is not int or pinned < 1:
        return "unknown", "引用缺少不小于 1 的整数 revision，无法判断新旧"
    if pinned != identity[1]:
        return "unknown", f"引用的 revision {pinned} 与 manifest 记录的 r{identity[1]} 不一致"
    if identity[0] == slot and pinned < revision:
        return "stale", f"引用了 slot {slot} 的旧修订 r{pinned}，目标修订为 r{revision}"
    return "current", None


def _ref_label(index: int, ref: dict) -> str:
    name = ref["id"] if ref["kind"] == "remote_artifact" else f"{ref['kind']} {ref['id']}"
    return f"items[{index}] {name}" + (f"@r{ref['revision']}" if type(ref["revision"]) is int else "")


def _dependencies(snapshot_id: str, snapshots: dict[str, dict], judge, trail: tuple = ()) -> list[dict]:
    """Every dependency of a snapshot that is not clearly current, following context_snapshot references.

    `judge(ref)` classifies one remote_artifact reference as (status, reason, slot, target revision). The task file
    (the local_file in the task partition, as context-pack writes it) and knowledge cards are not slot dependencies;
    every other reference kind is unknown, never silently current, and so is a chain deeper than MAX_DEPTH.
    """
    item = snapshots.get(snapshot_id)
    if item is None:
        return [{"ref": None, "status": "unknown", "reason": f"快照 {snapshot_id} 不在 .drama/snapshots/ 中"}]
    if item["problems"]:
        return [{"ref": None, "status": "unknown", "reason": "快照未通过完整性检查：" + problem} for problem in item["problems"]]
    found = []
    for index, packed in enumerate(item["doc"]["items"]):  # omitted entries never entered the context, so they are not dependencies
        ref = packed["ref"]
        label = _ref_label(index, ref)
        if ref["kind"] == "knowledge_card" or (ref["kind"] == "local_file" and packed["partition"] == "task"):
            continue
        if ref["kind"] == "remote_artifact":
            status, why, slot, target = judge(ref)
            if status != "current":
                found.append({"ref": label, "status": status, "reason": why, "slot": slot, "pinned": ref["revision"], "target": target})
        elif ref["kind"] != "context_snapshot":
            found.append({"ref": label, "status": "unknown", "reason": "该引用类型的依赖未评估"})
        elif ref["id"] in (*trail, snapshot_id):
            found.append({"ref": label, "status": "unknown", "reason": "快照之间的引用成环，无法判定"})
        elif len(trail) >= MAX_DEPTH:
            found.append({"ref": label, "status": "unknown", "reason": f"快照引用嵌套超过 {MAX_DEPTH} 层，未继续展开"})
        else:
            found += [dict(inner, ref=f"{label} > {inner['ref']}" if inner["ref"] else label)
                      for inner in _dependencies(ref["id"], snapshots, judge, (*trail, snapshot_id))]
    return found


def _public(finding: dict) -> dict:
    return {key: finding[key] for key in ("ref", "status", "reason")}


def _verdict(result: dict, reasons: list[dict]) -> dict:
    status = next((name for name in ("stale", "unknown") if any(reason["status"] == name for reason in reasons)), "current")
    result.update(status=status, reasons=reasons)
    if status == "unknown":
        result["suggestion"] = WIDEN
    return result


def _judge_snapshot(item: dict, snapshots: dict[str, dict], judge) -> dict:
    return _verdict({"snapshotId": item["id"], "path": item["path"]}, [_public(found) for found in _dependencies(item["id"], snapshots, judge)])


def _claims(entries: list[dict], slot: str) -> list[dict]:
    """Entries naming `slot`, in manifest order, except those whose artifact resolves to one trusted other slot.

    Only a clean correction removes a claim: while the artifact's identity is unresolved (contradicting strongest
    entries, differing revisions, no usable slot), every entry keeps the claim it states, so doubt never disappears
    because the evidence contradicts itself.
    """
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        groups.setdefault(repr(entry.get("artifactId")), []).append(entry)
    resolved: dict[str, tuple | None] = {}

    def claims(entry: dict) -> bool:
        artifact = entry.get("artifactId")
        key = repr(artifact)
        if key not in resolved:  # a str id equals only itself, so its group is all _identity would look at
            resolved[key] = _identity(groups[key] if isinstance(artifact, str) else entries, artifact)[0]
        return resolved[key] is None or resolved[key][0] == slot
    return [entry for entry in entries if entry.get("slot") == slot and claims(entry)]


def _slot_evidence(entries: list[dict], slot: str) -> tuple[dict[int, list], list[tuple]]:
    """What the manifest holds for a slot: trusted {revision: [artifactId]} and the claimants that cannot be trusted.

    A claimant is an artifact with an entry naming this slot whose identity does not resolve (host-declared, no or
    unexpected slotSource, conflicting entries); it comes back as (artifactId, why, every revision its entries state).
    An entry whose artifact a stronger source settled in another slot is not a claim on this one.
    """
    trusted: dict[int, list] = {}
    claimants: dict[str, tuple] = {}
    for entry in _claims(entries, slot):
        artifact = entry.get("artifactId")
        identity, why = _identity(entries, artifact)
        if identity is None:
            claimants[repr(artifact)] = (artifact, why, [other.get("revision") for other in entries if other.get("artifactId") == artifact])
        elif artifact not in trusted.setdefault(identity[1], []):
            trusted[identity[1]].append(artifact)
    return trusted, list(claimants.values())


def _own_outputs(found: list[dict], run: dict, entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split a run's findings into those that still count and the stale pins its own recorded outputs cover.

    The rule only ever clears on complete, trusted, unambiguous evidence. Revisions of a slot increase by one per
    save, so a pin of revision P is covered against judged revision T only when every revision P+1..T is a trusted
    cached entry listed in the run's outputs, none of them is claimed by two trusted artifacts, and no untrusted or
    ambiguous entry claims the slot at a revision not provably at or below P. A trusted revision in that span the
    run did not produce leaves the pin stale; any other shortfall leaves it unknown. Outputs are the run record's
    claim; a planned or failed run covers nothing, and a run with no own output in the span is judged without the rule.
    """
    produced: dict[str, dict[int, str]] = {}
    for index, ref in enumerate(run["outputs"] if run["status"]["run"] not in ("planned", "failed") else []):
        identity, _ = _identity(entries, ref["id"]) if ref["kind"] == "remote_artifact" else (None, None)
        if identity and ref["revision"] == identity[1]:
            produced.setdefault(identity[0], {}).setdefault(identity[1], f"outputs[{index}] {ref['id']}@r{identity[1]}")
    kept, own = [], []
    for item in found:
        if item["status"] != "stale":
            kept.append(item)
            continue
        slot, pinned, mine = item["slot"], item["pinned"], produced.get(item["slot"], {})
        trusted, claimants = _slot_evidence(entries, slot)
        low, high = pinned + 1, item["target"]  # the span is never walked integer by integer: a target can be huge
        foreign = sorted(revision for revision in trusted if low <= revision <= high and revision not in mine)
        claimed = sorted(revision for revision in mine if low <= revision <= high)
        if foreign or not claimed:  # stale as it would be without the rule, against the highest revision that is not its own output
            kept.append(dict(item, against=foreign[-1] if foreign else high))
            continue
        stated = {revision for _, _, revisions in claimants for revision in revisions if type(revision) is int}
        doubts, cursor = [], low
        for revision in sorted(revision for revision in stated | set(trusted) if low <= revision <= high) + [high + 1]:
            if cursor < revision:  # a run of revisions nothing in the manifest states
                doubts.append((f"r{cursor}" if cursor == revision - 1 else f"r{cursor} 至 r{revision - 1}") + " 未缓存，无法确认是否为该运行产出")
            if revision <= high and revision not in trusted:
                doubts.append(f"r{revision} 只有不可信的缓存条目，无法确认是否为该运行产出")
            cursor = revision + 1
        doubts += [f"r{revision} 有多个不同的可信 artifactId（{'、'.join(map(str, trusted[revision]))}）"
                   for revision in sorted(trusted) if low <= revision <= high and len(trusted[revision]) > 1]
        doubts += [f"manifest 中 {artifact} 声称属于该 slot，但{why}" for artifact, why, revisions in claimants
                   if not all(type(revision) is int and revision <= pinned for revision in revisions)]
        named = f"slot {slot} 的 {'、'.join(f'r{revision}' for revision in claimed)}（{'、'.join(mine[revision] for revision in claimed)}）"
        if doubts:
            kept.append(dict(item, status="unknown", reason=f"运行记录声称产出了 {named}，但证据不完整，无法确认它覆盖了 r{pinned} 之后的全部修订："
                                                             + "；".join(doubts)))
        else:
            own.append(dict(item, status="current", produced=item["target"], output=mine[item["target"]],
                            reason=f"运行记录声称产出了 {named}，快照对旧修订 r{pinned} 的引用不使它失效"))
    return kept, own


def _judge_run(item: dict, loaded: dict[str, dict], snapshots: dict[str, dict], judge, entries: list[dict]) -> dict:
    result = {"runId": item["id"], "path": item["path"], "contextSnapshotId": None}
    if item["problems"]:
        return _verdict(result, [{"ref": None, "status": "unknown", "reason": "运行记录无效：" + problem} for problem in item["problems"]])
    result["contextSnapshotId"] = snapshot_id = item["doc"]["contextSnapshotId"]
    ref = f"context_snapshot {snapshot_id}"
    if snapshot_id not in snapshots:
        return _verdict(result, [{"ref": ref, "status": "unknown", "reason": "所依赖的快照不在 .drama/snapshots/ 中"}])
    kept, own = _own_outputs(_dependencies(snapshot_id, loaded, judge), item["doc"], entries)
    worst = "stale" if any(found["status"] == "stale" for found in kept) else "unknown"
    text = f"所依赖的快照为 {worst}" if snapshots[snapshot_id]["status"] == worst else "所依赖的快照中有无法判定的引用"
    lead = [{"ref": ref, "status": worst, "reason": text}] if kept else []
    return _verdict(result, lead + [_public(found) for found in kept + own])


def _count(items: list[dict]) -> dict:
    return {name: sum(item["status"] == name for item in items) for name in ("stale", "unknown", "current")}


def run_impact(project: str, slot: str | None = None, revision: int | str | None = None, artifact: str | None = None) -> dict:
    """Mark every snapshot and run stale, unknown or current against one slot revision. Read-only."""
    drama = drama_dir(project)
    if not ((artifact is None and slot is not None and revision is not None) or (artifact is not None and slot is None and revision is None)):
        raise ValueError("给出 --slot 与 --revision 两者，或只给 --artifact；两组互斥，也不能只给一半")
    if artifact is None:
        text = str(revision) if type(revision) in (int, str) else ""
        if not (text.isascii() and text.isdigit() and int(text) >= 1):
            raise ValueError(f"--revision 必须是不小于 1 的整数，收到 {revision!r}")
        if not isinstance(slot, str) or not slot.strip():
            raise ValueError("--slot 不能为空")
        revision = int(text)
    entries = _entries(drama)
    resolved = "--slot/--revision"
    if artifact is not None:
        identity, why = _identity(entries, artifact)
        if identity is None:
            raise ValueError(f"--artifact {artifact} 无法解析出可信的 slot 与 revision：{why}。"
                             "请用它的 get_story_artifact 响应重新缓存（receipt cache），或显式给出 --slot 与 --revision")
        (slot, revision), resolved = identity, f"--artifact {artifact}"
    loaded = {item["id"]: item for item in _snapshots(drama)}

    def judge(ref: dict) -> tuple[str, str | None, str, int]:
        return (*judge_ref(ref, entries, slot, revision), slot, revision)

    snapshots = [_judge_snapshot(item, loaded, judge) for item in loaded.values()]
    by_id = {item["snapshotId"]: item for item in snapshots}
    runs = [_judge_run(item, loaded, by_id, judge, entries) for item in _records(drama, "runs", "run-handoff", "runId")]
    seen = bool(_claims(entries, slot))
    warnings = [] if seen else [f"manifest 中没有任何条目属于 slot {slot}：可能是拼写错误，也可能该 slot 从未缓存。结论只覆盖记录在案的引用，"
                                "全部为 current 不说明这个 slot 的修订没有影响"]
    newest = _newest(entries, slot)[0] or None
    if newest and revision < newest:
        warnings.append(f"目标修订 r{revision} 低于 slot {slot} 已缓存的最新可信修订 r{newest}：结论只针对 r{revision}，"
                        f"引用 r{revision} 及更高修订的记录在这里不会标为 stale；要看最新修订的影响，改用 --revision {newest}")
    return {"ok": True, "command": "impact", "project": str(drama.parent),
            "target": {"slot": slot, "revision": revision, "resolvedFrom": resolved, "slotInManifest": seen, "newestTrustedRevision": newest},
            "snapshots": snapshots, "runs": runs, "summary": {"snapshots": _count(snapshots), "runs": _count(runs)},
            "warnings": warnings, "note": NOTE, "read_only": True, "remote_verified": False}


def _newest(entries: list[dict], slot: str) -> tuple[int, str | None]:
    """Newest trusted revision the manifest holds for a slot, and a doubt when an untrusted entry may be newer still."""
    newest, untrusted = 0, []
    for entry in _claims(entries, slot):
        identity, _ = _identity(entries, entry.get("artifactId"))
        if identity is None:
            untrusted.append(entry)
        else:
            newest = max(newest, identity[1])
    doubt = next((f"manifest 中 {entry.get('artifactId')} 也声称属于 slot {slot}，但条目不可信，无法排除它是更新的修订" for entry in untrusted
                  if not (type(entry.get("revision")) is int and entry["revision"] <= newest)), None)
    return newest, doubt


def _against_newest(ref: dict, entries: list[dict]) -> tuple[str, str | None, str, int]:
    """judge_ref against the newest trusted revision cached for the reference's own slot."""
    identity, _ = _identity(entries, ref["id"])
    slot = identity[0] if identity else ""
    newest, doubt = _newest(entries, slot)
    status, why = judge_ref(ref, entries, slot, newest)
    return ("unknown", doubt, slot, newest) if status == "current" and doubt else (status, why, slot, newest)


def _staleness(run: dict, snapshots: dict[str, dict], entries: list[dict], manifest_error: str | None, project: Path) -> dict:
    """Compare what a run's snapshot pins with the newest trusted revision of each slot in the local cache manifest.

    Uses _dependencies, judge_ref and _own_outputs, so the rules are impact's. It only ever claims what the local cache shows.
    """
    found, own = ([{"ref": None, "status": "unknown", "reason": manifest_error}], []) if manifest_error else _own_outputs(
        _dependencies(run["contextSnapshotId"], snapshots, lambda ref: _against_newest(ref, entries)), run, entries)
    produced = [{"ref": item["ref"], "slot": item["slot"], "pinnedRevision": item["pinned"], "producedRevision": item["produced"],
                 "output": item["output"]} for item in own]
    newer = [{"ref": item["ref"], "slot": item["slot"], "pinnedRevision": item["pinned"], "newestTrustedRevision": item["target"],
              "staleAgainstRevision": item["against"],
              "impactCommand": f"drama_tools.py impact {shlex.quote(str(project))} --slot={shlex.quote(item['slot'])} --revision {item['against']}"}
             for item in found if item["status"] == "stale"]
    reasons = [f"{item['ref']}：{item['reason']}" if item["ref"] else item["reason"] for item in found if item["status"] == "unknown"]
    if newer:
        return {"stalenessCheck": "newer_revision_cached", "possiblyStale": True, "newerRevisions": newer, "stalenessReasons": reasons,
                "ownOutputs": produced}
    check = "unknown" if reasons else "newer_revision_is_own_output" if produced else "no_newer_revision_cached"
    return {"stalenessCheck": check, "newerRevisions": [], "stalenessReasons": reasons, "ownOutputs": produced}


def _breaks(text: str) -> bool:
    return any(char in LINE_BREAKS for char in text)


def _shown(slot: str) -> str:
    """A slot as the text view may print it: escaped when it holds a line break, so one line never alters it."""
    return json.dumps(slot) if _breaks(slot) else slot


def _run_summary(item: dict, staleness: dict) -> dict:
    doc = item["doc"]
    modified = datetime.fromtimestamp(item["file"].stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return {"runId": doc["runId"], "path": item["path"], "taskId": doc["taskId"], "workstation": doc["workstation"],
            "contextSnapshotId": doc["contextSnapshotId"], "status": doc["status"], "unfinished": doc["unfinished"],
            "nextAction": doc["nextAction"], "modifiedAt": modified, **staleness}


def _next_action(receipts: dict, invalid: list[dict], latest: dict | None) -> dict:
    """Unknown saves first, then invalid records, then a possibly stale latest run, then its own nextAction, then a hint."""
    if receipts["pending"]:
        first, total = receipts["pending"][0], len(receipts["pending"])
        slot = f"（slot {first['slot']}）" if first["slot"] else ""
        text = (f"对账结果未知的保存回执 {first['requestId']}{slot}：先用 list_story_artifacts 查该 slot 的新修订，"
                f"再用 get_story_artifact 核对 record.requestId，然后 receipt record … --reconciles {first['requestId']}；"
                "对账前不要换新 requestId 重试" + (f"（共 {total} 份未决回执）" if total > 1 else ""))
        return {"basis": "unknown_receipt", "text": text, "from": f".drama/receipts/{first['requestId']}.json"}
    if invalid:
        first = invalid[0]
        return {"basis": "invalid_record", "from": first["path"],
                "text": f"处理无效或损坏的记录 {first['path']}：{first['errors'][0]}（共 {len(invalid)} 项）；{first['advice']}"}
    if latest is not None and latest.get("possiblyStale"):
        first, more = latest["newerRevisions"][0], len(latest["newerRevisions"]) - 1
        slot = _shown(first["slot"])
        # a command holding a line break cannot be printed on one line without changing it: point at the exact JSON value instead
        start = (f"先对 slot {slot} 的 r{first['staleAgainstRevision']} 运行 impact（命令含换行类字符，写不成安全的单行命令："
                 "完整命令见 status --json 的 nextAction.impactCommand）" if _breaks(first["impactCommand"]) else f"先运行 {first['impactCommand']} ")
        text = (f"{start}确认失效范围，再决定是否重新装包、重跑：最近运行 {latest['runId']} 的快照引用了 "
                f"slot {slot} 的 r{first['pinnedRevision']}，本地缓存已有可信的 r{first['staleAgainstRevision']}"
                + (f"（另有 {more} 个 slot 也有更新修订）" if more else ""))
        return {"basis": "stale_run", "text": text, "from": latest["path"], "impactCommand": first["impactCommand"],
                "recordedNextAction": latest["nextAction"]}
    if latest is not None:
        return {"basis": "latest_run", "text": latest["nextAction"], "from": latest["path"]}
    return {"basis": "no_runs", "from": None,
            "text": "尚无运行记录：先读取审批记录与本地绑定，确认当前任务后再开始工位运行，并把 run-handoff 写到 .drama/runs/<runId>.json"}


def run_status(project: str) -> dict:
    """Report unreconciled receipts, runs and snapshot integrity, and the next step they imply. Read-only."""
    drama = drama_dir(project)
    receipts = pending(project)
    invalid = [{"kind": "receipt", "path": Path(item["path"]).relative_to(drama.parent).as_posix(), "errors": item["errors"],
                "advice": ADVICE["uncounted" if item["errors"][0].startswith("reconciliation not counted") else "receipt"]}
               for item in receipts["invalid"]]
    try:
        entries, manifest_error = _entries(drama), None
    except ValueError as error:  # impact exits 1 on the same file; here it is an invalid record so the rest is still reported
        entries, manifest_error = [], str(error)
        invalid.append({"kind": "manifest", "path": ".drama/cache/manifest.json", "errors": [manifest_error], "advice": ADVICE["manifest"]})
    snapshots, loaded = [], {}
    for item in _snapshots(drama):
        loaded[item["id"]] = item
        doc = item["doc"] if isinstance(item["doc"], dict) else {}
        snapshots.append({"snapshotId": item["id"], "path": item["path"], "intact": not item["problems"],
                          "completeness": doc.get("completeness") if doc.get("completeness") in ("complete", "incomplete") else None,
                          "createdFor": doc.get("createdFor") if isinstance(doc.get("createdFor"), dict) else None, "problems": item["problems"]})
    records = _records(drama, "runs", "run-handoff", "runId")
    newest_first = sorted((item for item in records if not item["problems"]),
                          key=lambda item: (item["file"].stat().st_mtime_ns, item["id"]), reverse=True)
    runs = [_run_summary(item, _staleness(item["doc"], loaded, entries, manifest_error, drama.parent)) for item in newest_first]
    invalid += [{"kind": "snapshot", "path": item["path"], "errors": item["problems"], "advice": ADVICE["snapshot"]}
                for item in snapshots if not item["intact"]]
    invalid += [{"kind": "run", "path": item["path"], "errors": item["problems"], "advice": ADVICE["run"]} for item in records if item["problems"]]
    latest = runs[0] if runs else None
    return {"ok": True, "command": "status", "project": str(drama.parent), "nextAction": _next_action(receipts, invalid, latest),
            "receipts": {key: receipts[key] for key in ("pending", "read_only_unknown", "unreconcilable_unknown", "resolved_verified", "resolved_host_judged")},
            "runs": {"count": len(records), "recencyBasis": "file_mtime", "latest": latest,
                     "open": [run for run in runs if run["status"]["run"] in OPEN_RUNS or run["unfinished"]]},
            "snapshots": snapshots, "invalid": invalid,
            "note": "只读取 .drama/ 下的本地记录，不读聊天记录；不证明远端状态、采用或质量。最近运行按文件修改时间判定，复制或检出后可能不准。"
                    "失效提示只比较本地缓存 manifest 里的可信条目，不说明远端有没有更新的修订。",
            "read_only": True, "remote_verified": False, "adoption_verified": False}


def _run_lines(label: str, run: dict) -> list[str]:
    lines = [f"- {label}：{run['runId']}（{run['workstation']}，{run['status']['run']}/{run['status']['goal']}，任务 {run['taskId']}，"
             f"快照 {run['contextSnapshotId']}，修改于 {run['modifiedAt']}）", f"    下一步：{run['nextAction']}"]
    lines += [f"    未完成：{'；'.join(run['unfinished'])}"] if run["unfinished"] else []
    lines += [f"    可能已失效：快照引用 slot {_shown(item['slot'])} 的 r{item['pinnedRevision']}，本地缓存已有可信的 r{item['staleAgainstRevision']}；"
              + ("命令含换行类字符，见 status --json 的 newerRevisions[].impactCommand" if _breaks(item["impactCommand"]) else f"先运行 {item['impactCommand']}")
              for item in run["newerRevisions"]]
    lines += [f"    快照引用 slot {_shown(item['slot'])} 的 r{item['pinnedRevision']}；运行记录声称更新的 r{item['producedRevision']} 是它自己的产出"
              f"（{item['output']}），不因此失效" for item in run["ownOutputs"]]
    if run["stalenessReasons"]:
        lines.append(f"    {'其余引用' if run['newerRevisions'] else ''}无法判断是否失效：{'；'.join(run['stalenessReasons'])}")
    elif not run["newerRevisions"] and not run["ownOutputs"]:
        lines.append("    本地缓存中没有它所引用 slot 的更新修订；这不说明远端没有")
    return lines


def _one_line(text: str) -> str:
    """Recorded values may span lines; the text view keeps one logical line per printed line."""
    parts = text.splitlines()
    return " ".join([parts[0].rstrip(), *(part.strip() for part in parts[1:] if part.strip())]) if parts else ""


def render_status(result: dict) -> str:
    """Human-readable status; the first line is the next action."""
    receipts, runs, action = result["receipts"], result["runs"], result["nextAction"]
    lines = ["下一步：" + action["text"]]
    if action["basis"] == "stale_run":
        pinned = runs["latest"]["newerRevisions"][0]["pinnedRevision"]
        lines.append(f"该运行按旧修订 r{pinned} 的上下文记录的下一步（先看 impact 结果，不要直接照做）：{action['recordedNextAction']}")
    doubt = "最近运行是否失效无法判断，见下。" if runs["latest"] and runs["latest"]["stalenessCheck"] == "unknown" else ""
    lines += [f"依据：{BASIS[action['basis']]}" + (f"（{action['from']}）" if action["from"] else "") + "。" + doubt + result["note"], "",
             f"未决回执（{len(receipts['pending'])}）"]
    for item in receipts["pending"]:
        known = "".join(f"，{label} {item[key]}" for label, key in (("slot", "slot"), ("expectedRevision", "expectedRevision")) if item[key] is not None)
        lines.append(f"- {item['requestId']}：{item['operation']}{known}；不可重试，先对账")
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
        lines.append(f"- {item['snapshotId']}：{'完好' if item['intact'] else '有问题'}，completeness: {item['completeness'] or '未知'}")
        lines += [f"    {problem}" for problem in item["problems"]]
    if result["invalid"]:
        lines += ["", f"无效或损坏的记录（{len(result['invalid'])}）"]
        for item in result["invalid"]:
            lines += [f"- [{item['kind']}] {item['path']}：{'；'.join(item['errors'])}", f"    处理：{item['advice']}"]
    return "\n".join(map(_one_line, lines))
