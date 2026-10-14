"""Shared parsing for mali-story deconstruction-template rawMd (Storyline / Visible Text /
Speakers and Transcript). Parsing and description statistics only -- never a judgment call.

Ported from the阶段 A手工脚本（D6-0 试点的 corpus_lib.py）so the
formal corpus/* commands reproduce the same real numbers; extended with a Storyline-paragraph
parser used by label.py's `speakerAttributionSuspect` heuristic (stage-a-report.md §8 #1).

Not a command by itself -- no `main`. Imported by segment.py / label.py / rate.py via the same
sys.path-insert pattern used by the阶段 A scripts, so each command stays runnable standalone.
"""
from __future__ import annotations

import re

TS = r"(\d{2}):(\d{2})\.(\d{3})"
TS_RANGE = re.compile(rf"^{TS}\s*[–-]\s*{TS}\s*$")
LINE_BLOCK = re.compile(
    # The [ \t]* right after "State:" (not \s*) is deliberate: a blank State value ("State:
    # \n") must not let the greedy whitespace class eat that newline too, or it swallows the
    # following "Content:" line into the state capture (reproduced with a synthetic empty-
    # state fixture; real exports so far always have non-empty State text so this never showed
    # up against them).
    rf"^{TS}\s*[–-]\s*{TS}\s*\n\s*Speaker:\s*(?P<spk>.+?)\s*\n(?:\s*State:[ \t]*(?P<state>.*?)\s*\n)?\s*Content:\s*(?P<content>.+?)\s*(?=\n\s*\n|\Z)",
    re.M | re.S,
)
# A Storyline paragraph starts with a bare timestamp range, then prose until the next one.
STORYLINE_BLOCK = re.compile(
    rf"^{TS}\s*[–-]\s*{TS}\s*\n(?P<text>.*?)(?=\n{TS}\s*[–-]\s*{TS}\s*\n|\Z)",
    re.M | re.S,
)


def ms(h, m, s):
    return (int(h) * 60 + int(m)) * 1000 + int(s)


def split_sections(raw_md):
    """Split rawMd on '## ' headings into {heading: body}."""
    out = {}
    cur = None
    buf = []
    for line in raw_md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def parse_transcript(raw_md):
    """Return (speaker_profiles_text, lines[], sections{}). lines[] keeps original order."""
    secs = split_sections(raw_md)
    tr = secs.get("Speakers and Transcript", "")
    profiles = ""
    body = tr
    m = re.search(r"Speaker profiles:\s*\n(.*?)(?=\n\s*\n\d{2}:\d{2}\.\d{3})", tr, re.S)
    if m:
        profiles = m.group(1).strip()
        body = tr[m.end():]
    lines = []
    for mm in LINE_BLOCK.finditer(body):
        g = mm.groups()
        t0 = ms(g[0], g[1], g[2])
        t1 = ms(g[3], g[4], g[5])
        spk = mm.group("spk").strip()
        state = (mm.group("state") or "").strip()
        content = mm.group("content").strip().replace("\n", " ")
        content = re.sub(r"^[“\"]|[”\"]$", "", content)
        lines.append({"t0": t0, "t1": t1, "speaker": spk, "state": state, "text": content})
    return profiles, lines, secs


def is_monologue(line):
    s = line["speaker"] + " " + line["state"]
    return bool(re.search(r"内心|独白|OS|旁白|心声|画外", s))


def cjk_count(s):
    return len(re.findall(r"[一-鿿]", s))


def episode_stats(lines, storyline_end_ms_value=None):
    voiced = [l for l in lines if not is_monologue(l)]
    speech_chars = sum(cjk_count(l["text"]) for l in voiced)
    voiced_ms = sum(max(0, l["t1"] - l["t0"]) for l in voiced)
    all_ms = sum(max(0, l["t1"] - l["t0"]) for l in lines)
    end = max([l["t1"] for l in lines] + ([storyline_end_ms_value] if storyline_end_ms_value else [0]))
    return {
        "lines": len(lines),
        "voicedLines": len(voiced),
        "monologueLines": len(lines) - len(voiced),
        "speechChars": speech_chars,
        "voicedMs": voiced_ms,
        "allSpeechMs": all_ms,
        "episodeEndMs": end,
        "speakers": sorted({l["speaker"] for l in voiced}),
    }


def storyline_end_ms(secs):
    st = secs.get("Storyline", "")
    ends = []
    for m in re.finditer(rf"{TS}\s*[–-]\s*{TS}", st):
        g = m.groups()
        ends.append(ms(g[3], g[4], g[5]))
    return max(ends) if ends else None


def storyline_paragraphs(secs):
    """[{startMs, endMs, text}] for each timestamped Storyline paragraph, in order.

    Used only to cross-check which character name the拉片方 description associates with a
    time range -- plain substring search over the paragraph text, no model call.
    """
    st = secs.get("Storyline", "")
    out = []
    for m in STORYLINE_BLOCK.finditer(st):
        g = m.groups()
        start = ms(g[0], g[1], g[2])
        end = ms(g[3], g[4], g[5])
        out.append({"startMs": start, "endMs": end, "text": m.group("text").strip()})
    return out


def overlapping_paragraphs(paragraphs, t0, t1):
    """Storyline paragraphs whose [startMs, endMs) overlaps the line's [t0, t1)."""
    return [p for p in paragraphs if p["startMs"] < t1 and p["endMs"] > t0]
