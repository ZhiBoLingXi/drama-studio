"""D6-3 tools: the dialogue-layer criterion, --legacy-dialogue, dialogueLayerRules, retell-after-revise on records,
the revision-list scan, numeric task constraints, and context-pack's samples partition, quote cap and pack history.

One passing and one failing case per S rule; synthetic fixtures from schemas/examples/ and the season-check fixtures.
"""
import copy
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
from checks import season_check  # noqa: E402
import test_context_pack_d6 as packs  # noqa: E402  (module import: its TestCase is not collected twice)
from test_season_check import Season, run  # noqa: E402
from test_season_check_d6 import DialogueLayer, put  # noqa: E402


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    text = proc.stdout if proc.stdout.lstrip().startswith("{") else proc.stderr
    return proc.returncode, json.loads(text)


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"

    def tearDown(self):
        self.tmp.cleanup()


class DialogueProjectCriterion(Temp):  # decisions §2
    def test_a_dialogue_plan_anywhere_under_planning_or_drama_switches_it_on(self):
        for where in ("planning/dialogue/dialogue-plan-003.json", ".drama/checks/deep/x/dp.json"):
            with self.subTest(where=where):
                self.tearDown()
                self.setUp()
                put(self.root, where, example("dialogue-plan"))
                self.assertTrue(season_check.dialogue_project(self.root))

    def test_other_places_and_other_records_do_not(self):
        put(self.root, ".drama/cache/dp.json", example("dialogue-plan"))
        put(self.root, "runs/dp.json", example("dialogue-plan"))
        put(self.root, "planning/episodes/episode-plan-003.json", example("episode-plan"))
        self.assertFalse(season_check.dialogue_project(self.root))
        self.assertFalse(season_check.dialogue_project(self.root / "missing"))


class LegacyDialogueFlag(Temp):  # decisions §2, plan §4.4
    def test_without_the_flag_the_old_three_never_appear(self):
        Season(self.root, voice=False, dialogue_read=False)
        code, out = run("season-check", self.root, "--episodes", "2-3")
        self.assertEqual((code, out["failures"]), (0, []))
        self.assertIn("--legacy-dialogue", out["legacyDialogueRules"])
        self.assertNotIn("dialogueLayerRules", out)

    def test_with_the_flag_they_run_and_the_output_has_no_new_key(self):
        Season(self.root, voice=False, dialogue_read=False)
        code, out = run("season-check", self.root, "--episodes", "2-3", "--legacy-dialogue")
        self.assertEqual({f["rule"] for f in out["failures"]}, {"voice-card", "dialogue-read"})
        self.assertNotIn("legacyDialogueRules", out)

    def test_outline_only_runs_add_no_key(self):
        Season(self.root)
        code, out = run("season-check", self.root, "--outline", "2-3")
        self.assertNotIn("legacyDialogueRules", out)


class DialogueLayerRules(Temp):
    def setUp(self):
        super().setUp()
        self.season = Season(self.root, voice=False, dialogue_read=False)
        self.layer = DialogueLayer(self.root)

    def check(self):
        self.layer.write()
        code, out = run("season-check", self.root, "--episodes", "2-3")
        return code, out

    def test_rules_are_listed_with_what_they_were_evaluated_on(self):
        code, out = self.check()
        listed = out["dialogueLayerRules"]
        self.assertEqual(sorted(listed), sorted(season_check.DIALOGUE_LAYER_RULES))
        self.assertEqual(listed["dup-two-tier"], {"status": "passed", "evaluatedOn": ["第2集", "第3集"]})
        self.assertEqual(listed["fixlist-no-lines"]["status"], "not_evaluated")  # no revision list on record
        del self.layer.records[3]["genre-ep-003.json"]
        (self.root / ".drama/checks/genre-ep-003.json").unlink()
        code, out = self.check()
        self.assertEqual(out["dialogueLayerRules"]["genre-lexicon"]["status"], "failed")

    def test_retell_after_revise_needs_a_retell_of_the_final_text(self):  # records only, no cold-read runs
        for n in (2, 3):  # the retell read the draft before the dialogue pass revised it
            self.layer.records[n][f"retell-ep-{n:03d}.json"]["target"]["file"] = f"runs/b1/ep-{n:03d}.md"
        code, out = self.check()
        self.assertEqual({f["rule"] for f in out["failures"]}, {"retell-after-revise"})
        for n in (2, 3):
            self.layer.records[n][f"retell-ep-{n:03d}.json"]["target"]["file"] = self.season.final(n)
        code, out = self.check()
        self.assertEqual(out["failures"], [])

    def test_the_layer_rules_run_without_any_run_handoff(self):
        bare = Path(self.tmp.name) / "bare"
        (bare / ".drama").mkdir(parents=True)
        (bare / ".drama/project.json").write_text("{}", encoding="utf-8")
        DialogueLayer(bare).write()
        code, out = run("season-check", bare, "--episodes", "2-3")
        listed = out["dialogueLayerRules"]
        self.assertEqual((listed["plan-text-align"]["status"], listed["retell-after-revise"]["status"]), ("passed", "not_evaluated"))
        self.assertIn("author", {f["rule"] for f in out["failures"]})

    def test_a_revision_list_whose_target_is_a_file_is_found(self):
        fixlist = {"schema": "revision-list/v0-pilot", "target": "runs/b1/ep-003.d.md",
                   "items": [{"id": "RV-1", "where": "g1:L44", "problem": "称呼不对", "action": "本轮不改：登记进决定队列"}]}
        self.layer.records[3]["revision-list-x.json"] = fixlist
        code, out = self.check()
        self.assertEqual(out["dialogueLayerRules"]["fixlist-no-lines"], {"status": "passed", "evaluatedOn": ["第3集"]})
        fixlist["items"][0]["action"] = "少40字"
        code, out = self.check()
        self.assertEqual({f["rule"] for f in out["failures"]}, {"fixlist-no-lines"})


class RevisionListContract(unittest.TestCase):  # plan §4.4: the revision-list scan
    def test_the_example_passes(self):
        self.assertEqual(contracts.check_contract("revision-list", example("revision-list")), [])

    def test_a_replacement_line_is_refused(self):
        doc = example("revision-list")
        doc["items"][0]["action"] = "改成：\n刘叔：箱子早送到王姨家了。"
        self.assertTrue(any("替换台词" in e for e in contracts.check_contract("revision-list", doc)))
        doc = example("revision-list")
        doc["items"][0]["replacement"] = "刘叔：箱子早送到王姨家了。"  # any free-text field is read
        self.assertTrue(any("替换台词" in e for e in contracts.check_contract("revision-list", doc)))

    def test_a_numeric_instruction_is_refused(self):
        for text in ("这一场少40字", "台词压到五行", "每句不超过十个字"):
            doc = example("revision-list")
            doc["items"][1]["action"] = text
            with self.subTest(text=text):
                self.assertTrue(any("数值指令" in e for e in contracts.check_contract("revision-list", doc)))

    def test_locators_and_instruction_labels_are_not_lines(self):
        doc = example("revision-list")
        doc["items"][0].update(where="g1:L44, L59", action="本轮不改：对话表已登记为有意不交代")
        doc["items"][1]["note"] = "原因：台词目标 C2"
        self.assertEqual(contracts.check_contract("revision-list", doc), [])

    def test_the_cli_exits_2_on_a_refused_list(self):
        with tempfile.TemporaryDirectory() as base:
            doc = example("revision-list")
            doc["items"][0]["action"] = "刘叔：箱子早送到了。"
            path = Path(base) / "rl.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(tool("contract-check", "revision-list", path)[0], 2)


class PlanTextMapContract(unittest.TestCase):  # the C5b map that plan-text-consistency reads
    def test_the_example_passes(self):
        self.assertEqual(contracts.check_contract("plan-text-map", example("plan-text-map")), [])

    def test_an_exchange_pointing_at_an_unmarked_line_fails(self):
        doc = example("plan-text-map")
        doc["exchangeToLines"]["X-T1-02"] = [2]
        self.assertTrue(any("not marked exchangeId X-T1-02" in e for e in contracts.check_contract("plan-text-map", doc)))

    def test_a_verbatim_line_is_listed_in_the_summary(self):
        doc = example("plan-text-map")
        doc["verbatimFrom"] = []
        self.assertTrue(any("verbatimFrom summary" in e for e in contracts.check_contract("plan-text-map", doc)))

    def test_a_line_outside_every_exchange_may_say_so(self):
        doc = example("plan-text-map")
        doc["lineToPlan"].append({"line": 4, "text": "仓管：哎——", "kind": "dialogue", "exchangeId": None})
        self.assertEqual(contracts.check_contract("plan-text-map", doc), [])


class PreservedHumanSource(Temp):  # D6-3: preserved only counts what a person asked to keep
    def test_contract_check_takes_old_strings_and_sourced_objects(self):
        doc = example("review-record")
        self.assertEqual(contracts.check_contract("review-record", doc), [])  # the example's plain string, old form
        doc["preserved"] = [{"item": "递手的动作", "noteId": "WN-003"}, {"item": "称呼", "humanWords": "这句别动"}]
        self.assertEqual(contracts.check_contract("review-record", doc), [])

    def test_contract_check_refuses_an_object_without_a_source(self):
        doc = example("review-record")
        doc["preserved"] = [{"item": "递手的动作"}]
        self.assertTrue(any("human source" in e for e in contracts.check_contract("review-record", doc)))

    def test_the_dialogue_layer_refuses_an_unsourced_preserved_item(self):
        Season(self.root)
        DialogueLayer(self.root).write()
        reviews = sorted((self.root / ".drama/reviews").glob("*.json"))
        doc = json.loads(reviews[-1].read_text(encoding="utf-8"))
        doc["preserved"] = ["递手的动作"]
        reviews[-1].write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        code, out = run("season-check", self.root, "--episodes", "2-3")
        self.assertIn("preserved-human-source", {f["rule"] for f in out["failures"]})
        self.assertEqual(out["dialogueLayerRules"]["preserved-human-source"]["status"], "failed")
        doc["preserved"] = [{"item": "递手的动作", "noteId": "WN-003"}]
        reviews[-1].write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        code, out = run("season-check", self.root, "--episodes", "2-3")
        self.assertEqual(out["dialogueLayerRules"]["preserved-human-source"]["status"], "passed")

    def test_a_legacy_project_is_not_held_to_it(self):
        Season(self.root)
        reviews = sorted((self.root / ".drama/reviews").glob("*.json"))
        doc = json.loads(reviews[-1].read_text(encoding="utf-8"))
        doc["preserved"] = ["递手的动作"]
        reviews[-1].write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        code, out = run("season-check", self.root, "--episodes", "2-3")
        self.assertEqual(out["failures"], [])


class PreservedOnPlanReviews(unittest.TestCase):  # same rule on the outline side: reviews of episode plans
    def review(self, target, preserved):
        doc = example("review-record")
        doc["target"] = {"kind": "local_file", "id": target, "revision": None}
        doc.pop("additionalTargets", None)
        doc["findings"] = []
        doc["preserved"] = preserved
        return contracts.check_contract("review-record", doc)

    def test_a_plan_review_keeps_only_human_sourced_items(self):
        errors = self.review("planning/episodes/episode-plan-005.json", ["第 3 拍的停顿"])
        self.assertTrue(any("human-sourced" in e for e in errors), errors)
        self.assertTrue(any("human source" in e for e in self.review("planning/episodes/episode-plan-005.json", [{"item": "停顿"}])))

    def test_sourced_items_pass_and_other_reviews_are_unchanged(self):
        self.assertEqual(self.review("planning/episodes/episode-plan-005.json", [{"item": "停顿", "noteId": "WN-1"}]), [])
        self.assertEqual(self.review("runs/plan/outline-005.md", ["第 3 拍的停顿"]), [])


class NumericTaskConstraints(unittest.TestCase):  # plan §4.4 acceptance wording
    def test_the_plan_s_own_examples_are_refused(self):
        for text in ("少 40 字", "比 e1 少 40 字", "不超过 3 行", "行数变化不超过 3 行"):
            doc = example("task")
            doc["constraints"] = [{"text": text, "origin": "orchestrator", "cite": "C1"}]
            with self.subTest(text=text):
                self.assertTrue(any("numeric_dialogue" in e for e in contracts.check_contract("task", doc)))

    def test_a_constraint_about_content_passes(self):
        doc = example("task")
        doc["constraints"] = [{"text": "称呼按台词目标 C2", "origin": "orchestrator", "cite": "C2"}]
        self.assertEqual(contracts.check_contract("task", doc), [])


class SamplesPackage(unittest.TestCase):  # decisions §1 (#2), §5: samples partition, quote cap, pack history
    _base = packs.D6PackTests
    setUp, tearDown, write, pack, SAMPLES, sample_pack = (_base.setUp, _base.tearDown, _base.write, _base.pack, _base.SAMPLES,
                                                          _base.sample_pack)

    def test_samples_go_to_their_own_partition(self):
        code, out = self.sample_pack(20000)
        self.assertEqual(code, 0, out.get("errors"))
        partitions = {i["partition"] for i in out["items"] if i["ref"].startswith("sample")}
        self.assertEqual(partitions, {"samples"})
        self.assertGreater(out["partition_chars"]["samples"], 0)

    def test_quotes_per_topic_caps_the_corpus_positives(self):
        for cap, expected in (("0", ["sample T2 对照对 CP-01"]), ("1", ["sample T1 正例 EX-0001", "sample T2 正例 EX-0002",
                                                                        "sample T2 对照对 CP-01"])):
            with self.subTest(cap=cap):
                items = [("current_plan", "runs/plan/episode-plan-003.json"), ("current_plan", "runs/plan/dialogue-plan-003.json")]
                args = [str(self.project / a) if a.startswith("runs/") else a for a in self.SAMPLES]
                code, out = self.pack("dialogue_designer", items, 20000, *args, "--quotes-per-topic", cap)
                self.assertEqual([i["ref"] for i in out["items"] if i["ref"].startswith("sample")], expected)
                self.assertEqual(out["samples"]["quotesPerTopic"], int(cap))

    def rewrite_corpus(self, rows):
        self.write("runs/corpus/exchanges.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

    def masked(self, ident, lines):
        return {"exchangeId": ident, "situation": {"function": "问清"}, "skeleton": "问一件 → 对方答", "maskedLines": lines}

    def test_a_raw_transcript_row_is_refused(self):
        rows = [self.masked(f"EX-000{i}", ["［甲］：嗯。"]) for i in range(1, 5)]
        rows[1] = {"exchangeId": "EX-0002", "situation": {"function": "问清"}, "lines": [{"speaker": "甲", "text": "原话"}]}
        self.rewrite_corpus(rows)
        code, out = self.sample_pack(20000)
        self.assertEqual(code, 1, out)
        self.assertIn("原始转写", out["error"])
        rows[1] = {"exchangeId": "EX-0002", "situation": {"function": "问清"}, "skeleton": "x"}  # no maskedLines either
        self.rewrite_corpus(rows)
        code, out = self.sample_pack(20000)
        self.assertEqual(code, 1, out)

    def test_the_cap_counts_masked_lines_and_leaves_whole_samples_out(self):
        rows = [self.masked("EX-0001", ["［甲］：一。"]), self.masked("EX-0002", ["［甲］：一。", "［乙］：二。"]),
                self.masked("EX-0003", ["［甲］：三。"]), self.masked("EX-0004", [])]
        self.rewrite_corpus(rows)
        code, out = self.sample_pack(20000)
        self.assertEqual(code, 0, out)
        self.assertEqual([o["ref"] for o in out["omitted"]], ["sample T2 正例 EX-0003"])  # T2 already has 2 lines from EX-0002
        self.assertEqual((out["samples"]["omittedForQuoteCap"], out["samples"]["maskedLinesPerTopic"]), (1, {"T1": 1, "T2": 2}))
        snapshot_items = [i for i in out["items"] if i["ref"].startswith("sample")]
        self.assertTrue(all(i["partition"] == "samples" for i in snapshot_items))

    def test_a_sample_without_masked_lines_fits_a_zero_cap(self):
        rows = [self.masked("EX-0001", []), self.masked("EX-0002", ["［甲］：一。"]), self.masked("EX-0003", []),
                self.masked("EX-0004", [])]
        self.rewrite_corpus(rows)
        items = [("current_plan", "runs/plan/episode-plan-003.json"), ("current_plan", "runs/plan/dialogue-plan-003.json")]
        args = [str(self.project / a) if a.startswith("runs/") else a for a in self.SAMPLES]
        code, out = self.pack("dialogue_designer", items, 20000, *args, "--quotes-per-topic", "0")
        packed = [i["ref"] for i in out["items"] if i["ref"].startswith("sample")]
        self.assertIn("sample T1 正例 EX-0001", packed)
        self.assertNotIn("sample T2 正例 EX-0002", packed)
        self.assertEqual({o["reason"] for o in out["omitted"]}, {"quote_cap"})

    def plan_with_masked_exemplars(self, lines_by_ref):
        for scene in self.dialogue_plan["scenes"]:
            for topic in scene["topics"]:
                for positive in topic["exemplars"]["positives"]:
                    if positive["ref"] in lines_by_ref:
                        positive.update(situationKey={"function": "问清"}, skeleton="问一件 → 对方答", walkthrough="她在防备",
                                        maskedLines=lines_by_ref[positive["ref"]])

    def pack_from_plan(self, *extra):  # a C5b author package, as the ruling describes
        self.task_doc.update(layer="C5b", dialogueTarget={"targetId": "town-dialogue-target", "revision": "v0.1"})
        items = [("current_plan", "runs/plan/dialogue-plan-003.json")]
        return self.pack("author", items, 20000, "--exemplars", str(self.project / "runs/plan/dialogue-plan-003.json"), *extra)

    def test_exemplars_can_be_read_from_the_dialogue_plan(self):  # D6-3 ruling: no separate JSONL needed
        self.plan_with_masked_exemplars({"TPL-TOWN-01#EX-0001": ["［甲］：一。"], "EX-0002": ["［甲］：二。", "［乙］：二。"], "EX-0003": ["［甲］：三。"]})
        code, out = self.pack_from_plan()
        self.assertEqual(code, 0, out)
        packed = [i["ref"] for i in out["items"] if i["ref"].startswith("sample")]
        self.assertEqual(packed, ["sample T1 正例 TPL-TOWN-01#EX-0001", "sample T2 正例 EX-0002"])
        self.assertTrue(all(i["partition"] == "samples" for i in out["items"] if i["ref"].startswith("sample")))
        self.assertEqual([o["ref"] for o in out["omitted"]], ["sample T2 正例 EX-0003"])  # T2 at 2 lines already
        self.assertEqual(out["samples"]["maskedLinesPerTopic"], {"T1": 1, "T2": 2})
        code, out = self.pack_from_plan("--quotes-per-topic", "0")
        self.assertEqual([i["ref"] for i in out["items"] if i["ref"].startswith("sample")], [])

    def test_a_plan_exemplar_without_masked_lines_is_refused(self):
        self.plan_with_masked_exemplars({"EX-0002": ["［甲］：二。"]})
        self.dialogue_plan["scenes"][0]["topics"][0]["exemplars"]["positives"][0].pop("maskedLines", None)  # T1 cites one without
        code, out = self.pack_from_plan()
        self.assertEqual(code, 1, out)
        self.assertIn("maskedLines", out["error"])

    def test_a_negative_cap_is_an_input_error(self):
        items = [("current_plan", "runs/plan/dialogue-plan-003.json")]
        code, out = self.pack("dialogue_designer", items, 20000, *self.SAMPLES[:2], "--quotes-per-topic", "-1")
        self.assertEqual(code, 1)

    def pack_written(self, episode):
        self.dialogue_plan["episode"] = episode
        items = [("current_plan", "runs/plan/episode-plan-003.json"), ("current_plan", "runs/plan/dialogue-plan-003.json")]
        args = [str(self.project / a) if a.startswith("runs/") else a for a in self.SAMPLES]
        self.write("runs/plan/episode-plan-003.json", self.episode_plan)
        self.write("runs/plan/dialogue-plan-003.json", self.dialogue_plan)
        task = self.base / "task.json"
        task.write_text(json.dumps(dict(self.task_doc, taskId=f"t-{episode}"), ensure_ascii=False), encoding="utf-8")
        selection = self.base / "sel.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": name, "revision": None}, "partition": part, "required": True, "reason": "测试"}
            for part, name in items]}, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(TOOL), "context-pack", str(self.project), "--task", str(task),
                               "--selection", str(selection), "--role", "dialogue_designer", "--budget", "20000", *args],
                              capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout or proc.stderr)

    def test_history_is_written_and_a_sample_repeated_next_episode_is_reported(self):
        code, out = self.pack_written(3)
        self.assertEqual((code, out["samples"]["repeatedFromPreviousEpisode"]), (0, []))
        history = json.loads((self.project / ".drama/packs/history.json").read_text(encoding="utf-8"))
        self.assertEqual([p["episode"] for p in history["packs"]], [3])
        code, out = self.pack_written(4)
        self.assertIn("3:positive:EX-0001", out["samples"]["repeatedFromPreviousEpisode"])
        code, out = self.pack_written(6)  # not consecutive to 4
        self.assertEqual(out["samples"]["repeatedFromPreviousEpisode"], [])

    def test_a_dry_run_reports_but_writes_no_history(self):
        code, out = self.sample_pack(20000)
        self.assertFalse((self.project / ".drama/packs/history.json").exists())
        self.assertEqual(out["samples"]["repeatedFromPreviousEpisode"], [])


class SamplesInSnapshots(unittest.TestCase):
    def test_old_snapshots_still_pass_and_samples_belong_to_c5_packages(self):
        doc = example("context-snapshot")
        self.assertEqual(contracts.check_contract("context-snapshot", doc), [])
        doc["items"][2]["partition"] = "samples"
        doc["items"][2]["ref"] = {"kind": "local_file", "id": "runs/corpus/exchanges.jsonl", "revision": doc["items"][2]["ref"]["revision"]}
        self.assertEqual(contracts.check_contract("context-snapshot", doc), [])
        doc["createdFor"]["role"] = "reader_effect"
        self.assertTrue(any("samples partition" in e for e in contracts.check_contract("context-snapshot", doc)))


if __name__ == "__main__":
    unittest.main()
