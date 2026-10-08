"""Plan importing an old local project's drafts into mali-story candidates; never calls mali-story.

`preview` only reads: the project files and the list_story_artifacts response(s) the host saved
beforehand. `apply` additionally writes one save_story_artifact input JSON per importable file into
`--out`, and nothing else. Neither proves anything remote: the listing is whatever the host saved,
and a written request is not a save. The host sends each request through MCP after the screenwriter
confirms, then records the response with `receipt record`.

Mapping rules (conservative; anything not matched below is reported as skipped with a reason):

* Only regular, non-hidden `.md` files directly inside `episodes/`, `planning/`, `reviews/` and
  `research/` are candidates. Files in sub-folders (experiments, history copies), symlinks,
  `reference/` (benchmark material, not this drama's text), `deliveries/` (compilations of other
  drafts), top-level files such as PROJECT.md and any other folder are skipped.
* Episode numbers N (1-9999) become episode_ref `ep-NN` (zero-padded to at least two digits, as in
  references/mali-story.md: `ep-03`); a file name may write N as `ep03`, `ep-003`, `第3集` or `3`.
  - `episodes/<N>.md`, `<N>-draft.md`, `<N>正文.md`      -> episode_draft,   slot `ep-NN-draft`
  - `planning/<N>-outline.md`, `<N>集纲.md`              -> episode_outline, slot `ep-NN-outline`
  - `reviews/<N>-review.md`, `<N>评审.md`                 -> review,          slot `ep-NN-review`
  - `planning/characters.md`, `人物.md`, `人物小传.md`     -> characters,      slot `characters`
  - `planning/series-outline.md`, `大纲.md`, `全剧大纲.md` -> series_outline,  slot `series-outline`
  - `research/positioning.md`                            -> research,        slot `positioning`
  Version suffixes (`characters-v1.md`), episode ranges (`01-10-v1.md`) and other names do not
  match, because the tool cannot tell which copy is current.
* A file that is empty, not UTF-8, or longer than the 500000-character body limit is skipped.
  When several files map to the same slot, all of them are skipped.
* A slot that already has any revision in the listing is a conflict (with the highest remote
  revision); only slots absent remotely are importable, so every request uses expected_revision 0.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

try:
    from .receipt import canonical_json, parse_response, publish_new, safe_id
except ImportError:  # loaded as a top-level module
    from receipt import canonical_json, parse_response, publish_new, safe_id

SCANNED = ("episodes", "planning", "reviews", "research")
SKIPPED_FOLDERS = {"reference": "reference/ 是对标与拉片资料，不是本剧稿件",
                   "deliveries": "deliveries/ 是已有稿件的交付汇编，导入会重复"}
BODY_LIMIT = 500000  # save_story_artifact body maxLength
SNAPSHOT = re.compile(r"sha256:[a-f0-9]{64}")
PRODUCERS = ("codex", "human", "external_ai")
_N = r"(?:ep-?|第)?0*(?P<n>\d{1,4})(?:集)?"
EPISODE_RULES = {  # folder -> [(file-name pattern, kind, slot suffix)]
    "episodes": [(re.compile(_N + r"(?:-?draft|正文)?\.md", re.I), "episode_draft", "draft")],
    "planning": [(re.compile(_N + r"-?(?:outline|集纲)\.md", re.I), "episode_outline", "outline")],
    "reviews": [(re.compile(_N + r"-?(?:review|评审)\.md", re.I), "review", "review")],
}
FIXED_RULES = {  # (folder, file name) -> (kind, slot)
    ("planning", "characters.md"): ("characters", "characters"),
    ("planning", "人物.md"): ("characters", "characters"),
    ("planning", "人物小传.md"): ("characters", "characters"),
    ("planning", "series-outline.md"): ("series_outline", "series-outline"),
    ("planning", "大纲.md"): ("series_outline", "series-outline"),
    ("planning", "全剧大纲.md"): ("series_outline", "series-outline"),
    ("research", "positioning.md"): ("research", "positioning"),
}


def _map(folder: str, name: str) -> tuple[str, str, str | None] | str:
    """Return (kind, slot, episodeRef), or the reason the file is skipped."""
    if not name.lower().endswith(".md"):
        return "不是 Markdown 稿件"
    fixed = FIXED_RULES.get((folder, name.lower() if name.isascii() else name))
    if fixed:
        return fixed[0], fixed[1], None
    for pattern, kind, suffix in EPISODE_RULES.get(folder, []):
        match = pattern.fullmatch(name)
        if match and int(match["n"]) >= 1:
            ref = f"ep-{int(match['n']):02d}"
            return kind, f"{ref}-{suffix}", ref
    return f"文件名不符合 {folder}/ 的映射约定（带版本后缀、多集合并或其他名称），无法确定 slot"


def _scan(project: Path, exclude: Path | None) -> tuple[list[dict], list[dict]]:
    """Walk the project read-only; return (mapped items, skipped files)."""
    mapped, skipped = [], []

    def skip(path: Path, reason: str) -> None:
        skipped.append({"source": path.relative_to(project).as_posix(), "reason": reason})

    for path in sorted(project.rglob("*")):
        rel = path.relative_to(project)
        if any(part.startswith(".") for part in rel.parts):
            continue  # .drama/, .git/ and other hidden entries are tool state, not drafts
        if exclude is not None and (path == exclude or exclude in path.parents):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        if path.is_symlink():
            skip(path, "符号链接，不跟随")
            continue
        top = rel.parts[0]
        if len(rel.parts) == 1:
            skip(path, "项目根目录的文件不是稿件（只扫描 episodes/ planning/ reviews/ research/）")
        elif top in SKIPPED_FOLDERS:
            skip(path, SKIPPED_FOLDERS[top])
        elif top not in SCANNED:
            skip(path, f"{top}/ 不是约定的稿件目录")
        elif len(rel.parts) > 2:
            skip(path, f"{top}/ 的子目录（探索片段或历史副本），不自动映射")
        else:
            target = _map(top, rel.name)
            if isinstance(target, str):
                skip(path, target)
                continue
            raw = path.read_bytes()
            try:
                body = raw.decode("utf-8")
            except UnicodeDecodeError:
                skip(path, "不是 UTF-8 文本")
                continue
            if not body.strip():
                skip(path, "空文件")
            elif len(body) > BODY_LIMIT:
                skip(path, f"正文 {len(body)} 字，超过 save_story_artifact 上限 {BODY_LIMIT}")
            else:
                kind, slot, episode = target
                mapped.append({"source": rel.as_posix(), "slot": slot, "kind": kind, "episodeRef": episode,
                               "bodySha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "characters": len(body), "_body": body})
    by_slot: dict[str, list[dict]] = {}
    for item in mapped:
        by_slot.setdefault(item["slot"], []).append(item)
    kept = []
    for slot, items in by_slot.items():
        if len(items) == 1:
            kept.append(items[0])
            continue
        names = "、".join(item["source"] for item in items)
        skipped.extend({"source": item["source"], "reason": f"多个文件映射到同一 slot {slot}（{names}），无法确定哪份是当前稿"} for item in items)
    kept.sort(key=lambda item: item["source"])
    skipped.sort(key=lambda item: item["source"])
    return kept, skipped


def _listing(paths: list[str]) -> tuple[dict[str, dict], dict]:
    """Highest remote revision per slot from saved list_story_artifacts responses (one file per page)."""
    remote: dict[str, dict] = {}
    open_pages, rows_seen = 0, 0
    for name in paths:
        file = Path(name)
        try:
            value = json.loads(file.read_bytes().decode("utf-8-sig"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise ValueError(f"--listing {name} is not a readable JSON response: {error}") from None
        parsed = parse_response(value, "list_story_artifacts")
        if not parsed["ok"]:
            raise ValueError(f"--listing {name} is an error response ({parsed['errorCode'] or parsed['httpStatus']}); list again")
        data = parsed["data"]
        rows = data.get("records") if isinstance(data.get("records"), list) else data.get("items")
        if not isinstance(rows, list):
            raise ValueError(f"--listing {name} has no records list")
        if data.get("nextCursorId") is None:
            open_pages += 1
        for row in rows:
            revision = row.get("revision") if isinstance(row, dict) else None
            if not (isinstance(row, dict) and isinstance(row.get("slot"), str)
                    and isinstance(revision, int) and not isinstance(revision, bool) and revision >= 1):
                raise ValueError(f"--listing {name} has a row without a slot and a revision >= 1: {row!r}")
            rows_seen += 1
            seen = remote.setdefault(row["slot"], {"remoteRevision": 0, "remoteKinds": set()})
            seen["remoteRevision"] = max(seen["remoteRevision"], revision)
            if isinstance(row.get("kind"), str):
                seen["remoteKinds"].add(row["kind"])
    if open_pages != 1:  # keyset pagination: only the last page has nextCursorId null
        raise ValueError(f"the listing is incomplete or mixed: {open_pages} of {len(paths)} page(s) have nextCursorId null, "
                         "expected exactly one (the last page). List again with cursor_id until nextCursorId is null and pass every page")
    for seen in remote.values():
        seen["remoteKinds"] = sorted(seen["remoteKinds"])
    return remote, {"pages": len(paths), "rows": rows_seen, "slots": len(remote)}


def _plan(project: str, listings: list[str], exclude: Path | None = None) -> tuple[Path, dict, list[dict]]:
    root = Path(project).expanduser().absolute()
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    items, skipped = _scan(root, exclude)
    remote, summary = _listing(listings)
    create, conflicts = [], []
    for item in items:
        seen = remote.get(item["slot"])
        if seen is None:
            create.append(item)
        else:
            conflicts.append({**item, "remoteRevision": seen["remoteRevision"], "remoteKinds": seen["remoteKinds"],
                              "reason": f"远端 slot {item['slot']} 已有修订 r{seen['remoteRevision']}，不生成请求；先读远端稿再由主创决定"})
    public = lambda rows: [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]  # noqa: E731
    result = {"ok": True, "project": str(root), "listing": summary,
              "create": public(create), "conflicts": public(conflicts), "skipped": skipped,
              "counts": {"create": len(create), "conflicts": len(conflicts), "skipped": len(skipped)},
              "remote_verified": False, "adoption_verified": False,
              "note": "listing 是宿主保存的响应，工具不联网；须为不带 kind/slot 过滤的全量列举。计划不是保存，保存前须主创确认。"}
    return root, result, create


def run_preview(project: str, listings: list[str]) -> dict:
    _, result, _ = _plan(project, listings)
    return {**result, "read_only": True, "written": []}


def request_id_for(save: dict) -> str:
    """Content-determined: the slot plus a hash of the canonical input without request_id (body included)."""
    digest = hashlib.sha256(canonical_json({k: v for k, v in save.items() if k != "request_id"})).hexdigest()
    return f"import-{save['slot']}-{digest[:16]}"


def run_apply(project: str, listings: list[str], out: str, producer: str, input_snapshot_id: str) -> dict:
    if producer not in PRODUCERS:
        raise ValueError(f"--producer must be one of {', '.join(PRODUCERS)}")
    if not isinstance(input_snapshot_id, str) or not SNAPSHOT.fullmatch(input_snapshot_id):
        raise ValueError("--input-snapshot-id must be sha256:<64 hex>, the snapshotId of a get_writing_context read")
    root = Path(project).expanduser().absolute()
    state_path = root / ".drama" / "project.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"cannot read {state_path}: {error}") from None
    project_id = state.get("remoteProjectId") if isinstance(state, dict) else None
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError(f"{state_path} has no remoteProjectId; bind the project to its mali-story project first (never guessed)")
    target = Path(out).expanduser().absolute()
    if target.exists() and not target.is_dir():
        raise ValueError(f"--out {target} exists and is not a directory")
    resolved = target.resolve()
    forbidden = [root.resolve()] + [(root / name).resolve() for name in (".drama", *SCANNED, *SKIPPED_FOLDERS)]
    if resolved in forbidden or (root / ".drama").resolve() in resolved.parents:
        raise ValueError(f"--out {target} would mix requests into the project's own folders; use a separate folder")
    _, result, create = _plan(project, listings, exclude=resolved if root.resolve() in resolved.parents else None)
    requests, clashes = [], []
    for item in create:
        save = {"project_id": project_id, "slot": item["slot"], "kind": item["kind"], "expected_revision": 0,
                "body": item["_body"], "producer": producer, "input_snapshot_id": input_snapshot_id}
        if item["episodeRef"] is not None:
            save["episode_ref"] = item["episodeRef"]
        save["request_id"] = safe_id(request_id_for(save), "request_id")
        path = target / f"{save['request_id']}.json"
        content = (json.dumps(save, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and path.read_bytes() != content:
            clashes.append(str(path))
        requests.append({"source": item["source"], "slot": item["slot"], "requestId": save["request_id"],
                         "bodySha256": item["bodySha256"], "path": str(path), "_content": content})
    base = {**result, "read_only": False, "projectId": project_id, "producer": producer, "inputSnapshotId": input_snapshot_id, "out": str(target)}
    if clashes:
        return {**base, "requests": [], "passed": False, "status": "refused",
                "error": "existing request file(s) differ: " + ", ".join(clashes) + "; nothing written"}
    for request in requests:
        path = Path(request["path"])
        request["existing"] = path.exists()
        if not request["existing"] and not publish_new(path, request["_content"]):
            raise ValueError(f"{path} appeared during the run; rerun apply")
        del request["_content"]
    return {**base, "requests": requests, "status": "written",
            "next": "主创确认后，宿主逐条用 save_story_artifact 发送这些文件的内容，原样保存响应，再执行 receipt record "
                    "<项目> <响应> --operation save_story_artifact --request-id <requestId> --input <请求文件>"}
