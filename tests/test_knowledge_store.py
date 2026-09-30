import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
EXAMPLE = json.loads((ROOT / "skills/drama-studio/schemas/examples/knowledge-card.json").read_text(encoding="utf-8"))


def card(card_id, revision=1, knowledge_type="K3", workstations=("C2", "C4", "C5"), usage="creative_reference",
         processing="pending", sources=None, problem=None):
    doc = copy.deepcopy(EXAMPLE)
    doc.update(cardId=card_id, revision=revision, knowledgeType=knowledge_type, usage=usage, processing=processing)
    doc["transfer"]["workstations"] = list(workstations)
    if sources:
        doc["evidence"] = {"nature": "observation", "sources": [
            {"sourceId": source_id, "location": location, "versionOrDate": "2026-09-30"} for source_id, location in sources]}
    if problem:
        doc["content"]["problem"] = problem
    return doc


def run_cli(*args):
    run = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    return run.returncode, json.loads(run.stdout or run.stderr)


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


class KnowledgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "proj"
        self.cards = self.project / "knowledge/cards"
        self.cards.mkdir(parents=True)
        source = self.project / "knowledge/sources/src-shared"
        source.mkdir(parents=True)
        (source / "notes.md").write_text("第一行\n第二行\n第三行\n", encoding="utf-8")
        self.write(card("kc-a", 1, problem="旧版问题"))
        self.write(card("kc-a", 2, sources=[("src-shared", "knowledge/sources/src-shared/notes.md#L1-L3")],
                        problem="新版：道歉必须有代价"))
        self.write(card("kc-b", 1, knowledge_type="K1", workstations=["C5"], usage="comparison_only",
                        sources=[("src-shared", "mali-story://templates/tpl-9#ep3")], problem="退婚场面如何反转"))
        self.write(card("kc-c", 1, workstations=["C1"], usage="evaluation_only", processing="retired",
                        sources=[("src-solo", "https://example.com/report")]))
        self.write(card("kc-d", 1, knowledge_type="K2", workstations=["C3"],
                        sources=[("src-solo", "mali-story://templates/tpl-2")]))
        (self.cards / "README.txt").write_text("说明", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, doc, name=None):
        name = name or f"{doc['cardId']}@r{doc['revision']}.json"
        (self.cards / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return self.cards / name

    def search(self, *args):
        return run_cli("knowledge", "search", self.project, *args)

    def ids(self, result):
        return [item["cardId"] for item in result["results"]]

    def test_valid_store_passes_and_ignores_non_json(self):
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 0, result)
        self.assertTrue(result["passed"])
        self.assertEqual(result["checked"], 5)
        self.assertEqual(result["invalid"], [])
        self.assertTrue(any(path.endswith("README.txt") for path in result["ignored"]))
        for key, value in (("network_used", False), ("models_called", False), ("read_only", True)):
            self.assertIs(result[key], value)

    def test_ac1_one_invalid_card_exits_2_with_path_and_errors(self):
        bad = card("kc-bad")
        del bad["usage"]
        path = self.write(bad)
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["invalid"]), 1)
        self.assertEqual(result["invalid"][0]["path"], str(path))
        self.assertTrue(any("usage: required" in error for error in result["invalid"][0]["errors"]))

    def test_broken_json_is_an_invalid_card_not_a_crash(self):
        (self.cards / "kc-broken@r1.json").write_text("{", encoding="utf-8")
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2)
        self.assertTrue(result["ok"])
        self.assertTrue(result["invalid"][0]["path"].endswith("kc-broken@r1.json"))

    def test_filename_mismatch_or_bad_revision_exits_2(self):
        self.write(card("kc-e", 1), name="kc-e@r2.json")
        self.write(card("kc-f", 1), name="kc-other@r1.json")
        self.write(card("kc-g", 1), name="kc-g@r0.json")
        self.write(card("kc-h", 1), name="kc-h.json")
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2)
        errors = {Path(item["path"]).name: " ".join(item["errors"]) for item in result["invalid"]}
        self.assertIn("revision", errors["kc-e@r2.json"])
        self.assertIn("cardId", errors["kc-other@r1.json"])
        self.assertIn("filename", errors["kc-g@r0.json"])
        self.assertIn("filename", errors["kc-h.json"])

    def test_cardid_containing_at_r_splits_on_last_marker(self):
        self.write(card("kc@rich", 3))
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 0, result)

    def test_ac5_studio_scope_card_is_rejected(self):
        studio = card("kc-studio")
        studio["scope"]["level"] = "studio"
        self.write(studio)
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2)
        self.assertTrue(any("not enabled in this version" in error for error in result["invalid"][0]["errors"]))

    def test_ac2_type_filter_and_retired_exclusion(self):
        code, result = self.search("--type", "K3")
        self.assertEqual(code, 0, result)
        self.assertIsNone(result["passed"])
        self.assertEqual(self.ids(result), ["kc-a"])
        self.assertTrue(all(item["knowledgeType"] == "K3" for item in result["results"]))
        code, result = self.search("--type", "K3", "--include-retired")
        self.assertEqual(code, 0)
        self.assertEqual(self.ids(result), ["kc-a", "kc-c"])
        code, result = self.search()
        self.assertNotIn("kc-c", self.ids(result))

    def test_ac3_shared_source_marks_both_cards(self):
        code, result = self.search()
        by_id = {item["cardId"]: item for item in result["results"]}
        self.assertEqual(by_id["kc-a"]["sameSource"], [{"sourceId": "src-shared", "cards": ["kc-b"]}])
        self.assertEqual(by_id["kc-b"]["sameSource"], [{"sourceId": "src-shared", "cards": ["kc-a"]}])
        self.assertIn("同源:src-shared", by_id["kc-a"]["line"])
        self.assertIn("同源:src-shared", by_id["kc-b"]["line"])
        self.assertEqual(by_id["kc-a"]["line"].split()[:4], ["kc-a@r2", "K3", "C2,C4,C5", "creative_reference"])
        # The retired sibling does not create a same-source mark by default.
        self.assertEqual(by_id["kc-d"]["sameSource"], [])
        self.assertIn("无同源", by_id["kc-d"]["line"])
        code, result = self.search("--include-retired")
        by_id = {item["cardId"]: item for item in result["results"]}
        self.assertEqual(by_id["kc-d"]["sameSource"], [{"sourceId": "src-solo", "cards": ["kc-c"]}])

    def test_same_source_is_computed_before_filters(self):
        code, result = self.search("--type", "K1")
        self.assertEqual(self.ids(result), ["kc-b"])
        self.assertEqual(result["results"][0]["sameSource"], [{"sourceId": "src-shared", "cards": ["kc-a"]}])

    def test_workstation_usage_and_text_filters(self):
        self.assertEqual(self.ids(self.search("--workstation", "C5")[1]), ["kc-a", "kc-b"])
        self.assertEqual(self.ids(self.search("--workstation", "C3")[1]), ["kc-d"])
        self.assertEqual(self.ids(self.search("--usage", "comparison_only")[1]), ["kc-b"])
        self.assertEqual(self.ids(self.search("--text", "退婚")[1]), ["kc-b"])
        self.assertEqual(self.ids(self.search("--text", "KC-D")[1]), ["kc-d"])
        self.assertEqual(self.ids(self.search("--text", "旧版问题")[1]), [])

    def test_search_uses_latest_revision_and_show_honours_revision(self):
        code, result = self.search("--type", "K3")
        self.assertEqual(result["results"][0]["revision"], 2)
        code, result = run_cli("knowledge", "show", self.project, "kc-a")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["card"]["revision"], 2)
        code, result = run_cli("knowledge", "show", self.project, "kc-a", "--revision", "1")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["card"]["content"]["problem"], "旧版问题")
        self.assertEqual(result["available_revisions"], [1, 2])

    def test_search_reports_invalid_cards_and_excludes_them(self):
        bad = card("kc-bad")
        bad["scope"]["level"] = "public"
        self.write(bad)
        code, result = self.search()
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        self.assertNotIn("kc-bad", self.ids(result))
        self.assertTrue(result["invalid"][0]["path"].endswith("kc-bad@r1.json"))

    def test_ac4_show_reports_local_source_status(self):
        code, result = run_cli("knowledge", "show", self.project, "kc-a")
        self.assertEqual(code, 0, result)
        source = result["sources"][0]
        self.assertEqual(source["status"], "present")
        self.assertEqual(source["position"], "L1-L3")
        self.assertTrue(source["path"].endswith("knowledge/sources/src-shared/notes.md"))
        code, result = run_cli("knowledge", "show", self.project, "kc-b")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["sources"][0]["status"], "external_not_checked")
        self.write(card("kc-a", 3, sources=[("src-shared", "knowledge/sources/src-shared/gone.md#L5")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-a")
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        self.assertEqual(result["sources"][0]["status"], "missing")
        self.assertEqual(result["missing"], ["knowledge/sources/src-shared/gone.md#L5"])

    def test_show_rejects_path_traversal_out_of_source_dir(self):
        (self.project / "secret.md").write_text("x", encoding="utf-8")
        for index, location in enumerate(["knowledge/sources/src-shared/../../../secret.md",
                                          "knowledge/sources/src-other/notes.md"], start=1):
            self.write(card(f"kc-t{index}", sources=[("src-shared", location)]))
            code, result = run_cli("knowledge", "show", self.project, f"kc-t{index}")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["sources"][0]["status"], "outside_source_dir")

    def test_show_invalid_card_exits_2(self):
        bad = card("kc-bad")
        bad["scope"]["level"] = "studio"
        self.write(bad)
        code, result = run_cli("knowledge", "show", self.project, "kc-bad")
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        self.assertTrue(result["errors"])

    def test_unknown_card_revision_or_project_exits_1(self):
        self.assertEqual(run_cli("knowledge", "show", self.project, "kc-none")[0], 1)
        self.assertEqual(run_cli("knowledge", "show", self.project, "kc-a", "--revision", "9")[0], 1)
        self.assertEqual(run_cli("knowledge", "validate", self.project / "nope")[0], 1)
        self.assertEqual(run_cli("knowledge", "search", self.project / "nope")[0], 1)

    def test_missing_store_is_empty_with_hint(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        for command in ("validate", "search"):
            with self.subTest(command=command):
                code, result = run_cli("knowledge", command, empty)
                self.assertEqual(code, 0, result)
                self.assertTrue(result["ok"])
                self.assertIsNone(result["passed"])
                self.assertEqual(result["store_status"], "no_store")
                self.assertIn("knowledge/cards/<cardId>@r<revision>.json", result["hint"])
        self.assertEqual(run_cli("knowledge", "search", empty)[1]["results"], [])
        self.assertEqual(run_cli("knowledge", "show", empty, "kc-a")[0], 1)
        self.assertEqual(list(empty.iterdir()), [])

    def test_commands_are_read_only(self):
        (self.cards / "kc-broken@r1.json").write_text("{", encoding="utf-8")
        self.write(card("kc-m", sources=[("src-shared", "knowledge/sources/src-shared/gone.md")]))
        before = snapshot(self.project)
        run_cli("knowledge", "validate", self.project)
        self.search()
        self.search("--include-retired", "--text", "道歉", "--workstation", "C5", "--usage", "creative_reference", "--type", "K3")
        for args in (("kc-a",), ("kc-a", "--revision", "1"), ("kc-b",), ("kc-m",), ("kc-broken",), ("kc-none",)):
            run_cli("knowledge", "show", self.project, *args)
        self.assertEqual(snapshot(self.project), before)

    def test_doctor_still_offline(self):
        code, result = run_cli("doctor")
        self.assertEqual(code, 0)
        self.assertFalse(result["network_used"])
        self.assertFalse(result["models_called"])


if __name__ == "__main__":
    unittest.main()
