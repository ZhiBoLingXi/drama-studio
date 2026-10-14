"""Check that a run of episodes followed the season workstation flow, from the project's local records only.

`season-check` reads `<project>/.drama/` (runs, snapshots, reviews, receipts) and, for every episode in the range,
looks for the evidence `references/workstations/season-run.md` asks for: upstream C1-C4 runs, one author run per
episode whose package holds that episode's plan, the newest text of the episode before it and the state record after
it, sealed first and second reads, at most one directed revision, and a confirmed save receipt for the final text.
It never reads the texts' meaning, the network or chat history: passing proves the records are complete and
consistent, not that the writing is good or that the remote holds them.

Two rule sets live side by side (D6-1). `--outline` runs the outline-layer rules on top of the old ones only when the
project has `planning/season-plan.json`; `--episodes` runs the dialogue-layer rules instead of voice-card,
dialogue-pass and dialogue-read only when the project has a dialogue-plan record, and says so with `ruleSet:
outline-layer` / `episodeRuleSet: dialogue-layer`. Otherwise neither key appears and the output is the 0.3.6 output. The new rules read records from `planning/`, `.drama/checks/` and
`.drama/tasks/` (any depth), recognised by their schema marker or by the drama_tools command in their reproduceCommand.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex

from .contract_check import blocklist_hits, check_contract, finished_at
from .receipt import area, contained, drama_dir

NOTE = ("只核对 .drama/ 里的记录是否齐全、彼此一致；不判断正文质量，不联网，也不证明远端已保存。"
        "通过不等于“写得好”，失败的条目在补齐证据或重做之前，不能在交付说明里写“已按流程完成”。")
EPISODE = re.compile(r"(?:^|[^a-z])(?:ep|episode|outline)[-_]?0*(\d{1,4})(?!\d)|第0*(\d{1,4})集")
STATE = re.compile(r"^(?:runs|\.drama)/state/after-ep-0*(\d{1,4})\.md$")
UPSTREAM = ("C1", "C2", "C3")
# a dialogue line: a short speaker name, an optional bracketed direction, a colon, then the words
SPEAKER = re.compile(r"^\s*([^\s:：（(#*|>\-△▲【\[]{1,10})\s*(?:[（(][^）)\n]{0,40}[）)])?\s*[:：]\s*\S")
HEADING = re.compile(r"^\s*(#{1,6}\s|场\s*\d|[｜|])")  # episode titles and scene headings
NOT_SPEAKERS = {"人物", "出场人物", "地点", "时间", "场景", "道具", "字幕", "标题", "备注", "注", "特写", "画面", "镜头", "旁白", "音效", "闪回", "转场"}
VOICED_FROM = 3  # a speaker with this many lines in an episode needs a voice card
LAYER_DIRS = ("planning", ".drama/checks", ".drama/tasks")  # where the D6 records are looked up
SEASON_PLAN = "planning/season-plan.json"
# schema markers written two ways in D6-0 (drama-studio/<kind>/v0, <kind>/v0-pilot) and their aliases
MARKER = re.compile(r"^(?:drama-studio/)?([a-z][a-z-]*)/v")
MARKER_KINDS = {"dialogue-check": "answers", "reality-check": "answers", "decisions": "decision-queue", "ledger": "ledger-entry"}
# saved tool output, recognised by the drama_tools subcommand (or the module) in its reproduceCommand
COMMAND_KINDS = {"plan-text-consistency": "plan-text-consistency", "plan_text_consistency.py": "plan-text-consistency",
                 "answers-consistency": "consistency", "consistency.py": "consistency",
                 "lexicon": "genre-scan", "lexicon.py": "genre-scan", "retell-check": "retell-check",
                 "dup-check": "dup-hits", "dup_check.py": "dup-hits"}
NAME_FIELDS = ("textFile", "text", "file", "fileA", "plan")


def _speaker(line: str) -> str | None:
    match = SPEAKER.match(line)
    return match.group(1) if match and match.group(1) not in NOT_SPEAKERS else None


def _read_ref(root: Path, ref: dict) -> str | None:
    """The text a run output points at: a project file, or the cached page revision; None when it cannot be read."""
    if ref.get("kind") == "local_file":
        path = root / ref["id"]
    elif ref.get("kind") == "remote_page" and isinstance(ref.get("revision"), int):
        path = root / ".drama" / "cache" / f"{ref['id']}@r{ref['revision']}.md"
    else:
        return None
    try:
        return path.read_text(encoding="utf-8") if path.resolve().is_relative_to(root.resolve()) and path.is_file() else None
    except (OSError, ValueError):
        return None


def _voice_text(root: Path, items: list[dict]) -> str:
    """Everything the packed K5 (language and expression) cards say, to look speakers' names up in."""
    found = []
    for item in items:
        ref = item["ref"]
        if ref.get("kind") != "knowledge_card":
            continue
        try:
            card = json.loads((root / "knowledge" / "cards" / f"{ref['id']}@r{ref['revision']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if card.get("knowledgeType") == "K5":
            found.append(json.dumps(card.get("content"), ensure_ascii=False))
    return "\n".join(found)


def _episode_of_name(name: str) -> int | None:
    match = EPISODE.search(PurePosixPath(name).name.lower())
    return int(match.group(1) or match.group(2)) if match else None


def _load_folder(drama: Path, name: str, contract: str, problems: list) -> list[tuple[Path, dict, bytes]]:
    folder = area(drama, name)
    found = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = contained(path, drama).read_bytes()
            doc = json.loads(data.decode("utf-8"))
        except (OSError, ValueError) as error:
            problems.append({"scope": f".drama/{name}/{path.name}", "rule": "record", "message": f"无法读取：{error}"})
            continue
        errors = check_contract(contract, doc)
        if errors:
            problems.append({"scope": f".drama/{name}/{path.name}", "rule": "record",
                             "message": f"contract-check {contract} 不通过：" + "; ".join(errors)})
            continue
        found.append((path, doc, data))
    return found


def _pages(receipts: list[dict]) -> dict[str, dict]:
    """pageId -> {episode, semantic} from the page writes' receipts (create_page records episodeRef and semantic)."""
    pages: dict[str, dict] = {}
    for doc in receipts:
        page = (doc.get("remote") or {}).get("pageId")
        if not page:
            continue
        try:
            notes = json.loads(doc.get("notes") or "{}")
        except ValueError:
            notes = {}
        info = pages.setdefault(page, {"episode": None, "semantic": None})
        ref = notes.get("episodeRef")
        if isinstance(ref, str) and re.fullmatch(r"ep-\d+", ref):
            info["episode"] = int(ref[3:])
        elif info["episode"] is None and isinstance(notes.get("title"), str):
            info["episode"] = _episode_of_name(notes["title"])
        info["semantic"] = notes.get("semantic") or info["semantic"]
    return pages


def _classify(ref: dict, partition: str | None, pages: dict) -> tuple[str, int | None]:
    """('state'|'plan'|'text'|'other', episode) for a snapshot item or run output."""
    kind, ident = ref.get("kind"), ref.get("id") or ""
    if kind == "local_file":
        state = STATE.match(ident)
        if state:
            return "state", int(state.group(1))
        episode = _episode_of_name(ident)
        if episode is None or ident.startswith(".drama/reviews/"):
            return "other", None
        plan = partition == "current_plan" or "outline" in PurePosixPath(ident).name.lower()
        return ("plan" if plan else "text"), episode
    if kind == "remote_page":
        info = pages.get(ident)
        if not info or info["episode"] is None:
            return "other", None
        if info["semantic"] == "episode":
            return "text", info["episode"]
        return ("plan" if info["semantic"] in ("episode_outline", "outline", "synopsis") else "other"), info["episode"]
    return "other", None


def _same(a: dict, b: dict) -> bool:
    if a.get("kind") != b.get("kind") or a.get("id") != b.get("id"):
        return False
    return a.get("kind") != "remote_page" or a.get("revision") == b.get("revision")


def _range(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,4})\s*(?:-\s*(\d{1,4}))?\s*", text or "")
    if not match:
        raise ValueError("--episodes must be N or A-B (e.g. 31-80)")
    first, last = int(match.group(1)), int(match.group(2) or match.group(1))
    if first < 1 or last < first:
        raise ValueError("--episodes must be ascending and start at 1 or later")
    return first, last


def _ep_int(value) -> int | None:
    """6, "006", "6A", "ep006A" -> 6: split episodes (6A, 6B) belong to the episode number they split."""
    match = re.match(r"^(?:ep|episode)?[-_]?0*(\d{1,4})", str(value).strip().lower()) if value is not None else None
    return int(match.group(1)) if match else None


def _command(doc: dict) -> list[str]:
    try:
        return shlex.split(doc.get("reproduceCommand") or "")
    except ValueError:
        return []


def record_kind(doc) -> str | None:
    """The D6 object a record is: its schema marker, else the command that produced it."""
    if not isinstance(doc, dict):
        return None
    marker = doc.get("schemaVersion") or doc.get("schema")
    match = MARKER.match(marker) if isinstance(marker, str) else None
    if match:
        return MARKER_KINDS.get(match.group(1), match.group(1))
    tokens = _command(doc)
    for index, token in enumerate(tokens):
        name = PurePosixPath(token).name
        if name == "drama_tools.py":
            words = [t for t in tokens[index + 1:index + 3] if not t.startswith("-")]
            kind = next((COMMAND_KINDS[w] for w in words if w in COMMAND_KINDS), None)
        elif name in COMMAND_KINDS:
            kind = COMMAND_KINDS[name]
        else:
            continue
        return None if kind == "dup-hits" and "--list-hits" not in tokens else kind
    return None


def record_episode(doc: dict, name: str) -> int | None:
    """The episode a record belongs to: its own field, its target, the file it checked, or its file name."""
    target = doc.get("target") if isinstance(doc.get("target"), dict) else {}
    for value in (doc.get("episode"), target.get("episode")):
        if _ep_int(value) is not None:
            return _ep_int(value)
    tokens = _command(doc)
    named = [doc.get(key) for key in NAME_FIELDS] + [target.get("file")]
    named += [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == "--new"]
    for value in named:
        if isinstance(value, str) and _episode_of_name(value) is not None:
            return _episode_of_name(value)
    return _episode_of_name(name)


def layer_records(root: Path) -> dict[str, list[tuple[str, dict]]]:
    """kind -> [(project-relative path, document)] for every readable JSON record under LAYER_DIRS; unreadable files
    are skipped here (contract-check reports them), so a project without these folders reads as having none."""
    found: dict[str, list[tuple[str, dict]]] = {}
    for folder in LAYER_DIRS:
        base = root / folder
        if not base.is_dir() or not base.resolve().is_relative_to(root.resolve()):
            continue
        for path in sorted(base.rglob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            kind = record_kind(doc)
            if kind:
                found.setdefault(kind, []).append((path.relative_to(root).as_posix(), doc))
    return found


def run_season_check(project: str, episodes: str | None = None, batch_size: int = 10, allow_offline: bool = False,
                     outline: str | None = None, outline_batch: int = 15, skip_dialogue: bool = False,
                     revise: bool = False, since: str | None = None) -> dict:
    if episodes is None and outline is None:
        raise ValueError("give --episodes (written episodes) and/or --outline (episode outlines) as N or A-B")
    first, last = _range(episodes) if episodes is not None else (1, 0)
    outline_range = _range(outline) if outline is not None else None
    if batch_size < 1 or outline_batch < 1:
        raise ValueError("--batch-size and --outline-batch must be at least 1")
    drama = drama_dir(project)
    root = drama.parent
    failures: list[dict] = []
    warnings: list[dict] = []

    def fail(scope, rule, message):
        failures.append({"scope": scope, "rule": rule, "message": message})

    def warn(scope, rule, message):
        warnings.append({"scope": scope, "rule": rule, "message": message})

    runs = _load_folder(drama, "runs", "run-handoff", failures)
    snaps = {doc["snapshotId"]: (path, doc, data) for path, doc, data in _load_folder(drama, "snapshots", "context-snapshot", failures)}
    reviews = _load_folder(drama, "reviews", "review-record", failures)
    receipts = [doc for _, doc, _ in _load_folder(drama, "receipts", "remote-receipt", failures)]
    project_doc = {}
    try:
        project_doc = json.loads((drama / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        warn("project", "project", "读不出 .drama/project.json，按没有远端项目处理")
    remote_project = project_doc.get("remoteProjectId") if isinstance(project_doc, dict) else None
    pages = _pages(receipts)
    records = layer_records(root)
    outline_layer = outline_range is not None and (root / SEASON_PLAN).is_file()
    dialogue_layer = episodes is not None and bool(records.get("dialogue-plan"))

    # runs in finish order; a run without a valid finishedAt cannot be placed and fails
    ordered = []
    for path, doc, _ in runs:
        when = finished_at(doc.get("finishedAt"))
        if when is None:
            fail(f"run {doc['runId']}", "finished-at", "运行记录没有有效的 finishedAt，无法判断先后")
            continue
        ordered.append((when, doc))
    ordered.sort(key=lambda pair: pair[0])
    everything = ordered  # C1-C3 are looked up in the whole history; --since narrows the rest to one version's runs
    if since is not None:
        start = finished_at(since)
        if start is None:
            raise ValueError("--since must be an ISO 8601 time with an offset, e.g. 2026-10-11T19:00:00+08:00")
        ordered = [(when, doc) for when, doc in ordered if when >= start]

    # snapshot integrity: the .sha256 sidecar must match the bytes
    for snap_id, (path, doc, data) in snaps.items():
        sidecar = path.with_suffix(".sha256")
        recorded = sidecar.read_text(encoding="utf-8").split()[:1] if sidecar.is_file() else None
        if recorded != [hashlib.sha256(data).hexdigest()]:
            fail(f"snapshot {snap_id}", "snapshot-sealed", "快照缺少 .sha256 或与字节不符")

    def snapshot_items(run: dict) -> tuple[list[dict], list[str]]:
        items, missing = [], []
        for snap_id in [run["contextSnapshotId"], *run.get("additionalSnapshotIds", [])]:
            if snap_id in snaps:
                items += snaps[snap_id][1]["items"]
            else:
                missing.append(snap_id)
        return items, missing

    def role(run: dict) -> str | None:
        snap = snaps.get(run["contextSnapshotId"])
        return snap[1]["createdFor"]["role"] if snap else None

    def text_outputs(run: dict) -> dict[int, list[dict]]:
        found: dict[int, list[dict]] = {}
        for ref in run["outputs"]:
            kind, episode = _classify(ref, None, pages)
            if kind == "text" and episode is not None:
                found.setdefault(episode, []).append(ref)
        return found

    # usage copied between runs: identical measured usage on different runs is not a measurement
    seen_usage: dict[str, list[str]] = {}
    for _, run in ordered:
        usage = run["host"].get("usage")
        if isinstance(usage, dict) and any(usage.get(key) is not None for key in ("chars", "tokens")):
            seen_usage.setdefault(json.dumps(usage, sort_keys=True), []).append(run["runId"])
    for usage, ids in seen_usage.items():
        if len(ids) > 1:
            fail("runs " + ", ".join(ids), "usage-copied",
                 f"{len(ids)} 次运行的用量完全相同（{usage}），不是逐次实测；没实测就写 source: unknown，不填 chars/tokens")

    # upstream: C1-C3 once before the first author run, C4 per episode
    c5_runs = [(when, run) for when, run in ordered if run["workstation"] == "C5"]
    first_author = min((when for when, run in c5_runs if any(first <= n <= last for n in text_outputs(run))), default=None)
    for station in UPSTREAM if episodes is not None else ():
        if not any(run["workstation"] == station and (first_author is None or when <= first_author) for when, run in everything):
            fail(station, "upstream", f"没有 {station} 的运行交接；从集纲起步也要记录 {station}（采用用户给定材料时写明来源）")

    per_episode: dict[int, dict] = {}
    previous_state_sha: dict[int, str] = {}
    for n in range(first, last + 1):
        scope = f"第{n}集"
        entry = per_episode.setdefault(n, {})
        writers = [(when, run) for when, run in c5_runs if n in text_outputs(run)]
        c4 = [run["runId"] for when, run in ordered if run["workstation"] == "C4"
              and (revise or any(_classify(ref, None, pages)[1] == n for ref in run["outputs"]))
              and (not writers or when <= writers[0][0])]
        entry["c4Runs"] = c4
        if not c4:
            fail(scope, "c4", "没有覆盖本集的 C4 运行交接（集纲确认或修改单），且须早于作者运行")
        if not writers:
            fail(scope, "author", "没有产出本集正文的 C5 运行交接")
            continue
        author_when, author = writers[0]
        entry["authorRun"] = author["runId"]
        entry["revisionRuns"] = [run["runId"] for _, run in writers[1:]]
        written = sorted(text_outputs(author))
        if len(written) > 1 and not revise:
            fail(scope, "one-episode-per-author-run",
                 f"作者运行 {author['runId']} 一次写了 {len(written)} 集（{written[0]}–{written[-1]}），"
                 "批内应逐集写，前一集定稿后再给下一集装包")
        polish = [(at, run) for at, run in writers[1:] if role(run) == "dialogue_author"]
        if len(writers) - len(polish) > 2:
            warn(scope, "one-directed-revision", f"作者和台词遍之外又有 {len(writers) - len(polish) - 1} 次 C5 运行；每批只做一次定向修订，纠错重存除外")
        if role(author) != "author":
            fail(scope, "author-role", f"作者运行 {author['runId']} 的快照不是 author 包")
        items, missing = snapshot_items(author)
        if missing:
            fail(scope, "author-snapshot", f"作者运行引用的快照不存在：{', '.join(missing)}")
        classified = [(_classify(item["ref"], item["partition"], pages), item) for item in items]
        if not any(kind == "plan" and episode == n for (kind, episode), _ in classified) and not (
                revise and any(item["partition"] == "current_plan" for item in items)):
            fail(scope, "author-plan", "作者包里没有本集的集纲或修改单")
        # the newest text of n-1 that existed when the author started
        earlier = [run for when, run in ordered if when < author_when and n - 1 in text_outputs(run)]
        packed_prev = [item for (kind, episode), item in classified if kind == "text" and episode == n - 1]
        if n - 1 in written or revise:
            pass  # same run: reported by one-episode-per-author-run; a revision of a full draft has a fixed entry
        elif earlier:
            newest = text_outputs(earlier[-1])[n - 1][-1]
            if not packed_prev:
                fail(scope, "author-previous-text", f"作者包没有装第{n - 1}集正文（应装 {newest['id']}）")
            elif not any(_same(item["ref"], newest) for item in packed_prev):
                fail(scope, "author-previous-text", f"作者包装的第{n - 1}集不是当时的最新稿 {newest['id']}")
        elif not packed_prev and n > 1:
            (warn if n == first else fail)(scope, "author-previous-text",
                                           f"作者包没有第{n - 1}集正文；前文缺失要在状态记录里写明")
        states = [item for (kind, episode), item in classified if kind == "state" and episode == n - 1]
        if revise:
            pass  # the entry is the existing draft, not a state carried from the episode before
        elif not states:
            fail(scope, "author-state", f"作者包没有入口状态记录 runs/state/after-ep-{n - 1:03d}.md（谁知道什么、承诺与付款、物件、故事日）")
        else:
            previous_state_sha[n] = states[0]["sha256"]
            proposals = [p for when, run in ordered if when < author_when and n - 1 in text_outputs(run)
                         for p in run.get("stateChangeProposals", [])]
            if proposals and previous_state_sha.get(n - 1) == states[0]["sha256"]:
                fail(scope, "state-updated", f"第{n - 1}集有 {len(proposals)} 条状态变更，但入口状态记录与上一集用的完全相同，没有更新")
        # final text, its save receipt, and the reads
        final = text_outputs(writers[-1][1])[n][-1]
        entry["final"] = final["id"] + (f"@r{final['revision']}" if final.get("revision") is not None else "")
        saved = [r for r in receipts if (r.get("localRef") or {}).get("id") == final["id"]
                 or ((r.get("remote") or {}).get("pageId") == final["id"] and r["remote"].get("revision") == final.get("revision"))]
        outcomes = {r["outcome"] for r in saved}
        entry["receipt"] = sorted(outcomes) or None
        if "confirmed" in outcomes:
            pass
        elif "not_sent" in outcomes:
            message = ("最终稿只有 not_sent 回执，没写入 mali-story" +
                       ("；项目已绑定远端，必须保存" if remote_project else "；按路线图需先建远端项目，离线只用于临时断线"))
            (warn if allow_offline and not remote_project else fail)(scope, "saved", message)
        else:
            fail(scope, "saved", "最终稿没有 confirmed 保存回执" + ("（有未决回执，先对账）" if "unknown" in outcomes else ""))
        if dialogue_layer:
            _text_layer(scope, n, entry, records, writers, ordered, snapshot_items, role, pages, fail, warn)
        elif not skip_dialogue:
            _dialogue(scope, n, entry, root, writers, polish, ordered, final, items, snapshot_items, role, text_outputs, pages, fail)
        covering = []
        for path, review, data in reviews:
            refs = [review["target"], *review.get("additionalTargets", []), *review["readingScope"]]
            if any(_classify(ref, None, pages) == ("text", n) for ref in refs):
                covering.append((path, review, data))
        firsts = [c for c in covering if c[1]["firstReadWithoutAuthorNotes"]]
        seconds = [c for c in covering if not c[1]["firstReadWithoutAuthorNotes"]]
        entry["firstRead"] = [c[1]["reviewId"] for c in firsts]
        entry["secondRead"] = [c[1]["reviewId"] for c in seconds]
        if not firsts:
            fail(scope, "first-read", "没有首读记录（firstReadWithoutAuthorNotes: true）")
        unsealed = []
        for path, review, data in firsts:
            sidecar = path.with_suffix(".sha256")
            if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").split()[:1] != [hashlib.sha256(data).hexdigest()]:
                unsealed.append(review["reviewId"])
            targets = [review["target"], *review.get("additionalTargets", [])]
            size = len({_classify(ref, None, pages)[1] for ref in targets} - {None})
            if size > batch_size:
                fail(scope, "batch-size", f"首读 {review['reviewId']} 一次审 {size} 集，超过每批 {batch_size} 集")
        if firsts and len(unsealed) == len(firsts):
            fail(scope, "first-read-sealed", f"首读 {'、'.join(unsealed)} 没有封存或 .sha256 与字节不符")
        elif unsealed:
            warn(scope, "first-read-sealed", f"另有未封存的首读记录：{'、'.join(unsealed)}（多为旧版本的记录）")
        if not seconds:
            fail(scope, "second-read", "没有次读记录（带集纲、规则和状态记录的第二次审读）")
        readers = [run for _, run in ordered if run["workstation"] == "C6" and role(run) == "reader_effect"
                   and any(_classify(i["ref"], i["partition"], pages) == ("text", n) for i in snapshot_items(run)[0])]
        if not readers:
            fail(scope, "reader-package", "没有装了本集正文的 C6 首读包（reader_effect）")
        elif n > 1 and not any(_classify(i["ref"], i["partition"], pages) == ("text", n - 1)
                               for run in readers for i in snapshot_items(run)[0]):
            (warn if n == first else fail)(scope, "reader-previous-text", f"首读包没有第{n - 1}集正文")

    per_outline = _outlines(outline_range, outline_batch, ordered, snapshot_items, reviews, receipts, pages,
                            remote_project, allow_offline, fail, warn) if outline_range else {}
    if outline_layer:
        _outline_layer(outline_range, records, root, per_outline, fail)

    failed_episodes = sorted({int(re.match(r"第(\d+)集", f["scope"]).group(1)) for f in failures if f["scope"].startswith("第")})
    failed_outlines = sorted({int(re.match(r"集纲第(\d+)集", f["scope"]).group(1)) for f in failures if f["scope"].startswith("集纲第")})
    by_rule: dict[str, int] = {}
    for item in failures:
        by_rule[item["rule"]] = by_rule.get(item["rule"], 0) + 1
    result = {"ok": True, "command": "season-check", "project": str(drama.parent), "episodes": f"{first}-{last}" if episodes is not None else None,
            "outline": f"{outline_range[0]}-{outline_range[1]}" if outline_range else None, "outlineBatch": outline_batch,
            "batchSize": batch_size, "allowOffline": allow_offline, "dialogueChecked": not skip_dialogue, "revise": revise, "since": since, "remoteProjectId": remote_project,
            "passed": not failures, "failureCount": len(failures), "failuresByRule": by_rule,
            "failedEpisodes": failed_episodes, "failedOutlines": failed_outlines, "failures": failures, "warnings": warnings,
            "perEpisode": {str(n): per_episode[n] for n in sorted(per_episode)},
            "perOutline": {str(n): per_outline[n] for n in sorted(per_outline)},
            "network_used": False, "models_called": False, "remote_verified": False, "note": NOTE}
    # only a side that switched to the new rules says so; a legacy project's output stays the 0.3.6 output byte for byte
    if outline_layer:
        result["ruleSet"] = "outline-layer"
    if dialogue_layer:
        result["episodeRuleSet"] = "dialogue-layer"
    return result


def _saved(ref: dict, receipts: list[dict]) -> set[str]:
    return {r["outcome"] for r in receipts if (r.get("localRef") or {}).get("id") == ref["id"]
            or ((r.get("remote") or {}).get("pageId") == ref["id"] and r["remote"].get("revision") == ref.get("revision"))}


def _outlines(span, batch, ordered, snapshot_items, reviews, receipts, pages, remote_project, allow_offline, fail, warn) -> dict:
    """Episode outlines (C4): written in order, in segments, from the characters, the structure, the outline before
    and the state of what is already written; reviewed in a context that did not write them; saved."""
    def plans(run: dict) -> dict[int, dict]:
        found = {}
        for ref in run["outputs"]:
            kind, episode = _classify(ref, None, pages)
            if kind == "plan" and episode is not None:
                found[episode] = ref
        return found

    def texts(run: dict) -> set[int]:
        return {episode for kind, episode in (_classify(ref, None, pages) for ref in run["outputs"]) if kind == "text"}

    result: dict[int, dict] = {}
    c4 = [(when, run) for when, run in ordered if run["workstation"] == "C4"]
    for n in range(span[0], span[1] + 1):
        scope, entry = f"集纲第{n}集", result.setdefault(n, {})
        writers = [(when, run) for when, run in c4 if n in plans(run)]
        if not writers:
            fail(scope, "outline-run", "没有产出本集集纲的 C4 运行交接")
            continue
        when, author = writers[0]
        segment = sorted(plans(author))
        entry.update(run=author["runId"], segment=f"{segment[0]}-{segment[-1]}")
        if len(segment) > batch:
            fail(scope, "outline-segment", f"C4 运行 {author['runId']} 一次写了 {len(segment)} 集集纲，超过每段 {batch} 集")
        items, missing = snapshot_items(author)
        if missing:
            fail(scope, "outline-snapshot", f"C4 运行引用的快照不存在：{', '.join(missing)}")
        refs = [item["ref"] for item in items]
        for station, rule, what in (("C2", "outline-characters", "人物小传与规则"), ("C3", "outline-structure", "全剧结构")):
            earlier = [run for at, run in ordered if run["workstation"] == station and at <= when]
            if not earlier:
                fail(scope, rule, f"写集纲之前没有 {station} 的运行交接（{what}）")
            elif not all(any(_same(ref, out) for ref in refs) for out in earlier[-1]["outputs"]):
                fail(scope, rule, f"集纲包没有装 {station} 最新产出的{what}（{earlier[-1]['runId']} 的产出）")
        if n == segment[0]:
            before = [run for at, run in c4 if at < when and n - 1 in plans(run)]
            if before:
                newest = plans(before[-1])[n - 1]
                if not any(_same(ref, newest) for ref in refs):
                    fail(scope, "outline-previous", f"集纲包没有装第{n - 1}集集纲的最新稿（{newest['id']}）")
            elif any(n - 1 in plans(run) for _, run in c4):
                fail(scope, "outline-sequential", f"第{n - 1}集集纲不是在这一段之前写完的；集纲按顺序分段写，不并行")
            elif n > 1:
                warn(scope, "outline-previous", f"记录里没有第{n - 1}集集纲")
            written = max((e for at, run in ordered if at < when and run["workstation"] == "C5" for e in texts(run) if e < n), default=None)
            if written is not None and not any(_classify(ref, None, pages) == ("state", written) for ref in refs):
                fail(scope, "outline-entry-state",
                     f"已写到第{written}集正文，集纲包却没有装 runs/state/after-ep-{written:03d}.md；后面的集纲要从实际正文接")
        final = plans(writers[-1][1])[n]
        covering = [review for _, review, _ in reviews
                    if any(_classify(ref, None, pages) == ("plan", n) for ref in [review["target"], *review.get("additionalTargets", [])])]
        entry["reviews"] = [review["reviewId"] for review in covering]
        if not covering:
            fail(scope, "outline-review", "没有审读本集集纲的审读记录")
        elif not any(review["context"] in ("independent", "human") for review in covering):
            fail(scope, "outline-review", "集纲只有作者同一上下文的自审，没有独立上下文或真人的审读")
        outcomes = _saved(final, receipts)
        entry["receipt"] = sorted(outcomes) or None
        if "confirmed" not in outcomes:
            message = "集纲没有 confirmed 保存回执，未存成 mali-story 页面"
            (warn if allow_offline and not remote_project else fail)(scope, "outline-saved", message)
    return result


def _dialogue(scope, n, entry, root, writers, polish, ordered, final, author_items, snapshot_items, role, text_outputs, pages, fail) -> None:
    """Voice cards for the speakers, a dialogue pass that only touches dialogue lines, and a dialogue read."""
    text = _read_ref(root, final)
    if text is None:
        fail(scope, "voice-card", f"读不到最终稿 {final['id']}（本地文件或 .drama/cache/ 里的页面修订），无法核对说话人")
    else:
        counts: dict[str, int] = {}
        for line in text.splitlines():
            name = _speaker(line)
            if name:
                counts[name] = counts.get(name, 0) + 1
        voices = _voice_text(root, author_items)
        missing = sorted(name for name, lines in counts.items() if lines >= VOICED_FROM and name not in voices)
        entry["speakers"] = counts
        if missing:
            fail(scope, "voice-card", f"这些人物各有 {VOICED_FROM} 句以上台词，但作者包里没有写到他们的声音卡（K5 知识卡）：{'、'.join(missing)}")
    if not polish:
        fail(scope, "dialogue-pass", "没有台词与表演遍：作者运行之后要有一次只改台词、括注和动作的 C5 运行（dialogue_author 包）")
        return
    when, run = polish[0]
    entry["dialogueRun"] = run["runId"]
    if not _voice_text(root, snapshot_items(run)[0]):
        fail(scope, "dialogue-pass", f"台词遍 {run['runId']} 的包里没有声音卡")
    earlier = [r for at, r in writers if at < when]
    before = _read_ref(root, text_outputs(earlier[-1])[n][-1]) if earlier else None
    after = _read_ref(root, text_outputs(run)[n][-1])
    if before is None or after is None:
        fail(scope, "dialogue-pass", "读不到台词遍前后的两份稿，无法核对它没有动场次")
    else:
        keep = lambda body: [line.strip() for line in body.splitlines() if HEADING.match(line)]
        if keep(before) != keep(after):
            fail(scope, "dialogue-pass", f"台词遍 {run['runId']} 增删或改写了场头；这一遍改台词、表演括注和动作，不动场次")
    readers = [r for at, r in ordered if at > when and r["workstation"] == "C6" and role(r) == "dialogue_read"
               and any(_classify(i["ref"], i["partition"], pages) == ("text", n) for i in snapshot_items(r)[0])]
    entry["dialogueRead"] = [r["runId"] for r in readers]
    if not readers:
        fail(scope, "dialogue-read", "台词遍之后没有台词读：新上下文里只给正文的 C6 运行（dialogue_read 包）")


def _ep_label(value) -> str:
    """"006A" and "6A" name the same planned episode."""
    return re.sub(r"^(?:ep|episode)?[-_]?0*(?=\d)", "", str(value).strip().lower()).upper()


def _entries(records: dict, kind: str, field: str) -> dict:
    """id -> entry across every record of a kind, later files (by path) overriding earlier ones."""
    found = {}
    for _, doc in records.get(kind, []):
        for entry in doc.get(field, []) if isinstance(doc.get(field), list) else []:
            if isinstance(entry, dict) and entry.get("id"):
                found[entry["id"]] = entry
    return found


def _outline_layer(span, records, root, per_outline, fail) -> None:
    """The outline-layer rules (implementation plan §2.2 #12): season assignment, a planned ledger delta backed by
    the episode's own scenes or beats, capacity that fits or names a proposal with a default, reality refs that exist
    and are not contested, a cold retell of the plan's events; and, project-wide, defaults on open decisions and the
    patch cap. They judge records, not the plan's quality."""
    try:
        season = json.loads((root / SEASON_PLAN).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        season = {}
        fail("季编排", "outline-season-assigned", f"{SEASON_PLAN} 读不出：{error}")
    assigned = {_ep_int(e.get("episode")) for e in season.get("episodes", []) if isinstance(e, dict)} if isinstance(season, dict) else set()
    plans: dict[int, list] = {}
    for path, doc in records.get("episode-plan", []):
        plans.setdefault(record_episode(doc, path), []).append((path, doc))
    ledger = _entries(records, "ledger-entry", "entries")
    decisions = _entries(records, "decision-queue", "entries")
    retold = {_ep_label(doc["target"].get("episode")) for _, doc in records.get("retell-record", [])
              if isinstance(doc.get("target"), dict) and doc["target"].get("kind") == "episode_plan_events"}
    for n in range(span[0], span[1] + 1):
        scope, entry = f"集纲第{n}集", per_outline.setdefault(n, {})
        if n not in assigned:
            fail(scope, "outline-season-assigned", f"第{n}集不在 {SEASON_PLAN} 的 episodes 里；集纲按季编排的分配写")
        found = plans.get(n, [])
        entry["episodePlans"] = [path for path, _ in found]
        if not found:
            fail(scope, "outline-ledger-delta", "没有本集的分集计划记录（planning/ 下的 episode-plan），ledgerDelta、容量、现实依据与冷读都无从核对")
            continue
        unverified = 0
        for path, plan in found:
            label = f"{path}（{plan.get('episode')}）"
            delta = plan.get("ledgerDelta")
            events = plan.get("events") if isinstance(plan.get("events"), dict) else {}
            anchors = {s.get("sceneId") for s in events.get("scenes", []) if isinstance(s, dict)}
            anchors |= {b.get("beatId") for s in events.get("scenes", []) if isinstance(s, dict) for b in s.get("beats", []) if isinstance(b, dict)}
            if not isinstance(delta, dict) or not (delta.get("writes") or delta.get("reads")):
                fail(scope, "outline-ledger-delta", f"{label} 没有声明 ledgerDelta 的 reads/writes（计划轨）")
            else:
                for index, write in enumerate(delta.get("writes") or []):
                    support = write.get("supportedBy") if isinstance(write, dict) else None
                    cited = support if isinstance(support, list) else [support]
                    if not cited or any(ref not in anchors for ref in cited):
                        fail(scope, "outline-ledger-delta", f"{label} ledgerDelta.writes[{index}] 的 supportedBy {support!r} 不是本集的场或拍")
            status = (plan.get("capacity") or {}).get("status") if isinstance(plan.get("capacity"), dict) else None
            if isinstance(status, str) and status.startswith("proposal:"):
                proposal = decisions.get(status.split(":", 1)[1])
                if proposal is None:
                    fail(scope, "outline-capacity", f"{label} capacity.status {status} 指向的提案不在决定队列里")
                elif not proposal.get("default"):
                    fail(scope, "outline-capacity", f"{label} capacity.status {status} 指向的提案没有 default，流程无法按默认走")
            elif status != "fits":
                fail(scope, "outline-capacity", f"{label} capacity.status 是 {status!r}；应为 fits 或 proposal:<决定队列 id>（超出时登记提案，不是失败）")
            for ref in plan.get("realityRefs") or []:
                ident = ref.get("id") if isinstance(ref, dict) else ref
                known = ledger.get(ident)
                if known is None:
                    fail(scope, "outline-reality-refs", f"{label} realityRefs 引用的 {ident} 不在底账里")
                elif known.get("status") == "contested":
                    fail(scope, "outline-reality-refs", f"{label} realityRefs 引用的 {ident} 处于 contested；矛盾解决前不能作依据")
                elif known.get("status") == "unverified":
                    unverified += 1
            if _ep_label(plan.get("episode")) not in retold:
                fail(scope, "outline-retell", f"{label} 没有只读 events 的冷读复述记录（retell-record，target.kind episode_plan_events）")
        entry["unverifiedRealityRefs"] = unverified
    for ident, decision in decisions.items():
        if decision.get("status") not in ("decided", "closed", "withdrawn") and not decision.get("default"):
            fail("决定队列", "outline-decision-default", f"{ident} 还没定，却没有 default；每条等人的决定都要带默认走法")
    maps = records.get("function-map", [])
    if maps:
        path, doc = maps[-1]
        for thread in doc.get("threads", []) if isinstance(doc.get("threads"), list) else []:
            for function in thread.get("functions", []) if isinstance(thread, dict) else []:
                for candidate in function.get("candidates", []) if isinstance(function, dict) else []:
                    # rejected candidates keep their history; only the implementation in use is capped
                    if isinstance(candidate, dict) and candidate.get("status") == "selected" \
                            and isinstance(candidate.get("patchCount"), int) and candidate["patchCount"] >= 3:
                        fail("功能地图", "outline-patch-cap", f"{path} {candidate.get('candidateId')} patchCount {candidate['patchCount']}："
                             "到 2 之后又原地修订；应回 C3a 换实现（新 id，计数归零）")
    for ident, item in ledger.items():
        if item.get("status") != "retired" and isinstance(item.get("patchCount"), int) and item["patchCount"] >= 3:
            fail("底账", "outline-patch-cap", f"{ident} patchCount {item['patchCount']}：到 2 之后又原地修订")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _text_layer(scope, n, entry, records, writers, ordered, snapshot_items, role, pages, fail, warn) -> None:
    """The dialogue-layer rules (implementation plan §2.2 #12), run instead of voice-card, dialogue-pass and
    dialogue-read when the project keeps dialogue plans: each is a record that must exist or a field that must hold."""
    def mine(kind):
        return [(path, doc) for path, doc in records.get(kind, []) if record_episode(doc, path) == n]

    plans = mine("dialogue-plan")
    entry["dialoguePlans"] = [path for path, _ in plans]
    if not plans:
        fail(scope, "dialogue-plan", "没有本集的对话表记录（C5a 的 dialogue-plan）")
    target_ids = [doc["targetId"] for _, doc in records.get("dialogue-target", []) if isinstance(doc.get("targetId"), str)]
    for path, plan in plans:
        errors = check_contract("dialogue-plan", plan)
        if errors:
            fail(scope, "dialogue-plan", f"{path} contract-check dialogue-plan 不通过：" + "; ".join(errors[:5]))
        based = plan.get("basedOn") if isinstance(plan.get("basedOn"), dict) else {}
        cited = " ".join(_strings([based.get("target"), based.get("dialogueTarget")]))
        if not cited:
            fail(scope, "target-ref", f"{path} 的 basedOn 没有引用台词目标（target）")
        elif not any(ident in cited for ident in target_ids):
            fail(scope, "target-ref", f"{path} 引用的台词目标不在项目的 dialogue-target 记录里（{cited[:80]}）")
    if not mine("plan-text-consistency"):
        fail(scope, "plan-text-align", "没有本集正文对照对话表的 plan-text-consistency 记录")
    if not [doc for _, doc in mine("retell-record") if doc["target"].get("kind") == "episode_text"]:
        fail(scope, "cold-retell", "没有只读本集正文的冷读复述记录（retell-record，target.kind episode_text）")
    checks = [path for path, doc in mine("answers") if str(doc.get("questionsVersion") or doc.get("schema") or "").startswith("dialogue-check")]
    entry["situationChecks"] = checks
    if not checks:
        fail(scope, "situation-check", "没有本集正文的处境核对记录（对话问题单的回答记录）")
    elif len(checks) > 1 and not mine("consistency"):
        fail(scope, "consistency-record", f"本集有 {len(checks)} 份处境核对，却没有它们之间的 answers-consistency 记录")
    cold = [when for when, run in ordered if run["workstation"] == "C6" and role(run) == "cold_reader"
            and any(_classify(i["ref"], i["partition"], pages) == ("text", n) for i in snapshot_items(run)[0])]
    if cold and any(when > min(cold) for when, _ in writers) and not any(when > writers[-1][0] for when in cold):
        fail(scope, "retell-after-revise", f"冷读之后又改了正文（{writers[-1][1]['runId']}），改后没有再做一次冷读")
    tasks = {doc.get("taskId"): (path, doc) for path, doc in records.get("task", [])}
    found = [tasks[run["taskId"]] for _, run in writers if run["taskId"] in tasks]
    if not found:
        warn(scope, "constraint-origin", "没有本集作者运行的任务记录（.drama/tasks/），任务约束的来源与禁词未核")
    for path, task in found:
        for index, constraint in enumerate(task.get("constraints") or []):
            text, origin = constraint.get("text") or "", constraint.get("origin")
            if not origin or (origin == "orchestrator" and not constraint.get("cite")):
                fail(scope, "constraint-origin", f"{path} constraints[{index}] 没有来源，或编排方约束没有引用台词目标条款")
            for category, hit in blocklist_hits(text):
                fail(scope, "no-numeric-dialogue-constraint", f"{path} constraints[{index}] 命中 {category} 禁词（{hit!r}），不论来源都拒")
    for path, fixlist in mine("revision-list"):
        quoted = [line.strip() for text in _strings(fixlist) for line in text.splitlines() if _speaker(line)]
        if quoted:
            fail(scope, "fixlist-no-lines", f"{path} 写了替换台词（{quoted[0][:30]}…）；修订单只指问题与引用，不写台词")
    tiers = {doc.get("k") for _, doc in mine("dup-hits")}
    if not {8, 13} <= tiers:
        fail(scope, "dup-two-tier", f"逐条命中记录缺 {sorted({8, 13} - tiers)} 字档（装包样本 8 字、全库 13 字）")
    if not mine("genre-scan"):
        fail(scope, "genre-lexicon", "没有本集正文的题材禁词扫描记录（corpus lexicon）")
