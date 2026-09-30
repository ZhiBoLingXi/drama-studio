"""Turn saved mali-story MCP responses into remote-receipts and a verified local text cache.

Passing proves only that the saved response files parse, that every receipt passes
`contract-check remote-receipt`, that receipts and the cache manifest are append-only, and that
cached text hashes to the fingerprint the saved read responses declare. The tool never calls
mali-story, so it never proves a response is genuine, that a candidate exists remotely, or that
anything was adopted; a receipt or cache entry is never adoption evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

try:
    from .contract_check import check_contract
except ImportError:  # loaded as a top-level module
    from contract_check import check_contract

SCHEMA = "drama-studio/remote-receipt/v0"
MANIFEST = "drama-studio/cache-manifest/v0"
LOCK_TIMEOUT = 5.0
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
FINGERPRINT = re.compile(r"sha256:[a-f0-9]{64}")
KINDS = ("research", "adaptation_options", "characters", "series_outline", "episode_outline", "episode_draft", "review")
READ_KEYS = ("fingerprint", "coveredRange")
EXPECTED = {"save_story_artifact": (("record",),), "get_story_artifact": (("record",),),
            "read_story_artifact": (READ_KEYS,), "get_writing_context": (("snapshotId",),),
            "list_story_artifacts": (("records",), ("items",)), "prepare_story_context": ()}
TOOL_RESULT = "mali-tool-result/v1"
RECONCILERS = ("get_story_artifact", "list_story_artifacts", "save_story_artifact")
WRITES = ("save_story_artifact",)  # unknowns reconcilable by requestId; prepare_story_context has no lookup


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


def atomic_write(path: Path, content: bytes) -> None:
    """Temp file in the same folder + os.replace; used only for the manifest, under manifest_lock."""
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


def publish_new(path: Path, content: bytes) -> bool:
    """Exclusively create `path` (temp file + os.link). False when another writer got there first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            return False
        return True
    finally:
        os.unlink(temp)


@contextmanager
def manifest_lock(folder: Path):
    """O_EXCL lock around manifest read-modify-write; a lock left behind is reported, never removed."""
    folder.mkdir(parents=True, exist_ok=True)
    lock, deadline = folder / "manifest.json.lock", time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError(f"{lock} still exists after {LOCK_TIMEOUT}s: another receipt cache may be running. "
                                 "If none is, delete that lock file by hand and retry") from None
            time.sleep(0.05)
    try:
        os.write(handle, str(os.getpid()).encode())
        os.close(handle)
        yield
    finally:
        os.unlink(lock)


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


def _refused(base: dict, reason: str) -> dict:
    return {**base, "warnings": [], "passed": False, "status": "reconcile_refused", "path": None, "error": reason + "; nothing written"}


def _slot(doc: dict) -> str | None:
    ref = doc.get("localRef") or {}
    return ref["id"][5:] if ref.get("kind") == "remote_artifact" and str(ref.get("id", "")).startswith("slot:") else None


def _reconcile_check(operation: str, reconciles: str, target, doc: dict, parsed: dict | None,
                     request: dict) -> tuple[str | None, str]:
    """Return (refusal reason, enforcement note) for a receipt that claims to resolve `reconciles`."""
    if not isinstance(target, dict) or check_contract("remote-receipt", target):
        return f"local receipt {reconciles!r} fails contract-check; it cannot be reconciled", ""
    if target["operation"] != "save_story_artifact" or target["outcome"] != "unknown":
        return f"{reconciles!r} is a {target['operation']} with outcome {target['outcome']!r}; only an unknown save is reconciled", ""
    if doc["remote"]["projectId"] != target["remote"]["projectId"]:
        return f"projectId {doc['remote']['projectId']!r} is not the unknown save's {target['remote']['projectId']!r}", ""
    if operation == "save_story_artifact" and doc["inputFingerprint"] != target.get("inputFingerprint"):
        return "the re-send input differs from the unknown save (inputFingerprint); only an identical re-send may reconcile it", ""
    if doc["outcome"] != "confirmed":
        if operation == "save_story_artifact":  # the attempt is recorded, but only a confirmed re-send resolves the target
            return None, {"check": f"identical re-send with outcome {doc['outcome']!r}; does not resolve {reconciles!r}"}
        return f"this {operation} outcome is {doc['outcome']!r}; only a confirmed response can resolve an unknown", ""
    found = _field(parsed["data"].get("record"), "requestId")
    if operation == "save_story_artifact":
        if found != reconciles:
            return f"the re-send response record.requestId is {found!r}, not {reconciles!r}", ""
        return None, {"check": "identical re-send; inputFingerprint and record.requestId matched (S)", "observedRequestId": found}
    if operation == "get_story_artifact":
        if found != reconciles:
            return f"get_story_artifact record.requestId is {found!r}, not {reconciles!r}. Check the next revision in the slot", ""
        return None, {"check": "record.requestId matched (S)", "observedRequestId": found}
    slot = _field(request, "slot")
    if slot is None or slot != _slot(target):
        return f"list_story_artifacts must be filtered by the unknown save's slot {_slot(target)!r}; --input has {slot!r}", ""
    expected = _notes(target).get("expectedRevision")
    data = parsed["data"]
    rows = data.get("records") if isinstance(data.get("records"), list) else data.get("items")
    match = next((row for row in rows or [] if isinstance(row, dict) and row.get("slot") == slot
                  and _is_int(row.get("revision")) and _is_int(expected) and row["revision"] > expected
                  and row.get("inputSnapshotId") == target["remote"]["inputSnapshotId"]), None)
    if match is None:
        return (f"no listed row in slot {slot!r} has revision > {expected!r} and inputSnapshotId "
                f"{target['remote']['inputSnapshotId']!r}: the save probably did not land. Re-send the identical save "
                f"with the same request_id {reconciles!r} (server replay is idempotent) and record it with --reconciles {reconciles}"), ""
    return None, {"check": "host matched a newer listed revision in the same project, slot and snapshot; list rows carry no requestId (M)",
                  "matchedArtifactId": match.get("id"), "matchedRevision": match["revision"]}


def record_receipt(project: str, response_path: str, operation: str, request_id: str, input_path: str,
                   reconciles: str | None = None) -> dict:
    drama = drama_dir(project)
    safe_id(request_id, "requestId")
    if operation not in EXPECTED:
        raise ValueError(f"Unknown operation {operation!r}")
    request = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("--input must be the JSON object sent to the MCP tool")
    base = {"ok": True, "enforcement": "S", "remote_verified": False, "adoption_verified": False, "warnings": []}
    target = None
    if reconciles is not None:
        safe_id(reconciles, "--reconciles")
        if operation not in RECONCILERS:
            raise ValueError(f"--reconciles is recorded from {', '.join(RECONCILERS)} only")
        target_path = drama / "receipts" / f"{reconciles}.json"
        if not target_path.is_file():
            raise ValueError(f"No local receipt {reconciles!r} to reconcile")
        target = json.loads(target_path.read_text(encoding="utf-8"))
    declared = _field(request, "request_id", "requestId")
    if operation == "save_story_artifact" and reconciles is not None:
        if declared != reconciles:  # an identical re-send keeps the original request_id (S)
            return _refused(base, f"a re-send must carry the original request_id {reconciles!r}; --input has {declared!r}")
    elif declared is not None and declared != request_id:
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
    if operation == "save_story_artifact":
        slot = _field(request, "slot")
        if slot is not None:
            doc["localRef"] = {"kind": "remote_artifact", "id": f"slot:{slot}", "revision": None}
        notes.update(kind=_field(request, "kind"), episodeRef=_field(request, "episode_ref", "episodeRef"),
                     expectedRevision=_field(request, "expected_revision", "expectedRevision"))
    if reconciles is not None:
        doc["localRef"] = {"kind": "remote_receipt", "id": reconciles, "revision": None}
        reason, check = _reconcile_check(operation, reconciles, target, doc, parsed, request)
        if reason:
            return _refused(base, reason)
        notes.update(reconciles=reconciles, **(check if isinstance(check, dict) else {"check": check}))
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
    content = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if not path.exists() and publish_new(path, content):
        return {**base, "passed": True, "status": "written", "path": str(path), "receipt": doc}
    try:  # present before us, or a concurrent writer won the race; never trust it unchecked
        existing = json.loads(path.read_text(encoding="utf-8"))
        problems = check_contract("remote-receipt", existing) if isinstance(existing, dict) else ["not a JSON object"]
    except (UnicodeDecodeError, ValueError) as error:
        existing, problems = None, [f"not JSON: {error}"]
    if problems:
        return {**base, "warnings": [], "passed": False, "status": "invalid_existing", "path": str(path),
                "error": f"existing receipt {path.name} is invalid ({'; '.join(problems)}); inspect with receipt show. Nothing written"}
    old, new = str(existing.get("inputFingerprint")), doc["inputFingerprint"]
    if old == new and existing.get("outcome") != outcome:
        return {**base, "warnings": [], "passed": False, "status": "outcome_differs", "path": str(path),
                "existingOutcome": existing.get("outcome"), "newOutcome": outcome,
                "error": f"requestId {request_id} is recorded as {existing.get('outcome')!r}; this response says {outcome!r}. "
                         f"Receipts are append-only: record it under a new --request-id (e.g. {request_id}.resend-1) with "
                         f"--reconciles {request_id}; only a confirmed re-send resolves the unknown."}
    if old == new:
        return {**base, "passed": True, "status": "replay", "path": str(path), "receipt": existing}
    return {**base, "warnings": [], "passed": False, "status": "conflict", "path": str(path),
            "existingInputFingerprint": old[7:19], "newInputFingerprint": new[7:19],
            "error": f"requestId {request_id} already recorded with inputFingerprint {old[7:19]}…; new input is {new[7:19]}…. Existing receipt kept; never reuse a requestId for different input."}


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
    by_id = {doc["requestId"]: doc for doc in valid}
    verified, host_judged = set(), set()
    for doc in list(valid):  # only confirmed reconcilers count; re-check their stored evidence
        if not (doc.get("localRef", {}).get("kind") == "remote_receipt" and doc["outcome"] == "confirmed" and doc["operation"] in RECONCILERS):
            continue
        target_id, notes = doc["localRef"]["id"], _notes(doc)
        target = by_id.get(target_id)
        if target is None or target["operation"] != "save_story_artifact" or target["outcome"] != "unknown":
            reason = f"reconciles {target_id!r}, which is not a valid unknown save receipt"
        elif doc["remote"]["projectId"] != target["remote"]["projectId"]:
            reason = f"projectId {doc['remote']['projectId']!r} is not the reconciled save's {target['remote']['projectId']!r}"
        elif doc["operation"] == "list_story_artifacts":
            reason = None if notes.get("matchedArtifactId") and _is_int(notes.get("matchedRevision")) else "list reconciliation names no matched row"
        else:
            reason = None if notes.get("observedRequestId") == target_id else f"notes.observedRequestId {notes.get('observedRequestId')!r} is not {target_id!r}"
        if reason:
            invalid.append({"path": str(drama / "receipts" / f"{doc['requestId']}.json"), "errors": [f"reconciliation not counted: {reason}"]})
            continue
        (host_judged if doc["operation"] == "list_story_artifacts" else verified).add(target_id)
    items, read_only, unreconcilable = [], [], []
    for doc in valid:
        request_id = doc["requestId"]
        if doc["outcome"] != "unknown" or request_id in verified or request_id in host_judged:
            continue
        if doc["operation"] == "save_story_artifact" and doc.get("localRef", {}).get("kind") == "remote_receipt":
            continue  # an unconfirmed re-send attempt: its target stays pending on its own
        attempts = sorted(d["requestId"] for d in valid if d["operation"] == "save_story_artifact" and d["outcome"] != "confirmed"
                          and d.get("localRef", {}).get("kind") == "remote_receipt" and d["localRef"]["id"] == request_id)
        if doc["operation"] not in WRITES:
            dead_end = doc["operation"] == "prepare_story_context"
            (unreconcilable if dead_end else read_only).append({
                "requestId": request_id, "operation": doc["operation"], "projectId": doc["remote"]["projectId"], "retryAllowed": False,
                "note": "prepare_story_context has no requestId lookup; re-read the context state (get_writing_context) before any retry"
                        if dead_end else "re-read; no write to reconcile"})
            continue
        slot = _slot(doc)
        project_id, expected = doc["remote"]["projectId"], _notes(doc).get("expectedRevision")
        newer = f"revision > {expected}" if _is_int(expected) else "each listed revision, newest first"
        list_args = {"project_id": project_id, **({"slot": slot} if slot else {})}
        items.append({"requestId": request_id, "operation": doc["operation"], "projectId": project_id, "slot": slot,
                      "expectedRevision": expected, "retryAllowed": False, "unconfirmedAttempts": attempts, "steps": [
                          {"tool": "list_story_artifacts", "args": list_args, "why": "find revisions saved after the lost call"},
                          {"tool": "get_story_artifact", "args": {"project_id": project_id, "artifact_id": f"<id of {newer}>"},
                           "check": f"record.requestId == {request_id!r}"},
                          {"command": f"drama_tools.py receipt record <project> <get-response.json> --operation get_story_artifact "
                                      f"--request-id <new-read-id> --input <get-input.json> --reconciles {request_id}"}]})
    unknown = {doc["requestId"] for doc in valid if doc["outcome"] == "unknown"}
    return {"ok": True, "pending": items, "read_only_unknown": read_only, "unreconcilable_unknown": unreconcilable, "resolved_verified": sorted(verified & unknown),
            "resolved_host_judged": sorted((host_judged - verified) & unknown), "invalid": invalid,
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


def _chunk(data: dict, name: str) -> dict:
    span = data.get("coveredRange") if isinstance(data.get("coveredRange"), dict) else {}
    fields = {"projectId": data.get("projectId"), "artifactId": data.get("artifactId"), "revision": data.get("revision"),
              "fingerprint": data.get("fingerprint"), "totalCharacters": data.get("totalCharacters"),
              "text": data.get("text"), "from": span.get("from"), "to": span.get("to"), "nextOffset": data.get("nextOffset")}
    kinds = {"projectId": str, "artifactId": str, "fingerprint": str, "text": str}
    for key, value in fields.items():
        if key == "nextOffset" and value is None:
            continue
        if not (isinstance(value, kinds[key]) if key in kinds else _is_int(value)):
            raise ValueError(f"{name}: read_story_artifact chunk has no valid {key}")
    if not FINGERPRINT.fullmatch(fields["fingerprint"]):
        raise ValueError(f"{name}: fingerprint is not sha256:<hex>")
    safe_id(fields["artifactId"], "artifactId")
    return fields


def _refuse(error: str) -> dict:
    return {"ok": True, "passed": False, "status": "refused", "error": error + "; nothing written",
            "remote_verified": False, "adoption_verified": False}


def _join(chunks: list[dict]) -> tuple[str | None, str | None]:
    """Return (text, None) for a complete verified sequence, else (None, reason)."""
    identity = {(c["projectId"], c["artifactId"], c["revision"], c["fingerprint"], c["totalCharacters"]) for c in chunks}
    if len(identity) > 1:
        return None, "chunks disagree on projectId, artifactId, revision, fingerprint or totalCharacters"
    # a read at offset == totalCharacters returns an empty chunk; it adds no text, so drop it
    chunks = [c for c in chunks if not (c["from"] == c["to"] == c["totalCharacters"] and c["text"] == "")] or chunks
    by_start: dict[int, dict] = {}
    for chunk in chunks:
        if len(chunk["text"]) != chunk["to"] - chunk["from"]:
            return None, f"chunk at {chunk['from']} holds {len(chunk['text'])} code points but covers {chunk['from']}-{chunk['to']}"
        seen = by_start.setdefault(chunk["from"], chunk)
        if seen != chunk:
            return None, f"two different chunks start at offset {chunk['from']}"
    ordered, expected = [by_start[key] for key in sorted(by_start)], 0
    for index, chunk in enumerate(ordered):
        if chunk["from"] != expected:
            return None, f"gap: expected a chunk at offset {expected}, next starts at {chunk['from']}"
        expected = chunk["to"]
        if index < len(ordered) - 1 and chunk["nextOffset"] != chunk["to"]:
            return None, f"chunk at {chunk['from']} says nextOffset {chunk['nextOffset']}, not {chunk['to']}"
    last = ordered[-1]
    if last["nextOffset"] is not None or last["to"] != last["totalCharacters"]:
        return None, f"final chunk missing: read stops at {last['to']} of {last['totalCharacters']} (nextOffset {last['nextOffset']})"
    text = "".join(chunk["text"] for chunk in ordered)
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != last["fingerprint"]:
        return None, f"joined text hashes to {digest[:19]}…, server fingerprint is {last['fingerprint'][:19]}…"
    return text, None


def cache(project: str, response_paths: list[str], slot: str | None = None, kind: str | None = None,
          episode_ref: str | None = None) -> dict:
    """Cache one artifact revision from a full read_story_artifact sequence (verified) or a get (unverified)."""
    drama = drama_dir(project)
    chunks, records = [], {}
    for name in response_paths:
        parsed = _parse(json.loads(Path(name).read_text(encoding="utf-8")), (READ_KEYS, ("record",)), [])
        if not parsed["ok"]:
            raise ValueError(f"{name}: the saved call failed ({parsed['errorCode']}); nothing to cache")
        if isinstance(parsed["data"].get("record"), dict):
            record = parsed["data"]["record"]
            records[canonical_json(record)] = record
        else:
            chunks.append(_chunk(parsed["data"], name))
    if len(records) > 1:
        raise ValueError("Pass at most one get_story_artifact response per call")
    record = next(iter(records.values()), None)
    if record is not None:
        if not (isinstance(record.get("body"), str) and _is_int(record.get("revision"))):
            raise ValueError("get_story_artifact record has no body or revision")
        safe_id(record.get("id"), "artifactId")
        given = {"slot": slot, "kind": kind, "episodeRef": episode_ref}
        clash = [key for key, value in given.items() if value is not None and value != record.get(key)]
        if clash:
            raise ValueError(f"--{', --'.join(clash)} disagree with the get_story_artifact record")
        slot, kind, episode_ref = record.get("slot"), record.get("kind"), record.get("episodeRef")
    if not slot or not kind:
        raise ValueError("slot and kind are unknown: add a get_story_artifact response or pass --slot and --kind")
    if kind not in KINDS:
        raise ValueError(f"kind {kind!r} not in {KINDS}")
    if kind in ("episode_outline", "episode_draft") and not episode_ref:
        raise ValueError(f"{kind} needs an episodeRef (--episode-ref)")
    warnings = []
    if chunks:
        text, reason = _join(chunks)
        if reason:
            return _refuse(reason)
        artifact, revision, server = chunks[0]["artifactId"], chunks[0]["revision"], chunks[0]["fingerprint"]
        if record is not None and (record.get("id"), record.get("revision"), record.get("body")) != (artifact, revision, text):
            return _refuse("the get_story_artifact record is not the same artifact revision and text as the read chunks")
        operation = "read_story_artifact"
    else:
        text, artifact, revision, server = record["body"], record["id"], record["revision"], None
        operation = "get_story_artifact"
        warnings.append("get_story_artifact carries no full-text fingerprint: cached as verified=false; read the artifact with read_story_artifact to nextOffset null to verify")
    content = text.encode("utf-8")
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    verified = server is not None and digest == server
    name = f"{artifact}@r{revision}.md"
    folder = drama / "cache"
    path, manifest_path, rel = folder / name, folder / "manifest.json", f".drama/cache/{name}"
    entry = {"path": rel, "artifactId": artifact, "slot": slot, "kind": kind, "episodeRef": episode_ref,
             "revision": revision, "sha256": digest, "serverFingerprint": server, "verified": verified,
             "operation": operation, "readAt": _now()}
    with manifest_lock(folder):
        manifest = {"schemaVersion": MANIFEST, "entries": []}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("schemaVersion") != MANIFEST or not isinstance(manifest.get("entries"), list):
                raise ValueError(f"{manifest_path} is not a {MANIFEST} manifest")
        same = [item for item in manifest["entries"] if isinstance(item, dict) and item.get("path") == rel]
        for item in same:
            clash = [f"{key} {item.get(key)!r} (manifest) vs {entry[key]!r} (this call)"
                     for key in ("slot", "kind", "episodeRef") if item.get(key) != entry[key]]
            if clash:
                return _refuse(f"{rel} is already cached with different metadata: " + "; ".join(clash))
        status = "written"
        if path.exists() or not publish_new(path, content):
            if path.read_bytes() != content:
                return _refuse(f"{path} already exists with different bytes")
            status = "unchanged"
        existing = next((item for item in same if item.get("verified") == verified), None)
        if not verified:  # never shadow a verified read with a later unverified entry for the same bytes
            existing = next((item for item in same if item.get("verified") is True and item.get("sha256") == digest), existing)
        if existing is None:
            manifest["entries"].append(entry)
            atomic_write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"ok": True, "passed": True, "status": status, "path": str(path), "entry": existing or entry,
            "manifestAppended": existing is None, "verified": verified, "warnings": warnings,
            "remote_verified": False, "adoption_verified": False}


def run_receipt(args) -> dict:
    """Dispatch `drama_tools.py receipt <subcommand>`; refusals return passed=False, input errors raise."""
    if args.receipt_command == "record":
        return record_receipt(args.project, args.response, args.operation, args.request_id, args.input_path, args.reconciles)
    if args.receipt_command == "pending":
        return pending(args.project)
    if args.receipt_command == "cache":
        return cache(args.project, args.responses, args.slot, args.kind, args.episode_ref)
    return show(args.project, args.request_id)
