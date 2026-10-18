"""Tool fixes from the second literal recheck (wording rulings #1, #2, #3, #11, #15).

#1 feedback-ingest: only the user's words become a decided entry; a writer's or advisor's are pending with a default.
#2 constraint blocklist v4: numeric_dialogue counts 字／行／句／来回 only, so production limits on people pass.
#3 episode-check: max_scenes, a per-episode cap on scene headings.
#11 context-pack: a C5a package with labelled exchanges and no dialogue plan packs their annotation fields only.
#15 dialogue-plan-check: a fact deferredTo a capacity proposal needs no carriage, but the proposal must exist with a default.
Fabricated fixtures only; one passing and one failing case per S rule.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/drama-studio/scripts"
TOOL = SCRIPTS / "drama_tools.py"
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))
from checks import contract_check as contracts  # noqa: E402
import test_context_pack_d6 as packs  # noqa: E402
import test_dialogue_plan_check as plan_checks  # noqa: E402


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    text = proc.stdout if proc.stdout.lstrip().startswith("{") else proc.stderr
    return proc.returncode, json.loads(text) if text.strip() else {}


class Temp(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)

    def write(self, name, doc):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path


class OnlyTheUserDecides(Temp):  # 1
    NOTES = "# 批注（编造）\n\n### n1\n\n> 王姨：就这么办吧。\n\n- 就这么定了，第 6 集不加夜戏。\n"

    def queue(self, *args, source=None):
        out = self.base / f"out-{len(list(self.base.iterdir()))}"
        code, result = tool("feedback-ingest", source or self.write("notes.md", self.NOTES), "--out", out, *args)
        self.assertEqual(code, 0, result)
        queue = json.loads((out / "decisions.json").read_text(encoding="utf-8"))
        self.assertEqual(contracts.check_contract("decision-queue", queue), [])
        return queue["entries"][0]

    def test_a_note_of_unknown_source_is_pending_with_a_default(self):
        entry = self.queue("--author", "编剧甲")
        self.assertEqual((entry["status"], entry["default"], entry["decision"], entry["decidedBy"]), ("pending", "as_said", None, None))
        self.assertEqual((entry["basisBy"], entry["basisRole"]), ("编剧甲", "unknown"))
        self.assertIn("就这么定了", entry["basisWords"])
        self.assertNotIn("humanWords", entry)  # humanWords are the user's words on a decided entry only
        writer = self.queue("--author", "编剧甲", "--author-role", "writer")
        self.assertEqual((writer["status"], writer["basisRole"]), ("pending", "writer"))

    def test_the_user_s_words_are_decided(self):
        entry = self.queue("--author", "主创", "--author-role", "user")
        self.assertEqual((entry["status"], entry["decision"], entry["decidedBy"]), ("decided", "as_said", "主创"))
        self.assertIn("就这么定了", entry["humanWords"])
        self.assertNotIn("basisWords", entry)
        self.assertEqual(self.queue("--author", "主创", "--user-name", "主创")["status"], "decided")
        self.assertEqual(self.queue("--author", "编剧甲", "--user-name", "主创")["status"], "pending")

    def test_a_comment_s_own_author_role_counts(self):
        comments = {"comments": [{"commentId": "a", "quote": "王姨：就这么办吧。", "text": "就这么定了", "level": "decision",
                                  "author": "顾问乙", "authorRole": "advisor"},
                                 {"commentId": "b", "quote": "老陈：走吧。", "text": "定了，不加夜戏", "level": "decision",
                                  "author": "主创", "authorRole": "user"}]}
        out = self.base / "c"
        code, result = tool("feedback-ingest", self.write("c.json", comments), "--out", out)
        statuses = [e["status"] for e in json.loads((out / "decisions.json").read_text(encoding="utf-8"))["entries"]]
        self.assertEqual(statuses, ["pending", "decided"])


class HumanWordsAreTheUsers(unittest.TestCase):  # 1, contract-check side
    def entry(self, **extra):
        return {"id": "DQ-1", "kind": "other", "question": "加夜戏吗", "options": [{"optionId": "as_said", "text": "不加"}],
                "default": "as_said", "defaultReason": "编剧意见", "affects": [], **extra}

    def test_pending_rests_on_basis_words_and_decided_needs_human_words(self):
        ok = {"entries": [self.entry(status="pending", basisWords="不加夜戏", basisBy="编剧甲", basisRole="writer"),
                          self.entry(id="DQ-2", status="decided", decision="as_said", humanWords="不加", decidedBy="主创")]}
        self.assertEqual(contracts.check_contract("decision-queue", ok), [])
        bad = {"entries": [self.entry(status="pending", humanWords="不加夜戏")]}
        self.assertTrue(any("basisWords" in e for e in contracts.check_contract("decision-queue", bad)))
        bad = {"entries": [self.entry(status="decided", decision="as_said", basisWords="不加夜戏")]}
        self.assertTrue(any("humanWords" in e for e in contracts.check_contract("decision-queue", bad)))


class ProductionLimitsPass(Temp):  # 2
    def check(self, text):
        doc = example("task")
        doc["constraints"] = [{"text": text, "origin": "user"}]
        return tool("contract-check", "task", self.write("task.json", doc))

    def test_limits_on_people_and_scenes_pass(self):
        for text in ("演员不超过 5 人", "演员不超过5人", "每场最多 2 人", "每集最多三个场景", "每集最多出场 4 人"):
            with self.subTest(text=text):
                code, out = self.check(text)
                self.assertEqual(code, 0, out)

    def test_dialogue_measures_are_still_refused(self):
        for text in ("每句不超过十个字", "这一场少40字", "每场最多 3 句", "换人数保持原样", "换人次数不超过 6", "来回不超过 4 个来回"):
            with self.subTest(text=text):
                code, out = self.check(text)
                self.assertEqual(code, 2, out)
                self.assertIn("numeric_dialogue", " ".join(out["errors"]))

    def test_the_blocklist_is_v4(self):
        data = contracts.load_data("constraint-blocklist")
        self.assertEqual(data["version"], "v4")


class SceneCap(Temp):  # 3
    TEXT = "# 第1集\n\n" + "".join(f"场1-{n} 客厅 日 内\n△ 他进门。\n甲：你好。\n乙：好。\n\n" for n in range(1, 5))

    def test_more_scenes_than_the_cap_is_unmet(self):
        path = self.write("ep.md", self.TEXT)
        code, out = tool("episode-check", path, "--max-scenes", 3)
        self.assertEqual((code, out["constraint_status"]), (2, "unmet"), out)
        self.assertEqual(out["episodes"][0]["checks"][0]["actual"], 4)
        code, out = tool("episode-check", path, "--max-scenes", 4)
        self.assertEqual((code, out["constraint_status"]), (0, "met"), out)

    def test_the_config_takes_max_scenes(self):
        config = self.write("cfg.json", {"schemaVersion": 1, "source": "制作方：每集最多三个场景", "constraints": {"max_scenes": 3}})
        code, out = tool("episode-check", self.write("ep.md", self.TEXT), "--config", config)
        self.assertEqual((code, out["constraint_status"]), (2, "unmet"), out)
        bad = self.write("bad.json", {"schemaVersion": 1, "source": "x", "constraints": {"max_scenes": 2.5}})
        self.assertEqual(tool("episode-check", self.write("ep.md", self.TEXT), "--config", bad)[0], 1)


class C5aAnnotationsOnly(unittest.TestCase):  # 11
    RAW = "这是原始台词行不该进包"

    def setUp(self):
        self.case = packs.D6PackTests("test_two_positives_and_one_pair_per_topic")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        rows = [{"exchangeId": f"EX-000{i}", "templateId": "T1", "episodeIndex": 1, "about": "问清", "situation": {"function": "问清"},
                 "walkthrough": "她先防备", "skeleton": "问 → 答", "lines": [{"speaker": "甲", "text": self.RAW}],
                 "maskedLines": ["［甲］：嗯。"], "quality": {"label": "low" if i == 3 else "ok"}} for i in range(1, 4)]
        rows.append({"exchangeId": "EX-0004", "lines": [{"speaker": "甲", "text": self.RAW}]})  # not labelled
        self.case.write("runs/corpus/labelled.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
        self.exemplars = str(self.case.project / "runs/corpus/labelled.jsonl")

    def pack(self, *extra, dry_run=True, plan=False, flag=True):
        extra = (("--annotations-only",) if flag else ()) + extra
        items = [("current_plan", "runs/plan/episode-plan-003.json")] + ([("current_plan", "runs/plan/dialogue-plan-003.json")] if plan else [])
        if dry_run:
            return self.case.pack("dialogue_designer", items, 20000, "--exemplars", self.exemplars, *extra)
        self.case.pack("dialogue_designer", items, 20000, "--exemplars", self.exemplars, *extra)  # writes task/selection
        result = subprocess.run([sys.executable, "-B", str(TOOL), "context-pack", str(self.case.project), "--task", str(self.case.base / "task.json"),
                                 "--selection", str(self.case.base / "sel.json"), "--role", "dialogue_designer", "--budget", "20000",
                                 "--exemplars", self.exemplars, *extra], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def test_labelled_exchanges_go_in_as_annotations_without_lines(self):
        code, out = self.pack()
        self.assertEqual(code, 0, out.get("error") or out.get("errors"))
        self.assertEqual(out["samples"]["mode"], "annotations_only")
        self.assertEqual([i["ref"] for i in out["items"] if i["ref"].startswith("sample")], ["sample 标注 EX-0001", "sample 标注 EX-0002"])
        self.assertEqual((out["samples"]["leftOutLowLabel"], out["samples"]["leftOutUnlabelled"]), (["EX-0003"], ["EX-0004"]))
        code, out = self.pack(dry_run=False)
        self.assertEqual(code, 0, out.get("error") or out.get("errors"))
        view = (self.case.project / out["samples"]["view"]).read_text(encoding="utf-8")
        self.assertNotIn(self.RAW, view)
        self.assertNotIn("maskedLines", view)
        self.assertEqual([sorted(json.loads(l)) for l in view.splitlines()][0],
                         ["about", "episodeIndex", "exchangeId", "situation", "skeleton", "templateId", "walkthrough"])
        snapshot = json.loads(Path(out["snapshot_path"]).read_text(encoding="utf-8"))
        sample = next(i for i in snapshot["items"] if i["partition"] == "samples")
        packed = view[sample["ref"]["range"]["start"]:sample["ref"]["range"]["end"]]
        self.assertEqual(json.loads(packed)["exchangeId"], "EX-0001")

    def test_without_the_flag_c5a_with_no_plan_is_refused_and_says_so(self):
        code, out = self.pack(flag=False)
        self.assertEqual(code, 1, out)
        self.assertIn("--annotations-only", out["error"])
        code, out = self.pack(plan=True)  # the flag with a dialogue plan in the package
        self.assertEqual(code, 1, out)
        self.assertIn("--annotations-only", out["error"])

    def test_with_a_dialogue_plan_raw_rows_are_still_refused(self):
        code, out = self.pack(plan=True, flag=False)
        self.assertEqual(code, 1, out)
        self.assertIn("原始转写", out["error"])

    def test_c5b_and_contrast_pairs_keep_the_old_rules(self):
        code, out = self.pack("--contrast-pairs", str(self.case.project / "runs/contrast-pairs.jsonl"))
        self.assertEqual(code, 1, out)
        self.assertIn("--contrast-pairs", out["error"])


class DeferredFacts(unittest.TestCase):  # 15
    _base = plan_checks.DialoguePlanCheckTests
    setUp, write, run_check, rule = _base.setUp, _base.write, _base.run_check, _base.rule

    def deferred_plan(self, target="CP-split-1", proposals=True):
        plan = plan_checks.good_plan()
        plan["infoLedger"][2] = {"infoId": "I3", "factId": "I3-f1", "deferredTo": target}
        if proposals:
            plan["changeProposals"] = [{"id": "CP-split-1", "targetLayer": "C4", "default": "按粗估比例拆两段，本段写前一半"}]
        return plan

    def test_a_deferred_fact_needs_no_carriage_when_its_proposal_has_a_default(self):
        result = self.rule(self.deferred_plan(), "info-ledger")
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["deferred"], [{"factId": "I3-f1", "deferredTo": "CP-split-1"}])
        self.assertEqual(contracts.check_contract("dialogue-plan", self.contract_plan()), [])

    def test_the_proposal_must_exist_and_have_a_default(self):
        self.assertEqual(self.rule(self.deferred_plan("CP-nope"), "info-ledger")["status"], "fail")
        plan = self.deferred_plan()
        plan["changeProposals"][0]["default"] = ""
        self.assertEqual(self.rule(plan, "info-ledger")["status"], "fail")
        plan = self.deferred_plan()
        plan["infoLedger"][2]["carriedBy"] = {"exchangeIds": ["E1"]}
        self.assertEqual(self.rule(plan, "info-ledger")["status"], "fail")

    def test_a_proposal_whose_kind_is_known_must_be_capacity(self):
        plan = self.deferred_plan()
        plan["changeProposals"][0]["kind"] = "upstream_change"
        result = self.rule(plan, "info-ledger")
        self.assertEqual(result["status"], "fail")
        self.assertIn("capacity", " ".join(result["items"]))
        plan["changeProposals"][0]["kind"] = "capacity"
        self.assertEqual(self.rule(plan, "info-ledger")["status"], "pass")

    def test_a_proposal_in_the_decision_queue_counts(self):
        plan = self.deferred_plan(proposals=False)
        self.assertEqual(self.rule(plan, "info-ledger")["status"], "fail")
        queue = self.write("dq.json", {"entries": [{"id": "CP-split-1", "kind": "capacity", "question": "拆吗", "default": "split",
                                                    "options": [{"optionId": "split", "text": "拆"}], "defaultReason": "超时",
                                                    "affects": [], "status": "pending"}]})
        run = subprocess.run([sys.executable, "-B", str(plan_checks.CHECKS / "dialogue_plan_check.py"), str(self.write("dp.json", plan)),
                              "--episode-plan", str(self.episode), "--knows", str(self.knows), "--decisions", str(queue)],
                             capture_output=True, text=True)
        self.assertEqual(json.loads(run.stdout)["rules"]["info-ledger"]["status"], "pass", run.stdout)
        queue.write_text(queue.read_text(encoding="utf-8").replace('"capacity"', '"other"'), encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(plan_checks.CHECKS / "dialogue_plan_check.py"), str(self.write("dp.json", plan)),
                              "--episode-plan", str(self.episode), "--knows", str(self.knows), "--decisions", str(queue)],
                             capture_output=True, text=True)
        self.assertEqual(json.loads(run.stdout)["rules"]["info-ledger"]["status"], "fail", run.stdout)  # a queue entry says its kind

    def contract_plan(self):
        doc = example("dialogue-plan")
        first = doc["infoLedger"][0]
        doc["infoLedger"].append({"infoId": first["infoId"], "factId": "F-deferred", "deferredTo": "CP-split-1"})
        return doc

    def test_contract_check_wants_carriage_unless_deferred(self):
        doc = example("dialogue-plan")
        doc["infoLedger"].append({"infoId": doc["infoLedger"][0]["infoId"], "factId": "F-x"})
        self.assertTrue(any("carriedBy" in e for e in contracts.check_contract("dialogue-plan", doc)))
        doc["infoLedger"][-1]["deferredTo"] = ""
        self.assertTrue(contracts.check_contract("dialogue-plan", doc))



if __name__ == "__main__":
    unittest.main()
