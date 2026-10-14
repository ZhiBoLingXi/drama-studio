"""Ledger (底账) tools: init, merge, apply, replay, check, diff, knows, view, stats.

The ledger holds six kinds of entries (timeline, money, object, knowledge, procedure, agenda) on
two tracks: `planned` (episode plans' `ledgerDelta`) and `actual` (what a draft really wrote).
`ledger@ep000` is the prehistory; every later revision is ep000 plus deltas applied in episode
order. Field names follow the D6-0 pilot ledgers; extra registration fields (`whyMissing`,
`emptyFields[]`, `conflictsWith[]`, `currentClaim`, `notFound`, ...) are allowed and only read by
the rules that use them.

Timeline entries may carry `subtype: "state"` for legal, bodily or relationship states with a
duration (d6-1 decision #1): `stateOf`, `state`, `validFrom`, `validTo` instead of did/didNot/why.

Passing `check` proves only that the rules below hold on the given files. It says nothing about
whether the world the ledger describes is plausible, whether a card's rule is right, or whether
any human approved an entry. Read-only except `init`, `merge`, `apply` and `replay --out`, which
write only the named output. Never goes online or calls a model.

Exit codes: 0 completed (and, for check, no blocking rule failed); 1 input error; 2 a blocking
rule failed (`check`) or a write could not be applied (`apply`, `replay`).
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import shlex
import sys

KIND_FIELDS = {
    "timeline": ["when", "who", "where", "did", "didNot", "why", "knownTo"],
    "money": ["amount", "from", "to", "account", "whoCanMove", "trace", "procedureRef"],
    "object": ["object", "holder", "location", "howItGotThere", "state", "visibleTo"],
    "knowledge": ["who", "knows", "since", "how", "notKnows"],
    "procedure": ["name", "realWorldRule", "nextNecessaryMove", "realityRef", "usedIn"],
    "agenda": ["party", "goal", "means", "constraints", "nextMove", "validFrom", "validTo"],
}
STATE_FIELDS = ["stateOf", "state", "validFrom", "validTo", "knownTo"]  # timeline subtype: state
SUBTYPES = {"timeline": {"state"}}
VALID_KINDS = set(KIND_FIELDS)
VALID_ORIGINS = {"user_given", "user_given_modified", "designed", "derived_from_text"}
VALID_STATUSES = {"asserted", "verified", "unverified", "contested", "retired", "license_pending", "accepted_license"}
VALID_TRACKS = ("planned", "actual")
RETIRE_EVENTS = {"deceived", "forgot", "corrected"}
RETIRED_BY_VOCAB = {"layer_choice"}
# A scene write only counts as "this scene touched the entry's timing" when it changes one of these.
TIMING_FIELDS = {"since", "knownTo", "knownToSince", "visibleTo", "visibleToSince"}
ROLE_BY_TRACK = {"planned": "C4", "actual": "C5-actual"}
BLOCKING_RULES_PRESELECT = {"schema-basic", "refs-exist"}
SCHEMA = "drama-studio/ledger-entry/v0"


class InputError(ValueError):
    """An input file is missing, unreadable or not the expected shape (exit code 1)."""


# ---------------------------------------------------------------------------
# Shared helpers (also used by plan_check, season_plan_check, capacity, decision, function_map)
# ---------------------------------------------------------------------------
def load_json(path, label):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise InputError(f"找不到{label}：{path}") from None
    except json.JSONDecodeError as e:
        raise InputError(f"{label}不是合法 JSON：{path}（{e}）") from None


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_nonempty(value):
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    if isinstance(value, dict):
        return len(value) > 0 and any(is_nonempty(v) for v in value.values())
    if isinstance(value, list):
        return len(value) > 0 and all(is_nonempty(v) for v in value)
    return True


EP_TOKEN_RE = re.compile(r"^\s*(?:ep)?0*(\d+)([A-Za-z]*)", re.IGNORECASE)


def ep_key(token):
    """Comparable key for an episode id: 5, "5", "ep005", "6A", "ep6A 6A-1.b1", "6A-1.b4" -> (6, "A").

    "pre" sorts before every episode. Returns None when no episode can be read (never guesses).
    Integer and "number+letter" ids mixed in one run (5 next to "6A") compare without TypeError —
    the D6-0 multi-delta crash came from comparing them raw."""
    if token is None or isinstance(token, bool):
        return None
    if isinstance(token, (int, float)):
        return (int(token), "")
    text = str(token).strip()
    if text.lower() == "pre":
        return (-1, "")
    m = EP_TOKEN_RE.match(text)
    return (int(m.group(1)), m.group(2).upper()) if m else None


def ep_label(key):
    if key is None:
        return None
    return "pre" if key[0] < 0 else f"{key[0]}{key[1]}"


def reproduce_command(script, argv):
    """A runnable command line: file arguments resolved to absolute paths."""
    tokens = []
    for arg in argv:
        if not arg.startswith("-") and os.path.exists(arg):
            tokens.append(os.path.abspath(arg))
        else:
            tokens.append(arg)
    return shlex.join(["python3", "-B", os.path.abspath(script)] + tokens)


def emit(result):
    print(json.dumps(result, ensure_ascii=False, indent=2))


def schema_head(doc):
    """Keep the input's schema marker (schemaVersion, or the pilot files' schema); default to ours."""
    head = {k: doc[k] for k in ("schemaVersion", "schema") if isinstance(doc, dict) and k in doc}
    return head or {"schemaVersion": SCHEMA}


def merge_decision_docs(docs):
    """Several decision-queue files read as one: {"entries": [...]} in the given order."""
    entries = []
    for doc in docs or []:
        entries.extend((doc or {}).get("entries", []) or [])
    return {"entries": entries} if docs else None


# Beat references: "6A-1.b4" or "ep6A 6A-1.b1" / "ep006A 6A-1.b1" (both prefixes occur in real data).
BEAT_REF_RE = re.compile(r"([0-9A-Za-z]+(?:-[0-9A-Za-z]+)?)\.b(\d+)")
# Only the beat at the start of a value counts ("ep6A 6A-1.b1 ...", "6A-1.b4（注）"); a beat id
# mentioned inside a note, e.g. "pre（去年登记；本集 6B-1.b1 翻出）", is never read as the timing.
LEADING_BEAT_RE = re.compile(r"^\s*(?:ep0*\d+[A-Za-z]*\s*)?([0-9A-Za-z]+(?:-[0-9A-Za-z]+)?)\.b(\d+)", re.IGNORECASE)
PRE_RE = re.compile(r"^\s*pre(?:$|[\s（(；;，,、:：])", re.IGNORECASE)


def parse_beat_ref(text):
    """(sceneId, beatNum) of the beat a value starts with (after an optional "ep6A"/"ep006A" prefix);
    (None, None) for "pre..." (before this episode) or when the value does not start with a beat."""
    text = str(text or "")
    if PRE_RE.match(text):
        return None, None
    m = LEADING_BEAT_RE.match(text)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def beat_sort_key(beat_text, scene_order_index):
    """Scene not in this episode plan sorts before every scene of it; unparseable sorts earliest."""
    scene, num = parse_beat_ref(beat_text)
    if scene is None:
        return (-2, 0)
    if scene not in scene_order_index:
        return (-1, 0)
    return (scene_order_index[scene], num)


def since_value_parts(value):
    """A knowledge entry's `since`: a string is one part; a dict {part: beat} is several parts
    learnt at different beats (judged part by part, never by the latest beat). None if neither."""
    if isinstance(value, str):
        return [(None, value)]
    if isinstance(value, dict):
        parts = [(aspect, beat) for aspect, beat in value.items() if isinstance(beat, str)]
        return parts or None
    return None


def person_since_parts(value, person):
    """knownToSince / visibleToSince for one person: {person: beat} or {person: {part: beat}}."""
    if not isinstance(value, dict):
        return None
    return since_value_parts(value.get(person))


# ---------------------------------------------------------------------------
# Load and index
# ---------------------------------------------------------------------------
def index_entries(entries):
    by_id, dups = {}, []
    for e in entries:
        eid = e.get("id") if isinstance(e, dict) else None
        if not is_nonempty(eid):
            continue
        if eid in by_id:
            dups.append(eid)
            continue
        by_id[eid] = copy.deepcopy(e)
    return by_id, dups


def load_ledger(path):
    """(doc, entries_by_id, duplicate_ids)."""
    doc = load_json(path, "底账文件")
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        raise InputError(f"底账文件缺 entries 数组：{path}")
    by_id, dups = index_entries(entries)
    return doc, by_id, dups


def check_delta_doc(doc, path):
    if not isinstance(doc, dict):
        raise InputError(f"{path} 不是 ledger-delta 对象")
    for key in ("episode", "track", "writes"):
        if key not in doc:
            raise InputError(f"{path} 缺顶层字段 {key!r}")
    if doc["track"] not in VALID_TRACKS:
        raise InputError(f"{path} track={doc['track']!r} 不是 planned/actual")
    if not isinstance(doc["writes"], list):
        raise InputError(f"{path} writes 不是数组")
    return doc


def load_delta(path):
    return check_delta_doc(load_json(path, "ledger-delta 文件"), path)


def iter_candidates(function_map_doc):
    for thread in (function_map_doc or {}).get("threads", []) or []:
        for fn in thread.get("functions", []) or []:
            for cand in fn.get("candidates", []) or []:
                yield thread, fn, cand


def collect_selected_entry_ids(function_map_doc):
    """entryId of every ledgerDeps item of a selected candidate (deps not yet in the ledger skipped)."""
    return {dep["entryId"] for _, _, cand in iter_candidates(function_map_doc) if cand.get("status") == "selected"
            for dep in cand.get("ledgerDeps", []) or [] if is_nonempty(dep.get("entryId"))}


def collect_function_ids(function_map_doc):
    return {fn["functionId"] for thread in (function_map_doc or {}).get("threads", []) or []
            for fn in thread.get("functions", []) or [] if is_nonempty(fn.get("functionId"))}


def build_card_index(cards_dir):
    """Card ids matchable by realityRef: filename stem before "@", plus `cardId`/`id`/`knowledgeId`.
    A realityRef may point into a card ("K1-x#3"); the part after "#" is ignored when matching."""
    ids = set()
    if not cards_dir or not os.path.isdir(cards_dir):
        return ids
    for path in sorted(glob.glob(os.path.join(cards_dir, "*.json"))):
        ids.add(os.path.splitext(os.path.basename(path))[0].split("@")[0])
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("cardId", "id", "knowledgeId"):
            if isinstance(doc, dict) and is_nonempty(doc.get(key)):
                ids.add(doc[key])
    return ids


# ---------------------------------------------------------------------------
# Applying deltas
# ---------------------------------------------------------------------------
def write_target_id(write):
    change = write.get("change") or {}
    return change.get("id") if write.get("entryId") == "new" else write.get("entryId")


def apply_write(entries_by_id, write, episode, track, errors=None, where=""):
    """Apply one write in place. Structural problems are recorded in `errors` (when given) instead
    of raising, so apply can report everything it could not apply."""
    entry_id = write.get("entryId")
    change = write.get("change") or {}
    rev = f"ep{episode}.{track}" if episode is not None else track
    record = {"rev": rev, "change": change, "by": ROLE_BY_TRACK.get(track, "feedback"), "when": rev, "reason": write.get("reason")}
    if entry_id == "new":
        new_id = change.get("id")
        if not is_nonempty(new_id):
            if errors is not None:
                errors.append(f"{where}: new 写缺 change.id")
            return None
        if new_id in entries_by_id:
            if errors is not None:
                errors.append(f"{where}: new 写的 id {new_id!r} 与既有条目冲突")
            return None
        new_entry = copy.deepcopy(change)
        new_entry.setdefault("history", []).append(record)
        new_entry.setdefault("patchCount", 0)
        entries_by_id[new_id] = new_entry
        return new_id
    if entry_id not in entries_by_id:
        if errors is not None:
            errors.append(f"{where}: writes 引用的 id {entry_id!r} 不存在")
        return None
    entry = entries_by_id[entry_id]
    for k, v in change.items():
        if k != "id":
            entry[k] = copy.deepcopy(v)
    entry.setdefault("history", []).append(record)
    return entry_id


def apply_delta(entries_by_id, delta, errors=None):
    episode, track = delta.get("episode"), delta.get("track")
    touched = []
    for i, w in enumerate(delta.get("writes", []) or []):
        tid = apply_write(entries_by_id, w, episode, track, errors=errors, where=f"ep{episode}.{track}/writes[{i}]")
        if tid is not None:
            touched.append(tid)
    return touched


def episode_order_key(season_doc=None):
    """Sort key for episode ids: the season plan's finalSequence order when given, else natural order
    (5 < 6A < 6B < 7). Ids missing from finalSequence fall back to natural order after the listed ones."""
    order = {}
    for item in (season_doc or {}).get("finalSequence", []) or []:
        if item.get("id") is not None and isinstance(item.get("newEpisodeNo"), (int, float)):
            order[str(item.get("id"))] = item["newEpisodeNo"]

    def key(episode):
        natural = ep_key(episode) or (10 ** 9, str(episode))
        if str(episode) in order:
            return (0, order[str(episode)], natural)
        return (1, natural[0], natural)
    return key


# ---------------------------------------------------------------------------
# Rules (outline-layer design §10.2 plus the D6-0 additions). Each returns
# {"status": "pass|fail|report", "items": [...]}; main() decides what blocks by --stage.
# ---------------------------------------------------------------------------
def _justified(e, empty_fields, f):
    """A null field is deliberate when emptyFields names it or whyMissing/whyNotApplicable is set."""
    return f in empty_fields or bool(e.get("whyMissing")) or bool(e.get("whyNotApplicable"))


def required_fields(entry):
    if entry.get("kind") == "timeline" and entry.get("subtype") == "state":
        return STATE_FIELDS
    return KIND_FIELDS.get(entry.get("kind"), [])


def entry_problems(eid, e):
    """schema-basic for one entry. Calibrated on the D6-0 pilot ledgers: timeline needs did or didNot
    (where may be null; why needs whyMissing/whyNotApplicable/whyPartial); procedure realWorldRule
    may be null only when unverified with notFound; money's six fields accept only emptyFields;
    a knowledge entry that records only notKnows exempts knows and how."""
    items = []
    kind = e.get("kind")
    if kind not in VALID_KINDS:
        items.append({"id": eid, "problem": f"kind={kind!r} 不合法"})
    if e.get("origin") not in VALID_ORIGINS:
        items.append({"id": eid, "problem": f"origin={e.get('origin')!r} 不合法"})
    if e.get("status") not in VALID_STATUSES:
        items.append({"id": eid, "problem": f"status={e.get('status')!r} 不合法"})
    if kind not in KIND_FIELDS:
        return items
    subtype = e.get("subtype")
    if subtype is not None and subtype not in SUBTYPES.get(kind, set()):
        items.append({"id": eid, "problem": f"{kind} 的 subtype={subtype!r} 不合法"})
        return items
    empty_fields = set(e.get("emptyFields") or [])
    for f in required_fields(e):
        if f not in e:
            items.append({"id": eid, "problem": f"缺专有字段 {f}"})

    def null_unjustified(fields):
        for f in fields:
            if f in e and e[f] is None and not _justified(e, empty_fields, f):
                items.append({"id": eid, "problem": f"专有字段 {f} 为 null，且无 emptyFields/whyMissing/whyNotApplicable 登记"})

    if kind == "timeline" and subtype == "state":
        for f in ("stateOf", "state"):
            if f in e and not is_nonempty(e[f]):
                items.append({"id": eid, "problem": f"状态条目的 {f} 为空"})
        null_unjustified(["validFrom", "knownTo"])  # validTo null means the state still holds
    elif kind == "timeline":
        unstated = e.get("unstated") is True and e.get("whyMissing")
        if not is_nonempty(e.get("did")) and not is_nonempty(e.get("didNot")) and not unstated:
            items.append({"id": eid, "problem": "did 与 didNot 都为空，至少要有一个非空"})
        if e.get("why") is None and not (e.get("whyMissing") or e.get("whyNotApplicable") or e.get("whyPartial")):
            items.append({"id": eid, "problem": "专有字段 why 为 null，且 whyMissing/whyNotApplicable/whyPartial 都不为真"})
        null_unjustified(["when", "who", "knownTo"])
    elif kind == "procedure":
        if e.get("realWorldRule") is None and not (e.get("status") == "unverified" and is_nonempty(e.get("notFound"))):
            items.append({"id": eid, "problem": "专有字段 realWorldRule 为 null，且不是 status=unverified 带非空 notFound"})
        null_unjustified(["name", "realityRef", "usedIn"])
    elif kind == "money":
        for f in ("amount", "from", "to", "account", "whoCanMove", "trace"):
            if f in e and e[f] is None and f not in empty_fields:
                items.append({"id": eid, "problem": f"专有字段 {f} 为 null，且不在 emptyFields 里（money 只认 emptyFields）"})
    elif kind == "knowledge":
        exempt = {"knows", "how"} if e.get("knows") is None and is_nonempty(e.get("notKnows")) else set()
        violated = [f for f in KIND_FIELDS["knowledge"]
                    if f in e and e[f] is None and f not in exempt and not _justified(e, empty_fields, f)]
        if violated:
            diag = ("whyMissing", "whyNotApplicable", "whyPartial", "isFalseBelief", "currentClaim", "inferred", "notFound", "emptyFields")
            items.append({"id": eid, "problem": f"专有字段 {violated} 为 null，且无 emptyFields/whyMissing/whyNotApplicable 登记",
                          "entryFields": {f: e.get(f) for f in KIND_FIELDS["knowledge"]},
                          "entryFlags": {k: e.get(k) for k in diag if k in e}})
    else:
        null_unjustified(KIND_FIELDS[kind])
    return items


def rule_schema_basic(entries_by_id, duplicate_ids=()):
    items = [{"id": eid, "problem": "id 重复"} for eid in duplicate_ids]
    for eid, e in entries_by_id.items():
        items.extend(entry_problems(eid, e))
    return {"status": "fail" if items else "pass", "items": items}


def rule_delta_applies(entries_by_id, deltas):
    items = []
    working = copy.deepcopy(entries_by_id)
    for delta in deltas:
        episode, track = delta.get("episode"), delta.get("track")
        for i, w in enumerate(delta.get("writes", []) or []):
            where = f"ep{episode}.{track}/writes[{i}]"
            change = w.get("change") or {}
            if w.get("entryId") == "new":
                if not is_nonempty(change.get("id")):
                    items.append(f"{where}: new 写缺 change.id")
                    continue
                if change.get("id") in working:
                    items.append(f"{where}: new 写的 id {change['id']!r} 与既有条目冲突")
                kind = change.get("kind")
                if kind not in VALID_KINDS:
                    items.append(f"{where}: new 写 kind={kind!r} 不合法或缺失")
                else:
                    for f in required_fields(change):
                        if f not in change:
                            items.append(f"{where}: new 写缺专有字段 {f}")
                for f in ("title", "origin", "status", "introducedAt"):
                    if not is_nonempty(change.get(f)):
                        items.append(f"{where}: new 写缺公共字段 {f}")
            elif w.get("entryId") not in working:
                items.append(f"{where}: writes 引用的 id {w.get('entryId')!r} 不存在")
            apply_write(working, w, episode, track)
    return {"status": "fail" if items else "pass", "items": items}


def rule_object_single_chain(entries_by_id, deltas, stage="default"):
    """After all deltas: one live (non-retired) entry per object; every holder/location change has a
    supportedBy. A group whose entries are all contested and pairwise conflictsWith each other is a
    registered disagreement: reported under pre-select, still blocking afterwards."""
    blocking, exempt = [], []
    working = copy.deepcopy(entries_by_id)
    for delta in deltas:
        episode, track = delta.get("episode"), delta.get("track")
        for i, w in enumerate(delta.get("writes", []) or []):
            change = w.get("change") or {}
            existing = working.get(w.get("entryId")) if w.get("entryId") != "new" else None
            is_object = (existing and existing.get("kind") == "object") or (w.get("entryId") == "new" and change.get("kind") == "object")
            if is_object and ("holder" in change or "location" in change) and not is_nonempty(w.get("supportedBy")):
                blocking.append(f"ep{episode}.{track}/writes[{i}]: 改 holder/location 但 supportedBy 为空")
        apply_delta(working, delta)
    by_object = {}
    for eid, e in working.items():
        if e.get("kind") == "object" and is_nonempty(e.get("object")) and isinstance(e.get("object"), str):
            by_object.setdefault(e["object"], []).append(eid)

    def registered(ids):
        return all(working[i].get("status") == "contested" for i in ids) and all(
            all(o in set(working[a].get("conflictsWith") or []) for o in ids if o != a) for a in ids)

    for obj, ids in by_object.items():
        active = [i for i in ids if working[i].get("status") != "retired"]
        if len(active) <= 1:
            continue
        msg = f"object={obj!r} 同时有 {len(active)} 个非 retired 条目：{active}"
        if registered(active):
            if stage == "pre-select":
                exempt.append(msg + "（两两互为 conflictsWith 且都 contested，pre-select 下只报）")
            else:
                blocking.append(msg + "（两两互为 conflictsWith 且都 contested，已过 pre-select，仍拦）")
        else:
            blocking.append(msg)
    return {"status": "fail" if blocking else ("report" if exempt else "pass"), "items": blocking + exempt}


def rule_knowledge_monotonic(entries_by_id, deltas):
    items = []
    working = copy.deepcopy(entries_by_id)
    for delta in deltas:
        episode, track = delta.get("episode"), delta.get("track")
        for i, w in enumerate(delta.get("writes", []) or []):
            change = w.get("change") or {}
            existing = working.get(w.get("entryId")) if w.get("entryId") != "new" else None
            if (existing and existing.get("kind") == "knowledge" and existing.get("status") != "retired"
                    and change.get("status") == "retired" and change.get("event") not in RETIRE_EVENTS):
                items.append(f"ep{episode}.{track}/writes[{i}]: 知识条目 {w.get('entryId')} 被 retired，"
                             f"但 change.event={change.get('event')!r} 不在 {sorted(RETIRE_EVENTS)} 里")
        apply_delta(working, delta)
    return {"status": "fail" if items else "pass", "items": items}


def rule_money_closed(entries_by_id, stage="default"):
    """from/to/whoCanMove non-empty; account and trace non-empty or `no_trace` with a reason
    (accountReason/traceReason). A field listed in emptyFields is a registration, not an exemption:
    it is still reported. amount is not checked (a card gives a rule's magnitude, not the sum)."""
    items = []
    for eid, e in entries_by_id.items():
        if e.get("kind") != "money" or e.get("status") == "retired":
            continue
        for f in ("from", "to", "whoCanMove"):
            if not is_nonempty(e.get(f)):
                items.append(f"{eid}: {f} 为空")
        for f, reason in (("account", "accountReason"), ("trace", "traceReason")):
            v = e.get(f)
            if v == "no_trace":
                if not is_nonempty(e.get(reason)):
                    items.append(f"{eid}: {f}=no_trace 但 {reason} 为空")
            elif not is_nonempty(v):
                items.append(f"{eid}: {f} 为空且未标 no_trace")
    if stage == "pre-select":
        return {"status": "report", "items": items}
    return {"status": "fail" if items else "pass", "items": items}


def presence_vs_timeline(entries_by_id, scenes):
    """Episode-plan scenes [{sceneId, time, place, present[]}] against timeline entries: nobody in two
    scenes of the same time; a present person's timeline entry for the same `when` names the same place.
    Literal string comparison of when/time and where/place only. Called by plan_check."""
    items = []
    timeline = [e for e in entries_by_id.values() if e.get("kind") == "timeline" and e.get("subtype") != "state"]
    by_time = {}
    for sc in scenes or []:
        by_time.setdefault(sc.get("time"), []).append(sc)
    for t, scs in by_time.items():
        seen = {}
        for sc in scs:
            for person in sc.get("present") or []:
                if person in seen and seen[person] != sc.get("sceneId"):
                    items.append(f"{person} 同一时段（{t}）同时出现在 {seen[person]} 与 {sc.get('sceneId')}")
                seen[person] = sc.get("sceneId")
    for sc in scenes or []:
        for person in sc.get("present") or []:
            for te in timeline:
                if te.get("who") == person and te.get("where") and sc.get("place") and te.get("when") == sc.get("time") \
                        and te["where"] != sc["place"]:
                    items.append(f"{person} 在场次 {sc.get('sceneId')}（{sc.get('place')}），但时间线账 {te.get('id')} 说同时段在 {te['where']}")
    return items


def rule_planned_vs_actual(deltas):
    by_episode = {}
    for d in deltas:
        by_episode.setdefault(str(d.get("episode")), {})[d.get("track")] = d
    items = []
    sort_key = episode_order_key()
    for ep in sorted(by_episode, key=sort_key):
        tracks = by_episode[ep]
        if "planned" not in tracks or "actual" not in tracks:
            continue
        pw = {write_target_id(w): w.get("change") for w in tracks["planned"].get("writes", []) or []}
        aw = {write_target_id(w): w.get("change") for w in tracks["actual"].get("writes", []) or []}
        diff = {}
        for eid in sorted(set(pw) | set(aw), key=str):
            if eid not in pw:
                diff[eid] = {"onlyIn": "actual", "change": aw[eid]}
            elif eid not in aw:
                diff[eid] = {"onlyIn": "planned", "change": pw[eid]}
            elif pw[eid] != aw[eid]:
                diff[eid] = {"planned": pw[eid], "actual": aw[eid]}
        if diff:
            items.append({"episode": tracks["planned"].get("episode"), "diff": diff})
    return {"status": "report", "items": items}


def rule_unverified_count(entries_by_id):
    return {"status": "report", "items": [{"id": eid, "dependents": e.get("dependents", [])}
                                          for eid, e in entries_by_id.items() if e.get("status") == "unverified"]}


def rule_patch_cap(entries_by_id, deltas):
    """An entry with patchCount >= 2 modified in place (not retired) is refused; patchCount null
    (unknown, e.g. a migrated project) never triggers."""
    items = []
    for delta in deltas:
        episode, track = delta.get("episode"), delta.get("track")
        for i, w in enumerate(delta.get("writes", []) or []):
            entry = entries_by_id.get(w.get("entryId")) if w.get("entryId") != "new" else None
            count = (entry or {}).get("patchCount")
            if isinstance(count, int) and not isinstance(count, bool) and count >= 2 \
                    and (w.get("change") or {}).get("status") != "retired":
                items.append(f"ep{episode}.{track}/writes[{i}]: {w.get('entryId')} patchCount={count} ≥ 2，被原地修改（非 retired）")
    return {"status": "fail" if items else "pass", "items": items}


def _count_by_conflict_kind(entries_by_id, ids):
    by_kind = {}
    for eid in ids:
        notes = entries_by_id[eid].get("conflictNotes") or []
        kinds = {n.get("conflictKind") or "unspecified" for n in notes if isinstance(n, dict)} or {"unspecified"}
        for k in sorted(kinds):
            by_kind.setdefault(k, []).append(eid)
    return by_kind


def rule_contested_zero(entries_by_id, stage, scope_ids=None, decisions_doc=None):
    """Contested entries counted by conflictKind. With a scope, out-of-scope entries are listed only;
    an in-scope entry whose remaining opponents are all out of scope, registered in
    conflictsOutOfScope and pointed at an existing decision (decisionRef), is reported, not blocking."""
    contested = [eid for eid, e in entries_by_id.items() if e.get("status") == "contested"]
    in_scope = contested if scope_ids is None else [eid for eid in contested if eid in scope_ids]
    by_kind = _count_by_conflict_kind(entries_by_id, in_scope)
    items = {"ids": in_scope, "countByConflictKind": {k: len(v) for k, v in by_kind.items()}, "idsByConflictKind": by_kind}
    exempt = []
    if scope_ids is not None:
        items["outOfScopeIds"] = [eid for eid in contested if eid not in scope_ids]
        decision_ids = {d.get("id") for d in (decisions_doc or {}).get("entries", []) or []}
        for eid in in_scope:
            e = entries_by_id[eid]
            if (not [c for c in e.get("conflictsWith") or [] if c in scope_ids] and is_nonempty(e.get("conflictsOutOfScope"))
                    and is_nonempty(e.get("decisionRef")) and e.get("decisionRef") in decision_ids):
                exempt.append(eid)
        if exempt:
            items["exemptConflictsOutOfScopeIds"] = exempt
    if stage == "pre-select":
        return {"status": "report", "items": items}
    if [eid for eid in in_scope if eid not in exempt]:
        return {"status": "fail", "items": items}
    return {"status": "report" if exempt else "pass", "items": items}


def rule_why_missing(entries_by_id, stage, function_map_doc=None):
    """Timeline entries with whyMissing are listed. After pre-select one blocks when a selected
    candidate's ledgerDeps use it and it has no whyMissingImpact (why the gap does not matter there)."""
    missing = [eid for eid, e in entries_by_id.items() if e.get("kind") == "timeline" and e.get("whyMissing")]
    if stage == "pre-select":
        return {"status": "report", "items": [{"id": eid} for eid in missing]}
    selected = collect_selected_entry_ids(function_map_doc) if function_map_doc else set()
    items, blocking = [], False
    for eid in missing:
        referenced = eid in selected
        impact = is_nonempty(entries_by_id[eid].get("whyMissingImpact"))
        items.append({"id": eid, "referencedBySelected": referenced, "hasWhyMissingImpact": impact})
        blocking = blocking or (referenced and not impact)
    result = {"status": "fail" if blocking else "report", "items": items}
    if function_map_doc is None:
        result["note"] = "未给 --function-map，无法判定是否被 selected 候选引用，按只报处理"
    return result


def _dependent_function_ids(dependents):
    for dep in dependents or []:
        if isinstance(dep, str) and dep.startswith("F-"):
            yield dep
        elif isinstance(dep, dict) and is_nonempty(dep.get("functionId")):
            yield dep["functionId"]


def rule_refs_exist(entries_by_id, cards_dir=None, function_map_doc=None):
    """realityRef ids exist under --cards; conflictsWith targets exist and point back (or list this
    entry in their conflictsOutOfScope); a retired entry's old conflictsWith is history and not
    checked; dependents' functionIds exist in --function-map."""
    items = []
    card_ids = build_card_index(cards_dir) if cards_dir else None
    function_ids = collect_function_ids(function_map_doc) if function_map_doc else None
    for eid, e in entries_by_id.items():
        if card_ids is not None:
            for ref in e.get("realityRef") or []:
                if isinstance(ref, str) and ref.split("#")[0] not in card_ids:
                    items.append(f"{eid}: realityRef {ref!r} 在 --cards 目录下找不到对应卡")
        if e.get("status") != "retired":
            for other_id in e.get("conflictsWith") or []:
                other = entries_by_id.get(other_id)
                if other is None:
                    items.append(f"{eid}: conflictsWith 指向不存在的 {other_id!r}")
                elif eid not in (other.get("conflictsWith") or []) and eid not in (other.get("conflictsOutOfScope") or []):
                    items.append(f"{eid}: conflictsWith {other_id}，但 {other_id} 没有反向列出 {eid}")
        if function_ids is not None:
            for fid in _dependent_function_ids(e.get("dependents")):
                if fid not in function_ids:
                    items.append(f"{eid}: dependents 引用的 functionId {fid!r} 不在功能地图里")
    result = {"status": "fail" if items else "pass", "items": items}
    if cards_dir is None:
        result["note"] = "未给 --cards，realityRef 一项未核"
    return result


def rule_license_has_words(entries_by_id):
    items = [eid for eid, e in entries_by_id.items() if e.get("status") == "accepted_license" and not is_nonempty(e.get("humanWords"))]
    return {"status": "fail" if items else "pass", "items": items}


def rule_procedure_open(entries_by_id):
    """Procedure entries (not retired/verified) still owing a next necessary move. Report only."""
    return {"status": "report", "items": [eid for eid, e in entries_by_id.items() if e.get("kind") == "procedure"
                                          and e.get("status") not in ("retired", "verified") and is_nonempty(e.get("nextNecessaryMove"))]}


def rule_retired_user_given_justified(entries_by_id, decisions_doc=None):
    """A retired user_given entry needs somewhere it went: decisionRef (must exist when --decisions is
    given), retiresInto, or retiredBy from the vocabulary (layer_choice)."""
    decision_ids = {d.get("id") for d in (decisions_doc or {}).get("entries", []) or []}
    items = []
    for eid, e in entries_by_id.items():
        if e.get("status") != "retired" or e.get("origin") not in ("user_given", "user_given_modified"):
            continue
        ref = e.get("decisionRef")
        if is_nonempty(ref) and decisions_doc is not None and ref not in decision_ids:
            items.append(f"{eid}: decisionRef={ref!r} 在决定队列里找不到")
            continue
        retired_by = e.get("retiredBy")
        if is_nonempty(retired_by) and retired_by not in RETIRED_BY_VOCAB:
            items.append(f"{eid}: retiredBy={retired_by!r} 不在词表 {sorted(RETIRED_BY_VOCAB)} 内")
            continue
        if not (is_nonempty(ref) or is_nonempty(e.get("retiresInto")) or is_nonempty(retired_by)):
            items.append(f"{eid}: status=retired 的用户给定条目没有 decisionRef/retiresInto/retiredBy，查不到退役去处")
    return {"status": "fail" if items else "pass", "items": items}


def rule_selected_deps_not_contested(entries_by_id, function_map_doc):
    if function_map_doc is None:
        return {"status": "report", "items": [], "note": "未给 --function-map，未核"}
    selected = collect_selected_entry_ids(function_map_doc)
    items, seen = [], set()
    for eid in sorted(selected):
        e = entries_by_id.get(eid)
        if e is None or e.get("status") != "contested":
            continue
        for other in e.get("conflictsWith") or []:
            pair = tuple(sorted((eid, other)))
            if other in selected and pair not in seen:
                seen.add(pair)
                items.append(f"{eid} 与 {other} 互为 contested，但都被 selected 候选的 ledgerDeps 引用")
    return {"status": "fail" if items else "pass", "items": items}


def rule_not_asked_not_verified(entries_by_id):
    items = [eid for eid, e in entries_by_id.items() if e.get("notAsked") and e.get("status") == "verified"]
    return {"status": "fail" if items else "pass", "items": items}


# --scope: rules see every entry; violations about out-of-scope ids move to outOfScopeItems.
_ID_TOKEN_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+){0,2}-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")


def load_scope_ids(path):
    """A plain id list, or a scope file with ledgerEntries[] (strings or {id})."""
    doc = load_json(path, "范围文件")
    if isinstance(doc, list):
        return {x if isinstance(x, str) else (x or {}).get("id") for x in doc} - {None}
    ids = set()
    for item in (doc or {}).get("ledgerEntries", []) or []:
        if isinstance(item, str):
            ids.add(item)
        elif isinstance(item, dict) and is_nonempty(item.get("id")):
            ids.add(item["id"])
    return ids


def _item_ids(item):
    if isinstance(item, dict):
        if is_nonempty(item.get("id")):
            return [item["id"]]
        return item["ids"] if isinstance(item.get("ids"), list) else []
    if isinstance(item, str):
        return _ID_TOKEN_RE.findall(item)
    return []


def apply_scope_filter(result, scope_ids):
    items = result.get("items")
    if scope_ids is None or not isinstance(items, list):
        return result
    inside, outside = [], []
    for it in items:
        ids = _item_ids(it)
        (inside if not ids or any(i in scope_ids for i in ids) else outside).append(it)
    new = dict(result, items=inside)
    if outside:
        new["outOfScopeItems"] = outside
    if result["status"] == "fail":
        new["status"] = "fail" if inside else "pass"
    return new


def delta_chains(deltas):
    """Deltas in episode order, as the chains a ledger revision is built from: the planned chain, and
    when actual deltas are given, the actual chain (an episode without an actual delta keeps its
    planned one). Planned and actual of one episode are alternatives, never applied one after another."""
    ordered = sorted(deltas, key=lambda d: episode_order_key()(d.get("episode")))
    planned = [d for d in ordered if d.get("track") == "planned"]
    if not any(d.get("track") == "actual" for d in ordered):
        return [planned]
    actual_eps = {str(d.get("episode")) for d in ordered if d.get("track") == "actual"}
    actual = [d for d in ordered if d.get("track") == "actual" or str(d.get("episode")) not in actual_eps]
    return [planned, actual] if planned else [actual]


def over_chains(rule_fn, chains):
    """Run a delta rule on every chain; items merged without repeats, worst status wins."""
    rank = {"pass": 0, "report": 1, "fail": 2}
    status, items = "pass", []
    for chain in chains:
        result = rule_fn(chain)
        status = max(status, result["status"], key=rank.get)
        items.extend(i for i in result["items"] if i not in items)
    return {"status": status, "items": items}


def run_all_checks(entries_by_id, deltas, stage, cards_dir=None, function_map_doc=None, scope_ids=None,
                   decisions_doc=None, duplicate_ids=()):
    chains = delta_chains(deltas)
    rules = {
        "schema-basic": rule_schema_basic(entries_by_id, duplicate_ids),
        "delta-applies": over_chains(lambda c: rule_delta_applies(entries_by_id, c), chains),
        "object-single-chain": over_chains(lambda c: rule_object_single_chain(entries_by_id, c, stage), chains),
        "knowledge-monotonic": over_chains(lambda c: rule_knowledge_monotonic(entries_by_id, c), chains),
        "money-closed": rule_money_closed(entries_by_id, stage),
        "presence-vs-timeline": {"status": "report", "items": [],
                                 "note": "按场的判法要分集计划的 events.scenes，由 plan-check 调用；ledger check 不单独跑这条"},
        "planned-vs-actual": rule_planned_vs_actual(deltas),
        "unverified-count": rule_unverified_count(entries_by_id),
        "patch-cap": over_chains(lambda c: rule_patch_cap(entries_by_id, c), chains),
        "contested-zero": rule_contested_zero(entries_by_id, stage, scope_ids, decisions_doc),
        "why-missing": rule_why_missing(entries_by_id, stage, function_map_doc),
        "refs-exist": rule_refs_exist(entries_by_id, cards_dir, function_map_doc),
        "license-has-words": rule_license_has_words(entries_by_id),
        "retired-user-given-justified": rule_retired_user_given_justified(entries_by_id, decisions_doc),
        "procedure-open": rule_procedure_open(entries_by_id),
        "selected-deps-not-contested": rule_selected_deps_not_contested(entries_by_id, function_map_doc),
        "not-asked-not-verified": rule_not_asked_not_verified(entries_by_id),
    }
    if scope_ids is not None:  # contested-zero applies the scope itself (it needs the decisions)
        rules = {name: r if name == "contested-zero" else apply_scope_filter(r, scope_ids) for name, r in rules.items()}
    blocking_names = BLOCKING_RULES_PRESELECT if stage == "pre-select" else set(rules)
    return rules, not any(rules[name]["status"] == "fail" for name in blocking_names if name in rules)


# ---------------------------------------------------------------------------
# Knowledge export (knows)
# ---------------------------------------------------------------------------
def knows_for_person(entries_by_id, person, at=None):
    """knows/notKnows of one person: knowledge entries with `who`, plus derived items from object
    `visibleTo` and timeline `knownTo` (marked kind/derivedFrom/text). `at` (an episode id) filters
    knowledge parts whose `since` names a later episode; parts without a readable episode stay."""
    at_key = ep_key(at) if at is not None else None
    knows, not_knows = [], set()
    for eid, e in entries_by_id.items():
        if e.get("status") == "retired":
            continue
        kind = e.get("kind")
        if kind == "knowledge" and e.get("who") == person:
            parts = since_value_parts(e.get("since")) or [(None, e.get("since"))]
            kept = []
            for aspect, beat in parts:
                key = ep_key(beat)
                if at_key is not None and key is not None and key > at_key:
                    continue
                item = {"entryId": eid, "knows": e.get("knows"), "since": beat, "how": e.get("how")}
                if aspect:
                    item["part"] = aspect
                kept.append(item)
            knows.extend(kept)
            if kept:
                not_knows.update(x for x in e.get("notKnows") or [] if isinstance(x, str))
        elif kind == "object" and person in (e.get("visibleTo") or []):
            knows.append({"entryId": eid, "kind": "object", "derivedFrom": "visibleTo", "text": e.get("title") or e.get("object")})
        elif kind == "timeline" and person in (e.get("knownTo") or []):
            knows.append({"entryId": eid, "kind": "timeline", "derivedFrom": "knownTo",
                          "text": e.get("title") or e.get("did") or e.get("state")})
    known_texts = {k.get("knows") for k in knows if k.get("knows")} | {k.get("text") for k in knows if k.get("text")}
    return {"knows": knows, "notKnows": sorted(x for x in not_knows if x not in known_texts)}


def _in_or_after_scene(beat_text, scene_order_index, current_idx):
    if beat_text is None or current_idx is None:
        return False
    scene, _ = parse_beat_ref(beat_text)
    if scene is None:
        return False
    return beat_sort_key(beat_text, scene_order_index)[0] >= current_idx


def knows_scene_aware(entries_by_id, person, scene_order_index, current_scene_id, touched_this_scene=()):
    """knows of one person before a scene starts. Beat-timed data (knowledge `since`, object
    `visibleToSince`, timeline `knownToSince`, nested per part) is judged part by part: parts timed in
    this scene or later are left out. An entry without beat data counts as known before the scene,
    unless this scene's writes created it or touched its timing fields (no evidence it was known)."""
    current_idx = scene_order_index.get(current_scene_id)
    touched = set(touched_this_scene or ())
    knows, not_knows = [], set()

    def add_parts(eid, parts, fallback_item, text_fallback):
        any_known = False
        if parts is None:
            if eid in touched:
                return False
            knows.append(fallback_item)
            return True
        for aspect, beat in parts:
            if _in_or_after_scene(beat, scene_order_index, current_idx):
                continue
            any_known = True
            if "knows" in fallback_item:
                item = {"entryId": eid, "knows": fallback_item["knows"], "since": beat, "how": fallback_item["how"]}
            else:
                item = dict(fallback_item, text=aspect or text_fallback)
            if aspect:
                item["part"] = aspect
            knows.append(item)
        return any_known

    for eid, e in entries_by_id.items():
        if e.get("status") == "retired":
            continue
        kind = e.get("kind")
        if kind == "knowledge" and e.get("who") == person:
            base = {"entryId": eid, "knows": e.get("knows"), "since": e.get("since"), "how": e.get("how")}
            if add_parts(eid, since_value_parts(e.get("since")), base, None):
                not_knows.update(x for x in e.get("notKnows") or [] if isinstance(x, str))
        elif kind == "object" and person in (e.get("visibleTo") or []):
            text = e.get("title") or e.get("object")
            add_parts(eid, person_since_parts(e.get("visibleToSince"), person),
                      {"entryId": eid, "kind": "object", "derivedFrom": "visibleTo", "text": text}, text)
        elif kind == "timeline" and person in (e.get("knownTo") or []):
            text = e.get("title") or e.get("did") or e.get("state")
            add_parts(eid, person_since_parts(e.get("knownToSince"), person),
                      {"entryId": eid, "kind": "timeline", "derivedFrom": "knownTo", "text": text}, text)
    known_texts = {k.get("knows") for k in knows if k.get("knows")} | {k.get("text") for k in knows if k.get("text")}
    return {"knows": knows, "notKnows": sorted(x for x in not_knows if x not in known_texts)}


def within_scene_events(entries_by_id, scene_id):
    """Who newly knows what at which beat inside one scene (knowledge `since`, object
    `visibleToSince`, timeline `knownToSince`; nested parts listed separately with `aspect`)."""
    beats = {}

    def add(beat_text, eid, who, aspect=None):
        scene, num = parse_beat_ref(beat_text)
        if scene != scene_id:
            return
        item = {"entryId": eid, "who": who}
        if aspect:
            item["aspect"] = aspect
        beats.setdefault(num, []).append(item)

    for eid, e in entries_by_id.items():
        if e.get("status") == "retired":
            continue
        kind = e.get("kind")
        if kind == "knowledge" and e.get("who"):
            for aspect, beat in since_value_parts(e.get("since")) or []:
                add(beat, eid, e["who"], aspect)
        elif kind in ("object", "timeline"):
            field = "visibleToSince" if kind == "object" else "knownToSince"
            for person, val in (e.get(field) or {}).items() if isinstance(e.get(field), dict) else []:
                for aspect, beat in since_value_parts(val) or []:
                    add(beat, eid, person, aspect)
    return [{"beatId": f"{scene_id}.b{num}", "newlyKnown": beats[num]} for num in sorted(beats)]


def scene_states(base_entries_by_id, plan):
    """Walk an episode plan's scenes in order. Yields (scene, working_entries, touched_ids, apply_errors)
    with this scene's ledgerDelta writes already applied (a write that only appends beat timing to an
    older entry must count) and `touched_ids` holding the entries this scene created or whose timing
    fields it changed. Writes whose supportedBy names no scene of the plan are returned at the end."""
    scenes = (plan.get("events") or {}).get("scenes") or []
    scene_ids = [sc.get("sceneId") for sc in scenes]
    delta = plan.get("ledgerDelta") or {}
    writes_by_scene, unresolved = {}, []
    for w in delta.get("writes", []) or []:
        supported = w.get("supportedBy") or ""
        sid = supported.split(".")[0] if isinstance(supported, str) and supported else None
        if sid in scene_ids:
            writes_by_scene.setdefault(sid, []).append(w)
        else:
            unresolved.append(w)
    working = copy.deepcopy(base_entries_by_id)
    errors = []
    states = []
    for sc in scenes:
        sid = sc.get("sceneId")
        touched = set()
        for w in writes_by_scene.get(sid, []):
            target = write_target_id(w)
            if target and (w.get("entryId") == "new" or TIMING_FIELDS & set(w.get("change") or {})):
                touched.add(target)
            apply_write(working, w, plan.get("episode"), delta.get("track", "planned"), errors=errors, where=f"{sid}")
        states.append((sc, copy.deepcopy(working), touched))
    return states, unresolved, errors


def knows_by_scene(base_entries_by_id, plan):
    scenes = (plan.get("events") or {}).get("scenes") or []
    if not scenes:
        raise InputError("分集计划 events.scenes 为空")
    order = {sc.get("sceneId"): i for i, sc in enumerate(scenes)}
    states, unresolved, errors = scene_states(base_entries_by_id, plan)
    out = []
    for sc, working, touched in states:
        sid = sc.get("sceneId")
        present = sc.get("present") or []
        out.append({"sceneId": sid, "present": present,
                    "byPerson": {p: knows_scene_aware(working, p, order, sid, touched) for p in present},
                    "withinScene": within_scene_events(working, sid)})
    return out, unresolved, errors


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------
def merge_field(entry, field_name, value):
    """Append, never overwrite: lists extend without duplicates, dicts update, strings join with "；"."""
    existing = entry.get(field_name)
    if isinstance(value, list):
        existing = existing if isinstance(existing, list) else ([] if existing is None else [existing])
        for item in value:
            if item not in existing:
                existing.append(item)
        entry[field_name] = existing
    elif isinstance(value, dict):
        entry[field_name] = dict(existing, **value) if isinstance(existing, dict) else dict(value)
    elif existing is None:
        entry[field_name] = value
    elif isinstance(existing, str) and isinstance(value, str):
        if value not in existing:
            entry[field_name] = existing + "；" + value
    else:
        entry[field_name] = value


def normalize_entry_fields(entry):
    """Field-name unification across parts: defectKey -> defectKeys[]; a string nextNecessaryMove ->
    {mandated, customary, legacyText}; conflictNotes -> [{with, note, conflictKind}]."""
    if "defectKey" in entry:
        dk = entry.pop("defectKey")
        keys = entry.get("defectKeys") or []
        for item in dk if isinstance(dk, list) else [dk]:
            if item not in keys:
                keys.append(item)
        entry["defectKeys"] = keys
    if entry.get("kind") == "procedure" and isinstance(entry.get("nextNecessaryMove"), str):
        entry["nextNecessaryMove"] = {"mandated": None, "customary": None, "legacyText": entry["nextNecessaryMove"]}
    if isinstance(entry.get("conflictNotes"), list):
        entry["conflictNotes"] = [{"with": n.get("with"), "note": n.get("note"), "conflictKind": n.get("conflictKind")}
                                  if isinstance(n, dict) else {"with": None, "note": str(n), "conflictKind": None}
                                  for n in entry["conflictNotes"]]


def apply_amendment(entry, amendment, part_name, rev):
    """amendment.add: statusChange {to, note} changes status with a history line; a key ending in
    "Add" merges into the field without the suffix; any other key merges into the same-named field."""
    for key, value in (amendment.get("add") or {}).items():
        if key == "statusChange" and isinstance(value, dict):
            old = entry.get("status")
            entry["status"] = value.get("to")
            entry.setdefault("history", []).append({"rev": rev, "change": f"status {old} -> {value.get('to')}（来源段：{part_name}；{value.get('note', '')}）",
                                                    "by": f"merge:{part_name}", "when": rev})
        elif key.endswith("Add"):
            merge_field(entry, key[:-3], value)
        else:
            merge_field(entry, key, value)


def json_type(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", list: "array", dict: "object"}.get(type(value), "other")


def field_type_conflicts(entries):
    """Same field name, different JSON types between entries of the same kind (nulls ignored)."""
    seen = {}
    for e in entries:
        for k, v in e.items():
            t = json_type(v)
            if t is not None:
                seen.setdefault((e.get("kind"), k), {}).setdefault(t, []).append(e.get("id"))
    return [{"kind": kind, "field": field, "types": {t: ids[:5] for t, ids in types.items()}}
            for (kind, field), types in sorted(seen.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])) if len(types) > 1]


def normalize_title(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)


def cmd_merge(args):
    parts = [(p, load_json(p, "底账分段文件")) for p in args.part]
    merged, errors, warnings, part_meta, gap_groups, amendments = {}, [], [], [], [], []
    proc_titles = {}
    head = {}
    for path, doc in parts:
        if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
            raise InputError(f"底账分段文件缺 entries 数组：{path}")
        for key in ("rev", "track"):
            head.setdefault(key, doc.get(key))
        head.setdefault("head", schema_head(doc))
        part_meta.append({"part": doc.get("part"), "scope": doc.get("scope"), "cardRevision": doc.get("cardRevision"),
                          "sourceFile": os.path.basename(path)})
        gap_groups.extend(doc.get("gapGroups") or [])
        amendments.extend((doc.get("part") or os.path.basename(path), a) for a in doc.get("amendments") or [])
        for e in doc["entries"]:
            eid = e.get("id") if isinstance(e, dict) else None
            if not is_nonempty(eid):
                errors.append(f"{path}: 有条目缺 id")
            elif eid in merged:
                errors.append(f"{path}: id {eid!r} 与之前分段冲突")
            else:
                merged[eid] = copy.deepcopy(e)
                if e.get("kind") == "procedure" and is_nonempty(e.get("title")):
                    if e["title"] in proc_titles:
                        warnings.append(f"procedure 条目 title 完全相同：{eid} 与 {proc_titles[e['title']]}")
                    else:
                        proc_titles[e["title"]] = eid
    if errors:
        emit({"ok": True, "passed": False, "errors": errors, "warnings": warnings, "reproduceCommand": args.reproduce})
        return 2
    for e in merged.values():
        normalize_entry_fields(e)
    rev = head.get("rev") or "ep000"
    amendment_errors, applied = [], 0
    for part_name, amend in amendments:  # amendments may target entries of another part
        entry = merged.get(amend.get("entryId"))
        if entry is None:
            amendment_errors.append(f"[{part_name}] amendment 目标 {amend.get('entryId')!r} 不存在，跳过")
            continue
        apply_amendment(entry, amend, part_name, rev)
        applied += 1
    pairs = []
    for spec in args.same_procedure or []:
        ids = [x.strip() for x in spec.split(",") if x.strip()]
        if len(ids) != 2:
            raise InputError(f"--same-procedure 要两个 id，用逗号隔开：{spec!r}")
        pairs.append(tuple(ids))
    for eid, e in merged.items():
        for other in e.get("sameProcedureAs") or []:
            pairs.append((eid, other))
    same_errors, mismatch, seen = [], [], set()
    for a, b in pairs:
        for x, y in ((a, b), (b, a)):
            if x not in merged:
                same_errors.append(f"sameProcedureAs 对里的 {x!r} 不存在")
                continue
            lst = merged[x].setdefault("sameProcedureAs", [])
            if y not in lst:
                lst.append(y)
    for a, b in pairs:
        key = tuple(sorted((a, b)))
        if key in seen or a not in merged or b not in merged:
            continue
        seen.add(key)
        if merged[a].get("status") != merged[b].get("status"):
            mismatch.append({"pair": list(key), "statusA": merged[key[0]].get("status"), "statusB": merged[key[1]].get("status")})
    by_title = {}
    for eid, e in merged.items():
        if e.get("kind") == "procedure" and is_nonempty(e.get("title")):
            by_title.setdefault(normalize_title(e["title"]), []).append(eid)
    duplicates = [{"normalizedTitle": t, "ids": ids} for t, ids in by_title.items() if len(ids) > 1]
    type_conflicts = field_type_conflicts(merged.values())
    out_doc = {**(head.get("head") or {"schemaVersion": SCHEMA}), "rev": rev, "track": head.get("track") or "pre", "parts": part_meta,
               "gapGroups": gap_groups, "entries": list(merged.values()), "statusMismatch": mismatch,
               "possibleDuplicates": duplicates, "fieldTypeConflicts": type_conflicts, "formatNotes": []}
    write_json(args.out, out_doc)
    emit({"ok": True, "passed": True, "out": args.out, "entries": len(merged), "amendmentsApplied": applied,
          "amendmentErrors": amendment_errors, "sameProcedureErrors": same_errors, "warnings": warnings,
          "statusMismatch": mismatch, "possibleDuplicates": duplicates, "fieldTypeConflicts": type_conflicts,
          "reproduceCommand": args.reproduce})
    return 0


# ---------------------------------------------------------------------------
# Other subcommands
# ---------------------------------------------------------------------------
def cmd_init(args):
    if os.path.exists(args.out):
        raise InputError(f"{args.out} 已存在，init 不覆盖")
    doc = {"schemaVersion": SCHEMA, "rev": args.rev, "track": "pre", "entries": [], "formatNotes": []}
    write_json(args.out, doc)
    emit({"ok": True, "out": args.out, "rev": args.rev, "entries": 0, "reproduceCommand": args.reproduce})
    return 0


def load_decisions(paths):
    return merge_decision_docs([load_json(p, "决定队列") for p in paths]) if paths else None


def cmd_check(args):
    _, entries_by_id, dups = load_ledger(args.ledger)
    deltas = [load_delta(p) for p in args.delta or []]
    function_map_doc = load_json(args.function_map, "功能地图") if args.function_map else None
    scope_ids = load_scope_ids(args.scope) if args.scope else None
    rules, passed = run_all_checks(entries_by_id, deltas, args.stage, cards_dir=args.cards, function_map_doc=function_map_doc,
                                   scope_ids=scope_ids, decisions_doc=load_decisions(args.decisions), duplicate_ids=dups)
    emit({"ok": True, "passed": passed, "stage": args.stage, "scoped": scope_ids is not None,
          "deltas": [f"ep{d.get('episode')}.{d.get('track')}" for d in deltas], "rules": rules,
          "reproduceCommand": args.reproduce})
    return 0 if passed else 2


def rev_from_out(out, fallback):
    base = os.path.splitext(os.path.basename(out))[0] if out else ""
    m = re.match(r"ledger-(ep.+)", base)
    return m.group(1) if m else fallback


def cmd_apply(args):
    doc, entries_by_id, _ = load_ledger(args.ledger)
    deltas = [load_delta(p) for p in args.delta]
    errors, touched, tracks = [], set(), set()
    for delta in deltas:
        tracks.add(delta["track"])
        touched.update(apply_delta(entries_by_id, delta, errors=errors))
    out_doc = {**schema_head(doc), "rev": rev_from_out(args.out, "applied"),
               "track": tracks.pop() if len(tracks) == 1 else "mixed", "entries": list(entries_by_id.values()),
               "formatNotes": doc.get("formatNotes", [])}
    write_json(args.out, out_doc)
    emit({"ok": True, "passed": not errors, "out": args.out, "deltasApplied": len(deltas),
          "entriesTouched": sorted(touched), "errors": errors, "reproduceCommand": args.reproduce})
    return 0 if not errors else 2


def plan_replay(deltas, at, track, season_doc=None):
    """Pick and order the deltas for ledger@<at>.<track>. For track actual an episode without an
    actual delta uses its planned one and is listed in plannedFallback (never silently)."""
    at_key = ep_key(at)
    if at_key is None:
        raise InputError(f"--at {at!r} 读不出集号")
    by_episode = {}
    for path, d in deltas:
        slot = by_episode.setdefault(str(d.get("episode")), {})
        if d["track"] in slot:
            raise InputError(f"第 {d.get('episode')} 集 {d['track']} 轨给了两份 delta：{slot[d['track']][0]} 与 {path}")
        slot[d["track"]] = (path, d)
    sort_key = episode_order_key(season_doc)
    at_sort = sort_key(at)
    chosen, fallback, skipped = [], [], []
    for ep in sorted(by_episode, key=sort_key):
        if sort_key(ep) > at_sort:
            skipped.append(ep)
            continue
        tracks = by_episode[ep]
        if track in tracks:
            chosen.append(tracks[track])
        elif track == "actual" and "planned" in tracks:
            chosen.append(tracks["planned"])
            fallback.append(ep)
        else:
            raise InputError(f"第 {ep} 集没有 {track} 轨的 delta")
    return chosen, fallback, skipped


def render_state_md(rev, entries_by_id):
    live = {eid: e for eid, e in entries_by_id.items() if e.get("status") != "retired"}
    lines = [f"# 入口状态：ledger@{rev}", "", "由 `ledger replay --md` 从底账导出；不是手写，改账再导出。", ""]

    def table(header, rows):
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        for row in rows:
            lines.append("| " + " | ".join(str(c if c is not None else "").replace("|", "\\|").replace("\n", " ") for c in row) + " |")
        lines.append("")

    def text(v):
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        return v

    lines += ["## 谁知道什么", ""]
    by_who = {}
    for eid, e in live.items():
        if e.get("kind") == "knowledge":
            by_who.setdefault(e.get("who") or "（未写 who）", []).append((eid, e))
    for who in sorted(by_who):
        lines += [f"### {who}", ""]
        table(["id", "知道", "从何时", "怎么知道", "不知道"],
              [(eid, e.get("knows"), text(e.get("since")), e.get("how"), "；".join(map(str, e.get("notKnows") or [])))
               for eid, e in by_who[who]])
    lines += ["## 物件", ""]
    table(["id", "物件", "在谁手里", "在哪", "状态", "谁看得见"],
          [(eid, e.get("object") or e.get("title"), e.get("holder"), e.get("location"), text(e.get("state")),
            "、".join(map(str, e.get("visibleTo") or []))) for eid, e in live.items() if e.get("kind") == "object"])
    lines += ["## 状态（法律、人身、关系）", ""]
    table(["id", "谁／什么", "状态", "起", "止"],
          [(eid, e.get("stateOf"), e.get("state"), e.get("validFrom"), e.get("validTo"))
           for eid, e in live.items() if e.get("kind") == "timeline" and e.get("subtype") == "state"])
    lines += ["## 时间线", ""]
    timeline = [(eid, e) for eid, e in live.items() if e.get("kind") == "timeline" and e.get("subtype") != "state"]
    timeline.sort(key=lambda kv: ep_key(kv[1].get("introducedAt")) or (10 ** 9, ""))
    table(["id", "何时", "谁", "在哪", "做了", "没做", "谁知道"],
          [(eid, e.get("when"), e.get("who"), e.get("where"), e.get("did"), e.get("didNot"), "、".join(map(str, e.get("knownTo") or [])))
           for eid, e in timeline])
    lines += ["## 钱", ""]
    table(["id", "数额", "从", "到", "账户", "谁能动", "痕迹"],
          [(eid, e.get("amount"), e.get("from"), e.get("to"), e.get("account"), text(e.get("whoCanMove")), e.get("trace"))
           for eid, e in live.items() if e.get("kind") == "money"])
    lines += ["## 未闭合的程序", ""]
    table(["id", "程序", "欠的下一步", "状态"],
          [(eid, e.get("name") or e.get("title"), text(e.get("nextNecessaryMove")), e.get("status"))
           for eid in rule_procedure_open(live)["items"] for e in [live[eid]]])
    lines += ["## 未写明", ""]
    table(["id", "类", "标题", "登记"],
          [(eid, e.get("kind"), e.get("title"), "；".join(x for x in (
              "whyMissing" if e.get("whyMissing") else "", "unstated" if e.get("unstated") else "",
              ("emptyFields: " + "、".join(map(str, e.get("emptyFields")))) if is_nonempty(e.get("emptyFields")) else "") if x))
           for eid, e in live.items() if e.get("whyMissing") or e.get("unstated") or is_nonempty(e.get("emptyFields"))])
    return "\n".join(lines)


def cmd_replay(args):
    doc, entries_by_id, _ = load_ledger(args.ledger)
    deltas = [(p, load_delta(p)) for p in args.delta or []]
    season_doc = load_json(args.season, "季编排") if args.season else None
    chosen, fallback, skipped = plan_replay(deltas, args.at, args.track, season_doc)
    errors, steps = [], []
    for path, delta in chosen:
        touched = apply_delta(entries_by_id, delta, errors=errors)
        steps.append({"episode": delta.get("episode"), "track": delta.get("track"), "delta": path, "writes": len(delta.get("writes") or []),
                      "entriesTouched": len(set(touched))})
    rev = f"ep{ep_label(ep_key(args.at))}.{args.track}"
    out_doc = {**schema_head(doc), "rev": rev, "track": args.track, "replayedFrom": doc.get("rev"),
               "entries": list(entries_by_id.values()), "formatNotes": doc.get("formatNotes", [])}
    if args.out:
        write_json(args.out, out_doc)
    if args.md:
        print(render_state_md(rev, entries_by_id))
    else:
        emit({"ok": True, "passed": not errors, "rev": rev, "from": doc.get("rev"), "at": args.at, "track": args.track,
              "steps": steps, "plannedFallback": fallback, "notReplayed": skipped, "entries": len(entries_by_id),
              "out": args.out, "errors": errors, "reproduceCommand": args.reproduce})
    return 0 if not errors else 2


def cmd_diff(args):
    _, a, _ = load_ledger(args.a)
    _, b, _ = load_ledger(args.b)
    changed = {}
    for eid in sorted(set(a) & set(b)):
        fields = {k: {"from": a[eid].get(k), "to": b[eid].get(k)} for k in sorted(set(a[eid]) | set(b[eid]))
                  if k != "history" and a[eid].get(k) != b[eid].get(k)}
        if fields:
            changed[eid] = fields
    emit({"ok": True, "added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)), "changed": changed,
          "reproduceCommand": args.reproduce})
    return 0


def cmd_knows(args):
    _, entries_by_id, _ = load_ledger(args.ledger)
    if args.episode_plan:
        if args.who or args.all_present or args.at is not None:
            raise InputError("--episode-plan 与 --who/--all-present/--at 互斥")
        plan = load_json(args.episode_plan, "分集计划")
        scenes, unresolved, errors = knows_by_scene(entries_by_id, plan)
        result = {"ok": True, "episode": plan.get("episode"), "entryLedger": args.ledger, "episodePlan": args.episode_plan,
                  "scenes": scenes, "unresolvedWrites": unresolved, "applyErrors": errors}
    elif args.all_present:
        people = [p.strip() for p in args.all_present.split(",") if p.strip()]
        result = {"ok": True, "at": args.at, "byPerson": {p: knows_for_person(entries_by_id, p, args.at) for p in people}}
    elif args.who:
        result = {"ok": True, "who": args.who, "at": args.at, **knows_for_person(entries_by_id, args.who, args.at)}
    else:
        raise InputError("没给 --who、--all-present 或 --episode-plan")
    result["reproduceCommand"] = args.reproduce
    emit(result)
    return 0


def cmd_view(args):
    _, entries_by_id, _ = load_ledger(args.ledger)
    if not args.blank_period:
        raise InputError("view 目前只支持 --blank-period")
    by_who = {}
    for e in entries_by_id.values():
        if e.get("kind") == "timeline":
            by_who.setdefault(e.get("who") or "（未写 who）", []).append(e)
    lines = ["# 空白期总账（按「谁」分组的时间线账）", ""]
    for who in sorted(by_who):
        lines += [f"## {who}", "", "| when | did | didNot | why | whyMissing |", "| --- | --- | --- | --- | --- |"]
        for e in by_who[who]:
            did = e.get("did") if e.get("subtype") != "state" else f"{e.get('stateOf') or ''}：{e.get('state') or ''}"
            cells = [e.get("when") or e.get("validFrom") or "", did or "", e.get("didNot") or "", e.get("why") or "", "⚠" if e.get("whyMissing") else ""]
            lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
        lines.append("")
    markdown = "\n".join(lines)
    if args.md:
        print(markdown)
    else:
        emit({"ok": True, "people": sorted(by_who), "timelineEntries": sum(len(v) for v in by_who.values()),
              "markdown": markdown, "reproduceCommand": args.reproduce})
    return 0


def cmd_stats(args):
    _, entries_by_id, _ = load_ledger(args.ledger)
    by_kind_status, by_origin_status = {}, {}
    counts = {"whyMissingCount": 0, "unstatedCount": 0, "emptyFieldsNonEmptyCount": 0, "tensionCount": 0, "notAskedCount": 0,
              "introducedAtPreCount": 0, "introducedAtNonPreCount": 0, "stateSubtypeCount": 0}
    for e in entries_by_id.values():
        by_kind_status.setdefault(str(e.get("kind")), {}).setdefault(str(e.get("status")), 0)
        by_kind_status[str(e.get("kind"))][str(e.get("status"))] += 1
        by_origin_status.setdefault(str(e.get("origin")), {}).setdefault(str(e.get("status")), 0)
        by_origin_status[str(e.get("origin"))][str(e.get("status"))] += 1
        counts["whyMissingCount"] += bool(e.get("whyMissing"))
        counts["unstatedCount"] += bool(e.get("unstated"))
        counts["emptyFieldsNonEmptyCount"] += is_nonempty(e.get("emptyFields"))
        counts["tensionCount"] += is_nonempty(e.get("tension"))
        counts["notAskedCount"] += bool(e.get("notAsked"))
        counts["stateSubtypeCount"] += e.get("subtype") == "state"
        counts["introducedAtPreCount" if e.get("introducedAt") == "pre" else "introducedAtNonPreCount"] += 1
    pairs, seen = {}, set()
    for eid, e in entries_by_id.items():
        if e.get("status") != "contested":
            continue
        for note in e.get("conflictNotes") or []:
            if not isinstance(note, dict) or not note.get("with"):
                continue
            kind = note.get("conflictKind") or "unspecified"
            key = (tuple(sorted((eid, str(note["with"])))), kind)
            if key not in seen:
                seen.add(key)
                pairs[kind] = pairs.get(kind, 0) + 1
    emit({"ok": True, "entriesTotal": len(entries_by_id), "byKindStatus": by_kind_status, "byOriginStatus": by_origin_status,
          "contestedPairsByConflictKind": pairs, **counts, "reproduceCommand": args.reproduce})
    return 0


def build_parser(prog=None):
    ap = argparse.ArgumentParser(prog=prog, description="底账：init/merge/apply/replay/check/diff/knows/view/stats")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="写一份空底账（不覆盖已有文件）")
    p.add_argument("--out", required=True)
    p.add_argument("--rev", default="ep000")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("merge", help="合并分段底账：字段名归一、跨段 amendments、sameProcedureAs")
    p.add_argument("part", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--same-procedure", action="append", default=[], help="A,B：两条程序条目是同一程序（互加 sameProcedureAs）")
    p.set_defaults(func=cmd_merge)
    p = sub.add_parser("check", help="集纲方案 §10.2 规则与 D6-0 增补规则")
    p.add_argument("ledger")
    p.add_argument("--delta", action="append", default=[])
    p.add_argument("--cards", default=None, help="K1 知识卡目录")
    p.add_argument("--function-map", default=None)
    p.add_argument("--stage", default="default", choices=["default", "pre-select"])
    p.add_argument("--scope", default=None, help="范围文件；范围外条目的违规只报")
    p.add_argument("--decisions", action="append", default=[], help="决定队列文件，可给多个")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("apply", help="依次应用 delta，写新修订")
    p.add_argument("ledger")
    p.add_argument("--delta", action="append", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser("replay", help="从 ep000 按集序重放到第 N 集（planned 或 actual 轨）")
    p.add_argument("ledger")
    p.add_argument("--delta", action="append", default=[])
    p.add_argument("--at", required=True)
    p.add_argument("--track", choices=VALID_TRACKS, default="planned")
    p.add_argument("--season", default=None, help="季编排；给了按 finalSequence 排集序")
    p.add_argument("--out", default=None)
    p.add_argument("--md", action="store_true", help="打印可读入口状态 Markdown（不打 JSON）")
    p.set_defaults(func=cmd_replay)
    p = sub.add_parser("diff", help="两份修订的条目差异")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(func=cmd_diff)
    p = sub.add_parser("knows", help="某人到某集的 knows/notKnows，或分集计划按场的 knows 与 withinScene")
    p.add_argument("ledger")
    p.add_argument("--who", default=None)
    p.add_argument("--at", default=None, help="集号，如 5、6A")
    p.add_argument("--all-present", default=None, help="逗号分隔的名单")
    p.add_argument("--episode-plan", default=None)
    p.set_defaults(func=cmd_knows)
    p = sub.add_parser("view", help="总账视图")
    p.add_argument("ledger")
    p.add_argument("--blank-period", action="store_true")
    p.add_argument("--md", action="store_true")
    p.set_defaults(func=cmd_view)
    p = sub.add_parser("stats", help="按 kind×status、origin×status 统计")
    p.add_argument("ledger")
    p.set_defaults(func=cmd_stats)
    return ap


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser(prog).parse_args(argv)
    args.reproduce = reproduce_command(__file__, argv)
    try:
        return args.func(args)
    except (InputError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
