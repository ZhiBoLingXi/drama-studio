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

from contract_check import check_contract

SCHEMA = "drama-studio/remote-receipt/v0"
MANIFEST_V0 = "drama-studio/cache-manifest/v0"
MANIFEST = "drama-studio/cache-manifest/v1"  # written since v1.2 (#34); a v0 manifest and its entries stay readable
MANIFESTS = (MANIFEST_V0, MANIFEST)
LOCK_TIMEOUT = 5.0
FILE_MODE = 0o644  # published receipts, cache files and the manifest
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
FINGERPRINT = re.compile(r"sha256:[a-f0-9]{64}")
KINDS = ("research", "adaptation_options", "characters", "series_outline", "episode_outline", "episode_draft", "review")
READ_KEYS = ("fingerprint", "coveredRange")
# mali-story v0.20.0 page tools (#34): data keys of each success result, as page-version-service.ts returns them
PAGE_READ_KEYS = ("pageId", "fingerprint", "coveredRange")
PAGE_WRITES = ("create_page", "update_page", "restore_page", "label_page_revision")
PAGE_OPS = (*PAGE_WRITES, "read_page", "list_page_revisions")
PAGE_REQUEST_IDS = ("create_page", "update_page", "restore_page")  # label_page_revision takes no request_id
EXPECTED = {"save_story_artifact": (("record",),), "get_story_artifact": (("record",),),
            "read_story_artifact": (READ_KEYS,), "get_writing_context": (("snapshotId",),),
            "list_story_artifacts": (("records",), ("items",)), "prepare_story_context": (),
            "create_page": (("pageId", "revision", "fingerprint"),), "update_page": (("pageId", "revision", "previousRevision"),),
            "restore_page": (("pageId", "restoredFromRevision", "revision"),), "label_page_revision": (("revision", "label", "previousLabel"),),
            "read_page": (PAGE_READ_KEYS,), "list_page_revisions": (("revisions", "currentRevision"),)}
TOOL_RESULT = "mali-tool-result/v1"
RECONCILERS = ("get_story_artifact", "list_story_artifacts", "save_story_artifact", *PAGE_WRITES, "list_page_revisions")
WRITES = ("save_story_artifact", *PAGE_WRITES)  # unknowns reconcilable; prepare_story_context has no lookup
LABEL_NOTE = "版本标签只是给修订起的名字（mali-story：a label is not an approval），不是制作采用；工具也不把它当作采用证据"
SLOT_CHECK = "record.slot matched --input slot (S)"  # receipt note; without it a save receipt does not vouch for a slot
SLOT_SOURCES = ("host", "receipt", "record")  # weakest first; a manifest entry without slotSource counts as host
SLOT_FIELDS = ("slot", "kind", "episodeRef")  # what a stronger slot source corrects


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
    return {"ok": True, "data": data, "httpStatus": status, "errorCode": None, "retrySafe": None, "shape": " > ".join(shape),
            "errorDetails": None}


def _details(error) -> dict | None:
    """error.details as the server sent it (mali-story keeps it for VERSION_CONFLICT, IDEMPOTENCY_CONFLICT, PAGE_ALREADY_EXISTS)."""
    return error.get("details") if isinstance(error, dict) and isinstance(error.get("details"), dict) else None


def _error(code, status, retry_safe, shape: list[str], details=None) -> dict:
    return {"ok": False, "data": None, "httpStatus": status, "errorCode": code,
            "retrySafe": retry_safe if isinstance(retry_safe, bool) else None, "shape": " > ".join(shape), "errorDetails": details}


def _parse(value, keysets, shape: list[str], status=None) -> dict:
    value = _clean(value) if not shape else value
    if not isinstance(value, dict):
        raise ValueError("Unrecognised response shape: expected a JSON object")
    if isinstance(value.get("content"), list):
        result = _call_tool_result(value, keysets, shape)
        if value.get("isError") is True and result["ok"]:
            raise Unparseable("contradictory response: isError is true but the result says ok")
        return result
    if value.get("schemaVersion") == TOOL_RESULT:
        transport = value.get("transport") if isinstance(value.get("transport"), dict) else {}
        status = transport.get("status") if _is_int(transport.get("status")) else None
        if value.get("ok") is True:
            if status is not None and status >= 400:
                raise Unparseable(f"contradictory response: ok is true but transport.status is {status}")
            return _data(value.get("data"), keysets, shape + [TOOL_RESULT], status)
        recovery = value.get("recovery") if isinstance(value.get("recovery"), dict) else {}
        return _error(_code(value.get("error")), status, recovery.get("retrySafe"), shape + [TOOL_RESULT], _details(value.get("error")))
    if _is_int(value.get("status")) and "body" in value:
        shape = shape + ["dispatch{status,body}"]
        if value["status"] >= 400:
            body = value["body"] if isinstance(value["body"], dict) else {}
            return _error(_code(body.get("error")) or _code(body), value["status"], None, shape, _details(body.get("error")))
        return _parse(value["body"], keysets, shape, value["status"])
    if "data" in value and "error" in value:
        shape = shape + ["rest{requestId,data,error}"]
        if value["error"] is not None:
            return _error(_code(value["error"]), status, None, shape, _details(value["error"]))
        return _data(value["data"], keysets, shape, status)
    if keysets and any(all(key in value for key in keys) for keys in keysets):
        return _data(value, keysets, shape + ["bare data"], status)
    raise ValueError("Unrecognised response shape: not a CallToolResult, mali-tool-result/v1, dispatch envelope, REST envelope or bare data")


def _call_tool_result(value: dict, keysets, shape: list[str]) -> dict:
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


def _inside(path: Path, root: Path, what: str) -> Path:
    """Mirrors context_pack._inside: refuse anything that resolves outside the project."""
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{what} resolves outside the project ({resolved}); symlinked folders and files are refused")
    return resolved


def area(drama: Path, name: str) -> Path:
    """`.drama/receipts` or `.drama/cache`, refused when a symlink points it outside the project."""
    folder = drama / name
    _inside(folder, drama.parent, f".drama/{name}")
    return folder


def contained(path: Path, drama: Path) -> Path:
    if path.is_symlink() or path.exists():
        _inside(path, drama.parent, str(path.relative_to(drama.parent)))
    if path.is_symlink() and not path.exists():
        raise ValueError(f"{path} is a dangling symlink; remove or fix it by hand")
    return path


def atomic_write(path: Path, content: bytes) -> None:
    """Temp file in the same folder + os.replace; used only for the manifest, under manifest_lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        _write_stream(handle, content)
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
        _write_stream(handle, content)
        try:
            os.link(temp, path)
        except FileExistsError:
            return False
        except OSError:  # no hard links here (EPERM, ENOTSUP, EXDEV…): exclusive create instead
            return _create_exclusive(path, content)
        return True
    finally:
        os.unlink(temp)


def _write_stream(handle: int, content: bytes) -> None:
    with os.fdopen(handle, "wb") as stream:
        os.fchmod(stream.fileno(), FILE_MODE)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _create_exclusive(path: Path, content: bytes) -> bool:
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE)
    except FileExistsError:
        return False
    try:
        _write_stream(handle, content)
    except BaseException:
        os.unlink(path)  # never leave a partial file behind
        raise
    return True


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
        value = json.loads(raw.decode("utf-8-sig"))
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
    folder = area(drama, "receipts")
    items = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            contained(path, drama)
            items.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (UnicodeDecodeError, ValueError, OSError) as error:
            items.append((path, error))
    return items


def _page_remote(operation: str, data, request: dict) -> dict:
    """remote for a page operation: write results carry no projectId, so it comes from --input; the addressed page_id too."""
    data = data if isinstance(data, dict) else {}
    project = _field(data, "projectId") or _field(request, "project_id", "projectId")
    if project is None:
        raise ValueError("projectId is neither in the response nor in --input (project_id)")
    page = _field(data, "pageId") or _field(request, "page_id", "pageId")
    revision = data.get("revision") if operation != "list_page_revisions" and _is_int(data.get("revision")) else None
    snapshot = _field(data, "inputSnapshotId") or _field(request, "input_snapshot_id", "inputSnapshotId")
    return {"projectId": project, "artifactId": None, "pageId": page, "revision": revision, "inputSnapshotId": snapshot}


def body_fingerprint(request: dict) -> str | None:
    """sha256 of the UTF-8 page body sent, the algorithm mali-story uses for `fingerprint` (shared/text-fingerprint.ts)."""
    body = request.get("body")
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest() if isinstance(body, str) else None


def _page_notes(operation: str, request: dict, parsed: dict | None, outcome: str) -> dict:
    notes = {key: value for key, value in (
        ("expectedRevision", _field(request, "expected_revision", "expectedRevision")),
        ("producer", _field(request, "producer")), ("bodyFingerprint", body_fingerprint(request)),
        ("toRevision", _field(request, "to_revision", "toRevision")), ("title", _field(request, "title")),
        ("semantic", _field(request, "semantic")), ("episodeRef", _field(request, "episode_ref", "episodeRef"))) if value is not None}
    if operation == "label_page_revision":
        notes.update(revision=request.get("revision"), label=request.get("label"), labelNote=LABEL_NOTE)
    data = parsed["data"] if parsed and parsed["ok"] and isinstance(parsed["data"], dict) else {}
    for key in ("replayed", "unchanged", "previousRevision", "restoredFromRevision", "fingerprint", "previousLabel"):
        if key in data:
            notes["response" + key[0].upper() + key[1:]] = data[key]
    if outcome == "rejected_conflict" and parsed:
        notes["conflict"] = {"code": parsed["errorCode"], **(parsed.get("errorDetails") or {})}
    return notes


def _page_warnings(operation: str, notes: dict, outcome: str) -> list[str]:
    """What a page write receipt does not say, in the host's language (v1.2)."""
    warnings = []
    if notes.get("responseUnchanged") is True:
        warnings.append("update_page 返回 unchanged=true：正文与当前修订相同，服务端没有写入新修订，也没有记下这个 request_id；不要把它当作一次新写入")
    if notes.get("responseReplayed") is True:
        warnings.append("服务端重放了同一 request_id 的原结果（replayed=true）：这不是第二次写入")
    if outcome == "rejected_conflict":
        code = (notes.get("conflict") or {}).get("code")
        warnings.append("IDEMPOTENCY_CONFLICT：这个 request_id 已用于不同的输入；查清原请求再决定，不要改输入重发" if code == "IDEMPOTENCY_CONFLICT" else
                        "VERSION_CONFLICT：页面已被其他来源更新（见 notes.conflict.currentRevision）；先 read_page 读最新修订，合并后用新 request_id 写，"
                        "expected_revision 取新读到的修订号")
    if operation == "label_page_revision":
        warnings.append(LABEL_NOTE)
    return warnings


def _remote(operation: str, parsed: dict | None, request: dict) -> dict:
    data = parsed["data"] if parsed and parsed["ok"] else None
    if operation in PAGE_OPS:
        return _page_remote(operation, data, request)
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
    if target["operation"] in PAGE_WRITES and target["outcome"] == "unknown":
        return _reconcile_page(operation, reconciles, target, doc, parsed, request)
    if operation in PAGE_OPS:
        return f"{reconciles!r} is a {target['operation']} with outcome {target['outcome']!r}; {operation} reconciles only an unknown page write", ""
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


def _reconcile_page(operation: str, reconciles: str, target: dict, doc: dict, parsed: dict | None,
                    request: dict) -> tuple[str | None, dict | str]:
    """Resolve an unknown page write (v1.2, #34) by an identical re-send or by a list_page_revisions listing.

    mali-story v0.20.0 list rows carry no requestId (PageRevisionSummary), so a listing can only match the sent body's
    fingerprint and producer after expectedRevision: a host judgment (M), except for a label, whose requested state the
    row shows directly (S). Only the identical re-send with the original request_id is verified by request identity:
    the server replays an exact retry (replayed: true) before any revision check (R).
    """
    tnotes, op = _notes(target), target["operation"]
    if doc["remote"]["projectId"] != target["remote"]["projectId"]:
        return f"projectId {doc['remote']['projectId']!r} is not the unknown {op}'s {target['remote']['projectId']!r}", ""
    if operation == op:
        if doc["inputFingerprint"] != target["inputFingerprint"]:
            return f"the re-send input differs from the unknown {op} (inputFingerprint); only an identical re-send may reconcile it", ""
        if doc["outcome"] != "confirmed":  # recorded as an attempt; the target stays pending
            return None, {"check": f"identical re-send with outcome {doc['outcome']!r}; does not resolve {reconciles!r}"}
        data = parsed["data"]
        if op != "label_page_revision" and target["remote"].get("pageId") not in (None, data.get("pageId")):
            return f"the re-send response pageId {data.get('pageId')!r} is not the unknown {op}'s page {target['remote']['pageId']!r}", ""
        how = ("label is idempotent; the identical PUT confirmed the label (S)" if op == "label_page_revision" else
               "identical re-send with the original request_id; inputFingerprint matched (S), the server replays an exact retry (R)")
        return None, {"check": how, "resendOf": reconciles, "replayed": data.get("replayed")}
    if operation != "list_page_revisions":
        return f"an unknown {op} is reconciled by list_page_revisions or an identical {op} re-send, not by {operation}", ""
    if doc["outcome"] != "confirmed":
        return f"this {operation} outcome is {doc['outcome']!r}; only a confirmed response can resolve an unknown", ""
    page = target["remote"].get("pageId")
    if page is None:
        return (f"the unknown {op} names no pageId, so there is no page to list: re-send the identical input with the same request_id "
                f"{reconciles!r} (the server replays it) and record it with --reconciles {reconciles}"), ""
    if _field(request, "page_id", "pageId") != page:
        return f"list_page_revisions must list the unknown {op}'s page {page!r}; --input has {_field(request, 'page_id', 'pageId')!r}", ""
    data = parsed["data"]
    rows = [row for row in data.get("revisions") or [] if isinstance(row, dict) and _is_int(row.get("revision"))]
    if op == "label_page_revision":
        wanted, label = tnotes.get("revision"), tnotes.get("label")
        row = next((row for row in rows if row["revision"] == wanted), None)
        if row is None:
            return f"the listing has no row for r{wanted}; list again with before_revision {wanted + 1 if _is_int(wanted) else '?'}", ""
        if row.get("label") != label:
            return (f"r{wanted} is labelled {row.get('label')!r}, not {label!r}: the label probably did not land. Re-send the identical "
                    f"label_page_revision (idempotent) and record it with --reconciles {reconciles}"), ""
        return None, {"check": "the listed revision carries the requested label (S); a label is not an approval", "matchedRevision": wanted,
                      "labelState": label}
    expected = tnotes.get("expectedRevision")
    if not _is_int(expected):
        return f"the unknown {op} receipt records no integer expectedRevision; re-send the identical input instead", ""
    kind = "update" if op == "update_page" else "restore"

    def same(row: dict) -> bool:
        if row["revision"] <= expected or row.get("op") != kind or row.get("producer") != tnotes.get("producer"):
            return False
        return (row.get("fingerprint") == tnotes.get("bodyFingerprint") if kind == "update"
                else row.get("restoredFromRevision") == tnotes.get("toRevision"))

    match = min((row for row in rows if same(row)), key=lambda row: row["revision"], default=None)
    if match is None:
        current = data.get("currentRevision")
        if _is_int(current) and current <= expected:
            return (f"currentRevision {current} is not above expectedRevision {expected}: the {op} did not land. Re-send the identical input with "
                    f"the same request_id {reconciles!r} and record it with --reconciles {reconciles}"), ""
        lowest = min((row["revision"] for row in rows), default=None)
        if data.get("nextBeforeRevision") is not None and (lowest is None or lowest > expected + 1):
            return (f"the listing stops at r{lowest} and does not reach expectedRevision {expected}: list again with "
                    f"before_revision {data.get('nextBeforeRevision')} and record that page"), ""
        what = "body fingerprint" if kind == "update" else f"restoredFromRevision {tnotes.get('toRevision')}"
        return (f"no listed {kind} after r{expected} matches the sent {what} and producer {tnotes.get('producer')!r}: the {op} probably did not "
                f"land and the page has moved on. Re-read it (read_page) before writing again; an identical re-send would be VERSION_CONFLICT"), ""
    return None, {"check": f"host judged: a listed {kind} after expectedRevision matches the sent "
                           + ("body fingerprint" if kind == "update" else "restore source") + " and producer; list rows carry no requestId (M)",
                  "matchedPageId": page, "matchedRevision": match["revision"], "matchedFingerprint": match.get("fingerprint")}


def record_receipt(project: str, response_path: str, operation: str, request_id: str, input_path: str,
                   reconciles: str | None = None) -> dict:
    drama = drama_dir(project)
    safe_id(request_id, "requestId")
    if operation not in EXPECTED:
        raise ValueError(f"Unknown operation {operation!r}")
    request = json.loads(Path(input_path).read_text(encoding="utf-8-sig"))
    if not isinstance(request, dict):
        raise ValueError("--input must be the JSON object sent to the MCP tool")
    base = {"ok": True, "enforcement": "S", "remote_verified": False, "adoption_verified": False, "warnings": []}
    target = None
    if reconciles is not None:
        safe_id(reconciles, "--reconciles")
        if operation not in RECONCILERS:
            raise ValueError(f"--reconciles is recorded from {', '.join(RECONCILERS)} only")
        target_path = contained(area(drama, "receipts") / f"{reconciles}.json", drama)
        if not target_path.is_file():
            raise ValueError(f"No local receipt {reconciles!r} to reconcile")
        target = json.loads(target_path.read_text(encoding="utf-8"))
    declared = _field(request, "request_id", "requestId")
    if operation in ("save_story_artifact", *PAGE_REQUEST_IDS) and reconciles is not None:
        if declared != reconciles:  # an identical re-send keeps the original request_id (S)
            return _refused(base, f"a re-send must carry the original request_id {reconciles!r}; --input has {declared!r}")
    elif declared is not None and declared != request_id:
        raise ValueError(f"--input declares request_id {declared!r}, not {request_id!r}")
    parsed, evidence = _load_response(response_path, operation)
    outcome, retry = outcome_of(parsed)
    slot_checked = False
    if operation == "save_story_artifact" and outcome == "confirmed":  # the receipt's slot is later trusted by receipt cache
        saved = parsed["data"]["record"].get("slot") if isinstance(parsed["data"].get("record"), dict) else None
        if isinstance(saved, str) and saved != _field(request, "slot"):
            raise ValueError(f"--input says slot {_field(request, 'slot')!r} but the confirmed save response's record.slot is {saved!r}: "
                             "this input is not the request the response answers. Nothing written")
        slot_checked = isinstance(saved, str)
        if not slot_checked:
            base["warnings"].append("the save response carries no record.slot, so this receipt's slot is only the --input's claim: it will "
                                    "not vouch for a cached slot (receipt cache records slotSource host unless a get_story_artifact response is given)")
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
                     expectedRevision=_field(request, "expected_revision", "expectedRevision"), **({"slotCheck": SLOT_CHECK} if slot_checked else {}))
    if operation in PAGE_WRITES:
        notes.update(_page_notes(operation, request, parsed, outcome))
        base["warnings"] += _page_warnings(operation, notes, outcome)
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
    path = contained(area(drama, "receipts") / f"{request_id}.json", drama)
    content =(json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
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


def _page_pending(doc: dict, attempts: list[str]) -> dict:
    """Reconciliation steps for an unknown page write (v1.2). List rows carry no requestId in mali-story v0.20.0."""
    request_id, op, notes = doc["requestId"], doc["operation"], _notes(doc)
    project_id, page = doc["remote"]["projectId"], doc["remote"].get("pageId")
    expected = notes.get("expectedRevision")
    resend = {"tool": op, "args": "<原样的 --input 文件>", "why": (
        "原样重发：同一 request_id + 同一输入由服务端重放原结果（replayed: true），没落地的则这次写入；只有它能按 request_id 核实"
        if op in PAGE_REQUEST_IDS else "原样重发：标签写入是幂等的 PUT，重发得到同一状态")}
    record_resend = {"command": f"drama_tools.py receipt record <project> <resend-response.json> --operation {op} "
                                f"--request-id {request_id}.resend-{len(attempts) + 1} --input <原输入> --reconciles {request_id}"}
    record_list = {"command": f"drama_tools.py receipt record <project> <list-response.json> --operation list_page_revisions "
                              f"--request-id <new-read-id> --input <list-input.json> --reconciles {request_id}"}
    if op == "create_page" or page is None:
        steps = [resend, record_resend]
        summary = "create_page 结果未知时还不知道 pageId，无法列修订：用原 request_id 原样重发，由服务端重放"
    elif op == "label_page_revision":
        steps = [{"tool": "list_page_revisions", "args": {"project_id": project_id, "page_id": page},
                  "check": f"r{notes.get('revision')} 的 label == {notes.get('label')!r}"}, record_list, resend, record_resend]
        summary = f"先用 list_page_revisions 看页面 {page} 的 r{notes.get('revision')} 是否已带标签，没有就原样重发（标签不是采用）"
    else:
        what = (f"fingerprint == {notes.get('bodyFingerprint')}（--input 正文的 sha256）" if op == "update_page"
                else f"op == restore 且 restoredFromRevision == {notes.get('toRevision')}")
        steps = [{"tool": "list_page_revisions", "args": {"project_id": project_id, "page_id": page},
                  "why": "mali-story 的修订列表不带 requestId，无法直接按 request_id 查：只能找 expectedRevision 之后的修订按指纹与 producer 比对（宿主判断）",
                  "check": f"revision > {expected}，{what}，producer == {notes.get('producer')!r}"},
                 record_list, resend, record_resend]
        summary = (f"先用 list_page_revisions 查页面 {page} 在 r{expected} 之后的修订（列表行不带 requestId，按正文指纹与 producer 比对）；"
                   "要按 request_id 核实，就用原 request_id 原样重发")
    return {"requestId": request_id, "operation": op, "projectId": project_id, "pageId": page, "slot": None,
            "expectedRevision": expected, "retryAllowed": False, "unconfirmedAttempts": attempts, "summary": summary, "steps": steps}


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
        judged_by_host = doc["operation"] == "list_story_artifacts"
        if target is None or target["operation"] not in WRITES or target["outcome"] != "unknown":
            reason = f"reconciles {target_id!r}, which is not a valid unknown write receipt"
        elif (target["operation"] in PAGE_WRITES) != (doc["operation"] in PAGE_OPS):
            reason = f"a {doc['operation']} does not reconcile a {target['operation']}"
        elif doc["remote"]["projectId"] != target["remote"]["projectId"]:
            reason = f"projectId {doc['remote']['projectId']!r} is not the reconciled write's {target['remote']['projectId']!r}"
        elif doc["operation"] == "list_page_revisions":
            judged_by_host = notes.get("labelState") is None  # a listed label is the requested state itself (S)
            reason = None if _is_int(notes.get("matchedRevision")) and notes.get("reconciles") == target_id else "page list reconciliation names no matched revision"
        elif doc["operation"] in PAGE_WRITES:
            reason = None if notes.get("resendOf") == target_id and doc["inputFingerprint"] == target["inputFingerprint"] \
                else f"the re-send is not an identical {target['operation']} of {target_id!r}"
        elif doc["operation"] == "list_story_artifacts":
            reason = None if notes.get("matchedArtifactId") and _is_int(notes.get("matchedRevision")) else "list reconciliation names no matched row"
        else:
            reason = None if notes.get("observedRequestId") == target_id else f"notes.observedRequestId {notes.get('observedRequestId')!r} is not {target_id!r}"
        if reason:
            invalid.append({"path": str(drama / "receipts" / f"{doc['requestId']}.json"), "errors": [f"reconciliation not counted: {reason}"]})
            continue
        (host_judged if judged_by_host else verified).add(target_id)
    items, read_only, unreconcilable = [], [], []
    for doc in valid:
        request_id = doc["requestId"]
        if doc["outcome"] != "unknown" or request_id in verified or request_id in host_judged:
            continue
        if doc["operation"] in WRITES and doc.get("localRef", {}).get("kind") == "remote_receipt":
            continue  # an unconfirmed re-send attempt: its target stays pending on its own
        attempts = sorted(d["requestId"] for d in valid if d["operation"] == doc["operation"] and d["outcome"] != "confirmed"
                          and d.get("localRef", {}).get("kind") == "remote_receipt" and d["localRef"]["id"] == request_id)
        if doc["operation"] in PAGE_WRITES:
            items.append(_page_pending(doc, attempts))
            continue
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
    drama = drama_dir(project)
    path = contained(area(drama, "receipts") / f"{safe_id(request_id, 'requestId')}.json", drama)
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


def _page_chunk(data: dict, name: str) -> dict:
    """One read_page chunk (mali-story v0.20.0 readPageText): same chunk fields as a story artifact read, keyed by pageId."""
    span = data.get("coveredRange") if isinstance(data.get("coveredRange"), dict) else {}
    fields = {"projectId": data.get("projectId"), "pageId": data.get("pageId"), "revision": data.get("revision"),
              "fingerprint": data.get("fingerprint"), "totalCharacters": data.get("totalCharacters"),
              "text": data.get("text"), "from": span.get("from"), "to": span.get("to"), "nextOffset": data.get("nextOffset")}
    kinds = {"projectId": str, "pageId": str, "fingerprint": str, "text": str}
    for key, value in fields.items():
        if key == "nextOffset" and value is None:
            continue
        if not (isinstance(value, kinds[key]) if key in kinds else _is_int(value)):
            raise ValueError(f"{name}: read_page chunk has no valid {key}")
    if fields["revision"] < 1:
        raise ValueError(f"{name}: read_page revision {fields['revision']} names no page revision; cache a page with history (revision >= 1)")
    if not FINGERPRINT.fullmatch(fields["fingerprint"]):
        raise ValueError(f"{name}: fingerprint is not sha256:<hex>")
    safe_id(fields["pageId"], "pageId")
    return fields


def _refuse(error: str) -> dict:
    return {"ok": True, "passed": False, "status": "refused", "error": error + "; nothing written",
            "remote_verified": False, "adoption_verified": False}


def _join(chunks: list[dict]) -> tuple[str | None, str | None]:
    """Return (text, None) for a complete verified sequence, else (None, reason)."""
    identity = {(c["projectId"], c.get("artifactId", c.get("pageId")), c["revision"], c["fingerprint"], c["totalCharacters"]) for c in chunks}
    if len(identity) > 1:
        what = "pageId" if "pageId" in chunks[0] else "artifactId"
        return None, f"chunks disagree on projectId, {what}, revision, fingerprint or totalCharacters"
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


def slot_rank(entry: dict) -> int:
    source = entry.get("slotSource")
    return SLOT_SOURCES.index(source) if source in SLOT_SOURCES else 0


def _vouched(item: dict, fields: list[str]) -> str:
    """Say what stands behind the differing `fields` of a manifest entry, for a refusal or a correction warning."""
    source = item.get("slotSource")
    if source not in SLOT_SOURCES:
        return "The manifest entry has " + ("no slotSource" if source is None else f"an unknown slotSource {source!r}") + " (counts as host)"
    if source == "receipt" and fields != ["slot"]:
        return "In the manifest entry a save receipt vouches for the slot (slotSource 'receipt'), while kind and episodeRef were given by the host"
    return f"The manifest values come from slotSource {source!r}"


def effective_entries(entries: list[dict]) -> list[dict]:
    """Of the manifest entries for one artifact revision, those from its strongest slot source (record > receipt > host).

    These alone are authoritative: a weaker entry that differs has been corrected by them, whatever the order, and
    only disagreement among them is a conflict. receipt cache compares slot, kind and episodeRef against them;
    context-pack, impact and status read only the slot from them.
    """
    top = max(map(slot_rank, entries), default=0)
    return [entry for entry in entries if slot_rank(entry) == top]


def _saved_slots(drama: Path, project_id: str | None, artifact: str, revision: int) -> dict[str, str]:
    """slot -> requestId of every valid confirmed local save receipt for exactly this artifact revision.

    project_id None (a get record that carries none) matches on artifact and revision alone.

    Only receipts whose notes say the slot was matched against the response's record.slot count; one written from a
    response without a slot, or before that check existed, records only what the host's input claimed.

    A confirmed identical re-send (#26) points its localRef at the unknown save it reconciles instead of at the slot;
    its slot is that save's slot, taken only when the re-send's notes carry the slot check and the record.requestId
    match, and the reconciled receipt is a valid save of the same input in the same project.
    """
    valid = [doc for _, doc in _receipts(drama) if isinstance(doc, dict) and not check_contract("remote-receipt", doc)]
    by_id = {doc["requestId"]: doc for doc in valid}

    def slot_of(doc: dict) -> str | None:
        ref, notes = doc.get("localRef") or {}, _notes(doc)
        if ref.get("kind") != "remote_receipt":
            return _slot(doc)
        target = by_id.get(ref.get("id"))
        if target is None or notes.get("reconciles") != ref["id"] or notes.get("observedRequestId") != ref["id"]:
            return None
        same = (target["operation"], target["inputFingerprint"], target["remote"]["projectId"]) == (
            "save_story_artifact", doc["inputFingerprint"], doc["remote"]["projectId"])
        return _slot(target) if same else None

    return {slot_of(doc): doc["requestId"] for doc in valid
            if doc["operation"] == "save_story_artifact" and doc["outcome"] == "confirmed" and slot_of(doc)
            and _notes(doc).get("slotCheck") == SLOT_CHECK
            and project_id in (None, doc["remote"]["projectId"])
            and (doc["remote"].get("artifactId"), doc["remote"].get("revision")) == (artifact, revision)}


def _load_manifest(manifest_path: Path) -> dict:
    """The manifest to append to: v0 entries are kept as they are; the file is written back as v1 (#34)."""
    if not manifest_path.exists():
        return {"schemaVersion": MANIFEST, "entries": []}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") not in MANIFESTS or not isinstance(manifest.get("entries"), list):
        raise ValueError(f"{manifest_path} is not a {' or '.join(MANIFESTS)} manifest")
    return {**manifest, "schemaVersion": MANIFEST}


def _created_title(drama: Path, page_id: str) -> str | None:
    """The title a valid confirmed local create_page receipt sent for this page; no page tool returns a title."""
    titles = {_notes(doc).get("title") for _, doc in _receipts(drama) if isinstance(doc, dict) and not check_contract("remote-receipt", doc)
              and doc["operation"] == "create_page" and doc["outcome"] == "confirmed" and doc["remote"].get("pageId") == page_id}
    titles.discard(None)
    return titles.pop() if len(titles) == 1 else None


def cache_page(drama: Path, chunks: list[dict], meta: list[dict], title: str | None) -> dict:
    """Cache one page revision from a complete read_page sequence; verified only when the joined text hashes to its fingerprint.

    The manifest v1 entry records pageId, revision, title (host-declared or from a local create_page receipt: no page tool
    returns it), the labels the read chunks carried, producer, both hashes, operation read_page and readAt. A label
    observed in a read is a name for the revision, not production adoption.
    """
    text, reason = _join(chunks)
    if reason:
        return _refuse(reason)
    page, revision, server = chunks[0]["pageId"], chunks[0]["revision"], chunks[0]["fingerprint"]
    content = text.encode("utf-8")
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    labels = sorted({item["label"] for item in meta if isinstance(item.get("label"), str)})
    producers = sorted({item["producer"] for item in meta if isinstance(item.get("producer"), str)})
    warnings = [LABEL_NOTE] if labels else []
    if len(labels) > 1:
        warnings.append(f"读取过程中标签发生了变化（{'、'.join(labels)}）；标签可随时改写，manifest 记下的是读取时看到的全部标签")
    if title is None:
        title = _created_title(drama, page)
        if title is None:
            warnings.append("没有给 --title，本地也没有该页面的 confirmed create_page 回执：title 记为 null（页面工具不返回标题）")
    name = f"{page}@r{revision}.md"
    folder = area(drama, "cache")
    path, manifest_path, rel = folder / name, folder / "manifest.json", f".drama/cache/{name}"
    for file in (path, manifest_path):
        contained(file, drama)
    entry = {"path": rel, "pageId": page, "revision": revision, "title": title, "labels": labels,
             "producer": producers[0] if len(producers) == 1 else None, "sha256": digest, "serverFingerprint": server,
             "verified": digest == server, "operation": "read_page", "readAt": _now()}
    with manifest_lock(folder):
        manifest = _load_manifest(manifest_path)
        status = "written"
        if path.exists() or not publish_new(path, content):
            if path.read_bytes() != content:
                return _refuse(f"{path} already exists with different bytes")
            status = "unchanged"
        same = [item for item in manifest["entries"] if isinstance(item, dict) and item.get("path") == rel]
        keys = ("pageId", "revision", "title", "labels", "producer", "sha256", "serverFingerprint", "verified")
        existing = next((item for item in same if all(item.get(key) == entry[key] for key in keys)), None)
        if existing is None:  # append-only: a later read with other labels or another title adds an entry, never edits one
            manifest["entries"].append(entry)
            atomic_write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    returned = existing or entry
    return {"ok": True, "passed": True, "status": status, "path": str(path), "entry": returned, "manifestAppended": existing is None,
            "verified": returned["verified"] is True, "warnings": warnings, "remote_verified": False, "adoption_verified": False}


def cache(project: str, response_paths: list[str], slot: str | None = None, kind: str | None = None,
          episode_ref: str | None = None, title: str | None = None) -> dict:
    """Cache one page revision from a full read_page sequence (v1.2), or, read-only compatibility for candidates saved before
    the page model, one artifact revision from a full read_story_artifact sequence (verified) or a get (unverified).

    The entry's slotSource says who vouches for the slot: the get record, a local confirmed save receipt, or only the host.
    A call from a stronger source than every entry for the path appends an entry that corrects them: a get record
    corrects slot, kind and episodeRef, a save receipt only the slot it vouches for. An equal or weaker source that
    differs from the strongest entries is refused.
    """
    drama = drama_dir(project)
    chunks, records, pages, meta = [], {}, [], []
    for name in response_paths:
        parsed = _parse(json.loads(Path(name).read_text(encoding="utf-8-sig")), (READ_KEYS, ("record",)), [])
        if not parsed["ok"]:
            raise ValueError(f"{name}: the saved call failed ({parsed['errorCode']}); nothing to cache")
        if "pageId" in parsed["data"]:
            pages.append(_page_chunk(parsed["data"], name))
            meta.append(parsed["data"])
        elif isinstance(parsed["data"].get("record"), dict):
            record = parsed["data"]["record"]
            records[canonical_json(record)] = record
        else:
            chunks.append(_chunk(parsed["data"], name))
    if pages:
        if chunks or records:
            raise ValueError("read_page chunks cannot be cached together with story artifact responses; pass one page's chunks per call")
        if slot is not None or kind is not None or episode_ref is not None:
            raise ValueError("--slot, --kind and --episode-ref belong to story artifacts; a page is identified by its pageId and revision")
        return cache_page(drama, pages, meta, title)
    if title is not None:
        raise ValueError("--title belongs to read_page chunks; story artifacts have slot, kind and episodeRef")
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
        if record is None:  # read responses carry no slot: --slot is the host's word unless a save receipt backs it
            saved = _saved_slots(drama, chunks[0]["projectId"], artifact, revision)
            clash = sorted(f"{name!r} (receipt {request_id})" for name, request_id in saved.items() if name != slot)
            if clash:
                return _refuse(f"--slot {slot!r} disagrees with the local confirmed save receipt for {artifact}: slot {', '.join(clash)}")
            source = "receipt" if saved else "host"
    else:
        text, artifact, revision, server = record["body"], record["id"], record["revision"], None
        operation = "get_story_artifact"
    content = text.encode("utf-8")
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    verified = server is not None and digest == server
    name = f"{artifact}@r{revision}.md"
    folder = area(drama, "cache")
    path, manifest_path, rel = folder / name, folder / "manifest.json", f".drama/cache/{name}"
    for file in (path, manifest_path):
        contained(file, drama)
    entry = {"path": rel, "artifactId": artifact, "slot": slot, "kind": kind, "episodeRef": episode_ref,
             "revision": revision, "sha256": digest, "serverFingerprint": server, "verified": verified,
             "operation": operation, "readAt": _now(), "slotSource": "record" if record is not None else source}
    with manifest_lock(folder):
        manifest = _load_manifest(manifest_path)
        same =[item for item in manifest["entries"] if isinstance(item, dict) and item.get("path") == rel]
        corrected = disputed = False
        for item in effective_entries(same):
            fields = [key for key in SLOT_FIELDS if item.get(key) != entry[key]]
            if not fields:
                continue
            differing = "; ".join(f"{key} {item.get(key)!r} (manifest) vs {entry[key]!r} (this call)" for key in fields)
            odd = [key for key in fields if not isinstance(item.get(key), str) and (key != "episodeRef" or item.get(key) is not None)]
            if odd:  # nothing this tool writes: such an entry is reported, never corrected
                return _refuse(f"{rel} is already cached with different metadata: {differing}. The manifest entry's {', '.join(odd)} "
                               "is not a string, so the entry was not written by this tool and is not corrected")
            held = f"{_vouched(item, fields)}; this call's source is {entry['slotSource']!r}"
            if slot_rank(entry) <= slot_rank(item):  # an equal or weaker source never overrides what is cached
                return _refuse(f"{rel} is already cached with different metadata: {differing}. {held}. Only a stronger source corrects "
                               "cached metadata (record > receipt > host)"
                               + ("" if item.get("slotSource") == "record" else "; re-cache with the get_story_artifact response to correct it"))
            if entry["slotSource"] == "receipt" and fields != ["slot"]:  # kind and episodeRef of such a call are still the host's word
                return _refuse(f"{rel} is already cached with different metadata: {differing}. {held}, and a save receipt vouches only "
                               "for the slot: re-cache with the get_story_artifact response to correct kind or episodeRef")
            if not corrected:
                warnings.append(f"this call's slotSource {entry['slotSource']!r} corrects metadata cached earlier: {differing}. {held}. "
                                "The earlier manifest entry is kept unchanged and readers use the strongest source; snapshots packed "
                                "before this were checked against the old values")
            if "slot" in fields and item.get("slotSource") == "receipt" and not disputed:  # both slots were derived from saved server responses
                project_id = chunks[0]["projectId"] if chunks else record.get("projectId") if isinstance(record.get("projectId"), str) else None
                saved = _saved_slots(drama, project_id, artifact, revision).get(item["slot"])
                disputed = True
                warnings.append(f"two saved server responses disagree about this artifact revision's slot: the get_story_artifact record says "
                                f"{entry['slot']!r}, while a confirmed save receipt "
                                + (f"({saved}) " if saved else "(no matching local save receipt was found) ")
                                + f"vouched for {item.get('slot')!r}. The record is followed; inspect that receipt and both saved "
                                  "responses before relying on either")
            corrected = True
        status = "written"
        if path.exists() or not publish_new(path, content):
            if path.read_bytes() != content:
                return _refuse(f"{path} already exists with different bytes")
            status = "unchanged"
        if not verified:  # never shadow a verified read with a later unverified entry for the same bytes
            read = next((item for item in same if item.get("verified") is True and item.get("sha256") == digest), None)
            if read is not None:
                # the same bytes were verified by that read: restate it with this call's slot source rather than claim a new read
                entry.update(serverFingerprint=read.get("serverFingerprint"), verified=True, operation=read.get("operation"),
                             readAt=read.get("readAt"))
        # append-only: an entry is reused unless this call brings a stronger slot source for the same path (which may correct it)
        existing = max((item for item in same if item.get("verified") == entry["verified"] and slot_rank(item) >= slot_rank(entry)
                        and all(item.get(key) == entry[key] for key in SLOT_FIELDS)), key=slot_rank, default=None)
        if existing is None:
            manifest["entries"].append(entry)
            atomic_write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    returned = existing or entry
    if not returned.get("verified"):
        warnings.append("get_story_artifact carries no full-text fingerprint: cached as verified=false; read the artifact with read_story_artifact to nextOffset null to verify")
    if max(map(slot_rank, [*same, returned])) == 0:  # the strongest source recorded for this path, as impact reads it
        warnings.append("slot is the host's declaration (slotSource: host), so impact reports references to this artifact as unknown; "
                        "re-cache with the get_story_artifact response to record the slot")
    return {"ok": True, "passed": True, "status": status, "path": str(path), "entry": returned,
            "manifestAppended": existing is None, "verified": returned.get("verified") is True, "warnings": warnings,
            "remote_verified": False, "adoption_verified": False}


def run_receipt(args) -> dict:
    """Dispatch `drama_tools.py receipt <subcommand>`; refusals return passed=False, input errors raise."""
    if args.receipt_command == "record":
        return record_receipt(args.project, args.response, args.operation, args.request_id, args.input_path, args.reconciles)
    if args.receipt_command == "pending":
        return pending(args.project)
    if args.receipt_command == "cache":
        return cache(args.project, args.responses, args.slot, args.kind, args.episode_ref, args.title)
    return show(args.project, args.request_id)
