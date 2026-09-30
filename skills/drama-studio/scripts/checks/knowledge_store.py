"""Read-only commands over a project-private knowledge store.

Cards live at <project>/knowledge/cards/<cardId>@r<revision>.json; local evidence at
knowledge/sources/<sourceId>/. Nothing here writes, calls a network or a model. A same-source
mark only says cards share a sourceId; it says nothing about content overlap or reliability.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from checks.contract_check import check_contract

CARDS = "knowledge/cards"
SOURCES = "knowledge/sources"
FLAGS = {"network_used": False, "models_called": False, "read_only": True}
HINT = ("未找到知识库。约定：卡片放在 <项目>/knowledge/cards/<cardId>@r<revision>.json（每个修订一个新文件），"
        "本地原始证据放在 <项目>/knowledge/sources/<sourceId>/…；本工具只读，不会创建目录。")
SAME_SOURCE_NOTE = "同源只说明多张卡共享同一 sourceId（来源重复），不说明内容重复或来源可靠。"
REVISION = re.compile(r"[1-9][0-9]*")


def _project(project: str) -> Path:
    root = Path(project).expanduser().absolute()
    if not root.is_dir():
        raise ValueError(f"Project directory not found: {root}")
    return root


def _parse_name(name: str) -> tuple[str, int] | None:
    stem = name[:-len(".json")]
    index = stem.rfind("@r")
    if index <= 0 or not REVISION.fullmatch(stem[index + 2:]):
        return None
    return stem[:index], int(stem[index + 2:])


def _load_entry(path: Path) -> dict:
    parsed = _parse_name(path.name)
    entry = {"path": str(path), "cardId": parsed[0] if parsed else None,
             "revision": parsed[1] if parsed else None, "doc": None, "errors": []}
    if parsed is None:
        entry["errors"].append("filename: must be <cardId>@r<revision>.json with a positive integer revision")
    try:
        entry["doc"] = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        entry["errors"].append(f"json: {error}")
        return entry
    entry["errors"].extend(check_contract("knowledge-card", entry["doc"]))
    doc = entry["doc"]
    if parsed and isinstance(doc, dict):
        if doc.get("cardId") != parsed[0]:
            entry["errors"].append(f"filename: cardId {parsed[0]!r} does not match content cardId {doc.get('cardId')!r}")
        if doc.get("revision") != parsed[1]:
            entry["errors"].append(f"filename: revision {parsed[1]} does not match content revision {doc.get('revision')!r}")
    return entry


def _load_store(root: Path) -> dict:
    """Return entries (valid and invalid), ignored paths and the store status."""
    base = {"project": str(root), **FLAGS}
    if not (root / "knowledge").is_dir():
        return {**base, "store_status": "no_store", "hint": HINT, "entries": [], "ignored": []}
    cards = root / CARDS
    if not cards.is_dir():
        return {**base, "store_status": "no_cards", "hint": HINT, "entries": [], "ignored": []}
    entries, ignored = [], []
    for path in sorted(cards.iterdir()):
        if path.is_file() and path.suffix == ".json":
            entries.append(_load_entry(path))
        else:
            ignored.append(str(path))
    return {**base, "store_status": "present", "entries": entries, "ignored": ignored}


def _public(store: dict) -> dict:
    return {key: value for key, value in store.items() if key != "entries"}


def _invalid(entries: list[dict]) -> list[dict]:
    return [{"path": entry["path"], "errors": entry["errors"]} for entry in entries if entry["errors"]]


def run_knowledge_validate(project: str) -> dict:
    store = _load_store(_project(project))
    entries = store["entries"]
    invalid = _invalid(entries)
    passed = False if invalid else (True if entries else None)
    return {"ok": True, "command": "knowledge validate", **_public(store), "checked": len(entries),
            "valid": [{"path": e["path"], "cardId": e["cardId"], "revision": e["revision"]} for e in entries if not e["errors"]],
            "invalid": invalid, "passed": passed, "enforcement": "S"}


def _texts(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in _texts(item)]
    return []


def _line(doc: dict, same: list[dict]) -> str:
    marks = "  ".join(f"同源:{item['sourceId']}({','.join(item['cards'])})" for item in same) or "无同源"
    line = f"{doc['cardId']}@r{doc['revision']}  {doc['knowledgeType']}  {','.join(doc['transfer']['workstations'])}  {doc['usage']}  {marks}"
    return line + ("  [retired]" if doc["processing"] == "retired" else "")


def run_knowledge_search(project: str, knowledge_type: str | None = None, workstation: str | None = None,
                         usage: str | None = None, text: str | None = None, include_retired: bool = False) -> dict:
    store = _load_store(_project(project))
    latest: dict[str, dict] = {}
    for entry in store["entries"]:
        if not entry["errors"] and entry["revision"] > latest.get(entry["cardId"], {}).get("revision", 0):
            latest[entry["cardId"]] = entry
    pool = [entry for _, entry in sorted(latest.items())
            if include_retired or entry["doc"]["processing"] != "retired"]
    # Same-source is computed over the whole participating set, before any filter narrows it.
    holders: dict[str, set[str]] = {}
    for entry in pool:
        for source in entry["doc"]["evidence"]["sources"]:
            holders.setdefault(source["sourceId"], set()).add(entry["cardId"])
    needle = text.casefold() if text else None
    results = []
    for entry in pool:
        doc = entry["doc"]
        if knowledge_type and doc["knowledgeType"] != knowledge_type:
            continue
        if workstation and workstation not in doc["transfer"]["workstations"]:
            continue
        if usage and doc["usage"] != usage:
            continue
        if needle and needle not in "\n".join([doc["cardId"], *_texts(doc["content"]), *_texts(doc["transfer"])]).casefold():
            continue
        source_ids = dict.fromkeys(source["sourceId"] for source in doc["evidence"]["sources"])
        same = [{"sourceId": sid, "cards": sorted(holders[sid] - {doc["cardId"]})}
                for sid in source_ids if len(holders[sid]) > 1]
        results.append({"cardId": doc["cardId"], "revision": doc["revision"], "path": entry["path"],
                        "knowledgeType": doc["knowledgeType"], "workstations": doc["transfer"]["workstations"],
                        "usage": doc["usage"], "processing": doc["processing"], "sameSource": same,
                        "line": _line(doc, same)})
    invalid = _invalid(store["entries"])
    return {"ok": True, "command": "knowledge search", **_public(store),
            "filters": {"type": knowledge_type, "workstation": workstation, "usage": usage, "text": text,
                        "include_retired": include_retired},
            "count": len(results), "results": results, "invalid": invalid,
            "same_source_scope": "latest valid revision per card" + ("" if include_retired else ", retired excluded"),
            "same_source_note": SAME_SOURCE_NOTE, "passed": False if invalid else None}


def _check_source(root: Path, source: dict) -> dict:
    location = source["location"]
    result = {"sourceId": source["sourceId"], "location": location, "versionOrDate": source["versionOrDate"]}
    if not location.startswith(SOURCES + "/"):
        return {**result, "kind": "external", "status": "external_not_checked"}
    relative, _, position = location.partition("#")
    sources = (root / SOURCES).resolve()
    allowed = (root / SOURCES / source["sourceId"]).resolve()
    target = (root / relative).resolve()
    result.update(kind="local", path=str(target), position=position or None)
    if allowed.parent != sources or not target.is_relative_to(allowed) or target == allowed:
        return {**result, "status": "outside_source_dir"}
    return {**result, "status": "present" if target.is_file() else "missing"}


def run_knowledge_show(project: str, card_id: str, revision: int | None = None) -> dict:
    root = _project(project)
    store = _load_store(root)
    matches = {entry["revision"]: entry for entry in store["entries"] if entry["cardId"] == card_id}
    if not matches:
        detail = f" ({store['hint']})" if store["store_status"] != "present" else ""
        raise ValueError(f"Knowledge card not found: {card_id}{detail}")
    if revision is not None and revision not in matches:
        raise ValueError(f"Revision {revision} of {card_id} not found; available: {sorted(matches)}")
    entry = matches[revision if revision is not None else max(matches)]
    sources = []
    if not entry["errors"]:
        sources = [_check_source(root, source) for source in entry["doc"]["evidence"]["sources"]]
    missing = [item["location"] for item in sources if item["status"] in ("missing", "outside_source_dir")]
    return {"ok": True, "command": "knowledge show", **_public(store), "path": entry["path"],
            "cardId": card_id, "revision": entry["revision"], "available_revisions": sorted(matches),
            "card": entry["doc"], "errors": entry["errors"], "sources": sources, "missing": missing,
            "sources_checked": not entry["errors"], "passed": not (entry["errors"] or missing)}
