import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
FIXTURES = ROOT / "tests/fixtures/mcp-synthetic"
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
sys.path.insert(0, str(ROOT / "skills/drama-studio/scripts"))
sys.dont_write_bytecode = True
from checks import project_status, receipt  # noqa: E402
from checks.contract_check import check_contract  # noqa: E402

ART1 = "9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41"
CHUNKS = [f"08-read-chunk-{i}.response.json" for i in range(1, 5)]
FILLER = "sha256:" + "a" * 64
TASK_ITEM = {"ref": {"kind": "local_file", "id": "task:task-ep2-draft", "revision": FILLER, "sha256": FILLER}, "partition": "task",
             "required": True, "usage": "project_text", "chars": 5, "sha256": FILLER, "reason": "任务定义"}


def entry(artifact, slot, revision, source="record"):
    """A hand-written cache manifest v0 entry (#15); source None leaves slotSource out, as entries written before #10 do."""
    item = {"path": f".drama/cache/{artifact}@r{revision}.md", "artifactId": artifact, "slot": slot, "kind": "episode_draft",
            "episodeRef": slot, "revision": revision, "sha256": FILLER, "serverFingerprint": FILLER, "verified": True,
            "operation": "read_story_artifact", "readAt": "2026-10-01T08:00:00+08:00"}
    return item if source is None else dict(item, slotSource=source)


def ref(artifact, revision, required=True):
    return {"ref": {"kind": "remote_artifact", "id": artifact, "revision": revision}, "partition": "project_facts",
            "required": required, "usage": "project_text", "chars": 10, "reason": "测试材料"}


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "demo"
        run = subprocess.run([sys.executable, "-B", str(TOOL), "init-project", str(self.project), "--title", "演示"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.drama = self.project / ".drama"

    def manifest(self, *entries):
        (self.drama / "cache").mkdir(exist_ok=True)
        (self.drama / "cache/manifest.json").write_text(json.dumps(
            {"schemaVersion": "drama-studio/cache-manifest/v0", "entries": list(entries)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def snapshot(self, snapshot_id, items, sidecar=True, omitted=(), completeness="complete"):
        doc = {"schemaVersion": "drama-studio/context-snapshot/v0", "snapshotId": snapshot_id,
               "createdFor": {"taskId": "task-ep2-draft", "workstation": "C5", "role": "author"},
               "projectBase": {"remoteProjectId": "proj-demo-0001", "sourceSnapshotId": None},
               "budget": {"unit": "chars", "limit": 20000}, "items": [TASK_ITEM, *items], "omitted": list(omitted),
               "completeness": completeness}
        return self.write_snapshot(snapshot_id, doc, sidecar)

    def write_snapshot(self, name, doc, sidecar=True):
        folder = self.drama / "snapshots"
        folder.mkdir(exist_ok=True)
        path = folder / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if sidecar:  # the format context-pack writes
            (folder / f"{name}.sha256").write_text(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}.json\n", encoding="utf-8")
        return path

    def run_handoff(self, run_id, snapshot_id, **changes):
        doc = json.loads((EXAMPLES / "run-handoff.json").read_text(encoding="utf-8"))
        doc.update(runId=run_id, contextSnapshotId=snapshot_id, **changes)
        folder = self.drama / "runs"
        folder.mkdir(exist_ok=True)
        path = folder / f"{run_id}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def impact(self, **target):
        result = project_status.run_impact(str(self.project), **target)
        return result, {item["snapshotId"]: item for item in result["snapshots"]}, {item["runId"]: item for item in result["runs"]}

    def ac4_fixture(self):
        """One unknown save receipt (real receipt record on the synthetic fixture) and one run whose nextAction is set."""
        receipt.record_receipt(str(self.project), str(FIXTURES / "05-unknown.response.json"), "save_story_artifact", "d1-save-3",
                               str(FIXTURES / "05-unknown.input.json"))
        self.snapshot("ctx-a", [])
        self.run_handoff("run-ep21-c5-1", "ctx-a")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)

    def ac1_fixture(self):
        """art-1 = slot ep-1 r1, art-2 = slot ep-1 r2; snapshot A pins art-1, snapshot B pins nothing in slot ep-1."""
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-9", "ep-0", 1))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.snapshot("ctx-b", [ref("art-9", 1)])


class ImpactTests(ProjectCase):
    def test_ac1_slot_and_revision_mark_snapshot_a_stale_and_b_current(self):
        self.ac1_fixture()
        result, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()}, {"ctx-a": "stale", "ctx-b": "current"})
        self.assertEqual(result["target"], {"slot": "ep-1", "revision": 2, "resolvedFrom": "--slot/--revision"})
        reason = snapshots["ctx-a"]["reasons"][0]
        self.assertEqual((reason["ref"], reason["status"]), ("items[1] art-1@r1", "stale"))
        self.assertIn("ep-1", reason["reason"])
        self.assertEqual((snapshots["ctx-b"]["reasons"], snapshots["ctx-a"]["path"]), ([], ".drama/snapshots/ctx-a.json"))
        self.assertEqual(result["summary"]["snapshots"], {"stale": 1, "unknown": 0, "current": 1})

    def test_ac1_artifact_resolves_through_the_manifest_to_the_same_result(self):
        self.ac1_fixture()
        by_slot, by_artifact = self.impact(slot="ep-1", revision=2)[0], self.impact(artifact="art-2")[0]
        self.assertEqual(by_artifact["target"], {"slot": "ep-1", "revision": 2, "resolvedFrom": "--artifact art-2"})
        for key in ("snapshots", "runs", "summary"):
            self.assertEqual(by_artifact[key], by_slot[key])

    def test_ac2_run_inherits_the_state_of_its_snapshot(self):
        self.ac1_fixture()
        self.run_handoff("run-a", "ctx-a")
        self.run_handoff("run-b", "ctx-b")
        self.run_handoff("run-lost", "ctx-missing")
        self.run_handoff("run-bad", "ctx-b", workstation="C9")
        (self.drama / "runs/run-broken.json").write_text("{", encoding="utf-8")
        result, _, runs = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in runs.items()},
                         {"run-a": "stale", "run-b": "current", "run-lost": "unknown", "run-bad": "unknown", "run-broken": "unknown"})
        self.assertEqual(runs["run-a"]["contextSnapshotId"], "ctx-a")
        self.assertEqual(runs["run-a"]["reasons"][0]["ref"], "context_snapshot ctx-a")
        self.assertIn("items[1] art-1@r1", [reason["ref"] for reason in runs["run-a"]["reasons"]])
        self.assertIn("ctx-missing", runs["run-lost"]["reasons"][0]["ref"])
        for run_id in ("run-lost", "run-bad", "run-broken"):
            self.assertIn("扩大阅读", runs[run_id]["suggestion"])
        self.assertEqual(result["summary"]["runs"], {"stale": 1, "unknown": 3, "current": 1})

    def test_ac3_reference_without_a_revision_is_unknown_and_never_current(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2))
        self.snapshot("ctx-null", [ref("art-1", None, required=False)])
        self.snapshot("ctx-text", [ref("art-1", "1", required=False)])
        absent = json.loads(self.snapshot("ctx-absent", [ref("art-1", 1)]).read_text(encoding="utf-8"))
        del absent["items"][1]["ref"]["revision"]  # not a valid snapshot any more; still must not read as current
        self.write_snapshot("ctx-absent", absent)
        self.run_handoff("run-null", "ctx-null")
        for target in ({"slot": "ep-1", "revision": 2}, {"artifact": "art-2"}, {"slot": "ep-7", "revision": 1}):
            result, snapshots, runs = self.impact(**target)
            for item in (*snapshots.values(), runs["run-null"]):
                with self.subTest(target=target, item=item.get("snapshotId") or item["runId"]):
                    self.assertEqual(item["status"], "unknown")
                    self.assertNotIn("current", json.dumps(item, ensure_ascii=False))
                    self.assertIn("扩大阅读", item["suggestion"])
                    self.assertTrue(item["reasons"])
            self.assertIn("revision", snapshots["ctx-null"]["reasons"][0]["reason"])
            self.assertIn("art-1", snapshots["ctx-null"]["reasons"][0]["ref"])
            self.assertEqual(result["summary"]["snapshots"]["current"], 0)

    def test_judge_ref_defaults_to_unknown(self):
        entries = [entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-h", "ep-1", 1, "host"),
                   entry("art-legacy", "ep-1", 1, None), entry("art-split", "ep-1", 1), entry("art-split", "ep-2", 1),
                   entry("art-twice", "ep-1", 1), entry("art-twice", "ep-1", 2), entry("art-odd", "ep-1", True), entry("art-noslot", "", 1)]
        cases = {"revision key absent": {"kind": "remote_artifact", "id": "art-1"},
                 "revision null": {"kind": "remote_artifact", "id": "art-1", "revision": None},
                 "revision is a string": {"kind": "remote_artifact", "id": "art-1", "revision": "1"},
                 "revision is a bool": {"kind": "remote_artifact", "id": "art-1", "revision": True},
                 "revision differs from the manifest": {"kind": "remote_artifact", "id": "art-1", "revision": 3},
                 "artifact not in the manifest": {"kind": "remote_artifact", "id": "art-404", "revision": 1},
                 "slot declared by the host": {"kind": "remote_artifact", "id": "art-h", "revision": 1},
                 "entry without slotSource": {"kind": "remote_artifact", "id": "art-legacy", "revision": 1},
                 "two slots for one artifact": {"kind": "remote_artifact", "id": "art-split", "revision": 1},
                 "two revisions for one artifact": {"kind": "remote_artifact", "id": "art-twice", "revision": 1},
                 "manifest revision is not an integer": {"kind": "remote_artifact", "id": "art-odd", "revision": 1},
                 "manifest slot is empty": {"kind": "remote_artifact", "id": "art-noslot", "revision": 1},
                 "not an object": "art-1@r1"}
        for label, reference in cases.items():
            with self.subTest(label):
                status, why = project_status.judge_ref(reference, entries, "ep-1", 2)
                self.assertEqual(status, "unknown")
                self.assertTrue(why)
        self.assertEqual(project_status.judge_ref(cases["revision differs from the manifest"] | {"revision": 1}, entries, "ep-1", 2)[0], "stale")
        for label, reference, target in [("same slot, same revision", ("art-2", 2), ("ep-1", 2)), ("same slot, newer than target", ("art-2", 2), ("ep-1", 1)),
                                         ("another slot", ("art-1", 1), ("ep-9", 5))]:
            with self.subTest(label):
                self.assertEqual(project_status.judge_ref({"kind": "remote_artifact", "id": reference[0], "revision": reference[1]}, entries, *target),
                                 ("current", None))

    def test_unknown_manifest_lookups_reach_the_snapshot_with_reasons(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-h", "ep-1", 1, "host"), entry("art-legacy", "ep-1", 1, None))
        self.snapshot("ctx-404", [ref("art-404", 1)])
        self.snapshot("ctx-host", [ref("art-h", 1)])
        self.snapshot("ctx-legacy", [ref("art-legacy", 1)])
        self.snapshot("ctx-mixed", [ref("art-404", 1), ref("art-1", 1)])
        _, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()},
                         {"ctx-404": "unknown", "ctx-host": "unknown", "ctx-legacy": "unknown", "ctx-mixed": "stale"})
        self.assertIn("manifest", snapshots["ctx-404"]["reasons"][0]["reason"])
        self.assertIn("slotSource", snapshots["ctx-host"]["reasons"][0]["reason"])
        self.assertEqual([reason["status"] for reason in snapshots["ctx-mixed"]["reasons"]], ["unknown", "stale"])
        self.assertNotIn("suggestion", snapshots["ctx-mixed"])

    def test_strongest_slot_source_of_an_artifact_is_trusted(self):
        self.manifest(entry("art-1", "ep-1", 1, "host"), entry("art-1", "ep-1", 1, "receipt"))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.assertEqual(self.impact(slot="ep-1", revision=2)[1]["ctx-a"]["status"], "stale")

    def test_only_packed_remote_artifacts_count_as_dependencies(self):
        self.manifest(entry("art-1", "ep-1", 1))
        card = {"ref": {"kind": "knowledge_card", "id": "art-1", "revision": 1}, "partition": "knowledge", "required": False,
                "usage": "creative_reference", "chars": 3, "reason": "同名知识卡"}
        left_out = {"ref": {"kind": "remote_artifact", "id": "art-1", "revision": 1}, "required": False, "reason": "not_relevant"}
        self.snapshot("ctx-omitted", [card], omitted=[left_out])
        self.snapshot("ctx-task-only", [])
        _, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()}, {"ctx-omitted": "current", "ctx-task-only": "current"})

    def test_damaged_snapshot_is_unknown_whatever_it_references(self):
        self.manifest(entry("art-9", "ep-0", 1))
        self.snapshot("ctx-no-sidecar", [ref("art-9", 1)], sidecar=False)
        edited = self.snapshot("ctx-edited", [ref("art-9", 1)])
        edited.write_bytes(edited.read_bytes() + b" ")
        self.snapshot("ctx-over-budget", [dict(ref("art-9", 1), chars=99999)])
        renamed = self.snapshot("ctx-original", [ref("art-9", 1)])
        self.write_snapshot("ctx-renamed", json.loads(renamed.read_text(encoding="utf-8")))
        renamed.unlink()
        (self.drama / "snapshots/ctx-original.sha256").unlink()
        (self.drama / "snapshots/ctx-broken.json").write_text("{", encoding="utf-8")
        _, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual(sorted(snapshots), ["ctx-broken", "ctx-edited", "ctx-no-sidecar", "ctx-over-budget", "ctx-renamed"])
        for key, needle in [("ctx-no-sidecar", ".sha256"), ("ctx-edited", ".sha256"), ("ctx-over-budget", "contract-check"),
                            ("ctx-renamed", "snapshotId"), ("ctx-broken", "ctx-broken.json")]:
            with self.subTest(key):
                self.assertEqual(snapshots[key]["status"], "unknown")
                self.assertIn(needle, " ".join(reason["reason"] for reason in snapshots[key]["reasons"]))
                self.assertIn("扩大阅读", snapshots[key]["suggestion"])

    def test_ac3b_host_declared_slot_is_unknown_until_recached_with_the_get_response(self):
        chunks = [str(FIXTURES / name) for name in CHUNKS]
        cached = receipt.cache(str(self.project), chunks, slot="ep-03-outline", kind="episode_outline", episode_ref="ep-03")
        self.assertEqual((cached["passed"], cached["entry"]["slotSource"]), (True, "host"))
        self.snapshot("ctx-ep3", [ref(ART1, 1)])
        _, snapshots, _ = self.impact(slot="ep-03-outline", revision=2)
        self.assertEqual(snapshots["ctx-ep3"]["status"], "unknown")
        self.assertIn("slotSource", snapshots["ctx-ep3"]["reasons"][0]["reason"])
        with self.assertRaisesRegex(ValueError, "get_story_artifact"):
            self.impact(artifact=ART1)
        recached = receipt.cache(str(self.project), chunks + [str(FIXTURES / "03-get.response.json")])
        self.assertEqual((recached["manifestAppended"], recached["entry"]["slotSource"]), (True, "record"))
        self.assertEqual(self.impact(slot="ep-03-outline", revision=2)[1]["ctx-ep3"]["status"], "stale")
        result, snapshots, _ = self.impact(artifact=ART1)
        self.assertEqual((result["target"]["slot"], result["target"]["revision"], snapshots["ctx-ep3"]["status"]), ("ep-03-outline", 1, "current"))

    def test_target_arguments_are_checked(self):
        self.ac1_fixture()
        self.manifest(entry("art-1", "ep-1", 1), entry("art-h", "ep-1", 2, "host"), entry("art-legacy", "ep-1", 3, None))
        for label, target in [("nothing", {}), ("slot only", {"slot": "ep-1"}), ("revision only", {"revision": 2}),
                              ("both forms", {"slot": "ep-1", "revision": 2, "artifact": "art-1"}), ("artifact and slot", {"slot": "ep-1", "artifact": "art-1"}),
                              ("revision below 1", {"slot": "ep-1", "revision": 0}), ("unknown artifact", {"artifact": "art-404"}),
                              ("host-declared artifact", {"artifact": "art-h"}), ("artifact without slotSource", {"artifact": "art-legacy"})]:
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    self.impact(**target)

    def test_unreadable_manifest_is_an_error_and_a_missing_one_judges_nothing_current(self):
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.assertEqual(self.impact(slot="ep-1", revision=2)[1]["ctx-a"]["status"], "unknown")
        (self.drama / "cache").mkdir()
        for content in ("[]", "{", json.dumps({"schemaVersion": "other", "entries": []})):
            with self.subTest(content):
                (self.drama / "cache/manifest.json").write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "manifest"):
                    self.impact(slot="ep-1", revision=2)

    def test_output_states_what_it_does_not_prove(self):
        self.ac1_fixture()
        result = self.impact(slot="ep-1", revision=2)[0]
        self.assertEqual((result["ok"], result["command"], result["read_only"], result["remote_verified"]), (True, "impact", True, False))
        self.assertIn("隐含依赖未评估", result["note"])
        self.assertNotIn("passed", result)
        self.assertEqual(check_contract("context-snapshot", json.loads((self.drama / "snapshots/ctx-a.json").read_text(encoding="utf-8"))), [])
        self.assertEqual(result["project"], str(self.project))


class StatusTests(ProjectCase):
    def record(self, response, operation, request_id, input_name, reconciles=None):
        return receipt.record_receipt(str(self.project), str(FIXTURES / response), operation, request_id, str(FIXTURES / input_name), reconciles)

    def unknown_save(self):
        return self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")

    def status(self):
        result = project_status.run_status(str(self.project))
        return result, project_status.render_status(result).splitlines()

    def test_ac4_reports_the_unknown_receipt_and_the_run_and_leads_with_reconciliation(self):
        self.unknown_save()
        self.snapshot("ctx-a", [])
        self.run_handoff("run-ep21-c5-1", "ctx-a")
        result, lines = self.status()
        self.assertEqual([item["requestId"] for item in result["receipts"]["pending"]], ["d1-save-3"])
        latest = result["runs"]["latest"]
        self.assertEqual((latest["runId"], latest["nextAction"], latest["unfinished"], latest["contextSnapshotId"]),
                         ("run-ep21-c5-1", "请用户决定是否接受 C4 变更提案", ["C4 变更待用户决定"], "ctx-a"))
        self.assertEqual((latest["status"], latest["workstation"], latest["path"]),
                         ({"run": "finished", "goal": "partially_met"}, "C5", ".drama/runs/run-ep21-c5-1.json"))
        self.assertEqual((result["runs"]["count"], result["runs"]["recencyBasis"]), (1, "file_mtime"))
        self.assertEqual(result["snapshots"], [{"snapshotId": "ctx-a", "path": ".drama/snapshots/ctx-a.json", "intact": True, "completeness": "complete",
                                                "createdFor": {"taskId": "task-ep2-draft", "workstation": "C5", "role": "author"}, "problems": []}])
        self.assertEqual((result["nextAction"]["basis"], result["nextAction"]["from"]), ("unknown_receipt", ".drama/receipts/d1-save-3.json"))
        self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"], latest["stalenessReasons"]), ("no_newer_revision_cached", [], []))
        self.assertTrue(lines[0].startswith("下一步：对账"), lines[0])
        for needle in ("d1-save-3", "ep-03-outline", "--reconciles d1-save-3", "不要换新 requestId"):
            self.assertIn(needle, lines[0])
        text = "\n".join(lines)
        for needle in ("请用户决定是否接受 C4 变更提案", "C4 变更待用户决定", "run-ep21-c5-1", "ctx-a", "list_story_artifacts", "file_mtime"):
            self.assertIn(needle, text)
        self.assertEqual((result["ok"], result["command"], result["read_only"], result["remote_verified"], result["adoption_verified"]),
                         (True, "status", True, False, False))
        self.assertNotIn("passed", result)

    def test_next_action_priority_is_receipts_then_invalid_records_then_latest_run_then_a_hint(self):
        result, lines = self.status()
        self.assertEqual((result["nextAction"]["basis"], result["runs"]["latest"], result["runs"]["count"]), ("no_runs", None, 0))
        self.assertTrue(lines[0].startswith("下一步：尚无运行记录"), lines[0])
        self.snapshot("ctx-a", [])
        self.run_handoff("run-1", "ctx-a")
        result, lines = self.status()
        self.assertEqual((result["nextAction"]["basis"], result["nextAction"]["from"]), ("latest_run", ".drama/runs/run-1.json"))
        self.assertEqual(lines[0], "下一步：请用户决定是否接受 C4 变更提案")
        (self.drama / "runs/run-broken.json").write_text("{", encoding="utf-8")
        result, lines = self.status()
        self.assertEqual((result["nextAction"]["basis"], result["nextAction"]["from"]), ("invalid_record", ".drama/runs/run-broken.json"))
        self.assertTrue(lines[0].startswith("下一步：处理无效或损坏的记录"), lines[0])
        self.assertEqual([(item["kind"], item["path"]) for item in result["invalid"]], [("run", ".drama/runs/run-broken.json")])
        self.assertEqual(result["runs"]["latest"]["runId"], "run-1")
        self.unknown_save()
        result, lines = self.status()
        self.assertEqual(result["nextAction"]["basis"], "unknown_receipt")
        self.assertTrue(lines[0].startswith("下一步：对账"), lines[0])
        self.assertIn("run-broken.json", "\n".join(lines))

    def test_reconciled_and_read_only_unknowns_do_not_lead(self):
        self.unknown_save()
        self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        lost = Path(self.temp.name) / "read-lost.input.json"
        lost.write_text(json.dumps({"project_id": "2f70c1e9fad74f35ae27f", "artifact_id": ART1}), encoding="utf-8")
        receipt.record_receipt(str(self.project), str(Path(self.temp.name) / "missing.json"), "read_story_artifact", "read-lost", str(lost))
        result, lines = self.status()
        self.assertEqual((result["receipts"]["pending"], result["receipts"]["resolved_verified"]), ([], ["d1-save-3"]))
        self.assertEqual([item["requestId"] for item in result["receipts"]["read_only_unknown"]], ["read-lost"])
        self.assertEqual(result["nextAction"]["basis"], "no_runs")
        self.assertIn("read-lost", "\n".join(lines))

    def stale_fixture(self, *extra):
        """The latest run's snapshot pins art-1 (slot ep-1 r1) while the cache already holds a trusted r2 of that slot."""
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2, "receipt"), entry("art-9", "ep-0", 1), *extra)
        self.snapshot("ctx-a", [ref("art-9", 1), ref("art-1", 1)])
        self.run_handoff("run-a", "ctx-a")

    def test_latest_run_pinning_an_older_revision_leads_with_the_impact_command(self):
        self.stale_fixture()
        result, lines = self.status()
        command = f"drama_tools.py impact {self.project} --slot ep-1 --revision 2"
        latest = result["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["possiblyStale"]), ("newer_revision_cached", True))
        self.assertEqual(latest["newerRevisions"], [{"ref": "items[2] art-1@r1", "slot": "ep-1", "pinnedRevision": 1,
                                                     "newestTrustedRevision": 2, "impactCommand": command}])
        self.assertEqual(latest["stalenessReasons"], [])
        action = result["nextAction"]
        self.assertEqual((action["basis"], action["from"], action["impactCommand"], action["recordedNextAction"]),
                         ("stale_run", ".drama/runs/run-a.json", command, "请用户决定是否接受 C4 变更提案"))
        self.assertTrue(lines[0].startswith(f"下一步：先运行 {command}"), lines[0])
        for needle in ("run-a", "slot ep-1", "r1", "r2", "再决定"):
            self.assertIn(needle, lines[0])
        self.assertNotIn("请用户决定是否接受 C4 变更提案", lines[0])
        self.assertEqual(lines[1], "该运行按旧修订 r1 的上下文记录的下一步（先看 impact 结果，不要直接照做）：请用户决定是否接受 C4 变更提案")
        self.assertIn("可能已失效", "\n".join(lines[2:]))
        self.assertEqual(json.loads(self.cli(*command.split()[1:]).stdout)["runs"][0]["status"], "stale")

    def test_possibly_stale_run_yields_to_unknown_receipts_and_invalid_records(self):
        self.stale_fixture()
        (self.drama / "runs/run-broken.json").write_text("{", encoding="utf-8")
        result, lines = self.status()
        self.assertEqual((result["nextAction"]["basis"], result["runs"]["latest"]["possiblyStale"]), ("invalid_record", True))
        self.unknown_save()
        result, lines = self.status()
        self.assertEqual(result["nextAction"]["basis"], "unknown_receipt")
        self.assertIn("可能已失效", "\n".join(lines))
        self.assertIn("--slot ep-1 --revision 2", "\n".join(lines))

    def test_no_newer_cached_revision_claims_only_what_the_local_cache_shows(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-9", "ep-0", 1))
        self.snapshot("ctx-a", [ref("art-2", 2), ref("art-9", 1)])
        self.run_handoff("run-a", "ctx-a")
        self.snapshot("ctx-task-only", [])
        self.run_handoff("run-b", "ctx-task-only", status={"run": "running", "goal": "not_assessed"})
        os.utime(self.drama / "runs/run-b.json", (1_000, 1_000))
        result, lines = self.status()
        for run in (result["runs"]["latest"], result["runs"]["open"][-1]):
            self.assertEqual((run["stalenessCheck"], run["newerRevisions"], run["stalenessReasons"]), ("no_newer_revision_cached", [], []))
            self.assertNotIn("possiblyStale", run)
        self.assertEqual((result["nextAction"]["basis"], lines[0]), ("latest_run", "下一步：请用户决定是否接受 C4 变更提案"))
        text = "\n".join(lines)
        self.assertEqual(text.count("本地缓存中没有它所引用 slot 的更新修订；这不说明远端没有"), 2)
        self.assertIn("本地缓存", result["note"])

    def test_unassessable_staleness_is_reported_as_unknown_and_never_as_fresh_or_stale(self):
        cases = {"host-declared slot": lambda: (self.manifest(entry("art-1", "ep-1", 1, "host"), entry("art-2", "ep-1", 2)), [ref("art-1", 1)]),
                 "entry without slotSource": lambda: (self.manifest(entry("art-1", "ep-1", 1, None)), [ref("art-1", 1)]),
                 "no manifest": lambda: (None, [ref("art-1", 1)]),
                 "artifact not in the manifest": lambda: (self.manifest(entry("art-2", "ep-1", 2)), [ref("art-1", 1)]),
                 "reference without a revision": lambda: (self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2)), [ref("art-1", None, required=False)]),
                 "untrusted newer entry in the slot": lambda: (self.manifest(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3, "host")), [ref("art-1", 1)]),
                 "unreadable manifest": lambda: (self.manifest(entry("art-1", "ep-1", 1)), [ref("art-1", 1)])}
        for label, build in cases.items():
            with self.subTest(label):
                if (self.drama / "cache/manifest.json").exists():
                    (self.drama / "cache/manifest.json").unlink()
                _, items = build()
                self.snapshot("ctx-a", items)
                self.run_handoff("run-a", "ctx-a")
                if label == "unreadable manifest":
                    (self.drama / "cache/manifest.json").write_text("{", encoding="utf-8")
                result, lines = self.status()
                latest = result["runs"]["latest"]
                self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"]), ("unknown", []))
                self.assertTrue(latest["stalenessReasons"])
                self.assertNotIn("possiblyStale", latest)
                self.assertEqual((result["nextAction"]["basis"], lines[0]), ("latest_run", "下一步：请用户决定是否接受 C4 变更提案"))
                text = "\n".join(lines)
                self.assertEqual(text.count("无法判断是否失效"), 1)
                for word in ("可能已失效", "没有它所引用 slot 的更新修订"):
                    self.assertNotIn(word, text)

    def test_run_without_a_usable_snapshot_has_unknown_staleness(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2))
        edited = self.snapshot("ctx-edited", [ref("art-1", 1)])
        self.run_handoff("run-lost", "ctx-missing")
        self.run_handoff("run-edited", "ctx-edited", status={"run": "running", "goal": "not_assessed"})
        edited.write_bytes(edited.read_bytes() + b" ")
        result, _ = self.status()
        runs = {run["runId"]: run for run in [result["runs"]["latest"], *result["runs"]["open"]]}
        self.assertEqual({key: run["stalenessCheck"] for key, run in runs.items()}, {"run-lost": "unknown", "run-edited": "unknown"})
        self.assertIn("ctx-missing", runs["run-lost"]["stalenessReasons"][0])
        self.assertIn(".sha256", runs["run-edited"]["stalenessReasons"][0])

    def test_mixed_references_report_the_newer_revision_and_the_unresolved_one(self):
        self.stale_fixture(entry("art-h", "ep-5", 1, "host"), entry("art-7", "ep-7", 1), entry("art-8", "ep-7", 4))
        self.snapshot("ctx-a", [ref("art-1", 1), ref("art-h", 1), ref("art-7", 1)])
        latest = self.status()[0]["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["possiblyStale"]), ("newer_revision_cached", True))
        self.assertEqual([(item["slot"], item["pinnedRevision"], item["newestTrustedRevision"]) for item in latest["newerRevisions"]],
                         [("ep-1", 1, 2), ("ep-7", 1, 4)])
        self.assertEqual(len(latest["stalenessReasons"]), 1)
        self.assertIn("art-h", latest["stalenessReasons"][0])

    def test_impact_command_quotes_paths_and_slots_with_spaces(self):
        self.manifest(entry("art-1", "ep 1", 1), entry("art-2", "ep 1", 2))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.run_handoff("run-a", "ctx-a")
        spaced = self.project.with_name("my drama")
        self.project.rename(spaced)
        command = project_status.run_status(str(spaced))["runs"]["latest"]["newerRevisions"][0]["impactCommand"]
        self.assertEqual(command, f"drama_tools.py impact '{spaced}' --slot 'ep 1' --revision 2")
        spaced.rename(self.project)

    def test_missing_slot_revision_or_completeness_is_not_printed_as_none(self):
        bare = Path(self.temp.name) / "bare.input.json"
        bare.write_text(json.dumps({"project_id": "2f70c1e9fad74f35ae27f", "input_snapshot_id": FILLER, "request_id": "lost-1"}), encoding="utf-8")
        receipt.record_receipt(str(self.project), str(Path(self.temp.name) / "missing.json"), "save_story_artifact", "lost-1", str(bare))
        (self.drama / "snapshots").mkdir()
        (self.drama / "snapshots/ctx-broken.json").write_text("{", encoding="utf-8")
        result, lines = self.status()
        self.assertEqual((result["receipts"]["pending"][0]["slot"], result["snapshots"][0]["completeness"]), (None, None))
        self.assertTrue(lines[0].startswith("下一步：对账结果未知的保存回执 lost-1："), lines[0])
        self.assertNotIn("None", "\n".join(lines))
        self.assertIn("completeness: 未知", "\n".join(lines))

    def test_invalid_receipts_and_damaged_snapshots_are_invalid_records(self):
        (self.drama / "receipts").mkdir()
        (self.drama / "receipts/broken.json").write_text("{", encoding="utf-8")
        edited = self.snapshot("ctx-edited", [])
        edited.write_bytes(edited.read_bytes() + b" ")
        self.snapshot("ctx-no-sidecar", [], sidecar=False)
        self.snapshot("ctx-ok", [ref("art-9", 1)], completeness="incomplete",
                      omitted=[{"ref": {"kind": "remote_artifact", "id": "art-8", "revision": 1}, "required": True, "reason": "missing"}])
        self.run_handoff("run-1", "ctx-ok")
        result, lines = self.status()
        self.assertEqual([(item["kind"], item["path"]) for item in result["invalid"]],
                         [("receipt", ".drama/receipts/broken.json"), ("snapshot", ".drama/snapshots/ctx-edited.json"),
                          ("snapshot", ".drama/snapshots/ctx-no-sidecar.json")])
        by_id = {item["snapshotId"]: item for item in result["snapshots"]}
        self.assertEqual({key: (item["intact"], item["completeness"]) for key, item in by_id.items()},
                         {"ctx-edited": (False, "complete"), "ctx-no-sidecar": (False, "complete"), "ctx-ok": (True, "incomplete")})
        self.assertIn(".sha256", by_id["ctx-edited"]["problems"][0])
        self.assertEqual((result["nextAction"]["basis"], result["nextAction"]["from"]), ("invalid_record", ".drama/receipts/broken.json"))
        text = "\n".join(lines)
        for needle in ("ctx-edited：有问题", "ctx-ok：完好", "incomplete", "共 3 项"):
            self.assertIn(needle, text)

    def test_snapshot_integrity_covers_contract_file_name_and_unreadable_files(self):
        self.snapshot("ctx-over-budget", [dict(ref("art-9", 1), chars=99999)])
        self.write_snapshot("ctx-renamed", json.loads(self.snapshot("ctx-original", []).read_text(encoding="utf-8")))
        (self.drama / "snapshots/ctx-broken.json").write_text("{", encoding="utf-8")
        by_id = {item["snapshotId"]: item for item in self.status()[0]["snapshots"]}
        self.assertTrue(by_id["ctx-original"]["intact"])
        for key, needle, completeness in [("ctx-over-budget", "contract-check", "complete"), ("ctx-renamed", "snapshotId", "complete"),
                                          ("ctx-broken", "ctx-broken.json", None)]:
            with self.subTest(key):
                self.assertEqual((by_id[key]["intact"], by_id[key]["completeness"]), (False, completeness))
                self.assertIn(needle, " ".join(by_id[key]["problems"]))

    def test_latest_run_is_by_file_mtime_and_every_open_run_is_listed(self):
        self.snapshot("ctx-a", [])
        stamps = {"run-z-oldest": 1_000, "run-a-newest": 5_000, "run-m-interrupted": 3_000, "run-k-closed": 4_000, "run-b-planned": 2_000}
        self.run_handoff("run-z-oldest", "ctx-a", unfinished=[], nextAction="最早的一步")
        self.run_handoff("run-a-newest", "ctx-a", unfinished=[], nextAction="继续写第 22 集")
        self.run_handoff("run-m-interrupted", "ctx-a", unfinished=[], status={"run": "interrupted", "goal": "not_assessed"}, nextAction="从第 3 场续写")
        self.run_handoff("run-k-closed", "ctx-a", unfinished=["复核结尾"], nextAction="复核")
        self.run_handoff("run-b-planned", "ctx-a", unfinished=[], status={"run": "planned", "goal": "not_assessed"}, nextAction="开始运行")
        for run_id, stamp in stamps.items():
            os.utime(self.drama / f"runs/{run_id}.json", (stamp, stamp))
        result, lines = self.status()
        self.assertEqual((result["runs"]["count"], result["runs"]["latest"]["runId"]), (5, "run-a-newest"))
        self.assertEqual([run["runId"] for run in result["runs"]["open"]], ["run-k-closed", "run-m-interrupted", "run-b-planned"])
        self.assertEqual(lines[0], "下一步：继续写第 22 集")
        text = "\n".join(lines)
        for needle in ("run-m-interrupted", "从第 3 场续写", "复核结尾", "run-b-planned"):
            self.assertIn(needle, text)
        self.assertNotIn("run-z-oldest", text)
        self.assertTrue(result["runs"]["latest"]["modifiedAt"].startswith("1970-01-0"))


class CliTests(ProjectCase):
    def test_help_lists_status_and_impact(self):
        listing = self.cli("--help").stdout
        self.assertLess(listing.index("receipt"), listing.index("status"))
        self.assertIn("impact", listing)
        self.assertIn("--json", self.cli("status", "--help").stdout)
        for flag in ("--slot", "--revision", "--artifact"):
            self.assertIn(flag, self.cli("impact", "--help").stdout)

    def test_ac4_status_prints_the_reconcile_action_on_the_first_line(self):
        self.ac4_fixture()
        run = self.cli("status", self.project)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        lines = run.stdout.splitlines()
        self.assertTrue(lines[0].startswith("下一步：对账"), lines[0])
        self.assertIn("d1-save-3", lines[0])
        self.assertFalse(run.stdout.lstrip().startswith("{"))
        for needle in ("请用户决定是否接受 C4 变更提案", "C4 变更待用户决定", "ctx-a：完好"):
            self.assertIn(needle, run.stdout)

    def test_status_first_line_is_the_impact_command_when_the_latest_run_pins_an_older_revision(self):
        self.ac1_fixture()
        self.run_handoff("run-a", "ctx-a")
        run = self.cli("status", self.project)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        lines = run.stdout.splitlines()
        self.assertTrue(lines[0].startswith(f"下一步：先运行 drama_tools.py impact {self.project} --slot ep-1 --revision 2"), lines[0])
        self.assertIn("请用户决定是否接受 C4 变更提案", lines[1])
        self.assertEqual(json.loads(self.cli("status", self.project, "--json").stdout)["nextAction"]["basis"], "stale_run")

    def test_status_json_is_parseable_and_matches_the_text_view(self):
        self.ac4_fixture()
        run = self.cli("status", self.project, "--json")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        result = json.loads(run.stdout)
        self.assertEqual(result, project_status.run_status(str(self.project)))
        self.assertEqual(self.cli("status", self.project).stdout, project_status.render_status(result) + "\n")
        self.assertEqual((result["receipts"]["pending"][0]["requestId"], result["runs"]["latest"]["nextAction"]),
                         ("d1-save-3", "请用户决定是否接受 C4 变更提案"))

    def test_impact_prints_json_and_exits_0_whatever_the_verdicts(self):
        self.ac1_fixture()
        self.snapshot("ctx-unknown", [ref("art-404", 1)])
        self.run_handoff("run-a", "ctx-a")
        for target in (("--slot", "ep-1", "--revision", "2"), ("--artifact", "art-2")):
            with self.subTest(target=target):
                run = self.cli("impact", self.project, *target)
                self.assertEqual((run.returncode, run.stderr), (0, ""))
                result = json.loads(run.stdout)
                self.assertEqual({item["snapshotId"]: item["status"] for item in result["snapshots"]},
                                 {"ctx-a": "stale", "ctx-b": "current", "ctx-unknown": "unknown"})
                self.assertEqual([(item["runId"], item["status"]) for item in result["runs"]], [("run-a", "stale")])
                self.assertEqual((result["read_only"], result["remote_verified"]), (True, False))

    def test_impact_input_errors_exit_1(self):
        self.ac1_fixture()
        for target in ((), ("--slot", "ep-1"), ("--revision", "2"), ("--slot", "ep-1", "--revision", "2", "--artifact", "art-2"),
                       ("--artifact", "art-404"), ("--slot", "ep-1", "--revision", "0")):
            with self.subTest(target=target):
                run = self.cli("impact", self.project, *target)
                self.assertEqual((run.returncode, run.stdout), (1, ""))
                self.assertFalse(json.loads(run.stderr)["ok"])
                self.assertNotIn("Traceback", run.stderr)

    def test_project_without_drama_exits_1_and_explains(self):
        bare = Path(self.temp.name) / "not-a-project"
        bare.mkdir()
        for path in (bare, Path(self.temp.name) / "absent"):
            for command in (("status",), ("status", "--json"), ("impact", "--slot", "ep-1", "--revision", "2"), ("impact", "--artifact", "art-2")):
                with self.subTest(path=path.name, command=command):
                    run = self.cli(command[0], path, *command[1:])
                    self.assertEqual((run.returncode, run.stdout), (1, ""))
                    error = json.loads(run.stderr)
                    self.assertFalse(error["ok"])
                    self.assertIn(".drama", error["error"])
                    self.assertIn("init-project", error["error"])
        self.assertEqual(list(bare.iterdir()), [])
        self.assertFalse((Path(self.temp.name) / "absent").exists())


def tree(root):
    """Every path under root with its sha256 (files) and mtime, so a new, changed, or created-then-deleted file shows up."""
    return {path.relative_to(root).as_posix(): (None if path.is_dir() or path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest(),
                                                path.lstat().st_mtime_ns) for path in sorted(root.rglob("*"))}


class ReadOnlyTests(ProjectCase):
    def full_project(self):
        """Real receipts and cache from the synthetic MCP fixtures, plus valid and damaged snapshots and runs."""
        self.ac4_fixture()
        receipt.record_receipt(str(self.project), str(FIXTURES / "02-save.response.json"), "save_story_artifact", "d1-save-2",
                               str(FIXTURES / "02-save.input.json"))
        receipt.cache(str(self.project), [str(FIXTURES / name) for name in CHUNKS] + [str(FIXTURES / "03-get.response.json")])
        receipt.cache(str(self.project), [str(FIXTURES / "07-reconcile-get.response.json")])  # revision 2 of the same slot
        self.snapshot("ctx-ep3", [ref(ART1, 1)])
        self.snapshot("ctx-unknown", [ref("art-404", 1)])
        edited = self.snapshot("ctx-edited", [])
        edited.write_bytes(edited.read_bytes() + b" ")
        self.run_handoff("run-ep3", "ctx-ep3", status={"run": "interrupted", "goal": "not_assessed"})
        (self.drama / "runs/run-broken.json").write_text("{", encoding="utf-8")
        (self.drama / "receipts/broken.json").write_text("[]", encoding="utf-8")

    def test_ac5_every_file_under_drama_is_unchanged_by_status_and_impact(self):
        self.full_project()
        before = tree(self.project)
        hashes = {name: digest for name, (digest, _) in before.items() if name.startswith(".drama/") and digest}
        self.assertGreaterEqual(len(hashes), 12)
        calls = [("status",), ("status", "--json"), ("impact", "--slot", "ep-03-outline", "--revision", "2"), ("impact", "--artifact", ART1),
                 ("impact", "--artifact", "art-404"), ("impact", "--slot", "ep-03-outline")]
        for call, code in zip(calls, (0, 0, 0, 0, 1, 1)):
            with self.subTest(call=call):
                run = self.cli(call[0], self.project, *call[1:])
                self.assertEqual(run.returncode, code, run.stderr)
                self.assertNotIn("Traceback", run.stderr)
                after = tree(self.project)
                self.assertEqual({name: digest for name, (digest, _) in after.items() if name.startswith(".drama/") and digest}, hashes)
                self.assertEqual(after, before)  # no lock file, temp file or folder appeared anywhere in the project, even briefly
        status = json.loads(self.cli("status", self.project, "--json").stdout)
        flagged = {run["runId"]: run["stalenessCheck"] for run in [status["runs"]["latest"], *status["runs"]["open"]]}
        self.assertEqual(flagged, {"run-ep3": "newer_revision_cached", "run-ep21-c5-1": "no_newer_revision_cached"})
        self.assertEqual(tree(self.project), before)
        stale = json.loads(self.cli("impact", self.project, "--slot", "ep-03-outline", "--revision", "2").stdout)
        self.assertEqual({item["snapshotId"]: item["status"] for item in stale["snapshots"]},
                         {"ctx-a": "current", "ctx-edited": "unknown", "ctx-ep3": "stale", "ctx-unknown": "unknown"})
        self.assertEqual({item["runId"]: item["status"] for item in stale["runs"]},
                         {"run-broken": "unknown", "run-ep21-c5-1": "current", "run-ep3": "stale"})

    def test_empty_project_stays_empty(self):
        before = tree(self.project)
        self.assertEqual(self.cli("status", self.project).returncode, 0)
        result = json.loads(self.cli("impact", self.project, "--slot", "ep-1", "--revision", "2").stdout)
        self.assertEqual((result["snapshots"], result["runs"]), ([], []))
        self.assertEqual(tree(self.project), before)
        self.assertEqual(sorted(path.name for path in self.drama.iterdir()), ["project.json"])

    def test_areas_symlinked_outside_the_project_are_refused_not_read(self):
        outside = Path(self.temp.name) / "outside"
        impact = ("impact", "--slot", "ep-1", "--revision", "2")
        for name, refused in [("receipts", [("status",)]), ("cache", [impact]), ("snapshots", [("status",), impact]), ("runs", [("status",), impact])]:
            with self.subTest(name):
                (outside / name).mkdir(parents=True)
                (self.drama / name).symlink_to(outside / name, target_is_directory=True)
                for call in refused:
                    run = self.cli(call[0], self.project, *call[1:])
                    self.assertEqual(run.returncode, 1, run.stdout)
                    self.assertIn("outside the project", json.loads(run.stderr)["error"])
                (self.drama / name).unlink()
        self.assertEqual(list(outside.rglob("*.*")), [])

    def test_records_symlinked_outside_or_malformed_are_reported_without_a_traceback(self):
        elsewhere = Path(self.temp.name) / "elsewhere.json"
        elsewhere.write_text((EXAMPLES / "run-handoff.json").read_text(encoding="utf-8"), encoding="utf-8")
        for name in ("snapshots", "runs"):
            folder = self.drama / name
            folder.mkdir()
            (folder / "run-ep21-c5-1.json").symlink_to(elsewhere)
            (folder / "dangling.json").symlink_to(folder / "nowhere.json")
            (folder / "list.json").write_text("[]", encoding="utf-8")
            (folder / "binary.json").write_bytes(b"\xff\xfe")
            (folder / "folder.json").mkdir()
        before = tree(self.project)
        run = self.cli("status", self.project, "--json")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        result = json.loads(run.stdout)
        self.assertEqual(len(result["invalid"]), 10)
        self.assertEqual((result["runs"]["latest"], result["nextAction"]["basis"]), (None, "invalid_record"))
        self.assertTrue(all(not item["intact"] for item in result["snapshots"]))
        outside = next(item for item in result["invalid"] if item["path"] == ".drama/runs/run-ep21-c5-1.json")
        self.assertIn("outside the project", outside["errors"][0])
        run = self.cli("impact", self.project, "--slot", "ep-1", "--revision", "2")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        result = json.loads(run.stdout)
        self.assertEqual({item["status"] for item in result["snapshots"] + result["runs"]}, {"unknown"})
        self.assertEqual(self.cli("status", self.project).returncode, 0)
        self.assertEqual(tree(self.project), before)


class InvariantTests(unittest.TestCase):
    def test_doctor_still_reports_offline_and_the_same_contracts(self):
        run = subprocess.run([sys.executable, "-B", str(TOOL), "doctor"], capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertEqual((run.returncode, result["network_used"], result["models_called"], result["mali_story"]), (0, False, False, "not_checked"))
        self.assertEqual(result["contracts"], ["context-snapshot", "knowledge-card", "remote-receipt", "review-record", "run-handoff", "selection", "task"])

    def test_module_imports_only_the_standard_library_and_sibling_checks(self):
        source = (ROOT / "skills/drama-studio/scripts/checks/project_status.py").read_text(encoding="utf-8")
        imported, names, called = set(), set(), set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add("." + node.module if node.level else node.module.split(".")[0])
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Call):
                called.add(node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", ""))
        self.assertEqual(imported, {"__future__", "datetime", "hashlib", "json", "pathlib", "shlex", ".contract_check", ".receipt"})
        writers = {"open", "write", "write_text", "write_bytes", "mkdir", "makedirs", "unlink", "rmdir", "rename", "replace", "touch",
                   "link", "symlink_to", "atomic_write", "publish_new", "manifest_lock", "cache", "record_receipt"}
        self.assertEqual((called | names) & writers, set())


class DocsTests(unittest.TestCase):
    def test_recovery_order_starts_with_status_and_keeps_the_earlier_steps(self):
        text = (ROOT / "skills/drama-studio/references/recovery.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^## .+$", text, re.M), ["## 本地与远端", "## 恢复顺序", "## 交付"])
        section = text.split("\n## 恢复顺序\n", 1)[1].split("\n## ", 1)[0]
        steps = [line for line in section.splitlines() if re.match(r"\d+\. ", line)]
        self.assertEqual([step.split(".")[0] for step in steps], ["1", "2", "3", "4", "5"])
        for needle in ("scripts/drama_tools.py status <项目目录>", "第一行", "不读聊天记录", "退出码 1"):
            self.assertIn(needle, steps[0])
        for needle in ("[两次审批](approval-flow.md)", "不重建同名项目", "只报告缓存状态及其日期", "响应未知的提交", "阅读测试进行到哪一步",
                       "不能猜造 ID", "drama_tools.py impact <项目目录> --slot", "--artifact", "stale", "unknown", "扩大阅读", "隐含依赖",
                       "不自动重跑", "反馈修订接续时", "宿主切换先停止原宿主写入"):
            self.assertIn(needle, section, needle)

    def test_readme_documents_status_and_impact_with_examples(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for example in ("drama_tools.py status ../my-drama\n", "drama_tools.py status ../my-drama --json\n",
                        "drama_tools.py impact ../my-drama --slot ep-03-outline --revision 2\n", "drama_tools.py impact ../my-drama --artifact "):
            self.assertIn(example, text)
        for needle in ("slotSource", "`record`", "`receipt`", "`host`", "`stale`", "`unknown`", "`current`", "扩大阅读", "隐含依赖未评估",
                       "recencyBasis: file_mtime", "read_only: true", "remote_verified: false", "第一行是下一步动作", "不写任何文件"):
            self.assertIn(needle, text, needle)

    def test_recovery_demo_states_its_synthetic_source_before_anything_else(self):
        text = (ROOT / "docs/d2/recovery-demo.md").read_text(encoding="utf-8")
        opening = "\n".join(text.splitlines()[:6])
        for needle in ("合成夹具", "tests/fixtures/mcp-synthetic/", "不是 #9 的真实产物", "待 #9"):
            self.assertIn(needle, opening, needle)
        for heading in ("## 全新会话恢复记录", "## 待 #9 真实产物补录", "## 只读证明"):
            self.assertIn(f"\n{heading}", text)
        self.assertNotIn("/Users/", text)
        self.assertIn("AC-6 不勾选", text)
        self.assertIn("docs/d2/recovery-demo.md", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
