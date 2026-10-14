"""capacity: one formula for season / episode / text, both bases reported, never a verdict, exit 0."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "skills/drama-studio/scripts/checks"
TOOL = ["python3", "-B", str(CHECKS / "capacity.py")]
VERDICT_WORDS = ("within", "outside", "fits", "exceeds", "pass", "over", "under", "verdict", "ok_by")

MEDIA = {"formatDefault": {"live": {"targetSecondsDefault": 60, "speechRateCharsPerMin": 300, "pauseShare": 0.25,
                                    "speechCharsPerEpisodeMin": 200}}}
TEXT = """# 第六集 仓库

场6A-1 镇仓库 日
人物：老陈、仓管
△ 老陈推门进来。
老陈（喘着气）：箱子在哪儿？
仓管：三年前就签收了（翻本子），签收人王姨。
场6A-2 王姨家 夜
王姨：你都知道了。
不是台词的一行
"""


def walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_keys(v)


class Capacity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.media = self.write("media.json", MEDIA)
        lines = [{"exchangeId": f"e{i}", "startMs": 0, "endMs": ms, "lines": [{"t0": 0, "t1": 1000}, {"t0": 1500, "t1": 2000}]}
                 for i, ms in enumerate((8000, 10000, 12000))]
        self.corpus = self.dir / "exchanges.jsonl"
        self.corpus.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        path = self.dir / name
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def run_tool(self, *args):
        result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def assert_no_verdict(self, out):
        for key in walk_keys(out):
            self.assertFalse(any(w in key.lower() for w in VERDICT_WORDS), key)

    def test_text_counts_dialogue_han_chars_with_letter_scene_ids(self):
        code, out = self.run_tool("text", self.write("ep.md", TEXT), "--media", self.media)
        self.assertEqual(code, 0)
        # 箱子在哪儿 5 + 三年前就签收了签收人王姨 12 + 你都知道了 5; parentheticals removed
        self.assertEqual((out["speechChars"], out["dialogueLinesCounted"]), (22, 3))
        self.assertEqual([s["sceneId"] for s in out["perScene"]], ["6A-1", "6A-2"])
        self.assertEqual(out["estimateSecA"], round(22 / 300 * 60 / 0.75, 1))
        self.assertEqual(out["estimateSecB"], round(22 / 200 * 60, 1))
        self.assert_no_verdict(out)

    def test_text_far_over_target_still_exit_0(self):
        code, out = self.run_tool("text", self.write("long.md", "场1-1 屋 日\n" + "老陈：" + "说" * 5000 + "\n"), "--media", self.media)
        self.assertEqual(code, 0)
        self.assertGreater(out["estimateSecA"], 600)
        self.assert_no_verdict(out)

    def test_episode_both_bases(self):
        plan = {"episode": "6A", "events": {"scenes": [{"sceneId": "6A-1", "beats": [
            {"beatId": "6A-1.b1"}, {"beatId": "6A-1.b2", "picture": True}, {"beatId": "6A-1.b3", "picture": True}]}]},
                "infoLedger": [{"infoId": "I1", "facts": [{"factId": "f1", "carrierBeat": "6A-1.b1"}, {"factId": "f2", "carrierBeat": "6A-1.b2"}]}],
                "capacity": {"targetSec": 60, "status": "fits", "estimateSec": 24.0}}
        code, out = self.run_tool("episode", self.write("plan.json", plan), "--media", self.media, "--corpus", self.corpus)
        self.assertEqual(code, 0)
        self.assertEqual(out["basis"]["exchangeMedianSec"], 10.0)
        self.assertEqual((out["infoCount"], out["pictureBeats"], out["estimateSecA"]), (2, 2, 24.0))
        self.assertEqual((out["dialogueFacts"], out["pictureCarriedFacts"], out["estimateSecB"]), (1, ["f2"], 14.0))
        self.assertNotIn("status", out["declared"])
        self.assert_no_verdict(out)

    def test_season_both_bases_and_split_child_counting(self):
        season = {"episodes": [
            {"episode": 1, "capacity": {"infoCount": 3, "pictureBeats": 1, "targetSec": 60, "status": "exceeds"},
             "infoItemsRough": [{"id": "1.1", "carrier": "d"}, {"id": "1.2", "carrier": "p"}, {"id": "1.3", "carrier": "d", "status": "moved_out", "to": "2A"}]},
            {"episode": "2A", "role": "split_child", "capacity": {"infoCount": 2, "pictureBeats": 0, "targetSec": 60},
             "infoItemsRough": [{"id": "2.1", "carrier": "d"}, {"id": "1.3", "carrier": "d", "status": "moved_in", "from": "1"}]}],
            "finalSequence": [{"id": "1", "newEpisodeNo": 1, "infoCount": 2, "pictureBeats": 1}, {"id": "2A", "newEpisodeNo": 2, "infoCount": 2, "pictureBeats": 0}]}
        code, out = self.run_tool("season", self.write("season.json", season), "--media", self.media, "--exchange-median-sec", "10")
        self.assertEqual(code, 0)
        ep1, ep2 = out["episodes"]
        self.assertEqual((ep1["estimateSecA"], ep1["estimateSecB"]), (32.0, 24.0))  # B: 2 dialogue + (1 picture fact + 1 beat)
        self.assertEqual((ep2["dialogueFacts"], ep2["estimateSecB"]), (2, 20.0))  # split child counted after actions
        self.assertEqual([f["estimateSecB"] for f in out["finalSequence"]], [14.0, 20.0])
        self.assert_no_verdict(out)

    def test_missing_corpus_and_median_is_input_error(self):
        code, out = self.run_tool("episode", self.write("p.json", {"episode": 1}), "--media", self.media)
        self.assertEqual((code, out["ok"]), (1, False))

    def test_runs_with_network_disabled(self):
        sys.dont_write_bytecode = True  # never leave .pyc files inside the bundle
        spec = importlib.util.spec_from_file_location("capacity_offline", CHECKS / "capacity.py")
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(CHECKS))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        buffer = io.StringIO()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network used")), contextlib.redirect_stdout(buffer):
            code = module.main(["text", str(self.write("ep.md", TEXT)), "--media", str(self.media)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["speechChars"], 22)


if __name__ == "__main__":
    unittest.main()
