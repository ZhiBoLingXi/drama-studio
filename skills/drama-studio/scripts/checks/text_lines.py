"""正文逐行解析与几个只读核对命令共用的小工具。

正文（编剧稿式 markdown）按 1-based 行号解析，空行也占一个行号，与 plan-text-map
的 `line` 字段同一种计数。场头取场号（`场6-1`、`场6A-1`、`### 场 6-1` 都认）。

共用小工具：读 JSON、输入错误、可直接运行的复现命令。只读、不联网、不调模型。
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import sys

SCENE_HEADER_RE = re.compile(r"^(#{1,6}\s*)?场\s*\d")
SCENE_ID_RE = re.compile(r"^场\s*(?P<sid>\S+)\s*(?P<rest>.*)$")
TITLE_RE = re.compile(r"^#{1,2}\s*第")
CAST_LINE_RE = re.compile(r"^人物[：:]")
DIALOGUE_LINE_RE = re.compile(r"^(?P<speaker>[^：\n（(]+)(?P<state>[（(][^）)]*[）)])?[：:](?P<content>.*)$")
PAREN_RE = re.compile(r"[（(][^）)]*[）)]")
HAN_RE = re.compile(r"[^一-鿿]")
SCRIPTS_DIR = Path(__file__).resolve().parents[1]


class InputError(Exception):
    """输入错误（文件读不了、不是合法 JSON、缺必需字段）：命令退出码 1。"""


def load_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError(f"找不到{label}：{path}") from None
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"{label}读不了或不是合法 JSON：{path}（{error}）") from None


def load_text(path, label="正文"):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InputError(f"读{label}失败：{path}（{error}）") from None


def is_nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value) and any(is_nonempty(v) for v in value.values())
    if isinstance(value, list):
        return bool(value) and all(is_nonempty(v) for v in value)
    return True


def abspath(path) -> str:
    return str(Path(path).expanduser().resolve())


def reproduce_command(module: str, args: list) -> str:
    """可直接运行的完整命令行：`python3 -B <scripts>/checks/<module>.py <参数>`。"""
    parts = [sys.executable, "-B", str(SCRIPTS_DIR / "checks" / f"{module}.py"), *[str(a) for a in args]]
    return " ".join(shlex.quote(p) for p in parts)


def run_cli(main_fn, argv) -> int:
    """各命令的 `main(argv)` 共用外壳：输入错误打到 stderr 并退出 1。"""
    try:
        result, code = main_fn(argv)
    except InputError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


def han_only(text) -> str:
    """只留汉字（与 dup_check.only_han 同口径）。"""
    return HAN_RE.sub("", text or "")


def strip_parens(text) -> str:
    return PAREN_RE.sub("", text or "")


def parse_lines(md_text: str) -> list[dict]:
    """逐行解析，返回 `[{line, raw, kind, sceneId, speaker, state, content}]`。

    kind ∈ title / scene / cast / action / dialogue / blank / other；action 的
    content 是「△」之后的文字，dialogue 的 content 是冒号之后的文字（括注原样保留）。
    """
    out, current_scene = [], None
    for i, raw in enumerate(md_text.splitlines(), start=1):
        line = raw.strip()
        rec = {"line": i, "raw": raw, "kind": "blank", "sceneId": current_scene,
               "speaker": None, "state": None, "content": None}
        if not line:
            pass
        elif TITLE_RE.match(line):
            rec["kind"] = "title"
        elif SCENE_HEADER_RE.match(line):
            match = SCENE_ID_RE.match(line.lstrip("#").strip())
            current_scene = match.group("sid") if match else None
            rec["kind"], rec["sceneId"] = "scene", current_scene
        elif line.startswith("#"):
            rec["kind"] = "other"
        elif CAST_LINE_RE.match(line):
            rec["kind"] = "cast"
        elif line.startswith("△"):
            rec["kind"], rec["content"] = "action", line[1:].strip()
        else:
            match = DIALOGUE_LINE_RE.match(line)
            if match:
                state = match.group("state")
                rec.update(kind="dialogue", speaker=match.group("speaker").strip(),
                           state=state.strip("（）()").strip() if state else None,
                           content=match.group("content").strip())
            else:
                rec["kind"] = "other"
        out.append(rec)
    return out


def dialogue_lines(parsed: list[dict]) -> list[dict]:
    return [row for row in parsed if row["kind"] == "dialogue"]


def speech_chars(parsed: list[dict]) -> tuple[int, int]:
    """口播汉字数与计入的对白行数：只算对白行冒号后的文字，去掉括注。"""
    rows = dialogue_lines(parsed)
    return sum(len(han_only(strip_parens(row["content"]))) for row in rows), len(rows)
