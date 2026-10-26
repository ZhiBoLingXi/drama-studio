"""`corpus rate` -- media-profile physical quantities only (dialogue structure architecture doc
§3.2 "媒介档案只保留物理量"). Ported from the阶段 A script
the D6-0 pilot's `media_profile.py` so the real numbers keep
reproducing exactly (local acceptance compares this against `media-profile-v0.json`); the field
names below follow the D6-1 decisions on top of that prototype, not the prototype's own names,
where the two differ:

  - `speechRate` (two units, both kept until `calibration: project_measured` per plan §2.5 #13):
    `speechRateCharsPerMin` / `speechRateCharsPerSec` -- chars spoken ÷ seconds those lines'
    timecodes cover. This is the "during speech" rate (architecture §3.2's literal definition).
  - `grossCharsPerMinute` -- chars spoken ÷ the whole episode's minutes, pauses included
    (stage-a-report.md §5: this is what "真人约 172 字/分、漫剧约 128 字/分" in §3.4 actually
    measured; the prototype called this field `speechCharsPerEpisodeMin`, renamed here per the
    implementation plan §2.1 #8).
  - `pauseShare` -- unchanged name; `pauseShareVoicedOnly` (voiced lines only, excludes
    monologue-covered time) is kept too, matching the real artifact (shared brief rule #3: real
    field beats the plan's abstract table when the two don't name the same thing).
  - `pictureBeatSec` -- cannot be measured from this corpus yet (no timing data isolates a pure
    visual beat from a pause); always `source: assumed` until D6-4 measures it from raw
    timecodes (plan §2.1 #8). The ~2s default here is the same order of magnitude the retell
    prompt already assumes for a silent beat (architecture doc §9.2) -- not a corpus measurement.
  - `calibration` -- `corpus_default` (the formula below) or `project_measured` once a project
    supplies its own measured numbers via `--override`; the prototype used a placeholder value
    `"uncalibrated"` before this enum was decided.
  - `format` / `formatSource` -- a script cannot judge a format from prose (that is an M call,
    architecture §3.2); `--series-format <templateId>=<live|anime>` supplies it explicitly
    (`formatSource: given`), otherwise every series defaults to `live` (`formatSource: assumed`).
    `formatEvidence` is still extracted mechanically (the raw rawMd's "视听风格简述" section,
    if present) -- that is quoting, not judging.

Exit codes: 0 on a successful computation (nothing here is a pass/fail gate -- "数字不当裁判");
1 if the raw directory or an episode file cannot be read/parsed.
"""
from __future__ import annotations

import argparse
import json
import datetime
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import corpus_transcript as T  # noqa: E402

PICTURE_BEAT_SEC_ASSUMED_DEFAULT = 2.0


def _style_hint(secs):
    return secs.get("视听风格简述", "")


def _load_series(raw_dir):
    """{templateId: {title, episodes: [{episodeIndex, durationSec, speechChars, voicedSec,
    allSpeechSec, voicedLines}], styles: [(episodeIndex, styleText)]}}"""
    per_series = {}
    for tdir in sorted((d for d in os.scandir(raw_dir) if d.is_dir()), key=lambda d: d.name):
        tid = tdir.name
        eps, styles, title = [], [], None
        files = sorted(f for f in os.listdir(tdir.path) if f.startswith("ep-") and f.endswith(".json"))
        for fname in files:
            with open(os.path.join(tdir.path, fname), encoding="utf-8") as f:
                rec = json.load(f)
            title = title or rec.get("title")
            _, lines, secs = T.parse_transcript(rec["rawMd"])
            st = T.episode_stats(lines, T.storyline_end_ms(secs))
            dur_ms = st["episodeEndMs"]
            if dur_ms <= 0:
                continue
            style = _style_hint(secs)
            if style:
                styles.append((rec.get("episodeIndex"), style[:200]))
            eps.append({
                "episodeIndex": rec.get("episodeIndex"), "durationSec": dur_ms / 1000,
                "speechChars": st["speechChars"], "voicedSec": st["voicedMs"] / 1000,
                "allSpeechSec": st["allSpeechMs"] / 1000, "voicedLines": st["voicedLines"],
            })
        if eps:
            per_series[tid] = {"title": title, "episodes": eps, "styles": styles}
    return per_series


def _format_default_entry(durs, chars, voiced_sec, all_speech_sec, dur_sec):
    return {
        "sampleEpisodes": len(durs),
        "targetSecondsDefault": round(statistics.median(durs), 1),
        "speechRateCharsPerMin": round(chars / voiced_sec * 60, 1) if voiced_sec else None,
        "speechRateCharsPerSec": round(chars / voiced_sec, 2) if voiced_sec else None,
        "grossCharsPerMinute": round(chars / dur_sec * 60, 1) if dur_sec else None,
        "pauseShare": round(1 - all_speech_sec / dur_sec, 3) if dur_sec else None,
    }


def compute_media_profile(raw_dir, series_format=None, project_overrides=None,
                           picture_beat_sec_assumed=PICTURE_BEAT_SEC_ASSUMED_DEFAULT):
    series_format = series_format or {}
    project_overrides = project_overrides or {}
    per_series_raw = _load_series(raw_dir)
    if not per_series_raw:
        raise ValueError(f"no series found under {raw_dir}")

    per_series = {}
    for tid, data in per_series_raw.items():
        eps = data["episodes"]
        total_chars = sum(e["speechChars"] for e in eps)
        total_voiced = sum(e["voicedSec"] for e in eps)
        total_dur = sum(e["durationSec"] for e in eps)
        total_all = sum(e["allSpeechSec"] for e in eps)
        fmt = series_format.get(tid, "live")
        per_series[tid] = {
            "title": data["title"], "format": fmt,
            "formatSource": "given" if tid in series_format else "assumed",
            "formatEvidence": [f"EP{n}: {s}" for n, s in data["styles"][:3]] or
                ["rawMd 没有《视听风格简述》段；未证据化，format 按 assumed 处理"],
            "sampleEpisodes": len(eps), "episodeIndexes": [e["episodeIndex"] for e in eps],
            "episodeDurationSec": {
                "median": round(statistics.median(e["durationSec"] for e in eps), 1),
                "mean": round(statistics.mean(e["durationSec"] for e in eps), 1),
                "min": round(min(e["durationSec"] for e in eps), 1),
                "max": round(max(e["durationSec"] for e in eps), 1),
            },
            "speechRateCharsPerMin": round(total_chars / total_voiced * 60, 1) if total_voiced else None,
            "speechRateCharsPerSec": round(total_chars / total_voiced, 2) if total_voiced else None,
            "grossCharsPerMinute": round(total_chars / total_dur * 60, 1) if total_dur else None,
            "pauseShare": round(1 - total_all / total_dur, 3) if total_dur else None,
            "pauseShareVoicedOnly": round(1 - total_voiced / total_dur, 3) if total_dur else None,
            "perEpisode": eps,
        }

    by_format = {}
    for tid, s in per_series.items():
        agg = by_format.setdefault(s["format"], {"series": [], "chars": 0, "voicedSec": 0.0,
                                                   "allSpeechSec": 0.0, "durSec": 0.0, "durs": []})
        agg["series"].append(tid)
        for e in s["perEpisode"]:
            agg["chars"] += e["speechChars"]; agg["voicedSec"] += e["voicedSec"]
            agg["allSpeechSec"] += e["allSpeechSec"]; agg["durSec"] += e["durationSec"]
            agg["durs"].append(e["durationSec"])

    format_default = {}
    for fmt, agg in by_format.items():
        entry = {"series": agg["series"], **_format_default_entry(
            agg["durs"], agg["chars"], agg["voicedSec"], agg["allSpeechSec"], agg["durSec"])}
        override = project_overrides.get(fmt)
        entry["projectValue"] = {**entry, **override} if override else {
            k: entry[k] for k in ("targetSecondsDefault", "speechRateCharsPerMin",
                                   "speechRateCharsPerSec", "grossCharsPerMinute", "pauseShare")
        }
        entry["source"] = "measured_project" if override else "measured_corpus"
        format_default[fmt] = entry

    return {
        "schema": "media-profile/v1", "calibration": "project_measured" if project_overrides else "corpus_default",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "note": "只含物理量。口径：口播语速（speechRate）≠每集每分钟台词汉字（grossCharsPerMinute，含停顿）；两个口径同时报，不自行选一。不含任何每分钟几句/换人次数之类的配额。时间码未经原片核验。",
        "measurementBasis": {
            "speechRate": "speechChars(voiced) / voicedSec * 60",
            "grossCharsPerMinute": "speechChars(voiced) / episodeDurationSec * 60",
            "pauseShare": "1 - allSpeechSec / episodeDurationSec",
            "episodeDuration": "max(end timecode in Storyline, Transcript)",
        },
        "pictureBeatSec": {"value": picture_beat_sec_assumed, "source": "assumed",
                           "note": "画面拍时长语料量不出，暂用经验值；D6-4 从原始转写的时间码量出后替换。"},
        "formatDefault": format_default,
        "perSeries": per_series,
    }


def _parse_series_format(pairs):
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"--series-format expects templateId=format, got: {pair}")
        tid, fmt = pair.split("=", 1)
        out[tid] = fmt
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", help="corpus/raw/ directory (one subdirectory per templateId, each with ep-*.json)")
    parser.add_argument("--series-format", action="append", help="templateId=live|anime; repeatable; unlisted series default to live (formatSource: assumed)")
    parser.add_argument("--override", help="JSON file {format: {field: value}} of project-measured values; sets calibration: project_measured")
    parser.add_argument("--picture-beat-sec", type=float, default=PICTURE_BEAT_SEC_ASSUMED_DEFAULT)
    args = parser.parse_args(argv)
    try:
        series_format = _parse_series_format(args.series_format)
        overrides = None
        if args.override:
            with open(args.override, encoding="utf-8") as f:
                overrides = json.load(f)
        result = compute_media_profile(args.raw_dir, series_format, overrides, args.picture_beat_sec)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    result["ok"] = True
    result["reproduceCommand"] = "{} -B {} {}{}{}".format(
        sys.executable, os.path.abspath(__file__), os.path.abspath(args.raw_dir),
        "".join(f" --series-format {p}" for p in (args.series_format or [])),
        f" --override {os.path.abspath(args.override)}" if args.override else "",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
