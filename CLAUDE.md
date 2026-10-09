# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also `AGENTS.md` (shared repo rules) and `INSTALL.md` (the AI-facing install protocol). Project docs and skill content are written in Chinese; keep new user-facing text in Chinese to match.

## What this repo is

Drama Studio is a distributable AI skill (not an app) for Chinese short-drama (短剧/漫剧) creation: market research → benchmark selection → mali-story 拉片 templates → original topic → outline/characters/episode plan → scripts → review/revision. The model does the creative judgment; bundled Python scripts do only objectively computable checks; the human screenwriter makes approval decisions. mali-story (via MCP) owns remote tasks, billing and adopted story state.

## Commands

Python 3.10+ standard library only. No packages, no build step. Always pass `-B` (no bytecode).

```sh
python3 -B -m unittest discover -s tests -v          # all tests
python3 -B -m unittest discover -s tests -p test_distribution.py -k test_plan_does_not_write   # single test
python3 -B scripts/validate.py                        # syntax, Markdown links/code fences, bundle contents
```

Run both tests and `validate.py` after relevant changes.

Installer (`--host` is `codex | claude-code | workbuddy | chatgpt`; add `--scope project --project /abs/path`, `--upgrade`, or `--skills-dir`):

```sh
python3 -B scripts/install.py plan --host claude-code
python3 -B scripts/install.py install --host claude-code
python3 -B scripts/install.py verify --host claude-code
python3 -B scripts/install.py package --host workbuddy   # → dist/drama-studio-workbuddy.zip
```

Bundled local tools: `python3 -B skills/drama-studio/scripts/drama_tools.py {doctor|init-project|status|context-pack|contract-check|receipt|impact|episode-check|dup-check|reference-check|knowledge|import-project}` (see README for example invocations; SKILL.md lists every subcommand and `tests/test_skill_routing.py` keeps the two in sync).

## Architecture

- **`skills/drama-studio/` is the product.** It must stay self-contained: `SKILL.md` (router table mapping the current task stage to a `references/*.md` method doc), `references/` (loaded on demand), `templates/` (records the AI fills in), `scripts/` (offline tools). `schemas/` (D0 contract JSON Schemas). `validate.py` rejects bundled files that aren't `.md`/`.py`/`.json`, JSON that isn't a schema with matching `$id`, and any `/Users/` absolute path inside the bundle. Don't depend on the user's personal skills (DramaRewrite, DramaContinuation, etc.).
- **`scripts/install.py`** does receipt-based installs: it hashes the skill inventory, writes `.drama-studio-install.json` in the destination, and on `--upgrade` only replaces an install whose files still match the receipt (otherwise refuses; old version goes to a backup path). Never overwrite an unowned or user-modified skill directory. `package` injects WorkBuddy-specific frontmatter fields and refuses to silently overwrite a differing existing ZIP. `validate.py` imports `inventory`/`SOURCE` from it.
- **`drama_tools.py`** dispatches to `scripts/checks/{episode_check,dup_check,reference_check}.py` and prints JSON. Exit-code contract (callers must read the structured status, not just the code): `0` completed (possibly statistics only), `1` input/execution error, `2` explicit constraint failed / not evaluable, dup-check failed, or reference coverage `needs_review`.
- **Workstation contracts (C1–C6, v0.1)** live in `references/workstations/` and are the default writing path: `references/writing.md` opens with the workstation steps and the offline fallback, `references/workstations/season-run.md` covers multi-batch runs. Handoff objects (task, knowledge-card, context-snapshot, review-record, run-handoff, remote-receipt) are validated by `contract-check` (`checks/contract_check.py`: a stdlib JSON Schema subset plus cross-field rules). Each invariant is labelled S (script-enforced), R (mali-story server-enforced) or M (model convention); only S/R may appear in acceptance criteria. Examples in `skills/drama-studio/schemas/examples/` must keep passing (`tests/test_contracts.py` asserts one example per schema).
- **episode-check is statistics-only by default** (`constraint_status: not_configured`, `passed: null`). Constraints apply only via explicit `--config`, explicit threshold flags, or `--preset legacy-aigc`; configs are never auto-discovered. Scene headings accept `场11-1 ...` and `### 11-1 ...`; code-fenced content is ignored.
- `tests/` loads `scripts/install.py` via importlib and runs `drama_tools.py` as a subprocess against temp dirs.
- `evals/` holds scenario fixtures and recorded eval runs (human-read, not automated tests). `docs/` holds design/refactor plans. Current authority: `docs/design/drama-studio-system-architecture-2026-09-29.md` (v1.2: every piece of content is a mali-story page with Feishu-like revisions; a new revision is current at once, acceptance is a revision label, rollback is restore; no local version store) and the implementation roadmap (phases D0–D5). Pre-migration story-artifact candidates stay readable. Evidence per phase is in `docs/d0/`–`docs/d5/`; D0–D4 are done, D3 refined and compressed 《渊心锁》 1–60. The R0–R7 task packs in `docs/refactor-stages-2026-09-28/` are `planned` designs, not implemented features.
- `projects/` (user drama workspaces) and `dist/` are gitignored. Keep user projects, private references, credentials and videos out of the distribution.

## Rules that matter here

- Honesty of status is a core design principle: tools and docs must not claim MCP connectivity, remote success, quality approval or originality that wasn't verified (`doctor` reports `mali_story: not_checked`; low literal duplication ≠ originality). Preserve these `not_checked`/`null` semantics when editing.
- Do not introduce provider credentials, network calls or a model runtime into the local tools.
- Installation is not permission to create stories, upload videos or start paid tasks. Discover live mali-story capabilities before use; source code is not deployment evidence.
- Report installation, host discovery, MCP authorization, business reads and end-to-end creative acceptance separately.
- Document new commands in README.md. Keep Markdown links valid (validate.py checks them).
