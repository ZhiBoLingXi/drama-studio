"""capacity: one formula, three entries — season (rough), episode (re-check), text (fine).

season / episode (outline-layer design §7.1):
  estimateSecA = facts × exchangeMedianSec + pictureBeats × pictureBeatSec
                 (every fact counted as one exchange, picture-carried ones too)
  estimateSecB = dialogue-carried facts × exchangeMedianSec + picture units × pictureBeatSec
                 (season: picture units = carrier "p" facts + pictureBeats, since there pictureBeats
                 excludes beats that carry a fact; episode: picture units = beats marked picture,
                 which already include the beats that carry a fact)
  exchangeMedianSec is the median exchange length of the corpus (exchanges.jsonl, endMs - startMs).
  pictureBeatSec is the media profile's value when it has one, else 2.0 (assumed, not measured).
text (dialogue-structure design §3.3):
  estimateSecA = speech chars ÷ speechRateCharsPerMin × 60 ÷ (1 − pauseShare)
  estimateSecB = speech chars ÷ grossCharsPerMinute (speechCharsPerEpisodeMin) × 60
  speech chars: Han characters of dialogue lines ("人名（括注）：台词"), parentheticals removed;
  scene headings (场6-1 / 场6A-1 / ### 6A-1 ...), cast lines, △ action lines and titles excluded.

Both bases are always reported. The tool only computes and reports: the output carries no
within/outside/fits/exceeds verdict and the exit code is 0 whatever the numbers are (numbers are
not judges; a capacity proposal is a decision-queue entry, not a failure). An unreadable input is
still exit 1. Never goes online or calls a model.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys

try:
    from . import ledger as L
except ImportError:  # run as a script
    import ledger as L

DEFAULT_PICTURE_BEAT_SEC = 2.0
FORMULA_SEASON_A = "infoCount × exchangeMedianSec + pictureBeats × pictureBeatSec"
FORMULA_SEASON_B = "dialogueFacts × exchangeMedianSec + (pictureFacts + pictureBeats) × pictureBeatSec"
FORMULA_EPISODE_B = "dialogueFacts × exchangeMedianSec + pictureBeats × pictureBeatSec（画面拍已含承载事实的拍）"
FORMULA_TEXT_A = "speechChars ÷ speechRateCharsPerMin × 60 ÷ (1 − pauseShare)"
FORMULA_TEXT_B = "speechChars ÷ grossCharsPerMinute × 60"

# Screenplay line parsing; identical to the D6-0 text_lines parser (letter scene ids such as 6A-1).
SCENE_HEADER_RE = re.compile(r"^(#{1,6}\s*)?场\s*\d")
HASH_SCENE_RE = re.compile(r"^#{1,6}\s*(?P<sid>\d+[A-Za-z]?-\d+[A-Za-z]?)(?:\s|$)")
SCENE_ID_RE = re.compile(r"^场\s*(?P<sid>\S+)\s*(?P<rest>.*)$")
TITLE_RE = re.compile(r"^#{1,2}\s*第")
CAST_LINE_RE = re.compile(r"^人物[：:]")
DIALOGUE_LINE_RE = re.compile(r"^(?P<speaker>[^：\n（(]+)(?P<state>[（(][^）)]*[）)])?[：:](?P<content>.*)$")
PAREN_RE = re.compile(r"[（(][^）)]*[）)]")
HAN_RE = re.compile(r"[一-鿿]")


def han_count(text):
    return len(HAN_RE.findall(text or ""))


def parse_lines(md_text):
    """1-based line records: kind ∈ title/scene/cast/action/dialogue/blank/other, with the current
    sceneId, speaker, state (parenthetical before the colon) and content."""
    out, scene = [], None
    for i, raw in enumerate(md_text.splitlines(), start=1):
        line = raw.strip()
        rec = {"line": i, "kind": "blank", "sceneId": scene, "speaker": None, "state": None, "content": None}
        if not line:
            pass
        elif TITLE_RE.match(line):
            rec["kind"] = "title"
        elif SCENE_HEADER_RE.match(line) or HASH_SCENE_RE.match(line):
            m = SCENE_ID_RE.match(line.lstrip("#").strip()) or HASH_SCENE_RE.match(line)
            scene = m.group("sid") if m else None
            rec.update(kind="scene", sceneId=scene)
        elif line.startswith("#"):
            rec["kind"] = "other"
        elif CAST_LINE_RE.match(line):
            rec["kind"] = "cast"
        elif line.startswith("△"):
            rec.update(kind="action", content=line[1:].strip())
        else:
            m = DIALOGUE_LINE_RE.match(line)
            if m:
                state = m.group("state")
                rec.update(kind="dialogue", speaker=m.group("speaker").strip(),
                           state=state.strip("（）()").strip() if state else None, content=m.group("content").strip())
            else:
                rec["kind"] = "other"
        out.append(rec)
    return out


def load_media(path, fmt):
    doc = L.load_json(path, "媒介档案")
    fd = ((doc or {}).get("formatDefault") or {}).get(fmt)
    if not isinstance(fd, dict):
        raise L.InputError(f"媒介档案里没有形态 {fmt!r}（有 {sorted(((doc or {}).get('formatDefault') or {}).keys())}）")
    return doc, fd


def picture_beat_sec(media_doc, media_fd, override):
    if override is not None:
        return override, "argument"
    for source in (media_fd, media_doc):
        value = (source or {}).get("pictureBeatSec")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value), "media_profile"
        if isinstance(value, dict) and isinstance(value.get("value"), (int, float)):
            return float(value["value"]), f"media_profile:{value.get('source', 'unknown')}"
    return DEFAULT_PICTURE_BEAT_SEC, "assumed"


def exchange_stats(corpus_path):
    durations, gaps = [], []
    try:
        with open(corpus_path, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    durations.append((rec["endMs"] - rec["startMs"]) / 1000.0)
                except (json.JSONDecodeError, KeyError, TypeError):
                    raise L.InputError(f"{corpus_path} 第 {n} 行不是带 startMs/endMs 的交换记录") from None
                lines = rec.get("lines") or []
                for a, b in zip(lines, lines[1:]):
                    try:
                        g = (b["t0"] - a["t1"]) / 1000.0
                    except (KeyError, TypeError):
                        continue
                    if g > 0:
                        gaps.append(g)
    except FileNotFoundError:
        raise L.InputError(f"找不到语料：{corpus_path}") from None
    if not durations:
        raise L.InputError(f"{corpus_path} 里没有可用的交换记录")
    return {"n": len(durations), "medianSec": round(statistics.median(durations), 2),
            "interLineGapMedianSec": round(statistics.median(gaps), 2) if gaps else None, "interLineGapN": len(gaps)}


def outline_basis(args):
    media_doc, media_fd = load_media(args.media, args.format)
    if args.exchange_median_sec is not None:
        stats = {"n": None, "medianSec": args.exchange_median_sec, "interLineGapMedianSec": None, "interLineGapN": None,
                 "source": "argument"}
    elif args.corpus:
        stats = dict(exchange_stats(args.corpus), source="corpus")
    else:
        raise L.InputError("要 --corpus（算语料交换中位时长）或 --exchange-median-sec")
    pbs, pbs_source = picture_beat_sec(media_doc, media_fd, args.picture_beat_sec)
    basis = {"format": args.format, "calibration": (media_doc or {}).get("calibration"),
             "exchangeMedianSec": stats["medianSec"], "exchangeMedianSource": stats["source"], "exchangeSampleN": stats["n"],
             "interLineGapMedianSec": stats["interLineGapMedianSec"], "interLineGapNote": "同一来回内两句台词的间隙中位数，只作旁证，不进公式",
             "pictureBeatSec": pbs, "pictureBeatSecSource": pbs_source}
    return basis, media_fd


def estimate(facts, pictures, basis):
    return round(facts * basis["exchangeMedianSec"] + pictures * basis["pictureBeatSec"], 1)


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def season_items(ep, statuses):
    return [i for i in ep.get("infoItemsRough", []) or [] if i.get("status", "kept") in statuses]


def carriers(items):
    d = sum(1 for i in items if i.get("carrier") == "d")
    p = sum(1 for i in items if i.get("carrier") == "p")
    return d, p, len(items) - d - p


def cmd_season(args):
    doc = L.load_json(args.season_plan, "季编排")
    if not isinstance(doc, dict) or not isinstance(doc.get("episodes"), list):
        raise L.InputError("季编排缺 episodes 数组")
    basis, media_fd = outline_basis(args)
    default_target = media_fd.get("targetSecondsDefault")
    by_id = {str(ep.get("episode")): ep for ep in doc["episodes"]}

    def row(ep_id, cap, items, notes):
        info, pics = number(cap.get("infoCount")), number(cap.get("pictureBeats"))
        if info is None:
            notes.append("capacity.infoCount 未给，按条目数")
            info = len(items)
        if pics is None:
            notes.append("capacity.pictureBeats 未给，按 0")
            pics = 0
        d, p, unknown = carriers(items)
        if unknown:
            notes.append(f"{unknown} 条信息没有 carrier（d/p），口径乙未计入它们")
        if items and len(items) != info:
            notes.append(f"按条目数 {len(items)} 与 capacity.infoCount {info} 不同；口径甲用 infoCount，口径乙用条目")
        target = number(cap.get("targetSec"))
        if target is None:
            target = default_target
            notes.append("targetSec 未给，取媒介档案 targetSecondsDefault")
        return {"episode": ep_id, "infoCount": info, "pictureBeats": pics, "estimateSecA": estimate(info, pics, basis),
                "dialogueFacts": d, "pictureFacts": p, "estimateSecB": estimate(d, p + pics, basis) if items else None,
                "targetSec": target, "notes": notes}

    # Counting rule: before actions = kept + moved_out; a split child exists only after the split,
    # so it is counted as after actions (kept + moved_in); merged_in never adds a count.
    episodes = [row(ep.get("episode"), ep.get("capacity") or {},
                    season_items(ep, ("kept", "moved_in") if ep.get("role") == "split_child" else ("kept", "moved_out")), [])
                for ep in doc["episodes"]]
    final = []
    for item in doc.get("finalSequence", []) or []:
        ep = by_id.get(str(item.get("id")))
        notes = [] if ep else ["episodes[] 里没有这一集，口径乙算不了"]
        r = row(item.get("id"), item, season_items(ep, ("kept", "moved_in")) if ep else [], notes)
        r["newEpisodeNo"] = item.get("newEpisodeNo")
        final.append(r)
    L.emit({"ok": True, "entry": "season", "basis": basis, "formulas": {"A": FORMULA_SEASON_A, "B": FORMULA_SEASON_B},
            "episodes": episodes, "finalSequence": final, "reproduceCommand": args.reproduce})
    return 0


def cmd_episode(args):
    plan = L.load_json(args.episode_plan, "分集计划")
    if not isinstance(plan, dict):
        raise L.InputError("分集计划不是 JSON 对象")
    basis, media_fd = outline_basis(args)
    picture_beat_ids = set()
    for sc in (plan.get("events") or {}).get("scenes", []) or []:
        for b in sc.get("beats", []) or []:
            if b.get("picture"):
                picture_beat_ids.add(b.get("beatId"))
    facts = [f for info in plan.get("infoLedger", []) or [] for f in info.get("facts") or []]
    picture_facts = [f.get("factId") for f in facts if f.get("carrierBeat") in picture_beat_ids]
    dialogue_facts = len(facts) - len(picture_facts)
    cap = plan.get("capacity") or {}
    notes = []
    target = number(cap.get("targetSec"))
    if target is None:
        target = media_fd.get("targetSecondsDefault")
        notes.append("capacity.targetSec 未给，取媒介档案 targetSecondsDefault")
    L.emit({"ok": True, "entry": "episode", "episode": plan.get("episode"), "basis": basis,
            "formulas": {"A": FORMULA_SEASON_A, "B": FORMULA_EPISODE_B},
            "infoCount": len(facts), "pictureBeats": len(picture_beat_ids), "estimateSecA": estimate(len(facts), len(picture_beat_ids), basis),
            "dialogueFacts": dialogue_facts, "pictureCarriedFacts": picture_facts,
            "estimateSecB": estimate(dialogue_facts, len(picture_beat_ids), basis), "targetSec": target,
            "declared": {k: cap.get(k) for k in ("infoCount", "pictureBeats", "estimateSec", "estimateSecBasisB", "targetSec") if k in cap},
            "notes": notes, "reproduceCommand": args.reproduce})
    return 0


def cmd_text(args):
    _, media_fd = load_media(args.media, args.format)
    try:
        with open(args.text_file, "r", encoding="utf-8") as f:
            parsed = parse_lines(f.read())
    except FileNotFoundError:
        raise L.InputError(f"找不到正文：{args.text_file}") from None
    per_scene, chars, lines = {}, 0, 0
    for rec in parsed:
        if rec["kind"] != "dialogue":
            continue
        n = han_count(PAREN_RE.sub("", rec["content"] or ""))
        chars += n
        lines += 1
        slot = per_scene.setdefault(rec["sceneId"] or "（场头之前）", {"speechChars": 0, "dialogueLines": 0})
        slot["speechChars"] += n
        slot["dialogueLines"] += 1
    rate, pause = number(media_fd.get("speechRateCharsPerMin")), number(media_fd.get("pauseShare"))
    gross = number(media_fd.get("grossCharsPerMinute")) or number(media_fd.get("speechCharsPerEpisodeMin"))
    notes = []
    a = round(chars / rate * 60 / (1 - pause), 1) if rate and pause is not None and pause < 1 else None
    b = round(chars / gross * 60, 1) if gross else None
    if a is None:
        notes.append("媒介档案缺 speechRateCharsPerMin/pauseShare，口径甲算不了")
    if b is None:
        notes.append("媒介档案缺 grossCharsPerMinute（speechCharsPerEpisodeMin），口径乙算不了")
    L.emit({"ok": True, "entry": "text", "textFile": args.text_file, "speechChars": chars, "dialogueLinesCounted": lines,
            "perScene": [{"sceneId": sid, **v} for sid, v in per_scene.items()],
            "estimateSecA": a, "estimateSecB": b, "formulas": {"A": FORMULA_TEXT_A, "B": FORMULA_TEXT_B},
            "media": {"format": args.format, "speechRateCharsPerMin": rate, "pauseShare": pause, "grossCharsPerMinute": gross,
                      "targetSecondsDefault": media_fd.get("targetSecondsDefault")},
            "notes": notes, "reproduceCommand": args.reproduce})
    return 0


def build_parser(prog=None):
    ap = argparse.ArgumentParser(prog=prog, description="容量：季编排粗估 / 分集计划复核 / 正文精估，一套公式，两口径并报，不判定")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, target, func in (("season", "season_plan", cmd_season), ("episode", "episode_plan", cmd_episode)):
        p = sub.add_parser(name)
        p.add_argument(target)
        p.add_argument("--media", required=True)
        p.add_argument("--corpus", default=None, help="exchanges.jsonl；算语料交换中位时长")
        p.add_argument("--exchange-median-sec", type=float, default=None, help="不给语料时直接给中位时长")
        p.add_argument("--format", default="live")
        p.add_argument("--picture-beat-sec", type=float, default=None)
        p.set_defaults(func=func)
    p = sub.add_parser("text")
    p.add_argument("text_file")
    p.add_argument("--media", required=True)
    p.add_argument("--format", default="live")
    p.set_defaults(func=cmd_text)
    return ap


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser(prog).parse_args(argv)
    args.reproduce = L.reproduce_command(__file__, argv)
    try:
        return args.func(args)
    except (L.InputError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
