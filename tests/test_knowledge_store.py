import copy
import hashlib
import json
import os
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

    def test_show_symlink_loop_source_is_unresolvable(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink not supported")
        loop_dir = self.project / "knowledge/sources/src-loop"
        loop_dir.mkdir()
        link = loop_dir / "loop.md"
        try:
            os.symlink(link, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not supported")
        self.write(card("kc-loop", sources=[("src-loop", "knowledge/sources/src-loop/loop.md")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-loop")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["sources"][0]["status"], "unresolvable")
        self.assertIn("error", result["sources"][0])
        self.assertIn(result["sources"][0]["location"], result["missing"])

    def test_show_symlink_escaping_source_dir_exits_2(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink not supported")
        outside = self.project / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        source_dir = self.project / "knowledge/sources/src-link"
        source_dir.mkdir()
        link = source_dir / "escape.md"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not supported")
        self.write(card("kc-escape", sources=[("src-link", "knowledge/sources/src-link/escape.md")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-escape")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["sources"][0]["status"], "outside_source_dir")

    def test_show_source_id_with_dotdot_exits_2(self):
        self.write(card("kc-traverse", sources=[("../secret", "knowledge/sources/../secret/notes.md")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-traverse")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["sources"][0]["status"], "outside_source_dir")

    def test_show_nul_in_location_is_unresolvable_exit_2_not_1(self):
        self.write(card("kc-nul", sources=[("src-shared", "knowledge/sources/src-shared/notes\x00.md")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-nul")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["sources"][0]["status"], "unresolvable")

    def test_source_dir_itself_is_missing_not_outside(self):
        self.write(card("kc-dir", sources=[("src-shared", "knowledge/sources/src-shared")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-dir")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["sources"][0]["status"], "missing")

    def test_deeply_nested_json_card_is_invalid_not_a_crash(self):
        (self.cards / "kc-deep@r1.json").write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2, result)
        self.assertTrue(any(item["path"].endswith("kc-deep@r1.json") for item in result["invalid"]))
        self.assertTrue(any(item["path"].endswith("kc-a@r2.json") for item in result["valid"]))

    def test_non_dict_json_card_is_invalid(self):
        (self.cards / "kc-list@r1.json").write_text("[1, 2, 3]", encoding="utf-8")
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2, result)
        self.assertTrue(any(item["path"].endswith("kc-list@r1.json") for item in result["invalid"]))

    def test_non_utf8_card_is_invalid(self):
        (self.cards / "kc-bytes@r1.json").write_bytes(b"\xff\xfe\x00\x01")
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2, result)
        self.assertTrue(any(item["path"].endswith("kc-bytes@r1.json") for item in result["invalid"]))

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() != 0, "cannot deny read access as root")
    def test_unreadable_card_is_invalid_others_still_processed(self):
        path = self.write(card("kc-locked"))
        path.chmod(0o000)
        try:
            code, result = run_cli("knowledge", "validate", self.project)
            self.assertEqual(code, 2, result)
            self.assertTrue(any(item["path"].endswith("kc-locked@r1.json") for item in result["invalid"]))
            self.assertTrue(any(item["path"].endswith("kc-a@r2.json") for item in result["valid"]))
        finally:
            path.chmod(0o644)

    def test_non_file_named_like_a_card_is_invalid_not_ignored(self):
        (self.cards / "kc-a@r3.json").mkdir()
        if hasattr(os, "symlink"):
            try:
                os.symlink(Path(self.temp.name) / "nowhere.json", self.cards / "kc-a@r4.json")
            except (OSError, NotImplementedError):
                pass
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2, result)
        self.assertIn(3, [item["revision"] for item in result["invalid"] if item["cardId"] == "kc-a"])
        self.assertTrue(all("not a regular file" in item["errors"][0] for item in result["invalid"]))
        code, result = run_cli("knowledge", "search", self.project)
        self.assertEqual(code, 2, result)
        hit = next(item for item in result["results"] if item["cardId"] == "kc-a")
        self.assertEqual(hit["revision"], 2)
        self.assertIn(3, hit["newerInvalidRevisions"])
        self.assertIn("[newer-invalid:r3", hit["line"])

    def test_unexpandable_home_is_a_json_error_not_a_traceback(self):
        run = subprocess.run([sys.executable, "-B", str(TOOL), "knowledge", "validate", "~no_such_user_zz9/proj"],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertNotIn("Traceback", run.stderr)
        self.assertFalse(json.loads(run.stderr)["ok"])

    def test_source_id_spelling_variants_do_not_alias_a_folder(self):
        cases = [("src-shared/", "knowledge/sources/src-shared/notes.md", "outside_source_dir"),
                 ("SRC-SHARED", "knowledge/sources/SRC-SHARED/notes.md", "missing")]
        for index, (source_id, location, status) in enumerate(cases, start=1):
            self.write(card(f"kc-alias{index}", sources=[(source_id, location)]))
            code, result = run_cli("knowledge", "show", self.project, f"kc-alias{index}")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["sources"][0]["status"], status)

    def test_show_without_local_sources_does_not_claim_a_pass(self):
        code, result = run_cli("knowledge", "show", self.project, "kc-b")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["local_sources_checked"], 0)
        self.assertIsNone(result["passed"])
        code, result = run_cli("knowledge", "show", self.project, "kc-a")
        self.assertTrue(result["passed"])
        self.assertFalse(result["sources"][0]["position_checked"])

    def test_no_cards_status_is_ok_with_hint(self):
        no_cards = Path(self.temp.name) / "no-cards"
        (no_cards / "knowledge").mkdir(parents=True)
        code, result = run_cli("knowledge", "validate", no_cards)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["store_status"], "no_cards")
        self.assertIn("knowledge/cards/<cardId>@r<revision>.json", result["hint"])

    def test_empty_cards_dir_validate_passed_null_exit_0(self):
        empty_cards = Path(self.temp.name) / "empty-cards"
        (empty_cards / "knowledge/cards").mkdir(parents=True)
        code, result = run_cli("knowledge", "validate", empty_cards)
        self.assertEqual(code, 0, result)
        self.assertIsNone(result["passed"])
        self.assertEqual(result["checked"], 0)

    def test_newest_invalid_revision_falls_back_to_older_valid(self):
        bad = card("kc-a", 3)
        del bad["usage"]
        self.write(bad)
        code, result = self.search()
        self.assertEqual(code, 2, result)
        by_id = {item["cardId"]: item for item in result["results"]}
        self.assertEqual(by_id["kc-a"]["revision"], 2)
        self.assertEqual(by_id["kc-a"]["newerInvalidRevisions"], [3])
        self.assertIn("[newer-invalid:r3]", by_id["kc-a"]["line"])
        code, result = run_cli("knowledge", "show", self.project, "kc-a")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["revision"], 3)
        self.assertTrue(result["errors"])

    def test_invalid_entries_carry_card_id_and_revision(self):
        bad = card("kc-bad")
        del bad["usage"]
        self.write(bad)
        code, result = run_cli("knowledge", "validate", self.project)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["invalid"][0]["cardId"], "kc-bad")
        self.assertEqual(result["invalid"][0]["revision"], 1)
        self.write(card("kc-x", 1), name="kc-bad-name.json")
        code, result = run_cli("knowledge", "validate", self.project)
        stray = next(item for item in result["invalid"] if item["path"].endswith("kc-bad-name.json"))
        self.assertIsNone(stray["cardId"])
        self.assertIsNone(stray["revision"])

    def test_show_reports_local_sources_checked_count(self):
        self.write(card("kc-multi", sources=[
            ("src-shared", "knowledge/sources/src-shared/notes.md"),
            ("src-solo", "mali-story://templates/tpl-2")]))
        code, result = run_cli("knowledge", "show", self.project, "kc-multi")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["local_sources_checked"], 1)

    def test_text_filter_does_not_match_workstation_code(self):
        code, result = self.search("--text", "C2")
        self.assertEqual(self.ids(result), [])

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
