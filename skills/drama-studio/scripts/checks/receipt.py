"""Turn saved mali-story MCP responses into remote-receipts and a verified local text cache.

Passing proves only that the saved response files parse, that every receipt passes
`contract-check remote-receipt`, that receipts and the cache manifest are append-only, and that
cached text hashes to the fingerprint the saved read responses declare. The tool never calls
mali-story, so it never proves a response is genuine, that a candidate exists remotely, or that
anything was adopted; a receipt or cache entry is never adoption evidence.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

try:
    from .contract_check import check_contract
except ImportError:  # loaded as a top-level module
    from contract_check import check_contract

SCHEMA = "drama-studio/remote-receipt/v0"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
READ_KEYS = ("fingerprint", "coveredRange")
EXPECTED = {"save_story_artifact": (("record",),), "get_story_artifact": (("record",),),
            "read_story_artifact": (READ_KEYS,), "get_writing_context": (("snapshotId",),),
            "list_story_artifacts": (("records",), ("items",)), "prepare_story_context": ()}
TOOL_RESULT = "mali-tool-result/v1"


class Unparseable(ValueError):
    """The response bytes could not be read at all; for a sent request the outcome is unknown."""


def _clean(value):
    return {k: v for k, v in value.items() if not k.startswith("_")} if isinstance(value, dict) else value


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _code(error) -> str | None:
    return error.get("code") if isinstance(error, dict) and isinstance(error.get("code"), str) else None


def _data(data, keysets, shape: list[str], status) -> dict:
    if keysets and not (isinstance(data, dict) and any(all(key in data for key in keys) for keys in keysets)):
        wanted = " or ".join("+".join(keys) for keys in keysets)
        raise ValueError(f"Response data does not match this operation (expected keys {wanted}); was the right file or --operation given?")
    return {"ok": True, "data": data, "httpStatus": status, "errorCode": None, "retrySafe": None, "shape": " > ".join(shape)}


def _error(code, status, retry_safe, shape: list[str]) -> dict:
    return {"ok": False, "data": None, "httpStatus": status, "errorCode": code,
            "retrySafe": retry_safe if isinstance(retry_safe, bool) else None, "shape": " > ".join(shape)}


def _parse(value, keysets, shape: list[str], status=None) -> dict:
    value = _clean(value) if not shape else value
    if not isinstance(value, dict):
        raise ValueError("Unrecognised response shape: expected a JSON object")
    if isinstance(value.get("content"), list):
        if isinstance(value.get("structuredContent"), dict):
            return _parse(value["structuredContent"], keysets, shape + ["CallToolResult.structuredContent"])
        text = next((item.get("text") for item in value["content"] if isinstance(item, dict) and item.get("type") == "text"), None)
        try:
            inner = json.loads(text)
        except (TypeError, ValueError) as error:
            raise Unparseable("CallToolResult text is missing or not JSON") from error
        shape = shape + ["CallToolResult.text"]
        if value.get("isError") and isinstance(inner, dict) and inner.get("error") is True:  # unexpectedMcpFailure text
            return _error(_code(inner), None, None, shape)
        return _parse(inner, keysets, shape)
    if value.get("schemaVersion") == TOOL_RESULT:
        transport = value.get("transport") if isinstance(value.get("transport"), dict) else {}
        status = transport.get("status") if _is_int(transport.get("status")) else None
        if value.get("ok") is True:
            return _data(value.get("data"), keysets, shape + [TOOL_RESULT], status)
        recovery = value.get("recovery") if isinstance(value.get("recovery"), dict) else {}
        return _error(_code(value.get("error")), status, recovery.get("retrySafe"), shape + [TOOL_RESULT])
    if _is_int(value.get("status")) and "body" in value:
        shape = shape + ["dispatch{status,body}"]
        if value["status"] >= 400:
            body = value["body"] if isinstance(value["body"], dict) else {}
            return _error(_code(body.get("error")) or _code(body), value["status"], None, shape)
        return _parse(value["body"], keysets, shape, value["status"])
    if "data" in value and "error" in value:
        shape = shape + ["rest{requestId,data,error}"]
        if value["error"] is not None:
            return _error(_code(value["error"]), status, None, shape)
        return _data(value["data"], keysets, shape, status)
    if keysets and any(all(key in value for key in keys) for keys in keysets):
        return _data(value, keysets, shape + ["bare data"], status)
    raise ValueError("Unrecognised response shape: not a CallToolResult, mali-tool-result/v1, dispatch envelope, REST envelope or bare data")


def parse_response(value, operation: str) -> dict:
    """Return ok, data, httpStatus, errorCode, retrySafe and the recognised shape path."""
    if operation not in EXPECTED:
        raise ValueError(f"Unknown operation {operation!r}")
    return _parse(value, EXPECTED[operation], [])


def outcome_of(parsed: dict | None) -> tuple[str, bool]:
    """Map a parsed response (None = missing or unreadable) to (outcome, retryAllowed)."""
    if parsed is None:
        return "unknown", False
    if parsed["ok"]:
        return "confirmed", False
    status, code = parsed.get("httpStatus"), parsed.get("errorCode")
    if status == 409 or code == "VERSION_CONFLICT":
        return "rejected_conflict", False
    if code == "MCP_OUTCOME_UNKNOWN" or (status is not None and status >= 500):
        return "unknown", False
    return "rejected_other", parsed.get("retrySafe") is True


def canonical_json(value) -> bytes:
    return json.dumps(_clean(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def input_fingerprint(value) -> str:
    """Local conflict key only; differs from mali-story's server-side requestFingerprint."""
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def safe_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} {value!r} is not a safe identifier ({SAFE_ID.pattern}); it becomes a file name")
    return value


def drama_dir(project: str) -> Path:
    path = Path(project).expanduser().absolute() / ".drama"
    if not path.is_dir():
        raise ValueError(f"{path} does not exist; run init-project first")
    return path


def write_new(path: Path, content: bytes) -> None:
    """Atomically create a file; callers check existence first and never overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _field(mapping, *keys):
    return next((mapping[key] for key in keys if isinstance(mapping, dict) and mapping.get(key) is not None), None)


def _load_response(path: str, operation: str) -> tuple[dict | None, str]:
    """Return (parsed, evidence); parsed is None when the file is missing, empty or unreadable."""
    file = Path(path)
    if not file.is_file():
        return None, f"response file missing: {file.name}"
    raw = file.read_bytes()
    if not raw.strip():
        return None, f"response file empty: {file.name}"
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, f"response file is not JSON: {file.name}"
    try:
        parsed = parse_response(value, operation)
    except Unparseable as error:
        return None, f"response unreadable: {error}"
    status = f"; HTTP {parsed['httpStatus']}" if parsed["httpStatus"] is not None else ""
    state = "ok" if parsed["ok"] else f"error {parsed['errorCode'] or 'without code'}"
    return parsed, f"saved response {file.name}: {parsed['shape']}; {state}{status}"


def _receipts(drama: Path) -> list[tuple[Path, object]]:
    folder = drama / "receipts"
    items = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            items.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (UnicodeDecodeError, ValueError) as error:
            items.append((path, error))
    return items


def _remote(operation: str, parsed: dict | None, request: dict) -> dict:
    data = parsed["data"] if parsed and parsed["ok"] else None
    record = data.get("record") if isinstance(data, dict) and isinstance(data.get("record"), dict) else None
    source = record if record is not None else data if operation == "read_story_artifact" else None
    project = _field(record or data or {}, "projectId") or _field(request, "projectId", "project_id")
    if project is None:
        raise ValueError("projectId is neither in the response nor in --input (projectId|project_id)")
    if operation == "get_writing_context" and isinstance(data, dict):
        snapshot = data.get("snapshotId")
    else:
        snapshot = _field(source or {}, "inputSnapshotId") or _field(request, "inputSnapshotId", "input_snapshot_id")
    artifact = _field(source or {}, "id" if record is not None else "artifactId")
    revision = source.get("revision") if isinstance(source, dict) and _is_int(source.get("revision")) else None
    return {"projectId": project, "artifactId": artifact, "revision": revision, "inputSnapshotId": snapshot}


def record_receipt(project: str, response_path: str, operation: str, request_id: str, input_path: str,
                   reconciles: str | None = None) -> dict:
    drama = drama_dir(project)
    safe_id(request_id, "requestId")
    if operation not in EXPECTED:
        raise ValueError(f"Unknown operation {operation!r}")
    request = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("--input must be the JSON object sent to the MCP tool")
    declared = _field(request, "request_id", "requestId")
    if declared is not None and declared != request_id:
        raise ValueError(f"--input declares request_id {declared!r}, not {request_id!r}")
    parsed, evidence = _load_response(response_path, operation)
    outcome, retry = outcome_of(parsed)
    remote = _remote(operation, parsed, request)
    if outcome != "confirmed":
        remote.update(artifactId=None, revision=None)
    notes: dict = {}
    doc = {"schemaVersion": SCHEMA, "operation": operation, "requestId": request_id,
           "inputFingerprint": input_fingerprint(request), "remote": remote, "outcome": outcome,
           "retryAllowed": retry, "observedAt": _now(), "evidence": evidence}
    base = {"ok": True, "enforcement": "S", "remote_verified": False, "adoption_verified": False, "warnings": []}
    if operation == "save_story_artifact":
        slot = _field(request, "slot")
        if slot is not None:
            doc["localRef"] = {"kind": "remote_artifact", "id": f"slot:{slot}", "revision": None}
        notes.update(kind=_field(request, "kind"), episodeRef=_field(request, "episode_ref", "episodeRef"),
                     expectedRevision=_field(request, "expected_revision", "expectedRevision"))
    if reconciles is not None:
        safe_id(reconciles, "--reconciles")
        if operation not in ("get_story_artifact", "list_story_artifacts"):
            raise ValueError("--reconciles is recorded from get_story_artifact or list_story_artifacts only")
        if not (drama / "receipts" / f"{reconciles}.json").is_file():
            raise ValueError(f"No local receipt {reconciles!r} to reconcile")
        doc["localRef"] = {"kind": "remote_receipt", "id": reconciles, "revision": None}
        if operation == "get_story_artifact":
            found = _field(parsed["data"].get("record"), "requestId") if outcome == "confirmed" else None
            if found != reconciles:
                return {**base, "passed": False, "status": "reconcile_mismatch", "path": None,
                        "error": f"get_story_artifact record.requestId is {found!r}, not {reconciles!r}; nothing written. Check the next revision in the slot."}
            notes.update(reconciles=reconciles, check="record.requestId matched (S)")
        else:
            notes.update(reconciles=reconciles, check="host matched a listed revision; list rows carry no requestId (M)")
    if notes:
        doc["notes"] = json.dumps(notes, ensure_ascii=False)
    errors = check_contract("remote-receipt", doc)
    if errors:
        raise ValueError("Generated receipt fails contract-check: " + "; ".join(errors))
    if operation == "save_story_artifact" and remote["inputSnapshotId"] is not None:
        contexts = {item["remote"].get("inputSnapshotId") for _, item in _receipts(drama) if isinstance(item, dict)
                    and item.get("operation") == "get_writing_context" and item.get("outcome") == "confirmed" and isinstance(item.get("remote"), dict)}
        if remote["inputSnapshotId"] not in contexts:
            base["warnings"].append("inputSnapshotId matches no local confirmed get_writing_context receipt; record that read before trusting this save's provenance")
    path = drama / "receipts" / f"{request_id}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        old, new = str(existing.get("inputFingerprint")), doc["inputFingerprint"]
        if old == new:
            return {**base, "passed": True, "status": "replay", "path": str(path), "receipt": existing}
        return {**base, "passed": False, "status": "conflict", "path": str(path),
                "existingInputFingerprint": old[7:19], "newInputFingerprint": new[7:19],
                "error": f"requestId {request_id} already recorded with inputFingerprint {old[7:19]}…; new input is {new[7:19]}…. Existing receipt kept; never reuse a requestId for different input."}
    write_new(path, (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {**base, "passed": True, "status": "written", "path": str(path), "receipt": doc}


def _notes(doc: dict) -> dict:
    try:
        notes = json.loads(doc.get("notes") or "{}")
    except ValueError:
        return {}
    return notes if isinstance(notes, dict) else {}


def pending(project: str) -> dict:
    """List unknown receipts that no reconciliation receipt resolves yet, with the calls to make."""
    drama = drama_dir(project)
    valid, invalid = [], []
    for path, doc in _receipts(drama):
        errors = [f"not JSON: {doc}"] if isinstance(doc, Exception) else check_contract("remote-receipt", doc)
        if not errors and path.stem != doc["requestId"]:
            errors = [f"file name does not match requestId {doc['requestId']!r}"]
        (invalid.append({"path": str(path), "errors": errors}) if errors else valid.append(doc))
    reconciled = {doc["localRef"]["id"] for doc in valid if doc.get("localRef", {}).get("kind") == "remote_receipt"}
    items, resolved = [], []
    for doc in valid:
        if doc["outcome"] != "unknown":
            continue
        request_id = doc["requestId"]
        if request_id in reconciled:
            resolved.append(request_id)
            continue
        ref = doc.get("localRef") or {}
        slot = ref["id"][5:] if ref.get("kind") == "remote_artifact" and ref.get("id", "").startswith("slot:") else None
        project_id, expected = doc["remote"]["projectId"], _notes(doc).get("expectedRevision")
        newer = f"revision > {expected}" if _is_int(expected) else "each listed revision, newest first"
        list_args = {"project_id": project_id, **({"slot": slot} if slot else {})}
        items.append({"requestId": request_id, "operation": doc["operation"], "projectId": project_id, "slot": slot,
                      "expectedRevision": expected, "retryAllowed": False, "steps": [
                          {"tool": "list_story_artifacts", "args": list_args, "why": "find revisions saved after the lost call"},
                          {"tool": "get_story_artifact", "args": {"project_id": project_id, "artifact_id": f"<id of {newer}>"},
                           "check": f"record.requestId == {request_id!r}"},
                          {"command": f"drama_tools.py receipt record <project> <get-response.json> --operation get_story_artifact "
                                      f"--request-id <new-read-id> --input <get-input.json> --reconciles {request_id}"}]})
    return {"ok": True, "pending": items, "resolved": sorted(resolved), "invalid": invalid,
            "note": "Never retry an unknown call with a new requestId; reconcile first.",
            "remote_verified": False, "adoption_verified": False}


def show(project: str, request_id: str) -> dict:
    path = drama_dir(project) / "receipts" / f"{safe_id(request_id, 'requestId')}.json"
    if not path.is_file():
        raise ValueError(f"No receipt {request_id!r} in {path.parent}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    errors = check_contract("remote-receipt", doc)
    return {"ok": True, "path": str(path), "passed": not errors, "errors": errors, "receipt": doc,
            "enforcement": "S", "remote_verified": False, "adoption_verified": False}
