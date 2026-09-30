"""Assemble a reproducible context-snapshot from a task, a host selection and local cache/knowledge files.

Deterministic assembly only: no semantic selection, no truncation, no network, no model. Reads --task,
--selection, <project>/.drama/cache/ (through its manifest) and <project>/knowledge/cards/; writes only
<project>/.drama/snapshots/, and never overwrites an existing snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from .contract_check import check_contract

MANIFEST_VERSION = "drama-studio/cache-manifest/v0"
PARTITIONS = ["task", "project_facts", "current_plan", "knowledge", "unknowns"]


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _label(ref: dict) -> str:
    span = ref.get("range")
    return f"{ref.get('kind')} {ref.get('id')}@r{ref.get('revision')}" + (f" [{span['start']}:{span['end']}]" if span else "")


def _inside(path: Path, root: Path, what: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{what} resolves outside the project ({resolved}); symlinked folders are refused")
    return resolved


def _load_json(path: Path, what: str):
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except ValueError as error:
        raise ValueError(f"{what} is not valid UTF-8 JSON: {path}: {error}") from error


def _manifest(cache: Path) -> list:
    path = cache / "manifest.json"
    if not path.is_file():
        return []
    manifest = _load_json(path, "cache manifest")
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != MANIFEST_VERSION or not isinstance(manifest.get("entries"), list):
        raise ValueError(f"cache manifest must be an object with schemaVersion {MANIFEST_VERSION} and an entries list: {path}")
    return manifest["entries"]


def _read_cache(root: Path, cache: Path, entries: list, ref: dict, where: str, allow_unverified: bool,
                errors: list[str], unknowns: list[str]):
    matches = [entry for entry in entries if isinstance(entry, dict)
               and entry.get("artifactId") == ref["id"] and type(entry.get("revision")) is int and entry["revision"] == ref["revision"]]
    if not matches:
        return "missing", None
    if len({(entry.get("path"), entry.get("sha256"), entry.get("slot")) for entry in matches}) > 1:
        errors.append(f"{where}: cache manifest has conflicting entries for this artifact revision")
        return "error", None
    entry = matches[-1]
    for field in ("path", "slot", "sha256"):
        if not isinstance(entry.get(field), str) or not entry[field]:
            raise ValueError(f"{where}: cache manifest entry has no {field}")
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(cache.resolve()):
        errors.append(f"{where}: manifest path {entry['path']!r} resolves outside .drama/cache/; refused to read it")
        return "error", None
    if not path.is_file():
        return "missing", None
    data = path.read_bytes()
    if _sha(data) != entry["sha256"]:
        errors.append(f"{where}: cache file {entry['path']} is {_sha(data)} but the manifest recorded {entry['sha256']}; the file changed after caching")
        return "error", None
    if entry.get("verified") is not True:
        if not allow_unverified:
            errors.append(f"{where}: manifest marks this cache verified: false (server fingerprint not checked); pass --allow-unverified to pack it anyway")
            return "error", None
        unknowns.append(f"服务端指纹未核验：{ref['id']}@r{ref['revision']}")
    elif entry.get("serverFingerprint") != entry["sha256"]:
        errors.append(f"{where}: manifest claims verified but serverFingerprint differs from sha256")
        return "error", None
    return "ok", (data, entry["slot"])


def _read_card(cards: Path, ref: dict, where: str, project_id: str, errors: list[str]):
    if "/" in ref["id"] or "\\" in ref["id"] or ref["id"] in (".", ".."):
        raise ValueError(f"{where}: card id must be a plain file name inside knowledge/cards/")
    path = cards / f"{ref['id']}@r{ref['revision']}.json"
    if path.is_symlink() and not path.resolve().is_relative_to(cards.resolve()):
        errors.append(f"{where}: card file is a symlink pointing outside knowledge/cards/; refused to read it")
        return "error", None
    if not path.is_file():
        return "missing", None
    data = path.read_bytes()
    card = _load_json(path, f"{where}: knowledge card")
    problems = check_contract("knowledge-card", card)
    if problems:
        errors.append(f"{where}: knowledge card fails contract-check: " + "; ".join(problems))
        return "error", None
    if card["cardId"] != ref["id"] or card["revision"] != ref["revision"]:
        errors.append(f"{where}: card file declares {card['cardId']}@r{card['revision']}")
        return "error", None
    if card["scope"]["projectId"] != project_id:
        errors.append(f"{where}: card belongs to project {card['scope']['projectId']!r}, not this task's project {project_id!r}")
        return "error", None
    if card["processing"] == "retired":
        return "retired", None
    return "ok", (data, card["usage"])


def _name(errors: list[str], item_labels: list[str], omitted_labels: list[str]) -> list[str]:
    named = []
    for error in errors:
        match = re.search(r"\b(items|omitted)\[(\d+)\]", error)
        labels = item_labels if match and match.group(1) == "items" else omitted_labels
        named.append(f"{error} — {labels[int(match.group(2))]}" if match and int(match.group(2)) < len(labels) else error)
    return named


def run_context_pack(project, task, selection, role: str, budget: int, dry_run: bool = False,
                     allow_unverified: bool = False) -> dict:
    root = Path(project).expanduser().absolute()
    if not root.is_dir():
        raise ValueError(f"Project directory not found: {root}")
    if budget < 1:
        raise ValueError("--budget must be a positive number of chars")
    task_bytes = Path(task).read_bytes()
    task_doc = _load_json(Path(task), "task")
    problems = check_contract("task", task_doc)
    if problems:
        raise ValueError("task fails contract-check: " + "; ".join(problems))
    if task_doc["workstation"] is None:
        raise ValueError("task.workstation is null; a snapshot needs a concrete workstation (C1-C6)")
    chosen = _load_json(Path(selection), "selection")
    if isinstance(chosen, dict) and isinstance(chosen.get("items"), list):
        for index, item in enumerate(chosen["items"]):
            if isinstance(item, dict) and item.get("partition") == "task":
                raise ValueError(f"selection.items[{index}]: partition 'task' is filled from --task and cannot be selected")
    problems = check_contract("selection", chosen)
    if problems:
        raise ValueError("selection fails contract-check: " + "; ".join(problems))

    task_hash = _sha(task_bytes)
    items = [{"ref": {"kind": "local_file", "id": f"task:{task_doc['taskId']}", "revision": task_hash, "sha256": task_hash},
              "partition": "task", "required": True, "usage": "project_text", "chars": len(task_bytes.decode("utf-8")),
              "sha256": task_hash, "reason": "任务定义（context-pack 按 --task 自动装入）"}]
    item_labels, omitted, omitted_labels = [f"task {task_doc['taskId']}"], [], []
    errors, unknowns = [], list(chosen.get("unknowns", []))
    cache, cards = root / ".drama" / "cache", root / "knowledge" / "cards"
    for folder, what in ((cache, ".drama/cache"), (cards, "knowledge/cards")):
        if folder.exists():
            _inside(folder, root, what)
    entries, slots, card_revisions = None, {}, {}
    for index, item in enumerate(chosen["items"]):
        ref = item["ref"]
        where = f"selection.items[{index}] ({_label(ref)})"
        if ref["kind"] not in ("remote_artifact", "knowledge_card"):
            raise ValueError(f"{where}: kind must be remote_artifact (cache) or knowledge_card")
        if not isinstance(ref["revision"], int) or isinstance(ref["revision"], bool):
            raise ValueError(f"{where}: revision must pin an integer revision")
        span = ref.get("range")
        if span and span["start"] > span["end"]:
            raise ValueError(f"{where}: range start {span['start']} is after end {span['end']}")
        clean = {key: ref[key] for key in ("kind", "id", "revision", "sha256", "range") if key in ref}
        if ref["kind"] == "remote_artifact":
            entries = _manifest(cache) if entries is None else entries
            status, loaded = _read_cache(root, cache, entries, ref, where, allow_unverified, errors, unknowns)
        else:
            status, loaded = _read_card(cards, ref, where, task_doc["project"]["localId"], errors)
        if status in ("missing", "retired"):
            omitted.append({"ref": clean, "required": item["required"], "reason": "missing" if status == "missing" else "not_relevant"})
            omitted_labels.append(where)
            continue
        if status == "error":
            continue
        data, detail = loaded
        if ref["kind"] == "remote_artifact":
            usage = item.get("usage", "project_text")
            prior = slots.setdefault(detail, (ref["id"], ref["revision"], index))
            if prior[:2] != (ref["id"], ref["revision"]):
                errors.append(f"{where}: slot {detail!r} is already packed as {prior[0]}@r{prior[1]} (selection.items[{prior[2]}]); one package cannot mix revisions of a slot")
        else:
            usage = detail
            if "usage" in item and item["usage"] != usage:
                raise ValueError(f"{where}: selection usage {item['usage']!r} conflicts with the card's own usage {usage!r}")
            prior = card_revisions.setdefault(ref["id"], (ref["revision"], index))
            if prior[0] != ref["revision"]:
                errors.append(f"{where}: card {ref['id']} is already packed at r{prior[0]} (selection.items[{prior[1]}]); one package cannot mix card revisions")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"{where}: file is not UTF-8 text: {error}") from error
        if span:
            if span["end"] > len(text):
                raise ValueError(f"{where}: range {span['start']}:{span['end']} is outside the text (length {len(text)} code points)")
            text = text[span["start"]:span["end"]]
        if "sha256" in ref and ref["sha256"] != _sha(data):
            errors.append(f"{where}: ref.sha256 pins {ref['sha256']} but the file is {_sha(data)}")
        clean["sha256"] = _sha(data)
        if usage == "evaluation_only" and role != "evaluation":
            errors.append(f"{where}: evaluation_only material cannot enter the {role} package")
        if usage == "comparison_only" and role not in ("similarity_review", "evaluation"):
            errors.append(f"{where}: comparison_only material is limited to similarity_review/evaluation, not {role}")
        if role == "reader_effect" and item["partition"] == "current_plan":
            errors.append(f"{where}: a reader_effect package must not include current_plan (author plans)")
        items.append({"ref": clean, "partition": item["partition"], "required": item["required"], "usage": usage,
                      "chars": len(text), "sha256": _sha(text.encode("utf-8")), "reason": item["reason"]})
        item_labels.append(where)

    partition_chars = {name: sum(i["chars"] for i in items if i["partition"] == name) for name in PARTITIONS}
    total = sum(partition_chars.values())
    if total > budget:
        spread = ", ".join(f"{name}={chars}" for name, chars in partition_chars.items() if chars)
        errors.append(f"budget: {total} chars exceed --budget {budget} by {total - budget} ({spread}); nothing truncated or written — shrink the unit or the selection")
    completeness = "incomplete" if any(entry["required"] for entry in omitted) else "complete"
    result = {"ok": True, "command": "context-pack", "project": str(root), "role": role, "dry_run": dry_run,
              "budget": budget, "total_chars": total, "partition_chars": partition_chars,
              "items": [{"ref": label, "partition": i["partition"], "usage": i["usage"], "required": i["required"], "chars": i["chars"]}
                        for label, i in zip(item_labels, items)],
              "omitted_count": len(omitted),
              "omitted": [{"ref": label, "required": o["required"], "reason": o["reason"]} for label, o in zip(omitted_labels, omitted)],
              "completeness": completeness, "written": False, "existing": False,
              "network_used": False, "models_called": False, "remote_verified": False}
    if errors:
        return {**result, "passed": False, "errors": errors}

    snapshot = {"schemaVersion": "drama-studio/context-snapshot/v0", "snapshotId": "",
                "createdFor": {"taskId": task_doc["taskId"], "workstation": task_doc["workstation"], "role": role},
                "projectBase": {"remoteProjectId": task_doc["project"]["remoteProjectId"],
                                "sourceSnapshotId": chosen.get("sourceSnapshotId")},
                "budget": {"unit": "chars", "limit": budget}, "items": items, "omitted": omitted,
                "completeness": completeness}
    unknowns = list(dict.fromkeys(unknowns))
    if unknowns:
        snapshot["unknowns"] = unknowns
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    snapshot_id = "ctx-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    snapshot["snapshotId"] = snapshot_id
    problems = check_contract("context-snapshot", snapshot)
    if problems:
        return {**result, "passed": False, "errors": _name(problems, item_labels, omitted_labels)}

    body = (json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    folder = root / ".drama" / "snapshots"
    target, sidecar = folder / f"{snapshot_id}.json", folder / f"{snapshot_id}.sha256"
    sidecar_body = f"{digest}  {snapshot_id}.json\n".encode("utf-8")
    result.update(snapshot_id=snapshot_id, snapshot_sha256="sha256:" + digest, unknowns=unknowns)
    result["would_write" if dry_run else "snapshot_path"] = str(target)
    if not dry_run:
        result["sha256_path"] = str(sidecar)
    if folder.exists() or folder.is_symlink():
        _inside(folder, root, ".drama/snapshots")
    for path, content in ((target, body), (sidecar, sidecar_body)):
        if path.exists() and path.read_bytes() != content:
            return {**result, "passed": False, "errors": [f"{path.name} already exists with different bytes; snapshots are never overwritten"]}
    if not dry_run:
        folder.mkdir(parents=True, exist_ok=True)
        _inside(folder, root, ".drama/snapshots")
        written = [path.name for path, content in ((target, body), (sidecar, sidecar_body)) if _publish(path, content)]
        result.update(written=target.name in written, existing=target.name not in written, written_files=written)
    return {**result, "passed": True, "errors": []}


def _publish(path: Path, content: bytes) -> bool:
    """Write complete bytes to a temp file, then hard-link it into place; never replaces an existing file."""
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temp, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temp, path)
        return True
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError(f"{path.name} appeared concurrently with different bytes; snapshots are never overwritten")
        return False
    finally:
        temp.unlink()
