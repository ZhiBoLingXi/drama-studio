"""`corpus defaults` -- recompute the bundled statistics from a corpus (plan §4.5; D6-4 decisions §3).

From a corpus folder (`raw/<templateId>/ep-*.json`, `exchanges.jsonl`, `manifest.json`) this recomputes:
  - the media-profile defaults per format (the same formula as `corpus rate`) and the exchange median seconds per
    format, each with n (series, episodes, exchanges);
  - per bundled genre-lexicon list: how often its words occur in the corpus genre it names and in the other genres
    (n episodes and lines per genre), which assumed words the corpus confirms (seen in the list's genre, never in the
    others), and new candidates (Han 2-3-grams frequent in the list's genre and absent from the others, character
    names left out). Candidates may hold series-specific words, so they stay in --out (the project), never in the bundle;
  - a comparison with the bundled `default-media-profile.json` and `genre-lexicon.json`.

The corpus may be a studio corpus folder (`<studio root>/corpus/`, plan §8 #1); its exchanges must then all be
scope.level studio from a mali-story template. The bundle only ever takes statistics and word lists, never corpus lines. Reads only; writes --out when given (never
overwrites). Exit codes: 0 done; 1 input error.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rate  # noqa: E402
from studio import studio_corpus_root, studio_row_problem  # noqa: E402

DATA = os.path.join(HERE, "..", "..", "..", "schemas", "data")
HAN = re.compile(r"[一-鿿]+")
GENRE_OF_LIST = {"仙侠／古装玄幻": ("仙侠", "古装", "玄幻"), "霸总／都市言情": ("霸总", "都市", "言情")}


def _load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _exchanges(corpus):
    rows = []
    with open(os.path.join(corpus, "exchanges.jsonl"), "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def exchange_medians(rows):
    by_format = collections.defaultdict(list)
    for row in rows:
        fmt = (row.get("series") or {}).get("format") or "live"
        if isinstance(row.get("startMs"), (int, float)) and isinstance(row.get("endMs"), (int, float)):
            by_format[fmt].append((row["endMs"] - row["startMs"]) / 1000.0)
    return {fmt: {"value": round(statistics.median(values), 1), "n": len(values), "source": "measured_corpus"}
            for fmt, values in by_format.items()}


def _genre_side(genre, list_genre):
    return any(word in (genre or "") for word in GENRE_OF_LIST.get(list_genre, ()))


def lexicon_stats(rows, lexicon):
    names = {line.get("speaker") for row in rows for line in row.get("lines") or [] if line.get("speaker")}
    out = []
    for entry in lexicon.get("lists", []):
        list_genre = entry.get("fromGenre")
        side = [r for r in rows if _genre_side((r.get("series") or {}).get("genre"), list_genre)]
        other = [r for r in rows if r not in side]
        text = lambda group: [line.get("text") or "" for r in group for line in r.get("lines") or []]  # noqa: E731
        side_text, other_text = "\n".join(text(side)), "\n".join(text(other))
        counts = {w: (side_text.count(w), other_text.count(w)) for w in entry.get("words", [])}
        grams = collections.Counter()
        episodes = collections.defaultdict(set)
        for r in side:
            for line in r.get("lines") or []:
                for run in HAN.findall(line.get("text") or ""):
                    for size in (2, 3):
                        for i in range(len(run) - size + 1):
                            gram = run[i:i + size]
                            grams[gram] += 1
                            episodes[gram].add((r.get("templateId"), r.get("episodeIndex")))
        candidates = [{"word": g, "count": c, "episodes": len(episodes[g])} for g, c in grams.most_common()
                      if c >= 3 and len(episodes[g]) >= 2 and g not in other_text and not any(g in n for n in names)][:30]
        out.append({"fromGenre": list_genre,
                    "n": {"exchanges": len(side), "episodes": len({(r.get("templateId"), r.get("episodeIndex")) for r in side}),
                          "series": len({r.get("templateId") for r in side}), "otherExchanges": len(other)},
                    "assumedWords": len(counts),
                    "confirmed": sorted(w for w, (a, b) in counts.items() if a > 0 and b == 0),
                    "seenInOtherGenres": sorted(w for w, (a, b) in counts.items() if b > 0),
                    "notSeen": sorted(w for w, (a, b) in counts.items() if a == 0 and b == 0),
                    "candidates": candidates if side else [],
                    "evaluable": bool(side) and bool(other)})
    return out


def compare_media(measured, bundled):
    diffs = []
    for fmt, values in measured["formatDefault"].items():
        old = (bundled.get("formatDefault") or {}).get(fmt) or {}
        for key in ("speechRateCharsPerMin", "pauseShare", "speechCharsPerEpisodeMin", "targetSecondsDefault"):
            new_key = "grossCharsPerMinute" if key == "speechCharsPerEpisodeMin" else key
            if old.get(key) != values.get(new_key):
                diffs.append({"format": fmt, "field": key, "bundled": old.get(key), "measured": values.get(new_key)})
    old_ex = bundled.get("exchangeMedianSec") or {}
    for fmt, values in measured["exchangeMedianSec"].items():
        if (old_ex.get(fmt) or {}).get("value") != values["value"]:
            diffs.append({"format": fmt, "field": "exchangeMedianSec", "bundled": (old_ex.get(fmt) or {}).get("value"), "measured": values["value"]})
    return diffs


def run_defaults(corpus, series_format, out=None, media_path=None, lexicon_path=None):
    media_path = media_path or os.path.join(DATA, "default-media-profile.json")
    lexicon_path = lexicon_path or os.path.join(DATA, "genre-lexicon.json")
    rows = _exchanges(corpus)
    scope = "studio" if studio_corpus_root(corpus) is not None else "project"
    bad = [r.get("exchangeId") for r in rows if studio_row_problem(r)] if scope == "studio" else []
    if bad:  # plan §8 #1: the studio corpus holds mali-story template data only
        raise ValueError(f"{corpus} 是工作室语料目录，但 exchanges.jsonl 有 {len(bad)} 行不是 scope.level: studio 且 "
                         f"origin.kind: mali_story_template：{bad[:5]}")
    profile = rate.compute_media_profile(os.path.join(corpus, "raw"), series_format)
    measured = {"formatDefault": {fmt: {k: v[k] for k in ("series", "sampleEpisodes", "targetSecondsDefault", "speechRateCharsPerMin",
                                                          "grossCharsPerMinute", "pauseShare") if k in v}
                                  for fmt, v in profile["formatDefault"].items()},
                "exchangeMedianSec": exchange_medians(rows)}
    for fmt, values in measured["formatDefault"].items():
        values["n"] = {"series": len(values.pop("series")), "episodes": values["sampleEpisodes"]}
    lexicon = lexicon_stats(rows, _load(lexicon_path))
    result = {"ok": True, "corpus": corpus, "scope": scope, "media": measured, "mediaDiffs": compare_media(measured, _load(media_path)),
              "lexicon": lexicon,
              "note": "随包数据只取统计量与词表；candidates 可能含系列专有词，只写进 --out（项目目录）"}
    if out:
        if os.path.exists(out):
            raise ValueError(f"{out} 已存在；不覆盖")
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        result["out"] = out
    result["lexicon"] = [{k: v for k, v in entry.items() if k != "candidates"} | {"candidateCount": len(entry["candidates"])}
                         for entry in lexicon]  # stdout carries no candidate words
    return result


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog=prog, description="从语料重算随包的媒介档案默认值与题材禁词表统计（标 n）；只读")
    parser.add_argument("corpus", help="corpus folder: raw/<templateId>/ep-*.json and exchanges.jsonl")
    parser.add_argument("--series-format", action="append", default=[], help="templateId=live|anime (unlisted: live)")
    parser.add_argument("--out", help="write the full recomputation (with lexicon candidates) here; never overwrites")
    parser.add_argument("--media", help="bundled media profile to compare with (default schemas/data/default-media-profile.json)")
    parser.add_argument("--lexicon", help="bundled genre lexicon to compare with (default schemas/data/genre-lexicon.json)")
    args = parser.parse_args(argv)
    try:
        formats = dict(pair.split("=", 1) for pair in args.series_format)
        result = run_defaults(args.corpus, formats, args.out, args.media, args.lexicon)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
