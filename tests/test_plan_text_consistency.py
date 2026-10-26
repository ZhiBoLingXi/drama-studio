import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts"

TEXT = "# 第1集\n\n场1-1 镇上仓库 日 内\n人物：老陈、王姨\n△老陈推门进来。\n老陈：箱子在仓库里。\n王姨：哦。\n老陈：钱呢？\n"
EPISODE_PLAN = {"infoLedger": [{"infoId": "I1", "facts": [{"factId": "F1", "keywords": ["箱子", "仓库"]}]},
                               {"infoId": "I2", "facts": [{"factId": "F2", "keywords": ["钱", "柜子"]}]}]}
DIALOGUE_PLAN = {"scenes": [{"sceneId": "1-1", "topics": [
    {"topicId": "T1", "segments": [{"segmentId": "T1-s1", "between": ["老陈", "王姨"], "closer": "王姨应了"}],
     "exchanges": [{"exchangeId": "X-T1-01", "speaker": "老陈", "addressee": "王姨", "carries": ["F1"]},
                   {"exchangeId": "X-T1-02", "speaker": "王姨", "addressee": "老陈"}]},
    {"topicId": "T2", "interruptedBy": {"who": "老陈", "at": "X-T1-02 之后"},
     "segments": [{"segmentId": "T2-s1", "between": ["老陈", "王姨"], "closer": "老陈问完"}],
     "exchanges": [{"exchangeId": "X-T2-01", "speaker": "老陈", "addressee": "王姨", "carries": ["F2"]}]}]}]}
MAP = {"text": "text.md",
       "lineToPlan": [{"line": 6, "kind": "dialogue", "exchangeId": "X-T1-01", "carries": ["F1"]},
                      {"line": 7, "kind": "dialogue", "exchangeId": "X-T1-02", "closerOf": "T1-s1"},
                      {"line": 8, "kind": "dialogue", "exchangeId": "X-T2-01", "carries": ["F2"], "closerOf": "T2-s1"}],
       "exchangeToLines": {"X-T1-01": [6], "X-T1-02": [7], "X-T2-01": [8]},
       "verbatimFrom": [{"line": 7, "from": "writer-note WN-1"}]}


class PlanTextConsistencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        (self.dir / "text.md").write_text(TEXT, encoding="utf-8")
        self.episode = self.write("ep.json", EPISODE_PLAN)

    def write(self, name, value):
        path = self.dir / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def run_check(self, dplan=DIALOGUE_PLAN, ptmap=MAP):
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "plan_text_consistency.py"), str(self.write("map.json", ptmap)),
                              "--dialogue-plan", str(self.write("dp.json", dplan)), "--episode-plan", str(self.episode)],
                             capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_aligned_text_passes_and_keyword_gaps_are_low_quality_reports(self):
        code, result = self.run_check()
        self.assertEqual((code, result["passed"]), (0, True), result["rules"])
        keywords = result["rules"]["carries-keywords"]
        self.assertEqual((keywords["status"], keywords["signalQuality"]), ("report", "low"))
        self.assertEqual([(i["factId"], i["missingKeywords"]) for i in keywords["items"]], [("F2", ["柜子"])])
        self.assertEqual(result["verbatimFrom"][0]["line"], 7)
        self.assertEqual(result["rules"]["interrupted-by"]["items"], [])
        self.assertIn("plan_text_consistency.py", result["reproduceCommand"])

    def test_speaker_mismatch_fails(self):
        dplan = copy.deepcopy(DIALOGUE_PLAN)
        dplan["scenes"][0]["topics"][0]["exchanges"][0]["speaker"] = "王姨"
        code, result = self.run_check(dplan)
        self.assertEqual(code, 2)
        self.assertEqual(result["rules"]["speaker-sequence"]["status"], "fail")
        ptmap = copy.deepcopy(MAP)
        ptmap["exchangeToLines"]["X-T1-01"] = [5]
        self.assertEqual(self.run_check(ptmap=ptmap)[0], 2)

    def test_closer_missing_duplicated_or_out_of_order_fails(self):
        missing = copy.deepcopy(MAP)
        del missing["lineToPlan"][1]["closerOf"]
        duplicated = copy.deepcopy(MAP)
        duplicated["lineToPlan"][0]["closerOf"] = "T1-s1"
        for ptmap in (missing, duplicated):
            code, result = self.run_check(ptmap=ptmap)
            self.assertEqual((code, result["rules"]["topic-boundary"]["status"]), (2, "fail"))
        dplan = copy.deepcopy(DIALOGUE_PLAN)
        dplan["scenes"][0]["topics"][0]["segments"].append({"segmentId": "T1-s2", "between": ["王姨", "老陈"], "closer": "y"})
        ordered = copy.deepcopy(MAP)
        ordered["lineToPlan"][0]["closerOf"], ordered["lineToPlan"][1]["closerOf"] = "T1-s1", "T1-s2"
        self.assertEqual(self.run_check(dplan, ordered)[0], 0)
        ordered["lineToPlan"][0]["closerOf"], ordered["lineToPlan"][1]["closerOf"] = "T1-s2", "T1-s1"
        self.assertEqual(self.run_check(dplan, ordered)[0], 2)

    def test_interrupted_by_is_report_or_not_evaluable(self):
        dplan = copy.deepcopy(DIALOGUE_PLAN)
        dplan["scenes"][0]["topics"][1]["interruptedBy"]["who"] = "王姨"
        code, result = self.run_check(dplan)
        self.assertEqual((code, len(result["rules"]["interrupted-by"]["items"])), (0, 1))
        dplan["scenes"][0]["topics"][1]["interruptedBy"]["at"] = "T1-s1 之后"
        code, result = self.run_check(dplan)
        self.assertEqual((code, len(result["rules"]["interrupted-by"]["notEvaluable"])), (0, 1))

    def test_unfindable_text_is_input_error(self):
        ptmap = copy.deepcopy(MAP)
        ptmap["text"] = "nope.md"
        self.assertEqual(self.run_check(ptmap=ptmap)[0], 1)


if __name__ == "__main__":
    unittest.main()
