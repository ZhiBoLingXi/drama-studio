"""feedback-ingest（骨架）：人工反馈 → writer-note，按 level 路由，只列派生物草稿清单。

输入三种（实施计划 §2.2 #9；台词方案 §9.2、§9.3）：
- 飞书评论导出 JSON（`<comment><quote>…</quote><msg user=…>…</msg></comment>`），或通用
  `{"comments": [{commentId, quote, author, text | messages[], level?, category?}]}`；
- 改稿 md：给 `--original` 时逐行比对对白，改句记句级、增删对白记来回级；
- 原话记录 md／txt：空行分段，段内 `>` 开头的行是被批原文，其余是原话；可写 `[level: …]` 标层级。

level 推断：明写的为准；改稿按改动类型；批注按一个小词表推（`levelBasis: lexicon`，信号质量低），
推不出写 `unknown`，不找人问。每条 writer-note `scope.level: project`。同类（同 level 或同 category）
≥2 次的，在草稿清单里标起草约定或新问；同一落点给了不同改法的互标 `conflictsWith`。
本命令不写任何文件：实际派生（反例交换、对照对、约定、K1 草稿、底账修订提案、决定）在 D6-4。
退出码：0；1 输入错误。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.text_lines import (DIALOGUE_LINE_RE, InputError, abspath, load_json, load_text, parse_lines,
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
    if suggestion:
        return "line", "suggestion_is_a_line"
    for level, words in LEXICON:
        if any(word in (human_note or "") for word in words):
            return level, "lexicon"
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
        notes.append(make_note(source, item.get("quote"), note_text, item.get("suggestion") or suggestion,
                               item.get("author"), item.get("level"), item.get("category"), item.get("commentId") or f"comments[{i}]"))
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


def run_feedback_ingest(path, original=None, text=None, plan_text_map=None, author=None) -> dict:
    source_path = Path(path)
    if source_path.suffix == ".json":
        source = {"kind": "comment", "file": source_path.name}
        notes = notes_from_comments(load_json(path, "评论导出"), source)
    elif original:
        source = {"kind": "revised_text", "file": source_path.name}
        notes = notes_from_revision(load_text(path, "改稿"), load_text(original, "原稿"), source)
    else:
        source = {"kind": "verbatim_record", "file": source_path.name}
        notes = notes_from_record(load_text(path, "原话记录"), source)
    for note in notes:
        note["author"] = note["author"] or author
    attach(notes, text, plan_text_map)
    mark_conflicts(notes)
    drafts, recurring = draft_list(notes)
    counts = {level: sum(n["level"] == level for n in notes) for level in LEVELS}
    return {"ok": True, "passed": None, "writerNotes": notes, "levelCounts": counts, "derivedDrafts": drafts,
            "recurringGroups": recurring, "unrouted": [n["noteId"] for n in notes if n["level"] == "unknown"],
            "note": "只列派生物草稿清单，不写任何文件；派生在 D6-4。level 推断 lexicon 的信号质量低"}


def _main(argv):
    parser = argparse.ArgumentParser(description="人工反馈 → writer-note，按 level 路由，只列派生物草稿；不写文件")
    parser.add_argument("input", help="飞书评论 JSON、改稿 md（配 --original）或原话记录 md／txt")
    parser.add_argument("--original", help="改稿对应的原稿，逐行比对对白")
    parser.add_argument("--text", help="被批注的正文：把被批原文定位到行号")
    parser.add_argument("--plan-text-map", help="对照表：行号挂到交换")
    parser.add_argument("--author", help="原话记录或改稿的作者")
    args = parser.parse_args(argv)
    result = run_feedback_ingest(args.input, args.original, args.text, args.plan_text_map, args.author)
    command = [abspath(args.input)]
    for flag, value in (("--original", args.original), ("--text", args.text), ("--plan-text-map", args.plan_text_map)):
        if value:
            command += [flag, abspath(value)]
    if args.author:
        command += ["--author", args.author]
    result["reproduceCommand"] = reproduce_command("feedback_ingest", command)
    return result, 0


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
