import hashlib
import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
