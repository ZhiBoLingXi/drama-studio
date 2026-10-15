import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts/checks"

PLAN = {"episode": "1", "infoLedger": [
            {"infoId": "I1", "facts": [{"factId": "I1-f1", "text": "老陈在仓库找到箱子", "keywords": ["老陈", "箱子", "仓库"]}]},
            {"infoId": "I2", "facts": [{"factId": "I2-f1", "text": "王姨把钥匙藏进米缸", "keywords": ["钥匙", "米缸"]}]}],
        "events": {"scenes": [{"sceneId": "1-1", "beats": [{"beatId": "1-1.b1", "text": "老陈抱着箱子，走出仓库"}]}]},
        "exit": {"closingEvent": {"beatRef": "1-1.b1"}}}


def retell(**extra):
    return {"schema": "retell-record/v0-pilot", "target": {"kind": "episode_plan_events", "episode": "1"},
            "readingScope": ["episode_plan_events"], "promptVersion": {"files": [{"path": "cold-read.md", "sha256": "sha256:0"}]},
            "events": [{"order": 1, "what": "老陈在仓库翻出箱子", "why": "x", "sourceLine": "1-1.b1"},
                       {"order": 2, "what": "王姨把那把小东西埋进装米的缸", "why": "x", "sourceLine": "1-1.b2"}],
            "stopsAt": "老陈抱着箱子出门", **extra}


class RetellCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.plan = self.write("plan.json", PLAN)

    def write(self, name, value):
        path = self.dir / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def run_check(self, value, *args):
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "retell_check.py"), str(self.write("r.json", value)),
                              "--plan", str(self.plan), *map(str, args)], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def statuses(self, result):
        return {f["factId"]: f["status"] for f in result["facts"]}

    def test_without_fact_refs_keywords_decide_and_are_marked_low_quality(self):
        code, result = self.run_check(retell())
        self.assertEqual(code, 0)
        self.assertEqual(self.statuses(result), {"I1-f1": "retold", "I2-f1": "missing"})
        self.assertEqual(result["basis"], "keywords")
        self.assertTrue(all(f["signalQuality"] == "low" for f in result["facts"]))
        self.assertIn("retell_check.py", result["reproduceCommand"])

    def test_reader_fact_refs_win_over_keywords(self):
        value = retell()
        value["events"][0]["factRefs"] = ["I1-f1"]
        value["events"][1]["factRefs"] = ["I2-f1"]
        code, result = self.run_check(value)
        self.assertEqual(self.statuses(result), {"I1-f1": "retold", "I2-f1": "retold"})
        self.assertEqual(result["facts"][1]["keywordEvidence"]["status"], "missing")

    def test_unreferenced_fact_is_missing_when_refs_exist(self):
        value = retell()
        value["events"][0]["factRefs"] = ["I1-f1"]
        _, result = self.run_check(value)
        self.assertEqual(self.statuses(result)["I2-f1"], "missing")

    def test_annotation_file_status_and_dangling_refs(self):
        refs = self.write("refs.json", {"facts": [{"factId": "I1-f1", "status": "partial", "retellRefs": [1]},
                                                  {"factId": "I9-f1", "status": "retold", "retellRefs": [7]}]})
        _, result = self.run_check(retell(), "--factrefs", refs)
        self.assertEqual(self.statuses(result), {"I1-f1": "partial", "I2-f1": "missing"})
        self.assertTrue(any("I9-f1" in n for n in result["notes"]))
        self.assertTrue(any("[7]" in n for n in result["notes"]))

    def test_closing_event_is_heuristic(self):
        _, result = self.run_check(retell())
        self.assertEqual(result["closingEvent"]["status"], "retold")
        self.assertEqual(result["closingEvent"]["signalQuality"], "low")

    def test_target_kind_reading_scope_and_prompt_version_are_noted(self):
        value = retell(target={"kind": "outline"}, readingScope=["episode_text", "episode_plan_events"])
        del value["promptVersion"]
        code, result = self.run_check(value)
        self.assertEqual(code, 0)
        self.assertEqual(len([n for n in result["notes"] if "target.kind" in n or "readingScope" in n or "promptVersion" in n]), 3)

    def test_dialogue_plan_needs_episode_plan_and_limits_facts(self):
        dplan = self.write("dp.json", {"schema": "dialogue-plan/v0-pilot", "infoLedger": [{"factId": "I2-f1"}], "scenes": []})
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "retell_check.py"), str(self.write("r.json", retell())),
                              "--plan", str(dplan)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "retell_check.py"), str(self.write("r.json", retell())),
                              "--plan", str(dplan), "--episode-plan", str(self.plan)], capture_output=True, text=True)
        self.assertEqual([f["factId"] for f in json.loads(run.stdout)["facts"]], ["I2-f1"])

    def test_top_level_fact_refs_like_the_schema(self):
        value = retell(factRefs=[{"factId": "I2-f1", "status": "retold", "retellRefs": [2]}])
        _, result = self.run_check(value)
        self.assertEqual(self.statuses(result), {"I1-f1": "missing", "I2-f1": "retold"})
        self.assertEqual(result["basis"], "factRefs")


if __name__ == "__main__":
    unittest.main()
