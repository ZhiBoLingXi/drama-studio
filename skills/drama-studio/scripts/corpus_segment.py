"""`corpus segment` -- S candidate exchange boundaries from a raw episode transcript
(architecture doc §4.1: "S 候选边界...M 确认"). Produces provisional spans; a human or model
annotator narrows/moves them and writes the `about` / `situation` / `walkthrough` labels that
`label.py` then checks (M is out of scope here, same split as the shared brief).

Candidate boundary signals, all mechanical / script-only:
  - `new_speaker`: a speaker not seen in the last `--window` voiced lines starts talking.
  - `pause`: the gap to the previous line is >= `--pause-ms` (default 4000, the long-tail pause
    architecture §4.1 calls out).
  - `monologue_run`: >=2 consecutive monologue lines just ended.
  - `storyline_boundary`: the line starts at or after a Storyline paragraph's start timestamp
    (time-code aligned; see transcript.storyline_paragraphs).

Input: a raw episode JSON (the `corpus/raw/<templateId>/ep-<NNN>.json` shape `extract.py`
produced in the阶段 A run -- a dict with `rawMd`, `templateId`, `episodeIndex`), or a directory
of them (globbed `ep-*.json`).

Output is boundary points plus the provisional segments they cut the episode into; it does not
decide which segments are usable samples (that is `filter.py`) and it does not count as the
final `dialogue-exchange` list.

Exit codes: 0 always for a successful parse (candidates are exploratory, not a gate); 1 if the
input cannot be read or parsed.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import corpus_transcript as T  # noqa: E402

DEFAULT_PAUSE_MS = 4000
DEFAULT_WINDOW = 4


def candidate_boundaries(lines, secs, pause_ms=DEFAULT_PAUSE_MS, window=DEFAULT_WINDOW):
    boundaries = []
    recent_voiced = []
    monologue_run = 0
    storyline_starts = sorted(p["startMs"] for p in T.storyline_paragraphs(secs))
    used_storyline_starts = set()
    prev = None
    for i, line in enumerate(lines):
        reasons = []
        if prev is not None and line["t0"] - prev["t1"] >= pause_ms:
            reasons.append("pause")
        if not T.is_monologue(line):
            if line["speaker"] not in recent_voiced[-window:]:
                reasons.append("new_speaker")
        if monologue_run >= 2 and not T.is_monologue(line):
            reasons.append("monologue_run")
        for start in storyline_starts:
            if start in used_storyline_starts:
                continue
            if prev is None or (prev["t1"] <= start <= line["t0"] + 1):
                if line["t0"] >= start:
                    reasons.append("storyline_boundary")
                    used_storyline_starts.add(start)
                    break
        if reasons:
            boundaries.append({"lineIndex": i, "reasons": sorted(set(reasons))})
        if T.is_monologue(line):
            monologue_run += 1
        else:
            monologue_run = 0
            recent_voiced.append(line["speaker"])
        prev = line
    return boundaries


def segments_from_boundaries(line_count, boundaries):
    starts = sorted({0, *(b["lineIndex"] for b in boundaries)})
    starts = [s for s in starts if s < line_count]
    segments = []
    for idx, start in enumerate(starts):
        end = (starts[idx + 1] - 1) if idx + 1 < len(starts) else line_count - 1
        if end >= start:
            segments.append({"lineStart": start, "lineEnd": end})
    return segments


def segment_episode(record):
    _, lines, secs = T.parse_transcript(record["rawMd"])
    boundaries = candidate_boundaries(lines, secs)
    segments = segments_from_boundaries(len(lines), boundaries)
    return {
        "templateId": record.get("templateId"), "episodeIndex": record.get("episodeIndex"),
        "lineCount": len(lines), "boundaryCount": len(boundaries),
        "boundaries": boundaries, "segmentCount": len(segments), "segments": segments,
    }


def run_segment(paths):
    files = []
    for p in paths:
        matched = sorted(glob.glob(p)) if any(c in p for c in "*?[]") else [p]
        for f in matched:
            if os.path.isdir(f):
                files.extend(sorted(glob.glob(os.path.join(f, "ep-*.json"))))
            else:
                files.append(f)
    if not files:
        raise ValueError("no input files matched")
    episodes = []
    for f in files:
        with open(f, encoding="utf-8") as handle:
            record = json.load(handle)
        if "rawMd" not in record:
            raise ValueError(f"{f}: missing rawMd")
        episodes.append(segment_episode(record))
    return {
        "ok": True, "episodeCount": len(episodes),
        "totalSegmentCount": sum(e["segmentCount"] for e in episodes),
        "episodes": episodes,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="raw episode JSON file(s), glob(s), or a corpus/raw/<templateId>/ directory")
    parser.add_argument("--pause-ms", type=int, default=DEFAULT_PAUSE_MS)
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    args = parser.parse_args(argv)
    try:
        result = run_segment(args.paths)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    result["reproduceCommand"] = "{} -B {} {}".format(
        sys.executable, os.path.abspath(__file__), " ".join(os.path.abspath(p) if not any(c in p for c in "*?[]") else p for p in args.paths),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
