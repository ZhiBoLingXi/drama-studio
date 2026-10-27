import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts"


def fact(fid, beat, ledger=None):
    value = {"factId": fid, "text": "x", "carrierBeat": beat, "keywords": ["x"]}
    if ledger:
        value["ledgerRef"] = ledger
    return value


EPISODE_PLAN = {
    "episode": "9",
    "infoLedger": [
        {"infoId": "I1", "facts": [fact("I1-f1", "9-1.b1", ["L-kn-001"])]},
        {"infoId": "I2", "knownByInStory": ["王姨"], "facts": [fact("I2-f1", "9-2.b1")]},
        {"infoId": "I3", "knownByInStoryRefs": [{"who": "老陈", "ledgerRef": "L-kn-999"}, {"who": "王姨", "ledgerRef": "L-kn-999"}],
         "facts": [fact("I3-f1", "9-1.b2")]},
        {"infoId": "I4", "knownByInStoryRefs": [{"who": "老陈", "ledgerRef": "L-kn-002"}], "facts": [fact("I4-f1", "9-1.b3")]},
        {"infoId": "I5", "facts": [fact("I5-f1", "9-1.b9", "L-kn-005")]},
        {"infoId": "I6", "facts": [fact("I6-f1", "9-1.b9", "L-kn-006")]},
        {"infoId": "I7", "facts": [fact("I7-f1", "9-2.b1", "L-kn-007")]},
        {"infoId": "I8", "facts": [fact("I8-f1", "9-1.b9", "L-kn-008")]},
        {"infoId": "I9", "facts": [fact("I9-f1", "9-1.b5", "L-kn-009")]},
        {"infoId": "I10", "facts": [fact("I10-f1", "9-1.b2", "L-kn-009")]},
    ],
    "ledgerDelta": {"writes": [
        {"entryId": "new", "change": {"id": "L-kn-005", "who": "老陈", "since": "ep9 9-1.b9", "how": "在场（自己做的）"}},
        {"entryId": "new", "change": {"id": "L-kn-006", "who": "王姨", "since": "ep9 9-1.b9", "how": "在场（自己做的）"}},
        {"entryId": "new", "change": {"id": "L-kn-007", "who": "老陈", "since": "ep009 9-2.b1", "how": "在场（自己做的）"}},
        {"entryId": "new", "change": {"id": "L-kn-008", "who": "老陈", "since": "ep9 9-1.b9", "how": "被告知"}},
    ]},
}

KNOWS = {"scenes": [
    {"sceneId": "9-1", "byPerson": {
        "老陈": {"knows": [{"entryId": "L-kn-001", "text": "箱子在仓库"}], "notKnows": []},
        "王姨": {"knows": [{"entryId": "L-obj-001", "text": "柜子在后屋"}], "notKnows": ["钱在抽屉里"]}},
     "withinScene": [{"beatId": "9-1.b3", "newlyKnown": [{"entryId": "L-kn-009", "who": "王姨"}]}]},
    {"sceneId": "9-2", "byPerson": {"王姨": {"knows": [], "notKnows": ["钱在抽屉里"]}}},
]}


def good_plan():
    ledger = [{"infoId": "I1", "factId": "I1-f1", "carriedBy": {"exchangeIds": ["E1"], "note": "老陈说出"}}]
    ledger += [{"infoId": f"I{i}", "factId": f"I{i}-f1", "carriedBy": {"pictureReason": "画面交代"}} for i in range(2, 11)]
    return {"episode": "9", "infoLedger": ledger, "changeProposals": [], "scenes": [{
        "sceneId": "9-1", "participants": ["老陈", "王姨"], "topics": [{
            "topicId": "T1",
            "situation": {"speakerWants": "x", "listener": "王姨",
                          "listenerKnows": {"initial": {"knows": ["L-obj-001（visibleTo）"]}, "narrowedOut": []}},
            "segments": [{"segmentId": "T1-s1", "between": ["老陈", "王姨"], "closer": "老陈说完"}],
            "exchanges": [
                {"exchangeId": "E1", "segmentId": "T1-s1", "speaker": "老陈", "addressee": "王姨", "carries": ["I1-f1"]},
                {"exchangeId": "E2", "segmentId": "T1-s1", "speaker": "王姨", "addressee": "老陈", "carries": []}],
            "exemplars": {"positives": [{"source": "human", "lines": ["示例句"]}]}}]}]}


class DialoguePlanCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.episode = self.write("ep.json", EPISODE_PLAN)
        self.knows = self.write("knows.json", KNOWS)

    def write(self, name, value):
        path = self.dir / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def run_check(self, plan):
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "dialogue_plan_check.py"), str(self.write("dp.json", plan)),
                              "--episode-plan", str(self.episode), "--knows", str(self.knows)], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def rule(self, plan, name):
        return self.run_check(plan)[1]["rules"][name]

    def with_carries(self, index, facts):
        plan = good_plan()
        plan["scenes"][0]["topics"][0]["exchanges"][index]["carries"] = facts
        return plan

    def test_good_plan_passes(self):
        code, result = self.run_check(good_plan())
        self.assertEqual((code, result["passed"]), (0, True), result["rules"])
        self.assertIn("dialogue_plan_check.py", result["reproduceCommand"])

    def test_info_ledger(self):
        for mutate in (lambda p: p["infoLedger"][0].update(factId="I1-f-nope"),
                       lambda p: p["infoLedger"].pop(1),
                       lambda p: p["infoLedger"][1].update(carriedBy={}),
                       lambda p: p["infoLedger"][0]["carriedBy"].update(exchangeIds=["E1", "E-nope"]),
                       lambda p: p["infoLedger"][0].update(carriedBy={"exchangeId": "E1"})):
            plan = good_plan()
            mutate(plan)
            self.assertEqual(self.rule(plan, "info-ledger")["status"], "fail")

    def test_between_is_a_speaker_pair_not_a_range(self):
        topic = lambda p: p["scenes"][0]["topics"][0]  # noqa: E731
        plan = good_plan()
        topic(plan)["segments"].append({"segmentId": "T1-s2", "between": ["王姨", "老陈"], "closer": "王姨回应"})
        topic(plan)["exchanges"].append({"exchangeId": "E3", "segmentId": "T1-s2", "speaker": "王姨", "addressee": "老陈"})
        self.assertEqual(self.rule(plan, "topics-segments")["status"], "pass")
        interleaved = copy.deepcopy(plan)
        topic(interleaved)["exchanges"].insert(1, topic(interleaved)["exchanges"].pop())
        self.assertEqual(self.rule(interleaved, "topics-segments")["status"], "fail")
        for segment_change in ({"between": ["老陈", "老陈"]}, {"closer": ""}, {"between": "老陈到王姨"}):
            bad = good_plan()
            topic(bad)["segments"][0].update(segment_change)
            self.assertEqual(self.rule(bad, "topics-segments")["status"], "fail", segment_change)
        offstage = good_plan()
        topic(offstage)["segments"][0]["between"] = ["老陈", "电话那头"]
        result = self.rule(offstage, "topics-segments")
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["notes"])
        dangling = good_plan()
        topic(dangling)["exchanges"][0]["segmentId"] = "T1-nope"
        self.assertEqual(self.rule(dangling, "topics-segments")["status"], "fail")

    def test_speaker_knows_by_ledger_id(self):
        self.assertEqual(self.rule(self.with_carries(1, ["I3-f1"]), "speaker-knows")["status"], "fail")
        self.assertEqual(self.rule(self.with_carries(0, ["I1-f1", "I3-f1"]), "speaker-knows")["status"], "fail")
        result = self.rule(self.with_carries(1, ["I2-f1"]), "speaker-knows")
        self.assertEqual((result["status"], result["notEvaluable"][0]["factId"]), ("pass", "I2-f1"))
        result = self.rule(self.with_carries(1, ["I4-f1"]), "speaker-knows")
        self.assertEqual((result["status"], len(result["notEvaluable"])), ("pass", 1))
        self.assertEqual(self.rule(self.with_carries(0, ["I4-f1"]), "speaker-knows")["status"], "fail")

    def test_told_earlier_in_scene(self):
        plan = good_plan()
        plan["scenes"][0]["topics"][0]["exchanges"][0]["carries"] = ["I3-f1"]
        plan["scenes"][0]["topics"][0]["exchanges"][1]["carries"] = ["I3-f1"]
        items = self.rule(plan, "speaker-knows")["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("'老陈'", items[0])

    def test_self_actor_write_in_same_scene(self):
        result = self.rule(self.with_carries(0, ["I5-f1"]), "speaker-knows")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["selfActorExemptions"][0]["basis"], "same_scene_actor")
        for fid in ("I6-f1", "I7-f1", "I8-f1"):
            self.assertEqual(self.rule(self.with_carries(0, [fid]), "speaker-knows")["status"], "fail", fid)

    def test_within_scene_by_beat(self):
        result = self.rule(self.with_carries(1, ["I9-f1"]), "speaker-knows")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["withinSceneExemptions"][0]["basis"], "within_scene_beat")
        self.assertEqual(self.rule(self.with_carries(1, ["I10-f1"]), "speaker-knows")["status"], "fail")

    def test_listener_knows_is_report_only(self):
        plan = good_plan()
        plan["scenes"][0]["topics"][0]["situation"]["listenerKnows"]["initial"]["knows"].append("L-kn-001")
        code, result = self.run_check(plan)
        self.assertEqual(code, 0)
        self.assertTrue(any("L-kn-001" in i for i in result["rules"]["listener-knows"]["items"]))
        plan = good_plan()
        plan["scenes"][0]["topics"][0]["situation"]["listenerKnows"] = "王姨知道钱在抽屉里"
        result = self.rule(plan, "listener-knows")
        self.assertTrue(result["textHeuristicFallback"])
        plan["scenes"][0]["topics"][0]["situation"]["listenerKnows"] = "王姨不知道钱在抽屉里"
        self.assertEqual(self.rule(plan, "listener-knows")["items"], [])

    def test_addressee(self):
        plan = good_plan()
        plan["scenes"][0]["topics"][0]["exchanges"][0]["addressee"] = None
        self.assertEqual(self.rule(plan, "addressee")["status"], "fail")
        plan["scenes"][0]["topics"][0]["exchanges"][0]["whyNoAddressee"] = "自言自语"
        self.assertEqual(self.rule(plan, "addressee")["status"], "pass")
        plan["scenes"][0]["monologues"] = [{"who": "老陈"}]
        self.assertEqual(self.rule(plan, "addressee")["status"], "fail")

    def test_exemplars(self):
        cases = [({"positives": []}, "fail"), ({"positives": [], "no_exemplar": True}, "pass"),
                 ({"positives": [{"source": "corpus", "maskedLines": ["［甲］：一句。"]}]}, "pass"),
                 ({"positives": [{"source": "corpus", "maskedLines": ["［甲］：一句。两句。", "［乙］：三句。"]}]}, "fail"),
                 ({"positives": [{"source": "corpus"}]}, "fail"),
                 ({"positives": [{"source": "fanfiction"}]}, "fail")]
        for exemplars, expected in cases:
            plan = good_plan()
            plan["scenes"][0]["topics"][0]["exemplars"] = exemplars
            self.assertEqual(self.rule(plan, "exemplars")["status"], expected, exemplars)

    def test_no_estimates_or_quota_fields(self):
        for mutate in (lambda p: p.update(estimates={"seconds": 90}),
                       lambda p: p["scenes"][0]["topics"][0].update(turnCount=3)):
            plan = good_plan()
            mutate(plan)
            self.assertEqual(self.run_check(plan)[0], 2)
        plan = good_plan()
        plan["scenes"][0]["topics"][0]["shape"] = {"turns": "一来一回"}
        self.assertEqual(self.rule(plan, "no-quota-fields")["status"], "pass")

    def test_change_proposals_need_default(self):
        plan = good_plan()
        plan["changeProposals"] = [{"targetLayer": "C4"}]
        self.assertEqual(self.rule(plan, "change-proposals")["status"], "fail")
        plan["changeProposals"][0]["default"] = "按已知写，登记进决定队列"
        self.assertEqual(self.rule(plan, "change-proposals")["status"], "pass")


if __name__ == "__main__":
    unittest.main()
