"""plan-events: export an episode plan's events for the cold reader (D6-2 §5 #9).

The cold read of an episode plan reads what happens and nothing of the design. This command keeps, per scene, sceneId,
time, place, present and beats, and per beat beatId, who, text, quote and offscreen; every other field (saysFact,
picture, carriers, and the plan's moves, infoLedger, ledgerDelta, summary, capacity, exit ...) stays out, and the
output lists which fields inside events were dropped. `context-pack --role cold_reader` takes this export and refuses a whole
episode plan.

Writes --out (never overwrites a file with different bytes; same bytes is a no-op) or prints to stdout. Read-only
otherwise; never goes online or calls a model. Exit codes: 0 written or printed; 1 input error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import ledger as L

SCHEMA = "drama-studio/episode-plan-events/v0"
SCENE_KEYS = ("sceneId", "time", "place", "present", "beats")
BEAT_KEYS = ("beatId", "who", "text", "quote", "offscreen")


def export_events(plan: dict, source: str, data: bytes) -> tuple[dict, list[str]]:
    events = plan.get("events") if isinstance(plan.get("events"), dict) else None
    if events is None or not isinstance(events.get("scenes"), list):
        raise L.InputError("分集计划没有 events.scenes")
    dropped = {f"events.{key}" for key in events if key != "scenes"}
    scenes = []
    for scene in events["scenes"]:
        if not isinstance(scene, dict):
            continue
        dropped |= {f"scenes[].{key}" for key in scene if key not in SCENE_KEYS}
        beats = []
        for beat in scene.get("beats") or []:
            if isinstance(beat, dict):
                dropped |= {f"beats[].{key}" for key in beat if key not in BEAT_KEYS}
                beats.append({key: beat[key] for key in BEAT_KEYS if key in beat})
        scenes.append({**{key: scene[key] for key in SCENE_KEYS if key in scene and key != "beats"}, "beats": beats})
    doc = {"schemaVersion": SCHEMA, "episode": plan.get("episode"),
           "source": {"file": source, "sha256": "sha256:" + hashlib.sha256(data).hexdigest()},
           "events": {"scenes": scenes}}
    return doc, sorted(dropped)


def main(argv=None, prog=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog=prog, description="导出分集计划的 events（给冷读包；去掉 saysFact 等设计字段）")
    ap.add_argument("episode_plan")
    ap.add_argument("--out", default=None, help="写到这个文件（如 .drama/checks/events-ep001.json）；不给则打印")
    args = ap.parse_args(argv)
    try:
        with open(args.episode_plan, "rb") as handle:
            data = handle.read()
        try:
            plan = json.loads(data.decode("utf-8"))
        except ValueError as error:
            raise L.InputError(f"分集计划不是合法 JSON：{error}") from None
        if not isinstance(plan, dict):
            raise L.InputError("分集计划不是 JSON 对象")
        doc, dropped = export_events(plan, os.path.basename(args.episode_plan), data)
        body = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            if os.path.exists(args.out):
                with open(args.out, "r", encoding="utf-8") as handle:
                    if handle.read() != body:
                        raise L.InputError(f"{args.out} 已存在且内容不同；不覆盖，换一个文件名")
            else:
                with open(args.out, "w", encoding="utf-8") as handle:
                    handle.write(body)
    except (L.InputError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    L.emit({"ok": True, "episode": doc["episode"], "out": args.out, "scenes": len(doc["events"]["scenes"]),
            "beats": sum(len(s["beats"]) for s in doc["events"]["scenes"]), "dropped": dropped,
            **({} if args.out else {"export": doc}), "reproduceCommand": L.reproduce_command(__file__, argv)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
