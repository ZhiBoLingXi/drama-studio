"""逐集客观检查：把"可数的质量"脚本化，作为正文闸门（落地第一步）。

针对竖屏短剧/AIGC 漫剧分场剧本（格式：`# 第X集` / `场X-Y 地点 日/夜 内/外` / `人物：…` / `△…` / `角色（括注）：台词`）。
逐集计算：汉字数、场数、△行/台词行比、物理地点数、冲突回合（说话人交替次数）、对白括注率、结尾留扣（启发式）。
与硬线对比（可配置）：字数≥1200、场数≥10、回合≥6、△比≥20%、地点≤3、括注率（AIGC 画面规格）。

这些指标为什么重要：2 分钟竖屏体量靠冲突回合与可拍场次撑满；△是喂给 AIGC 的生成参数，密度不够画面就随机；
地点数直接决定制作成本；结尾留"扣"是集间留存的命脉。脚本只卡"可数"的，情绪振幅/反派智商等交批评者。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

EP_RE = re.compile(r"^#{1,2}\s*第([0-9一二三四五六七八九十百零〇]+)集")
SCENE_RE = re.compile(r"^场\s*(\d+)[-–](\d+)\s+(.+?)\s+(日|夜|晨|黄昏|清晨|深夜)\s+(内|外)")
SCENE_LOOSE_RE = re.compile(r"^场\s*\d+[-–]\d+\s+(.+)$")
DIALOG_RE = re.compile(r"^([^△#场\s【（(：:]{1,12})(（[^）]*）|\([^)]*\))?\s*[：:]\s*(.+)$")
HOOK_HINTS = ("？", "?", "——", "…", "会不会", "究竟", "到底", "怎么办", "要来了", "拉开", "还没", "谁", "为何", "为什么", "能否", "是否")
DEFAULTS = dict(min_chars=1200, min_scenes=10, min_rounds=6, min_delta_ratio=0.20, max_locations=3, min_paren_ratio=0.6)


@dataclass
class EpisodeStats:
    episode: str
    chars: int = 0
    scenes: int = 0
    locations: int = 0
    location_list: list = field(default_factory=list)
    delta_lines: int = 0
    dialog_lines: int = 0
    delta_ratio: float = 0.0
    rounds: int = 0
    paren_ratio: float = 0.0
    ending_hook: str = "unknown"
    slots: int = 0            # 梗机制插槽数（【SLOT-N…】标记），规则每集 ≤1，超出只提示不判死
    warnings: list = field(default_factory=list)
    fails: list = field(default_factory=list)


def _han_count(s: str) -> int:
    return len(re.sub(r"[^一-鿿]", "", s))


def _norm_location(loc: str) -> str:
    # "镇魔渊 内殿" / "临渊城 血祭台" → 取主地点（第一个空格前）合并子区域，避免同地点切细被算成多地点
    loc = loc.strip()
    return loc.split(" ")[0].split("/")[0]


def split_episodes(text: str) -> list[tuple[str, list[str]]]:
    eps, cur, buf = [], None, []
    for line in text.splitlines():
        m = EP_RE.match(line.strip())
        if m:
            if cur is not None:
                eps.append((cur, buf))
            cur, buf = f"第{m.group(1)}集", []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        eps.append((cur, buf))
    return eps


def analyze_episode(name: str, lines: list[str], th: dict) -> EpisodeStats:
    st = EpisodeStats(episode=name)
    content = []
    for l in lines:
        s = l.strip()
        if not s or s.startswith("【"):  # 跳过自检/说明块
            continue
        content.append(s)
    st.chars = sum(_han_count(s) for s in content)
    st.slots = sum(s.count("【SLOT-") for s in content)
    if st.slots > 1:
        st.warnings.append(f"梗插槽 {st.slots} 处 > 1（规则每集≤1，只放切片位）")
    locs, prev_speaker, dialog_with_paren = [], None, 0
    last_content = ""
    for s in content:
        if s.startswith("场"):
            m = SCENE_RE.match(s) or SCENE_LOOSE_RE.match(s)
            if m:
                st.scenes += 1
                loc = m.group(3) if m.re is SCENE_RE else m.group(1).split(" 日")[0].split(" 夜")[0]
                locs.append(_norm_location(loc))
                prev_speaker = None
            continue
        if s.startswith("人物"):
            continue
        if s.startswith("△"):
            st.delta_lines += 1
            last_content = s
            continue
        dm = DIALOG_RE.match(s)
        if dm:
            st.dialog_lines += 1
            if dm.group(2):
                dialog_with_paren += 1
            spk = dm.group(1)
            if prev_speaker and spk != prev_speaker:
                st.rounds += 1
            prev_speaker = spk
            last_content = s
    st.location_list = sorted(set(locs))
    st.locations = len(st.location_list)
    st.delta_ratio = round(st.delta_lines / st.dialog_lines, 2) if st.dialog_lines else 0.0
    st.paren_ratio = round(dialog_with_paren / st.dialog_lines, 2) if st.dialog_lines else 0.0
    st.ending_hook = "疑似留扣" if any(h in last_content for h in HOOK_HINTS) else "疑似收尾（请人工确认是否留扣）"
    # 硬线
    if st.chars < th["min_chars"]:
        st.fails.append(f"字数 {st.chars} < {th['min_chars']}")
    if st.scenes < th["min_scenes"]:
        st.fails.append(f"场数 {st.scenes} < {th['min_scenes']}")
    if st.rounds < th["min_rounds"]:
        st.fails.append(f"冲突回合 {st.rounds} < {th['min_rounds']}")
    if st.delta_ratio < th["min_delta_ratio"]:
        st.fails.append(f"△/台词比 {st.delta_ratio:.2f} < {th['min_delta_ratio']:.2f}")
    if st.locations > th["max_locations"]:
        st.fails.append(f"物理地点 {st.locations} > {th['max_locations']}")
    if st.paren_ratio < th["min_paren_ratio"]:
        st.fails.append(f"对白括注率 {st.paren_ratio:.2f} < {th['min_paren_ratio']:.2f}（AIGC 画面规格：每句台词带情绪/动作括注）")
    return st


def run_episode_check(path: str, **overrides) -> dict:
    th = {**DEFAULTS, **{k: v for k, v in overrides.items() if v is not None}}
    text = open(path, encoding="utf-8").read()
    eps = split_episodes(text)
    if not eps:
        return {"ok": False, "error": "未识别到 `# 第X集` 集标题，检查正文格式"}
    names = [name for name, _ in eps]
    if len(set(names)) != len(names):
        return {"ok": False, "error": "存在重复集标题，先核对集序"}
    results = [asdict(analyze_episode(n, ls, th)) for n, ls in eps]
    failed = [r["episode"] for r in results if r["fails"]]
    return {"ok": True, "thresholds": th, "episodes": results, "failed_episodes": failed, "passed": not failed}


def format_report(r: dict) -> str:
    if not r.get("ok"):
        return f"[error] {r.get('error')}"
    th = r["thresholds"]
    head = (
        f"硬线: 字数≥{th['min_chars']} 场数≥{th['min_scenes']} 回合≥{th['min_rounds']} "
        f"△比≥{th['min_delta_ratio']:.2f} 地点≤{th['max_locations']} 括注率≥{th['min_paren_ratio']:.2f}"
    )
    rows = ["| 集 | 字数 | 场数 | 回合 | △/台词 | 括注率 | 地点 | SLOT | 结尾 | 结果 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for e in r["episodes"]:
        res = "✅" if not e["fails"] else "❌ " + "；".join(e["fails"])
        if e.get("warnings"):
            res += " ⚠ " + "；".join(e["warnings"])
        rows.append(
            f"| {e['episode']} | {e['chars']} | {e['scenes']} | {e['rounds']} | {e['delta_ratio']:.2f} | "
            f"{e['paren_ratio']:.2f} | {e['locations']} | {e.get('slots', 0)} | {e['ending_hook']} | {res} |"
        )
    tail = "全部过闸 ✅" if r["passed"] else f"未过闸集: {', '.join(r['failed_episodes'])} ❌"
    return "\n".join([head, "", *rows, "", tail])
