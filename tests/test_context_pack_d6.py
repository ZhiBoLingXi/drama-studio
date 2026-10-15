"""context-pack D6-1 roles: cold_reader, C5a (dialogue_designer) capacity gate, C5b dialogue-plan gate, samples by topic.

Synthetic fixtures from schemas/examples/ only. The old roles' behaviour is covered, unchanged, by test_context_pack.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
TEXT = "场3-1 镇口小卖部 上午\n刘叔：你那箱子，该不会也在里头？\n老陈：哪个仓库？\n"


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def exchange(ident, words):
    # D6-3 (plan §8 #2) changed this fixture on purpose: samples are packed as masked sample records, not transcript rows
    # with `lines`; the record keeps one masked line, so the D6-1 expectations below hold unchanged
    return {"exchangeId": ident, "situation": {"function": "问清"}, "skeleton": "问一件 → 对方答", "maskedLines": [f"［甲］：{words}"]}


class D6PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / "proj"
        self.task_doc = example("task")
        self.episode_plan = example("episode-plan")
        self.dialogue_plan = example("dialogue-plan")
        second = copy.deepcopy(self.dialogue_plan["scenes"][0]["topics"][0])
        second["topicId"] = "T2"
        second["segments"][0]["segmentId"] = "T2-s1"
        for index, row in enumerate(second["exchanges"]):
            row.update(exchangeId=f"X-T2-0{index + 1}", segmentId="T2-s1")
        second["exemplars"] = {"positives": [{"ref": "EX-0002", "source": "corpus"}, {"ref": "EX-0003", "source": "corpus"},
                                             {"ref": "EX-0004", "source": "corpus"}, {"ref": "writer-ep-001 L3", "source": "project"}],
                               "contrast": [{"pairId": "CP-01"}, {"pairId": "CP-02"}]}
        self.dialogue_plan["scenes"][0]["topics"].append(second)
        self.write("runs/ep-003.md", TEXT)
        self.write("runs/corpus/exchanges.jsonl", "\n".join(json.dumps(exchange(f"EX-000{i}", "甲说了一句话" * i), ensure_ascii=False)
                                                            for i in range(1, 5)) + "\n")
        # D6-4 changed this fixture on purpose: a contrast pair without a source (provenance or fromNotes) is not packed
        self.write("runs/contrast-pairs.jsonl", json.dumps({"pairId": "CP-01", "whyNotHere": "这里对方不会接话",
                                                            "provenance": {"negativeFrom": "check_and_retell"}}, ensure_ascii=False) + "\n")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False), encoding="utf-8")

    def pack(self, role, items, budget=20000, *extra):
        self.write("runs/plan/episode-plan-003.json", self.episode_plan)
        self.write("runs/plan/dialogue-plan-003.json", self.dialogue_plan)
        task = self.base / "task.json"
        task.write_text(json.dumps(self.task_doc, ensure_ascii=False), encoding="utf-8")
        selection = self.base / "sel.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": name, "revision": None}, "partition": part, "required": True, "reason": "测试"}
            for part, name in items]}, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(TOOL), "context-pack", str(self.project), "--task", str(task),
                                 "--selection", str(selection), "--role", role, "--budget", str(budget), "--dry-run", *extra],
                                capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    # cold_reader -------------------------------------------------------------------------------------------------
    def test_cold_reader_takes_one_project_facts_item(self):
        code, out = self.pack("cold_reader", [("project_facts", "runs/ep-003.md")])
        self.assertEqual((code, out["passed"]), (0, True), out.get("errors"))

    def test_cold_reader_with_two_items_or_a_plan_exits_2(self):
        code, out = self.pack("cold_reader", [("project_facts", "runs/ep-003.md"), ("project_facts", "runs/plan/episode-plan-003.json")])
        self.assertEqual(code, 2)
        self.assertTrue(any("exactly one project_facts" in e for e in out["errors"]), out["errors"])
        code, out = self.pack("cold_reader", [("project_facts", "runs/ep-003.md"), ("current_plan", "runs/plan/episode-plan-003.json")])
        self.assertEqual(code, 2)
        self.assertTrue(any("current_plan" in e for e in out["errors"]), out["errors"])

    # C5a ---------------------------------------------------------------------------------------------------------
    def test_c5a_packs_a_plan_that_fits(self):
        code, out = self.pack("dialogue_designer", [("current_plan", "runs/plan/episode-plan-003.json")])
        self.assertEqual(code, 0, out.get("errors"))

    def test_c5a_without_an_episode_plan_exits_2(self):
        code, out = self.pack("dialogue_designer", [("project_facts", "runs/ep-003.md")])
        self.assertEqual(code, 2)
        self.assertTrue(any("no episode-plan" in e for e in out["errors"]))

    def test_c5a_proposal_needs_a_decision_with_a_default(self):
        self.episode_plan["capacity"]["status"] = "proposal:D-001"
        code, out = self.pack("dialogue_designer", [("current_plan", "runs/plan/episode-plan-003.json")])
        self.assertEqual(code, 2)
        self.assertTrue(any("no decision queue" in e for e in out["errors"]), out["errors"])
        self.write("planning/decisions.json", example("decision-queue"))
        code, out = self.pack("dialogue_designer", [("current_plan", "runs/plan/episode-plan-003.json")])
        self.assertEqual(code, 0, out.get("errors"))
        queue = example("decision-queue")
        queue["entries"][0]["default"] = None
        self.write("runs/plan/decisions.json", queue)
        code, out = self.pack("dialogue_designer", [("current_plan", "runs/plan/episode-plan-003.json"),
                                                    ("current_plan", "runs/plan/decisions.json")])
        self.assertEqual(code, 2)
        self.assertTrue(any("without a default" in e for e in out["errors"]), out["errors"])

    def test_c5a_other_capacity_status_exits_2(self):
        self.episode_plan["capacity"]["status"] = "exceeds"
        code, out = self.pack("dialogue_designer", [("current_plan", "runs/plan/episode-plan-003.json")])
        self.assertEqual(code, 2)

    # C5b ---------------------------------------------------------------------------------------------------------
    def c5b(self):
        self.task_doc.update(layer="C5b", dialogueTarget={"targetId": "town-dialogue-target", "revision": "v0.1"})

    def test_c5b_packs_a_dialogue_plan_that_passes_contract_check(self):
        self.c5b()
        code, out = self.pack("author", [("current_plan", "runs/plan/dialogue-plan-003.json")])
        self.assertEqual(code, 0, out.get("errors"))

    def test_c5b_with_a_broken_or_missing_dialogue_plan_exits_2(self):
        self.c5b()
        code, out = self.pack("author", [("project_facts", "runs/ep-003.md")])
        self.assertEqual(code, 2)
        del self.dialogue_plan["infoLedger"]
        code, out = self.pack("author", [("current_plan", "runs/plan/dialogue-plan-003.json")])
        self.assertEqual(code, 2)
        self.assertTrue(any("fails contract-check dialogue-plan" in e for e in out["errors"]), out["errors"])

    def test_without_a_layer_the_author_role_is_unchanged(self):
        code, out = self.pack("author", [("project_facts", "runs/ep-003.md")])
        self.assertEqual(code, 0, out.get("errors"))
        self.assertNotIn("samples", out)

    # samples -----------------------------------------------------------------------------------------------------
    SAMPLES = ("--exemplars", "runs/corpus/exchanges.jsonl", "--contrast-pairs", "runs/contrast-pairs.jsonl")

    def sample_pack(self, budget):
        items = [("current_plan", "runs/plan/episode-plan-003.json"), ("current_plan", "runs/plan/dialogue-plan-003.json")]
        args = [str(self.project / a) if a.startswith("runs/") else a for a in self.SAMPLES]
        return self.pack("dialogue_designer", items, budget, *args)

    def test_two_positives_and_one_pair_per_topic(self):
        code, out = self.sample_pack(20000)
        self.assertEqual(code, 0, out.get("errors"))
        samples = [i["ref"] for i in out["items"] if i["ref"].startswith("sample")]
        # T1 cites EX-0001; T2 cites EX-0002..4 (third left out), a project positive (not a corpus sample) and two pairs
        self.assertEqual(samples, ["sample T1 正例 EX-0001", "sample T2 正例 EX-0002", "sample T2 对照对 CP-01", "sample T2 正例 EX-0003"])
        self.assertEqual(out["samples"]["unresolved"], [])
        self.assertEqual(out["samples"]["omittedForBudget"], 0)

    def test_a_cited_sample_missing_from_the_file_is_listed_unresolved(self):
        self.dialogue_plan["scenes"][0]["topics"][0]["exemplars"]["positives"].insert(0, {"ref": "EX-9999", "source": "corpus"})
        code, out = self.sample_pack(20000)
        self.assertEqual((code, out["samples"]["unresolved"]), (0, ["T1:EX-9999"]))

    def test_budget_drops_whole_samples_from_the_lowest_priority(self):
        code, full = self.sample_pack(20000)
        need = full["total_chars"]
        last = next(i["chars"] for i in full["items"] if i["ref"] == "sample T2 正例 EX-0003")
        code, out = self.sample_pack(need - 1)
        self.assertEqual(code, 0, out.get("errors"))
        self.assertEqual(out["samples"]["omittedForBudget"], 1)
        self.assertEqual([o["ref"] for o in out["omitted"]], ["sample T2 正例 EX-0003"])
        self.assertEqual(out["omitted"][0]["reason"], "budget")
        self.assertEqual(out["total_chars"], need - last)

    def test_samples_only_for_c5a_or_c5b_and_inside_the_project(self):
        code, out = self.pack("reader_effect", [("project_facts", "runs/ep-003.md")], 20000,
                              "--exemplars", str(self.project / "runs/corpus/exchanges.jsonl"))
        self.assertEqual(code, 1)
        outside = self.base / "exchanges.jsonl"
        outside.write_text("", encoding="utf-8")
        code, out = self.pack("dialogue_designer", [("current_plan", "runs/plan/episode-plan-003.json"),
                                                    ("current_plan", "runs/plan/dialogue-plan-003.json")], 20000, "--exemplars", str(outside))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
