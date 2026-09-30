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
from checks.contract_check import run_contract_check, schema_names
from checks.context_pack import run_context_pack
from checks.dup_check import run_dup_check
from checks.episode_check import PRESETS, run_episode_check
from checks.knowledge_store import run_knowledge_search, run_knowledge_show, run_knowledge_validate
from checks.reference_check import run_reference_check
from checks.receipt import EXPECTED as RECEIPT_OPERATIONS, KINDS as ARTIFACT_KINDS, run_receipt


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
    commands.add_parser("doctor", help="Check the offline tools load; proves nothing about MCP")
    init = commands.add_parser("init-project", help="Create a local project workspace only")
    init.add_argument("path", type=Path)
    init.add_argument("--title", required=True)
    episode = commands.add_parser("episode-check", help="Episode statistics; constraints only when explicitly configured")
    episode.add_argument("path")
    episode.add_argument("--config", dest="config_path", help="Explicit project constraints JSON; never auto-discovered")
    episode.add_argument("--preset", choices=sorted(PRESETS), help="Opt-in historical example, not a quality standard")
    episode.add_argument("--min-rounds", type=int, help="Deprecated alias for --min-speaker-changes")
    for key in ("min-chars", "min-scenes", "min-speaker-changes", "max-locations"):
        episode.add_argument("--" + key, type=int)
    for key in ("min-delta-ratio", "min-paren-ratio"):
        episode.add_argument("--" + key, type=float)
    duplicate = commands.add_parser("dup-check", help="Literal n-gram overlap; not an originality certificate")
    duplicate.add_argument("--new", nargs="+", required=True)
    duplicate.add_argument("--source", nargs="+", required=True)
    duplicate.add_argument("--k", nargs="+", type=int, default=[5, 8, 13])
    duplicate.add_argument("--threshold", type=float, default=40)
    reference = commands.add_parser("reference-check", help="Inspect saved template detail coverage, not source truth")
    reference.add_argument("path")
    reference.add_argument("--expected-episodes", type=int)
    contract = commands.add_parser("contract-check", help="Validate a workstation handoff object; shape and script rules only (examples in schemas/examples/)")
    contract.add_argument("contract", choices=schema_names())
    contract.add_argument("path")
    pack = commands.add_parser("context-pack", help="Assemble a reproducible context-snapshot from local cache and knowledge cards; never truncates or goes online")
    pack.add_argument("project")
    pack.add_argument("--task", required=True)
    pack.add_argument("--selection", required=True)
    pack.add_argument("--role", required=True, choices=["author", "reader_effect", "fact_check", "similarity_review", "evaluation"])
    pack.add_argument("--budget", required=True, type=int, help="Character budget; exceeding it exits 2 without writing")
    pack.add_argument("--dry-run", action="store_true", help="Run every check and print the package; write nothing")
    pack.add_argument("--allow-unverified", action="store_true", help="Accept manifest entries marked verified: false and note them in unknowns")
    knowledge = commands.add_parser("knowledge", help="Read-only project-private knowledge cards: validate, search, show")
    knowledge_commands = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_commands.add_parser("validate", help="contract-check every card and its filename").add_argument("project")
    search = knowledge_commands.add_parser("search", help="Latest valid revisions; same-source marked; retired excluded by default")
    search.add_argument("project")
    search.add_argument("--type", dest="knowledge_type", choices=[f"K{i}" for i in range(1, 10)])
    search.add_argument("--workstation", choices=[f"C{i}" for i in range(1, 7)])
    search.add_argument("--usage", choices=["creative_reference", "comparison_only", "evaluation_only"])
    search.add_argument("--text", help="Case-insensitive substring over cardId, content and transfer")
    search.add_argument("--include-retired", action="store_true")
    show = knowledge_commands.add_parser("show", help="Print one card and check its local source files exist")
    show.add_argument("project")
    show.add_argument("card_id")
    show.add_argument("--revision", type=int)
    receipt = commands.add_parser("receipt", help="Turn saved mali-story MCP responses into receipts and cached text; never calls MCP or proves adoption")
    receipt_commands = receipt.add_subparsers(dest="receipt_command", required=True)
    record = receipt_commands.add_parser("record", help="Write .drama/receipts/<requestId>.json from a saved response (append-only)")
    record.add_argument("project")
    record.add_argument("response", help="Saved MCP response JSON; missing or unreadable means outcome unknown")
    record.add_argument("--operation", required=True, choices=sorted(RECEIPT_OPERATIONS))
    record.add_argument("--request-id", required=True)
    record.add_argument("--input", required=True, dest="input_path", help="The exact JSON input sent to the MCP tool")
    record.add_argument("--reconciles", help="requestId of the unknown receipt this get/list call resolves")
    pending = receipt_commands.add_parser("pending", help="List unknown receipts and the reconciliation calls to make")
    pending.add_argument("project")
    cache = receipt_commands.add_parser("cache", help="Cache full read_story_artifact text into .drama/cache and append the manifest")
    cache.add_argument("project")
    cache.add_argument("responses", nargs="+", help="All read chunks (and optionally one get_story_artifact response)")
    cache.add_argument("--slot")
    cache.add_argument("--kind", choices=ARTIFACT_KINDS)
    cache.add_argument("--episode-ref")
    show = receipt_commands.add_parser("show", help="Print one receipt and its contract-check result")
    show.add_argument("project")
    show.add_argument("request_id")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result = {"ok": sys.version_info >= (3, 10), "python": platform.python_version(),
                      "checks_imported": True, "network_used": False, "models_called": False,
                      "mali_story": "not_checked", "host_skill_discovery": "not_checked",
                      "review_status": "not_run", "contracts": schema_names()}
        elif args.command == "init-project":
            result = initialize(args.path, args.title)
        elif args.command == "episode-check":
            overrides = {k: v for k, v in vars(args).items() if k not in ("command", "path") and v is not None}
            result = run_episode_check(args.path, **overrides)
        elif args.command == "contract-check":
            result = run_contract_check(args.contract, args.path)
        elif args.command == "knowledge" and args.knowledge_command == "validate":
            result = run_knowledge_validate(args.project)
        elif args.command == "knowledge" and args.knowledge_command == "search":
            result = run_knowledge_search(args.project, args.knowledge_type, args.workstation, args.usage,
                                          args.text, args.include_retired)
        elif args.command == "knowledge":
            result = run_knowledge_show(args.project, args.card_id, args.revision)
        elif args.command == "reference-check":
            result = run_reference_check(args.path, args.expected_episodes)
        elif args.command == "context-pack":
            result = run_context_pack(args.project, args.task, args.selection, args.role, args.budget,
                                      dry_run=args.dry_run, allow_unverified=args.allow_unverified)
        elif args.command == "receipt":
            result = run_receipt(args)
        else:
            result = run_dup_check(args.new, args.source, ks=args.k, threshold=args.threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if not result.get("ok") else (2 if result.get("passed") is False or result.get("constraint_status") == "not_evaluable" or result.get("coverage_status") == "needs_review" else 0)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
