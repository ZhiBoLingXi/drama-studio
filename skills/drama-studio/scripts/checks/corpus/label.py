"""`corpus label` -- the S part only (vocabulary + format checks on a labels file, plus the
`speakerAttributionSuspect` candidate flag). The M part -- writing `about` / `situation` /
`walkthrough` for a candidate segment -- is a model job and stays out of scope here; D6-4 adds
the double-run agreement pass (`corpus/LABEL_GUIDE.md`, stage-a-report.md §4, §8.4).

Input is a labels JSONL file in the shape `corpus/LABEL_GUIDE.md` documents (one compact label
per line: `exchangeId`, `templateId`, `episodeIndex`, `lineStart`, `lineEnd`, `about`,
`situation{...}`, `walkthrough`, `quality{transcript,label,note}`). Field names follow the real
阶段 A labels (`corpus/labels/*.jsonl`), not the architecture doc's `speaker`/`listener` spelling
of `emotion` (the real files use `a`/`b`) -- see shared brief rule #3.

Checks:
  - format: required keys present and typed, `lineStart <= lineEnd`, no duplicate `exchangeId`
    within the file. A format problem is a real defect -> contributes to exit code 2.
  - vocabulary: situation fields checked against the open word lists in `corpus/LABEL_GUIDE.md`
    §词表. The vocabulary is explicitly open ("用了新值要在 note 里说一句"), so an out-of-list
    value is only a defect when `quality.note` gives no explanation -- this only ever *reports*,
    never blocks (architecture doc §3.1: a diagnostic signal is a pointer, not a verdict).
  - speakerAttributionSuspect: a line is flagged when its time range overlaps more than one
    Storyline paragraph and some paragraph names a different known speaker without naming the
    line's attributed speaker (stage-a-report.md §8 #1 -- this is exactly how the real CKXR
    EP1 misattribution shows up: the merged line's tail oversteps into the next paragraph,
    which only names the other character). Requires the matching `corpus/raw/<templateId>/
    ep-<NNN>.json` to read Storyline + Transcript from; without it the field is `null`
    (`not_evaluable`), never guessed.

Exit codes: 0 clean; 1 unreadable/malformed input; 2 a format defect was found (vocabulary
warnings alone never raise this).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import transcript as T  # noqa: E402

FUNCTION_VOCAB = {
    "交代", "求助", "施压", "对质", "安抚", "撒谎", "拒绝", "认错", "下命令", "讨价",
    "相认", "告别", "试探", "哄", "报信", "打岔", "夸赞", "问清", "辩解", "商量",
    "示好", "宣告", "训斥", "请求",
}
RELATION_VOCAB = {
    "大人对孩子", "孩子对大人", "孩子对孩子", "师徒", "上对下", "亲人-父母子女",
    "亲人-夫妻", "亲人-兄妹", "对手", "办事人员对群众", "群众对办事人员", "陌生人",
    "恋人", "同伙", "商家对顾客", "顾客对商家", "同事",
}
POWER_DIRECTION_VOCAB = {"down", "up", "level"}
INFO_MODE_VOCAB = {
    "问答", "追问链", "误会纠正", "被打断补全", "第三方替观众问", "宣告被接",
    "重复确认", "自言自语", "转述", "以物证说",
}
EMOTION_VOCAB = {
    "平静", "急", "怒", "怕", "羞", "哄", "疲", "撒娇", "强撑", "哀求", "防备",
    "讥讽", "得意", "委屈", "愧", "喜", "疑",
}
REQUIRED_KEYS = ("exchangeId", "templateId", "episodeIndex", "lineStart", "lineEnd",
                 "about", "situation", "walkthrough", "quality")
REQUIRED_SITUATION_KEYS = ("speakerWants", "listenerKnows", "relation", "powerDirection",
                           "addresseeIsChild", "emotion", "function", "infoMode", "audienceLearns")


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw or raw.startswith("//"):
                continue
            try:
                rows.append((ln, json.loads(raw)))
            except json.JSONDecodeError as error:
                raise ValueError(f"line {ln}: invalid JSON ({error})") from error
    return rows


def _format_issues(ln, row):
    issues = []
    for key in REQUIRED_KEYS:
        if key not in row:
            issues.append({"code": "missing_field", "field": key, "line": ln})
    if "lineStart" in row and "lineEnd" in row:
        a, b = row.get("lineStart"), row.get("lineEnd")
        if not isinstance(a, int) or isinstance(a, bool) or not isinstance(b, int) or isinstance(b, bool):
            issues.append({"code": "line_range_not_int", "line": ln})
        elif a < 0 or b < a:
            issues.append({"code": "line_range_invalid", "line": ln, "lineStart": a, "lineEnd": b})
    if "episodeIndex" in row:
        idx = row["episodeIndex"]
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 1:
            issues.append({"code": "episode_index_invalid", "line": ln})
    situation = row.get("situation")
    if "situation" in row and not isinstance(situation, dict):
        issues.append({"code": "situation_not_object", "line": ln})
    elif isinstance(situation, dict):
        for key in REQUIRED_SITUATION_KEYS:
            if key not in situation:
                issues.append({"code": "missing_situation_field", "field": key, "line": ln})
    quality = row.get("quality")
    if "quality" in row and not isinstance(quality, dict):
        issues.append({"code": "quality_not_object", "line": ln})
    return issues


def _vocab_warnings(ln, row):
    warnings = []
    situation = row.get("situation")
    if not isinstance(situation, dict):
        return warnings
    note = ((row.get("quality") or {}).get("note") or "").strip() if isinstance(row.get("quality"), dict) else ""
    explained = bool(note)

    def check(label, value, vocab):
        if value is None:
            return
        if value not in vocab and not explained:
            warnings.append({"code": "out_of_vocab", "field": label, "value": value, "line": ln})

    relation = situation.get("relation")
    check("situation.relation", relation, RELATION_VOCAB)
    check("situation.powerDirection", situation.get("powerDirection"), POWER_DIRECTION_VOCAB)
    func = situation.get("function") or {}
    if isinstance(func, dict):
        check("situation.function.primary", func.get("primary"), FUNCTION_VOCAB)
        if func.get("secondary") is not None:
            check("situation.function.secondary", func.get("secondary"), FUNCTION_VOCAB)
    info_modes = situation.get("infoMode") or []
    if isinstance(info_modes, list):
        for value in info_modes:
            check("situation.infoMode[]", value, INFO_MODE_VOCAB)
    emotion = situation.get("emotion") or {}
    if isinstance(emotion, dict):
        # Real labels (corpus/labels/*.jsonl) key emotion a/b, not speaker/listener.
        for key in ("a", "b"):
            if key in emotion:
                check(f"situation.emotion.{key}", emotion.get(key), EMOTION_VOCAB)
    return warnings


def _load_raw_lines(raw_dir, template_id, episode_index):
    path = os.path.join(raw_dir, template_id, f"ep-{episode_index:03d}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        rec = json.load(f)
    _, lines, secs = T.parse_transcript(rec["rawMd"])
    return lines, secs


def speaker_attribution_suspect(lines, secs, line_start, line_end):
    """Candidate flag only -- S cross-checks Storyline text, M/human confirms (docstring above)."""
    paragraphs = T.storyline_paragraphs(secs)
    if not paragraphs:
        return None, ["no_storyline_section"]
    known_speakers = sorted({l["speaker"] for l in lines if not T.is_monologue(l)})
    reasons = []
    suspect = False
    for i in range(line_start, min(line_end, len(lines) - 1) + 1):
        if i < 0 or i >= len(lines):
            continue
        line = lines[i]
        if T.is_monologue(line):
            continue
        speaker = line["speaker"]
        overlapping = T.overlapping_paragraphs(paragraphs, line["t0"], line["t1"])
        if len(overlapping) < 2:
            continue
        for para in overlapping:
            names_present = [name for name in known_speakers if name and name in para["text"]]
            if speaker not in names_present:
                others = [name for name in names_present if name != speaker]
                if others:
                    suspect = True
                    reasons.append({
                        "lineIndex": i, "speaker": speaker,
                        "paragraphStartMs": para["startMs"], "paragraphEndMs": para["endMs"],
                        "otherNamesInParagraph": others,
                    })
    return suspect, reasons


def run_label(label_path, raw_dir=None):
    rows = _read_jsonl(label_path)
    seen_ids = {}
    out_rows = []
    all_format_issues = []
    for ln, row in rows:
        issues = _format_issues(ln, row)
        exchange_id = row.get("exchangeId")
        if isinstance(exchange_id, str):
            if exchange_id in seen_ids:
                issues.append({"code": "duplicate_exchange_id", "exchangeId": exchange_id,
                               "line": ln, "firstLine": seen_ids[exchange_id]})
            else:
                seen_ids[exchange_id] = ln
        warnings = _vocab_warnings(ln, row)
        suspect, suspect_reasons = None, ["not_evaluable_no_raw_dir"]
        if raw_dir and not issues and isinstance(row.get("templateId"), str) and isinstance(row.get("episodeIndex"), int):
            loaded = _load_raw_lines(raw_dir, row["templateId"], row["episodeIndex"])
            if loaded is None:
                suspect, suspect_reasons = None, ["raw_episode_not_found"]
            else:
                lines, secs = loaded
                suspect, suspect_reasons = speaker_attribution_suspect(
                    lines, secs, row.get("lineStart", 0), row.get("lineEnd", -1))
        all_format_issues.extend(issues)
        out_rows.append({
            "exchangeId": exchange_id, "line": ln,
            "formatIssues": issues, "vocabWarnings": warnings,
            "speakerAttributionSuspect": suspect, "speakerAttributionEvidence": suspect_reasons,
        })
    return {
        "ok": True, "labelFile": label_path, "rawDir": raw_dir,
        "rowCount": len(out_rows), "formatIssueCount": len(all_format_issues),
        "vocabWarningCount": sum(len(r["vocabWarnings"]) for r in out_rows),
        "speakerAttributionSuspectCount": sum(1 for r in out_rows if r["speakerAttributionSuspect"]),
        "rows": out_rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label_file")
    parser.add_argument("--raw-dir", help="corpus/raw/ directory to read Storyline/Transcript from for speakerAttributionSuspect; omit to leave it not_evaluable")
    args = parser.parse_args(argv)
    try:
        result = run_label(args.label_file, args.raw_dir)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    result["reproduceCommand"] = "{} -B {} {}".format(
        sys.executable, os.path.abspath(__file__), os.path.abspath(args.label_file),
    ) + (f" --raw-dir {os.path.abspath(args.raw_dir)}" if args.raw_dir else "")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["formatIssueCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
