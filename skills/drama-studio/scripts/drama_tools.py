#!/usr/bin/env python3
"""Offline helpers. Never call a model, upload data or claim a remote connection."""
from __future__ import annotations

import argparse
import contextlib
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import platform
import shlex
import sys
import uuid

sys.dont_write_bytecode = True
from checks.contract_check import question_sets, run_contract_check, schema_names
from checks.context_pack import run_context_pack
from checks.dup_check import run_dup_check
from checks.episode_check import PRESETS, run_episode_check
from checks.import_project import PRODUCERS, run_apply, run_preview
from checks.knowledge_store import run_knowledge_search, run_knowledge_show, run_knowledge_validate
from checks.project_status import render_status, run_impact, run_status
from checks.reference_check import run_reference_check
from checks.season_check import run_season_check
from checks.receipt import EXPECTED as RECEIPT_OPERATIONS, KINDS as ARTIFACT_KINDS, run_receipt


def initialize(path: Path, title: str) -> dict:
    path = path.expanduser().absolute()
    if not title.strip():
        raise ValueError("Project title cannot be empty")
    path.mkdir(parents=True, exist_ok=False)
    for folder in (".drama", "research", "reference", "planning", "episodes", "reviews", "deliveries"):
        (path / folder).mkdir()
    # D6-2 layout (decisions §1, §5 #23). .drama/ keeps only project.json: status reads an empty .drama/ as a new
    # project, so .drama/runs/ appears with the first run-handoff
    for folder in ("planning/ledger", "planning/episodes", "runs", "knowledge"):
        (path / folder).mkdir()
    state = {"schemaVersion": 1, "localId": str(uuid.uuid4()), "title": title,
             "remoteProjectId": None, "remoteTaskIds": [], "templateIds": [],
             "status": "local_workspace_only", "remoteVerification": "not_checked",
             "nextAction": "Clarify the current task and discover mali-story capabilities"}
    (path / ".drama" / "project.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path / "PROJECT.md").write_text(f"# {title}\n\n本地工作目录已建立。尚未连接远端项目、生成剧本或批准任何版本。\n", encoding="utf-8")
    return {"ok": True, "path": str(path), "state": state}


# D6-1 commands that live in their own modules: drama_tools subcommand -> (module, leading argv it adds)
DELEGATED = {
    "ledger": ("checks.ledger", "Ledger: init/merge/apply/replay/check/diff/knows/view/stats; S rules only"),
    "plan-check": ("checks.plan_check", "Episode-plan S check (presence, speaker-knows, delta support); --characters reports, never blocks"),
    "plan-events": ("checks.plan_events", "Export an episode plan's events only (no saysFact or design fields) for the cold_reader package"),
    "season-plan-check": ("checks.season_plan_check", "Season-plan S check against the function map, capacity and decision queue"),
    "capacity": ("checks.capacity", "Capacity season/episode/text: one formula, both bases reported; exceeding writes a proposal and still exits 0"),
    "decision": ("checks.decision", "Decision queue add/list/decide/check; every pending entry carries a default, decide needs humanWords"),
    "function-map": ("checks.function_map", "Function map check/merge/topics (retrieval topics from required_unstated procedure deps)"),
    "defects": ("checks.function_map", "defects build: derive the defect register from answer records (the records stay the only source)"),
    "check-answers": ("checks.answers_check", "Answer-record format against its question set; coverage and --cross reports never block"),
    "retell-check": ("checks.retell_check", "Cold retell against the plan's infoLedger facts and closing event: retold/partial/missing"),
    "answers-consistency": ("checks.consistency", "Two answer records on the same target: where their three-state answers differ (reports only)"),
    "dialogue-plan-check": ("checks.dialogue_plan_check", "Dialogue-plan S check (segments, closers, carries, listenerKnows from the ledger)"),
    "plan-text-consistency": ("checks.plan_text_consistency", "Text against its dialogue plan: speakers, topic boundaries, closers, carried keywords"),
    "dialogue-diagnose": ("checks.diagnose", "Dialogue signals with position and situation; no within/outside verdicts"),
    "feedback-ingest": ("checks.feedback_ingest", "Writer feedback -> writer-note records routed by level (derivatives are drafts)"),
    "corpus": ("checks.corpus", "Corpus S commands: segment/label/agree/filter/lexicon/rate/defaults, and fetch bookkeeping; offline"),
}
CORPUS_COMMANDS = ("segment", "label", "agree", "filter", "lexicon", "rate", "defaults", "fetch")
TOOL = Path(__file__).resolve()


def reproduce(words: list[str], argv: list[str]) -> str:
    """A runnable drama_tools command line; arguments naming existing files become absolute paths."""
    tokens = [os.path.abspath(arg) if not arg.startswith("-") and os.path.exists(arg) else arg for arg in argv]
    return shlex.join(["python3", "-B", str(TOOL), *words, *tokens])


def delegate(argv: list[str]) -> int:
    """Run a D6-1 module command and print its output with reproduceCommand in drama_tools form."""
    command, rest = argv[0], argv[1:]
    words, module = [command], DELEGATED.get(command, ("checks.dup_check",))[0]
    if command == "corpus":
        if not rest or rest[0] not in CORPUS_COMMANDS:
            print(json.dumps({"ok": False, "error": f"corpus needs one of: {', '.join(CORPUS_COMMANDS)}"}, ensure_ascii=False), file=sys.stderr)
            return 1
        module, words, rest = f"checks.corpus.{rest[0]}", [command, rest[0]], rest[1:]
    elif command == "defects":
        rest = ["defects", *rest]
        words = []
    entry = importlib.import_module(module).main
    prog = " ".join(["drama_tools.py", *words])
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            code = entry(rest, prog=prog) if "prog" in inspect.signature(entry).parameters else entry(rest)
        except SystemExit as stop:  # argparse --help or a usage error
            code = stop.code if isinstance(stop.code, int) else 1
    output = buffer.getvalue()
    try:
        result = json.loads(output)
    except ValueError:
        result = None
    if isinstance(result, dict) and "reproduceCommand" in result:
        result["reproduceCommand"] = reproduce(words, rest)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.write(output)
    return code


def contract_context(args) -> dict | None:
    """Cross-file context for contract-check rules a single file cannot settle; None when no flag was given."""
    if not any((args.records, args.defects, args.cards, args.questions, args.base_questions, args.decisions)):
        return None
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    context: dict = {}
    if args.records:
        context["records"] = {doc["checkId"]: doc for doc in map(load, args.records) if isinstance(doc, dict) and "checkId" in doc and "answers" in doc}
    if args.defects:
        kinds: dict[str, set] = {}
        for doc in map(load, args.defects):
            items = [(a, "defectKey") for a in doc.get("answers") or []] + [(d, "defectId") for d in doc.get("defects") or []] \
                if isinstance(doc, dict) else []
            for item, key in items:
                if isinstance(item, dict) and item.get(key):
                    kind = item.get("defectKind") or []
                    kinds.setdefault(item[key], set()).update([kind] if isinstance(kind, str) else kind)
        context["defectKinds"] = {key: sorted(value) for key, value in kinds.items()}
    if args.cards:
        paths = [p for arg in args.cards for p in (sorted(Path(arg).glob("*.json")) if Path(arg).is_dir() else [Path(arg)])]
        context["cards"] = {doc["cardId"]: doc.get("coverage") for doc in map(load, paths) if isinstance(doc, dict) and "cardId" in doc}
    if args.questions:
        context["questionSets"] = {**question_sets(), **{f"{doc['id']}@{doc['version']}": doc for doc in map(load, args.questions)}}
    if args.base_questions:
        context["baseQuestionSet"] = load(args.base_questions)
    if args.decisions:
        context["decisionIds"] = {e.get("id") for doc in map(load, args.decisions) if isinstance(doc, dict)
                                  for e in doc.get("entries") or [] if isinstance(e, dict)}
    return context


def main() -> int:
    argv = sys.argv[1:]
    if argv and (argv[0] in DELEGATED or (argv[0] == "dup-check" and "--list-hits" in argv)):
        try:
            return delegate(argv)
        except (OSError, ValueError) as error:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
            return 1
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
    episode.add_argument("--speech", action="store_true", help="Add per-episode speech volume (spoken Han chars); no time estimate, that is capacity text")
    duplicate = commands.add_parser("dup-check", help="Literal n-gram overlap; not an originality certificate")
    duplicate.add_argument("--new", nargs="+", required=True)
    duplicate.add_argument("--source", nargs="+", required=True)
    duplicate.add_argument("--k", nargs="+", type=int, default=[5, 8, 13])
    duplicate.add_argument("--threshold", type=float, default=40)
    duplicate.add_argument("--list-hits", action="store_true", help="List each k-char hit with its line instead of rates: --new one file, --k one size (8 for packed samples, 13 for the whole corpus)")
    duplicate.add_argument("--source-dialogue-plan", help="--list-hits pool: the corpus samples a dialogue plan packed")
    duplicate.add_argument("--source-corpus-jsonl", help="--list-hits pool: every line of a corpus exchanges.jsonl")
    duplicate.add_argument("--exclude-verbatim", help="--list-hits: plan-text map whose verbatimFrom lines are listed apart")
    reference = commands.add_parser("reference-check", help="Inspect saved template detail coverage, not source truth")
    reference.add_argument("path")
    reference.add_argument("--expected-episodes", type=int)
    contract = commands.add_parser("contract-check", help="Validate a workstation handoff object; shape and script rules only (examples in schemas/examples/)")
    contract.add_argument("contract", choices=schema_names())
    contract.add_argument("path")
    contract.add_argument("--records", nargs="+", help="Answer records a function map's selected candidates cite (inquiryRef)")
    contract.add_argument("--defects", nargs="+", help="Answer records or defect registers giving each defectKey its defectKind")
    contract.add_argument("--cards", nargs="+", help="Knowledge cards (files or folders): an empty card cannot back a holds answer")
    contract.add_argument("--questions", nargs="+", help="Project question sets (id@version) besides the bundled ones")
    contract.add_argument("--base-questions", help="The bundled question set a project set extends (may add, not remove)")
    contract.add_argument("--decisions", nargs="+", help="Decision queues: a run-handoff's decisionRefs must name their entries")
    pack = commands.add_parser("context-pack", help="Assemble a reproducible context-snapshot from local cache and knowledge cards; never truncates or goes online")
    pack.add_argument("project")
    pack.add_argument("--task", required=True)
    pack.add_argument("--selection", required=True)
    pack.add_argument("--role", required=True, choices=["author", "dialogue_author", "reader_effect", "dialogue_read", "fact_check", "similarity_review", "evaluation",
                                                        "function_mapper", "ledger_keeper", "season_planner", "dialogue_designer", "situation_checker", "cold_reader"])
    pack.add_argument("--budget", required=True, type=int, help="Character budget; exceeding it exits 2 without writing")
    pack.add_argument("--dry-run", action="store_true", help="Run every check and print the package; write nothing")
    pack.add_argument("--allow-unverified", action="store_true", help="Accept manifest entries marked verified: false and note them in unknowns")
    pack.add_argument("--exemplars", help="C5a/C5b: masked sample records to pack the plan's cited positives from -- a JSONL file, or the dialogue plan itself (its exemplars.positives); inside the project")
    pack.add_argument("--contrast-pairs", help="C5a/C5b: contrast-pairs.jsonl (inside the project) to pack the plan's cited pairs from")
    pack.add_argument("--studio-corpus", help="C5a/C5b: the studio corpus folder (<studio root>/corpus/, beside STUDIO.md); --exemplars may then be a file in it, whose records must be scope.level studio from a mali-story template")
    pack.add_argument("--quotes-per-topic", type=int, default=2, help="C5a/C5b: masked original lines (maskedLines) a topic's samples may carry in all, default 2; 0 for none")
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
    record.add_argument("--reconciles", help="requestId of the unknown save or page write this confirmed get, list or identical re-send resolves")
    pending = receipt_commands.add_parser("pending", help="List unknown receipts and the reconciliation calls to make")
    pending.add_argument("project")
    cache = receipt_commands.add_parser("cache", help="Cache full read_page (or legacy read_story_artifact) text into .drama/cache and append the manifest")
    cache.add_argument("project")
    cache.add_argument("responses", nargs="+", help="All read_page chunks of one page revision, or all read_story_artifact chunks (and optionally one get_story_artifact response)")
    cache.add_argument("--slot")
    cache.add_argument("--kind", choices=ARTIFACT_KINDS)
    cache.add_argument("--episode-ref")
    cache.add_argument("--title", help="read_page only: the page title as the host knows it (page tools return no title); defaults to a local create_page receipt's title")
    show = receipt_commands.add_parser("show", help="Print one receipt and its contract-check result")
    show.add_argument("project")
    show.add_argument("request_id")
    importer = commands.add_parser("import-project", help="Plan saving old local drafts as mali-story candidates; never calls MCP")
    import_commands = importer.add_subparsers(dest="import_command", required=True)
    preview = import_commands.add_parser("preview", help="Read-only: map local drafts to slot/kind/episode_ref and report remote conflicts")
    apply = import_commands.add_parser("apply", help="Write one save_story_artifact input JSON per non-conflicting draft into --out only")
    for sub in (preview, apply):
        sub.add_argument("project")
        sub.add_argument("--listing", action="append", required=True,
                         help="Saved list_story_artifacts response (no kind/slot filter); repeat once per page")
    apply.add_argument("--out", required=True, help="Folder for the request files; nothing else is written")
    apply.add_argument("--producer", required=True, choices=PRODUCERS)
    apply.add_argument("--input-snapshot-id", required=True, help="snapshotId of the get_writing_context read (sha256:<hex>)")
    status = commands.add_parser("status", help="Next step from local receipts, runs and snapshots; read-only, reads no chat history, proves nothing remote")
    status.add_argument("project")
    status.add_argument("--json", action="store_true", help="Print JSON instead of text whose first line is the next action")
    season = commands.add_parser("season-check", help="Per-episode evidence that a season run followed the workstation flow; read-only, judges records not writing")
    season.add_argument("project")
    season.add_argument("--episodes", help="Written episodes to check: N or A-B, e.g. 31-80")
    season.add_argument("--outline", help="Episode outlines to check: N or A-B, e.g. 11-60")
    season.add_argument("--outline-batch", type=int, default=15, help="Most outlines one C4 run may write (default 15)")
    season.add_argument("--batch-size", type=int, default=10, help="Most episodes one first read may cover (default 10)")
    season.add_argument("--skip-dialogue", action="store_true", help="Leave out the voice-card, dialogue-pass and dialogue-read checks (recorded in the output)")
    season.add_argument("--legacy-dialogue", action="store_true", help="Also run voice-card, dialogue-pass and dialogue-read on old records (retired in D6-3); output then equals 0.3.6")
    season.add_argument("--revise", action="store_true", help="A feedback revision of an existing full draft: batches may share one author run and the entry-state rules do not apply")
    season.add_argument("--since", help="Only count C4-C6 runs finished at or after this ISO time (one version of a project revised several times)")
    season.add_argument("--allow-offline", action="store_true", help="Only when the user agreed to an offline run: not_sent saves warn instead of fail while no remote project is bound")
    impact = commands.add_parser("impact", help="Mark snapshots and runs stale/unknown/current for a slot or page revision; read-only, implicit content dependencies not assessed")
    impact.add_argument("project")
    impact.add_argument("--slot", help="Target slot; needs --revision")
    impact.add_argument("--revision", help="The slot's or page's new revision (integer >= 1)")
    impact.add_argument("--artifact", help="artifactId of the new revision, resolved through the cache manifest; excludes --slot/--revision")
    impact.add_argument("--card", help="Only snapshots and runs packing this knowledge card, judged on it alone; excludes --slot/--revision/--artifact")
    impact.add_argument("--page", help="pageId of a mali-story page; with --revision marks snapshots and runs pinning an older revision stale; excludes --slot/--artifact/--card")
    for name, (_, text) in DELEGATED.items():
        commands.add_parser(name, help=text, add_help=False)
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
            context = contract_context(args)
            result = run_contract_check(args.contract, args.path, context)
            if context is not None:
                flags = [token for flag in ("records", "defects", "cards", "questions", "decisions") if getattr(args, flag)
                         for token in ["--" + flag, *getattr(args, flag)]]
                flags += ["--base-questions", args.base_questions] if args.base_questions else []
                result["reproduceCommand"] = reproduce(["contract-check", args.contract], [args.path, *flags])
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
                                      dry_run=args.dry_run, allow_unverified=args.allow_unverified,
                                      exemplars=args.exemplars, contrast_pairs=args.contrast_pairs,
                                      quotes_per_topic=args.quotes_per_topic, studio_corpus=args.studio_corpus)
        elif args.command == "import-project" and args.import_command == "preview":
            result = run_preview(args.project, args.listing)
        elif args.command == "import-project":
            result = run_apply(args.project, args.listing, args.out, args.producer, args.input_snapshot_id)
        elif args.command == "receipt":
            result = run_receipt(args)
        elif args.command == "status":
            result = run_status(args.project)
            if not args.json:
                print(render_status(result))
                return 0
        elif args.command == "season-check":
            result = run_season_check(args.project, args.episodes, args.batch_size, args.allow_offline, args.outline, args.outline_batch, args.skip_dialogue, args.revise, args.since,
                                      args.legacy_dialogue)
        elif args.command == "impact":
            result = run_impact(args.project, args.slot, args.revision, args.artifact, args.card, args.page)
        else:
            result = run_dup_check(args.new, args.source, ks=args.k, threshold=args.threshold)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if not result.get("ok") else (2 if result.get("passed") is False or result.get("constraint_status") == "not_evaluable" or result.get("coverage_status") == "needs_review" else 0)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
