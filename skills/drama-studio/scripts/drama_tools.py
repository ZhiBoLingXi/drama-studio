#!/usr/bin/env python3
"""Offline helpers. Never call a model, upload data or claim a remote connection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
import uuid

sys.dont_write_bytecode = True
from checks.dup_check import run_dup_check
from checks.episode_check import PRESETS, run_episode_check


def initialize(path: Path, title: str) -> dict:
    path = path.expanduser().absolute()
    if not title.strip():
        raise ValueError("Project title cannot be empty")
    path.mkdir(parents=True, exist_ok=False)
    for folder in (".drama", "research", "reference", "planning", "episodes", "reviews", "deliveries"):
        (path / folder).mkdir()
    state = {"schemaVersion": 1, "localId": str(uuid.uuid4()), "title": title,
             "remoteProjectId": None, "remoteTaskIds": [], "templateIds": [],
             "status": "local_workspace_only", "remoteVerification": "not_checked",
             "nextAction": "Clarify the current task and discover mali-story capabilities"}
    (path / ".drama" / "project.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path / "PROJECT.md").write_text(f"# {title}\n\n本地工作目录已建立。尚未连接远端项目、生成剧本或批准任何版本。\n", encoding="utf-8")
    return {"ok": True, "path": str(path), "state": state}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    init = commands.add_parser("init-project")
    init.add_argument("path", type=Path)
    init.add_argument("--title", required=True)
    episode = commands.add_parser("episode-check")
    episode.add_argument("path")
    episode.add_argument("--config", dest="config_path", help="Explicit project constraints JSON; never auto-discovered")
    episode.add_argument("--preset", choices=sorted(PRESETS), help="Opt-in historical example, not a quality standard")
    episode.add_argument("--min-rounds", type=int, help="Deprecated alias for --min-speaker-changes")
    for key in ("min-chars", "min-scenes", "min-speaker-changes", "max-locations"):
        episode.add_argument("--" + key, type=int)
    for key in ("min-delta-ratio", "min-paren-ratio"):
        episode.add_argument("--" + key, type=float)
    duplicate = commands.add_parser("dup-check")
    duplicate.add_argument("--new", nargs="+", required=True)
    duplicate.add_argument("--source", nargs="+", required=True)
    duplicate.add_argument("--k", nargs="+", type=int, default=[5, 8, 13])
    duplicate.add_argument("--threshold", type=float, default=40)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result = {"ok": sys.version_info >= (3, 10), "python": platform.python_version(),
                      "checks_imported": True, "network_used": False, "models_called": False,
                      "mali_story": "not_checked", "host_skill_discovery": "not_checked",
                      "review_status": "not_run"}
        elif args.command == "init-project":
            result = initialize(args.path, args.title)
        elif args.command == "episode-check":
            overrides = {k: v for k, v in vars(args).items() if k not in ("command", "path") and v is not None}
            result = run_episode_check(args.path, **overrides)
        else:
            result = run_dup_check(args.new, args.source, ks=args.k, threshold=args.threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if not result.get("ok") else (2 if result.get("passed") is False or result.get("constraint_status") == "not_evaluable" else 0)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
