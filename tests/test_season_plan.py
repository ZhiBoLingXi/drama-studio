"""season-plan check: S rules on a synthetic three-episode season with one split and one move."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/checks/season_plan_check.py")]


def cap(info, pics, status="fits", **extra):
    out = {"infoCount": info, "pictureBeats": pics, "estimateSec": round(info * 10 + pics * 2, 1), "targetSec": 60, "status": status}
    out.update(extra)
    return out


def item(iid, carrier="d", status="kept", **extra):
    out = {"id": iid, "carrier": carrier, "fact": f"事实{iid}", "status": status}
    out.update(extra)
    return out


def season():
    return {
        "episodes": [
            {"episode": 1, "role": "original", "functions": ["F-box-1"], "capacity": cap(7, 0, "exceeds", action="rearrange", actionDetail="1.7 挪到第 3 集"),
             "infoItemsRough": [item(f"1.{i}") for i in range(1, 7)] + [item("1.7", status="moved_out", to="3")]},
            {"episode": 2, "role": "original", "functions": ["F-box-2"], "capacity": cap(8, 1, "exceeds", action="split", actionDetail="拆成 2A、2B"),
             "infoItemsRough": [item(f"2.{i}", goesTo="2A" if i < 5 else "2B") for i in range(1, 9)]},
            {"episode": "2A", "role": "split_child", "splitFrom": 2, "functions": [], "capacity": cap(4, 1), "infoItemsRough": [item(f"2.{i}") for i in range(1, 5)]},
            {"episode": "2B", "role": "split_child", "splitFrom": 2, "functions": [], "capacity": cap(4, 0), "infoItemsRough": [item(f"2.{i}", "p" if i == 8 else "d") for i in range(5, 9)]},
            {"episode": 3, "role": "original", "functions": [], "capacity": cap(3, 0), "infoItemsRough": [item("3.1"), item("3.2"), item("1.7", status="moved_in", **{"from": "1"})]},
        ],
        "finalSequence": [
            {"id": "1", "newEpisodeNo": 1, "infoCount": 6, "pictureBeats": 0, "estimateSec": 60.0, "estimateSecBasisB": 60.0},
            {"id": "2A", "newEpisodeNo": 2, "infoCount": 4, "pictureBeats": 1, "estimateSec": 42.0, "estimateSecBasisB": 42.0},
            {"id": "2B", "newEpisodeNo": 3, "infoCount": 4, "pictureBeats": 0, "estimateSec": 40.0, "estimateSecBasisB": 32.0},
            {"id": "3", "newEpisodeNo": 4, "infoCount": 3, "pictureBeats": 0, "estimateSec": 30.0, "estimateSecBasisB": 30.0},
        ],
        "threads": [{"plantId": "P-1", "plantedAt": "1", "payAt": "3"}],
        "decisions": ["DQ-S1"],
        "pending": [{"decisionId": "DQ-S1", "defaultUsed": "split"}],
    }


FMAP = {"threads": [{"threadId": "T", "functions": [{"functionId": "F-box-1", "status": "selected"}, {"functionId": "F-box-2", "status": "selected"},
                                                     {"functionId": "F-box-3", "status": "selected", "outOfScope": "第 20 集以后"}]}]}
DECISIONS = {"entries": [{"id": "DQ-S1", "default": "split", "options": [{"optionId": "split", "losesFunctions": []},
                                                                          {"optionId": "drop", "losesFunctions": [{"functionId": "F-box-2"}]}]},
                         {"id": "DQ-S2", "default": "drop", "status": "decided", "humanWords": "这条线不要了",
                          "options": [{"optionId": "drop", "losesFunctions": [{"functionId": "F-box-2"}]}]}]}
MEDIA = {"formatDefault": {"live": {"targetSecondsDefault": 60, "speechRateCharsPerMin": 300, "pauseShare": 0.3, "speechCharsPerEpisodeMin": 200}}}


class SeasonPlanCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        path = self.dir / name
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def run_check(self, doc, decisions=DECISIONS, extra=("--exchange-median-sec", "10")):
        args = [self.write("season.json", doc), "--function-map", self.write("fm.json", FMAP), "--media", self.write("media.json", MEDIA), *extra]
        if decisions is not None:
            args += ["--decisions", self.write("dq.json", decisions)]
        result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def rule(self, doc, name, **kw):
        return self.run_check(doc, **kw)[1]["rules"][name]

    def test_clean_season_passes(self):
        code, out = self.run_check(season())
        self.assertEqual(code, 0, json.dumps(out, ensure_ascii=False, indent=1))
        self.assertIn("reproduceCommand", out)

    def test_capacity_fields(self):
        doc = season()
        del doc["episodes"][4]["capacity"]["targetSec"]
        self.assertEqual(self.rule(doc, "capacity-fields")["status"], "fail")

    def test_exceeds_needs_action_and_no_pending_word(self):
        doc = season()
        doc["episodes"][0]["capacity"].update(action=None, actionDetail="")
        self.assertEqual(len(self.rule(doc, "action-when-exceeds")["items"]), 2)
        doc = season()
        doc["episodes"][0]["capacity"]["actionDetail"] = "待定，等主创"
        self.assertIn("待定", self.rule(doc, "action-when-exceeds")["items"][0])

    def test_drop_is_never_a_system_default(self):
        doc = season()
        doc["episodes"][4]["capacity"] = cap(3, 0, "exceeds", action="drop_function", actionDetail="删 F-box-2")
        self.assertEqual(self.rule(doc, "drop-not-default")["status"], "fail")
        doc["episodes"][4]["capacity"]["decisionRef"] = "DQ-S2"
        self.assertEqual(self.rule(doc, "drop-not-default")["status"], "pass")
        decisions = copy.deepcopy(DECISIONS)
        decisions["entries"][0]["default"] = "drop"
        self.assertIn("DQ-S1", self.rule(season(), "drop-not-default", decisions=decisions)["items"][0])

    def test_threads_need_pay(self):
        doc = season()
        doc["threads"][0]["payAt"] = None
        self.assertEqual(self.rule(doc, "threads-pay")["status"], "fail")

    def test_functions_covered(self):
        doc = season()
        doc["episodes"][1]["functions"] = []
        self.assertIn("F-box-2", self.rule(doc, "functions-covered")["items"][0])

    def test_splits(self):
        doc = season()
        del doc["episodes"][3]
        doc["finalSequence"] = [f for f in doc["finalSequence"] if f["id"] != "2B"]
        self.assertEqual(self.rule(doc, "splits")["status"], "fail")
        doc = season()
        doc["episodes"][1]["capacity"]["action"] = "rearrange"
        self.assertEqual(self.rule(doc, "splits")["status"], "fail")

    def test_final_sequence_recomputed_both_bases(self):
        doc = season()
        doc["finalSequence"][1]["estimateSec"] = 50
        self.assertEqual(self.rule(doc, "final-sequence")["status"], "fail")
        doc = season()
        doc["finalSequence"][2]["estimateSecBasisB"] = 40.0  # 2B: 3 dialogue facts, 1 picture fact -> 32
        self.assertIn("estimateSecBasisB", self.rule(doc, "final-sequence")["items"][0])
        r = self.run_check(season(), extra=())[1]["rules"]["final-sequence"]
        self.assertEqual(r["status"], "report")  # no corpus, no median: not recomputed, said so

    def test_moves_reciprocal(self):
        doc = season()
        doc["episodes"][4]["infoItemsRough"].pop()
        self.assertIn("找不到", self.rule(doc, "moves-reciprocal")["items"][0])

    def test_decision_refs(self):
        doc = season()
        doc["pending"].append({"decisionId": "DQ-404", "defaultUsed": "x"})
        self.assertEqual(self.rule(doc, "decision-refs")["status"], "fail")
        self.assertEqual(self.rule(season(), "decision-refs", decisions=None)["status"], "report")

    def test_duplicate_episode_and_bad_input(self):
        doc = season()
        doc["episodes"].append(copy.deepcopy(doc["episodes"][4]))
        code, out = self.run_check(doc)
        self.assertEqual((code, out["rules"]["episode-ids-unique"]["status"]), (2, "fail"))
        code, out = self.run_check({"episodes": []})
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
