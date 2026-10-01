import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
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


def other(kind, ref_id, revision=None):
    """A packed item whose reference is not a remote_artifact; the schema allows these in hand-written snapshots."""
    return {"ref": {"kind": kind, "id": ref_id, "revision": revision}, "partition": "project_facts", "required": False,
            "usage": "project_text", "chars": 1, "reason": "宿主手写的引用"}


def output(artifact, revision):
    return {"kind": "remote_artifact", "id": artifact, "revision": revision}


DONE = {"status": {"run": "finished", "goal": "met"}, "unfinished": []}


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
        self.assertEqual(result["target"], {"slot": "ep-1", "revision": 2, "resolvedFrom": "--slot/--revision",
                                            "slotInManifest": True, "newestTrustedRevision": 2})
        self.assertEqual(result["warnings"], [])
        reason = snapshots["ctx-a"]["reasons"][0]
        self.assertEqual((reason["ref"], reason["status"]), ("items[1] art-1@r1", "stale"))
        self.assertIn("ep-1", reason["reason"])
        self.assertEqual((snapshots["ctx-b"]["reasons"], snapshots["ctx-a"]["path"]), ([], ".drama/snapshots/ctx-a.json"))
        self.assertEqual(result["summary"]["snapshots"], {"stale": 1, "unknown": 0, "current": 1})

    def test_ac1_artifact_resolves_through_the_manifest_to_the_same_result(self):
        self.ac1_fixture()
        by_slot, by_artifact = self.impact(slot="ep-1", revision=2)[0], self.impact(artifact="art-2")[0]
        self.assertEqual(by_artifact["target"], {"slot": "ep-1", "revision": 2, "resolvedFrom": "--artifact art-2",
                                                 "slotInManifest": True, "newestTrustedRevision": 2})
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

    CORRECTED = {"record after host": [("ep-9", "host"), ("ep-1", "record")], "record before host": [("ep-1", "record"), ("ep-9", "host")],
                 "record after an entry without slotSource": [("ep-9", None), ("ep-1", "record")],
                 "record after an unexpected slotSource": [("ep-9", "trusted-by-me"), ("ep-1", "record")],
                 "receipt after host": [("ep-9", "host"), ("ep-1", "receipt")],
                 "record after receipt and host": [("ep-9", "host"), ("ep-9", "receipt"), ("ep-1", "record")],
                 "record settles two host entries that disagree": [("ep-9", "host"), ("ep-8", "host"), ("ep-1", "record")]}

    def test_slot_resolves_from_the_strongest_source_and_a_corrected_entry_is_not_a_conflict(self):
        for label, entries in self.CORRECTED.items():
            with self.subTest(label):
                self.manifest(*(entry("art-fix", slot, 1, source) for slot, source in entries), entry("art-2", "ep-1", 2))
                self.snapshot("ctx-a", [ref("art-fix", 1)])
                reference = {"kind": "remote_artifact", "id": "art-fix", "revision": 1}
                self.assertEqual(project_status.judge_ref(reference, project_status._entries(self.drama), "ep-1", 2)[0], "stale")
                result, snapshots, _ = self.impact(artifact="art-fix")
                self.assertEqual(result["target"], {"slot": "ep-1", "revision": 1, "resolvedFrom": "--artifact art-fix",
                                                    "slotInManifest": True, "newestTrustedRevision": 2})
                self.assertEqual((snapshots["ctx-a"]["status"], snapshots["ctx-a"]["reasons"]), ("current", []))
                result, snapshots, _ = self.impact(slot="ep-1", revision=2)
                self.assertEqual(snapshots["ctx-a"]["reasons"], [{"ref": "items[1] art-fix@r1", "status": "stale",
                                                                  "reason": "引用了 slot ep-1 的旧修订 r1，目标修订为 r2"}])
                result, snapshots, _ = self.impact(slot="ep-9", revision=5)  # the slot only the corrected entry named
                self.assertEqual(snapshots["ctx-a"]["status"], "current")
                self.assertEqual((result["target"]["slotInManifest"], result["target"]["newestTrustedRevision"], len(result["warnings"])), (False, None, 1))

    def test_contradicting_strongest_entries_stay_unknown_and_revisions_are_never_corrected(self):
        cases = {"two record entries": [entry("art-x", "ep-1", 1), entry("art-x", "ep-4", 1)],
                 "two record entries over a host entry": [entry("art-x", "ep-1", 1, "host"), entry("art-x", "ep-1", 1), entry("art-x", "ep-4", 1)],
                 "two receipt entries": [entry("art-x", "ep-1", 1, "receipt"), entry("art-x", "ep-4", 1, "receipt")],
                 "two host entries": [entry("art-x", "ep-1", 1, "host"), entry("art-x", "ep-4", 1, "host")],
                 "host entry and one without slotSource": [entry("art-x", "ep-1", 1, "host"), entry("art-x", "ep-4", 1, None)],
                 "a stronger entry with another revision": [entry("art-x", "ep-1", 1, "host"), entry("art-x", "ep-1", 2)],
                 "strongest source is only the host": [entry("art-x", "ep-1", 1, None), entry("art-x", "ep-1", 1, "host")]}
        for label, entries in cases.items():
            with self.subTest(label):
                self.manifest(*entries, entry("art-2", "ep-1", 2))
                self.snapshot("ctx-a", [ref("art-x", 1)])
                for target in ({"slot": "ep-1", "revision": 2}, {"slot": "ep-4", "revision": 2}):
                    item = self.impact(**target)[1]["ctx-a"]
                    self.assertEqual((item["status"], len(item["reasons"])), ("unknown", 1))
                    self.assertIn("扩大阅读", item["suggestion"])
                with self.assertRaises(ValueError):
                    self.impact(artifact="art-x")

    def test_corrected_entry_no_longer_claims_the_slot_it_named(self):
        ep1 = [entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2)]
        for label, entries in self.CORRECTED.items():
            with self.subTest(label):  # art-fix r2 really belongs to ep-1; the weaker entries named ep-9 (or ep-8)
                fixed = [entry("art-fix", slot, 2, source) for slot, source in entries]
                run, latest, status, _ = self.strict(entry("art-9", "ep-9", 1), entry("art-9b", "ep-9", 2), *fixed,
                                                     outputs=("art-9b", 2), pins=("art-9", 1))
                self.assertEqual(self.impact(slot="ep-9", revision=2)[2]["run-rev"]["reasons"], [{
                    "ref": "items[1] art-9@r1", "status": "current",
                    "reason": "运行记录声称产出了 slot ep-9 的 r2（outputs[0] art-9b@r2），快照对旧修订 r1 的引用不使它失效"}])
                self.assertEqual((latest["stalenessCheck"], latest["stalenessReasons"], status["nextAction"]["basis"]),
                                 ("newer_revision_is_own_output", [], "latest_run"))
        with self.subTest("uncorrected, the same host entry still leaves the run unknown"):
            self.assertDoubt(self.strict(*ep1, entry("art-fix", "ep-1", 2, "host"), outputs=("art-2", 2)), "art-fix", "宿主声明")
            run = self.strict(*ep1, entry("art-fix", "ep-1", 2, "host"), entry("art-fix", "ep-7", 2), outputs=("art-2", 2))[0]
            self.assertEqual((run["status"], run["reasons"][0]["status"]), ("current", "current"))
        with self.subTest("the corrected artifact counts in the slot the record names"):
            fixed = [entry("art-fix", "ep-9", 2, "host"), entry("art-fix", "ep-1", 2)]
            run = self.strict(*ep1[:1], *fixed, outputs=("art-fix", 2))[0]
            self.assertEqual((run["status"], run["reasons"][0]["status"]), ("current", "current"))
            self.assertDoubt(self.strict(*ep1, *fixed, outputs=("art-2", 2)), "r2", "art-fix", "多个")  # two trusted artifacts at ep-1 r2
        with self.subTest("contradicting record entries claim their own slots, not the one a weaker entry named"):
            run = self.strict(*ep1, entry("art-x", "ep-1", 2, "host"), entry("art-x", "ep-4", 2), entry("art-x", "ep-5", 2), outputs=("art-2", 2))[0]
            self.assertEqual((run["status"], run["reasons"][0]["status"]), ("current", "current"))
            self.assertDoubt(self.strict(*ep1, entry("art-x", "ep-7", 2, "host"), entry("art-x", "ep-1", 2), entry("art-x", "ep-5", 2),
                                         outputs=("art-2", 2)), "art-x")

    def test_corrected_entry_raises_no_doubt_about_a_newer_revision_in_the_slot_it_named(self):
        fixed = [entry("art-fix", "ep-1", 4, "host"), entry("art-fix", "ep-7", 4)]
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), *fixed)
        self.snapshot("ctx-a", [ref("art-2", 2)])
        self.run_handoff("run-a", "ctx-a")
        latest = project_status.run_status(str(self.project))["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"], latest["stalenessReasons"]), ("no_newer_revision_cached", [], []))
        result = self.impact(slot="ep-1", revision=2)[0]
        self.assertEqual((result["target"]["newestTrustedRevision"], result["warnings"]), (2, []))  # art-fix is not a trusted r4 of ep-1
        self.assertEqual(self.impact(slot="ep-7", revision=4)[0]["target"]["newestTrustedRevision"], 4)
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), fixed[0])  # without the correction the doubt is still raised
        latest = project_status.run_status(str(self.project))["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], len(latest["stalenessReasons"])), ("unknown", 1))

    def test_ac2_wrong_host_declared_slot_is_judged_once_the_get_response_corrects_it(self):
        chunks = [str(FIXTURES / name) for name in CHUNKS]
        cached = receipt.cache(str(self.project), chunks, slot="ep-99-outline", kind="episode_outline", episode_ref="ep-03")
        self.assertEqual((cached["passed"], cached["entry"]["slotSource"], cached["entry"]["slot"]), (True, "host", "ep-99-outline"))
        self.snapshot("ctx-ep3", [ref(ART1, 1)])
        self.assertEqual(self.impact(slot="ep-03-outline", revision=2)[1]["ctx-ep3"]["status"], "unknown")
        with self.assertRaisesRegex(ValueError, "get_story_artifact"):
            self.impact(artifact=ART1)
        corrected = receipt.cache(str(self.project), chunks + [str(FIXTURES / "03-get.response.json")])
        self.assertEqual((corrected["passed"], corrected["manifestAppended"], corrected["entry"]["slot"]), (True, True, "ep-03-outline"))
        result, snapshots, _ = self.impact(artifact=ART1)
        self.assertEqual(result["target"], {"slot": "ep-03-outline", "revision": 1, "resolvedFrom": f"--artifact {ART1}",
                                            "slotInManifest": True, "newestTrustedRevision": 1})
        self.assertEqual((snapshots["ctx-ep3"]["status"], result["warnings"], result["remote_verified"]), ("current", [], False))
        self.assertEqual(self.impact(slot="ep-03-outline", revision=2)[1]["ctx-ep3"]["status"], "stale")
        wrong = self.impact(slot="ep-99-outline", revision=2)
        self.assertEqual((wrong[1]["ctx-ep3"]["status"], wrong[0]["target"]["slotInManifest"]), ("current", False))

    def test_only_packed_remote_artifacts_count_as_dependencies(self):
        self.manifest(entry("art-1", "ep-1", 1))
        card = {"ref": {"kind": "knowledge_card", "id": "art-1", "revision": 1}, "partition": "knowledge", "required": False,
                "usage": "creative_reference", "chars": 3, "reason": "同名知识卡"}
        left_out = {"ref": {"kind": "remote_artifact", "id": "art-1", "revision": 1}, "required": False, "reason": "not_relevant"}
        self.snapshot("ctx-omitted", [card], omitted=[left_out])
        self.snapshot("ctx-task-only", [])
        _, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()}, {"ctx-omitted": "current", "ctx-task-only": "current"})

    def test_unassessed_reference_kinds_are_unknown_and_never_current(self):
        self.ac1_fixture()
        for kind, ref_id in [("local_file", ".drama/cache/art-1@r1.md"), ("remote_snapshot", "wsnap-77"), ("remote_brief", "brief-1"),
                             ("remote_receipt", "d1-save-2")]:
            self.snapshot(f"ctx-{kind}", [ref("art-9", 1), other(kind, ref_id)])
        self.snapshot("ctx-ignored", [ref("art-9", 1), dict(other("knowledge_card", "kc-1", 1), partition="knowledge")])
        self.snapshot("ctx-task-lookalike", [ref("art-9", 1), other("local_file", "task:another-task")])  # not in the task partition
        _, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual((snapshots["ctx-ignored"]["status"], snapshots["ctx-task-lookalike"]["status"]), ("current", "unknown"))
        self.assertEqual(snapshots["ctx-task-lookalike"]["reasons"][0]["reason"], "该引用类型的依赖未评估")
        for kind in ("local_file", "remote_snapshot", "remote_brief", "remote_receipt"):
            with self.subTest(kind):
                item = snapshots[f"ctx-{kind}"]
                self.assertEqual(item["status"], "unknown")
                self.assertEqual([(reason["status"], reason["reason"]) for reason in item["reasons"]], [("unknown", "该引用类型的依赖未评估")])
                self.assertIn(f"items[2] {kind} ", item["reasons"][0]["ref"])
                self.assertNotIn("current", json.dumps(item, ensure_ascii=False))
                self.assertIn("扩大阅读", item["suggestion"])

    def test_context_snapshot_reference_inherits_the_verdict_of_the_snapshot_it_names(self):
        self.ac1_fixture()
        self.snapshot("ctx-on-a", [other("context_snapshot", "ctx-a")])
        self.snapshot("ctx-on-b", [other("context_snapshot", "ctx-b")])
        self.snapshot("ctx-on-on-a", [ref("art-9", 1), other("context_snapshot", "ctx-on-a")])
        self.snapshot("ctx-on-missing", [other("context_snapshot", "ctx-gone")])
        self.snapshot("ctx-on-edited", [other("context_snapshot", "ctx-edited")])
        edited = self.snapshot("ctx-edited", [ref("art-9", 1)])
        edited.write_bytes(edited.read_bytes() + b" ")
        self.snapshot("ctx-self", [other("context_snapshot", "ctx-self")])
        self.snapshot("ctx-loop-1", [other("context_snapshot", "ctx-loop-2")])
        self.snapshot("ctx-loop-2", [other("context_snapshot", "ctx-loop-1")])
        self.run_handoff("run-nested", "ctx-on-on-a")
        self.run_handoff("run-on-b", "ctx-on-b")
        _, snapshots, runs = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()},
                         {"ctx-a": "stale", "ctx-b": "current", "ctx-on-a": "stale", "ctx-on-b": "current", "ctx-on-on-a": "stale",
                          "ctx-on-missing": "unknown", "ctx-on-edited": "unknown", "ctx-edited": "unknown", "ctx-self": "unknown",
                          "ctx-loop-1": "unknown", "ctx-loop-2": "unknown"})
        self.assertEqual(snapshots["ctx-on-on-a"]["reasons"], [{
            "ref": "items[2] context_snapshot ctx-on-a > items[1] context_snapshot ctx-a > items[1] art-1@r1", "status": "stale",
            "reason": "引用了 slot ep-1 的旧修订 r1，目标修订为 r2"}])
        self.assertIn("ctx-gone", snapshots["ctx-on-missing"]["reasons"][0]["reason"])
        self.assertIn(".sha256", snapshots["ctx-on-edited"]["reasons"][0]["reason"])
        for key in ("ctx-self", "ctx-loop-1", "ctx-loop-2"):
            self.assertIn("成环", snapshots[key]["reasons"][0]["reason"])
        self.assertEqual((runs["run-nested"]["status"], runs["run-on-b"]["status"]), ("stale", "current"))
        self.assertIn("art-1@r1", runs["run-nested"]["reasons"][-1]["ref"])

    def revision_fixture(self):
        """ctx-a pins ep-1 r1; ctx-two also pins ep-0 r1. The manifest holds trusted r2 and r3 of ep-1 and r2 of ep-0."""
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-3", "ep-1", 3, "receipt"),
                      entry("art-9", "ep-0", 1), entry("art-9b", "ep-0", 2), entry("art-h", "ep-5", 2, "host"))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.snapshot("ctx-two", [ref("art-1", 1), ref("art-9", 1)])

    def test_run_that_produced_the_target_revision_itself_is_not_stale(self):
        self.revision_fixture()
        self.run_handoff("run-rev", "ctx-a", outputs=[output("art-2", 2)], **DONE)
        self.run_handoff("run-reader", "ctx-a", outputs=[], **DONE)
        for target in ({"artifact": "art-2"}, {"slot": "ep-1", "revision": 2}, {"slot": "ep-1", "revision": 1}):
            with self.subTest(target=target):
                _, snapshots, runs = self.impact(**target)
                older = target.get("revision") != 1
                self.assertEqual(snapshots["ctx-a"]["status"], "stale" if older else "current")
                self.assertEqual((runs["run-rev"]["status"], runs["run-reader"]["status"]), ("current", "stale" if older else "current"))
                self.assertNotIn("suggestion", runs["run-rev"])
                if older:
                    self.assertEqual(runs["run-rev"]["reasons"], [{
                        "ref": "items[1] art-1@r1", "status": "current",
                        "reason": "运行记录声称产出了 slot ep-1 的 r2（outputs[0] art-2@r2），快照对旧修订 r1 的引用不使它失效"}])
                else:
                    self.assertEqual(runs["run-rev"]["reasons"], [])

    def test_only_a_trusted_output_at_or_above_the_target_clears_a_run(self):
        self.revision_fixture()
        cases = {"output older than the target": ([output("art-2", 2)], {"slot": "ep-1", "revision": 3}),
                 "output only declared by the host": ([output("art-h", 2)], {"slot": "ep-1", "revision": 2}),
                 "output not in the manifest": ([output("art-404", 2)], {"slot": "ep-1", "revision": 2}),
                 "output revision differs from the manifest": ([output("art-2", 5)], {"slot": "ep-1", "revision": 2}),
                 "output without a revision": ([output("art-2", None)], {"slot": "ep-1", "revision": 2}),
                 "output in another slot": ([output("art-9b", 2)], {"slot": "ep-1", "revision": 2}),
                 "output is not a remote artifact": ([{"kind": "local_file", "id": "art-2", "revision": 2}], {"slot": "ep-1", "revision": 2})}
        for label, (outputs, target) in cases.items():
            with self.subTest(label):
                self.run_handoff("run-rev", "ctx-a", outputs=outputs, **DONE)
                run = self.impact(**target)[2]["run-rev"]
                self.assertEqual(run["status"], "stale")
                self.assertEqual([reason["status"] for reason in run["reasons"]], ["stale", "stale"])
        self.run_handoff("run-rev", "ctx-a", outputs=[output("art-2", 2), output("art-3", 3)], **DONE)
        self.assertEqual(self.impact(slot="ep-1", revision=3)[2]["run-rev"]["status"], "current")

    def test_own_output_must_cover_every_cached_revision_between_the_pin_and_the_target(self):
        self.revision_fixture()  # ep-1 has trusted r1, r2 and r3 cached
        self.run_handoff("run-skipped", "ctx-a", outputs=[output("art-3", 3)], **DONE)  # never saw r2 and did not produce it
        self.run_handoff("run-chain", "ctx-a", outputs=[output("art-2", 2), output("art-3", 3)], **DONE)
        self.run_handoff("run-first", "ctx-a", outputs=[output("art-2", 2)], **DONE)
        for revision, expected in [(2, {"run-skipped": "stale", "run-chain": "current", "run-first": "current"}),
                                   (3, {"run-skipped": "stale", "run-chain": "current", "run-first": "stale"})]:
            with self.subTest(revision=revision):
                runs = self.impact(slot="ep-1", revision=revision)[2]
                self.assertEqual({key: run["status"] for key, run in runs.items()}, expected)
        chain = self.impact(slot="ep-1", revision=3)[2]["run-chain"]["reasons"]
        self.assertEqual(chain, [{"ref": "items[1] art-1@r1", "status": "current",
                                  "reason": "运行记录声称产出了 slot ep-1 的 r2、r3（outputs[0] art-2@r2、outputs[1] art-3@r3），快照对旧修订 r1 的引用不使它失效"}])
        skipped = self.impact(slot="ep-1", revision=3)[2]["run-skipped"]["reasons"]
        self.assertEqual([reason["status"] for reason in skipped], ["stale", "stale"])

    def test_own_output_never_clears_a_target_revision_that_is_not_cached(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.run_handoff("run-rev", "ctx-a", outputs=[output("art-3", 3)], **DONE)
        self.assertEqual(self.impact(slot="ep-1", revision=2)[2]["run-rev"]["status"], "stale")  # nothing cached at r2, no own output up to r2
        for revision, missing in [(3, ["r2 未缓存"]), (4, ["r2 未缓存", "r4 未缓存"])]:
            run = self.impact(slot="ep-1", revision=revision)[2]["run-rev"]
            self.assertEqual(run["status"], "unknown")
            for needle in missing:
                self.assertIn(needle, run["reasons"][1]["reason"])

    def strict(self, *entries, outputs=("art-3", 3), pins=("art-1", 1)):
        """Write the manifest, a snapshot pinning `pins` and a finished run listing `outputs`; return both commands' view of the run."""
        self.manifest(*entries)
        self.snapshot("ctx-a", [ref(*pins)])
        listed = [outputs] if isinstance(outputs[0], str) else list(outputs)
        self.run_handoff("run-rev", "ctx-a", outputs=[output(*item) for item in listed], nextAction="请编剧审阅", **DONE)
        newest = max(item[1] for item in listed)
        run = self.impact(slot="ep-1", revision=newest)[2]["run-rev"]
        status = project_status.run_status(str(self.project))
        return run, status["runs"]["latest"], status, project_status.render_status(status).splitlines()

    def assertDoubt(self, view, *needles):
        run, latest, status, lines = view
        self.assertEqual((run["status"], latest["stalenessCheck"]), ("unknown", "unknown"))
        self.assertIn("扩大阅读", run["suggestion"])
        self.assertNotIn("current", json.dumps(run["reasons"], ensure_ascii=False))
        self.assertEqual((latest["newerRevisions"], latest["ownOutputs"]), ([], []))
        self.assertNotIn("possiblyStale", latest)
        self.assertEqual((status["nextAction"]["basis"], lines[0]), ("latest_run", "下一步：请编剧审阅"))
        self.assertIn("最近运行是否失效无法判断，见下。", lines[1])
        text = "\n".join(lines)
        self.assertIn("无法判断是否失效", text)
        for word in ("不因此失效", "可能已失效", "没有它所引用 slot 的更新修订"):
            self.assertNotIn(word, text)
        for needle in needles:
            self.assertIn(needle, " ".join(reason["reason"] for reason in run["reasons"]))
            self.assertIn(needle, " ".join(latest["stalenessReasons"]))

    def test_repro_1_untrusted_or_ambiguous_claimant_between_the_pin_and_the_output_is_unknown(self):
        r1, r3 = entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3)
        cases = {"host-declared r2": [entry("art-2", "ep-1", 2, "host")],
                 "r2 without slotSource": [entry("art-2", "ep-1", 2, None)],
                 "r2 with an unexpected slotSource": [entry("art-2", "ep-1", 2, "trusted-by-me")],
                 "r2 with conflicting entries": [entry("art-2", "ep-1", 2), entry("art-2", "ep-4", 2)],
                 "r2 with conflicting revisions": [entry("art-2", "ep-1", 2), entry("art-2", "ep-1", 5)]}
        for label, middle in cases.items():
            with self.subTest(label):
                self.assertDoubt(self.strict(r1, *middle, r3), "art-2", "r2 只有不可信的缓存条目")
            with self.subTest(label + ", listed among the run's outputs"):
                self.assertDoubt(self.strict(r1, *middle, r3, outputs=[("art-2", 2), ("art-3", 3)]), "art-2")

    def test_repro_2_untrusted_claimant_above_the_own_output_is_unknown(self):
        view = self.strict(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-3", "ep-1", 3, "host"), outputs=("art-2", 2))
        self.assertDoubt(view, "art-3", "宿主声明")
        self.assertNotEqual(view[1]["stalenessCheck"], "newer_revision_is_own_output")
        legacy = self.strict(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-odd", "ep-1", "3", None), outputs=("art-2", 2))
        self.assertDoubt(legacy, "art-odd")

    def test_repro_3_uncached_revision_between_the_pin_and_the_output_is_unknown(self):
        self.assertDoubt(self.strict(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3)), "r2 未缓存，无法确认是否为该运行产出")
        self.assertDoubt(self.strict(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3), entry("art-5", "ep-1", 5),
                                     outputs=[("art-3", 3), ("art-5", 5)]), "r2 未缓存", "r4 未缓存")

    def test_repro_4_two_trusted_artifacts_at_one_revision_is_unknown(self):
        view = self.strict(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-2b", "ep-1", 2, "receipt"), outputs=("art-2", 2))
        self.assertDoubt(view, "r2", "art-2b", "多个")

    def test_own_output_still_clears_on_complete_trusted_unambiguous_evidence(self):
        trusted = [entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-3", "ep-1", 3, "receipt")]
        below_the_pin = [entry("art-0", "ep-1", 1, "host"), entry("art-other", "ep-9", 7, "host")]  # provably not above the pin, or another slot
        for label, entries, outputs in [("in-place r1 to r2", trusted[:2], ("art-2", 2)),
                                        ("r2 and r3 from r1", trusted, [("art-2", 2), ("art-3", 3)]),
                                        ("untrusted claimants at or below the pin or elsewhere", trusted[:2] + below_the_pin, ("art-2", 2))]:
            with self.subTest(label):
                run, latest, status, lines = self.strict(*entries, outputs=outputs)
                self.assertEqual((run["status"], latest["stalenessCheck"], status["nextAction"]["basis"]), ("current", "newer_revision_is_own_output", "latest_run"))
                self.assertIn("运行记录声称产出了", run["reasons"][0]["reason"])
        run, latest, status, lines = self.strict(*trusted)  # r2 is someone else's trusted revision: stale, not doubt
        self.assertEqual((run["status"], latest["stalenessCheck"], latest["possiblyStale"], status["nextAction"]["basis"]),
                         ("stale", "newer_revision_cached", True, "stale_run"))
        self.assertEqual(latest["newerRevisions"][0]["staleAgainstRevision"], 2)
        run, latest, _, _ = self.strict(*trusted, entry("art-h", "ep-1", 4, "host"))  # stale wins over the doubt a claimant adds
        self.assertEqual((run["status"], latest["stalenessCheck"]), ("stale", "newer_revision_cached"))

    def test_huge_revisions_are_judged_quickly_with_the_same_verdicts_and_wording(self):
        huge = 999_999_999_999
        self.manifest(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.run_handoff("run-rev", "ctx-a", outputs=[output("art-3", 3)], nextAction="请编剧审阅", **DONE)
        self.run_handoff("run-reader", "ctx-a", outputs=[], **DONE)
        os.utime(self.drama / "runs/run-reader.json", (1_000, 1_000))

        def timed(*args):
            started = time.monotonic()
            run = self.cli(*args)
            self.assertLess(time.monotonic() - started, 5, args)
            self.assertEqual((run.returncode, run.stderr), (0, ""))
            return json.loads(run.stdout)

        def reasons(result, run_id):
            run = next(item for item in result["runs"] if item["runId"] == run_id)
            return run["status"], [reason["reason"] for reason in run["reasons"]]

        small, big = timed("impact", self.project, "--slot", "ep-1", "--revision", "4"), timed("impact", self.project, "--slot", "ep-1", "--revision", huge)
        self.assertEqual(big["target"]["revision"], huge)
        self.assertEqual(reasons(small, "run-reader"), ("stale", ["所依赖的快照为 stale", "引用了 slot ep-1 的旧修订 r1，目标修订为 r4"]))
        self.assertEqual(reasons(big, "run-reader"), ("stale", ["所依赖的快照为 stale", f"引用了 slot ep-1 的旧修订 r1，目标修订为 r{huge}"]))
        prefix = "运行记录声称产出了 slot ep-1 的 r3（outputs[0] art-3@r3），但证据不完整，无法确认它覆盖了 r1 之后的全部修订：r2 未缓存，无法确认是否为该运行产出；"
        self.assertEqual(reasons(small, "run-rev"), ("unknown", ["所依赖的快照中有无法判定的引用", prefix + "r4 未缓存，无法确认是否为该运行产出"]))
        self.assertEqual(reasons(big, "run-rev"), ("unknown", ["所依赖的快照中有无法判定的引用", prefix + f"r4 至 r{huge} 未缓存，无法确认是否为该运行产出"]))

        # a trusted entry at a huge revision: someone else's is stale, the run's own leaves a gap it cannot account for
        self.manifest(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3), entry("art-big", "ep-1", huge), entry("art-h", "ep-1", 7, "host"))
        status = timed("status", self.project, "--json")
        latest = status["runs"]["latest"]
        self.assertEqual((latest["runId"], latest["stalenessCheck"], latest["newerRevisions"][0]["staleAgainstRevision"]), ("run-rev", "newer_revision_cached", huge))
        self.assertEqual(reasons(timed("impact", self.project, "--artifact", "art-big"), "run-rev")[0], "stale")
        self.run_handoff("run-rev", "ctx-a", outputs=[output("art-3", 3), output("art-big", huge)], nextAction="请编剧审阅", **DONE)
        status = timed("status", self.project, "--json")
        latest = status["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"], latest["ownOutputs"]), ("unknown", [], []))
        self.assertIn("：r2 未缓存，无法确认是否为该运行产出；r4 至 r6 未缓存，无法确认是否为该运行产出；r7 只有不可信的缓存条目，无法确认是否为该运行产出；"
                      f"r8 至 r{huge - 1} 未缓存，无法确认是否为该运行产出；manifest 中 art-h 声称属于该 slot", latest["stalenessReasons"][0])
        self.assertEqual(reasons(timed("impact", self.project, "--artifact", "art-big"), "run-rev")[0], "unknown")
        started = time.monotonic()
        self.assertIn("无法判断是否失效", self.cli("status", self.project).stdout)
        self.assertLess(time.monotonic() - started, 5)

    def test_own_output_rule_is_not_applied_to_planned_or_failed_runs(self):
        self.revision_fixture()
        for state, expected in [("planned", "stale"), ("failed", "stale"), ("running", "current"), ("interrupted", "current"), ("finished", "current")]:
            with self.subTest(state):
                self.run_handoff("run-rev", "ctx-a", outputs=[output("art-2", 2)], status={"run": state, "goal": "not_assessed"}, unfinished=[])
                self.assertEqual(self.impact(slot="ep-1", revision=2)[2]["run-rev"]["status"], expected)

    def test_lead_reason_of_a_run_describes_the_findings_that_remain(self):
        self.revision_fixture()
        self.snapshot("ctx-mixed", [ref("art-1", 1), ref("art-404", 1)])
        self.run_handoff("run-rev", "ctx-mixed", outputs=[output("art-2", 2)], **DONE)
        self.run_handoff("run-reader", "ctx-mixed", outputs=[], **DONE)
        _, snapshots, runs = self.impact(slot="ep-1", revision=2)
        self.assertEqual((snapshots["ctx-mixed"]["status"], runs["run-rev"]["status"], runs["run-reader"]["status"]), ("stale", "unknown", "stale"))
        lead = runs["run-rev"]["reasons"][0]
        self.assertEqual((lead["ref"], lead["status"]), ("context_snapshot ctx-mixed", "unknown"))
        self.assertNotIn("快照为 stale", lead["reason"])
        self.assertIn("无法判定", lead["reason"])
        self.assertEqual(runs["run-reader"]["reasons"][0]["reason"], "所依赖的快照为 stale")

    def test_own_output_clears_only_its_own_slot(self):
        self.revision_fixture()
        self.run_handoff("run-rev", "ctx-two", outputs=[output("art-2", 2)], **DONE)
        run = self.impact(slot="ep-0", revision=2)[2]["run-rev"]
        self.assertEqual((run["status"], [reason["ref"] for reason in run["reasons"]]), ("stale", ["context_snapshot ctx-two", "items[2] art-9@r1"]))
        run = self.impact(slot="ep-1", revision=2)[2]["run-rev"]
        self.assertEqual((run["status"], [reason["status"] for reason in run["reasons"]]), ("current", ["current"]))
        self.snapshot("ctx-two", [ref("art-1", 1), ref("art-404", 1)])
        run = self.impact(slot="ep-1", revision=2)[2]["run-rev"]
        self.assertEqual((run["status"], [reason["status"] for reason in run["reasons"]]), ("unknown", ["unknown", "unknown", "current"]))
        self.assertIn("扩大阅读", run["suggestion"])

    def test_very_deep_snapshot_chain_is_unknown_not_a_crash(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2))
        self.snapshot("ctx-0000", [ref("art-1", 1)])
        for depth in range(1, 1200):
            self.snapshot(f"ctx-{depth:04d}", [other("context_snapshot", f"ctx-{depth - 1:04d}")])
        self.run_handoff("run-deep", "ctx-1199")
        run = self.cli("impact", self.project, "--slot", "ep-1", "--revision", "2")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        result = json.loads(run.stdout)
        snapshots = {item["snapshotId"]: item for item in result["snapshots"]}
        self.assertEqual((snapshots["ctx-0000"]["status"], snapshots["ctx-0005"]["status"]), ("stale", "stale"))
        self.assertEqual((snapshots["ctx-1199"]["status"], result["runs"][0]["status"]), ("unknown", "unknown"))
        self.assertIn("层", snapshots["ctx-1199"]["reasons"][0]["reason"])
        self.assertEqual(result["summary"]["snapshots"]["current"], 0)
        run = self.cli("status", self.project, "--json")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        latest = json.loads(run.stdout)["runs"]["latest"]
        self.assertEqual(latest["stalenessCheck"], "unknown")
        self.assertNotIn("possiblyStale", latest)

    def test_revisions_below_one_are_invalid_everywhere(self):
        self.manifest(entry("art-0", "ep-1", 0), entry("art-neg", "ep-2", -1), entry("art-1", "ep-1", 1), entry("art-2", "ep-2", 2))
        self.snapshot("ctx-zero", [ref("art-0", 0)])
        self.snapshot("ctx-neg", [ref("art-neg", -1)])
        self.run_handoff("run-zero", "ctx-zero")
        _, snapshots, _ = self.impact(slot="ep-1", revision=1)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()}, {"ctx-zero": "unknown", "ctx-neg": "unknown"})
        self.assertEqual(project_status.judge_ref({"kind": "remote_artifact", "id": "art-1", "revision": 0}, [entry("art-1", "ep-1", 1)], "ep-1", 2)[0], "unknown")
        with self.assertRaises(ValueError):
            self.impact(artifact="art-0")
        status = project_status.run_status(str(self.project))
        latest = status["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"], status["nextAction"]["basis"]), ("unknown", [], "latest_run"))
        text = project_status.render_status(status)
        for word in ("的 r0", "可能已失效", "--revision"):  # the label may echo the reference as written; nothing treats r0 as a revision
            self.assertNotIn(word, text)

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

    def test_target_slot_unseen_in_the_manifest_is_flagged_without_changing_verdicts(self):
        self.ac1_fixture()
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-9", "ep-0", 1), entry("art-h", "ep-7", 4, "host"))
        result, snapshots, _ = self.impact(slot="ep-l", revision=2)  # a typo of ep-1
        self.assertEqual((result["target"]["slotInManifest"], result["target"]["newestTrustedRevision"]), (False, None))
        self.assertEqual(len(result["warnings"]), 1)
        for needle in ("ep-l", "拼写", "记录在案的引用"):
            self.assertIn(needle, result["warnings"][0])
        self.assertEqual({key: item["status"] for key, item in snapshots.items()}, {"ctx-a": "current", "ctx-b": "current"})
        host_only = self.impact(slot="ep-7", revision=5)[0]
        self.assertEqual((host_only["target"]["slotInManifest"], host_only["target"]["newestTrustedRevision"], host_only["warnings"]), (True, None, []))
        ahead = self.impact(slot="ep-1", revision=9)[0]
        self.assertEqual((ahead["target"]["revision"], ahead["target"]["newestTrustedRevision"], ahead["warnings"]), (9, 2, []))

    def test_target_below_the_newest_cached_revision_is_flagged_without_changing_verdicts(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-3", "ep-1", 3), entry("art-h", "ep-1", 9, "host"))
        self.snapshot("ctx-r1", [ref("art-1", 1)])
        self.snapshot("ctx-r2", [ref("art-2", 2)])
        result, snapshots, _ = self.impact(slot="ep-1", revision=2)
        self.assertEqual({key: item["status"] for key, item in snapshots.items()}, {"ctx-r1": "stale", "ctx-r2": "current"})
        self.assertEqual((result["target"]["newestTrustedRevision"], len(result["warnings"])), (3, 1))
        for needle in ("r2", "r3", "--revision 3"):
            self.assertIn(needle, result["warnings"][0])
        self.assertEqual(self.impact(artifact="art-2")[0]["warnings"], result["warnings"])
        for revision in (3, 4):
            self.assertEqual(self.impact(slot="ep-1", revision=revision)[0]["warnings"], [])

    def test_revision_is_validated_as_text_and_reported_as_an_integer(self):
        self.ac1_fixture()
        for good in ("2", 2, "02"):
            with self.subTest(good=good):
                self.assertEqual(self.impact(slot="ep-1", revision=good)[0]["target"]["revision"], 2)
        for bad in ("abc", "", "0", "-1", "2.5", " 2", "２", True, 0, 2.0):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "--revision"):
                    self.impact(slot="ep-1", revision=bad)
        for empty in ("", "  "):
            with self.assertRaisesRegex(ValueError, "--slot"):
                self.impact(slot=empty, revision=2)

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
        command = f"drama_tools.py impact {self.project} --slot=ep-1 --revision 2"
        latest = result["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["possiblyStale"]), ("newer_revision_cached", True))
        self.assertEqual(latest["newerRevisions"], [{"ref": "items[2] art-1@r1", "slot": "ep-1", "pinnedRevision": 1, "newestTrustedRevision": 2,
                                                     "staleAgainstRevision": 2, "impactCommand": command}])
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
        self.assertIn("--slot=ep-1 --revision 2", "\n".join(lines))

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
                 "untrusted newer entry in the slot": lambda: (self.manifest(entry("art-1", "ep-1", 1), entry("art-3", "ep-1", 3, "host")), [ref("art-1", 1)])}
        for label, build in cases.items():
            with self.subTest(label):
                if (self.drama / "cache/manifest.json").exists():
                    (self.drama / "cache/manifest.json").unlink()
                _, items = build()
                self.snapshot("ctx-a", items)
                self.run_handoff("run-a", "ctx-a")
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

    def test_corrupt_cache_manifest_is_an_invalid_record_and_leaves_staleness_unknown(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.run_handoff("run-a", "ctx-a")
        for content in ("{", "[]", json.dumps({"schemaVersion": "other", "entries": []}), json.dumps({"schemaVersion": "drama-studio/cache-manifest/v0"})):
            with self.subTest(content):
                (self.drama / "cache/manifest.json").write_text(content, encoding="utf-8")
                result, lines = self.status()
                self.assertEqual([(item["kind"], item["path"]) for item in result["invalid"]], [("manifest", ".drama/cache/manifest.json")])
                self.assertEqual((result["nextAction"]["basis"], result["nextAction"]["from"]), ("invalid_record", ".drama/cache/manifest.json"))
                latest = result["runs"]["latest"]
                self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"]), ("unknown", []))
                self.assertNotIn("possiblyStale", latest)
                self.assertTrue(lines[0].startswith("下一步：处理无效或损坏的记录 .drama/cache/manifest.json"), lines[0])
                self.assertIn("[manifest] .drama/cache/manifest.json", "\n".join(lines))
                with self.assertRaisesRegex(ValueError, "manifest"):
                    project_status.run_impact(str(self.project), slot="ep-1", revision=2)
        self.unknown_save()
        self.assertEqual(self.status()[0]["nextAction"]["basis"], "unknown_receipt")

    def test_each_kind_of_invalid_record_gets_advice_that_fits_it(self):
        self.unknown_save()
        self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        receipts = self.drama / "receipts"
        forged = json.loads((receipts / "d1-reconcile-3.json").read_text(encoding="utf-8"))
        forged.update(requestId="uncounted", notes=json.dumps(dict(json.loads(forged["notes"]), observedRequestId="someone-else")))
        (receipts / "uncounted.json").write_text(json.dumps(forged), encoding="utf-8")
        (receipts / "broken.json").write_text("{", encoding="utf-8")
        self.manifest()
        (self.drama / "cache/manifest.json").write_text("{", encoding="utf-8")
        self.snapshot("ctx-no-sidecar", [], sidecar=False)
        (self.drama / "runs").mkdir()
        (self.drama / "runs/run-broken.json").write_text("{", encoding="utf-8")
        result, lines = self.status()
        advice = {(item["kind"], Path(item["path"]).name): item["advice"] for item in result["invalid"]}
        self.assertEqual(sorted(advice), [("manifest", "manifest.json"), ("receipt", "broken.json"), ("receipt", "uncounted.json"),
                                          ("run", "run-broken.json"), ("snapshot", "ctx-no-sidecar.json")])
        for key, needles in {("receipt", "broken.json"): ("回执只追加", "不能当作恢复依据"),
                             ("receipt", "uncounted.json"): ("这份回执本身有效", "没有被计入", "不要改它", "新的 requestId"),
                             ("manifest", "manifest.json"): ("manifest 只追加", "工具不会修正", "impact"),
                             ("snapshot", "ctx-no-sidecar.json"): ("快照写入后不改", "context-pack"),
                             ("run", "run-broken.json"): ("宿主",)}.items():
            for needle in needles:
                self.assertIn(needle, advice[key], (key, needle))
        self.assertEqual(len(set(advice.values())), 5)
        text = "\n".join(lines)
        self.assertNotIn("修复或移走", text + json.dumps(result, ensure_ascii=False))
        first = result["invalid"][0]
        self.assertTrue(result["nextAction"]["text"].endswith(first["advice"]))
        for item in result["invalid"]:
            self.assertIn("    处理：" + item["advice"], lines)

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

    def test_status_follows_nested_snapshots_and_reports_unassessed_reference_kinds_as_unknown(self):
        self.stale_fixture()
        self.snapshot("ctx-nested", [other("context_snapshot", "ctx-a")])
        self.run_handoff("run-a", "ctx-nested")
        latest = self.status()[0]["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["possiblyStale"]), ("newer_revision_cached", True))
        self.assertEqual([(item["ref"], item["slot"], item["pinnedRevision"], item["newestTrustedRevision"]) for item in latest["newerRevisions"]],
                         [("items[1] context_snapshot ctx-a > items[2] art-1@r1", "ep-1", 1, 2)])
        for kind in ("local_file", "remote_snapshot", "remote_brief", "remote_receipt"):
            with self.subTest(kind):
                self.snapshot("ctx-other", [ref("art-9", 1), other(kind, "some-id")])
                self.run_handoff("run-a", "ctx-other")
                result, lines = self.status()
                latest = result["runs"]["latest"]
                self.assertEqual((latest["stalenessCheck"], result["nextAction"]["basis"]), ("unknown", "latest_run"))
                self.assertNotIn("possiblyStale", latest)
                self.assertIn("该引用类型的依赖未评估", latest["stalenessReasons"][0])
                self.assertIn("无法判断是否失效", "\n".join(lines))
        self.snapshot("ctx-loop", [other("context_snapshot", "ctx-loop")])
        self.run_handoff("run-a", "ctx-loop")
        self.assertEqual(self.status()[0]["runs"]["latest"]["stalenessCheck"], "unknown")

    def test_run_that_produced_the_newest_revision_keeps_its_own_next_action(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-9", "ep-0", 1))
        self.snapshot("ctx-a", [ref("art-9", 1), ref("art-1", 1)])
        self.run_handoff("run-rev", "ctx-a", outputs=[output("art-2", 2)], nextAction="请编剧审阅第 1 集修订稿", **DONE)
        result, lines = self.status()
        latest = result["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], latest["newerRevisions"], latest["stalenessReasons"]), ("newer_revision_is_own_output", [], []))
        self.assertNotIn("possiblyStale", latest)
        self.assertEqual(latest["ownOutputs"], [{"ref": "items[2] art-1@r1", "slot": "ep-1", "pinnedRevision": 1, "producedRevision": 2,
                                                 "output": "outputs[0] art-2@r2"}])
        self.assertEqual((result["nextAction"]["basis"], lines[0]), ("latest_run", "下一步：请编剧审阅第 1 集修订稿"))
        text = "\n".join(lines)
        self.assertIn("运行记录声称更新的 r2 是它自己的产出", text)
        for word in ("可能已失效", "不要直接照做", "没有它所引用 slot 的更新修订", "无法判断"):
            self.assertNotIn(word, text)

    def test_status_is_stale_against_the_highest_revision_the_run_did_not_produce(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-3", "ep-1", 3))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.run_handoff("run-skipped", "ctx-a", outputs=[output("art-3", 3)], nextAction="请编剧审阅", **DONE)
        result, lines = self.status()
        latest = result["runs"]["latest"]
        command = f"drama_tools.py impact {self.project} --slot=ep-1 --revision 2"
        self.assertEqual((latest["stalenessCheck"], latest["possiblyStale"], latest["ownOutputs"]), ("newer_revision_cached", True, []))
        self.assertEqual(latest["newerRevisions"], [{"ref": "items[1] art-1@r1", "slot": "ep-1", "pinnedRevision": 1, "newestTrustedRevision": 3,
                                                     "staleAgainstRevision": 2, "impactCommand": command}])
        self.assertEqual(result["nextAction"]["basis"], "stale_run")
        self.assertTrue(lines[0].startswith(f"下一步：先运行 {command} "), lines[0])
        self.assertIn("本地缓存已有可信的 r2", lines[0])
        self.assertEqual(json.loads(self.cli(*command.split()[1:]).stdout)["runs"][0]["status"], "stale")
        self.run_handoff("run-skipped", "ctx-a", outputs=[output("art-2", 2), output("art-3", 3)], nextAction="请编剧审阅", **DONE)
        result, lines = self.status()
        latest = result["runs"]["latest"]
        self.assertEqual((latest["stalenessCheck"], lines[0]), ("newer_revision_is_own_output", "下一步：请编剧审阅"))
        self.assertEqual(latest["ownOutputs"], [{"ref": "items[1] art-1@r1", "slot": "ep-1", "pinnedRevision": 1, "producedRevision": 3,
                                                 "output": "outputs[1] art-3@r3"}])
        self.run_handoff("run-skipped", "ctx-a", outputs=[output("art-2", 2), output("art-3", 3)], nextAction="请编剧审阅",
                         status={"run": "failed", "goal": "not_met"}, unfinished=[])
        self.assertEqual(self.status()[0]["nextAction"]["basis"], "stale_run")

    def test_own_output_does_not_hide_a_newer_revision_or_another_slot(self):
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2), entry("art-3", "ep-1", 3), entry("art-9", "ep-0", 1),
                      entry("art-9b", "ep-0", 2), entry("art-h", "ep-5", 2, "host"))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.snapshot("ctx-two", [ref("art-1", 1), ref("art-9", 1)])
        for label, snapshot_id, outputs, slots in [("someone cached r3 after this run's r2", "ctx-a", [output("art-2", 2)], ["ep-1"]),
                                                   ("host-declared output", "ctx-a", [output("art-h", 2)], ["ep-1"]),
                                                   ("the other slot moved too", "ctx-two", [output("art-2", 2), output("art-3", 3)], ["ep-0"])]:
            with self.subTest(label):
                self.run_handoff("run-rev", snapshot_id, outputs=outputs, **DONE)
                result, lines = self.status()
                latest = result["runs"]["latest"]
                self.assertEqual((latest["stalenessCheck"], latest["possiblyStale"], result["nextAction"]["basis"]), ("newer_revision_cached", True, "stale_run"))
                self.assertEqual([item["slot"] for item in latest["newerRevisions"]], slots)
                self.assertTrue(lines[0].startswith("下一步：先运行 drama_tools.py impact"), lines[0])

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
        self.assertEqual(command, f"drama_tools.py impact '{spaced}' --slot='ep 1' --revision 2")
        spaced.rename(self.project)

    def test_printed_impact_command_runs_as_printed_even_for_awkward_slots(self):
        for slot in ("-ep-1", "--slot", "ep 1's", "集-1"):
            with self.subTest(slot=slot):
                self.manifest(entry("art-1", slot, 1), entry("art-2", slot, 2))
                self.snapshot("ctx-a", [ref("art-1", 1)])
                self.run_handoff("run-a", "ctx-a")
                command = self.status()[0]["nextAction"]["impactCommand"]
                run = self.cli(*shlex.split(command)[1:])
                self.assertEqual((run.returncode, run.stderr), (0, ""))
                result = json.loads(run.stdout)
                self.assertEqual((result["target"]["slot"], result["target"]["revision"], result["runs"][0]["status"]), (slot, 2, "stale"))

    def test_slot_with_a_line_break_is_never_altered_in_the_text_view(self):
        for slot in ("ep\n1", "ep\u20281", "ep\r\n1", "ep\u20291"):
            with self.subTest(slot=repr(slot)):
                self.manifest(entry("art-1", slot, 1), entry("art-2", slot, 2))
                self.snapshot("ctx-a", [ref("art-1", 1)])
                self.run_handoff("run-a", "ctx-a")
                result, lines = self.status()
                self.assertEqual(result["nextAction"]["basis"], "stale_run")
                command = result["nextAction"]["impactCommand"]
                self.assertEqual(result["runs"]["latest"]["newerRevisions"][0]["slot"], slot)
                run = self.cli(*shlex.split(command)[1:])  # the JSON command is exact and still runs
                self.assertEqual((run.returncode, json.loads(run.stdout)["target"]["slot"]), (0, slot))
                text = "\n".join(lines)
                self.assertNotIn("drama_tools.py impact", text)  # no one-line command could name this slot safely
                self.assertNotIn("ep 1", text)
                shown = json.dumps(slot)
                self.assertTrue(lines[0].startswith(f"下一步：先对 slot {shown} 的 r2 运行 impact"), lines[0])
                self.assertIn("status --json", lines[0])
                self.assertIn("impactCommand", lines[0])
                self.assertTrue(lines[2].startswith("依据："), lines[2])
                self.assertEqual(sum(shown in line for line in lines), 2)
                self.assertEqual(len(lines), len(project_status.render_status(json.loads(json.dumps(result))).splitlines()))

    def test_multi_line_values_do_not_break_the_first_line(self):
        self.snapshot("ctx-a", [])
        self.run_handoff("run-a", "ctx-a", nextAction="续写第 4 集\n然后保存候选\r\n\n再请编剧审阅", unfinished=["结尾钩子\n未定", "第二项"])
        result, lines = self.status()
        self.assertEqual(lines[0], "下一步：续写第 4 集 然后保存候选 再请编剧审阅")
        self.assertTrue(lines[1].startswith("依据："), lines[1])
        self.assertEqual(result["nextAction"]["text"], "续写第 4 集\n然后保存候选\r\n\n再请编剧审阅")
        self.assertEqual(result["runs"]["latest"]["unfinished"], ["结尾钩子\n未定", "第二项"])
        text = "\n".join(lines)
        self.assertIn("    下一步：续写第 4 集 然后保存候选 再请编剧审阅", lines)
        self.assertIn("    未完成：结尾钩子 未定；第二项", lines)
        self.assertEqual(len(lines), len(project_status.render_status(json.loads(json.dumps(result))).splitlines()))
        self.manifest(entry("art-1", "ep-1", 1), entry("art-2", "ep-1", 2))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        lines = self.status()[1]
        self.assertTrue(lines[0].startswith("下一步：先运行 "), lines[0])
        self.assertTrue(lines[1].endswith("：续写第 4 集 然后保存候选 再请编剧审阅"), lines[1])
        self.assertTrue(lines[2].startswith("依据："), lines[2])
        self.assertNotIn("\r", text)

    def test_unknown_staleness_of_the_latest_run_is_hinted_on_the_basis_line(self):
        self.manifest(entry("art-1", "ep-1", 1, "host"))
        self.snapshot("ctx-a", [ref("art-1", 1)])
        self.run_handoff("run-a", "ctx-a")
        lines = self.status()[1]
        self.assertTrue(lines[1].startswith("依据：最近一次运行记录的 nextAction（.drama/runs/run-a.json）。最近运行是否失效无法判断，见下。"), lines[1])
        self.unknown_save()
        lines = self.status()[1]
        self.assertTrue(lines[0].startswith("下一步：对账"), lines[0])
        self.assertIn("最近运行是否失效无法判断，见下。", lines[1])
        self.manifest(entry("art-1", "ep-1", 1))
        self.assertNotIn("无法判断", "\n".join(self.status()[1]))

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
        self.assertTrue(lines[0].startswith(f"下一步：先运行 drama_tools.py impact {self.project} --slot=ep-1 --revision 2"), lines[0])
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

    def test_issue_20_reproduction_is_corrected_then_judged_by_impact_and_packed_by_context_pack(self):
        chunks, get = [FIXTURES / name for name in CHUNKS], FIXTURES / "03-get.response.json"
        temp, task, art2 = Path(self.temp.name), EXAMPLES / "task.json", "c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d"
        elsewhere = json.loads(get.read_text(encoding="utf-8"))
        elsewhere["structuredContent"]["data"]["record"].update(id="art-ep99", slot="ep-99-outline", episodeRef="ep-99")
        (temp / "ep99-get.json").write_text(json.dumps(elsewhere, ensure_ascii=False), encoding="utf-8")

        def run(code, *args):
            done = self.cli(*args)
            self.assertEqual(done.returncode, code, done.stdout + done.stderr)
            return json.loads(done.stdout or done.stderr)

        def pack(project, name, artifacts, *flags):
            (temp / name).write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
                {"ref": {"kind": "remote_artifact", "id": artifact, "revision": revision}, "partition": "project_facts", "required": True,
                 "reason": "测试"} for artifact, revision in artifacts]}), encoding="utf-8")
            return "context-pack", project, "--task", task, "--selection", temp / name, "--role", "author", "--budget", "20000", *flags

        for label, correction in [("chunks and get, as in the issue", [*chunks, get]), ("get only", [get])]:
            with self.subTest(label):
                project = temp / label.split()[0]
                run(0, "init-project", project, "--title", "演示")
                manifest = project / ".drama/cache/manifest.json"
                wrong = run(0, "receipt", "cache", project, *chunks, "--slot", "ep-99-outline", "--kind", "episode_outline", "--episode-ref", "ep-03")
                self.assertEqual((wrong["entry"]["slotSource"], wrong["entry"]["slot"]), ("host", "ep-99-outline"))
                self.assertIn("可信的 slot", run(1, "impact", project, "--artifact", ART1)["error"])
                first = manifest.read_bytes()
                fixed = run(0, "receipt", "cache", project, *correction)
                self.assertEqual((fixed["manifestAppended"], fixed["entry"]["slotSource"], fixed["entry"]["slot"], fixed["verified"]),
                                 (True, "record", "ep-03-outline", True))
                self.assertTrue(manifest.read_bytes().startswith(first[:first.rindex(b"\n  ]")]))
                entries = json.loads(manifest.read_text(encoding="utf-8"))["entries"]
                self.assertEqual([(item["slotSource"], item["slot"]) for item in entries], [("host", "ep-99-outline"), ("record", "ep-03-outline")])

                impact = run(0, "impact", project, "--artifact", ART1)
                self.assertEqual(impact["target"], {"slot": "ep-03-outline", "revision": 1, "resolvedFrom": f"--artifact {ART1}",
                                                    "slotInManifest": True, "newestTrustedRevision": 1})
                dry = run(0, *pack(project, "one.json", [(ART1, 1)], "--dry-run"))  # verified: no --allow-unverified needed
                self.assertEqual((dry["passed"], dry["omitted_count"], dry["written"]), (True, 0, False))
                packed = run(0, *pack(project, "one.json", [(ART1, 1)]))
                self.assertNotIn("unknowns", json.loads(Path(packed["snapshot_path"]).read_text(encoding="utf-8")))
                snapshot_id = packed["snapshot_id"]
                judged = {target: {item["snapshotId"]: item for item in run(0, "impact", project, *target)["snapshots"]}[snapshot_id]
                          for target in (("--artifact", ART1), ("--slot", "ep-03-outline", "--revision", "2"), ("--slot", "ep-99-outline", "--revision", "2"))}
                self.assertEqual([item["status"] for item in judged.values()], ["current", "stale", "current"])
                self.assertEqual(judged["--slot", "ep-03-outline", "--revision", "2"]["reasons"], [{
                    "ref": f"items[1] {ART1}@r1", "status": "stale", "reason": "引用了 slot ep-03-outline 的旧修订 r1，目标修订为 r2"}])

                run(0, "receipt", "cache", project, FIXTURES / "07-reconcile-get.response.json")  # revision 2 of ep-03-outline
                run(0, "receipt", "cache", project, temp / "ep99-get.json")  # an artifact that really is in ep-99-outline
                mixed = run(2, *pack(project, "mixed.json", [(ART1, 1), (art2, 2)], "--allow-unverified", "--dry-run"))
                self.assertEqual(len(mixed["errors"]), 1, mixed["errors"])
                for needle in ("slot 'ep-03-outline'", f"{ART1}@r1", "one package cannot mix revisions of a slot"):
                    self.assertIn(needle, mixed["errors"][0])
                apart = run(0, *pack(project, "apart.json", [(ART1, 1), ("art-ep99", 1)], "--allow-unverified", "--dry-run"))
                self.assertEqual((apart["passed"], apart["omitted_count"], len(apart["items"])), (True, 0, 3))
                status = run(0, "status", project, "--json")
                self.assertEqual((status["invalid"], status["remote_verified"]), ([], False))

    def test_impact_input_errors_exit_1(self):
        self.ac1_fixture()
        for target in ((), ("--slot", "ep-1"), ("--revision", "2"), ("--slot", "ep-1", "--revision", "2", "--artifact", "art-2"),
                       ("--artifact", "art-404"), ("--slot", "ep-1", "--revision", "0"), ("--slot", "ep-1", "--revision", "abc"),
                       ("--slot", "", "--revision", "2"), ("--slot", "ep-1", "--revision", "")):
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
        for needle in ("scripts/drama_tools.py status <项目目录>", "第一行", "不读聊天记录", "退出码 1", "引用了旧修订", "impact 命令",
                       "不说明远端", "无法判断"):
            self.assertIn(needle, steps[0])
        for needle in ("[两次审批](approval-flow.md)", "不重建同名项目", "只报告缓存状态及其日期", "响应未知的提交", "阅读测试进行到哪一步",
                       "不能猜造 ID", "drama_tools.py impact <项目目录> --slot", "--artifact", "stale", "unknown", "扩大阅读", "隐含依赖",
                       "不自动重跑", "反馈修订接续时", "宿主切换先停止原宿主写入", "运行记录声称产出", "warnings"):
            self.assertIn(needle, section, needle)

    def test_readme_documents_status_and_impact_with_examples(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for example in ("drama_tools.py status ../my-drama\n", "drama_tools.py status ../my-drama --json\n",
                        "drama_tools.py impact ../my-drama --slot ep-03-outline --revision 2\n", "drama_tools.py impact ../my-drama --artifact "):
            self.assertIn(example, text)
        for needle in ("slotSource", "`record`", "`receipt`", "`host`", "`stale`", "`unknown`", "`current`", "扩大阅读", "隐含依赖未评估",
                       "recencyBasis: file_mtime", "read_only: true", "remote_verified: false", "第一行是下一步动作", "不写任何文件",
                       "possiblyStale", "stalenessCheck", "no_newer_revision_cached", "newer_revision_cached", "不说明远端",
                       "newer_revision_is_own_output", "运行记录声称", "每保存一次加 1", "完整、可信、无歧义", "`planned`", "staleAgainstRevision",
                       "slotCheck", "低于该 slot 已缓存的最新可信修订", "50 层", "`context_snapshot`", "该引用类型的依赖未评估", "slotInManifest",
                       "newestTrustedRevision", "拼写", "`--slot=", "record.slot", "kind 为 `manifest`"):
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
