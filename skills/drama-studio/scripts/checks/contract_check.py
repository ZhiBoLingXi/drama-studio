"""Validate D0 and D6 contract objects: a JSON Schema subset plus cross-field rules a schema cannot express.

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
PAGE_OPERATIONS = ("create_page", "update_page", "read_page", "list_page_revisions", "label_page_revision", "restore_page")
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
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: must be above {schema['exclusiveMinimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: allows at most {schema['maxItems']} items")
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
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate(item, schema["additionalProperties"], root, f"{path}.{key}", errors)


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
    supports = [rule["support"] for rule in doc["content"].get("rules", [])]
    if doc.get("coverage") == "empty" and any(support != "not_found" for support in supports):
        errors.append("coverage: an empty card records only what was searched and not found; every content.rules[].support must be not_found")
    if doc.get("coverage") == "sourced" and supports and "sourced" not in supports:
        errors.append("coverage: a sourced card needs at least one content.rules[] item with support: sourced")
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
        if item["usage"] == "comparison_only" and role not in COMPARISON_ROLES:
            errors.append(f"{where}: comparison_only material is limited to {'/'.join(COMPARISON_ROLES)}")
        if item["partition"] == "knowledge" and item["ref"]["kind"] != "knowledge_card":
            errors.append(f"{where}: knowledge partition only takes knowledge_card references")
        if item["partition"] == "project_facts" and item["ref"]["kind"] == "knowledge_card":
            errors.append(f"{where}: shared knowledge cannot be packed as project facts")
        if item["required"] and item["ref"].get("revision") is None:
            errors.append(f"{where}: required material must pin an exact revision")
        if item["ref"]["kind"] == "remote_page" and not (type(revision) is int and revision >= 1):
            errors.append(f"{where}: a remote_page reference is pageId + an integer revision >= 1")
    if total > doc["budget"]["limit"]:
        errors.append(f"budget: {total} chars exceed limit {doc['budget']['limit']}; shrink the unit or omit explicitly")
    for index, entry in enumerate(doc["omitted"]):
        span = entry["ref"].get("range")
        if span and span["start"] > span["end"]:
            errors.append(f"omitted[{index}]: range start is after end")
    missing_required = any(entry["required"] for entry in doc["omitted"])
    if missing_required and doc["completeness"] == "complete":
        errors.append("completeness: a required item was omitted, so the package cannot be complete")
    if doc["createdFor"]["role"] in ("reader_effect", "dialogue_read") and any(item["partition"] == "current_plan" for item in doc["items"]):
        errors.append("items: a reader_effect or dialogue_read package must not include author plans or explanations")
    errors.extend(_cold_reader_package(role, doc["items"], "items"))
    return errors


def _cold_reader_package(role, items, where) -> list[str]:
    """A cold reader gets exactly one project_facts item (this episode's text or its events) and nothing authored."""
    if role != "cold_reader":
        return []
    errors = []
    facts = [item for item in items if item["partition"] == "project_facts"]
    if len(facts) != 1:
        errors.append(f"{where}: a cold_reader package takes exactly one project_facts item (this episode's text or plan events), found {len(facts)}")
    if any(item["partition"] in ("current_plan", "knowledge") for item in items):
        errors.append(f"{where}: a cold_reader package must not include plans, explanations or knowledge")
    return errors


# comparison_only material is for comparing against: similarity and evaluation, and (D6-2) the reality check, which
# compares a move with K1 cards on the real world
COMPARISON_ROLES = ("similarity_review", "evaluation", "fact_check")
PLAN_FOLDER = "planning/episodes/"  # where C4 writes episode plans (docs/d6/d6-2-decisions.md §1)


def _rules_review_record(doc: dict) -> list[str]:
    errors = []
    for index, finding in enumerate(doc["findings"]):
        if finding["category"] == "fact" and not finding["evidence"]:
            errors.append(f"findings[{index}]: a fact finding needs quoted evidence")
    if doc["context"] == "serial_self_review" and doc.get("claimsIndependence"):
        errors.append("claimsIndependence: serial self review cannot claim independence")
    # D6-2: a review of an episode plan in the planning/episodes/ layout cites what every finding rests on
    plan_review = any(ref.get("kind") == "local_file" and str(ref.get("id", "")).startswith(PLAN_FOLDER)
                      for ref in [doc["target"], *doc.get("additionalTargets", [])])
    for index, finding in enumerate(doc["findings"]):
        if plan_review and not finding.get("cites") and finding.get("kind") != "preference":
            errors.append(f"findings[{index}]: a review of an episode plan ({PLAN_FOLDER}) needs cites "
                          "(functionId/ledgerId/targetClause/factEvidence) on every finding, or kind: preference")
        elif ("cites" in finding or "kind" in finding) and not finding.get("cites") and finding.get("kind") != "preference":
            errors.append(f"findings[{index}]: cites none of functionId/ledgerId/targetClause/factEvidence, so it must be kind: preference")
    known = {finding["id"] for finding in doc["findings"]}
    for index, item in enumerate(doc.get("adjudications", [])):
        missing = [finding for finding in item["findingIds"] if finding not in known]
        if missing:
            errors.append(f"adjudications[{index}]: unknown finding ids {missing}")
    return errors


NO_PACK_WORKSTATIONS = ("C1", "C2")  # their runs may record no context snapshot (D6-2 §5 #8)


def _rules_run_handoff(doc: dict) -> list[str]:
    errors = []
    current = LAYERS.index(doc["workstation"])
    for index, proposal in enumerate(doc["changeProposals"]):
        if "default" in proposal and proposal["default"] not in [o["optionId"] for o in proposal.get("options", [])]:
            errors.append(f"changeProposals[{index}]: default {proposal['default']!r} is not one of its options")
        target = LAYERS.index(proposal["targetLayer"])
        if target >= current:
            errors.append(f"changeProposals[{index}]: must target an upstream layer of {doc['workstation']}")
    usage = doc["host"]["usage"]
    if usage["source"] != "host_reported" and usage.get("tokens") is not None:
        errors.append("host.usage.tokens: only host-reported usage may state tokens")
    if doc["contextSnapshotId"] is None:  # D6-2 §5 #8: C1 and C2 pack no context; every other workstation does
        if doc["workstation"] not in NO_PACK_WORKSTATIONS:
            errors.append(f"contextSnapshotId: only {'/'.join(NO_PACK_WORKSTATIONS)} runs may have none; {doc['workstation']} runs from a package")
        if not (doc.get("noSnapshotReason") or "").strip():
            errors.append("noSnapshotReason: a run without a context snapshot says why")
    elif "noSnapshotReason" in doc:
        errors.append("noSnapshotReason: only a run whose contextSnapshotId is null gives one")
    extra = doc.get("additionalSnapshotIds", [])
    if doc["contextSnapshotId"] is not None and doc["contextSnapshotId"] in extra or len(set(extra)) != len(extra):
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
    operation = doc["operation"]
    if operation in PAGE_OPERATIONS:  # v1.2 page operations (#34)
        if remote.get("artifactId") is not None:
            errors.append("remote.artifactId: page operations name a pageId, not a story artifact")
        if operation == "create_page" and doc["outcome"] != "confirmed" and remote.get("pageId") is not None:
            errors.append("remote.pageId: an unconfirmed create_page has no page yet")
        if operation != "create_page" and doc["outcome"] != "not_sent" and remote.get("pageId") is None:
            errors.append(f"remote.pageId: {operation} addresses a page and must name it")
        if operation in ("create_page", "update_page", "restore_page", "label_page_revision") and doc["outcome"] == "confirmed" \
                and (remote.get("pageId") is None or remote.get("revision") is None):
            errors.append("remote: a confirmed page write must record pageId and revision")
        if doc["outcome"] != "confirmed" and remote.get("revision") is not None:
            errors.append("remote.revision: only a confirmed page call records a revision")
    elif remote.get("pageId") is not None:
        errors.append("remote.pageId: only page operations record a pageId")
    return errors


OUTLINE_REVIEW_KINDS = ("episode_plan", "function_map", "ledger", "season_plan")  # C6 reads of the outline layer (D6-2)


def _rules_task(doc: dict) -> list[str]:
    errors = []
    evidence = doc.get("adoptionEvidence")
    if doc["status"]["adoption"] == "adopted_remote" and (evidence is None or evidence["kind"] != "remote_receipt"):
        errors.append("status.adoption: adopted_remote needs a remote_receipt reference; local fields cannot certify adoption")
    if doc["authorization"]["source"] == "none" and doc["writeScope"]:
        errors.append("writeScope: no authorization recorded, so nothing may be written")
    for index, constraint in enumerate(doc.get("constraints", [])):
        for category, hit in blocklist_hits(constraint["text"]):
            errors.append(f"constraints[{index}]: hits the {category} blocklist ({hit!r}); rejected whatever the origin ({constraint['origin']})")
        if constraint["origin"] == "orchestrator" and not constraint.get("cite"):
            errors.append(f"constraints[{index}]: an orchestrator constraint must cite the target clause it rests on")
    outline_read = doc.get("layer") == "C6" and (doc.get("target") or {}).get("kind") in OUTLINE_REVIEW_KINDS
    if doc.get("layer") in ("C5a", "C5b", "C6") and "dialogueTarget" not in doc and not outline_read:
        errors.append(f"dialogueTarget: a {doc['layer']} task must cite the dialogue-target targetId@revision it follows")
    return errors


# ---- D6-1: data files, shared helpers ------------------------------------------------------------------

DATA_DIR = SCHEMA_DIR / "data"
TOOL = Path(__file__).resolve().parents[1] / "drama_tools.py"
QUOTA_KEYS = {"estimates", "acceptedBand", "hardRules", "softRules", "within", "outside", "passByNumber",
              "voicedLinesPerMinute", "turnsPerMinute", "topicsPerMinute", "charsPerLine", "monologueShare",
              "shortReplyShare", "questionAnsweredRate", "eventsPerEpisode", "actionToSpeechRatio"}
QUOTA_PATTERN = re.compile(r"(?i)(turn|topic|line|sentence|speaker|switch|exchange)s?(Per[A-Z]\w*|Share|Band|Range|Quota|Limit|Max|Min)$")
DEFECT_KINDS = ("contradicts_reality", "missing", "internal_conflict", "motive", "knowledge_gap", "consequence_unwritten")
LOAD_BEARING_DESTINATIONS = ("confirmed_gone", "license", "decision")
ORIGIN_RANK = {"user_given": 2, "user_given_modified": 1}


def load_data(name: str) -> dict:
    """A bundled data file from schemas/data/ (question sets, constraint blocklist)."""
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def question_sets() -> dict:
    """Bundled question sets keyed by id@version, as answers[].questionsVersion cites them."""
    sets = {}
    for path in sorted(DATA_DIR.glob("*-questions.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        sets[f"{doc['id']}@{doc['version']}"] = doc
    return sets


def blocklist_hits(text: str) -> list[tuple[str, str]]:
    hits = []
    for category in load_data("constraint-blocklist")["categories"]:
        found = next((term for term in category["terms"] if term in text), None)
        if found is None:
            match = next((m for m in (re.search(p, text) for p in category["patterns"]) if m), None)
            found = match.group(0) if match else None
        if found is not None:
            hits.append((category["id"], found))
    return hits


def _quota_fields(value, path="$") -> list[str]:
    """Paths of fields that would turn a number into a judge (quotas, bands, within/outside)."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in QUOTA_KEYS or QUOTA_PATTERN.search(key):
                found.append(f"{path}.{key}")
            found.extend(_quota_fields(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_quota_fields(item, f"{path}[{index}]"))
    return found


def _no_quota(doc, what) -> list[str]:
    return [f"{path}: {what} carries no quota, band or within/outside field (numbers are not judges)" for path in _quota_fields(doc)]


def _duplicates(values) -> list:
    seen, dup = set(), []
    for value in values:
        if value in seen and value not in dup:
            dup.append(value)
        seen.add(value)
    return dup


def _episode_key(value) -> str:
    """ep6A, ep006A, 6A and 006A are one episode (D6-0 report §10)."""
    text = str(value).strip()
    text = text[2:] if text.lower().startswith("ep") else text
    return (text.lstrip("0") or "0").upper()


# ---- D6-1 rules --------------------------------------------------------------------------------------------

def _rules_function_map(doc: dict, ctx=None, notes=None) -> list[str]:
    errors, notes = [], notes if notes is not None else []
    records = (ctx or {}).get("records")
    if records is None:
        notes.append("function-map selected-without-open-load-bearing: not evaluated (needs --records context)")
    for t_index, thread in enumerate(doc["threads"]):
        for f_index, function in enumerate(thread["functions"]):
            where = f"threads[{t_index}].functions[{f_index}] {function['functionId']}"
            if function["status"] == "dropped" and not (function.get("droppedCost") or "").strip():
                errors.append(f"{where}: a dropped function must state droppedCost (which function sentence goes empty, which episodes)")
            selected = [c["candidateId"] for c in function["candidates"] if c["status"] == "selected"]
            if function["status"] == "selected" and len(selected) != 1:
                errors.append(f"{where}: a selected function has exactly one selected candidate, found {selected}")
            for duplicate in _duplicates(c["candidateId"] for c in function["candidates"]):
                errors.append(f"{where}: candidateId {duplicate} repeats within the function")
            for candidate in function["candidates"]:
                cwhere = f"{where}/{candidate['candidateId']}"
                if candidate["status"] == "selected" and candidate.get("losesFunctions"):
                    errors.append(f"{cwhere}: losesFunctions is not empty, so the system cannot select it (only the lead can drop a function)")
                if candidate["status"] == "rejected" and not candidate.get("rejectedBecause"):
                    errors.append(f"{cwhere}: a rejected candidate needs rejectedBecause")
                for duplicate in _duplicates(dep["depId"] for dep in candidate["ledgerDeps"]):
                    errors.append(f"{cwhere}: depId {duplicate} repeats within the candidate")
                for duplicate in _duplicates(step["stepId"] for step in candidate["steps"]):
                    errors.append(f"{cwhere}: stepId {duplicate} repeats within the candidate")
                step_ranks = [ORIGIN_RANK.get(step["origin"], 0) for step in candidate["steps"] if "origin" in step]
                if step_ranks and ORIGIN_RANK.get(candidate["origin"], 0) != max(step_ranks):
                    errors.append(f"{cwhere}: candidate origin {candidate['origin']} must be the most user-given of its steps' origins (d6-1-decisions #4)")
                for c_index, close in enumerate(candidate.get("closes", [])):
                    if not close.get("confirmedBy"):
                        errors.append(f"{cwhere}.closes[{c_index}]: a closed defect counts only with confirmedBy (a fresh-context check record)")
                if candidate["status"] == "selected" and records is not None:
                    refs = candidate["inquiryRef"] if isinstance(candidate["inquiryRef"], list) else [candidate["inquiryRef"]]
                    for ref in filter(None, refs):
                        record = records.get(ref)
                        if record is None:
                            errors.append(f"{cwhere}: inquiryRef {ref} is not among the given records")
                            continue
                        for a_index, answer in enumerate(record.get("answers", [])):
                            if _open_load_bearing(answer):
                                errors.append(f"{cwhere}: {ref} answers[{a_index}] is a load-bearing notHolds without a disposition")
    return errors


def _open_load_bearing(answer: dict) -> bool:
    disposition = answer.get("disposition") or {}
    return answer.get("holds") == "notHolds" and answer.get("loadBearing") is True \
        and disposition.get("to") not in LOAD_BEARING_DESTINATIONS


def _rules_ledger_entry(doc: dict, ctx=None, notes=None) -> list[str]:
    errors, notes = [], notes if notes is not None else []
    entries = {entry["id"]: entry for entry in doc["entries"]}
    for duplicate in _duplicates(entry["id"] for entry in doc["entries"]):
        errors.append(f"entries: id {duplicate} repeats")
    kinds = (ctx or {}).get("defectKinds")
    for index, entry in enumerate(doc["entries"]):
        where = f"entries[{index}] {entry['id']}"
        status = entry["status"]
        noted = {note["with"]: note["conflictKind"] for note in entry.get("conflictNotes", [])}
        if status == "contested" and not entry.get("conflictsWith"):
            errors.append(f"{where}: a contested entry names what it conflicts with (conflictsWith)")
        for other in entry.get("conflictsWith", []):
            if status == "contested" and not entry.get("conflictKind") and other not in noted:
                errors.append(f"{where}: conflict with {other} needs a conflictKind (entry conflictKind or conflictNotes)")
            back = entries.get(other, {})
            if status != "retired" and other in entries and entry["id"] not in back.get("conflictsWith", []) \
                    and entry["id"] not in back.get("conflictsOutOfScope", []):
                errors.append(f"{where}: conflictsWith {other}, but {other} does not list it back (conflictsWith or conflictsOutOfScope)")
        if status == "accepted_license" and not (entry.get("humanWords") or "").strip():
            errors.append(f"{where}: accepted_license needs humanWords (the lead's own words)")
        if status in ("license_pending", "accepted_license") and entry.get("defectKeys"):
            if kinds is None:
                notes.append("ledger-entry license-on-contradicts-reality: not evaluated (needs --defects context)")
            else:
                for key in entry["defectKeys"]:
                    if not kinds.get(key):
                        notes.append("ledger-entry license-on-contradicts-reality: some cited defects have no recorded defectKind")
                    elif "contradicts_reality" not in kinds[key]:
                        errors.append(f"{where}: a license may only cover a defect of kind contradicts_reality; {key} is {kinds[key]}")
        if status == "retired" and entry["origin"] in ORIGIN_RANK \
                and not (entry.get("decisionRef") or entry.get("retiresInto") or entry.get("retiredBy")):
            errors.append(f"{where}: retiring a user-given entry needs decisionRef, retiresInto or retiredBy")
        if entry.get("notAsked") and status == "verified":
            errors.append(f"{where}: an entry no answer landed on (notAsked) cannot be verified")
        if entry.get("subtype") == "state" and (entry["kind"] != "timeline" or not entry.get("stateOf")):
            errors.append(f"{where}: subtype state is a timeline entry with stateOf (d6-1-decisions #1)")
    return errors


def _rules_ledger_delta(doc: dict, ctx=None, notes=None) -> list[str]:
    return _delta_errors(doc, "")


def _delta_errors(delta: dict, prefix: str) -> list[str]:
    errors = []
    for index, write in enumerate(delta["writes"]):
        where = f"{prefix}writes[{index}]"
        change = write["change"]
        if not change:
            errors.append(f"{where}: change is empty; write field-level changes")
        if write["entryId"] == "new":
            missing = [key for key in ("id", "kind", "title", "origin", "status", "introducedAt") if key not in change]
            if missing:
                errors.append(f"{where}: a new entry is a complete entry; change lacks {missing}")
        if not write.get("supportedBy"):
            errors.append(f"{where}: supportedBy must cite the scene or beat that carries the change")
    for duplicate in _duplicates(w["change"].get("id") for w in delta["writes"] if w["entryId"] == "new"):
        errors.append(f"{prefix}writes: new entry id {duplicate} is created twice")
    return errors


def _rules_question_set(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = [f"questions: q {q} repeats" for q in _duplicates(question["q"] for question in doc["questions"])]
    for index, question in enumerate(doc["questions"]):
        if question.get("status") == "drafted" and not question.get("noteId"):
            errors.append(f"questions[{index}]: a drafted question carries the writer-note noteId it came from")
    base = (ctx or {}).get("baseQuestionSet")
    if base is not None:
        kept = {question["q"] for question in doc["questions"]}
        removed = sorted(question["q"] for question in base["questions"] if question["q"] not in kept)
        if removed:
            errors.append(f"questions: a project may add questions but not remove them; missing {removed}")
    return errors


def _rules_answers(doc: dict, ctx=None, notes=None) -> list[str]:
    errors, notes = [], notes if notes is not None else []
    sets = (ctx or {}).get("questionSets") or question_sets()
    qset = sets.get(doc["questionsVersion"])
    if qset is None:
        notes.append(f"answers question-set rules: not evaluated ({doc['questionsVersion']} is not a bundled question set)")
    kinds = {question["q"]: question["answerKind"] for question in qset["questions"]} if qset else {}
    reality = doc["questionsVersion"].startswith("reality-check")
    unknown_subset = sorted(set(doc.get("askedSubset", [])) - set(kinds)) if qset else []
    if unknown_subset:
        errors.append(f"askedSubset: {unknown_subset} are not questions of {doc['questionsVersion']}")
    # answers may be empty only in an errata re-check, which confirms map errata fixed and answers no question (re-run N3)
    if not doc["answers"] and not ((doc.get("target") or {}).get("kind") == "errata_check" and doc.get("errataConfirmed")):
        errors.append("answers: empty; only a target.kind errata_check record with errataConfirmed answers no question")
    anchors = {("landsOn" in a) + 2 * ("quoteRef" in a) for a in doc["answers"]}
    cards = (ctx or {}).get("cards")
    if cards is None:
        notes.append("answers empty-card-not-holds-source: not evaluated (needs --cards context)")
    counted = {"notHolds": [], "not_evaluable": 0}
    for index, answer in enumerate(doc["answers"]):
        where = f"answers[{index}] q{answer['q']}"
        if ("landsOn" in answer) == ("quoteRef" in answer):
            errors.append(f"{where}: exactly one anchor — landsOn (reality check) or quoteRef (dialogue check)")
        if qset and answer["q"] not in kinds:
            errors.append(f"{where}: q {answer['q']} is not in {doc['questionsVersion']}")
        if answer["holds"] == "notHolds":
            if reality and not answer.get("defectKey"):
                errors.append(f"{where}: a notHolds answer carries a defectKey (one key per gap, for dedup)")
            for kind in answer.get("defectKind", []) if reality else []:
                if kind not in DEFECT_KINDS:
                    errors.append(f"{where}: defectKind {kind!r} not in {list(DEFECT_KINDS)}")
            if reality and answer.get("loadBearing") is True:
                disposition = answer.get("disposition")
                if not disposition:
                    errors.append(f"{where}: a load-bearing notHolds needs a disposition (confirmed_gone, license or decision)")
                elif disposition["to"] == "leaves_open":
                    errors.append(f"{where}: a load-bearing gap cannot be left open; only non-load-bearing gaps go to leavesOpen")
                elif not disposition.get("ref"):
                    errors.append(f"{where}: disposition {disposition['to']} must cite its check record, ledger entry or decision")
        if answer["holds"] == "not_evaluable" and reality and "because" not in answer:
            errors.append(f"{where}: not_evaluable says why (because: no_card, card_says_not_found or cannot_answer)")
        if cards is not None and answer["holds"] == "holds":
            empty = [card for card in answer.get("realityRef", []) if cards.get(card.split("#")[0].split("@")[0]) == "empty"]
            if empty:
                errors.append(f"{where}: cites empty card(s) {empty} as the source of a holds answer")
        if kinds.get(answer["q"]) == "informational":
            continue
        if answer["holds"] == "notHolds":
            counted["notHolds"].append(answer)
        elif answer["holds"] == "not_evaluable":
            counted["not_evaluable"] += 1
    if len(anchors) > 1:
        errors.append("answers: one record uses one anchor kind throughout (landsOn or quoteRef)")
    expected = allowed_outcomes(counted["notHolds"], counted["not_evaluable"])
    if doc["outcome"] not in expected:
        errors.append(f"outcome: {doc['outcome']} disagrees with the answers ({' or '.join(sorted(expected))}; informational questions do not count)")
    errors += subject_errors(doc)
    for c_index, close in enumerate(doc.get("closes", [])):
        if not close.get("confirmedBy"):
            errors.append(f"closes[{c_index}]: a closed defect counts only with confirmedBy (a fresh-context check record)")
    patched = {a.get("defectKey") for a in doc["answers"] if a.get("patch")}
    for c_index, close in enumerate(doc.get("closes", [])):
        if close["defectId"] in patched:
            errors.append(f"closes[{c_index}]: {close['defectId']} was answered with a patch, so it does not count as closed")
    return errors


def allowed_outcomes(not_holds: list, not_evaluable: int, inherited_may_say_fail: bool = False) -> set:
    """The outcomes a record's counted answers allow. D6-2 §5 #19: when every notHolds is not load-bearing the record may
    also say pass_with_unverified (the gaps stay in leavesOpen); a load-bearing one keeps it at fail. All-inherited gaps
    say fail_inherited (check-answers also takes fail there, as before)."""
    if not_holds:
        if all(a.get("inheritedFrom") for a in not_holds):
            failed = {"fail_inherited", "fail"} if inherited_may_say_fail else {"fail_inherited"}
        else:
            failed = {"fail"}
        if all(a.get("loadBearing") is not True for a in not_holds):
            failed.add("pass_with_unverified")
        return failed
    return {"pass_with_unverified"} if not_evaluable else {"pass"}


def subject_errors(doc: dict) -> list[str]:
    """D6-2 §5 #20: a record covering two or more moves or candidates (target.ids) says per answer which (subject)."""
    ids = (doc.get("target") or {}).get("ids") or []
    errors = []
    for index, answer in enumerate(doc.get("answers") or []):
        subject = answer.get("subject") if isinstance(answer, dict) else None
        if len(ids) > 1 and not subject:
            errors.append(f"answers[{index}]: the record covers {len(ids)} subjects (target.ids), so each answer names its subject")
        elif subject and ids and subject not in ids:
            errors.append(f"answers[{index}]: subject {subject!r} is not one of target.ids {ids}")
    return errors


def _rules_season_plan(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = []
    for layer in ("episodes", "episodesBeforeAction"):
        for duplicate in _duplicates(_episode_key(e["episode"]) for e in doc.get(layer, [])):
            errors.append(f"{layer}: episode {duplicate} appears twice")
    for index, episode in enumerate(doc["episodes"]):
        where, capacity = f"episodes[{index}] ep{episode['episode']}", episode["capacity"]
        if capacity["status"] == "exceeds" and not (capacity.get("action") and (capacity.get("actionDetail") or "").strip()):
            errors.append(f"{where}: exceeds needs an action (rearrange, split or drop_function) and actionDetail; pick one, do not park it")
        if re.search(r"待定|pending|TBD", json.dumps(capacity, ensure_ascii=False), re.I):
            errors.append(f"{where}: capacity must not say 待定/pending; choose the action")
    return errors


def _rules_episode_plan(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = []
    scenes = doc["events"]["scenes"]
    beats = [beat["beatId"] for scene in scenes for beat in scene["beats"]]
    scene_ids = [scene["sceneId"] for scene in scenes]
    for duplicate in _duplicates(scene_ids + beats):
        errors.append(f"events: id {duplicate} repeats")
    closing = doc["exit"]["closingEvent"]["beatRef"]
    if closing != scenes[-1]["beats"][-1]["beatId"]:
        errors.append(f"exit.closingEvent.beatRef: {closing} is not the last beat of the last scene ({scenes[-1]['beats'][-1]['beatId']})")
    known = set(beats) | set(scene_ids)
    for i_index, info in enumerate(doc["infoLedger"]):
        for f_index, fact in enumerate(info["facts"]):
            if fact["carrierBeat"] not in known:
                errors.append(f"infoLedger[{i_index}].facts[{f_index}]: carrierBeat {fact['carrierBeat']} is not a beat of this episode")
    for duplicate in _duplicates(fact["factId"] for info in doc["infoLedger"] for fact in info["facts"]):
        errors.append(f"infoLedger: factId {duplicate} repeats")
    errors.extend(_delta_errors(doc["ledgerDelta"], "ledgerDelta."))
    for index, write in enumerate(doc["ledgerDelta"]["writes"]):
        support = write.get("supportedBy")
        for ref in support if isinstance(support, list) else [support] if support else []:
            if ref not in known:
                errors.append(f"ledgerDelta.writes[{index}]: supportedBy {ref} is not a scene or beat of this episode")
    if _episode_key(doc["ledgerDelta"]["episode"]) != _episode_key(doc["episode"]):
        errors.append("ledgerDelta.episode: differs from the plan's episode")
    return errors


def _rules_decision_queue(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = [f"entries: id {d} repeats" for d in _duplicates(entry["id"] for entry in doc["entries"])]
    for index, entry in enumerate(doc["entries"]):
        where = f"entries[{index}] {entry['id']}"
        options = {option["optionId"]: option for option in entry["options"]}
        default = options.get(entry["default"])
        if default is None:
            errors.append(f"{where}: default {entry['default']!r} is not one of the optionIds {list(options)}")
        else:
            loses = default.get("losesFunctions") or []
            unknown = isinstance(loses, str) and loses.startswith("not_evaluable") or isinstance(loses, list) and loses \
                and all(isinstance(i, dict) and str(i.get("status", "")).startswith("not_evaluable") for i in loses)
            if loses and not unknown:
                errors.append(f"{where}: the default option drops function sentences (losesFunctions); the system default keeps every function")
        if entry["status"] == "decided" and not (entry.get("humanWords") or "").strip():
            errors.append(f"{where}: decided needs humanWords (the lead's own words)")
        if entry["status"] == "decided" and entry.get("decision") not in options:
            errors.append(f"{where}: decided needs decision, the chosen optionId (one of {list(options)})")
    return errors


def _rules_media_profile(doc: dict, ctx=None, notes=None) -> list[str]:
    return _no_quota(doc, "a media profile")


def _rules_dialogue_exchange(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = []
    if doc["startMs"] > doc["endMs"]:
        errors.append("startMs: after endMs")
    if doc.get("scope", {}).get("level") == "studio" and doc.get("origin", {}).get("kind") != "mali_story_template":
        errors.append("scope.level: studio only for exchanges whose origin.kind is mali_story_template (no project sentences)")
    if doc.get("refKind") == "local_fingerprint" and not doc.get("localSha256"):
        errors.append("localSha256: a local_fingerprint reference needs the fingerprint")
    if doc["snapshotId"] is None and doc.get("refKind") == "snapshot":
        errors.append("refKind: snapshot reference without a snapshotId; use local_fingerprint")
    return errors


def _rules_corpus_manifest(doc: dict, ctx=None, notes=None) -> list[str]:
    keys = [(e["templateId"], e["episodeIndex"]) for e in doc["episodes"]]
    return [f"episodes: {key[0]} episode {key[1]} listed twice" for key in _duplicates(keys)]


def _rules_dialogue_plan(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = _no_quota(doc, "a dialogue plan")
    facts = {item["factId"] for item in doc["infoLedger"]}
    exchanges, segments_used = set(), []
    for s_index, scene in enumerate(doc["scenes"]):
        for t_index, topic in enumerate(scene["topics"]):
            where = f"scenes[{s_index}].topics[{t_index}] {topic['topicId']}"
            segment_ids = [segment["segmentId"] for segment in topic["segments"]]
            for exchange in topic["exchanges"]:
                exchanges.add(exchange["exchangeId"])
                if "segmentId" in exchange and exchange["segmentId"] not in segment_ids:
                    errors.append(f"{where}: exchange {exchange['exchangeId']} names unknown segment {exchange['segmentId']}")
                unknown = [ref for ref in exchange["carries"] if ref not in facts]
                if unknown:
                    errors.append(f"{where}: exchange {exchange['exchangeId']} carries {unknown}, not in infoLedger factIds")
            segments_used.extend(segment_ids)
            cites = topic["shape"].get("citesSituation")
            situation_keys = ("speakerWants", "listenerKnows", "emotion", "relation", "powerDirection", "addresseeIsChild", "audienceLearns")
            if not cites and not any(key in topic["shape"]["reason"] for key in situation_keys):
                errors.append(f"{where}: shape.reason must cite the situation (citesSituation, or name speakerWants/listenerKnows/emotion/relation)")
            for audience in topic["situation"].get("audienceLearns", []):
                if audience not in facts:
                    errors.append(f"{where}: audienceLearns {audience} is not in infoLedger")
    for duplicate in _duplicates(segments_used):
        errors.append(f"scenes: segmentId {duplicate} repeats")
    for index, item in enumerate(doc["infoLedger"]):
        carried = item["carriedBy"]
        if not carried.get("exchangeIds") and not carried.get("pictureReason"):
            errors.append(f"infoLedger[{index}] {item['factId']}: carried by no exchange and no registered picture reason")
        unknown = [ref for ref in carried.get("exchangeIds", []) if ref not in exchanges]
        if unknown:
            errors.append(f"infoLedger[{index}] {item['factId']}: carriedBy names unknown exchanges {unknown}")
    return errors


def _rules_dialogue_target(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = _no_quota(doc, "a dialogue target")
    errors += [f"conventions: id {d} repeats" for d in _duplicates(c["id"] for c in doc["conventions"])]
    return errors


def _project_only(doc, what) -> list[str]:
    scope = doc.get("scope")
    if scope is not None and scope.get("level") != "project":
        return [f"scope.level: {what} hold private project sentences and stay project-level"]
    return []


def _rules_contrast_pair(doc: dict, ctx=None, notes=None) -> list[str]:
    return _project_only(doc, "contrast pairs")


def _rules_writer_note(doc: dict, ctx=None, notes=None) -> list[str]:
    return _project_only(doc, "writer notes")


def _rules_retell_record(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = []
    if len(doc["readingScope"]) != 1:
        errors.append(f"readingScope: a cold read takes exactly one item (this episode's text or plan events), found {len(doc['readingScope'])}")
    if not doc["promptVersion"]:
        errors.append("promptVersion: name the bundled cold-read prompt version")
    return errors


def _rules_plan_text_consistency(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = _no_quota(doc, "a consistency record")
    for index, topic in enumerate(doc.get("topics", [])):
        if topic["verdict"] == "inconsistent" and not (topic.get("note") or "").strip():
            errors.append(f"topics[{index}]: an inconsistent topic says where (note)")
    return errors


def _rules_defect_register(doc: dict, ctx=None, notes=None) -> list[str]:
    errors = [f"defects: defectId {d} repeats" for d in _duplicates(defect["defectId"] for defect in doc["defects"])]
    for index, defect in enumerate(doc["defects"]):
        if not defect["records"] and not defect.get("premiseRoundRecords"):
            errors.append(f"defects[{index}] {defect['defectId']}: a defect is derived from at least one answer record")
        disposition = defect.get("disposition")
        if isinstance(disposition, dict) and disposition.get("to") == "conflicting" and not disposition.get("dispositions"):
            errors.append(f"defects[{index}] {defect['defectId']}: a conflicting disposition lists the records' dispositions[]")
        if defect["loadBearing"] and isinstance(disposition, dict) and disposition.get("to") == "leaves_open":
            errors.append(f"defects[{index}] {defect['defectId']}: a load-bearing gap cannot be left open")
    return errors


def _rules_selection(doc: dict, ctx=None, notes=None) -> list[str]:
    return _cold_reader_package(doc.get("role"), doc["items"], "items")


# ---- legacy forms: D6-0 wrote some fields two ways; the canonical form is in the schema ---------------------

def _legacy_answers(doc, hints):
    records = []
    for answer in doc.get("answers", []) if isinstance(doc.get("answers"), list) else []:
        if not isinstance(answer, dict):
            continue
        if isinstance(answer.get("kind"), list):
            answer["defectKind"] = answer.get("defectKind") or answer.pop("kind")
            answer.pop("kind", None)
            hints.add("answers[].kind (list) → defectKind")
        if isinstance(answer.get("defectKeys"), list) and "defectKey" not in answer:
            answer["defectKey"] = (answer.pop("defectKeys") or [""])[0]
            hints.add("answers[].defectKeys (list) → defectKey (one key per answer)")
        disposition = answer.get("disposition")
        if isinstance(disposition, dict):
            to = {"decision_queue": "decision", "license_pending": "license", "accepted_license": "license"}.get(disposition.get("to"))
            if to:
                disposition["to"] = to
                hints.add("disposition.to decision_queue/license_pending → decision/license")
            route = {"a": "confirmed_gone", "b": "license", "c": "decision"}.get(disposition.get("route"))
            if disposition.get("to") is None and route:
                disposition["to"] = route
                hints.add("disposition.route a/b/c → to confirmed_gone/license/decision")
            if disposition.get("to") is None:
                answer.pop("disposition")
                hints.add("disposition without to (audit notes) → no disposition")
        if isinstance(answer.get("inheritedAt"), str):
            match = re.match(r"q(\d+)\D*?\s+(.+)", answer["inheritedAt"])
            answer["inheritedAt"] = {"q": int(match.group(1)), "landsOn": match.group(2)} if match else {"q": 0, "landsOn": answer["inheritedAt"]}
            hints.add("inheritedAt string → {q, landsOn}")
        basis = answer.get("loadBearingBasis")
        if isinstance(basis, str) and basis not in ("stated_in_record", "has_downstream", "function_sentence_step"):
            answer["loadBearingWhy"] = answer.get("loadBearingWhy") or basis
            answer.pop("loadBearingBasis")
            hints.add("loadBearingBasis free text → loadBearingWhy (basis is an enum, d6-1-decisions #8)")
        if answer.get("holds") == "not_evaluable" and "because" not in answer and "landsOn" in answer:
            answer["because"] = "cannot_answer"
            hints.add("not_evaluable without because (field added after the first round)")
        records.append(answer)
    if "scopeOfQuestions" in doc and "askedSubset" not in doc:
        doc["askedSubset"] = doc.pop("scopeOfQuestions")
        hints.add("scopeOfQuestions → askedSubset")
    for close in doc.get("closes", []) if isinstance(doc.get("closes"), list) else []:
        if isinstance(close, dict):
            if "defectId" not in close and "defect" in close:
                close["defectId"] = close["defect"]
                hints.add("closes[].defect → defectId")
            if "confirmedBy" not in close and close.get("record"):
                close["confirmedBy"] = close["record"]
                hints.add("closes[].record → confirmedBy")
    if doc.get("outcome") == "fail" and records:
        open_gaps = [a for a in records if a.get("holds") == "notHolds" and a.get("q") not in (14, 15)]
        if open_gaps and all(a.get("inheritedFrom") for a in open_gaps):
            doc["outcome"] = "fail_inherited"
            hints.add("outcome fail where every gap is inherited → fail_inherited")


def _legacy_ledger(doc, hints):
    for entry in doc.get("entries", []) if isinstance(doc.get("entries"), list) else []:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("nextNecessaryMove"), str):
            entry["nextNecessaryMove"] = {"mandated": None, "customary": None, "legacyText": entry["nextNecessaryMove"]}
            hints.add("nextNecessaryMove string → {mandated, customary}")
        if isinstance(entry.get("defectKey"), str):
            entry["defectKeys"] = entry.get("defectKeys") or [entry.pop("defectKey")]
            entry.pop("defectKey", None)
            hints.add("entry defectKey (string) → defectKeys (list)")


def _legacy_function_map(doc, hints):
    for thread in doc.get("threads", []) if isinstance(doc.get("threads"), list) else []:
        for function in thread.get("functions", []) if isinstance(thread, dict) else []:
            for candidate in function.get("candidates", []) if isinstance(function, dict) else []:
                ranks = [ORIGIN_RANK.get(s.get("origin"), 0) for s in candidate.get("steps", []) if isinstance(s, dict) and "origin" in s]
                if ranks and ORIGIN_RANK.get(candidate.get("origin"), 0) != max(ranks):
                    candidate["origin"] = {2: "user_given", 1: "user_given_modified", 0: "designed"}[max(ranks)]
                    hints.add("candidate origin designed while steps are user-given → the most user-given step origin")


def _legacy_contrast_pair(doc, hints):
    if "whyNotHere" not in doc:
        why = (doc.get("negative") or {}).get("whyNotHere") if isinstance(doc.get("negative"), dict) else None
        if why or doc.get("why"):
            doc["whyNotHere"] = why or doc["why"]
            hints.add("negative.whyNotHere / why → top-level whyNotHere")


def _legacy_retell(doc, hints):
    if "promptVersion" not in doc:
        doc["promptVersion"] = {"legacy": "not recorded"}
        hints.add("promptVersion missing (recorded only from the second round on)")


def _legacy_defect_register(doc, hints):
    for defect in doc.get("defects", []) if isinstance(doc.get("defects"), list) else []:
        basis = defect.get("loadBearingBasis") if isinstance(defect, dict) else None
        if isinstance(basis, list) and "on_implementation" in basis:
            defect["loadBearingBasis"] = [b for b in basis if b != "on_implementation"]
            hints.add("loadBearingBasis on_implementation (retired basis, finding #51) → dropped")


def _legacy_question_set(doc, hints):
    for question in doc.get("questions", []) if isinstance(doc.get("questions"), list) else []:
        if isinstance(question, dict) and "answerKind" not in question:
            question["answerKind"] = "tristate"
            hints.add("questions[].answerKind missing (added in D6-1; v1 data marks q14/q15 of the reality check informational)")


LEGACY = {"question-set": _legacy_question_set, "answers": _legacy_answers, "ledger-entry": _legacy_ledger, "function-map": _legacy_function_map,
          "contrast-pair": _legacy_contrast_pair, "retell-record": _legacy_retell, "defect-register": _legacy_defect_register}

RULES = {"knowledge-card": _rules_knowledge_card, "context-snapshot": _rules_context_snapshot,
         "review-record": _rules_review_record, "run-handoff": _rules_run_handoff,
         "remote-receipt": _rules_remote_receipt, "task": _rules_task, "selection": _rules_selection,
         "function-map": _rules_function_map, "ledger-entry": _rules_ledger_entry, "ledger-delta": _rules_ledger_delta,
         "question-set": _rules_question_set, "answers": _rules_answers, "season-plan": _rules_season_plan,
         "episode-plan": _rules_episode_plan, "decision-queue": _rules_decision_queue, "media-profile": _rules_media_profile,
         "dialogue-exchange": _rules_dialogue_exchange, "corpus-manifest": _rules_corpus_manifest,
         "contrast-pair": _rules_contrast_pair, "writer-note": _rules_writer_note, "dialogue-plan": _rules_dialogue_plan,
         "dialogue-target": _rules_dialogue_target, "retell-record": _rules_retell_record,
         "plan-text-consistency": _rules_plan_text_consistency, "defect-register": _rules_defect_register}
D6_RULES = set(RULES) - {"knowledge-card", "context-snapshot", "review-record", "run-handoff", "remote-receipt", "task"}


def _errors(name: str, document, context, notes) -> list[str]:
    schema = load_schema(name)
    errors: list[str] = []
    _validate(document, schema, schema, "$", errors)
    if not errors and name in RULES:
        errors.extend(RULES[name](document, context, notes) if name in D6_RULES else RULES[name](document))
    return errors


def check_contract(name: str, document, context: dict | None = None) -> list[str]:
    return _errors(name, document, context, [])


def check_contract_detailed(name: str, document, context: dict | None = None) -> dict:
    """Errors, plus which legacy D6-0 forms were seen and whether the document fails only because of them."""
    notes: list[str] = []
    errors = _errors(name, document, context, notes)
    hints: set[str] = set()
    only_legacy = False
    if name in LEGACY and isinstance(document, dict):
        normalized = json.loads(json.dumps(document))
        LEGACY[name](normalized, hints)
        if errors and hints:
            only_legacy = not _errors(name, normalized, context, [])
    return {"errors": errors, "legacyForms": sorted(hints), "failedOnlyOnLegacyForms": only_legacy,
            "notEvaluated": sorted(set(notes))}


def run_contract_check(name: str, path: str, context: dict | None = None) -> dict:
    """One JSON document, or one per line for .jsonl (exchanges, contrast pairs); line errors are prefixed."""
    text = Path(path).read_text(encoding="utf-8")
    documents = [json.loads(line) for line in text.splitlines() if line.strip()] if path.endswith(".jsonl") else [json.loads(text)]
    errors, hints, notes, only_legacy = [], set(), set(), True
    for number, document in enumerate(documents, 1):
        detail = check_contract_detailed(name, document, context)
        prefix = f"line {number}: " if path.endswith(".jsonl") else ""
        errors.extend(prefix + error for error in detail["errors"])
        hints.update(detail["legacyForms"])
        notes.update(detail["notEvaluated"])
        only_legacy = only_legacy and (not detail["errors"] or detail["failedOnlyOnLegacyForms"])
    absolute = str(Path(path).absolute())
    return {"ok": True, "contract": name, "path": absolute, "passed": not errors, "errors": errors,
            "legacyForms": sorted(hints), "failedOnlyOnLegacyForms": bool(errors) and only_legacy,
            "notEvaluated": sorted(notes), "enforcement": "S", "remote_verified": False, "adoption_verified": False,
            "reproduceCommand": f"python3 -B {TOOL} contract-check {name} {absolute}"}
