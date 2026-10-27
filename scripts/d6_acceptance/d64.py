"""D6-4 local acceptance: the corpus commands on the D6-0 small sample (runs/pilot-ep006/corpus) and feedback-ingest
on this project's three feedback sources. Rows carry counts only -- no corpus line, note or derived text.

  - corpus agree on the 40 double-run labels: raw agreement equals the D6-0 blind relabel (corpus/blind/agreement.json);
  - corpus defaults: the recomputed media statistics equal the bundled default-media-profile.json, and the lexicon
    statistics equal the measured block of the bundled genre-lexicon.json;
  - corpus fetch on a fabricated ledger (there was no mali-story connection in D6-4, decisions §1);
  - feedback-ingest on the episode 6 notes, writer-edit-pairs.md §二 and the reality review: each run goes to a
    temporary folder; the project keeps one copy under runs/d64-feedback/ (written once, then compared, never
    overwritten). The inputs are hashed before and after.

Not bundled. Each row: name, command, ok, detail (and explanation when the row is an explained difference).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
DATA = ROOT / "skills/drama-studio/data"
ANIME = "Q18WPQSB6ZEZ9Q3405FZX44VGC"


def row(name, command, ok, **detail):
    return {"stream": "d64", "name": name, "command": command, "ok": bool(ok), **detail}


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    text = proc.stdout if proc.stdout.lstrip().startswith("{") else proc.stderr
    try:
        return proc.returncode, json.loads(text)
    except ValueError:
        return proc.returncode, {"unparsed": text[-300:]}


def digest(paths):
    total = hashlib.sha256()
    for base in paths:
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        for path in files:
            total.update(str(path).encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return total.hexdigest()


def agree_rows(corpus):
    code, out = tool("corpus", "agree", corpus / "exchanges.jsonl")
    old = json.loads((corpus / "blind/agreement.json").read_text(encoding="utf-8"))["stats"]["rates"]
    same = (out["rates"]["functionRaw"], out["rates"]["relationRaw"], out["rates"]["infoModeOverlap"]) == \
        (old["function"], old["relation"], old["infoModeOverlap"])
    return [row("corpus agree：40 条双跑（D6-0 盲标）", "drama_tools.py corpus agree <corpus>/exchanges.jsonl", code == 0 and same,
                compared=out.get("compared"), rates=out.get("rates"), low=len(out.get("low", [])),
                d60Rates={k: old[k] for k in ("function", "relation", "infoModeOverlap")},
                note="未收敛的一致率与 D6-0 blind/agreement.json 相同；收敛后 function、relation 一致率上升，low 少于 D6-0 的 15 条")]


def defaults_rows(corpus):
    code, out = tool("corpus", "defaults", corpus, "--series-format", f"{ANIME}=anime")
    lexicon = json.loads((DATA / "genre-lexicon.json").read_text(encoding="utf-8"))
    same_lexicon = all(entry["measured"]["confirmed"] == measured["confirmed"] and entry["measured"]["n"] == measured["n"]
                       for entry, measured in zip(lexicon["lists"], out.get("lexicon", [])))
    return [row("corpus defaults：媒介档案默认值与随包文件一致", "drama_tools.py corpus defaults <corpus> --series-format <anime>",
                code == 0 and not out.get("mediaDiffs"), mediaDiffs=out.get("mediaDiffs"),
                n={fmt: v.get("n") for fmt, v in out.get("media", {}).get("formatDefault", {}).items()},
                exchangeMedianSec=out.get("media", {}).get("exchangeMedianSec")),
            row("corpus defaults：题材禁词表统计与随包文件一致", "同上", code == 0 and same_lexicon,
                lists=[{k: e.get(k) for k in ("fromGenre", "n", "assumedWords", "evaluable", "candidateCount")} | {"confirmed": len(e.get("confirmed", []))}
                       for e in out.get("lexicon", [])])]


def fetch_rows(base):
    templates = base / "templates.json"
    templates.write_text(json.dumps([{"templateId": f"FAKE-{i}", "episodesTotal": 12, "snapshotIds": {"1": f"s{i}"}} for i in range(3)]),
                         encoding="utf-8")
    ledger = base / "ledger.json"
    steps = [tool("corpus", "fetch", "plan", templates, "--out", ledger)]
    for name, doc in (("before", {"budgetMode": "unconfigured", "availableCredits": None}),):
        path = base / f"budget-{name}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        steps.append(tool("corpus", "fetch", "budget", ledger, "--label", name, "--reading", path))
    for i in range(3):
        response = base / f"resp-{i}.json"
        response.write_text(json.dumps({"data": {"snapshotId": f"s{i}"}}), encoding="utf-8")
        steps.append(tool("corpus", "fetch", "record", ledger, "--template", f"FAKE-{i}", "--episode", 1, "--response", response))
    after = base / "budget-after.json"
    after.write_text(json.dumps({"budgetMode": "unconfigured", "availableCredits": None}), encoding="utf-8")
    steps.append(tool("corpus", "fetch", "budget", ledger, "--label", "after", "--reading", after))
    code, out = tool("corpus", "fetch", "verify", ledger)
    ok = all(c == 0 for c, _ in steps) and code == 0 and out["billing"] == "unconfirmed" and out["items"]["done"] == 3
    return [row("corpus fetch：编造台账（plan／budget／record／verify）", "drama_tools.py corpus fetch plan|budget|record|verify <fake>",
                ok, billing=out.get("billing"), items=out.get("items"), observation=out.get("observation"),
                note="D6-4 没有 mali-story 连接，取用只在编造夹具上跑；真实读取调用次数与预算读数见 docs/d6/d6-4-corpus.md")]


LATER_FIELDS = ("authorRole",)  # writer-note fields added after the D6-4 project copy was written


def same_but_later_fields(kept, fresh):
    """The fresh derivatives equal the kept copy once the writer-note fields added later are left out."""
    if sorted(p.name for p in kept.iterdir()) != sorted(p.name for p in fresh.iterdir()):
        return False
    for path in fresh.iterdir():
        old, new = (kept / path.name).read_bytes(), path.read_bytes()
        if old == new:
            continue
        if path.name != "writer-notes.jsonl":
            return False
        rows = [json.loads(line) for line in new.decode("utf-8").splitlines() if line.strip()]
        stripped = "".join(json.dumps({k: v for k, v in r.items() if k not in LATER_FIELDS}, ensure_ascii=False) + "\n" for r in rows)
        if stripped.encode("utf-8") != old:
            return False
    return True


def feedback_rows(project, base):
    runs = project / "runs"
    sources = [("第 6 集批注", [runs / "input/feedback/writer-feedback-ep006-2026-10-13.md"], "ep006-notes"),
               ("writer-edit-pairs §二", [runs / "input/writer-edit-pairs.md", "--section", "二、"], "edit-pairs-2"),
               ("现实审查（程序类）", [runs / "pilot-v2/reality-check"], "reality-review")]
    kept = runs / "d64-feedback"
    rows = []
    for name, args, folder in sources:
        out_dir = base / folder
        code, out = tool("feedback-ingest", *args, "--out", out_dir)
        counts = {k: v for k, v in (out.get("derivedCounts") or {}).items() if v}
        traceable = True
        for path in out_dir.glob("*.jsonl"):
            if path.name != "writer-notes.jsonl":
                traceable &= all(json.loads(l).get("fromNotes") for l in path.read_text(encoding="utf-8").splitlines() if l.strip())
        target = kept / folder
        kept_note = None
        if not target.exists():  # the project keeps one copy, written once
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(out_dir, target)
            kept_note = "首次写入项目目录"
        explanation = None
        if kept_note is None:
            same = sorted(p.name for p in target.iterdir()) == sorted(p.name for p in out_dir.iterdir()) and all(
                (target / p.name).read_bytes() == p.read_bytes() for p in out_dir.iterdir())
            kept_note = "与项目目录里已有的派生物逐字节相同" if same else "与项目目录里已有的派生物不同（项目副本未改）"
            if not same and same_but_later_fields(target, out_dir):
                explanation = {"why": "D6-4 之后 writer-note 多了 authorRole（字面复读裁定 #1）；去掉这一字段后与项目副本逐字节相同",
                               "laterFields": list(LATER_FIELDS)}
            elif not same:
                traceable = False
        rows.append(row(f"feedback-ingest：{name}", f"drama_tools.py feedback-ingest <{folder}> --out <tmp>",
                        code == 0 and traceable and explanation is None,
                        notes=len(out.get("writerNotes", [])), levels={k: v for k, v in (out.get("levelCounts") or {}).items() if v},
                        derived=counts, everyDerivedHasFromNotes=traceable, projectCopy=f"runs/d64-feedback/{folder}", kept=kept_note,
                        **({"explanation": explanation} if explanation else {})))
    return rows


def run(V) -> list[dict]:
    V = Path(V).resolve()
    project = V.parents[1] if V.name == "pilot-v2" else V.parent
    corpus = project / "runs/pilot-ep006/corpus"
    inputs = [corpus, project / "runs/input/feedback/writer-feedback-ep006-2026-10-13.md", project / "runs/input/writer-edit-pairs.md",
              project / "runs/pilot-v2/reality-check"]
    missing = [str(p) for p in inputs if not p.exists()]
    if missing:
        return [{"skipped": True, "name": "D6-4 语料与反馈", "reason": f"缺：{missing}"}]
    before = digest(inputs)
    with tempfile.TemporaryDirectory() as base:
        base = Path(base)
        rows = agree_rows(corpus) + defaults_rows(corpus) + fetch_rows(base) + feedback_rows(project, base)
    after = digest(inputs)
    rows.append(row("语料与反馈原文件未被改动", "sha256 of the inputs, before and after", before == after, before=before[:16], after=after[:16]))
    return rows


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ROOT / "projects/qige-xiongdi/runs/pilot-v2"
    print(json.dumps(run(target), ensure_ascii=False, indent=2))
