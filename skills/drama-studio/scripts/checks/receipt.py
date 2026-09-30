"""Turn saved mali-story MCP responses into remote-receipts and a verified local text cache.

Passing proves only that the saved response files parse, that every receipt passes
`contract-check remote-receipt`, that receipts and the cache manifest are append-only, and that
cached text hashes to the fingerprint the saved read responses declare. The tool never calls
mali-story, so it never proves a response is genuine, that a candidate exists remotely, or that
anything was adopted; a receipt or cache entry is never adoption evidence.
"""
from __future__ import annotations

import hashlib
import json

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
