"""D6-1 corpus S commands: segment / label (S part) / filter / lexicon / rate
(skills/drama-studio/scripts/corpus_*.py). One positive and one negative fixture per S rule,
all synthetic (shared brief rule #2 -- no project names, plot or dialogue from any real show).
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "skills/drama-studio/scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(f"corpus_{name}", CORPUS_DIR / f"corpus_{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


segment = load("segment")
label = load("label")
filter_mod = load("filter")
lexicon = load("lexicon")
rate = load("rate")


def raw_md(storyline_blocks, transcript_blocks):
    story = "\n\n".join(f"{s} – {e}\n{text}" for s, e, text in storyline_blocks)
    lines = []
    for t0, t1, speaker, state, content in transcript_blocks:
        lines.append(f"{t0}–{t1}\nSpeaker: {speaker}\nState: {state}\nContent: {content}")
    transcript_body = "\n\n".join(lines)
    return (
        f"## Storyline\n\n{story}\n\n"
        "## Speakers and Transcript\n\n"
        "Speaker profiles:\n老赵：师傅\n小苟：徒弟\n\n"
        f"{transcript_body}\n"
    )


def write_episode(path, template_id, episode_index, raw_md_text, title="测试剧"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "templateId": template_id, "episodeIndex": episode_index, "title": title,
        "rawMd": raw_md_text,
    }, ensure_ascii=False), encoding="utf-8")


class SegmentTests(unittest.TestCase):
    def test_pause_gap_is_a_candidate_boundary(self):
        text = raw_md(
            [("00:00.000", "00:03.000", "张三和李四谈话。")],
            [("00:00.500", "00:02.000", "张三", "", "你好。"),
             ("00:07.000", "00:09.000", "李四", "", "好久不见。")],
        )
        _, lines, secs = segment.T.parse_transcript(text)
        boundaries = segment.candidate_boundaries(lines, secs)
        self.assertIn("pause", boundaries[1]["reasons"])

    def test_no_pause_boundary_under_threshold_same_speaker(self):
        text = raw_md(
            [("00:00.000", "00:03.000", "张三说话。")],
            [("00:00.000", "00:01.000", "张三", "", "第一句。"),
             ("00:01.500", "00:02.500", "张三", "", "第二句。")],
        )
        _, lines, secs = segment.T.parse_transcript(text)
        boundaries = segment.candidate_boundaries(lines, secs)
        by_index = {b["lineIndex"]: b["reasons"] for b in boundaries}
        self.assertNotIn(1, by_index)


class LabelFormatTests(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "exchangeId": "T1-e01-01", "templateId": "T1", "episodeIndex": 1,
            "lineStart": 0, "lineEnd": 1, "about": "测试",
            "situation": {"speakerWants": "x", "listenerKnows": "y", "relation": "师徒",
                          "powerDirection": "down", "addresseeIsChild": False,
                          "emotion": {"a": "怒", "b": "怕"},
                          "function": {"primary": "训斥"}, "infoMode": ["问答"],
                          "audienceLearns": "z"},
            "walkthrough": "w", "quality": {"transcript": "ok", "label": "ok", "note": ""},
        }
        row.update(overrides)
        return row

    def _run(self, rows, raw_dir=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.jsonl"
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
            return label.run_label(str(path), raw_dir)

    def test_well_formed_row_has_no_format_issues(self):
        result = self._run([self._row()])
        self.assertEqual(result["formatIssueCount"], 0)

    def test_missing_required_field_is_a_format_issue(self):
        row = self._row()
        del row["walkthrough"]
        result = self._run([row])
        self.assertEqual(result["formatIssueCount"], 1)
        self.assertEqual(result["rows"][0]["formatIssues"][0]["code"], "missing_field")

    def test_out_of_vocab_without_note_warns(self):
        row = self._row()
        row["situation"]["relation"] = "不在词表里的关系"
        result = self._run([row])
        self.assertEqual(result["vocabWarningCount"], 1)
        self.assertEqual(result["formatIssueCount"], 0)

    def test_out_of_vocab_with_explanatory_note_does_not_warn(self):
        row = self._row()
        row["situation"]["relation"] = "不在词表里的关系"
        row["quality"]["note"] = "新值，词表暂未收录"
        result = self._run([row])
        self.assertEqual(result["vocabWarningCount"], 0)

    def test_duplicate_exchange_id_is_a_format_issue(self):
        result = self._run([self._row(), self._row()])
        self.assertEqual(result["formatIssueCount"], 1)
        self.assertEqual(result["rows"][1]["formatIssues"][0]["code"], "duplicate_exchange_id")

    def test_cli_exits_2_on_format_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.jsonl"
            row = self._row()
            del row["about"]
            path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = label.main([str(path)])
        self.assertEqual(code, 2)


class SpeakerAttributionSuspectTests(unittest.TestCase):
    def _raw_dir_with_merged_line(self):
        tmp = tempfile.TemporaryDirectory()
        text = raw_md(
            [("00:00.000", "00:05.000", "老赵在屋内讲规则。"),
             ("00:05.000", "00:10.000", "小苟在门外开口说话。"),
             ("00:10.000", "00:15.000", "两人道别。")],
            [("00:03.000", "00:08.000", "老赵", "", "规则不能改，你还敢错。"),
             ("00:11.000", "00:13.000", "小苟", "", "我知错了。")],
        )
        write_episode(Path(tmp.name) / "T1" / "ep-001.json", "T1", 1, text)
        return tmp

    def test_line_spanning_two_storyline_speakers_is_suspect(self):
        tmp = self._raw_dir_with_merged_line()
        self.addCleanup(tmp.cleanup)
        with open(Path(tmp.name) / "T1" / "ep-001.json", encoding="utf-8") as f:
            rec = json.load(f)
        _, lines, secs = segment.T.parse_transcript(rec["rawMd"])
        suspect, reasons = label.speaker_attribution_suspect(lines, secs, 0, 0)
        self.assertTrue(suspect)
        self.assertEqual(reasons[0]["otherNamesInParagraph"], ["小苟"])

    def test_clean_single_paragraph_line_is_not_suspect(self):
        tmp = self._raw_dir_with_merged_line()
        self.addCleanup(tmp.cleanup)
        with open(Path(tmp.name) / "T1" / "ep-001.json", encoding="utf-8") as f:
            rec = json.load(f)
        _, lines, secs = segment.T.parse_transcript(rec["rawMd"])
        suspect, reasons = label.speaker_attribution_suspect(lines, secs, 1, 1)
        self.assertFalse(suspect)
        self.assertEqual(reasons, [])


class FilterTests(unittest.TestCase):
    def _run(self, rows, manifest=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exchanges.jsonl"
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
            manifest_path = None
            if manifest is not None:
                manifest_path = Path(tmp) / "manifest.json"
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            return filter_mod.run_filter([str(path)], str(manifest_path) if manifest_path else None)

    def _exchange(self, **overrides):
        row = {
            "exchangeId": "E1", "templateId": "T1", "episodeIndex": 1, "snapshotId": "sha256:aaa",
            "evidenceValidation": "not_run",
            "lines": [
                {"t0": 0, "t1": 1000, "speaker": "A", "state": "", "text": "你好", "isMonologue": False},
                {"t0": 1000, "t1": 2000, "speaker": "B", "state": "", "text": "你好吗", "isMonologue": False},
            ],
        }
        row.update(overrides)
        return row

    def test_two_speaker_exchange_passes(self):
        result = self._run([self._exchange()])
        self.assertFalse(result["results"][0]["excluded"])

    def test_single_speaker_run_is_excluded_as_no_response(self):
        row = self._exchange(lines=[
            {"t0": 0, "t1": 1000, "speaker": "A", "state": "", "text": "自语1", "isMonologue": False},
            {"t0": 1000, "t1": 2000, "speaker": "A", "state": "", "text": "自语2", "isMonologue": False},
        ])
        result = self._run([row])
        self.assertIn("no_response", result["results"][0]["reasons"])

    def test_ad_copy_is_excluded(self):
        row = self._exchange(lines=[
            {"t0": 0, "t1": 1000, "speaker": "A", "state": "", "text": "记得关注公众号", "isMonologue": False},
            {"t0": 1000, "t1": 2000, "speaker": "B", "state": "", "text": "好的", "isMonologue": False},
        ])
        result = self._run([row])
        self.assertIn("ad_copy", result["results"][0]["reasons"])

    def test_all_monologue_is_excluded(self):
        row = self._exchange(lines=[
            {"t0": 0, "t1": 1000, "speaker": "A（内心独白）", "state": "", "text": "心声", "isMonologue": True},
        ])
        result = self._run([row])
        self.assertIn("all_monologue", result["results"][0]["reasons"])

    def test_nonmonotonic_timecodes_are_unparseable(self):
        row = self._exchange(lines=[
            {"t0": 2000, "t1": 1000, "speaker": "A", "state": "", "text": "x", "isMonologue": False},
        ])
        result = self._run([row])
        self.assertIn("transcript_unparseable", result["results"][0]["reasons"])

    def test_stale_snapshot_is_flagged_against_manifest(self):
        manifest = {"episodes": [{"templateId": "T1", "episodeIndex": 1, "snapshotId": "sha256:new"}]}
        result = self._run([self._exchange()], manifest=manifest)
        self.assertIn("stale", result["results"][0]["reasons"])

    def test_current_snapshot_is_not_stale(self):
        manifest = {"episodes": [{"templateId": "T1", "episodeIndex": 1, "snapshotId": "sha256:aaa"}]}
        result = self._run([self._exchange()], manifest=manifest)
        self.assertNotIn("stale", result["results"][0]["reasons"])
        self.assertEqual(result["results"][0]["notes"]["staleStatus"], "current")


class LexiconTests(unittest.TestCase):
    def _lexicon(self):
        return {
            "note": "test", "lists": [
                {"fromGenre": "仙侠", "words": ["为师", "宗主"], "source": "assumed"},
            ],
        }

    def test_genre_word_in_a_different_genre_script_is_a_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lex_path = Path(tmp) / "lex.json"
            lex_path.write_text(json.dumps(self._lexicon(), ensure_ascii=False), encoding="utf-8")
            script_path = Path(tmp) / "script.md"
            script_path.write_text("张三：为师教你一招。\n", encoding="utf-8")
            result = lexicon.run_lexicon(str(script_path), "现实", str(lex_path))
        self.assertEqual(result["hitCount"], 1)
        self.assertEqual(result["hits"][0]["word"], "为师")

    def test_word_list_for_the_projects_own_genre_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            lex_path = Path(tmp) / "lex.json"
            lex_path.write_text(json.dumps(self._lexicon(), ensure_ascii=False), encoding="utf-8")
            script_path = Path(tmp) / "script.md"
            script_path.write_text("张三：为师教你一招。\n", encoding="utf-8")
            result = lexicon.run_lexicon(str(script_path), "仙侠", str(lex_path))
        self.assertEqual(result["hitCount"], 0)


class RateTests(unittest.TestCase):
    def test_known_synthetic_episode_reproduces_hand_computed_rate(self):
        # One voiced line 00:00-00:10 with 10 Chinese chars -> 60 chars/min during speech;
        # episode spans 0-20s -> grossCharsPerMinute = 10/20*60 = 30; pauseShare = 1-10/20 = 0.5.
        text = raw_md(
            [("00:00.000", "00:20.000", "场景说明。")],
            [("00:00.000", "00:10.000", "张三", "", "一二三四五六七八九十")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            write_episode(Path(tmp) / "T1" / "ep-001.json", "T1", 1, text)
            profile = rate.compute_media_profile(tmp, series_format={"T1": "live"})
        series = profile["perSeries"]["T1"]
        self.assertEqual(series["speechRateCharsPerMin"], 60.0)
        self.assertEqual(series["grossCharsPerMinute"], 30.0)
        self.assertEqual(series["pauseShare"], 0.5)
        self.assertEqual(profile["calibration"], "corpus_default")

    def test_empty_raw_dir_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                rate.compute_media_profile(tmp)

    def test_project_override_sets_measured_project(self):
        text = raw_md(
            [("00:00.000", "00:20.000", "场景说明。")],
            [("00:00.000", "00:10.000", "张三", "", "一二三四五六七八九十")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            write_episode(Path(tmp) / "T1" / "ep-001.json", "T1", 1, text)
            profile = rate.compute_media_profile(
                tmp, series_format={"T1": "live"},
                project_overrides={"live": {"speechRateCharsPerMin": 300.0}})
        self.assertEqual(profile["formatDefault"]["live"]["source"], "measured_project")
        self.assertEqual(profile["formatDefault"]["live"]["projectValue"]["speechRateCharsPerMin"], 300.0)
        self.assertEqual(profile["calibration"], "project_measured")


class CliSmokeTests(unittest.TestCase):
    """Each command stays runnable as a standalone script (`python3 -B <file> ...`)."""

    def test_rate_cli_runs_and_reports_reproduce_command(self):
        text = raw_md(
            [("00:00.000", "00:10.000", "x")],
            [("00:00.000", "00:05.000", "张三", "", "你好")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            write_episode(Path(tmp) / "T1" / "ep-001.json", "T1", 1, text)
            run = subprocess.run(
                [sys.executable, "-B", str(CORPUS_DIR / "corpus_rate.py"), tmp],
                capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertIn("reproduceCommand", result)


if __name__ == "__main__":
    unittest.main()
