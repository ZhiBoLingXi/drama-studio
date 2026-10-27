"""Assemble a reproducible context-snapshot from a task, a host selection and local cache/knowledge files.

Deterministic assembly only: no semantic selection, no truncation, no network, no model. Reads --task,
--selection, <project>/.drama/cache/ (through its manifest v0 or v1: remote_page by pageId@revision, remote_artifact by artifactId), <project>/knowledge/cards/ and, for local_file
items, files inside <project>/.drama/ (not its cache), <project>/runs/ or <project>/planning/, or a bundled question set
by id ("question-set:reality-check-questions@v1", read from the skill's data/); writes only
<project>/.drama/snapshots/, and never overwrites an existing snapshot.

D6-1 roles add package rules: a cold_reader gets exactly one project_facts item and nothing authored (of an episode
plan, only its plan-events export; D6-2); a C5a
(dialogue_designer) package needs this episode's plan with capacity.status fits, or proposal:<id> whose decision has a
default; a C5b package (task.layer C5b) needs a dialogue plan that passes contract-check. Samples (--exemplars,
--contrast-pairs) are the corpus positives and contrast pairs the packed dialogue plan cites, at most two positives and
one pair per topic, added first positives, then pairs, then second positives while the budget lasts; the rest are
listed as omitted for budget. Samples are the one thing the package leaves out to fit, and it says so.

D6-3: samples go into their own samples partition (no longer current_plan) as masked sample records (situation,
walkthrough, skeleton, maskedLines), never raw transcript rows. --exemplars is a JSONL of such records, or the dialogue
plan itself, whose exemplars.positives objects are packed as their own character ranges. --quotes-per-topic caps the
masked lines a topic's samples carry in all (default 2, 0 for none); a sample that would pass the cap is left out whole
(reason quote_cap). With --studio-corpus <studio root>/corpus/, --exemplars may be a JSONL in that folder (resolved
path; `..` or a symlink out of it is refused); its packed records must be scope.level studio from a mali-story template,
and are packed under the id studio-corpus/<path>. Contrast pairs and dialogue plans stay project files. A written package appends its samples to .drama/packs/history.json, and a sample the previous
episode's package also held is reported under samples.repeatedFromPreviousEpisode (reported, not refused).
With --annotations-only, a C5a (dialogue_designer) package with --exemplars and no dialogue plan yet (wording rulings #11) packs the labelled
exchanges of that file as their annotation fields only (situation, walkthrough, skeleton, about, ids): raw and masked
lines are stripped into a view under .drama/packs/annotations/, which the sample ranges point into.

D6-2: in a project that has started the outline layer (season_check.outline_project: planning/season-plan.json or
planning/function-map.json, or a JSON record under planning/ledger/ or planning/episodes/; the empty folders
init-project creates do not count, and 0.3.6-era projects have none of these), a C4 author package must hold the season plan and a ledger (season-check's
outline-season-assigned and outline-ledger-delta read them), else exit 2. Other projects' C4 packages are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from contract_check import COMPARISON_ROLES, DATA_DIR, check_contract
from corpus_studio import studio_corpus_dir, studio_row_problem
from receipt import MANIFESTS, effective_entries
from season_check import layer_records, outline_project, record_kind

PARTITIONS = ["task", "project_facts", "current_plan", "knowledge", "unknowns", "samples"]  # samples: D6-3, no longer in current_plan
QUOTES_PER_TOPIC = 2  # masked corpus lines (positives) per topic (D6-3 decisions §1, plan §8 #2); 0 packs none
HISTORY = ".drama/packs/history.json"  # which samples went into which episode's package
ANNOTATIONS = ".drama/packs/annotations"  # C5a's label-only views of labelled exchange files (wording rulings #11)
ANNOTATION_FIELDS = ("exchangeId", "templateId", "episodeIndex", "about", "situation", "walkthrough", "skeleton")
LOCAL_ROOTS = (".drama", "runs", "planning")  # the only folders a local_file selection item may read from
SAMPLE_ROOTS = (".drama", "runs", "knowledge", "planning", "corpus")  # corpus exchanges, project contrast pairs, a dialogue plan;
# corpus/ at the project root is where a new project keeps its corpus (D6-4 decisions §2)
SAMPLE_ROLES = ("dialogue_designer", "author")


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
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") not in MANIFESTS or not isinstance(manifest.get("entries"), list):
        raise ValueError(f"cache manifest must be an object with schemaVersion {' or '.join(MANIFESTS)} and an entries list: {path}")
    return manifest["entries"]


def _read_cache(root: Path, cache: Path, entries: list, ref: dict, where: str, allow_unverified: bool,
                errors: list[str], unknowns: list[str]):
    """A remote_artifact (by artifactId; slot from its strongest entries) or a remote_page (by pageId, v1.2) cache file."""
    page = ref["kind"] == "remote_page"
    matches = [entry for entry in entries if isinstance(entry, dict)
               and entry.get("pageId" if page else "artifactId") == ref["id"]
               and type(entry.get("revision")) is int and entry["revision"] == ref["revision"]]
    if not matches:
        return "missing", None
    # a page is its own identity; an artifact's slot comes from its strongest-source entries
    slots = {ref["id"]} if page else {entry.get("slot") for entry in effective_entries(matches)}
    if len({(entry.get("path"), entry.get("sha256")) for entry in matches}) > 1 or len(slots) > 1:
        errors.append(f"{where}: cache manifest has conflicting entries for this {'page' if page else 'artifact'} revision")
        return "error", None
    entry = dict(matches[-1], slot=slots.pop())
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


def _read_local(root: Path, ref: dict, where: str, errors: list[str]):
    """A local_file (#26): a project-relative path inside .drama/, runs/ or planning/, read as is and pinned by its sha256.

    Absolute paths, `..`, backslashes and anything resolving outside those folders (symlinks included) are input
    errors. The revision is null or the sha256 the host expects; the snapshot records the file's actual sha256 as both.
    """
    name = ref["id"]
    parts = name.split("/")
    if (not name or name.startswith("/") or "\\" in name or "\0" in name or any(part in ("", ".", "..") for part in parts)
            or parts[0] not in LOCAL_ROOTS or len(parts) < 2):
        raise ValueError(f"{where}: local_file id must be a relative path inside {' or '.join(f'{folder}/' for folder in LOCAL_ROOTS)} "
                         "without '..' (e.g. .drama/reviews/rev-ep45-1.json, runs/ep45/review.md or planning/season-plan.json)")
    if parts[:2] == [".drama", "cache"]:
        raise ValueError(f"{where}: cached pages and artifacts are packed as remote_page or remote_artifact through the cache manifest, not as local_file")
    if ref["revision"] is not None and not (isinstance(ref["revision"], str) and re.fullmatch(r"sha256:[a-f0-9]{64}", ref["revision"])):
        raise ValueError(f"{where}: a local_file revision must be null or the sha256:<hex> of the file")
    path = root / name
    for folder in LOCAL_ROOTS:
        if (root / folder).exists() or (root / folder).is_symlink():
            _inside(root / folder, root, folder)
    resolved = path.resolve()
    if not resolved.is_relative_to((root / parts[0]).resolve()):
        errors.append(f"{where}: {name} resolves outside {parts[0]}/ ({resolved}); refused to read it")
        return "error", None
    if not resolved.is_file():
        return "missing", None
    data = resolved.read_bytes()
    if ref["revision"] is not None and ref["revision"] != _sha(data):
        errors.append(f"{where}: revision pins {ref['revision']} but the file is {_sha(data)}")
        return "error", None
    return "ok", data


QUESTION_SET = "question-set:"  # a bundled question set packed by id@version (D6-2 §5 #22)
LEXICON = "lexicon:"  # a bundled genre lexicon packed the same way (D6-3 walkthrough #9)
BUNDLED = {QUESTION_SET: "*-questions.json", LEXICON: "*-lexicon.json"}


def _read_question_set(ref: dict, where: str, errors: list[str]):
    """local_file "question-set:<id>@<version>" or "lexicon:<id>@<version>": a question set or genre lexicon bundled
    under data/, read only, never copied into the project; pinned by its sha256 like any local_file."""
    prefix = next(p for p in BUNDLED if ref["id"].startswith(p))
    wanted = ref["id"][len(prefix):]
    for path in sorted(DATA_DIR.glob(BUNDLED[prefix])):
        data = path.read_bytes()
        doc = json.loads(data.decode("utf-8"))
        if f"{doc.get('id')}@{doc.get('version')}" == wanted:
            if ref["revision"] is not None and ref["revision"] != _sha(data):
                errors.append(f"{where}: revision pins {ref['revision']} but the bundled question set is {_sha(data)}")
                return "error", None
            return "ok", data
    raise ValueError(f"{where}: no bundled {prefix[:-1]} {wanted!r} under data/ (ids look like reality-check-questions@v1, genre-lexicon@v1)")


def _name(errors: list[str], item_labels: list[str], omitted_labels: list[str]) -> list[str]:
    named = []
    for error in errors:
        match = re.search(r"\b(items|omitted)\[(\d+)\]", error)
        labels = item_labels if match and match.group(1) == "items" else omitted_labels
        named.append(f"{error} — {labels[int(match.group(2))]}" if match and int(match.group(2)) < len(labels) else error)
    return named


def run_context_pack(project, task, selection, role: str, budget: int, dry_run: bool = False,
                     allow_unverified: bool = False, exemplars: str | None = None, contrast_pairs: str | None = None,
                     quotes_per_topic: int = QUOTES_PER_TOPIC, studio_corpus: str | None = None,
                     annotations_only: bool = False) -> dict:
    root = Path(project).expanduser().absolute()
    if not root.is_dir():
        raise ValueError(f"Project directory not found: {root}")
    if budget < 1:
        raise ValueError("--budget must be a positive number of chars")
    if quotes_per_topic < 0:
        raise ValueError("--quotes-per-topic must be 0 or more")
    studio = studio_corpus_dir(studio_corpus) if studio_corpus else None  # plan §8 #1: the corpus cache may be studio-level
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
    errors, unknowns, packed_docs = [], list(chosen.get("unknowns", [])), []
    cache, cards = root / ".drama" / "cache", root / "knowledge" / "cards"
    for folder, what in ((cache, ".drama/cache"), (cards, "knowledge/cards")):
        if folder.exists():
            _inside(folder, root, what)
    entries, slots, card_revisions, pages = None, {}, {}, {}
    for index, item in enumerate(chosen["items"]):
        ref = item["ref"]
        where = f"selection.items[{index}] ({_label(ref)})"
        if ref["kind"] not in ("remote_page", "remote_artifact", "knowledge_card", "local_file"):
            raise ValueError(f"{where}: kind must be remote_page or remote_artifact (cache), knowledge_card or local_file (.drama/, runs/ or planning/)")
        if ref["kind"] != "local_file" and (not isinstance(ref["revision"], int) or isinstance(ref["revision"], bool)):
            raise ValueError(f"{where}: revision must pin an integer revision" + (" (a remote_page is pageId + revision)" if ref["kind"] == "remote_page" else ""))
        span = ref.get("range")
        if span and span["start"] > span["end"]:
            raise ValueError(f"{where}: range start {span['start']} is after end {span['end']}")
        clean = {key: ref[key] for key in ("kind", "id", "revision", "sha256", "range") if key in ref}
        if ref["kind"] in ("remote_artifact", "remote_page"):
            entries = _manifest(cache) if entries is None else entries
            status, loaded = _read_cache(root, cache, entries, ref, where, allow_unverified, errors, unknowns)
        elif ref["kind"] == "local_file":
            reader = _read_question_set if ref["id"].startswith(tuple(BUNDLED)) else (lambda r, w, e: _read_local(root, r, w, e))
            status, loaded = reader(ref, where, errors)
            loaded = (loaded, None) if status == "ok" else loaded
        else:
            status, loaded = _read_card(cards, ref, where, task_doc["project"]["localId"], errors)
        if status in ("missing", "retired"):
            omitted.append({"ref": clean, "required": item["required"], "reason": "missing" if status == "missing" else "not_relevant"})
            omitted_labels.append(where)
            continue
        if status == "error":
            continue
        data, detail = loaded
        if ref["kind"] == "remote_page":
            usage = item.get("usage", "project_text")
            prior = pages.setdefault(ref["id"], (ref["revision"], index))
            if prior[0] != ref["revision"]:
                errors.append(f"{where}: page {ref['id']} is already packed at r{prior[0]} (selection.items[{prior[1]}]); one package cannot mix revisions of a page")
        elif ref["kind"] == "remote_artifact":
            usage = item.get("usage", "project_text")
            prior = slots.setdefault(detail, (ref["id"], ref["revision"], index))
            if prior[:2] != (ref["id"], ref["revision"]):
                errors.append(f"{where}: slot {detail!r} is already packed as {prior[0]}@r{prior[1]} (selection.items[{prior[2]}]); one package cannot mix revisions of a slot")
        elif ref["kind"] == "local_file":
            usage = item.get("usage", "project_text")
            clean["revision"] = _sha(data)  # the file's bytes are its revision, as for the task item
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
        if usage == "comparison_only" and role not in COMPARISON_ROLES:
            errors.append(f"{where}: comparison_only material is limited to {'/'.join(COMPARISON_ROLES)}, not {role}")
        if role in ("reader_effect", "dialogue_read", "cold_reader") and item["partition"] == "current_plan":
            errors.append(f"{where}: a {role} package must not include current_plan (author plans)")
        if text.lstrip().startswith("{"):
            try:
                packed_docs.append((where, json.loads(text)))
            except ValueError:
                pass
        items.append({"ref": clean, "partition": item["partition"], "required": item["required"], "usage": usage,
                      "chars": len(text), "sha256": _sha(text.encode("utf-8")), "reason": item["reason"]})
        item_labels.append(where)

    errors.extend(_role_rules(root, role, task_doc, items, item_labels, packed_docs))
    samples, view = None, None
    if exemplars or contrast_pairs:
        if role not in SAMPLE_ROLES or (role == "author" and task_doc.get("layer") != "C5b"):
            raise ValueError("--exemplars/--contrast-pairs pack samples for C5a (dialogue_designer) or C5b (author with task.layer C5b) only")
        room = budget - sum(i["chars"] for i in items)
        has_plan = any(record_kind(doc) == "dialogue-plan" for _, doc in packed_docs)
        if annotations_only:
            # wording rulings #11: C5a picks its samples before the dialogue plan exists, from labelled exchanges
            if role != "dialogue_designer" or not exemplars or contrast_pairs or has_plan:
                raise ValueError("--annotations-only is for a C5a (dialogue_designer) package with --exemplars, no --contrast-pairs "
                                 "and no dialogue plan in the selection")
            samples = _pack_annotations(root, exemplars, studio, room, items, item_labels, omitted, omitted_labels)
        elif role == "dialogue_designer" and not has_plan:
            raise ValueError("a C5a package without a dialogue plan packs samples with --annotations-only (the annotation fields of "
                             "labelled exchanges); with a dialogue plan, --exemplars packs the positives it cites")
        else:
            samples = _pack_samples(root, packed_docs, exemplars, contrast_pairs, room,
                                    items, item_labels, omitted, omitted_labels, quotes_per_topic, studio)
        view = samples.pop("_view", None)
        history = _history(root)
        samples["repeatedFromPreviousEpisode"] = _repeats(history, samples)
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
    if samples is not None:
        result["samples"] = samples
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
        if view:  # the annotation view the snapshot's sample ranges point into; content-addressed, never overwritten
            view[0].parent.mkdir(parents=True, exist_ok=True)
            _inside(view[0].parent, root, ANNOTATIONS)
            _publish(view[0], view[1])
        written = [path.name for path, content in ((target, body), (sidecar, sidecar_body)) if _publish(path, content)]
        result.update(written=target.name in written, existing=target.name not in written, written_files=written)
        if samples is not None and samples["keys"]:
            _record_history(root, history, snapshot_id, task_doc["taskId"], samples)
            result["historyPath"] = str(root / HISTORY)
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


def _role_rules(root: Path, role: str, task_doc: dict, items: list, labels: list, docs: list) -> list[str]:
    """Package rules of the D6 roles that need more than one item to judge (implementation plan §2.2 #13)."""
    errors = []
    if role == "cold_reader":
        facts = [label for label, item in zip(labels, items) if item["partition"] == "project_facts"]
        if len(facts) != 1:
            errors.append(f"cold_reader: the package takes exactly one project_facts item (this episode's text or its plan events), found {len(facts)}: {facts}")
        errors += [f"{label}: a cold_reader package takes no {item['partition']}" for label, item in zip(labels, items)
                   if item["partition"] == "knowledge"]
        # D6-2 §5 #9: of an episode plan, the cold reader gets the plan-events export only, never the whole plan
        errors += [f"{where}: a cold_reader package takes the plan's events export (drama_tools.py plan-events), not the whole "
                   "episode plan with its moves, infoLedger and saysFact" for where, doc in docs
                   if record_kind(doc) == "episode-plan" or (isinstance(doc, dict) and record_kind(doc) != "episode-plan-events"
                                                               and ("infoLedger" in doc or "moves" in doc))]
    if role == "dialogue_designer":
        plans = [(where, doc) for where, doc in docs if record_kind(doc) == "episode-plan"]
        if not plans:
            errors.append("dialogue_designer (C5a): the package holds no episode-plan, so its capacity cannot be checked")
        queues = [d for _, d in layer_records(root).get("decision-queue", [])] + [d for _, d in docs if record_kind(d) == "decision-queue"]
        decisions = {entry.get("id"): entry for doc in queues for entry in doc.get("entries", []) if isinstance(entry, dict)}  # packed wins
        for where, plan in plans:
            status = (plan.get("capacity") or {}).get("status") if isinstance(plan.get("capacity"), dict) else None
            if isinstance(status, str) and status.startswith("proposal:"):
                proposal = decisions.get(status.split(":", 1)[1])
                if proposal is None:
                    errors.append(f"{where}: capacity.status {status} names a proposal that no decision queue (packed or under planning/) holds")
                elif not proposal.get("default"):
                    errors.append(f"{where}: capacity.status {status} names a proposal without a default; C5a packs only a plan the flow can follow")
            elif status != "fits":
                errors.append(f"{where}: capacity.status is {status!r}; C5a packs a plan that fits or names a proposal:<id> with a default")
    if role == "author" and "C4" in (task_doc["workstation"], task_doc.get("layer")) and outline_project(root):
        kinds = {record_kind(doc) for _, doc in docs}
        # the C4 package checklist (c4-episode-outline.md, D6-2 §5 #10), the same one season-check outline-structure reads
        for kind, what, rule in (("season-plan", "season plan (planning/season-plan.json)", "outline-season-assigned"),
                                 ("ledger-entry", "ledger (planning/ledger/ledger-ep000.json or a replayed revision)", "outline-ledger-delta"),
                                 ("function-map", "function map (planning/function-map.json)", "outline-structure")):
            if kind not in kinds:
                errors.append(f"C4 author: the package holds no {what}; an episode plan is written from the season plan, the ledger "
                              f"and the function map (season-check {rule}); this project uses the outline layer")
    if task_doc.get("layer") == "C5b":
        plans = [(where, doc) for where, doc in docs if record_kind(doc) == "dialogue-plan"]
        if not plans:
            errors.append("C5b: the package holds no dialogue-plan; C5b writes from a dialogue plan that passes contract-check")
        for where, plan in plans:
            problems = check_contract("dialogue-plan", plan)
            if problems:
                errors.append(f"{where}: the dialogue plan fails contract-check dialogue-plan: " + "; ".join(problems[:5]))
    return errors


def _sample_file(root: Path, path: str, what: str, studio: Path | None = None) -> tuple[str, bytes, dict, dict, bool]:
    """A JSONL sample file inside the project, or (--exemplars only) inside the studio corpus folder: (id, bytes,
    key -> (start, end) of its line, key -> row, whether it is studio-level). Paths are resolved first, so `..` and a
    symlink that points out of the folder are judged by where they land."""
    resolved = Path(path).expanduser().absolute().resolve()
    in_project = resolved.is_relative_to(root.resolve()) and resolved.relative_to(root.resolve()).parts[0] in SAMPLE_ROOTS
    in_studio = studio is not None and what == "--exemplars" and resolved.is_relative_to(studio) and not in_project
    if not (in_project or in_studio):
        where = f"{', '.join(f'{f}/' for f in SAMPLE_ROOTS)} of the project"
        if studio is not None:
            where += " (--exemplars may also be in --studio-corpus; contrast pairs stay project-level)"
        raise ValueError(f"{what} must be a file inside {where}: {path}")
    ident = f"studio-corpus/{resolved.relative_to(studio).as_posix()}" if in_studio else resolved.relative_to(root.resolve()).as_posix()
    data = resolved.read_bytes()
    plan = _plan_exemplars(data.decode("utf-8"))
    if plan is not None:
        if in_studio:
            raise ValueError(f"{what}: a dialogue plan is a project record and is not read from the studio corpus: {path}")
        return (ident, data, *plan, False)
    spans, rows, offset = {}, {}, 0
    for line in data.decode("utf-8").splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if body.strip():
            try:
                row = json.loads(body)
            except ValueError as error:
                raise ValueError(f"{what} line at char {offset} is not JSON: {error}") from error
            key = row.get("exchangeId") or row.get("pairId") if isinstance(row, dict) else None
            if key:
                spans.setdefault(key, (offset, offset + len(body)))
                rows.setdefault(key, row)
        offset += len(line)
    return ident, data, spans, rows, in_studio


def _plan_exemplars(text: str):
    """When --exemplars is a dialogue plan (D6-3 ruling): (ref -> (start, end) of its exemplars.positives object in the
    file, ref -> that object), so each sample is packed as that object's own character range; None for a JSONL file."""
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    if record_kind(doc) != "dialogue-plan":
        return None
    wanted = {p.get("ref") for scene in doc.get("scenes") or [] for topic in scene.get("topics") or [] if isinstance(topic, dict)
              for p in ((topic.get("exemplars") or {}).get("positives") or []) if isinstance(p, dict)}
    spans, rows, stack, in_string, escaped = {}, {}, [], False, False
    for index, char in enumerate(text):  # every JSON object's span, strings respected
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append(index)
        elif char == "}" and stack:
            start = stack.pop()
            try:
                obj = json.loads(text[start:index + 1])
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("ref") in wanted and "source" in obj:
                spans.setdefault(obj["ref"], (start, index + 1))
                rows.setdefault(obj["ref"], obj)
    return spans, rows


def _masked_problem(row: dict) -> str | None:
    """A sample goes into a package as a masked sample record (situation, note, skeleton, maskedLines), never as a raw
    transcript: a row with `lines` or without a maskedLines list is refused (D6-3, plan §8 #2)."""
    masked_only = "; the samples partition takes masked sample records (situation, walkthrough, skeleton, maskedLines) only"
    if "lines" in row:
        return "是原始转写（带 lines）" + masked_only
    if "pairId" in row and not (row.get("provenance") or row.get("fromNotes")):
        return "没有来源（provenance 或 fromNotes）；无来源的条目不进包"  # D6-4
    if not isinstance(row.get("maskedLines"), list) and "pairId" not in row:
        return "没有 maskedLines（遮蔽后的原句）" + masked_only
    return None


def _pack_annotations(root, exemplars, studio, room, items, labels, omitted, omitted_labels) -> dict:
    """C5a without a dialogue plan (wording rulings #11): the labelled exchanges of --exemplars (annotated, through
    corpus filter) go in as their annotation fields only -- situation, walkthrough, skeleton, about and ids. Raw lines,
    masked lines and every other field are stripped, so no original line reaches the package. The stripped rows are a
    view written to .drama/packs/annotations/<sha>.jsonl (with the snapshot, never overwritten) that the sample ranges
    point into. Rows labelled low and rows with no situation are left out and counted. In file order, whole rows,
    while the budget lasts."""
    ident, data, spans, rows, in_studio = _sample_file(root, exemplars, "--exemplars", studio)
    if not rows:
        raise ValueError("--exemplars for C5a without a dialogue plan is a JSONL of labelled exchanges; this file has none")
    kept, low, unlabelled = [], [], []
    for key in sorted(rows, key=lambda k: spans[k][0]):
        row = rows[key]
        problem = studio_row_problem(row) if in_studio else None
        if problem:
            raise ValueError(f"sample {key} {problem}")
        if row.get("labelConfidence") == "low" or (row.get("quality") or {}).get("label") == "low":
            low.append(key)
        elif not isinstance(row.get("situation"), dict):
            unlabelled.append(key)
        else:
            kept.append({field: row[field] for field in ANNOTATION_FIELDS if field in row})
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in kept]
    body = ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
    path = root / ANNOTATIONS / f"{_sha(body).split(':')[1][:16]}.jsonl"
    view_id = path.relative_to(root).as_posix()
    packed, left, keys, offset = 0, 0, [], 0
    for row, line in zip(kept, lines):
        start, end = offset, offset + len(line)
        offset = end + 1
        ref = {"kind": "local_file", "id": view_id, "revision": _sha(body), "sha256": _sha(body), "range": {"start": start, "end": end}}
        label = f"sample 标注 {row['exchangeId']}"
        if len(line) <= room:
            room -= len(line)
            packed += 1
            keys.append({"kind": "annotation", "key": row["exchangeId"], "topicId": None})
            items.append({"ref": ref, "partition": "samples", "required": False, "usage": "creative_reference", "chars": len(line),
                          "sha256": _sha(line.encode("utf-8")),
                          "reason": f"样本标注：交换 {row['exchangeId']} 的处境、结构说明、骨架（取自 {ident}@{_sha(data)}，已剥掉原始台词行）"})
            labels.append(label)
        else:
            left += 1
            omitted.append({"ref": ref, "required": False, "reason": "budget"})
            omitted_labels.append(label)
    return {"packed": packed, "mode": "annotations_only", "fromStudioCorpus": in_studio, "source": ident, "sourceSha256": _sha(data),
            "view": view_id, "fields": list(ANNOTATION_FIELDS), "leftOutLowLabel": low, "leftOutUnlabelled": unlabelled,
            "omittedForBudget": left, "omittedForQuoteCap": 0, "unresolved": [], "episode": None, "keys": keys,
            "_view": (path, body),
            "policy": "C5a 还没有对话表：只装标注交换的标注字段（处境、结构说明、骨架），不装原始台词行与遮蔽句；"
                      "低一致的与没有处境的不装；C5a 选定后把遮蔽句写进对话表 exemplars.positives，C5b 再从对话表装"}


def _pack_samples(root, docs, exemplars, contrast_pairs, room, items, labels, omitted, omitted_labels,
                  quotes_per_topic=QUOTES_PER_TOPIC, studio=None) -> dict:
    """Two corpus positives and one contrast pair per topic of the packed dialogue plan(s), as masked sample records
    (situation, walkthrough, skeleton, maskedLines; a raw transcript row is refused), into the samples partition in priority
    order while the budget lasts. A topic's samples carry at most quotes_per_topic masked lines in all (default 2, 0 for
    none): a sample that would pass that is left out whole (reason quote_cap), so is one that does not fit the budget.
    Nothing is cut inside a sample."""
    plans = [doc for _, doc in docs if record_kind(doc) == "dialogue-plan"]
    if not plans:
        raise ValueError("samples follow the topics of a packed dialogue plan; the selection holds none")
    files = {"positive": _sample_file(root, exemplars, "--exemplars", studio) if exemplars else None,
             "contrast": _sample_file(root, contrast_pairs, "--contrast-pairs", studio) if contrast_pairs else None}
    tiers, seen, unresolved = ([], [], []), set(), []
    for plan in plans:
        for scene in plan.get("scenes") or []:
            for topic in scene.get("topics") or [] if isinstance(scene, dict) else []:
                shown = (topic.get("exemplars") or {}) if isinstance(topic, dict) else {}
                refs = [("positive", p.get("ref")) for p in shown.get("positives") or [] if isinstance(p, dict) and p.get("source") == "corpus"]
                refs += [("contrast", c.get("pairId")) for c in shown.get("contrast") or [] if isinstance(c, dict)]
                taken = {"positive": 0, "contrast": 0}
                for kind, ref in refs:
                    file = files[kind]
                    if file is None or not isinstance(ref, str) or taken[kind] >= (2 if kind == "positive" else 1):
                        continue
                    key = next((k for k in (ref, ref.split("#")[-1]) if k in file[2]), None)
                    if key is None:
                        unresolved.append(f"{topic.get('topicId')}:{ref}")
                        continue
                    problem = _masked_problem(file[3][key]) or (studio_row_problem(file[3][key]) if file[4] else None)
                    if problem:
                        raise ValueError(f"sample {key} (topic {topic.get('topicId')}) {problem}")
                    taken[kind] += 1
                    if (kind, key) in seen:
                        continue
                    seen.add((kind, key))
                    tier = 1 if kind == "contrast" else (0 if taken[kind] == 1 else 2)
                    tiers[tier].append((topic.get("topicId"), kind, key, file))
    packed, left, capped, keys, quotes = 0, 0, 0, [], {}
    for topic, kind, key, (ident, data, spans, rows, _) in [entry for tier in tiers for entry in tier]:
        start, end = spans[key]
        text = data.decode("utf-8")[start:end]
        ref = {"kind": "local_file", "id": ident, "revision": _sha(data), "sha256": _sha(data), "range": {"start": start, "end": end}}
        label = f"sample {topic} {'正例' if kind == 'positive' else '对照对'} {key}"
        masked = len(rows[key].get("maskedLines") or [])
        if quotes.get(topic, 0) + masked > quotes_per_topic:  # whole sample out: its masked lines would pass the topic's cap
            capped += 1
            omitted.append({"ref": ref, "required": False, "reason": "quote_cap"})
            omitted_labels.append(label)
            continue
        if len(text) <= room:
            quotes[topic] = quotes.get(topic, 0) + masked
            room -= len(text)
            packed += 1
            keys.append({"kind": kind, "key": key, "topicId": topic})
            items.append({"ref": ref, "partition": "samples", "required": False, "usage": "creative_reference",
                          "chars": len(text), "sha256": _sha(text.encode("utf-8")),
                          "reason": f"样本：话题 {topic} 的{'正例' if kind == 'positive' else '对照对'} {key}（对话表引用）"})
            labels.append(label)
        else:
            left += 1
            omitted.append({"ref": ref, "required": False, "reason": "budget"})
            omitted_labels.append(label)
    episodes = [plan.get("episode") for plan in plans if plan.get("episode") is not None]
    return {"packed": packed, "fromStudioCorpus": bool(files["positive"] and files["positive"][4]), "omittedForBudget": left, "omittedForQuoteCap": capped, "unresolved": unresolved,
            "quotesPerTopic": quotes_per_topic, "maskedLinesPerTopic": quotes,
            "episode": episodes[0] if episodes else None, "keys": keys,
            "policy": f"每话题至多 2 个语料正例＋1 个对照对，样本须是遮蔽后的样本记录；一个话题所有样本的 maskedLines 合计不超过 "
                      f"{quotes_per_topic} 句，超出的样本整条不装（reason: quote_cap）；先各话题第一正例、再对照对、再第二正例，"
                      "装到预算为止；不截断单条样本"}


def _episode_number(value):
    match = re.match(r"^(?:ep|episode)?[-_]?0*(\d{1,4})", str(value).strip().lower()) if value is not None else None
    return int(match.group(1)) if match else None


def _history(root: Path) -> list:
    path = root / HISTORY
    if not path.is_file():
        return []
    doc = _load_json(_inside(path, root, HISTORY), "pack history")
    return doc.get("packs", []) if isinstance(doc, dict) and isinstance(doc.get("packs"), list) else []


def _repeats(packs: list, samples: dict) -> list:
    """Samples of this package that the package of the episode just before also held (D6-3: no sample two episodes
    running). Episodes are compared by number; 6A and 6B count as consecutive."""
    n, label = _episode_number(samples["episode"]), str(samples["episode"])
    if n is None:
        return []
    before = [p for p in packs if isinstance(p, dict) and str(p.get("episode")) != label
              and _episode_number(p.get("episode")) in (n - 1, n)]
    mine = {(k["kind"], k["key"]) for k in samples["keys"]}
    return sorted({f"{p.get('episode')}:{k['kind']}:{k['key']}" for p in before for k in p.get("samples") or []
                   if isinstance(k, dict) and (k.get("kind"), k.get("key")) in mine})


def _record_history(root: Path, packs: list, snapshot_id: str, task_id: str, samples: dict) -> None:
    """Append this package's samples to .drama/packs/history.json (one entry per snapshot; never rewrites one)."""
    if any(isinstance(p, dict) and p.get("snapshotId") == snapshot_id for p in packs):
        return
    folder = root / ".drama" / "packs"
    folder.mkdir(parents=True, exist_ok=True)
    _inside(folder, root, ".drama/packs")
    entry = {"snapshotId": snapshot_id, "taskId": task_id, "episode": samples["episode"],
             "samples": [{"kind": k["kind"], "key": k["key"], "topicId": k["topicId"]} for k in samples["keys"]]}
    body = json.dumps({"schemaVersion": "drama-studio/pack-history/v0", "packs": [*packs, entry]}, ensure_ascii=False, indent=2) + "\n"
    temp = folder / f".history.{os.getpid()}.tmp"
    temp.write_text(body, encoding="utf-8")
    os.replace(temp, folder / "history.json")
