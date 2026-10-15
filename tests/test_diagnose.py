import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts/checks"

TEXT = ("# 第9集\n\n场9-1 镇上仓库 日 内\n人物：老陈、王姨\n"
        "王姨：钱在柜子里吗？\n王姨：你听到没？\n老陈：走。\n老陈：快点。\n老陈：出发。\n王姨：嗯。\n"
        "\n场9-2 镇上仓库 夜 内\n人物：老陈、王姨、仓管\n△箱子在仓库里。\n"
        "老陈（对王姨）：好。\n老陈（对仓管）：知道了，明白了。接着办。\n王姨（OS）：钞票在抽屉。\n")
EPISODE_PLAN = {"infoLedger": [{"infoId": "I1", "facts": [{"factId": "F1", "keywords": ["箱子", "仓库"]}]},
                               {"infoId": "I3", "facts": [{"factId": "F3", "keywords": ["钞票", "抽屉"]}]}]}


def dialogue_plan(monologue=False):
    scene = {"sceneId": "9-2", "topics": [
        {"topicId": "T1", "situation": {"speakerWants": "x"},
         "exchanges": [{"exchangeId": "X-D2-01", "speaker": "老陈", "addressee": "王姨", "carries": ["F1"], "oneItemPerLine": False}]},
        {"topicId": "T2", "situation": {"speakerWants": "y"},
         "exchanges": [{"exchangeId": "X-D2-02", "speaker": "老陈", "addressee": "仓管", "carries": ["F1"], "oneItemPerLine": True}]}]}
    if monologue:
        scene["monologues"] = [{"carries": ["F3"], "whyNoAddressee": "心里话"}]
    return {"scenes": [scene]}


MAP = {"exchangeToLines": {"X-D2-01": [15], "X-D2-02": [16]}}


def keys(value):
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()


class DiagnoseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.text = self.dir / "text.md"
        self.text.write_text(TEXT, encoding="utf-8")

    def write(self, name, value):
        path = self.dir / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def run_diagnose(self, *args):
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "diagnose.py"), str(self.text), *args], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def full(self, monologue=False):
        return self.run_diagnose("--plan-text-map", self.write("map.json", MAP),
                                 "--dialogue-plan", self.write("dp.json", dialogue_plan(monologue)),
                                 "--episode-plan", self.write("ep.json", EPISODE_PLAN))

    def test_text_only_signals_and_missing_inputs_are_not_evaluable(self):
        code, result = self.run_diagnose()
        self.assertEqual(code, 0)
        counts = result["signalCounts"]
        self.assertEqual((counts.get("QUESTION_UNANSWERED"), counts.get("IMPERATIVE_CHAIN")), (1, 1))
        self.assertGreaterEqual(counts.get("ONE_BREATH", 0), 1)
        self.assertEqual({n["code"] for n in result["notEvaluable"]},
                         {"OBJECT_MISSING", "INFO_IN_ACTION_ONLY", "INFO_REPEATED", "MONOLOGUE_FALLBACK", "ADDRESSEE_JUMP",
                          "ONE_ITEM_PER_LINE_MISMATCH", "UNCHANGED_ACROSS_REVISIONS"})
        self.assertIn("diagnose.py", result["reproduceCommand"])

    def test_plan_signals_carry_situation_and_quality(self):
        code, result = self.full()
        counts = result["signalCounts"]
        self.assertEqual(code, 0)
        self.assertEqual([counts.get(c) for c in ("INFO_IN_ACTION_ONLY", "INFO_REPEATED", "ADDRESSEE_JUMP",
                                                  "ONE_ITEM_PER_LINE_MISMATCH", "MONOLOGUE_FALLBACK")], [1, 2, 1, 1, 1])
        jump = next(s for s in result["signals"] if s["code"] == "ADDRESSEE_JUMP")
        self.assertEqual((jump["topic"], jump["situation"]), ("T2", {"speakerWants": "y"}))
        mismatch = next(s for s in result["signals"] if s["code"] == "ONE_ITEM_PER_LINE_MISMATCH")
        self.assertEqual(mismatch["signalQuality"], "low")
        self.assertTrue(all(s["signalQuality"] in ("low", "structural") for s in result["signals"]))

    def test_monologue_permit_removes_fallback(self):
        self.assertEqual(self.full(monologue=True)[1]["signalCounts"].get("MONOLOGUE_FALLBACK", 0), 0)

    def test_unchanged_across_revisions_matches_scene_ids_only(self):
        same = self.dir / "b.md"
        same.write_text("场9-1 镇上仓库 日 内\n人物：老陈、王姨\n王姨：别的？\n王姨：还有吗？\n老陈：好。\n老陈：行。\n老陈：走了。\n王姨：嗯嗯。\n",
                        encoding="utf-8")
        other = self.dir / "c.md"
        other.write_text("场9-9 别处 日 内\n人物：老陈\n老陈：你好。\n", encoding="utf-8")
        _, result = self.run_diagnose("--compare-with", str(same), str(other))
        found = [s for s in result["signals"] if s["code"] == "UNCHANGED_ACROSS_REVISIONS"]
        self.assertEqual([s["scene"] for s in found], ["9-1"])
        self.assertIn("9-9", result["unchangedAcrossRevisionsSkippedScenes"][1]["bOnlyScenes"])

    def test_numbers_never_judge(self):
        _, result = self.full()
        self.assertFalse({"within", "outside", "inRange", "passed_by_number"} & keys(result))
        self.assertIsNone(result["passed"])


if __name__ == "__main__":
    unittest.main()
