"""本地字面查重：连续 N 字 shingle 重合率（新稿 vs 对标语料）。

库函数 `run_dup_check(...)` 返回 dict，供 CLI 与 MCP 复用。
查重率定义：新稿的 k 字连续片段中，有多少比例能在对标语料里找到。13 字档最接近"照抄"判定。
只统计汉字（去标点/空格/英数）。
"""
from __future__ import annotations

import glob
import math
import re
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
