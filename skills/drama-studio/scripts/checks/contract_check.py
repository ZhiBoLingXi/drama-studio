"""Validate D0 contract objects: a JSON Schema subset plus cross-field rules a schema cannot express.

Passing proves shape and the listed script-enforced (S) rules only. It never proves that a
reference exists remotely, that a text supports a claim, or that anything was adopted.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
LAYERS = ["C1", "C2", "C3", "C4", "C5", "C6"]
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def schema_names() -> list[str]:
    return sorted(path.name[:-12] for path in SCHEMA_DIR.glob("*.schema.json"))  # examples/ holds one valid instance each


def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / f"{name}.schema.json"
    if name not in schema_names():
        raise ValueError(f"Unknown contract {name!r}; available: {', '.join(schema_names())}")
    return json.loads(path.read_text(encoding="utf-8"))


def _is_type(value, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[expected])


def _validate(value, schema: dict, root: dict, path: str, errors: list[str]) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"Unsupported $ref {ref}")
        schema = root["$defs"][ref[len("#/$defs/"):]]
    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, option) for option in options):
            errors.append(f"{path}: expected {'/'.join(options)}")
            return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(item, schema["items"], root, f"{path}[{index}]", errors)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], root, f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: not allowed")


def _ref_key(ref: dict) -> tuple:
    return (ref.get("kind"), ref.get("id"), ref.get("revision"), json.dumps(ref.get("range"), sort_keys=True))


def _rules_knowledge_card(doc: dict) -> list[str]:
    errors = []
    if doc["scope"]["level"] != "project":
        errors.append("scope.level: studio/public knowledge is not enabled in this version; keep cards project-private")
    nature = doc["evidence"]["nature"]
    if nature != "synthetic_example" and not doc["evidence"]["sources"]:
        errors.append("evidence.sources: non-synthetic knowledge needs at least one exact source")
    if nature == "synthetic_example" and doc["usage"] == "evaluation_only":
        errors.append("usage: a synthetic example cannot serve as evaluation evidence")
    return errors


def _rules_context_snapshot(doc: dict) -> list[str]:
    errors, seen, revisions = [], set(), {}
    role = doc["createdFor"]["role"]
    total = 0
    for index, item in enumerate(doc["items"]):
        where = f"items[{index}]"
        key = _ref_key(item["ref"])
        if key in seen:
            errors.append(f"{where}: duplicate reference")
        seen.add(key)
        identity = (item["ref"]["kind"], item["ref"]["id"])
        revision = item["ref"].get("revision")
        if identity in revisions and revisions[identity] != revision:
            errors.append(f"{where}: mixed revisions of {item['ref']['id']} ({revisions[identity]!r} and {revision!r}) in one package")
        revisions.setdefault(identity, revision)
        span = item["ref"].get("range")
        if span and span["start"] > span["end"]:
            errors.append(f"{where}: range start is after end")
        total += item["chars"]
        if item["usage"] == "evaluation_only" and role != "evaluation":
            errors.append(f"{where}: evaluation_only material cannot enter the {role} package")
        if item["usage"] == "comparison_only" and role not in ("similarity_review", "evaluation"):
            errors.append(f"{where}: comparison_only material is limited to similarity review")
        if item["partition"] == "knowledge" and item["ref"]["kind"] != "knowledge_card":
            errors.append(f"{where}: knowledge partition only takes knowledge_card references")
        if item["partition"] == "project_facts" and item["ref"]["kind"] == "knowledge_card":
            errors.append(f"{where}: shared knowledge cannot be packed as project facts")
        if item["required"] and item["ref"].get("revision") is None:
            errors.append(f"{where}: required material must pin an exact revision")
    if total > doc["budget"]["limit"]:
        errors.append(f"budget: {total} chars exceed limit {doc['budget']['limit']}; shrink the unit or omit explicitly")
    for index, entry in enumerate(doc["omitted"]):
        span = entry["ref"].get("range")
        if span and span["start"] > span["end"]:
            errors.append(f"omitted[{index}]: range start is after end")
    missing_required = any(entry["required"] for entry in doc["omitted"])
    if missing_required and doc["completeness"] == "complete":
        errors.append("completeness: a required item was omitted, so the package cannot be complete")
    if doc["createdFor"]["role"] == "reader_effect" and any(item["partition"] == "current_plan" for item in doc["items"]):
        errors.append("items: a reader_effect package must not include author plans or explanations")
    return errors


def _rules_review_record(doc: dict) -> list[str]:
    errors = []
    for index, finding in enumerate(doc["findings"]):
        if finding["category"] == "fact" and not finding["evidence"]:
            errors.append(f"findings[{index}]: a fact finding needs quoted evidence")
    if doc["context"] == "serial_self_review" and doc.get("claimsIndependence"):
        errors.append("claimsIndependence: serial self review cannot claim independence")
    return errors


def _rules_run_handoff(doc: dict) -> list[str]:
    errors = []
    current = LAYERS.index(doc["workstation"])
    for index, proposal in enumerate(doc["changeProposals"]):
        target = LAYERS.index(proposal["targetLayer"])
        if target >= current:
            errors.append(f"changeProposals[{index}]: must target an upstream layer of {doc['workstation']}")
    usage = doc["host"]["usage"]
    if usage["source"] != "host_reported" and usage.get("tokens") is not None:
        errors.append("host.usage.tokens: only host-reported usage may state tokens")
    extra = doc.get("additionalSnapshotIds", [])
    if doc["contextSnapshotId"] in extra or len(set(extra)) != len(extra):
        errors.append("additionalSnapshotIds: list each further snapshot once, and not the contextSnapshotId itself")
    if "finishedAt" in doc and finished_at(doc["finishedAt"]) is None:
        errors.append("finishedAt: not a valid ISO 8601 date-time with a UTC offset")
    return errors


def finished_at(value) -> datetime | None:
    """A run-handoff finishedAt as an aware datetime, or None when it is not a valid ISO 8601 time with an offset."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{3}|\.\d{6})?)?(Z|[+-]\d{2}:\d{2})", value):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _rules_remote_receipt(doc: dict) -> list[str]:
    errors = []
    remote = doc["remote"]
    if doc["outcome"] != "not_sent" and remote.get("projectId") is None:
        errors.append("remote.projectId: a sent request must name its project")
    if doc["outcome"] == "not_sent" and (remote.get("artifactId") is not None or remote.get("revision") is not None):
        errors.append("remote: an unsent request cannot carry remote results")
    if doc["operation"] == "save_story_artifact" and doc["outcome"] != "not_sent":
        if doc["outcome"] == "confirmed" and (remote.get("artifactId") is None or remote.get("revision") is None):
            errors.append("remote: a confirmed save must record artifactId and revision")
        if remote.get("inputSnapshotId") is None:
            errors.append("remote.inputSnapshotId: saves must bind the snapshot used to write")
    if doc["outcome"] == "unknown" and doc.get("retryAllowed"):
        errors.append("retryAllowed: an unknown outcome must be reconciled by requestId before any retry")
    return errors


def _rules_task(doc: dict) -> list[str]:
    errors = []
    evidence = doc.get("adoptionEvidence")
    if doc["status"]["adoption"] == "adopted_remote" and (evidence is None or evidence["kind"] != "remote_receipt"):
        errors.append("status.adoption: adopted_remote needs a remote_receipt reference; local fields cannot certify adoption")
    if doc["authorization"]["source"] == "none" and doc["writeScope"]:
        errors.append("writeScope: no authorization recorded, so nothing may be written")
    return errors


RULES = {"knowledge-card": _rules_knowledge_card, "context-snapshot": _rules_context_snapshot,
         "review-record": _rules_review_record, "run-handoff": _rules_run_handoff,
         "remote-receipt": _rules_remote_receipt, "task": _rules_task}


def check_contract(name: str, document) -> list[str]:
    schema = load_schema(name)
    errors: list[str] = []
    _validate(document, schema, schema, "$", errors)
    if not errors and name in RULES:
        errors.extend(RULES[name](document))
    return errors


def run_contract_check(name: str, path: str) -> dict:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = check_contract(name, document)
    return {"ok": True, "contract": name, "path": str(Path(path).absolute()), "passed": not errors,
            "errors": errors, "enforcement": "S", "remote_verified": False, "adoption_verified": False}
