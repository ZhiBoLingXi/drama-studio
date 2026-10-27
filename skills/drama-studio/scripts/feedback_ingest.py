"""feedback-ingest（骨架）：人工反馈 → writer-note，按 level 路由，只列派生物草稿清单。

输入三种（实施计划 §2.2 #9；台词方案 §9.2、§9.3）：
- 飞书评论导出 JSON（`<comment><quote>…</quote><msg user=…>…</msg></comment>`），或通用
  `{"comments": [{commentId, quote, author, text | messages[], level?, category?}]}`；
- 改稿 md：给 `--original` 时逐行比对对白，改句记句级、增删对白记来回级；
- 原话记录 md／txt：空行分段，段内 `>` 开头的行是被批原文，其余是原话；可写 `[level: …]` 标层级。

level 推断：明写的为准；改稿按改动类型；批注按一个小词表推（`levelBasis: lexicon`，信号质量低），
推不出写 `unknown`，不找人问。每条 writer-note `scope.level: project`。同类（同 level 或同 category）
≥2 次的，在草稿清单里标起草约定或新问；同一落点给了不同改法的互标 `conflictsWith`。
另认三种（D6-4）：md 里用 `### ` 分节的批注记录（每节一条：`>` 行是被批原文，其余是批注，形如「人名：台词」的
行算改法）；`--section <标题>` 只读 md 的那一节，节里的表格每行一条（「原 → 改」两列与「类别」列）；追问单回答
记录 JSON（`answers`）里落在程序或现实规则上的 notHolds，各成一条 `procedure`／`fact` 意见。

不给 `--out` 时不写任何文件，只列派生物草稿清单。给 `--out <空目录>` 时全路由派生（D6-4，§2.2 #9）：
- 句级、来回级、话题级、场结构、信息承载 → 反例（negatives.jsonl）；带改法的句级 → 人工正例（human-positives.jsonl），
  来回／话题级 → 对照对草稿（contrast-pairs.jsonl，contrast-pair 形状，provenance 指回 note）；
- 信息承载、对象约定、独白，以及同类 ≥2 次 → 约定草稿（conventions.jsonl）；同类 ≥2 次另起草新问（questions.jsonl）；
- 程序、事实 → 底账修订提案（ledger-proposals.jsonl）与 K1 卡草稿（k1-drafts.jsonl）；
- 决定 → 决定队列条目（decisions.json）。只有用户原话（note 的 authorRole 为 user）写 `decided`；编剧、顾问或来源不明的
  写 `pending`，带默认（照原话办），原话记在 basisWords（basisBy 谁说的、basisRole writer／advisor／unknown）；humanWords
  只用在 decided 条目、只记用户原话——编剧、顾问给意见，用户定。
  来源：评论项的 `authorRole`，或 `--author-role`；`--user-name <名字>` 让作者是这个名字的 note 算用户。都没有就不算用户。
每个派生物带 `fromNotes`（note id）与 `status: drafted`；`--purge <noteId> --out <目录>` 按 id 清掉它派生的全部条目。
给 `--target <台词目标>` 且起草了约定时，另写升版的台词目标（新 revision，约定 `status: drafted`、`sourceNotes`，
`changelog` 记一条），原文件不动。派生物一律 `scope.level: project`，只写进 --out，不改原文件。
退出码：0；1 输入错误（含 --out 不是空目录）。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from contract_check import REVISION_LABEL

AUTHOR_ROLES = ("user", "writer", "advisor")  # who said it; only the user decides (wording rulings #1)
from text_lines import (DIALOGUE_LINE_RE, InputError, abspath, load_json, load_text, parse_lines,
                               reproduce_command, run_cli)

LEVELS = ("line", "exchange", "topic", "scene_structure", "info_carriage", "object_convention", "monologue",
          "procedure", "fact", "decision", "unknown")
ROUTES = {
    "line": ["negative", "humanPositive"],
    "exchange": ["negative", "contrastPair"],
    "topic": ["negative", "contrastPair"],
    "scene_structure": ["negative"],
    "info_carriage": ["negative", "conventionDraft"],
    "object_convention": ["conventionDraft"],
    "monologue": ["conventionDraft"],
    "procedure": ["ledgerProposal", "k1Draft"],
    "fact": ["ledgerProposal", "k1Draft"],
    "decision": ["decision"],
}
RECURRENCE_DRAFTS = ["conventionDraft", "questionDraft"]
# 同类 ≥2 次才起草约定与新问的层级（台词方案 §9.3）；句级改法只附在反例上，不按次数起草。
RECURRENCE_LEVELS = {"exchange", "topic", "scene_structure", "info_carriage", "object_convention", "monologue"}
# 批注落在哪一层的词表：只作初推，推错就是 unknown 以外的错层，输出标 lexicon。
LEXICON = [
    ("info_carriage", ("交代", "讲清", "没看懂", "看不懂", "宾语", "主谓宾", "信息")),
    ("object_convention", ("对孩子", "对大人", "称呼", "跟谁说", "对谁说")),
    ("monologue", ("独白", "OS", "内心")),
    ("topic", ("话题", "绕", "跳")),
    ("exchange", ("接话", "回应", "来回", "顺序", "没人接")),
    ("procedure", ("程序", "流程", "手续", "规定")),
    ("decision", ("就这么定", "定了", "决定")),
]
COMMENT_RE = re.compile(r"<comment(?P<attrs>[^>]*)>(?P<body>.*?)</comment>", re.S)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUOTE_RE = re.compile(r"<quote>(.*?)</quote>", re.S)
MSG_RE = re.compile(r'<msg(?:\s+user="([^"]*)")?>(.*?)</msg>', re.S)
LEVEL_TAG_RE = re.compile(r"\[level:\s*([a-z_]+)\]")


def note_id(*parts) -> str:
    return "WN-" + hashlib.sha1("\x1f".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]


def infer_level(explicit, human_note, suggestion):
    if explicit:
        if explicit not in LEVELS:
            raise InputError(f"level={explicit!r} 不在 {list(LEVELS)}")
        return explicit, "explicit"
    for level, words in LEXICON:  # the note's own words first: a rewrite of a whole exchange still says 「话题」
        if any(word in (human_note or "") for word in words):
            return level, "lexicon"
    if suggestion:
        return "line", "suggestion_is_a_line"
    return "unknown", "none"


def make_note(source, quoted, note_text, suggestion=None, author=None, explicit_level=None, category=None, ref=None):
    level, basis = infer_level(explicit_level, note_text, suggestion)
    return {"schemaVersion": "drama-studio/writer-note/v0", "noteId": note_id(source["file"], ref, quoted, note_text, suggestion),
            "scope": {"level": "project"}, "author": author, "source": f"{source['kind']}:{source['file']}#{ref}",
            "sourceKind": source["kind"], "quotedText": quoted, "humanNote": note_text,
            "humanSuggestion": suggestion, "level": level, "levelBasis": basis,
            "signalQuality": "low" if basis == "lexicon" else "structural", "category": category,
            "attachesTo": {"lineRef": None, "planRef": None}, "conflictsWith": [], "outcome": []}


def split_messages(messages):
    """一条评论的几条消息：形如「人名：台词」的算改法，其余算批注原文。"""
    suggestion = next((m for m in messages if DIALOGUE_LINE_RE.match(m.strip())), None)
    return "\n".join(m for m in messages if m is not suggestion) or None, suggestion


def notes_from_comments(doc, source):
    notes = []
    raw = (((doc.get("data") or {}).get("document") or {}).get("reference_map") or {}).get("comments")
    if isinstance(raw, dict):
        for key, value in raw.items():
            for match in COMMENT_RE.finditer(str((value or {}).get("data") or "")):
                attrs = dict(ATTR_RE.findall(match.group("attrs")))
                quote = QUOTE_RE.search(match.group("body"))
                messages = [(user, text.strip()) for user, text in MSG_RE.findall(match.group("body"))]
                note_text, suggestion = split_messages([text for _, text in messages])
                notes.append(make_note(source, quote.group(1).strip() if quote else None, note_text, suggestion,
                                       messages[0][0] if messages else None, ref=attrs.get("comment-id") or key))
        return notes
    if not isinstance(doc.get("comments"), list):
        raise InputError("评论 JSON 既不是飞书文档评论导出，也没有 comments 数组")
    for i, item in enumerate(doc["comments"]):
        messages = [m.get("text") if isinstance(m, dict) else m for m in item.get("messages") or []] or [item.get("text")]
        note_text, suggestion = split_messages([m for m in messages if m])
        note = make_note(source, item.get("quote"), note_text, item.get("suggestion") or suggestion,
                         item.get("author"), item.get("level"), item.get("category"), item.get("commentId") or f"comments[{i}]")
        if item.get("authorRole") in AUTHOR_ROLES:
            note["authorRole"] = item["authorRole"]
        notes.append(note)
    return notes


def notes_from_revision(revised_text, original_text, source):
    old = [r for r in parse_lines(original_text) if r["kind"] == "dialogue"]
    new = [r for r in parse_lines(revised_text) if r["kind"] == "dialogue"]
    matcher = difflib.SequenceMatcher(a=[(r["speaker"], r["content"]) for r in old],
                                      b=[(r["speaker"], r["content"]) for r in new], autojunk=False)
    notes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        level = "line" if tag == "replace" and i2 - i1 == j2 - j1 else "exchange"
        for k in range(max(i2 - i1, j2 - j1)):
            before = old[i1 + k] if i1 + k < i2 else None
            after = new[j1 + k] if j1 + k < j2 else None
            note = make_note(source, before["raw"].strip() if before else None, f"改稿{tag}",
                             after["raw"].strip() if after else None, explicit_level=level,
                             ref=f"original:{before['line'] if before else '-'} revised:{after['line'] if after else '-'}")
            note["levelBasis"] = "diff"
            note["attachesTo"]["lineRef"] = before["line"] if before else None
            notes.append(note)
    return notes


def notes_from_record(text, source):
    notes = []
    for i, block in enumerate(re.split(r"\n\s*\n", text)):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
        quoted = " ".join(l.lstrip(">").strip() for l in lines if l.startswith(">")) or None
        said = "\n".join(l for l in lines if not l.startswith(">"))
        if not said and not quoted:
            continue
        tag = LEVEL_TAG_RE.search(said)
        notes.append(make_note(source, quoted, LEVEL_TAG_RE.sub("", said).strip() or None,
                               explicit_level=tag.group(1) if tag else None, ref=f"block[{i}]"))
    return notes


SECTION_RE = re.compile(r"^###\s+(.+?)\s*$", re.M)
LABEL_LINE_RE = re.compile(r"^\*\*[^*]+\*\*\s*$")  # 「**被批注的原文：**」这类小标题，不是批注
TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
CHANGE_RE = re.compile(r"^(?P<before>.+?)\s*→\s*(?P<after>.+)$")
PROCEDURE_DEP_RE = re.compile(r"(?:^|[-.])(?:p\d|proc)", re.I)


REWRITE_PREFIX = re.compile(r"^(?:台词修改|台词改为|改为|改成|建议改为)\s*[:：]\s*(.+)$")


def is_rewrite(line):
    """「人名：台词」 is a rewrite; 「这个程序不是这样走的：…」「原因：…」 open with a label, not a name."""
    match = DIALOGUE_LINE_RE.match(line)
    return bool(match) and not REVISION_LABEL.search(line.split("：", 1)[0].split(":", 1)[0])


def notes_from_sections(text, source):
    """`### ` 分节的批注记录：每节一条。"""
    notes = []
    parts = SECTION_RE.split(text)
    for i in range(1, len(parts) - 1, 2):
        heading, body = parts[i].strip(), parts[i + 1]
        body = re.split(r"^#{1,6}\s", body, maxsplit=1, flags=re.M)[0]  # a section ends at the next heading of any level
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        quoted = "\n".join(l.lstrip(">").strip() for l in lines if l.startswith(">")) or None
        said = [re.sub(r"^[-*]\s+", "", l) for l in lines if not l.startswith(">") and not LABEL_LINE_RE.match(l) and not l.startswith("#")]
        if not said and not quoted:
            continue
        suggestion = next((l for l in said if is_rewrite(l)), None)
        note_text = "\n".join(l for l in said if l is not suggestion) or None
        prefixed = next((REWRITE_PREFIX.match(l) for l in said if REWRITE_PREFIX.match(l)), None)
        if suggestion is None and prefixed:  # 「台词修改：……」: the rest of the line is the rewrite
            suggestion = prefixed.group(1).strip()
        notes.append(make_note(source, quoted, note_text, suggestion, ref=heading))
    return notes


def section_of(text, title):
    """The body under the first heading (any level) whose text starts with title, up to the next heading of that level."""
    match = re.search(rf"^(#{{1,6}})\s+{re.escape(title)}.*$", text, re.M)
    if not match:
        raise InputError(f"md 里没有以 {title!r} 开头的标题")
    level = len(match.group(1))
    rest = text[match.end():]
    end = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return rest[:end.start()] if end else rest


def notes_from_table(text, source):
    """表格每行一条：含「→」的那一格是原 → 改，「类别」列记 category。"""
    rows = [TABLE_ROW_RE.match(l.strip()) for l in text.splitlines()]
    rows = [[c.strip() for c in m.group(1).split("|")] for m in rows if m]
    if len(rows) < 2:
        return []
    header, notes = rows[0], []
    category_at = next((i for i, h in enumerate(header) if "类别" in h), None)
    for index, cells in enumerate(rows[2:], start=1):
        change = next((CHANGE_RE.match(c) for c in cells if "→" in c), None)
        if not change:
            continue
        where = cells[0]
        category = cells[category_at] if category_at is not None and category_at < len(cells) else None
        note = make_note(source, change.group("before"), f"{where}：改动（{category or '未分类'}）；{cells[-1]}",
                         change.group("after"), explicit_level="scene_structure" if category and "场头" in category else "line",
                         category=category, ref=f"row[{index}] {where}")
        note["levelBasis"] = "table"
        notes.append(note)
    return notes


def notes_from_answers(doc, source):
    """追问单回答记录里落在程序或现实规则上的 notHolds：程序依赖（D-…-p…、L-proc-…）或 defectKind contradicts_reality。"""
    notes = []
    for record in doc if isinstance(doc, list) else [doc]:
        for answer in (record.get("answers") or []) if isinstance(record, dict) else []:
            if not isinstance(answer, dict) or answer.get("holds") != "notHolds":
                continue
            lands = str(answer.get("landsOn") or "")
            kinds = answer.get("defectKind") or []
            if PROCEDURE_DEP_RE.search(lands.split()[0] if lands else ""):
                level = "procedure"
            elif "contradicts_reality" in (kinds if isinstance(kinds, list) else [kinds]):
                level = "fact"
            else:
                continue
            note = make_note(source, lands or None, answer.get("reason"), explicit_level=level,
                             ref=f"{record.get('checkId')}#q{answer.get('q')}")
            note["levelBasis"] = "answer_record"
            notes.append(note)
    return notes


def attach(notes, text_path=None, map_path=None):
    """被批原文定位到正文行，有对照表时再挂到交换。"""
    rows = parse_lines(load_text(text_path)) if text_path else []
    exchanges = {e.get("line"): e.get("exchangeId") for e in (load_json(map_path, "对照表").get("lineToPlan") or [])} if map_path else {}
    for note in notes:
        quote = (note["quotedText"] or "").strip()
        if quote and note["attachesTo"]["lineRef"] is None:
            found = next((r["line"] for r in rows if r["raw"].strip() == quote), None) or \
                next((r["line"] for r in rows if r["content"] and r["content"] in quote), None)
            note["attachesTo"]["lineRef"] = found
        if note["attachesTo"]["lineRef"] in exchanges:
            note["attachesTo"]["planRef"] = exchanges[note["attachesTo"]["lineRef"]]


def mark_conflicts(notes):
    by_anchor = {}
    for note in notes:
        anchor = note["attachesTo"]["lineRef"] or note["quotedText"]
        if anchor and note["humanSuggestion"]:
            by_anchor.setdefault(anchor, []).append(note)
    for group in by_anchor.values():
        if len({n["humanSuggestion"] for n in group}) > 1:
            for note in group:
                note["conflictsWith"] = [n["noteId"] for n in group if n is not note]


def draft_list(notes):
    drafts = [{"kind": kind, "fromNotes": [note["noteId"]], "status": "listed_not_written"}
              for note in notes for kind in ROUTES.get(note["level"], [])]
    groups = {}
    for note in notes:
        if note["category"] or note["level"] in RECURRENCE_LEVELS:
            groups.setdefault(note["category"] or note["level"], []).append(note["noteId"])
    recurring = {key: ids for key, ids in groups.items() if len(ids) >= 2}
    drafts += [{"kind": kind, "fromNotes": ids, "groupedBy": key, "status": "drafted_on_recurrence"}
               for key, ids in recurring.items() for kind in RECURRENCE_DRAFTS]
    return drafts, recurring


def run_feedback_ingest(path, original=None, text=None, plan_text_map=None, author=None, section=None, out=None,
                        target=None, author_role=None, user_names=None) -> dict:
    source_path = Path(path)
    if source_path.is_dir():  # a folder of answer records (a reality review)
        docs = [load_json(str(f), "回答记录") for f in sorted(source_path.glob("*.json"))]
        source = {"kind": "answer_record", "file": source_path.name}
        notes = notes_from_answers([d for d in docs if isinstance(d, dict) and isinstance(d.get("answers"), list)], source)
    elif source_path.suffix == ".json":
        doc = load_json(path, "评论导出或回答记录")
        if isinstance(doc, list) or (isinstance(doc, dict) and isinstance(doc.get("answers"), list)):
            source = {"kind": "answer_record", "file": source_path.name}
            notes = notes_from_answers(doc, source)
        else:
            source = {"kind": "comment", "file": source_path.name}
            notes = notes_from_comments(doc, source)
    elif original:
        source = {"kind": "revised_text", "file": source_path.name}
        notes = notes_from_revision(load_text(path, "改稿"), load_text(original, "原稿"), source)
    else:
        body = load_text(path, "原话记录")
        source = {"kind": "verbatim_record", "file": source_path.name}
        if section:
            body = section_of(body, section)
            source["file"] += f"#{section}"
            notes = notes_from_table(body, source) or notes_from_record(body, source)
        elif SECTION_RE.search(body):
            notes = notes_from_sections(body, source)
        else:
            notes = notes_from_record(body, source)
    users = set(user_names or [])
    for note in notes:
        note["author"] = note["author"] or author
        # wording rulings #1: only the user decides; a writer's or advisor's words are advice. Unknown is not the user.
        note["authorRole"] = note.get("authorRole") or author_role or ("user" if note["author"] and note["author"] in users else "unknown")
    attach(notes, text, plan_text_map)
    mark_conflicts(notes)
    drafts, recurring = draft_list(notes)
    counts = {level: sum(n["level"] == level for n in notes) for level in LEVELS}
    result = {"ok": True, "passed": None, "writerNotes": notes, "levelCounts": counts, "derivedDrafts": drafts,
              "recurringGroups": recurring, "unrouted": [n["noteId"] for n in notes if n["level"] == "unknown"],
              "note": "不给 --out 时只列派生物草稿清单，不写文件。level 推断 lexicon 的信号质量低"}
    if out:
        derived = derive(notes, recurring)
        written = write_derived(out, notes, derived, target)
        result.update(out=str(out), written=written,
                      derivedCounts={kind: len(rows) for kind, rows in derived.items()},
                      note="派生物写进 --out，每条带 fromNotes 与 status: drafted；--purge <noteId> 可按 id 清除")
    return result


FILES = {"negative": "negatives.jsonl", "humanPositive": "human-positives.jsonl", "contrastPair": "contrast-pairs.jsonl",
         "conventionDraft": "conventions.jsonl", "questionDraft": "questions.jsonl", "ledgerProposal": "ledger-proposals.jsonl",
         "k1Draft": "k1-drafts.jsonl"}


def _derived_row(kind, note):
    base = {"id": f"{kind[:3].upper()}-{note['noteId'][3:]}", "kind": kind, "fromNotes": [note["noteId"]], "status": "drafted",
            "scope": {"level": "project"}}
    if kind == "negative":
        return {**base, "quotedText": note["quotedText"], "why": note["humanNote"], "level": note["level"],
                "attachesTo": note["attachesTo"]}
    if kind == "humanPositive":
        return {**base, "text": note["humanSuggestion"], "verbatimFrom": note["source"], "replaces": note["quotedText"]}
    if kind == "contrastPair":
        return {"schemaVersion": "drama-studio/contrast-pair/v0", "pairId": base["id"], **base,
                "positive": {"humanText": note["humanSuggestion"]}, "negative": {"summary": note["quotedText"],
                                                                                  "location": note["attachesTo"]},
                "whyNotHere": note["humanNote"] or "编剧改了这一处", "provenance": {"negativeFrom": "writer_note", "humanNote": note["noteId"]}}
    if kind == "conventionDraft":
        return {**base, "text": note["humanNote"], "category": note["category"] or note["level"]}
    if kind == "ledgerProposal":
        return {**base, "proposal": "ledger_revision", "landsOn": note["quotedText"], "claim": note["humanNote"],
                "action": "交 C3b：按这条意见核对并改底账条目（新修订），改不改由 C3b 定"}
    if kind == "k1Draft":
        return {**base, "knowledgeType": "K1", "problem": note["humanNote"], "about": note["quotedText"],
                "evidence": {"sources": [{"sourceId": note["noteId"], "location": note["source"]}], "nature": "writer_note"},
                "action": "交检索代理：查出处后写成正式 K1 卡；没查到写空卡"}
    return {**base}


def derive(notes, recurring):
    derived = {kind: [] for kind in FILES}
    derived["decision"] = []
    by_id = {n["noteId"]: n for n in notes}
    for note in notes:
        for kind in ROUTES.get(note["level"], []):
            if kind in ("humanPositive", "contrastPair") and not note["humanSuggestion"]:
                continue
            if kind == "decision":
                derived["decision"].append(note)
            elif kind == "conventionDraft" and not note["humanNote"]:
                continue
            else:
                derived[kind].append(_derived_row(kind, note))
    for key, ids in recurring.items():
        members = [by_id[i] for i in ids]
        text = "；".join(dict.fromkeys(m["humanNote"] for m in members if m["humanNote"]))
        if not text:
            continue
        for kind in RECURRENCE_DRAFTS:
            row = {"id": f"{kind[:3].upper()}-R-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:8]}", "kind": kind,
                   "fromNotes": ids, "status": "drafted", "scope": {"level": "project"}, "groupedBy": key,
                   "text" if kind == "conventionDraft" else "question": text if kind == "conventionDraft" else f"（{key}）{text}？"}
            derived[kind].append(row)
    return derived


def _decision_queue(notes):
    """A user's words are a decision; anyone else's are a pending entry whose default is to do as they said."""
    entries = []
    for n in notes:
        if not n["humanNote"]:
            continue
        entry = {"id": f"DQ-{n['noteId'][3:]}", "kind": "other", "question": n["quotedText"] or n["humanNote"],
                 "options": [{"optionId": "as_said", "text": n["humanNote"]}], "default": "as_said", "affects": [],
                 "fromNotes": [n["noteId"]]}
        if n.get("authorRole") == "user":  # humanWords: the user's own words, on a decided entry only
            entry.update(defaultReason="用户原话已定", status="decided", decision="as_said", decidedBy=n["author"] or "user",
                         humanWords=n["humanNote"])
        else:  # advice: the words it rests on are basisWords, never humanWords
            role = n.get("authorRole") if n.get("authorRole") in ("writer", "advisor") else "unknown"
            who = {"writer": "编剧", "advisor": "顾问"}.get(role, "来源不明的")
            entry.update(defaultReason=f"{who}意见（{n['author'] or '未署名'}）；用户没定前按这条意见办", status="pending",
                         decision=None, decidedBy=None, basisWords=n["humanNote"], basisBy=n["author"], basisRole=role)
        entries.append(entry)
    return {"schemaVersion": "drama-studio/decision-queue/v0", "entries": entries}


def bump_revision(revision):
    match = re.match(r"^(.*?)(\d+)$", revision)
    return f"{match.group(1)}{int(match.group(2)) + 1}" if match else f"{revision}.1"


def bumped_target(target, conventions):
    doc = json.loads(json.dumps(target))
    previous = doc["revision"]
    doc["revision"] = bump_revision(previous)
    added = []
    for row in conventions:
        cid = f"C-{row['id']}"
        doc["conventions"].append({"id": cid, "text": row["text"], "status": "drafted", "sourceNotes": row["fromNotes"]})
        added.append(cid)
    doc["changelog"] = [*(doc.get("changelog") or []),
                        {"revision": doc["revision"], "from": previous, "by": "feedback-ingest", "change": f"新增约定草稿 {', '.join(added)}",
                         "noteIds": sorted({i for row in conventions for i in row["fromNotes"]})}]
    return doc


def write_derived(out, notes, derived, target=None):
    folder = Path(out)
    if folder.exists() and any(folder.iterdir()):
        raise InputError(f"--out {out} 不是空目录；派生物不覆盖，换一个目录或先 --purge")
    folder.mkdir(parents=True, exist_ok=True)
    written = {}

    def jsonl(name, rows):
        (folder / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        written[name] = len(rows)

    jsonl("writer-notes.jsonl", notes)
    for kind, name in FILES.items():
        if derived[kind]:
            jsonl(name, derived[kind])
    if derived["decision"]:
        queue = _decision_queue(derived["decision"])
        (folder / "decisions.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written["decisions.json"] = len(queue["entries"])
    if target and derived["conventionDraft"]:
        doc = bumped_target(load_json(target, "台词目标"), derived["conventionDraft"])
        name = f"dialogue-target.{doc['revision']}.json"
        (folder / name).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written[name] = 1
    return written


def purge(out, note):
    """Remove every derivative note `note` produced, from every file in --out (the notes file keeps the note)."""
    folder, removed = Path(out), {}
    if not folder.is_dir():
        raise InputError(f"--out {out} 不是目录")
    for path in sorted(folder.glob("*.jsonl")):
        if path.name == "writer-notes.jsonl":
            continue
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        kept = [r for r in rows if note not in (r.get("fromNotes") or [])]
        if len(kept) != len(rows):
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
            removed[path.name] = len(rows) - len(kept)
    queue = folder / "decisions.json"
    if queue.is_file():
        doc = json.loads(queue.read_text(encoding="utf-8"))
        kept = [e for e in doc["entries"] if note not in (e.get("fromNotes") or [])]
        if len(kept) != len(doc["entries"]):
            removed["decisions.json"] = len(doc["entries"]) - len(kept)
            queue.write_text(json.dumps(dict(doc, entries=kept), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "passed": None, "purged": note, "removed": removed}


def _main(argv):
    parser = argparse.ArgumentParser(description="人工反馈 → writer-note，按 level 路由；给 --out 时写派生物")
    parser.add_argument("input", nargs="?", help="飞书评论 JSON、回答记录 JSON、改稿 md（配 --original）或原话记录 md／txt")
    parser.add_argument("--original", help="改稿对应的原稿，逐行比对对白")
    parser.add_argument("--text", help="被批注的正文：把被批原文定位到行号")
    parser.add_argument("--plan-text-map", help="对照表：行号挂到交换")
    parser.add_argument("--author", help="原话记录或改稿的作者")
    parser.add_argument("--author-role", choices=AUTHOR_ROLES, help="作者是谁：user（用户本人）、writer（编剧）、advisor（顾问）；"
                        "只有 user 的决定类意见写 decided，其余写 pending 带默认。评论项自带 authorRole 时以它为准")
    parser.add_argument("--user-name", action="append", default=[], help="用户的名字（可多次）：作者是这个名字的 note 算用户")
    parser.add_argument("--section", help="md 只读这一节（标题开头的文字，如「二、」）；节里的表格每行一条")
    parser.add_argument("--out", help="派生物写到这个空目录（D6-4 全路由）；不给则只列草稿清单")
    parser.add_argument("--target", help="台词目标：起草了约定时另写升版的台词目标到 --out")
    parser.add_argument("--purge", help="note id：从 --out 清掉它派生的全部条目（不读 input）")
    args = parser.parse_args(argv)
    if args.purge:
        if not args.out:
            raise InputError("--purge 要和 --out 一起给")
        return purge(args.out, args.purge), 0
    if not args.input:
        raise InputError("要给 input（或 --purge <noteId> --out <目录>）")
    result = run_feedback_ingest(args.input, args.original, args.text, args.plan_text_map, args.author, args.section,
                                 args.out, args.target, args.author_role, args.user_name)
    command = [abspath(args.input)]
    for flag, value in (("--original", args.original), ("--text", args.text), ("--plan-text-map", args.plan_text_map)):
        if value:
            command += [flag, abspath(value)]
    for flag, value in (("--author", args.author), ("--author-role", args.author_role), ("--section", args.section)):
        if value:
            command += [flag, value]
    for name in args.user_name:
        command += ["--user-name", name]
    for flag, value in (("--out", args.out), ("--target", args.target)):
        if value:
            command += [flag, abspath(value)]
    result["reproduceCommand"] = reproduce_command("feedback_ingest", command)
    return result, 0


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
