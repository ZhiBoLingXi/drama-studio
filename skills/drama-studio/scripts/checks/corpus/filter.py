"""`corpus filter` -- S exclusion rules for "obviously unusable" samples (dialogue structure
architecture doc §4.4 第一层 S 过滤 table, plus the three rules §4.5 adds on top of it: stale
snapshots, the `evidenceValidation: not_run` passthrough note, and `missingFields`).

Input is one or more `dialogue-exchange`-shaped JSONL files (the real shape is
`corpus/exchanges.jsonl` from the阶段 A run: `exchangeId`, `lines[]` each
`{t0,t1,speaker,state,text,isMonologue}`, optional `missingFields`, `snapshotId`,
`evidenceValidation`). This never judges whether a passing sample is *good* (architecture §4.4:
"'优秀'怎么定：不靠人，也不靠分" is `anchors`/`recurrent`, a separate, later step) -- it only
decides whether a sample can be used as a sample at all.

Rules (S, §4.4 unless noted):
  - transcript_unparseable: timecodes not monotonic, a line has no speaker, or empty content.
  - too_few_speakers: fewer than 2 distinct non-monologue speakers.
  - no_response: every line shares one speaker (a "连说独白体" run, no one answers).
  - ad_copy: a line's text hits the ad-copy word list (下载/搜索/点击/APP/完整版/关注).
  - all_monologue: every line is a monologue line (narration/inner voice, nobody is "in" the
    scene) -- same bucket as `no_response`, kept as a separate reason code per the table.
  - state_label_leak (§4.4 "标注语言干净"): a line's `state` has non-Chinese runs; this does
    *not* exclude the sample, it only clears that line's `stateLabel` (reported, not blocking).
  - stale (§4.5): `snapshotId` differs from the current manifest's for the same
    templateId/episodeIndex -- only checked when `--manifest` is given; otherwise `not_evaluable`.
  - label_low (D6-4): `quality.label: low` or `labelConfidence: low` -- the double run (`corpus agree`) did not agree
    on the label, so the sample stays out of any search result.
  - missing_transcript (§4.5): `missingFields` names `rawMd`/`transcript` and there is no usable
    `lines[]` to cut from -- excluded. Any other `missingFields` entry is only noted.

`evidenceValidation: not_run` is never an exclusion reason (§4.5: "不作剔除条件"); it is passed
through into each row's output verbatim.

Exit codes: 0 (classification always succeeds once the input parses); 1 input/parse error.
Exclusion is the command's answer, not a failure -- consistent with the "数字不当裁判" /
"只报不拦" invariants used across the other diagnostic commands in this skill.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

AD_WORDS = ("下载", "搜索", "点击", "完整版", "关注公众号", "关注我")
NON_CHINESE_RUN = re.compile(r"[A-Za-z]{2,}")


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def _timecodes_monotonic(lines):
    prev_t1 = None
    for line in lines:
        t0, t1 = line.get("t0"), line.get("t1")
        if not isinstance(t0, int) or not isinstance(t1, int) or t0 > t1:
            return False
        if prev_t1 is not None and t0 < prev_t1:
            return False
        prev_t1 = t1
    return True


def filter_exchange(row, manifest_index=None):
    lines = row.get("lines") or []
    reasons = []
    notes = {}

    if not lines or not _timecodes_monotonic(lines):
        reasons.append("transcript_unparseable")
    else:
        if any(not (line.get("speaker") or "").strip() for line in lines):
            reasons.append("transcript_unparseable")
        if any(not (line.get("text") or "").strip() for line in lines):
            reasons.append("transcript_unparseable")

    voiced = [l for l in lines if not l.get("isMonologue")]
    speakers = {l.get("speaker") for l in voiced if l.get("speaker")}
    if not lines or len(speakers) < 2:
        if lines and not voiced:
            reasons.append("all_monologue")
        else:
            reasons.append("too_few_speakers")
    if lines and len({l.get("speaker") for l in lines if l.get("speaker")}) <= 1:
        reasons.append("no_response")

    for line in lines:
        text = line.get("text") or ""
        if any(word in text for word in AD_WORDS):
            reasons.append("ad_copy")
            break

    leaked_lines = [i for i, line in enumerate(lines) if NON_CHINESE_RUN.search(line.get("state") or "")]
    if leaked_lines:
        notes["stateLabelLeakLines"] = leaked_lines

    missing_fields = row.get("missingFields") or []
    if missing_fields:
        if not lines and any(f in ("rawMd", "transcript") for f in missing_fields):
            reasons.append("missing_transcript")
        notes["missingFields"] = missing_fields

    stale_status = "not_evaluable"
    if manifest_index is not None:
        key = (row.get("templateId"), row.get("episodeIndex"))
        current = manifest_index.get(key)
        if current is None:
            stale_status = "not_in_manifest"
        elif current != row.get("snapshotId"):
            stale_status = "stale"
            reasons.append("stale")
        else:
            stale_status = "current"
    notes["staleStatus"] = stale_status
    notes["evidenceValidation"] = row.get("evidenceValidation")

    # D6-4: a label the double run did not agree on (corpus agree) stays out of the pass list, so out of any search result
    quality = row.get("quality") if isinstance(row.get("quality"), dict) else {}
    if quality.get("label") == "low" or row.get("labelConfidence") == "low":
        reasons.append("label_low")
    reasons = sorted(set(reasons))
    return {
        "exchangeId": row.get("exchangeId"), "excluded": bool(reasons),
        "reasons": reasons, "notes": notes,
    }


def _manifest_index(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    index = {}
    for ep in manifest.get("episodes", []):
        index[(ep.get("templateId"), ep.get("episodeIndex"))] = ep.get("snapshotId")
    return index


def run_filter(paths, manifest_path=None):
    files = []
    for p in paths:
        files.extend(sorted(glob.glob(p)) if any(c in p for c in "*?[]") else [p])
    if not files:
        raise ValueError("no input files matched")
    manifest_index = _manifest_index(manifest_path) if manifest_path else None
    rows = []
    for f in files:
        rows.extend(_read_jsonl(f))
    results = [filter_exchange(row, manifest_index) for row in rows]
    by_reason = {}
    for r in results:
        for reason in r["reasons"]:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    return {
        "ok": True, "inputCount": len(results),
        "passCount": sum(1 for r in results if not r["excluded"]),
        "excludedCount": sum(1 for r in results if r["excluded"]),
        "byReason": by_reason, "results": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="dialogue-exchange JSONL file(s) or glob(s)")
    parser.add_argument("--manifest", help="corpus/manifest.json to check snapshotId staleness against; omit to leave stale checks not_evaluable")
    args = parser.parse_args(argv)
    try:
        result = run_filter(args.paths, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    result["reproduceCommand"] = "{} -B {} {}{}".format(
        sys.executable, os.path.abspath(__file__), " ".join(args.paths),
        f" --manifest {os.path.abspath(args.manifest)}" if args.manifest else "",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
