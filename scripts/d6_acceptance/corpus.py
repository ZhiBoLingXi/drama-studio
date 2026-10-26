"""D6-1 local acceptance, stream D (corpus S commands: segment / label / filter / lexicon / rate).

Reads only the real 阶段 A artifacts in E (the sibling `pilot-ep006` directory next to V,
`runs/pilot-v2` -- same "E/" convention `schemas.py` uses) and writes nothing. Not bundled.

Required by the shared brief: rate's physical quantities must match `E/media-profile-v0.json`;
segment's candidate count against `E/corpus/exchanges.jsonl`'s real count must either match or
be explained. Both are covered below; label/filter/lexicon have no D6-0 baseline to replay
against (the阶段 A run never implemented S exclusion/vocab checks), so their rows report counts
on the real data as a smoke test instead of a byte-for-byte comparison.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "skills/drama-studio/scripts"
PY = [sys.executable, "-B"]

SERIES_FORMAT = {
    "CKXRX6FCVQ6MRVFVPDN8SZV1SA": "live",
    "WGGTPN1C853MEEQPE3P1NQPP7V": "live",
    "Q18WPQSB6ZEZ9Q3405FZX44VGC": "anime",
}


def _E(V: Path) -> Path:
    return V.parent / "pilot-ep006"


def cli(module, *args):
    command = [*PY, str(CORPUS_DIR / f"corpus_{module}.py"), *map(str, args)]
    run = subprocess.run(command, capture_output=True, text=True)
    try:
        out = json.loads(run.stdout) if run.stdout.strip() else json.loads(run.stderr)
    except json.JSONDecodeError:
        out = {"unparsed": (run.stdout or run.stderr)[:500]}
    return run.returncode, out, " ".join(command[2:])


def row(name, command, ok, **detail):
    return {"stream": "D", "name": name, "command": command, "ok": bool(ok), **detail}


def acceptance_rate(E: Path):
    args = [str(E / "corpus/raw")]
    for tid, fmt in SERIES_FORMAT.items():
        args += ["--series-format", f"{tid}={fmt}"]
    code, out, cmd = cli("rate", *args)
    real = json.loads((E / "media-profile-v0.json").read_text(encoding="utf-8"))
    mismatches = []
    for fmt in ("live", "anime"):
        o, r = out["formatDefault"][fmt], real["formatDefault"][fmt]
        for field, real_field in (("targetSecondsDefault", "targetSecondsDefault"),
                                   ("speechRateCharsPerMin", "speechRateCharsPerMin"),
                                   ("grossCharsPerMinute", "speechCharsPerEpisodeMin"),
                                   ("pauseShare", "pauseShare")):
            if o[field] != r[real_field]:
                mismatches.append(f"formatDefault.{fmt}.{field}: {o[field]} != real {r[real_field]}")
    for tid in SERIES_FORMAT:
        o, r = out["perSeries"][tid], real["perSeries"][tid]
        for field, real_field in (("speechRateCharsPerMin", "speechRateCharsPerMin"),
                                   ("speechRateCharsPerSec", "speechRateCharsPerSec"),
                                   ("grossCharsPerMinute", "speechCharsPerEpisodeMin"),
                                   ("pauseShare", "pauseShare"), ("pauseShareVoicedOnly", "pauseShareVoicedOnly")):
            if o[field] != r[real_field]:
                mismatches.append(f"perSeries.{tid[:4]}.{field}: {o[field]} != real {r[real_field]}")
        if o["episodeDurationSec"] != r["episodeDurationSec"]:
            mismatches.append(f"perSeries.{tid[:4]}.episodeDurationSec differs")
    return [row("rate matches media-profile-v0.json physical quantities", cmd, code == 0 and not mismatches,
                exitCode=code, mismatches=mismatches,
                newFields={"grossCharsPerMinute": "renamed from the prototype's speechCharsPerEpisodeMin (plan §2.1 #8)",
                           "pictureBeatSec": out.get("pictureBeatSec")})]


def acceptance_segment(E: Path):
    raw_files = sorted(glob.glob(str(E / "corpus/raw/*/ep-*.json")))
    code, out, cmd = cli("segment", *raw_files)
    real_count = sum(1 for _ in (E / "corpus/exchanges.jsonl").read_text(encoding="utf-8").splitlines() if _.strip())
    candidate_count = out.get("totalSegmentCount")
    explanation = (
        "segment.py 只给 S 候选边界（新说话人／停顿≥4s／连续独白／Storyline 分段切换），"
        "不做话题合并；真实 exchanges.jsonl 是 M 把候选合并成话题级交换后的结果，"
        "候选数天然更多（本次 {cand} 条候选 vs {real} 条真实交换，约 {ratio:.1f}x）；"
        "这是「S 候选，M 确认」分工的预期差，不是 bug。"
    ).format(cand=candidate_count, real=real_count, ratio=(candidate_count / real_count) if real_count else 0)
    return [row("segment candidate count vs real exchanges.jsonl (explained, not required to match)", cmd,
                code == 0, exitCode=code, episodeCount=out.get("episodeCount"),
                candidateSegmentCount=candidate_count, realExchangeCount=real_count, explanation=explanation)]


def acceptance_label(E: Path):
    rows = []
    for path in sorted(glob.glob(str(E / "corpus/labels/*.jsonl"))):
        code, out, cmd = cli("label", path, "--raw-dir", str(E / "corpus/raw"))
        rows.append(row(f"label {Path(path).name}", cmd, code in (0, 2) and "formatIssueCount" in out,
                        exitCode=code, rowCount=out.get("rowCount"), formatIssueCount=out.get("formatIssueCount"),
                        vocabWarningCount=out.get("vocabWarningCount"),
                        speakerAttributionSuspectCount=out.get("speakerAttributionSuspectCount"),
                        explanation="真实标注文件没有正式词表闸门作基线；这里只核验格式通过、"
                                    "并把 speakerAttributionSuspect 候选数和词表外提醒数如实列出"))
    return rows


def acceptance_filter(E: Path):
    code, out, cmd = cli("filter", str(E / "corpus/exchanges.jsonl"), "--manifest", str(E / "corpus/manifest.json"))
    return [row("filter real exchanges.jsonl", cmd, code == 0, exitCode=code, inputCount=out.get("inputCount"),
                passCount=out.get("passCount"), excludedCount=out.get("excludedCount"), byReason=out.get("byReason"),
                explanation="阶段 A 从未实现排除逻辑，没有基线可比；这里只做烟雾测试，报告剔除分布供人工复核")]


def acceptance_lexicon(E: Path):
    code, out, cmd = cli("lexicon", str(E / "corpus/exchanges.jsonl"), "--project-genre", "现实", "--mode", "corpus")
    return [row("lexicon GENRE_LEAK scan on real exchanges.jsonl", cmd, code == 0, exitCode=code,
                hitCount=out.get("hitCount"),
                explanation="stage-a-report.md §8 #2 已记录《糯糯》样本原话带「为师」「宗主」等词；"
                            "命中数非零是预期的事实核对，只报不拦")]


def run(V) -> list[dict]:
    V = Path(V)
    E = _E(V)
    if not E.is_dir():
        return [{"stream": "D", "name": "skipped", "ok": True, "detail": f"{E} 不存在，跳过本地验收"}]
    return (acceptance_rate(E) + acceptance_segment(E) + acceptance_label(E) +
            acceptance_filter(E) + acceptance_lexicon(E))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    result = run(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["ok"] for r in result) else 2)
