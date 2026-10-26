"""plan-check: episode-plan S rules on a synthetic small-town episode (老陈 looks for a box)."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/plan_check.py")]


def entry(eid, kind, **fields):
    base = {"id": eid, "kind": kind, "title": eid, "origin": "designed", "status": "asserted", "introducedAt": "pre",
            "realityRef": [], "inquiryRef": [], "dependents": [], "patchCount": 0, "history": []}
    base.update(fields)
    return base


LEDGER = [
    entry("L-tl-001", "timeline", when="第3天上午", who="老陈", where="镇仓库", did="去仓库问箱子", didNot=None, why="找箱子", knownTo=["老陈"]),
    entry("L-obj-001", "object", object="木箱", holder="王姨", location="王姨家阁楼", howItGotThere="签收", state="封着", visibleTo=["王姨"]),
    entry("L-kn-001", "knowledge", who="王姨", knows="箱子在阁楼", since="pre", how="自己签收", notKnows=[]),
    entry("L-proc-001", "procedure", name="拒收退回", realWorldRule="退回寄件人", nextNecessaryMove=None, realityRef=[], usedIn=["F-box-1"]),
]


def knowledge(eid, who, knows, since, how):
    return entry(eid, "knowledge", introducedAt="ep3", who=who, knows=knows, since=since, how=how, notKnows=[])


def plan():
    return {
        "episode": 3, "title": "仓库",
        "entry": {"ledgerRev": "ep002.planned", "summary": "老陈到镇上，王姨在家"},
        "functions": [{"functionId": "F-box-1", "progress": "老陈第一次听说箱子被签收"}],
        "events": {"scenes": [
            {"sceneId": "3-1", "time": "第3天上午", "place": "镇仓库", "present": ["老陈", "仓管"], "beats": [
                {"beatId": "3-1.b1", "who": "仓管", "text": "仓管翻登记簿", "saysFact": "3-I1-f1"},
                {"beatId": "3-1.b2", "who": "老陈", "text": "老陈重复一遍：签收人是王姨", "saysFact": "3-I1-f1"}]},
            {"sceneId": "3-2", "time": "第3天中午", "place": "王姨家", "present": ["老陈", "王姨"], "beats": [
                {"beatId": "3-2.b1", "who": "老陈", "text": "老陈问王姨箱子", "saysFact": "3-I1-f1"},
                {"beatId": "3-2.b2", "who": "王姨", "text": "王姨不答", "picture": True}]}]},
        "moves": [{"who": "老陈", "did": "去仓库", "wants": "找箱子", "easierOption": "打电话", "whyNot": "没电话", "cost": "半天"}],
        "infoLedger": [{"infoId": "3-I1", "whyAudienceNeeds": "F-box-1", "laterDependents": ["4"], "knownByInStory": ["仓管", "老陈"],
                        "knownByInStoryRefs": [{"who": "仓管", "ledgerRef": "L-kn-3a"}, {"who": "老陈", "ledgerRef": "L-kn-3b"}],
                        "facts": [{"factId": "3-I1-f1", "text": "箱子三年前被王姨签收", "carrierBeat": "3-1.b1",
                                   "keywords": ["签收", "王姨"], "ledgerRef": ["L-kn-3b"]}]}],
        "ledgerDelta": {"episode": 3, "track": "planned", "reads": ["L-obj-001"], "writes": [
            {"entryId": "new", "change": knowledge("L-kn-3a", "仓管", "签收人是王姨", "pre", "自己经手"), "reason": "仓管经手", "supportedBy": "3-1.b1"},
            {"entryId": "new", "change": knowledge("L-kn-3b", "老陈", "签收人是王姨", "ep3 3-1.b1", "仓管告诉"), "reason": "被告知", "supportedBy": "3-1.b1"}]},
        "realityRefs": ["L-proc-001"],
        "threads": {"pays": ["P-1"], "plants": [{"plantId": "P-2", "what": "阁楼", "payAtEpisode": "4"}]},
        "exit": {"ledgerRev": "ep003.planned", "summary": "老陈知道了", "closingEvent": {"beatRef": "3-2.b2"}},
        "capacity": {"infoCount": 1, "sceneCount": 2, "pictureBeats": 1, "estimateSec": 12.8, "targetSec": 120, "basis": "合成", "status": "fits"},
        "pending": [{"decisionId": "DQ-1", "defaultUsed": "keep"}],
        "summary": {"hook": "老陈问王姨箱子"},
    }


SEASON = {"episodes": [{"episode": 3, "functions": ["F-box-1"]}, {"episode": "4A", "functions": []}],
          "finalSequence": [{"id": "2", "newEpisodeNo": 2}, {"id": "3", "newEpisodeNo": 3}, {"id": "4A", "newEpisodeNo": 4}],
          "threads": [{"plantId": "P-1", "plantedAt": "2", "payAt": "3"}, {"plantId": "P-2", "plantedAt": "3", "payAt": "4A"}]}
FMAP = {"threads": [{"threadId": "T-box", "functions": [{"functionId": "F-box-1"}]}]}
DECISIONS = {"entries": [{"id": "DQ-1", "default": "keep"}, {"id": "DQ-2", "default": None}]}


class PlanCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        path = self.dir / name
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def run_check(self, the_plan, ledger=None, season=SEASON, extra=()):
        args = [self.write("plan.json", the_plan), "--ledger", self.write("ledger.json", {"entries": ledger or LEDGER})]
        if season is not None:
            args += ["--season", self.write("season.json", season)]
        args += ["--function-map", self.write("fm.json", FMAP), "--decisions", self.write("dq.json", DECISIONS), *extra]
        result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def status(self, the_plan, name, **kw):
        return self.run_check(the_plan, **kw)[1]["rules"][name]

    def test_clean_plan_passes(self):
        code, out = self.run_check(plan())
        self.assertEqual(code, 0, json.dumps(out, ensure_ascii=False, indent=1))
        self.assertTrue(out["passed"])
        self.assertIn("reproduceCommand", out)

    def test_required_fields(self):
        p = plan()
        del p["moves"]
        self.assertEqual(self.status(p, "required-fields")["status"], "fail")

    def test_episode_and_functions_assigned_by_season(self):
        p = plan()
        p["functions"] = [{"functionId": "F-box-9"}]
        r = self.status(p, "functions-assigned")
        self.assertEqual(r["status"], "fail")
        self.assertEqual(len(r["items"]), 2)
        p = plan()
        p["episode"] = 5
        self.assertEqual(self.status(p, "episode-matches-season")["status"], "fail")

    def test_events_well_formed(self):
        p = plan()
        del p["events"]["scenes"][0]["place"]
        p["events"]["scenes"][1]["beats"][0]["beatId"] = "3-1.b1"
        items = self.status(p, "events-well-formed")["items"]
        self.assertTrue(any("place" in i for i in items) and any("重复" in i for i in items), items)

    def test_closing_event_must_be_last_beat(self):
        p = plan()
        p["exit"]["closingEvent"]["beatRef"] = "3-2.b1"
        self.assertEqual(self.status(p, "closing-event")["status"], "fail")

    def test_info_ledger_carrier_beat_and_keywords(self):
        p = plan()
        p["infoLedger"][0]["facts"][0].update(carrierBeat="9-9.b9", keywords=[])
        items = self.status(p, "info-ledger")["items"]
        self.assertEqual(len(items), 2, items)

    def test_ledger_delta_supported_by_and_applies(self):
        p = plan()
        p["ledgerDelta"]["writes"][0]["supportedBy"] = "场3-1"
        p["ledgerDelta"]["writes"].append({"entryId": "L-nope", "change": {"state": "x"}, "reason": "r", "supportedBy": "3-1"})
        items = self.status(p, "ledger-delta")["items"]
        self.assertTrue(any("场3-1" in i for i in items) and any("L-nope" in i for i in items), items)

    def test_presence_vs_timeline_is_report_only(self):
        ledger = copy.deepcopy(LEDGER)
        ledger[0]["where"] = "王姨家"
        code, out = self.run_check(plan(), ledger=ledger)
        r = out["rules"]["presence-vs-timeline"]
        self.assertEqual((r["status"], len(r["items"]), code), ("report", 1, 0))

    def test_speaker_knows_told_earlier_and_prior_scene(self):
        out = self.status(plan(), "speaker-knows")
        self.assertEqual(out["status"], "pass", out)
        bases = {(e["beat"], e["basis"]) for e in out["exemptions"]}
        self.assertIn(("3-1.b2", "told_earlier_in_scene"), bases)
        self.assertNotIn("3-2.b1", [e["beat"] for e in out["exemptions"]])  # known before scene 3-2: no exemption needed

    def test_speaker_knows_fails_when_ledger_times_it_later(self):
        p = plan()
        p["events"]["scenes"][0]["beats"][1]["saysFact"] = None
        p["ledgerDelta"]["writes"][1]["change"]["since"] = "ep3 3-2.b2"
        p["ledgerDelta"]["writes"][1]["supportedBy"] = "3-2.b2"
        out = self.status(p, "speaker-knows")
        self.assertEqual(out["status"], "fail")
        self.assertIn("3-2.b1", out["items"][0])

    def test_speaker_knows_self_actor_by_beat(self):
        p = plan()
        p["events"]["scenes"][0]["beats"] = [{"beatId": "3-1.b1", "who": "老陈", "text": "老陈自己翻到签收联", "saysFact": "3-I1-f1"}]
        p["infoLedger"][0]["facts"][0]["carrierBeat"] = "3-1.b1"
        p["ledgerDelta"]["writes"][1]["change"].update(since="ep3 3-1.b1", how="自己做的")
        out = self.status(p, "speaker-knows")
        self.assertEqual(out["status"], "pass", out)
        self.assertEqual(out["exemptions"][0]["basis"], "same_scene_actor")
        p["ledgerDelta"]["writes"][1]["change"].update(since="ep3 3-1.b2")
        self.assertEqual(self.status(p, "speaker-knows")["status"], "fail")

    def test_speaker_knows_before_marker(self):
        p = plan()
        p["events"]["scenes"][0]["beats"] = [{"beatId": "3-1.b1", "who": "老陈", "text": "老陈说出签收人", "saysFact": "3-I1-f1"}]
        p["ledgerDelta"]["writes"][1]["change"].update(since="ep3 3-1.b1 之前", how="材料未写")
        out = self.status(p, "speaker-knows")
        self.assertEqual((out["status"], out["exemptions"][0]["basis"]), ("pass", "within_scene_beat"))

    def test_speaker_knows_matches_ids_not_names(self):
        p = plan()
        # 仓管 is named in knownByInStory, but has no ledger id of his own and fact.ledgerRef is 老陈's entry
        p["infoLedger"][0]["knownByInStoryRefs"] = [{"who": "仓管", "ledgerRef": None}, {"who": "老陈", "ledgerRef": "L-kn-3b"}]
        out = self.status(p, "speaker-knows")
        # D6-2 decision §5 #25 changed this on purpose: it was "pass"; a pass with unjudged lines now says so
        self.assertEqual(out["status"], "pass_with_not_evaluable", out)
        self.assertEqual([(x["beat"], x["speaker"]) for x in out["notEvaluable"]], [("3-1.b1", "仓管")])

    def test_reality_refs_contested(self):
        ledger = copy.deepcopy(LEDGER)
        ledger[3]["status"] = "contested"
        r = self.status(plan(), "reality-refs", ledger=ledger)
        self.assertEqual((r["status"], r["items"]["contestedIds"]), ("fail", ["L-proc-001"]))
        ledger[3]["status"] = "unverified"
        r = self.status(plan(), "reality-refs", ledger=ledger)
        self.assertEqual((r["status"], r["items"]["unverifiedCount"]), ("pass", 1))

    def test_threads_order_by_final_sequence_with_letter_ids(self):
        p = plan()
        p["episode"] = "4A"
        p["functions"] = []
        p["threads"] = {"pays": ["P-2"], "plants": []}
        self.assertEqual(self.status(p, "threads")["status"], "pass")
        season = copy.deepcopy(SEASON)
        season["threads"][1]["plantedAt"] = "4A"
        p["threads"] = {"pays": ["P-2"], "plants": []}
        r = self.status(p, "threads", season=season)
        self.assertEqual(r["status"], "fail", r)
        season["threads"][1]["plantedAt"] = "out_of_scope"
        self.assertEqual(self.status(p, "threads", season=season)["status"], "report")

    def test_capacity_proposal_needs_default(self):
        p = plan()
        p["capacity"]["status"] = "proposal:DQ-2"
        self.assertEqual(self.status(p, "capacity")["status"], "fail")
        p["capacity"]["status"] = "proposal:DQ-1"
        self.assertEqual(self.status(p, "capacity")["status"], "pass")

    def test_pending_needs_existing_decision_and_default_used(self):
        p = plan()
        p["pending"] = [{"decisionId": "DQ-404", "defaultUsed": ""}]
        self.assertEqual(len(self.status(p, "pending")["items"]), 2)

    def test_summary_is_report_only(self):
        p = plan()
        p["summary"]["hook"] = "一句 events 里没有的话"
        code, out = self.run_check(p)
        self.assertEqual((code, out["rules"]["summary"]["status"]), (0, "report"))

    def test_bad_input_exit_1(self):
        result = subprocess.run(TOOL + [str(self.dir / "none.json"), "--ledger", str(self.dir / "none.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
