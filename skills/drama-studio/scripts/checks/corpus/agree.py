"""`corpus agree` -- the S part of the label/walkthrough double run (plan §4.5; stage-a-report.md §4, §8.4).

Two labels of the same exchange are compared after the vocabulary is converged (`schemas/data/corpus-label-vocabulary.json`):
function words in one synonym group count as the same; two relations agree when they are equal or one is the other's
parent (the more specific one is kept); infoMode agrees when the two sets overlap. An exchange whose function or
relation still differs, or whose infoMode sets do not overlap, is labelConfidence `low`; `corpus filter` keeps low
labels out of its pass list, so they do not reach a search result.

Input: an exchanges/labels JSONL whose rows carry both runs in `labelRuns {run1, run2}` (the阶段 A shape), or two
files joined by exchangeId (`--second`). With `--out`, a copy of the first file is written with `labelConfidence`,
`labelAgreement` and, for low rows, `quality.label: low`; the input is never changed. Writing the labels is the M part
(a model's job) and stays out of this command.

In a studio corpus folder (`<studio root>/corpus/`, beside STUDIO.md; plan §8 #1) every row must be scope.level
studio with origin.kind mali_story_template, else input error; --out may only go there from studio input.

Exit codes: 0 compared (disagreement is the answer, not a failure); 1 input error or --out would overwrite a file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from studio import studio_corpus_root, studio_row_problem  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "schemas", "data", "corpus-label-vocabulary.json")


def _rows(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for n, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError as error:
                    raise ValueError(f"{path} 第 {n} 行不是 JSON：{error}") from None
    return rows


def vocabulary(path=DATA):
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    groups = {member: g["group"] for g in doc["functionGroups"] for member in g["members"]}
    return groups, doc["relationParents"]


def run_of(row):
    """function, relation, infoMode of one labelling (a labelRuns run or a label row's situation)."""
    situation = row.get("situation") if isinstance(row.get("situation"), dict) else row
    function = situation.get("function")
    function = function.get("primary") if isinstance(function, dict) else function
    return function, situation.get("relation"), set(situation.get("infoMode") or [])


def compare(a, b, groups, parents):
    fa, ra, ia = a
    fb, rb, ib = b
    function_same = fa == fb or (fa in groups and groups.get(fa) == groups.get(fb))
    if ra == rb:
        relation_same, relation = True, ra
    elif rb in parents.get(ra, []):
        relation_same, relation = True, ra
    elif ra in parents.get(rb, []):
        relation_same, relation = True, rb
    else:
        relation_same, relation = False, None
    info_overlap = bool(ia & ib)
    agreement = {"function": function_same, "functionRaw": fa == fb, "relation": relation_same, "relationRaw": ra == rb,
                 "infoModeOverlap": info_overlap}
    converged = {"function": groups.get(fa, fa) if function_same else None, "relation": relation,
                 "infoMode": sorted(ia & ib) if info_overlap else None}
    return agreement, converged, ("high" if function_same and relation_same and info_overlap else "low")


def _studio_check(path, rows):
    """A labels file in the studio corpus holds mali-story template data only (plan §8 #1)."""
    if studio_corpus_root(path) is None:
        return "project"
    bad = [r.get("exchangeId") if isinstance(r, dict) else None for r in rows if studio_row_problem(r)]
    if bad:
        raise ValueError(f"{path} 在工作室语料目录里，但有 {len(bad)} 行不是 scope.level: studio 且 origin.kind: mali_story_template："
                         f"{bad[:5]}；项目句子不进工作室语料")
    return "studio"


def run_agree(path, second=None, vocab_path=DATA, out=None):
    groups, parents = vocabulary(vocab_path)
    rows = _rows(path)
    scope = _studio_check(path, rows)
    second_rows = _rows(second) if second else []
    if second:
        _studio_check(second, second_rows)
    if out and studio_corpus_root(out) is not None and scope != "studio":
        raise ValueError(f"--out {out} 在工作室语料目录里，输入却不是工作室语料；项目标注不写进工作室语料")
    others = {r.get("exchangeId"): r for r in second_rows} if second else {}
    records, unpaired = [], []
    for row in rows:
        runs = row.get("labelRuns") if isinstance(row.get("labelRuns"), dict) else None
        if second:
            other = others.get(row.get("exchangeId"))
            pair = (run_of(row), run_of(other)) if other else None
        elif runs and runs.get("run1") and runs.get("run2"):
            pair = (run_of(runs["run1"]), run_of(runs["run2"]))
        else:
            pair = None
        if pair is None:
            unpaired.append(row.get("exchangeId"))
            continue
        agreement, converged, confidence = compare(*pair, groups, parents)
        records.append({"exchangeId": row.get("exchangeId"), "agreement": agreement, "converged": converged,
                        "labelConfidence": confidence})
    n = len(records)
    rate = lambda key: round(sum(r["agreement"][key] for r in records) / n, 3) if n else None  # noqa: E731
    result = {"ok": True, "input": path, "second": second, "scope": scope, "compared": n, "notDoubleRun": len(unpaired),
              "rates": {k: rate(k) for k in ("functionRaw", "function", "relationRaw", "relation", "infoModeOverlap")},
              "low": [r["exchangeId"] for r in records if r["labelConfidence"] == "low"],
              "records": records,
              "note": "收敛规则见 schemas/data/corpus-label-vocabulary.json（source: assumed）；low 的不进 corpus filter 的通过名单"}
    if out:
        if os.path.exists(out):
            raise ValueError(f"{out} 已存在；不覆盖")
        by_id = {r["exchangeId"]: r for r in records}
        with open(out, "w", encoding="utf-8") as handle:
            for row in rows:
                record = by_id.get(row.get("exchangeId"))
                if record:
                    row = dict(row, labelConfidence=record["labelConfidence"], labelAgreement=record["agreement"])
                    if record["labelConfidence"] == "low":
                        row["quality"] = dict(row.get("quality") or {}, label="low")
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        result["out"] = out
    return result


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog=prog, description="双跑标注比对与一致性记录（S 部分）；不一致记 low")
    parser.add_argument("labels", help="exchanges/labels JSONL; rows carry labelRuns {run1, run2}, or give --second")
    parser.add_argument("--second", help="the second run as its own JSONL, joined by exchangeId")
    parser.add_argument("--vocabulary", default=DATA)
    parser.add_argument("--out", help="write a copy with labelConfidence (low rows get quality.label: low)")
    args = parser.parse_args(argv)
    try:
        result = run_agree(args.labels, args.second, args.vocabulary, args.out)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
