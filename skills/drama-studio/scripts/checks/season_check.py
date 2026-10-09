"""Check that a run of episodes followed the season workstation flow, from the project's local records only.

`season-check` reads `<project>/.drama/` (runs, snapshots, reviews, receipts) and, for every episode in the range,
looks for the evidence `references/workstations/season-run.md` asks for: upstream C1-C4 runs, one author run per
episode whose package holds that episode's plan, the newest text of the episode before it and the state record after
it, sealed first and second reads, at most one directed revision, and a confirmed save receipt for the final text.
It never reads the texts' meaning, the network or chat history: passing proves the records are complete and
consistent, not that the writing is good or that the remote holds them.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from .contract_check import check_contract, finished_at
from .receipt import area, contained, drama_dir

NOTE = ("只核对 .drama/ 里的记录是否齐全、彼此一致；不判断正文质量，不联网，也不证明远端已保存。"
        "通过不等于“写得好”，失败的条目在补齐证据或重做之前，不能在交付说明里写“已按流程完成”。")
EPISODE = re.compile(r"(?:^|[^a-z])(?:ep|episode|outline)[-_]?0*(\d{1,4})(?!\d)|第0*(\d{1,4})集")
STATE = re.compile(r"^(?:runs|\.drama)/state/after-ep-0*(\d{1,4})\.md$")
UPSTREAM = ("C1", "C2", "C3")


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


def run_season_check(project: str, episodes: str | None = None, batch_size: int = 10, allow_offline: bool = False,
                     outline: str | None = None, outline_batch: int = 15) -> dict:
    if episodes is None and outline is None:
        raise ValueError("give --episodes (written episodes) and/or --outline (episode outlines) as N or A-B")
    first, last = _range(episodes) if episodes is not None else (1, 0)
    outline_range = _range(outline) if outline is not None else None
    if batch_size < 1 or outline_batch < 1:
        raise ValueError("--batch-size and --outline-batch must be at least 1")
    drama = drama_dir(project)
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

    # runs in finish order; a run without a valid finishedAt cannot be placed and fails
    ordered = []
    for path, doc, _ in runs:
        when = finished_at(doc.get("finishedAt"))
        if when is None:
            fail(f"run {doc['runId']}", "finished-at", "运行记录没有有效的 finishedAt，无法判断先后")
            continue
        ordered.append((when, doc))
    ordered.sort(key=lambda pair: pair[0])

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
        if not any(run["workstation"] == station and (first_author is None or when <= first_author) for when, run in ordered):
            fail(station, "upstream", f"没有 {station} 的运行交接；从集纲起步也要记录 {station}（采用用户给定材料时写明来源）")

    per_episode: dict[int, dict] = {}
    previous_state_sha: dict[int, str] = {}
    for n in range(first, last + 1):
        scope = f"第{n}集"
        entry = per_episode.setdefault(n, {})
        writers = [(when, run) for when, run in c5_runs if n in text_outputs(run)]
        c4 = [run["runId"] for when, run in ordered if run["workstation"] == "C4"
              and any(_classify(ref, None, pages)[1] == n for ref in run["outputs"])
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
        if len(written) > 1:
            fail(scope, "one-episode-per-author-run",
                 f"作者运行 {author['runId']} 一次写了 {len(written)} 集（{written[0]}–{written[-1]}），"
                 "批内应逐集写，前一集定稿后再给下一集装包")
        if len(writers) > 2:
            warn(scope, "one-directed-revision", f"作者之后又有 {len(writers) - 1} 次 C5 运行；每批只做一次定向修订，纠错重存除外")
        if role(author) != "author":
            fail(scope, "author-role", f"作者运行 {author['runId']} 的快照不是 author 包")
        items, missing = snapshot_items(author)
        if missing:
            fail(scope, "author-snapshot", f"作者运行引用的快照不存在：{', '.join(missing)}")
        classified = [(_classify(item["ref"], item["partition"], pages), item) for item in items]
        if not any(kind == "plan" and episode == n for (kind, episode), _ in classified):
            fail(scope, "author-plan", "作者包里没有本集的集纲或修改单")
        # the newest text of n-1 that existed when the author started
        earlier = [run for when, run in ordered if when < author_when and n - 1 in text_outputs(run)]
        packed_prev = [item for (kind, episode), item in classified if kind == "text" and episode == n - 1]
        if n - 1 in written:
            pass  # written in the same run: already reported by one-episode-per-author-run
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
        if not states:
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
        for path, review, data in firsts:
            sidecar = path.with_suffix(".sha256")
            if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").split()[:1] != [hashlib.sha256(data).hexdigest()]:
                fail(scope, "first-read-sealed", f"首读 {review['reviewId']} 没有封存或 .sha256 与字节不符")
            targets = [review["target"], *review.get("additionalTargets", [])]
            size = len({_classify(ref, None, pages)[1] for ref in targets} - {None})
            if size > batch_size:
                fail(scope, "batch-size", f"首读 {review['reviewId']} 一次审 {size} 集，超过每批 {batch_size} 集")
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

    failed_episodes = sorted({int(re.match(r"第(\d+)集", f["scope"]).group(1)) for f in failures if f["scope"].startswith("第")})
    failed_outlines = sorted({int(re.match(r"集纲第(\d+)集", f["scope"]).group(1)) for f in failures if f["scope"].startswith("集纲第")})
    by_rule: dict[str, int] = {}
    for item in failures:
        by_rule[item["rule"]] = by_rule.get(item["rule"], 0) + 1
    return {"ok": True, "command": "season-check", "project": str(drama.parent), "episodes": f"{first}-{last}" if episodes is not None else None,
            "outline": f"{outline_range[0]}-{outline_range[1]}" if outline_range else None, "outlineBatch": outline_batch,
            "batchSize": batch_size, "allowOffline": allow_offline, "remoteProjectId": remote_project,
            "passed": not failures, "failureCount": len(failures), "failuresByRule": by_rule,
            "failedEpisodes": failed_episodes, "failedOutlines": failed_outlines, "failures": failures, "warnings": warnings,
            "perEpisode": {str(n): per_episode[n] for n in sorted(per_episode)},
            "perOutline": {str(n): per_outline[n] for n in sorted(per_outline)},
            "network_used": False, "models_called": False, "remote_verified": False, "note": NOTE}


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
