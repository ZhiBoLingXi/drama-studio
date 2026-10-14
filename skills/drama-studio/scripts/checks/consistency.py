"""consistency：两次独立跑的问题单回答按 (问, 落点) 对齐，列一致／不一致／只一方答到。

落点：对话问题单取 `quoteRef.line`；追问单取 `landsOn` 开头的 id，取不出用原文。
只报不拦——两份都可能错，一致也可能一起错。退出码 0；1 输入错误。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checks.answers_check import landing_key
from checks.text_lines import InputError, abspath, load_json, reproduce_command, run_cli


def index_answers(doc: dict) -> tuple[dict, int]:
    index, duplicates = {}, 0
    for answer in doc.get("answers") or []:
        if not isinstance(answer, dict):
            continue
        key = (answer.get("q"), *landing_key(answer))
        duplicates += key in index
        index.setdefault(key, []).append(answer.get("holds"))
    return index, duplicates


def run_consistency(path_a, path_b) -> dict:
    docs = []
    for path, label in ((path_a, "回答记录 a"), (path_b, "回答记录 b")):
        doc = load_json(path, label)
        if not isinstance(doc, dict) or not isinstance(doc.get("answers"), list):
            raise InputError(f"{label}缺 answers 数组：{path}")
        docs.append(doc)
    (index_a, dup_a), (index_b, dup_b) = index_answers(docs[0]), index_answers(docs[1])
    counts = {"agree": 0, "disagree": 0, "only_a": 0, "only_b": 0}
    rows = []
    for key in sorted(set(index_a) | set(index_b), key=lambda k: (k[0] if isinstance(k[0], int) else -1, k[1], str(k[2]))):
        holds_a, holds_b = index_a.get(key, []), index_b.get(key, [])
        if holds_a and holds_b:
            status = "agree" if sorted(map(str, holds_a)) == sorted(map(str, holds_b)) else "disagree"
        else:
            status = "only_a" if holds_a else "only_b"
        counts[status] += 1
        rows.append({"q": key[0], "alignBy": key[1], "landing": key[2], "status": status,
                     "holdsA": holds_a, "holdsB": holds_b})
    comparable = counts["agree"] + counts["disagree"]
    prompts = [d.get("promptVersion") for d in docs]
    notes = []
    if prompts[0] != prompts[1]:
        notes.append("两份记录的 promptVersion 不同（或有一份缺），比对结果不能当双跑一致性")
    elif not prompts[0]:
        notes.append("两份记录都没有 promptVersion，核不了是不是同一份提示词")
    return {"ok": True, "passed": None, "counts": counts, "comparablePairs": comparable,
            "agreementRate": round(counts["agree"] / comparable, 4) if comparable else None,
            "duplicateAlignKeysA": dup_a, "duplicateAlignKeysB": dup_b, "rows": rows, "notes": notes,
            "note": "只报不拦：两份都可能错，一致也可能一起错；不判对错"}


def _main(argv):
    parser = argparse.ArgumentParser(description="两次独立跑的问题单回答按 (问, 落点) 对齐，核一致性")
    parser.add_argument("a")
    parser.add_argument("b")
    args = parser.parse_args(argv)
    result = run_consistency(args.a, args.b)
    result["reproduceCommand"] = reproduce_command("consistency", [abspath(args.a), abspath(args.b)])
    return result, 0


def main(argv=None) -> int:
    return run_cli(_main, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
