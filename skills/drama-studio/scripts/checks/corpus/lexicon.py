"""`corpus lexicon` -- scan for genre-mismatched vocabulary bleeding into the project's own
genre (dialogue structure architecture doc §7.4, "怎样防止把仙侠腔学进现实题材"; ported from
the阶段 A ad-hoc script `genre_lexicon_scan.py`, generalized to take the project's genre as an
argument instead of a hardcoded constant).

The architecture's own wording: "对两种题材的语料做词频对照，在 A 题材高频、B 题材近零的词进
B 题材项目的禁词表……脚本对正文扫禁词，命中报 GENRE_LEAK，这是「有没有串腔」的事实核对" --
GENRE_LEAK is a fact check, never a verdict (same "数字不当裁判" / "只报不拦" invariant as the
other diagnostic commands here). The word list is a data file
(`schemas/data/genre-lexicon.json`), not a rule, and is marked `source: assumed` until a real
cross-genre corpus lets it be recomputed from frequency counts (stage-a-report.md §9 flags the
same gap: this project's corpus only covered one genre).

Two input modes, picked by `--mode` or guessed from the file extension:
  - `script` (default for .md/.txt): scans 正文/集纲 lines that look like action (`△...`) or
    dialogue (`姓名：...`) -- the same two line kinds `episode_check.py` already recognizes in
    this skill, kept intentionally simple here rather than importing that module's full line
    grammar.
  - `corpus` (default for .jsonl): scans a dialogue-exchange file's `lines[].text` and `about`/
    `walkthrough`, for checking a sample before it goes into a context pack (§7.5).

Exit codes: 0 always (GENRE_LEAK is only ever reported); 1 input/lexicon unreadable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LEXICON = os.path.join(HERE, "..", "..", "..", "schemas", "data", "genre-lexicon.json")
ACTION_RE = re.compile(r"^\s*△\s*(.+)$")
DIALOGUE_RE = re.compile(r"^([^△#【（(\s][^：:]{0,11})(?:（[^）]*）|\([^)]*\))?\s*[：:]\s*(.+)$")


def _load_json(path, label):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _script_lines(text):
    rows = []
    for i, raw in enumerate(text.splitlines(), start=1):
        m = ACTION_RE.match(raw)
        if m:
            rows.append((i, raw, m.group(1)))
            continue
        m = DIALOGUE_RE.match(raw)
        if m:
            rows.append((i, raw, m.group(2)))
    return rows


def _corpus_lines(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            record = json.loads(raw)
            for field in ("about", "walkthrough"):
                if record.get(field):
                    rows.append((ln, record.get(field), record.get(field)))
            for line in record.get("lines", []) or []:
                if line.get("text"):
                    rows.append((ln, line["text"], line["text"]))
    return rows


def scan(rows, lexicon, project_genre):
    hits = []
    for lst in lexicon.get("lists", []) or []:
        from_genre = lst.get("fromGenre")
        if from_genre == project_genre:
            continue
        for word in lst.get("words", []) or []:
            for line_no, raw, content in rows:
                if word in content:
                    hits.append({
                        "code": "GENRE_LEAK", "line": line_no, "word": word,
                        "fromGenre": from_genre, "toGenre": project_genre,
                        "wordListSource": lst.get("source"), "lineText": raw,
                    })
    return hits


def run_lexicon(input_path, project_genre, lexicon_path=DEFAULT_LEXICON, mode=None):
    mode = mode or ("corpus" if input_path.endswith(".jsonl") else "script")
    lexicon = _load_json(lexicon_path, "词表")
    if mode == "corpus":
        rows = _corpus_lines(input_path)
    else:
        with open(input_path, encoding="utf-8") as f:
            rows = _script_lines(f.read())
    hits = scan(rows, lexicon, project_genre)
    return {
        "ok": True, "inputFile": input_path, "mode": mode, "lexicon": lexicon_path,
        "lexiconNote": lexicon.get("note"), "projectGenre": project_genre,
        "hitCount": len(hits), "hits": hits,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file")
    parser.add_argument("--project-genre", required=True, help="the project's own genre, e.g. 现实 -- lists whose fromGenre equals this are skipped")
    parser.add_argument("--lexicon", default=DEFAULT_LEXICON)
    parser.add_argument("--mode", choices=["script", "corpus"])
    args = parser.parse_args(argv)
    try:
        result = run_lexicon(args.input_file, args.project_genre, args.lexicon, args.mode)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    result["reproduceCommand"] = "{} -B {} {} --project-genre {} --lexicon {}".format(
        sys.executable, os.path.abspath(__file__), os.path.abspath(args.input_file),
        args.project_genre, os.path.abspath(args.lexicon),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
