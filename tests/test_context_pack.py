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
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
EP1 = "第一集：林晚推开门，雨声灌进屋里。她把湿透的信放在桌上，父亲没有抬头。\n" * 8
EP2 = "第二集：父亲终于开口，说那封信是他十年前寄出的。林晚攥紧了伞柄。\n" * 8
PLAN = "第三集集纲：林晚决定离开小镇，父亲在车站追上她，却只递过一把伞。\n"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def card(card_id, usage="creative_reference", processing="pending", revision=1):
    doc = json.loads((EXAMPLES / "knowledge-card.json").read_text(encoding="utf-8"))
    doc.update(cardId=card_id, revision=revision, usage=usage, processing=processing)
    if usage == "evaluation_only":
        doc["evidence"] = {"nature": "observation", "sources": [{"sourceId": "src-1", "location": "第3集 02:10", "versionOrDate": "2026-09-01"}]}
    return doc


def cache_ref(artifact_id, revision, partition="project_facts", required=True, **extra):
    ref = {"kind": "remote_artifact", "id": artifact_id, "revision": revision}
    ref.update(extra.pop("ref", {}))
    return {"ref": ref, "partition": partition, "required": required, "reason": "测试材料", **extra}


def card_ref(card_id, revision=1, required=False, **extra):
    return {"ref": {"kind": "knowledge_card", "id": card_id, "revision": revision}, "partition": "knowledge",
            "required": required, "reason": "测试知识卡", **extra}


class ContextPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.make_project(self.base / "proj")
        task = json.loads((EXAMPLES / "task.json").read_text(encoding="utf-8"))
        self.task = self.base / "task.json"
        self.task.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def make_project(self, project):
        cache = project / ".drama" / "cache"
        cache.mkdir(parents=True)
        entries = []
        for artifact, revision, slot, text, verified in (
                ("art-ep01", 1, "episode-1-draft", EP1, True), ("art-ep02", 2, "episode-2-draft", EP2, True),
                ("art-ep02-old", 1, "episode-2-draft", EP2[:40], True), ("art-plan03", 1, "episode-3-outline", PLAN, True),
                ("art-ep03", 1, "episode-3-draft", EP1[:30], False)):
            name = f"{artifact}@r{revision}.md"
            data = text.encode("utf-8")
            (cache / name).write_bytes(data)
            entries.append({"path": f".drama/cache/{name}", "artifactId": artifact, "slot": slot, "kind": "episode_draft",
                            "episodeRef": None, "revision": revision, "sha256": sha(data),
                            "serverFingerprint": sha(data) if verified else None, "verified": verified,
                            "operation": "read_story_artifact", "readAt": "2026-09-30T08:00:00Z"})
        (cache / "manifest.json").write_text(json.dumps({"schemaVersion": "drama-studio/cache-manifest/v0", "entries": entries},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
        cards = project / "knowledge" / "cards"
        cards.mkdir(parents=True)
        for doc in (card("kc-cost"), card("kc-old", processing="retired"), card("kc-eval", usage="evaluation_only"),
                    card("kc-cmp", usage="comparison_only"), card("kc-cost", revision=2)):
            (cards / f"{doc['cardId']}@r{doc['revision']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return project

    def selection(self, items, name="sel.json", **extra):
        path = self.base / name
        path.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": items, **extra}, ensure_ascii=False), encoding="utf-8")
        return path

    def default_items(self):
        return [cache_ref("art-ep01", 1, ref={"range": {"start": 0, "end": 60}}),
                cache_ref("art-ep02", 2), cache_ref("art-plan03", 1, partition="current_plan"), card_ref("kc-cost")]

    def pack(self, items=None, role="author", budget=20000, project=None, *flags, selection=None):
        selection = selection or self.selection(self.default_items() if items is None else items)
        run = subprocess.run([sys.executable, "-B", str(TOOL), "context-pack", str(project or self.project), "--task", str(self.task),
                              "--selection", str(selection), "--role", role, "--budget", str(budget), *flags],
                             capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def snapshots(self, project=None):
        folder = (project or self.project) / ".drama" / "snapshots"
        return sorted(path.name for path in folder.iterdir()) if folder.exists() else []

    def written(self, result):
        return json.loads(Path(result["snapshot_path"]).read_text(encoding="utf-8"))

    def test_ac1_two_runs_are_byte_identical_and_report_path_chars_budget_omitted(self):
        code, first = self.pack()
        self.assertEqual(code, 0, first)
        for key in ("snapshot_path", "snapshot_id", "snapshot_sha256", "total_chars", "budget", "partition_chars", "omitted_count", "completeness"):
            self.assertIn(key, first)
        self.assertTrue(first["written"])
        self.assertEqual((first["budget"], first["omitted_count"]), (20000, 0))
        code, again = self.pack()
        self.assertEqual(code, 0)
        self.assertEqual((again["written"], again["existing"]), (False, True))
        other = self.make_project(self.base / "proj2")
        code, twin = self.pack(None, "author", 20000, other)
        self.assertEqual(code, 0)
        self.assertEqual(Path(first["snapshot_path"]).read_bytes(), Path(twin["snapshot_path"]).read_bytes())
        self.assertEqual(first["snapshot_sha256"], twin["snapshot_sha256"])
        self.assertTrue(first["snapshot_id"].startswith("ctx-"))

    def test_ac2_chars_are_measured_and_host_estimates_are_ignored(self):
        code, result = self.pack()
        self.assertEqual(code, 0)
        items = self.written(result)["items"]
        self.assertEqual(items[0]["partition"], "task")
        self.assertEqual(items[0]["chars"], len(self.task.read_text(encoding="utf-8")))
        self.assertEqual(items[1]["chars"], len(EP1[0:60]))
        self.assertEqual(items[1]["sha256"], sha(EP1[0:60].encode("utf-8")))
        self.assertEqual(items[1]["ref"]["sha256"], sha(EP1.encode("utf-8")))
        self.assertEqual(items[2]["chars"], len(EP2))
        self.assertNotEqual(len(EP1[0:60].encode("utf-8")), items[1]["chars"])
        wrong = self.default_items()
        wrong[0]["chars"] = 99999
        wrong[1]["chars"] = 1
        code, estimated = self.pack(wrong, project=self.make_project(self.base / "proj2"))
        self.assertEqual(code, 0)
        self.assertEqual(Path(estimated["snapshot_path"]).read_bytes(), Path(result["snapshot_path"]).read_bytes())

    def test_ac3_missing_required_reference_makes_the_package_incomplete(self):
        code, result = self.pack(self.default_items() + [cache_ref("art-ep09", 1), card_ref("kc-absent")])
        self.assertEqual(code, 0, result)
        snapshot = self.written(result)
        self.assertEqual(snapshot["completeness"], "incomplete")
        self.assertEqual(snapshot["omitted"], [
            {"ref": {"kind": "remote_artifact", "id": "art-ep09", "revision": 1}, "required": True, "reason": "missing"},
            {"ref": {"kind": "knowledge_card", "id": "kc-absent", "revision": 1}, "required": False, "reason": "missing"}])
        self.assertEqual(result["omitted_count"], 2)

    def test_ac4_over_budget_exits_2_and_writes_nothing(self):
        code, result = self.pack(budget=100)
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        error = " ".join(result["errors"])
        self.assertIn("exceed --budget 100 by", error)
        self.assertIn("project_facts=", error)
        self.assertIn("current_plan=", error)
        self.assertEqual(self.snapshots(), [])

    def test_ac5_reader_effect_rejects_author_plan_and_names_the_item(self):
        code, result = self.pack(role="reader_effect")
        self.assertEqual(code, 2)
        self.assertTrue(any("selection.items[2]" in e and "art-plan03@r1" in e and "current_plan" in e for e in result["errors"]), result["errors"])
        self.assertEqual(self.snapshots(), [])

    def test_ac6_retired_card_is_omitted_as_not_relevant(self):
        code, result = self.pack(self.default_items() + [card_ref("kc-old", required=True)])
        self.assertEqual(code, 0, result)
        snapshot = self.written(result)
        self.assertNotIn("kc-old", [item["ref"]["id"] for item in snapshot["items"]])
        self.assertEqual(snapshot["omitted"], [{"ref": {"kind": "knowledge_card", "id": "kc-old", "revision": 1}, "required": True, "reason": "not_relevant"}])
        self.assertEqual(snapshot["completeness"], "incomplete")

    def test_ac6b_same_slot_two_artifacts_and_tampered_cache_exit_2(self):
        code, result = self.pack(self.default_items() + [cache_ref("art-ep02-old", 1)])
        self.assertEqual(code, 2)
        self.assertTrue(any("slot 'episode-2-draft'" in e and "art-ep02-old@r1" in e for e in result["errors"]), result["errors"])
        path = self.project / ".drama/cache/art-ep02@r2.md"
        data = bytearray(path.read_bytes())
        data[0] ^= 1
        path.write_bytes(bytes(data))
        code, result = self.pack()
        self.assertEqual(code, 2)
        self.assertTrue(any("art-ep02@r2" in e and "changed after caching" in e for e in result["errors"]), result["errors"])
        self.assertEqual(self.snapshots(), [])

    def test_card_revisions_cannot_mix(self):
        code, result = self.pack(self.default_items() + [card_ref("kc-cost", revision=2)])
        self.assertEqual(code, 2)
        self.assertTrue(any("kc-cost" in e and "mix card revisions" in e for e in result["errors"]), result["errors"])

    def test_unverified_cache_is_refused_unless_explicitly_allowed(self):
        items = [cache_ref("art-ep03", 1)]
        code, result = self.pack(items)
        self.assertEqual(code, 2)
        self.assertTrue(any("art-ep03@r1" in e and "--allow-unverified" in e for e in result["errors"]), result["errors"])
        code, result = self.pack(items, "author", 20000, None, "--allow-unverified")
        self.assertEqual(code, 0, result)
        self.assertEqual(self.written(result)["unknowns"], ["服务端指纹未核验：art-ep03@r1"])

    def test_dry_run_checks_everything_and_writes_nothing(self):
        code, result = self.pack(None, "author", 20000, None, "--dry-run")
        self.assertEqual(code, 0, result)
        self.assertEqual((result["written"], result["dry_run"]), (False, True))
        self.assertEqual(len(result["items"]), 5)
        self.assertEqual(self.snapshots(), [])
        code, result = self.pack(None, "author", 100, None, "--dry-run")
        self.assertEqual(code, 2)
        self.assertEqual(self.snapshots(), [])

    def test_range_out_of_bounds_is_an_input_error_naming_ref_and_length(self):
        code, result = self.pack([cache_ref("art-ep01", 1, ref={"range": {"start": 0, "end": len(EP1) + 1}})])
        self.assertEqual(code, 1)
        self.assertIn("art-ep01@r1", result["error"])
        self.assertIn(f"length {len(EP1)}", result["error"])
        code, result = self.pack([cache_ref("art-ep01", 1, ref={"range": {"start": 9, "end": 3}})])
        self.assertEqual(code, 1)
        self.assertEqual(self.snapshots(), [])

    def test_usage_is_filtered_by_role(self):
        for card_id, blocked, allowed in (("kc-eval", "author", "evaluation"), ("kc-cmp", "author", "similarity_review"),
                                          ("kc-cmp", "reader_effect", "evaluation")):
            with self.subTest(card=card_id, role=blocked):
                code, result = self.pack([card_ref(card_id)], role=blocked)
                self.assertEqual(code, 2)
                self.assertTrue(any(card_id in e and "selection.items[0]" in e for e in result["errors"]), result["errors"])
                code, result = self.pack([card_ref(card_id)], role=allowed)
                self.assertEqual(code, 0, result)
        code, result = self.pack([cache_ref("art-ep01", 1, usage="evaluation_only")], role="author")
        self.assertEqual(code, 2)

    def test_empty_selection_gives_a_task_only_snapshot(self):
        code, result = self.pack([])
        self.assertEqual(code, 0, result)
        snapshot = self.written(result)
        self.assertEqual([item["partition"] for item in snapshot["items"]], ["task"])
        task_bytes = self.task.read_bytes()
        self.assertEqual(snapshot["items"][0]["ref"], {"kind": "local_file", "id": "task:task-ep21-draft",
                                                       "revision": sha(task_bytes), "sha256": sha(task_bytes)})
        self.assertEqual((snapshot["completeness"], snapshot["omitted"]), ("complete", []))
        self.assertEqual(snapshot["projectBase"], {"remoteProjectId": "proj-demo-0001", "sourceSnapshotId": None})

    def test_written_snapshot_passes_contract_check_and_sidecar_matches(self):
        code, result = self.pack(selection=self.selection(self.default_items(), sourceSnapshotId="wsnap-77"))
        self.assertEqual(code, 0, result)
        path = Path(result["snapshot_path"])
        self.assertEqual(path.name, result["snapshot_id"] + ".json")
        self.assertEqual(self.written(result)["projectBase"]["sourceSnapshotId"], "wsnap-77")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(Path(result["sha256_path"]).read_text(encoding="utf-8"), f"{digest}  {path.name}\n")
        self.assertEqual(result["snapshot_sha256"], "sha256:" + digest)
        check = subprocess.run([sys.executable, "-B", str(TOOL), "contract-check", "context-snapshot", str(path)], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertEqual(self.snapshots(), [path.name, result["snapshot_id"] + ".sha256"])

    def test_existing_snapshot_is_never_overwritten(self):
        code, result = self.pack()
        path = Path(result["snapshot_path"])
        path.write_bytes(path.read_bytes() + b" ")
        tampered = path.read_bytes()
        code, result = self.pack()
        self.assertEqual(code, 2)
        self.assertIn("never overwritten", result["errors"][0])
        self.assertEqual(path.read_bytes(), tampered)

    def test_manifest_path_outside_cache_is_refused(self):
        secret = self.project / "planning" / "secret.md"
        secret.parent.mkdir()
        secret.write_text("作者私下笔记", encoding="utf-8")
        manifest_path = self.project / ".drama/cache/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = copy.deepcopy(manifest["entries"][0])
        entry.update(artifactId="art-escape", path=".drama/cache/../../planning/secret.md", sha256=sha(secret.read_bytes()))
        entry["serverFingerprint"] = entry["sha256"]
        manifest["entries"].append(entry)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        code, result = self.pack([cache_ref("art-escape", 1)])
        self.assertEqual(code, 2)
        self.assertTrue(any("outside .drama/cache/" in e for e in result["errors"]), result["errors"])

    def test_input_errors_exit_1(self):
        cases = [[{"ref": {"kind": "local_file", "id": "notes.md", "revision": 1}, "partition": "project_facts", "required": True, "reason": "x"}],
                 [cache_ref("art-ep01", None)],
                 [cache_ref("art-ep01", 1, partition="task")],
                 [card_ref("kc-cost", usage="evaluation_only")]]
        for items in cases:
            with self.subTest(items=items):
                code, result = self.pack(items)
                self.assertEqual(code, 1, result)
                self.assertIn("selection", result["error"])
        task = json.loads(self.task.read_text(encoding="utf-8"))
        task["workstation"] = None
        self.task.write_text(json.dumps(task), encoding="utf-8")
        code, result = self.pack([])
        self.assertEqual(code, 1)
        self.assertIn("workstation", result["error"])

    def test_doctor_still_reports_offline_and_lists_selection(self):
        run = subprocess.run([sys.executable, "-B", str(TOOL), "doctor"], capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertEqual((result["network_used"], result["models_called"]), (False, False))
        self.assertIn("selection", result["contracts"])
        code, packed = self.pack()
        self.assertEqual((packed["network_used"], packed["models_called"], packed["remote_verified"]), (False, False, False))


if __name__ == "__main__":
    unittest.main()
