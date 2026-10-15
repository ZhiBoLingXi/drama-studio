"""Measure episodes; enforce explicit production constraints, never creative quality."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import re

EP_RE = re.compile(r"^#{1,2}\s*第([0-9一二三四五六七八九十百零〇]+)集")
SCENE_START_RE = re.compile(r"^(?:场|###\s+(?:场|\d))")
SCENE_ID_RE = re.compile(r"^(?:场\s*|###\s+(?:场\s*)?)(\d+)[-–](\d+)(?:\s+(.*))?$")
# Unknown time tokens must not silently become part of a guessed location.
# a day word may lead the time and an order word may follow it: 「次日晚」「次日晚稍后」「当天傍晚」 (D6-3 walkthrough #19)
SCENE_DETAIL_RE = re.compile(
    r"^(.+?)\s+((?:次日|当日|当天|翌日|隔天|第二天|同日|同一天)?(?:日|夜|晨|暮|黄昏|清晨|深夜|黎明|后半夜|前半夜|凌晨|傍晚|白天|"
    r"午后|下午|上午|正午|拂晓|晚上|早晨|入夜|晚|早)(?:稍后|稍早|前|后)?)\s+(内|外)\s*$")
SEPARATOR_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
DIALOG_RE = re.compile(r"^([^△#场\s【（(：:]{1,12})(（[^）]*）|\([^)]*\))?\s*[：:]\s*(.+)$")

# Available only through explicit selection; not universal writing standards.
PRESETS = {"legacy-aigc": dict(min_chars=1200, min_scenes=10, min_speaker_changes=6,
                              min_delta_ratio=0.20, max_locations=3, min_paren_ratio=0.6)}
RULES = {
    "min_chars": ("chars", "min", "汉字数"),
    "min_scenes": ("scenes", "min", "已识别场标题数"),
    "min_speaker_changes": ("speaker_changes", "min", "场内说话人交替次数"),
    "min_delta_ratio": ("delta_ratio", "min", "动作行／台词行比"),
    "max_locations": ("locations", "max", "已识别地点标签数"),
    "min_paren_ratio": ("paren_ratio", "min", "对白括注率"),
}
COUNT_RULES = {"min_chars", "min_scenes", "min_speaker_changes", "max_locations"}


def validate_constraints(values: dict) -> dict:
    if not isinstance(values, dict):
        raise ValueError("constraints must be an object")
    for key, value in values.items():
        if key not in RULES:
            raise ValueError(f"Unknown constraint: {key}")
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                (isinstance(value, float) and not math.isfinite(value)) or value < 0):
            raise ValueError(f"{key} must be finite and nonnegative")
        if key in COUNT_RULES and not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        if key == "min_paren_ratio" and value > 1:
            raise ValueError("min_paren_ratio must be between 0 and 1")
    return values


def resolve_constraints(config_path=None, preset=None, **overrides) -> tuple[dict, dict, list]:
    values, sources, warnings = {}, {}, []
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset: {preset}")
        values.update(PRESETS[preset])
        sources.update({key: f"preset:{preset}" for key in values})
        warnings.append("legacy-aigc 是历史示例规格，不是行业标准或质量认证。")
    if config_path is not None:
        path = Path(config_path).expanduser().resolve()
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or set(config) != {"schemaVersion", "source", "constraints"}:
            raise ValueError("Config requires exactly schemaVersion, source and constraints")
        if type(config["schemaVersion"]) is not int or config["schemaVersion"] != 1:
            raise ValueError("Unsupported config schemaVersion")
        if not isinstance(config["source"], str) or not config["source"].strip():
            raise ValueError("Config source must describe the project specification")
        configured = validate_constraints(config["constraints"])
        values.update(configured)
        sources.update({key: f"config:{path} ({config['source']})" for key in configured})
    overrides = {key: value for key, value in overrides.items() if value is not None}
    if "min_rounds" in overrides:
        if "min_speaker_changes" in overrides:
            raise ValueError("Use min_speaker_changes or legacy min_rounds, not both")
        overrides["min_speaker_changes"] = overrides.pop("min_rounds")
        warnings.append("min_rounds 已弃用：它统计说话人交替，不是冲突回合；请用 min_speaker_changes。")
    validate_constraints(overrides)
    values.update(overrides)
    sources.update({key: "explicit_argument" for key in overrides})
    return values, sources, warnings


@dataclass
class EpisodeStats:
    episode: str
    chars: int = 0
    scenes: int = 0
    locations: int = 0
    location_list: list = field(default_factory=list)
    delta_lines: int = 0
    dialog_lines: int = 0
    delta_ratio: float | None = None
    speaker_changes: int = 0
    paren_ratio: float | None = None
    slots: int = 0
    warnings: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    parse_coverage: dict = field(default_factory=dict)


def _episode_number(value: str) -> int:
    if value.isascii() and value.isdigit():
        return int(value)
    digits = dict(zip("零〇一二三四五六七八九", (0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9)))
    if all(char in digits for char in value):
        return int("".join(str(digits[char]) for char in value))
    total, current = 0, 0
    for char in value:
        if char in digits:
            current = digits[char]
        else:
            total += (current or 1) * {"十": 10, "百": 100}[char]
            current = 0
    return total + current


def split_episodes(text: str) -> list[tuple[str, list[str]]]:
    if any(re.match(r"^(?:`{3,}|~{3,})", line.strip()) for line in text.splitlines()):
        raise ValueError("正文含代码围栏；请提供不混入代码示例的剧本副本，不将示例标题当作实际集场")
    episodes, current, lines = [], None, []
    for line in text.splitlines():
        match = EP_RE.match(line.strip())
        if match:
            if current is not None:
                episodes.append((current, lines))
            current, lines = f"第{_episode_number(match.group(1))}集", []
        elif current is not None:
            lines.append(line)
    if current is not None:
        episodes.append((current, lines))
    return episodes


def analyze_episode(name: str, lines: list[str], constraints: dict, sources: dict) -> EpisodeStats:
    stats = EpisodeStats(episode=name)
    content = [line.strip() for line in lines if line.strip() and
               not line.strip().startswith("【") and not SEPARATOR_RE.fullmatch(line.strip())]
    body = [line for line in content if not line.startswith(("场", "人物", "#"))]
    if not body or not any(re.search(r"\w", line) for line in body):
        raise ValueError(f"{name} 正文为空（场标题与人物清单不算正文）")
    stats.chars = sum(len(re.sub(r"[^一-鿿]", "", line)) for line in body)
    stats.slots = sum(line.count("【SLOT-") for line in content)
    locations, previous_speaker, with_parenthetical = [], None, 0
    seen_scenes = set()
    invalid_headers, incomplete_locations, unknown_body = False, False, False
    episode_number = int(re.fullmatch(r"第(\d+)集", name).group(1))
    for line in content:
        if SCENE_START_RE.match(line):
            previous_speaker = None
            header = SCENE_ID_RE.fullmatch(line)
            if not header:
                invalid_headers, incomplete_locations = True, True
                stats.warnings.append(f"场标题未完整识别，地点数量可能不完整：{line}")
                continue
            scene_episode, scene_number = int(header.group(1)), int(header.group(2))
            if scene_episode != episode_number or scene_number < 1:
                raise ValueError(f"{name} 场号不属于本集或场序非正数：{line}")
            if scene_number in seen_scenes:
                raise ValueError(f"{name} 存在重复场号：{line}")
            seen_scenes.add(scene_number)
            stats.scenes += 1
            detail = SCENE_DETAIL_RE.fullmatch(header.group(3) or "")
            if detail:
                locations.append(detail.group(1).strip())
            else:
                incomplete_locations = True
                stats.warnings.append(f"场标题未完整识别，地点数量可能不完整：{line}")
            continue
        if line.startswith(("人物", "#")):
            continue
        if line.startswith("△"):
            stats.delta_lines += 1
            continue
        match = DIALOG_RE.match(line)
        if match:
            stats.dialog_lines += 1
            with_parenthetical += bool(match.group(2))
            speaker = match.group(1)
            if previous_speaker and speaker != previous_speaker:
                stats.speaker_changes += 1
            previous_speaker = speaker
        else:
            unknown_body = True
            stats.warnings.append(f"未识别为动作或台词，相关计数可能不完整：{line}")
    stats.location_list = sorted(set(locations))
    stats.locations = len(stats.location_list)
    if stats.dialog_lines:
        stats.delta_ratio = stats.delta_lines / stats.dialog_lines
        stats.paren_ratio = with_parenthetical / stats.dialog_lines
    if not stats.scenes:
        stats.warnings.append("未识别到场标题；场数与地点数不能作为完整制作统计。")
    stats.parse_coverage = {
        "scene_headers": "unknown" if not stats.scenes else "partial" if invalid_headers else "complete",
        "location_labels": "unknown" if not stats.scenes else "partial" if incomplete_locations else "complete",
        "body_lines": "partial" if unknown_body else "complete",
    }
    for key, expected in constraints.items():
        metric, operator, label = RULES[key]
        actual = getattr(stats, metric)
        unavailable = actual is None or (key != "min_chars" and bool(stats.warnings))
        status = ("not_evaluable" if unavailable else
                  "met" if (actual >= expected if operator == "min" else actual <= expected) else "unmet")
        stats.checks.append({"rule": key, "metric": metric, "label": label, "operator": operator,
                             "expected": expected, "actual": actual, "source": sources[key], "status": status})
    return stats


def speech_volume(lines: list[str]) -> dict:
    """口播量：对白行冒号后的汉字数（去括注、人名、△ 行与场头），只统计不估时（估时在 capacity text）。"""
    from checks.text_lines import parse_lines, speech_chars

    chars, counted = speech_chars(parse_lines("\n".join(lines)))
    return {"speech_chars": chars, "dialogue_lines_counted": counted,
            "note": "口播汉字数，不含括注与人名；不换算时长"}


def run_episode_check(path: str, *, config_path=None, preset=None, speech=False, **overrides) -> dict:
    """`speech=True` 时每集多一个 `speech` 统计块；不给时输出与退出码与原来逐字一致。"""
    constraints, sources, warnings = resolve_constraints(config_path, preset, **overrides)
    episodes = split_episodes(Path(path).read_text(encoding="utf-8"))
    if not episodes:
        return {"ok": False, "error": "未识别到 `# 第X集` 集标题，检查正文格式"}
    names = [name for name, _ in episodes]
    if len(set(names)) != len(names):
        return {"ok": False, "error": "存在重复集标题，先核对集序"}
    results = [asdict(analyze_episode(name, lines, constraints, sources)) for name, lines in episodes]
    if speech:
        for result, (_, lines) in zip(results, episodes):
            result["speech"] = speech_volume(lines)
    statuses = [check["status"] for result in results for check in result["checks"]]
    status = ("not_configured" if not constraints else "unmet" if "unmet" in statuses else
              "not_evaluable" if "not_evaluable" in statuses else "met")
    return {"ok": True, "schema_version": 2, "mode": "constraints" if constraints else "measurements",
            "thresholds": constraints, "rule_sources": sources, "warnings": warnings, "episodes": results,
            "constraint_status": status, "passed": True if status == "met" else False if status == "unmet" else None,
            "review_status": "not_run", "note": "统计与明确制作规格的核对，不代表创作质量、模型评审或编辑验收。"}


def format_report(result: dict) -> str:
    if not result.get("ok"):
        return f"[error] {result.get('error')}"
    heading = "尚未配置验收标准，仅报告统计。" if result["constraint_status"] == "not_configured" else "仅核对明确配置的制作规格。"
    rows = [heading, "创作评审：未执行。", *result["warnings"]]
    for episode in result["episodes"]:
        rows.append(f"{episode['episode']}：汉字 {episode['chars']}，场标题 {episode['scenes']}，"
                    f"说话人交替 {episode['speaker_changes']}，地点标签 {episode['locations']}")
        rows.extend(episode["warnings"])
        rows.extend(f"{check['label']}：实际 {check['actual']} / {check['operator']} {check['expected']}；"
                    f"{check['status']}；来源 {check['source']}" for check in episode["checks"])
    rows.append(f"规格核对状态：{result['constraint_status']}；此结果不评价剧本好坏。")
    return "\n".join(rows)
