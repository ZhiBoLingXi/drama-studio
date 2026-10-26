"""v1.2 page model (#34): receipts, cache, context-pack and impact keyed on pageId + revision.

Fixtures in tests/fixtures/mcp-pages-synthetic/ are hand-built from the mali-story v0.20.0 source, not live responses.
"""
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
FIXTURES = ROOT / "tests/fixtures/mcp-pages-synthetic"
EXAMPLES = ROOT / "skills/drama-studio/examples"
sys.path.insert(0, str(ROOT / "skills/drama-studio/scripts"))
sys.dont_write_bytecode = True
import receipt  # noqa: E402
from contract_check import check_contract  # noqa: E402

PROJECT = "2f70c1e9fad74f35ae27f"
PAGE = "5b0d6c1e-8f3a-4e2b-9c47-1a2b3c4d5e6f"
R2_CHUNKS = [f"07-read-r2-chunk-{i}.response.json" for i in range(1, 5)]


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class FixtureTests(unittest.TestCase):
    def test_every_fixture_is_marked_synthetic(self):
        names = sorted(FIXTURES.glob("*.json"))
        self.assertGreater(len(names), 20)
        for path in names:
            self.assertIn("synthetic", json.loads(path.read_text(encoding="utf-8")).get("_synthetic", ""), path.name)

    def test_each_response_parses_as_its_page_operation(self):
        for name, operation, ok in (("01-create.response.json", "create_page", True), ("02-update.response.json", "update_page", True),
                                    ("03-update-conflict.response.json", "update_page", False),
                                    ("04-update-unknown.response.json", "update_page", False),
                                    ("05-list-landed.response.json", "list_page_revisions", True),
                                    ("06-resend.response.json", "update_page", True), (R2_CHUNKS[0], "read_page", True),
                                    ("08-label.response.json", "label_page_revision", True), ("09-restore.response.json", "restore_page", True)):
            with self.subTest(name):
                parsed = receipt.parse_response(fixture(name), operation)
                self.assertEqual(parsed["ok"], ok)
                self.assertIn("mali-tool-result/v1", parsed["shape"])
                text_only = fixture(name)  # the text content alone parses the same way
                del text_only["structuredContent"]
                self.assertEqual(receipt.parse_response(text_only, operation)["ok"], ok)
        with self.assertRaises(ValueError):  # a read chunk is not an update result
            receipt.parse_response(fixture(R2_CHUNKS[0]), "update_page")

    def test_conflict_keeps_the_server_details(self):
        parsed = receipt.parse_response(fixture("03-update-conflict.response.json"), "update_page")
        self.assertEqual((parsed["httpStatus"], parsed["errorCode"], parsed["retrySafe"]), (409, "VERSION_CONFLICT", False))
        self.assertEqual(parsed["errorDetails"]["currentRevision"], 2)

    def test_read_chunks_join_to_the_full_body_fingerprint(self):
        datas = [receipt.parse_response(fixture(name), "read_page")["data"] for name in R2_CHUNKS]
        text = "".join(data["text"] for data in datas)
        self.assertEqual(len(text), datas[0]["totalCharacters"])
        self.assertGreater(len(text.encode("utf-8")), len(text))
        self.assertIn("𠮷", text)  # one code point outside the BMP: offsets are code points, not UTF-16 units
        self.assertEqual(sha(text.encode("utf-8")), datas[0]["fingerprint"])
        self.assertEqual(fixture("02-update.input.json")["body"], text)
        self.assertIsNone(datas[-1]["nextOffset"])
        self.assertTrue(datas[-1]["atEnd"])


class PageCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "proj"
        self.assertEqual(self.cli("init-project", str(self.project), "--title", "页面测试")[0], 0)

    def cli(self, *args):
        process = subprocess.run([sys.executable, "-B", str(TOOL), *args], capture_output=True, text=True)
        out = process.stdout if process.stdout.strip() else process.stderr
        try:
            return process.returncode, json.loads(out)
        except ValueError:
            return process.returncode, out

    def record(self, response, operation, request_id, input_name, *extra):
        return self.cli("receipt", "record", str(self.project), str(FIXTURES / response), "--operation", operation,
                        "--request-id", request_id, "--input", str(FIXTURES / input_name), *extra)

    def cache(self, *names, extra=()):
        return self.cli("receipt", "cache", str(self.project), *[str(FIXTURES / name) for name in names], *extra)

    def write_input(self, name, value):
        path = self.base / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path


class ReceiptTests(PageCase):
    def test_create_and_update_are_confirmed_with_page_id_and_revision(self):
        code, result = self.record("01-create.response.json", "create_page", "pg-create-1", "01-create.input.json")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["receipt"]["remote"], {"projectId": PROJECT, "artifactId": None, "pageId": PAGE, "revision": 1,
                                                       "inputSnapshotId": fixture("01-create.input.json")["input_snapshot_id"]})
        code, result = self.record("02-update.response.json", "update_page", "pg-update-2", "02-update.input.json")
        self.assertEqual((code, result["receipt"]["outcome"], result["receipt"]["remote"]["revision"]), (0, "confirmed", 2))
        notes = json.loads(result["receipt"]["notes"])
        self.assertEqual((notes["expectedRevision"], notes["responsePreviousRevision"], notes["responseReplayed"]), (1, 1, False))
        self.assertEqual(notes["bodyFingerprint"], fixture("02-update.response.json")["structuredContent"]["data"]["fingerprint"])
        self.assertEqual(check_contract("remote-receipt", result["receipt"]), [])
        self.assertFalse(result["adoption_verified"])

    def test_update_409_is_rejected_conflict_with_the_current_revision(self):
        code, result = self.record("03-update-conflict.response.json", "update_page", "pg-update-3", "03-update-conflict.input.json")
        self.assertEqual(code, 0, result)
        doc = result["receipt"]
        self.assertEqual((doc["outcome"], doc["retryAllowed"], doc["remote"]["revision"], doc["remote"]["pageId"]),
                         ("rejected_conflict", False, None, PAGE))
        conflict = json.loads(doc["notes"])["conflict"]
        self.assertEqual((conflict["code"], conflict["currentRevision"]), ("VERSION_CONFLICT", 2))
        self.assertTrue(any("VERSION_CONFLICT" in warning and "read_page" in warning for warning in result["warnings"]))
        self.assertEqual(self.cli("receipt", "pending", str(self.project))[1]["pending"], [])  # a conflict is not pending

    def test_unknown_update_lists_reconciliation_steps_by_list_page_revisions_and_request_id(self):
        code, result = self.record("04-update-unknown.response.json", "update_page", "pg-update-4", "04-update-unknown.input.json")
        self.assertEqual((code, result["receipt"]["outcome"], result["receipt"]["retryAllowed"]), (0, "unknown", False))
        pending = self.cli("receipt", "pending", str(self.project))[1]
        [item] = pending["pending"]
        self.assertEqual((item["requestId"], item["operation"], item["pageId"], item["expectedRevision"]), ("pg-update-4", "update_page", PAGE, 2))
        tools = [step.get("tool") for step in item["steps"]]
        self.assertEqual(tools[0], "list_page_revisions")
        self.assertEqual(item["steps"][0]["args"], {"project_id": PROJECT, "page_id": PAGE})
        self.assertIn(receipt.body_fingerprint(fixture("04-update-unknown.input.json")), item["steps"][0]["check"])
        self.assertIn("不带 requestId", item["steps"][0]["why"])
        self.assertIn("update_page", tools)  # the identical re-send with the original request_id
        commands = " ".join(step.get("command", "") for step in item["steps"])
        self.assertIn("--operation list_page_revisions", commands)
        self.assertIn("--request-id pg-update-4.resend-1", commands)
        self.assertIn("--reconciles pg-update-4", commands)
        status = self.cli("status", str(self.project), "--json")[1]
        self.assertEqual(status["nextAction"]["basis"], "unknown_receipt")
        self.assertIn("list_page_revisions", status["nextAction"]["text"])

    def test_listing_with_the_sent_body_resolves_the_unknown_as_host_judged(self):
        self.record("04-update-unknown.response.json", "update_page", "pg-update-4", "04-update-unknown.input.json")
        code, result = self.record("05-list-landed.response.json", "list_page_revisions", "pg-list-1", "05-list.input.json",
                                   "--reconciles", "pg-update-4")
        self.assertEqual((code, result["status"]), (0, "written"), result)
        notes = json.loads(result["receipt"]["notes"])
        self.assertEqual((notes["matchedRevision"], notes["matchedPageId"]), (3, PAGE))
        self.assertIn("(M)", notes["check"])
        pending = self.cli("receipt", "pending", str(self.project))[1]
        self.assertEqual((pending["pending"], pending["resolved_host_judged"], pending["resolved_verified"]), ([], ["pg-update-4"], []))

    def test_listing_without_the_write_is_refused_and_points_at_the_re_send(self):
        self.record("04-update-unknown.response.json", "update_page", "pg-update-4", "04-update-unknown.input.json")
        code, result = self.record("05-list-not-landed.response.json", "list_page_revisions", "pg-list-2", "05-list.input.json",
                                   "--reconciles", "pg-update-4")
        self.assertEqual((code, result["status"]), (2, "reconcile_refused"))
        self.assertIn("did not land", result["error"])
        self.assertIn("request_id 'pg-update-4'", result["error"])
        self.assertFalse((self.project / ".drama/receipts/pg-list-2.json").exists())

    def test_identical_re_send_resolves_the_unknown_as_verified(self):
        self.record("04-update-unknown.response.json", "update_page", "pg-update-4", "04-update-unknown.input.json")
        code, result = self.record("06-resend.response.json", "update_page", "pg-update-4.resend-1", "04-update-unknown.input.json",
                                   "--reconciles", "pg-update-4")
        self.assertEqual(code, 0, result)
        self.assertTrue(any("replayed=true" in warning for warning in result["warnings"]))
        pending = self.cli("receipt", "pending", str(self.project))[1]
        self.assertEqual((pending["pending"], pending["resolved_verified"]), ([], ["pg-update-4"]))
        changed = fixture("04-update-unknown.input.json")
        changed["body"] += "（改）"
        code, result = self.cli("receipt", "record", str(self.project), str(FIXTURES / "06-resend.response.json"), "--operation", "update_page",
                                "--request-id", "pg-update-4.resend-2", "--input", str(self.write_input("changed.json", changed)),
                                "--reconciles", "pg-update-4")
        self.assertEqual((code, result["status"]), (2, "reconcile_refused"))

    def test_unknown_create_can_only_be_re_sent(self):
        empty = self.base / "lost.json"
        code, result = self.cli("receipt", "record", str(self.project), str(empty), "--operation", "create_page",
                                "--request-id", "pg-create-1", "--input", str(FIXTURES / "01-create.input.json"))
        self.assertEqual((code, result["receipt"]["outcome"], result["receipt"]["remote"]["pageId"]), (0, "unknown", None))
        [item] = self.cli("receipt", "pending", str(self.project))[1]["pending"]
        self.assertEqual([step.get("tool") for step in item["steps"] if "tool" in step], ["create_page"])
        code, result = self.record("05-list-landed.response.json", "list_page_revisions", "pg-list-1", "05-list.input.json",
                                   "--reconciles", "pg-create-1")
        self.assertEqual((code, result["status"]), (2, "reconcile_refused"))
        self.assertIn("no page to list", result["error"])

    def test_label_is_a_name_never_adoption(self):
        code, result = self.record("08-label.response.json", "label_page_revision", "pg-label-1", "08-label.input.json")
        self.assertEqual((code, result["receipt"]["outcome"], result["receipt"]["remote"]["revision"]), (0, "confirmed", 2))
        self.assertFalse(result["adoption_verified"])
        self.assertTrue(any("不是制作采用" in warning for warning in result["warnings"]))
        self.assertIn("不是制作采用", json.loads(result["receipt"]["notes"])["labelNote"])
        task = json.loads((EXAMPLES / "task.json").read_text(encoding="utf-8"))
        task["status"]["adoption"] = "adopted_remote"  # a label's page reference cannot certify adoption
        task["adoptionEvidence"] = {"kind": "remote_page", "id": PAGE, "revision": 2}
        self.assertTrue(any("remote_receipt reference" in error for error in check_contract("task", task)))

    def test_restore_records_the_new_revision(self):
        code, result = self.record("09-restore.response.json", "restore_page", "pg-restore-5", "09-restore.input.json")
        self.assertEqual((code, result["receipt"]["remote"]["revision"]), (0, 4))
        self.assertEqual(json.loads(result["receipt"]["notes"])["responseRestoredFromRevision"], 2)

    def test_story_artifact_receipts_still_record_read_only(self):
        legacy = ROOT / "tests/fixtures/mcp-synthetic"
        code, result = self.cli("receipt", "record", str(self.project), str(legacy / "03-get.response.json"), "--operation",
                                "get_story_artifact", "--request-id", "legacy-get-1", "--input", str(legacy / "03-get.input.json"))
        self.assertEqual((code, result["receipt"]["outcome"]), (0, "confirmed"), result)
        self.assertNotIn("pageId", result["receipt"]["remote"])


class ContractTests(unittest.TestCase):
    def receipt_doc(self, **changes):
        doc = {"schemaVersion": "drama-studio/remote-receipt/v0", "operation": "update_page", "requestId": "pg-update-2",
               "inputFingerprint": "sha256:" + "a" * 64, "remote": {"projectId": PROJECT, "artifactId": None, "pageId": PAGE, "revision": 2,
                                                                    "inputSnapshotId": None},
               "outcome": "confirmed", "retryAllowed": False, "observedAt": "2026-10-08T10:00:00+08:00", "evidence": "示例"}
        doc.update(changes)
        return doc

    def test_page_receipt_rules(self):
        self.assertEqual(check_contract("remote-receipt", self.receipt_doc()), [])
        doc = self.receipt_doc()
        doc["remote"]["revision"] = None
        self.assertTrue(any("pageId and revision" in error for error in check_contract("remote-receipt", doc)))
        doc = self.receipt_doc()
        doc["remote"]["pageId"] = None
        self.assertTrue(any("must name it" in error for error in check_contract("remote-receipt", doc)))
        doc = self.receipt_doc()
        doc["remote"]["artifactId"] = "art-1"
        self.assertTrue(any("not a story artifact" in error for error in check_contract("remote-receipt", doc)))
        doc = self.receipt_doc(outcome="unknown")
        self.assertTrue(any("only a confirmed page call" in error for error in check_contract("remote-receipt", doc)))
        doc = self.receipt_doc(operation="create_page", outcome="unknown")
        doc["remote"].update(revision=None)
        self.assertTrue(any("no page yet" in error for error in check_contract("remote-receipt", doc)))
        doc = json.loads((EXAMPLES / "remote-receipt.json").read_text(encoding="utf-8"))
        doc["remote"]["pageId"] = PAGE
        self.assertTrue(any("only page operations" in error for error in check_contract("remote-receipt", doc)))

    def test_every_page_operation_is_a_receipt_operation(self):
        schema = json.loads((ROOT / "skills/drama-studio/schemas/remote-receipt.schema.json").read_text(encoding="utf-8"))
        operations = schema["properties"]["operation"]["enum"]
        for name in ("create_page", "update_page", "read_page", "list_page_revisions", "label_page_revision", "restore_page"):
            self.assertIn(name, operations)
            self.assertIn(name, receipt.EXPECTED)

    def test_remote_page_is_a_ref_kind_everywhere_and_in_the_examples(self):
        for path in (ROOT / "skills/drama-studio/schemas").glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("remote_page", schema["$defs"]["ref"]["properties"]["kind"]["enum"], path.name)
        for name in ("context-snapshot", "selection", "run-handoff", "task", "review-record"):
            text = (EXAMPLES / f"{name}.json").read_text(encoding="utf-8")
            self.assertIn('"remote_page"', text, name)
            self.assertEqual(check_contract(name, json.loads(text)), [], name)

    def test_snapshot_rejects_mixed_page_revisions_and_unpinned_pages(self):
        doc = json.loads((EXAMPLES / "context-snapshot.json").read_text(encoding="utf-8"))
        extra = copy.deepcopy(doc["items"][0])
        extra["ref"]["revision"] = 1
        extra["partition"] = "project_facts"
        doc["items"].append(extra)
        self.assertTrue(any("mixed revisions" in error for error in check_contract("context-snapshot", doc)))
        doc = json.loads((EXAMPLES / "context-snapshot.json").read_text(encoding="utf-8"))
        doc["items"][0]["ref"]["revision"] = "2"
        self.assertTrue(any("integer revision" in error for error in check_contract("context-snapshot", doc)))


class CacheTests(PageCase):
    def manifest(self):
        return json.loads((self.project / ".drama/cache/manifest.json").read_text(encoding="utf-8"))

    def test_full_read_is_cached_as_page_at_revision_with_a_v1_manifest(self):
        self.record("01-create.response.json", "create_page", "pg-create-1", "01-create.input.json")
        code, result = self.cache(*reversed(R2_CHUNKS))
        self.assertEqual(code, 0, result)
        cached = self.project / f".drama/cache/{PAGE}@r2.md"
        self.assertEqual(cached.read_bytes(), fixture("02-update.input.json")["body"].encode("utf-8"))
        manifest = self.manifest()
        self.assertEqual(manifest["schemaVersion"], "drama-studio/cache-manifest/v1")
        [entry] = manifest["entries"]
        self.assertEqual(set(entry), {"path", "pageId", "revision", "title", "labels", "producer", "sha256", "serverFingerprint",
                                      "verified", "operation", "readAt"})
        self.assertEqual((entry["pageId"], entry["revision"], entry["title"], entry["labels"], entry["producer"], entry["operation"]),
                         (PAGE, 2, "第3集 集纲", [], "external_ai", "read_page"))  # title from the local create_page receipt
        self.assertEqual(entry["sha256"], entry["serverFingerprint"])
        self.assertTrue(entry["verified"])
        self.assertEqual(self.cache(*R2_CHUNKS)[1]["status"], "unchanged")
        self.assertEqual(len(self.manifest()["entries"]), 1)

    def test_incomplete_or_tampered_reads_are_refused(self):
        code, result = self.cache(*R2_CHUNKS[:3])
        self.assertEqual((code, result["status"]), (2, "refused"))
        self.assertIn("final chunk missing", result["error"])
        tampered = fixture(R2_CHUNKS[1])
        tampered["structuredContent"]["data"]["text"] = tampered["structuredContent"]["data"]["text"][::-1]
        path = self.base / "tampered.json"
        path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
        code, result = self.cli("receipt", "cache", str(self.project), *[str(FIXTURES / name) for name in (R2_CHUNKS[0], R2_CHUNKS[2], R2_CHUNKS[3])], str(path))
        self.assertEqual(code, 2)
        self.assertIn("server fingerprint", result["error"])
        self.assertFalse((self.project / ".drama/cache/manifest.json").exists())

    def test_page_chunks_take_no_slot_and_do_not_mix_with_artifacts(self):
        code, result = self.cache(*R2_CHUNKS, extra=("--slot", "ep-03-outline"))
        self.assertEqual(code, 1)
        self.assertIn("pageId and revision", result["error"])
        code, result = self.cli("receipt", "cache", str(self.project), *[str(FIXTURES / name) for name in R2_CHUNKS],
                                str(ROOT / "tests/fixtures/mcp-synthetic/03-get.response.json"))
        self.assertEqual(code, 1)

    def test_v0_manifest_entries_stay_readable_after_a_page_is_cached(self):
        cache = self.project / ".drama/cache"
        cache.mkdir()
        body = "迁移前的历史候选正文".encode("utf-8")
        (cache / "art-old@r1.md").write_bytes(body)
        old = {"path": ".drama/cache/art-old@r1.md", "artifactId": "art-old", "slot": "ep-02-draft", "kind": "episode_draft",
               "episodeRef": "ep-02", "revision": 1, "sha256": sha(body), "serverFingerprint": sha(body), "verified": True,
               "operation": "read_story_artifact", "readAt": "2026-09-30T08:00:00Z", "slotSource": "record"}
        (cache / "manifest.json").write_text(json.dumps({"schemaVersion": "drama-studio/cache-manifest/v0", "entries": [old]}), encoding="utf-8")
        self.assertEqual(self.cache("07-read-r1-chunk-1.response.json", extra=("--title", "第3集 集纲"))[0], 0)
        manifest = self.manifest()
        self.assertEqual(manifest["schemaVersion"], "drama-studio/cache-manifest/v1")
        self.assertEqual(manifest["entries"][0], old)
        task = self.base / "task.json"
        task.write_text((EXAMPLES / "task.json").read_text(encoding="utf-8"), encoding="utf-8")
        selection = self.base / "sel.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "remote_artifact", "id": "art-old", "revision": 1}, "partition": "project_facts", "required": True, "reason": "历史候选"},
            {"ref": {"kind": "remote_page", "id": PAGE, "revision": 1}, "partition": "current_plan", "required": True, "reason": "集纲页面"}]},
            ensure_ascii=False), encoding="utf-8")
        code, result = self.cli("context-pack", str(self.project), "--task", str(task), "--selection", str(selection), "--role", "author",
                                "--budget", "20000", "--dry-run")
        self.assertEqual((code, result["passed"], result["completeness"]), (0, True, "complete"), result)


class PackAndImpactTests(PageCase):
    def setUp(self):
        super().setUp()
        self.cache_both()
        self.task = self.base / "task.json"
        self.task.write_text((EXAMPLES / "task.json").read_text(encoding="utf-8"), encoding="utf-8")

    def cache_both(self):
        self.assertEqual(self.cli("receipt", "cache", str(self.project), str(FIXTURES / "07-read-r1-chunk-1.response.json"))[0], 0)
        self.assertEqual(self.cli("receipt", "cache", str(self.project), *[str(FIXTURES / name) for name in R2_CHUNKS])[0], 0)

    def pack(self, *revisions, name="sel.json"):
        selection = self.base / name
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "remote_page", "id": PAGE, "revision": revision}, "partition": "project_facts", "required": True, "reason": "集纲页面"}
            for revision in revisions]}, ensure_ascii=False), encoding="utf-8")
        return self.cli("context-pack", str(self.project), "--task", str(self.task), "--selection", str(selection), "--role", "author", "--budget", "20000")

    def run_handoff(self, run_id, snapshot_id, outputs=()):
        doc = json.loads((EXAMPLES / "run-handoff.json").read_text(encoding="utf-8"))
        doc.update(runId=run_id, contextSnapshotId=snapshot_id, outputs=[{"kind": "remote_page", "id": PAGE, "revision": r} for r in outputs])
        doc.pop("additionalSnapshotIds", None)
        doc["stateChangeProposals"], doc["changeProposals"] = [], []
        runs = self.project / ".drama/runs"
        runs.mkdir(exist_ok=True)
        (runs / f"{run_id}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_mixing_two_revisions_of_one_page_exits_2_and_writes_nothing(self):
        code, result = self.pack(1, 2)
        self.assertEqual((code, result["passed"]), (2, False))
        self.assertIn("cannot mix revisions of a page", result["errors"][0])
        self.assertFalse((self.project / ".drama/snapshots").exists())

    def test_one_revision_is_packed_by_page_id_and_revision(self):
        code, result = self.pack(2)
        self.assertEqual((code, result["passed"]), (0, True), result)
        snapshot = json.loads(Path(result["snapshot_path"]).read_text(encoding="utf-8"))
        ref = snapshot["items"][1]["ref"]
        self.assertEqual((ref["kind"], ref["id"], ref["revision"]), ("remote_page", PAGE, 2))
        self.assertEqual(ref["sha256"], fixture(R2_CHUNKS[0])["structuredContent"]["data"]["fingerprint"])
        code, result = self.pack(3, name="missing.json")
        self.assertEqual((code, result["completeness"]), (0, "incomplete"))  # r3 is not cached: omitted, never guessed

    def test_page_reference_without_an_integer_revision_is_an_input_error(self):
        selection = self.base / "bad.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "remote_page", "id": PAGE, "revision": None}, "partition": "project_facts", "required": False, "reason": "缺修订"}]}),
            encoding="utf-8")
        code, result = self.cli("context-pack", str(self.project), "--task", str(self.task), "--selection", str(selection), "--role", "author", "--budget", "20000")
        self.assertEqual(code, 1)
        self.assertIn("pageId + revision", result["error"])

    def test_impact_page_marks_snapshots_and_runs_pinning_an_older_revision_stale(self):
        old = self.pack(1, name="old.json")[1]["snapshot_id"]
        new = self.pack(2, name="new.json")[1]["snapshot_id"]
        self.run_handoff("run-old", old)
        self.run_handoff("run-own", old, outputs=(2,))  # read r1 and wrote r2 itself
        self.run_handoff("run-new", new)
        code, result = self.cli("impact", str(self.project), "--page", PAGE, "--revision", "2")
        self.assertEqual(code, 0, result)
        snapshots = {item["snapshotId"]: item["status"] for item in result["snapshots"]}
        runs = {item["runId"]: item["status"] for item in result["runs"]}
        self.assertEqual(snapshots, {old: "stale", new: "current"})
        self.assertEqual(runs, {"run-old": "stale", "run-own": "current", "run-new": "current"})
        reason = next(item for item in result["snapshots"] if item["snapshotId"] == old)["reasons"][0]["reason"]
        self.assertIn(f"旧修订 r1，目标修订为 r2", reason)
        self.assertEqual(result["target"], {"page": PAGE, "revision": 2, "resolvedFrom": "--page/--revision"})
        self.assertIn("不是制作采用", result["note"])
        self.assertEqual((result["read_only"], result["remote_verified"]), (True, False))
        code, other = self.cli("impact", str(self.project), "--page", "page-unseen", "--revision", "2")
        self.assertEqual((code, other["snapshots"], other["runs"]), (0, [], []))
        self.assertTrue(other["warnings"])

    def test_impact_page_arguments_are_checked(self):
        for args in (("--page", PAGE), ("--page", PAGE, "--revision", "0"), ("--page", PAGE, "--revision", "2", "--slot", "s"),
                     ("--page", PAGE, "--revision", "2", "--card", "kc"), ("--page", " ", "--revision", "2")):
            with self.subTest(args):
                self.assertEqual(self.cli("impact", str(self.project), *args)[0], 1)

    def test_status_flags_a_run_pinning_an_older_cached_page_revision(self):
        old = self.pack(1, name="old.json")[1]["snapshot_id"]
        self.run_handoff("run-old", old)
        status = self.cli("status", str(self.project), "--json")[1]
        latest = status["runs"]["latest"]
        self.assertEqual(latest["stalenessCheck"], "newer_revision_cached")
        [newer] = latest["newerRevisions"]
        self.assertEqual((newer["page"], newer["pinnedRevision"], newer["staleAgainstRevision"]), (PAGE, 1, 2))
        self.assertIn(f"--page={PAGE} --revision 2", newer["impactCommand"])
        self.assertEqual(status["nextAction"]["basis"], "stale_run")
        code, text = self.cli("status", str(self.project))
        self.assertIn(f"页面 {PAGE}", text.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
