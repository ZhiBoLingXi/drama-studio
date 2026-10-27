"""本地字面查重：连续 N 字 shingle 重合率（新稿 vs 对标语料）。

库函数 `run_dup_check(...)` 返回 dict，供 CLI 与 MCP 复用。
查重率定义：新稿的 k 字连续片段中，有多少比例能在对标语料里找到。13 字档最接近"照抄"判定。
只统计汉字（去标点/空格/英数）。
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from typing import Iterable



def _load(paths: Iterable[str]) -> str:
    text = ""
    for p in paths:
        matched = glob.glob(p) or [p]
        for f in matched:
            with open(f, encoding="utf-8") as handle:
                text += handle.read()
    return text


def only_han(t: str) -> str:
    return re.sub(r"[^一-鿿]", "", t)


def _shingles(t: str, k: int) -> set[str]:
    return set(t[i : i + k] for i in range(len(t) - k + 1))


def _rate(new: str, k: int, src_set: set[str]) -> float:
    if len(new) < k:
        return 0.0
    total = len(new) - k + 1
    hit = sum(1 for i in range(total) if new[i : i + k] in src_set)
    return hit / total * 100


def run_dup_check(new_paths, source_paths, ks=(5, 8, 13), threshold=40.0) -> dict:
    if not ks or any(not isinstance(k, int) or isinstance(k, bool) or k <= 0 for k in ks):
        return {"ok": False, "error": "k must contain positive integers"}
    if not math.isfinite(threshold) or not 0 <= threshold <= 100:
        return {"ok": False, "error": "threshold must be between 0 and 100"}
    try:
        src = only_han(_load(source_paths))
        new = only_han(_load(new_paths))
    except (OSError, UnicodeError) as error:
        return {"ok": False, "error": str(error)}
    if not src or not new:
        return {"ok": False, "error": "新稿或对标语料为空，检查路径"}
    if min(len(src), len(new)) < max(ks):
        return {"ok": False, "error": "语料不足以计算所选连续字数，不可据此判为通过"}
    rates = {}
    for k in sorted(set(ks)):
        rates[k] = round(_rate(new, k, _shingles(src, k)), 2)
    gate_k = 13 if 13 in rates else max(rates)
    passed = rates[gate_k] < threshold
    return {
        "ok": True,
        "source_han": len(src),
        "new_han": len(new),
        "rates_percent": {str(k): v for k, v in rates.items()},
        "gate_k": gate_k,
        "threshold_percent": threshold,
        "passed": passed,
        "verdict": (
            f"连续{gate_k}字查重率 {rates[gate_k]:.2f}% < {threshold:.0f}%，字面查重达标。"
            if passed
            else f"连续{gate_k}字查重率 {rates[gate_k]:.2f}% ≥ {threshold:.0f}%，未过闸，需继续换骨。"
        ),
        "note": "字面查重只是硬指标；人名/人设/地名/组织/桥段/剧情走势六维语义查重仍需人审。",
    }


def _source_text(source_paths=(), dialogue_plan=None, corpus_jsonl=None) -> str:
    """命中列表的对标池：普通文件；对话表里 source=corpus 的 maskedLines（装包样本，8 字档）；
    语料库 exchanges.jsonl 的 lines[].text（全库，13 字档）。project／human 样本允许逐字用，不进池。"""
    parts = [_load(source_paths)] if source_paths else []
    if dialogue_plan:
        with open(dialogue_plan, encoding="utf-8") as handle:
            plan = json.load(handle)
        parts += [line for scene in plan.get("scenes") or [] for topic in scene.get("topics") or []
                  for positive in (topic.get("exemplars") or {}).get("positives") or []
                  if positive.get("source") == "corpus" for line in positive.get("maskedLines") or []]
    if corpus_jsonl:
        with open(corpus_jsonl, encoding="utf-8") as handle:
            for raw in handle:
                if raw.strip():
                    parts += [line["text"] for line in json.loads(raw).get("lines") or [] if line.get("text")]
    return "".join(parts)


def run_dup_hits(new_path, k, source_paths=(), dialogue_plan=None, corpus_jsonl=None, verbatim_map=None) -> dict:
    """`--list-hits`：逐条列出新稿 k 字片段在对标池里的命中与行号；plan-text-map 的 verbatimFrom 行另列。
    只报位置，不判过不过闸。"""
    from text_lines import parse_lines

    if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        return {"ok": False, "error": "k must be a positive integer"}
    if not (source_paths or dialogue_plan or corpus_jsonl):
        return {"ok": False, "error": "没给对标池（--source、--source-dialogue-plan 或 --source-corpus-jsonl）"}
    try:
        source = only_han(_source_text(source_paths, dialogue_plan, corpus_jsonl))
        with open(new_path, encoding="utf-8") as handle:
            parsed = parse_lines(handle.read())
        verbatim = set()
        if verbatim_map:
            with open(verbatim_map, encoding="utf-8") as handle:
                verbatim = {v.get("line") for v in json.load(handle).get("verbatimFrom") or [] if v.get("line")}
    except (OSError, UnicodeError, ValueError) as error:
        return {"ok": False, "error": str(error)}
    chars, line_at = [], []
    for row in parsed:
        if row["kind"] in ("action", "dialogue"):
            for char in only_han(row["content"] or ""):
                chars.append(char)
                line_at.append(row["line"])
    new = "".join(chars)
    src_set = _shingles(source, k)
    hits, verbatim_hits, seen = [], [], set()
    for i in range(len(new) - k + 1):
        gram = new[i : i + k]
        if gram in src_set and (gram, line_at[i]) not in seen:
            seen.add((gram, line_at[i]))
            (verbatim_hits if line_at[i] in verbatim else hits).append({"line": line_at[i], "ngram": gram})
    return {"ok": True, "passed": None, "k": k, "newHanChars": len(new), "sourceHanChars": len(source),
            "hitCount": len(hits), "hits": hits, "verbatimHitCount": len(verbatim_hits), "verbatimHits": verbatim_hits,
            "note": "只报命中位置，不判过不过闸；verbatimFrom 行是允许逐字采用的人工句，另列"}


def main(argv=None) -> int:
    """`--list-hits` 的命令行入口（旧的查重率由 drama_tools.py dup-check 出，输出不变）。"""
    import argparse
    import shlex

    parser = argparse.ArgumentParser(description="字面查重逐条命中列表")
    parser.add_argument("--new", required=True)
    parser.add_argument("--list-hits", action="store_true", required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--source", nargs="+", default=[])
    parser.add_argument("--source-dialogue-plan")
    parser.add_argument("--source-corpus-jsonl")
    parser.add_argument("--exclude-verbatim", help="plan-text-map：verbatimFrom 行的命中另列")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    result = run_dup_hits(args.new, args.k, args.source, args.source_dialogue_plan, args.source_corpus_jsonl,
                          args.exclude_verbatim)
    if not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 1
    command = [sys.executable, "-B", os.path.abspath(__file__), "--new", os.path.abspath(args.new), "--list-hits", "--k", str(args.k)]
    if args.source:
        command += ["--source", *map(os.path.abspath, args.source)]
    for flag, value in (("--source-dialogue-plan", args.source_dialogue_plan),
                        ("--source-corpus-jsonl", args.source_corpus_jsonl), ("--exclude-verbatim", args.exclude_verbatim)):
        if value:
            command += [flag, os.path.abspath(value)]
    result["reproduceCommand"] = " ".join(shlex.quote(part) for part in command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def format_report(r: dict) -> str:
    if not r.get("ok"):
        return f"[error] {r.get('error')}"
    lines = [
        f"对标语料: {r['source_han']} 汉字 | 新稿: {r['new_han']} 汉字",
        f"阈值: 连续 {r['gate_k']} 字查重率 < {r['threshold_percent']:.0f}% 视为过闸",
        "-" * 44,
    ]
    for k, v in r["rates_percent"].items():
        flag = ""
        if int(k) == r["gate_k"]:
            flag = "  ✅ 过闸" if r["passed"] else "  ❌ 未过闸"
        lines.append(f"连续 {int(k):>2} 字: 查重率 {v:6.2f}%{flag}")
    lines += ["", "结论: " + r["verdict"], "提醒: " + r["note"]]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
