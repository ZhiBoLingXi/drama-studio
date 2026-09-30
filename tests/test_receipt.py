import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
FIXTURES = ROOT / "tests/fixtures/mcp-synthetic"
sys.path.insert(0, str(ROOT / "skills/drama-studio/scripts"))
sys.dont_write_bytecode = True
from checks import receipt  # noqa: E402
from checks.contract_check import check_contract  # noqa: E402

SNAPSHOT = "sha256:23c10720efd4880fd3b431374bbc44cfd0552ceb18a2be6f7e67aa9b20894225"
ART1 = "9e3f6a2c-4b1d-4c8e-9a57-2d6b1f0c8e41"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ParserTests(unittest.TestCase):
    def test_every_fixture_is_marked_synthetic(self):
        for path in FIXTURES.glob("*.json"):
            self.assertIn("_synthetic", json.loads(path.read_text(encoding="utf-8")), path.name)

    def test_call_tool_result_prefers_structured_content(self):
        parsed = receipt.parse_response(fixture("02-save.response.json"), "save_story_artifact")
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["httpStatus"], 200)
        self.assertEqual(parsed["data"]["record"]["id"], ART1)
        self.assertIn("structuredContent", parsed["shape"])

    def test_text_only_call_tool_result_unwraps_dispatch_and_rest_envelopes(self):
        value = fixture("02-save.response.json")
        del value["structuredContent"]
        parsed = receipt.parse_response(value, "save_story_artifact")
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["httpStatus"], 200)
        self.assertEqual(parsed["data"]["record"]["requestId"], "d1-save-2")
        self.assertNotIn("V1StGXR8", json.dumps(parsed["data"]))  # REST requestId is the server's, never ours

    def test_bare_data_is_recognised_by_expected_key(self):
        parsed = receipt.parse_response(fixture("02-save-bare.response.json"), "save_story_artifact")
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["data"]["record"]["revision"], 1)
        chunk = fixture("08-read-chunk-3.response.json")
        self.assertEqual(receipt.parse_response(chunk["data"], "read_story_artifact")["data"]["coveredRange"]["from"], 48)
        listing = receipt.parse_response(fixture("04-list.response.json")["structuredContent"]["data"], "list_story_artifacts")
        self.assertEqual(len(listing["data"]["records"]), 2)

    def test_errors_carry_status_code_and_retry_safety(self):
        conflict = receipt.parse_response(fixture("06-conflict.response.json"), "save_story_artifact")
        self.assertEqual((conflict["ok"], conflict["httpStatus"], conflict["errorCode"], conflict["retrySafe"]), (False, 409, "VERSION_CONFLICT", False))
        unknown = receipt.parse_response(fixture("05-unknown.response.json"), "save_story_artifact")
        self.assertEqual((unknown["ok"], unknown["errorCode"]), (False, "MCP_OUTCOME_UNKNOWN"))
        text_only = fixture("05-unknown.response.json")
        del text_only["structuredContent"]
        self.assertEqual(receipt.parse_response(text_only, "save_story_artifact")["errorCode"], "MCP_OUTCOME_UNKNOWN")

    def test_unknown_shape_and_wrong_operation_are_input_errors(self):
        with self.assertRaises(ValueError):
            receipt.parse_response(fixture("09-unknown-shape.response.json"), "save_story_artifact")
        with self.assertRaises(ValueError):  # a read chunk is not a save response
            receipt.parse_response(fixture("08-read-chunk-1.response.json"), "save_story_artifact")

    def test_outcome_mapping(self):
        def parsed(ok, status=None, code=None, safe=None):
            return {"ok": ok, "httpStatus": status, "errorCode": code, "retrySafe": safe}
        self.assertEqual(receipt.outcome_of(parsed(True, 200)), ("confirmed", False))
        self.assertEqual(receipt.outcome_of(parsed(False, 409)), ("rejected_conflict", False))
        self.assertEqual(receipt.outcome_of(parsed(False, None, "VERSION_CONFLICT")), ("rejected_conflict", False))
        self.assertEqual(receipt.outcome_of(parsed(False, None, "MCP_OUTCOME_UNKNOWN", True)), ("unknown", False))
        self.assertEqual(receipt.outcome_of(parsed(False, 502, "OPERATION_FAILED", True)), ("unknown", False))
        self.assertEqual(receipt.outcome_of(None), ("unknown", False))
        self.assertEqual(receipt.outcome_of(parsed(False, 422, "INVALID_INPUT")), ("rejected_other", False))
        self.assertEqual(receipt.outcome_of(parsed(False, 429, "RATE_LIMITED", True)), ("rejected_other", True))

    def test_input_fingerprint_is_canonical_json_without_annotations(self):
        data = fixture("02-save.input.json")
        clean = {k: v for k, v in data.items() if not k.startswith("_")}
        expected = "sha256:" + hashlib.sha256(json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(receipt.input_fingerprint(data), expected)
        self.assertNotEqual(expected, fixture("02-save.response.json")["structuredContent"]["data"]["record"]["requestFingerprint"])

    def test_read_chunk_fixtures_are_consistent(self):
        chunks = [fixture(f"08-read-chunk-{i}.response.json") for i in range(1, 5)]
        datas = [receipt.parse_response(chunk, "read_story_artifact")["data"] for chunk in chunks]
        text = "".join(data["text"] for data in datas)
        self.assertEqual(len(text), datas[0]["totalCharacters"])
        self.assertGreater(len(text.encode("utf-8")), len(text))  # multi-byte text
        self.assertEqual("sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(), datas[0]["fingerprint"])
        self.assertEqual(text, fixture("03-get.response.json")["structuredContent"]["data"]["record"]["body"])


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "demo"
        run = subprocess.run([sys.executable, "-B", str(TOOL), "init-project", str(self.project), "--title", "演示"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.receipts = self.project / ".drama/receipts"

    def record(self, response, operation, request_id, input_name, reconciles=None):
        response_path = response if isinstance(response, Path) else FIXTURES / response
        return receipt.record_receipt(str(self.project), str(response_path), operation, request_id, str(FIXTURES / input_name if isinstance(input_name, str) else input_name), reconciles)

    def input_as(self, input_name, request_id):
        data = fixture(input_name)
        data["request_id"] = request_id
        path = Path(self.temp.name) / f"{request_id}.input.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def save(self, response="02-save.response.json", request_id="d1-save-2", input_name="02-save.input.json"):
        return self.record(response, "save_story_artifact", request_id, input_name)


class RecordTests(ProjectCase):
    def test_confirmed_save_writes_a_valid_receipt(self):
        result = self.save()
        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "written")
        self.assertFalse(result["remote_verified"])
        self.assertFalse(result["adoption_verified"])
        written = json.loads((self.receipts / "d1-save-2.json").read_text(encoding="utf-8"))
        self.assertEqual(written, result["receipt"])
        self.assertEqual(check_contract("remote-receipt", written), [])
        self.assertEqual(written["outcome"], "confirmed")
        self.assertFalse(written["retryAllowed"])
        self.assertEqual(written["remote"], {"projectId": "2f70c1e9fad74f35ae27f", "artifactId": ART1, "revision": 1, "inputSnapshotId": SNAPSHOT})
        self.assertEqual(written["localRef"], {"kind": "remote_artifact", "id": "slot:ep-03-outline", "revision": None})
        self.assertEqual(json.loads(written["notes"])["kind"], "episode_outline")
        self.assertEqual(written["inputFingerprint"], receipt.input_fingerprint(fixture("02-save.input.json")))

    def test_bare_response_records_the_same_remote_identity(self):
        result = self.save("02-save-bare.response.json")
        self.assertEqual(result["receipt"]["remote"]["artifactId"], ART1)
        self.assertEqual(result["receipt"]["outcome"], "confirmed")

    def test_snapshot_provenance_warning_is_non_blocking(self):
        self.assertTrue(any("get_writing_context" in w for w in self.save()["warnings"]))
        ctx = self.record("01-writing-context.response.json", "get_writing_context", "d1-ctx-1", "01-writing-context.input.json")
        self.assertEqual(ctx["receipt"]["remote"]["inputSnapshotId"], SNAPSHOT)
        second = self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        self.assertEqual(second["warnings"], [])

    def test_same_request_same_input_is_a_replay(self):
        self.save()
        before = sha_file(self.receipts / "d1-save-2.json")
        result = self.save()
        self.assertEqual((result["status"], result["passed"]), ("replay", True))
        self.assertEqual(sha_file(self.receipts / "d1-save-2.json"), before)
        self.assertEqual(len(list(self.receipts.iterdir())), 1)

    def test_same_request_different_input_is_refused_unchanged(self):
        self.save()
        before = sha_file(self.receipts / "d1-save-2.json")
        result = self.save(input_name="02-save.changed-input.json")
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "conflict")
        old = receipt.input_fingerprint(fixture("02-save.input.json"))[7:19]
        new = receipt.input_fingerprint(fixture("02-save.changed-input.json"))[7:19]
        self.assertNotEqual(old, new)
        self.assertIn(old, result["error"])
        self.assertIn(new, result["error"])
        self.assertEqual(sha_file(self.receipts / "d1-save-2.json"), before)

    def test_unknown_outcomes_never_allow_retry(self):
        result = self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        self.assertEqual(result["receipt"]["outcome"], "unknown")
        self.assertFalse(result["receipt"]["retryAllowed"])
        self.assertIsNone(result["receipt"]["remote"]["artifactId"])
        self.assertEqual(result["receipt"]["remote"]["inputSnapshotId"], SNAPSHOT)
        empty = Path(self.temp.name) / "empty.json"
        empty.write_text("", encoding="utf-8")
        broken = Path(self.temp.name) / "broken.json"
        broken.write_text("{\"content\": [", encoding="utf-8")
        for index, response in enumerate([Path(self.temp.name) / "missing.json", empty, broken]):
            with self.subTest(response=response.name):
                result = self.record(response, "save_story_artifact", f"lost-{index}", self.input_as("05-unknown.input.json", f"lost-{index}"))
                self.assertEqual((result["receipt"]["outcome"], result["receipt"]["retryAllowed"]), ("unknown", False))
                self.assertEqual(check_contract("remote-receipt", result["receipt"]), [])

    def test_conflict_response_is_rejected_conflict(self):
        result = self.save("06-conflict.response.json", "d1-save-4", self.input_as("02-save.input.json", "d1-save-4"))
        self.assertEqual((result["receipt"]["outcome"], result["receipt"]["retryAllowed"]), ("rejected_conflict", False))

    def test_input_errors_write_nothing(self):
        cases = [("09-unknown-shape.response.json", "d1-x", "02-save.input.json"),
                 ("02-save.response.json", "../escape", "02-save.input.json"),
                 ("02-save.response.json", "other-id", "02-save.input.json")]  # input request_id disagrees
        for response, request_id, input_name in cases:
            with self.subTest(request_id=request_id):
                with self.assertRaises(ValueError):
                    self.save(response, request_id, input_name)
        self.assertFalse(self.receipts.exists() and any(self.receipts.iterdir()))
        with self.assertRaises(ValueError):
            receipt.record_receipt(self.temp.name, str(FIXTURES / "02-save.response.json"), "save_story_artifact", "d1-save-2", str(FIXTURES / "02-save.input.json"))

    def test_project_id_must_be_known(self):
        bare_input = Path(self.temp.name) / "input.json"
        bare_input.write_text(json.dumps({"slot": "a", "input_snapshot_id": SNAPSHOT}), encoding="utf-8")
        with self.assertRaises(ValueError):
            receipt.record_receipt(str(self.project), str(FIXTURES / "05-unknown.response.json"), "save_story_artifact", "d1-save-9", str(bare_input))

    def test_get_reconciles_only_on_matching_request_id(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        wrong = self.record("03-get.response.json", "get_story_artifact", "d1-reconcile-x", "03-get.input.json", reconciles="d1-save-3")
        self.assertFalse(wrong["passed"])
        self.assertFalse((self.receipts / "d1-reconcile-x.json").exists())
        right = self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        self.assertTrue(right["passed"])
        self.assertEqual(right["receipt"]["localRef"], {"kind": "remote_receipt", "id": "d1-save-3", "revision": None})
        self.assertEqual(right["receipt"]["remote"]["revision"], 2)
        self.assertIn("(S)", right["receipt"]["notes"])
        self.assertEqual(check_contract("remote-receipt", right["receipt"]), [])

    def test_list_reconciliation_is_marked_as_host_judgement(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        result = self.record("04-list.response.json", "list_story_artifacts", "d1-list-3", "04-list.input.json", reconciles="d1-save-3")
        self.assertTrue(result["passed"])
        self.assertIn("(M)", result["receipt"]["notes"])

    def test_reconciles_needs_an_existing_local_receipt_and_a_read_operation(self):
        with self.assertRaises(ValueError):
            self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        with self.assertRaises(ValueError):
            self.record("02-save.response.json", "save_story_artifact", "d1-save-2", "02-save.input.json", reconciles="d1-save-3")


class PendingShowTests(ProjectCase):
    def unknown_save(self):
        return self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")

    def test_pending_suggests_reconciliation_by_request_id_and_slot(self):
        self.save()
        self.unknown_save()
        result = receipt.pending(str(self.project))
        self.assertEqual(len(result["pending"]), 1)
        item = result["pending"][0]
        self.assertEqual((item["requestId"], item["slot"], item["operation"]), ("d1-save-3", "ep-03-outline", "save_story_artifact"))
        self.assertEqual(item["projectId"], "2f70c1e9fad74f35ae27f")
        self.assertFalse(item["retryAllowed"])
        tools = [step.get("tool") or step.get("command") for step in item["steps"]]
        self.assertEqual(tools[:2], ["list_story_artifacts", "get_story_artifact"])
        self.assertIn("--reconciles d1-save-3", tools[2])
        self.assertEqual(item["steps"][0]["args"], {"project_id": "2f70c1e9fad74f35ae27f", "slot": "ep-03-outline"})
        self.assertIn("d1-save-3", item["steps"][1]["check"])
        self.assertEqual(item["expectedRevision"], 1)

    def test_reconciled_unknown_is_no_longer_pending(self):
        self.unknown_save()
        self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        result = receipt.pending(str(self.project))
        self.assertEqual(result["pending"], [])
        self.assertEqual(result["resolved"], ["d1-save-3"])

    def test_invalid_receipts_are_listed_not_trusted(self):
        self.unknown_save()
        (self.receipts / "broken.json").write_text("{", encoding="utf-8")
        bad = json.loads((self.receipts / "d1-save-3.json").read_text(encoding="utf-8"))
        bad["requestId"], bad["retryAllowed"] = "d1-save-5", True
        (self.receipts / "d1-save-5.json").write_text(json.dumps(bad), encoding="utf-8")
        result = receipt.pending(str(self.project))
        self.assertEqual([item["requestId"] for item in result["pending"]], ["d1-save-3"])
        self.assertEqual(sorted(Path(item["path"]).name for item in result["invalid"]), ["broken.json", "d1-save-5.json"])
        self.assertNotIn("passed", result)

    def test_show_returns_receipt_and_contract_result(self):
        self.save()
        shown = receipt.show(str(self.project), "d1-save-2")
        self.assertTrue(shown["passed"])
        self.assertEqual(shown["receipt"]["requestId"], "d1-save-2")
        self.assertFalse(shown["adoption_verified"])
        doc = shown["receipt"]
        doc["outcome"], doc["retryAllowed"] = "unknown", True
        (self.receipts / "tampered.json").write_text(json.dumps(doc), encoding="utf-8")
        tampered = receipt.show(str(self.project), "tampered")
        self.assertFalse(tampered["passed"])
        self.assertTrue(tampered["errors"])
        for missing in ("absent", "../d1-save-2"):
            with self.assertRaises(ValueError):
                receipt.show(str(self.project), missing)


CHUNKS = [f"08-read-chunk-{i}.response.json" for i in range(1, 5)]


class CacheTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.cache_dir = self.project / ".drama/cache"
        self.manifest = self.cache_dir / "manifest.json"
        self.body = fixture("03-get.response.json")["structuredContent"]["data"]["record"]["body"]
        self.fingerprint = fixture(CHUNKS[0])["structuredContent"]["data"]["fingerprint"]
        self.cached = self.cache_dir / f"{ART1}@r1.md"

    def cache(self, *names, **meta):
        paths = [str(name) if isinstance(name, Path) else str(FIXTURES / name) for name in names]
        return receipt.cache(str(self.project), paths, **meta)

    def variant(self, name, mutate, label):
        value = fixture(name)
        mutate(value)
        path = Path(self.temp.name) / label
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def assertNothingCached(self):
        self.assertFalse(self.cached.exists())
        self.assertFalse(self.manifest.exists())

    def test_verified_read_sequence_matches_server_fingerprint(self):
        result = self.cache(CHUNKS[2], CHUNKS[0], CHUNKS[3], CHUNKS[1], "03-get.response.json")
        self.assertTrue(result["passed"])
        self.assertEqual(self.cached.read_bytes(), self.body.encode("utf-8"))
        self.assertFalse(self.cached.read_bytes().endswith(b"\n"))
        digest = "sha256:" + sha_file(self.cached)
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schemaVersion"], "drama-studio/cache-manifest/v0")
        entry = manifest["entries"][0]
        self.assertEqual(set(entry), {"path", "artifactId", "slot", "kind", "episodeRef", "revision", "sha256", "serverFingerprint", "verified", "operation", "readAt"})
        self.assertEqual(digest, entry["sha256"])
        self.assertEqual(digest, entry["serverFingerprint"])
        self.assertEqual(digest, self.fingerprint)
        self.assertEqual((entry["path"], entry["slot"], entry["kind"], entry["episodeRef"], entry["revision"]),
                         (f".drama/cache/{ART1}@r1.md", "ep-03-outline", "episode_outline", "ep-03", 1))
        self.assertEqual((entry["verified"], entry["operation"]), (True, "read_story_artifact"))
        self.assertFalse(result["adoption_verified"])

    def test_chunks_alone_need_explicit_slot_and_kind(self):
        with self.assertRaises(ValueError):
            self.cache(*CHUNKS)
        with self.assertRaises(ValueError):  # episode kinds need an episodeRef
            self.cache(*CHUNKS, slot="ep-03-outline", kind="episode_outline")
        result = self.cache(*CHUNKS, slot="ep-03-outline", kind="episode_outline", episode_ref="ep-03")
        self.assertTrue(result["entry"]["verified"])

    def test_tampered_chunk_is_refused_and_nothing_written(self):
        def same_length(value):
            data = value["structuredContent"]["data"]
            data["text"] = "假" + data["text"][1:]
        def shorter(value):
            value["data"]["text"] = value["data"]["text"][:-1]
        for label, name, mutate in [("same.json", CHUNKS[0], same_length), ("short.json", CHUNKS[2], shorter)]:
            with self.subTest(label=label):
                chunks = [self.variant(name, mutate, label) if c == name else c for c in CHUNKS]
                result = self.cache(*chunks, "03-get.response.json")
                self.assertFalse(result["passed"])
                self.assertNothingCached()

    def test_gap_missing_final_chunk_and_conflicting_duplicate_are_refused(self):
        def edit(value):
            data = value["structuredContent"]["data"]
            data["text"] = "假" + data["text"][1:]
        tampered = self.variant(CHUNKS[0], edit, "dup.json")
        for label, names in [("missing final", CHUNKS[:3]), ("gap", [CHUNKS[0], CHUNKS[1], CHUNKS[3]]),
                             ("no start", CHUNKS[1:]), ("conflicting duplicate", [*CHUNKS, tampered])]:
            with self.subTest(label=label):
                result = self.cache(*names, "03-get.response.json")
                self.assertFalse(result["passed"])
                self.assertNothingCached()

    def test_identical_duplicate_chunks_are_dropped(self):
        self.assertTrue(self.cache(*CHUNKS, CHUNKS[1], "03-get.response.json")["passed"])

    def test_get_must_describe_the_same_text(self):
        result = self.cache(*CHUNKS, "07-reconcile-get.response.json")
        self.assertFalse(result["passed"])
        self.assertNothingCached()

    def test_get_only_cache_is_unverified(self):
        result = self.cache("03-get.response.json")
        self.assertTrue(result["passed"])
        entry = result["entry"]
        self.assertEqual((entry["verified"], entry["serverFingerprint"], entry["operation"]), (False, None, "get_story_artifact"))
        self.assertTrue(any("read_story_artifact" in warning for warning in result["warnings"]))
        self.assertEqual(self.cached.read_bytes(), self.body.encode("utf-8"))

    def test_recache_is_idempotent_and_manifest_is_append_only(self):
        self.cache(*CHUNKS, "03-get.response.json")
        before = self.manifest.read_bytes()
        again = self.cache(*CHUNKS, "03-get.response.json")
        self.assertEqual((again["status"], again["manifestAppended"]), ("unchanged", False))
        self.assertEqual(self.manifest.read_bytes(), before)
        first = json.loads(before)["entries"][0]
        self.cache("03-get.response.json")
        entries = json.loads(self.manifest.read_text(encoding="utf-8"))["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], first)
        self.assertEqual(entries[1]["verified"], False)

    def test_existing_cache_with_different_bytes_is_refused(self):
        self.cache_dir.mkdir()
        self.cached.write_bytes("别人的内容".encode("utf-8"))
        result = self.cache(*CHUNKS, "03-get.response.json")
        self.assertFalse(result["passed"])
        self.assertEqual(self.cached.read_bytes(), "别人的内容".encode("utf-8"))
        self.assertFalse(self.manifest.exists())

    def test_input_errors(self):
        def unsafe(value):
            value["structuredContent"]["data"]["artifactId"] = "../escape"
        def failed(value):
            value["structuredContent"] = fixture("06-conflict.response.json")["structuredContent"]
        for label, mutate in [("unsafe.json", unsafe), ("failed.json", failed)]:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.cache(self.variant(CHUNKS[0], mutate, label), *CHUNKS[1:], "03-get.response.json")
        with self.assertRaises(ValueError):
            self.cache("09-unknown-shape.response.json")
        with self.assertRaises(ValueError):
            self.cache("03-get.response.json", "07-reconcile-get.response.json")
        self.assertNothingCached()


class ReceiptCliTests(ProjectCase):
    def cli(self, *args):
        run = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
        output = run.stdout if run.stdout.strip().startswith("{") else run.stderr
        return run.returncode, (json.loads(output) if output.strip().startswith("{") else output), run

    def cli_record(self, response, request_id="d1-save-2", input_name="02-save.input.json", operation="save_story_artifact", *extra):
        return self.cli("receipt", "record", self.project, FIXTURES / response, "--operation", operation,
                        "--request-id", request_id, "--input", FIXTURES / input_name, *extra)

    def test_help_lists_the_receipt_commands(self):
        run = subprocess.run([sys.executable, "-B", str(TOOL), "receipt", "--help"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        for command in ("record", "pending", "cache", "show"):
            self.assertIn(command, run.stdout)
        self.assertIn("receipt", subprocess.run([sys.executable, "-B", str(TOOL), "--help"], capture_output=True, text=True).stdout)

    def test_record_replay_and_conflict_exit_codes(self):
        code, result, _ = self.cli_record("02-save.response.json")
        self.assertEqual((code, result["status"]), (0, "written"))
        before = sha_file(self.receipts / "d1-save-2.json")
        code, result, _ = self.cli_record("02-save.response.json")
        self.assertEqual((code, result["status"]), (0, "replay"))
        code, result, run = self.cli_record("02-save.response.json", "d1-save-2", "02-save.changed-input.json")
        self.assertEqual(code, 2)
        self.assertIn(receipt.input_fingerprint(fixture("02-save.input.json"))[7:19], run.stdout)
        self.assertIn(receipt.input_fingerprint(fixture("02-save.changed-input.json"))[7:19], run.stdout)
        self.assertEqual(sha_file(self.receipts / "d1-save-2.json"), before)

    def test_unknown_shape_exits_1_and_missing_response_is_unknown(self):
        code, result, _ = self.cli_record("09-unknown-shape.response.json")
        self.assertEqual((code, result["ok"]), (1, False))
        self.assertFalse(self.receipts.exists() and any(self.receipts.iterdir()))
        code, result, _ = self.cli_record("does-not-exist.json", "d1-save-3", "05-unknown.input.json")
        self.assertEqual((code, result["receipt"]["outcome"], result["receipt"]["retryAllowed"]), (0, "unknown", False))

    def test_pending_reconcile_and_show(self):
        self.cli_record("05-unknown.response.json", "d1-save-3", "05-unknown.input.json")
        code, result, _ = self.cli("receipt", "pending", self.project)
        self.assertEqual(code, 0)
        self.assertEqual((result["pending"][0]["requestId"], result["pending"][0]["slot"]), ("d1-save-3", "ep-03-outline"))
        code, _, _ = self.cli_record("03-get.response.json", "d1-reconcile-x", "03-get.input.json", "get_story_artifact", "--reconciles", "d1-save-3")
        self.assertEqual(code, 2)
        code, _, _ = self.cli_record("07-reconcile-get.response.json", "d1-reconcile-3", "07-reconcile-get.input.json", "get_story_artifact", "--reconciles", "d1-save-3")
        self.assertEqual(code, 0)
        self.assertEqual(self.cli("receipt", "pending", self.project)[1]["pending"], [])
        code, result, _ = self.cli("receipt", "show", self.project, "d1-reconcile-3")
        self.assertEqual((code, result["passed"]), (0, True))
        self.assertEqual(self.cli("receipt", "show", self.project, "absent")[0], 1)

    def test_cache_exit_codes(self):
        chunks = [FIXTURES / name for name in CHUNKS]
        self.assertEqual(self.cli("receipt", "cache", self.project, *chunks[:3], FIXTURES / "03-get.response.json")[0], 2)
        code, result, _ = self.cli("receipt", "cache", self.project, *chunks, FIXTURES / "03-get.response.json")
        self.assertEqual((code, result["entry"]["verified"]), (0, True))
        code, result, _ = self.cli("receipt", "cache", self.project, *chunks, "--slot", "ep-03-outline", "--kind", "episode_outline", "--episode-ref", "ep-03")
        self.assertEqual((code, result["status"]), (0, "unchanged"))
        self.assertEqual(self.cli("receipt", "cache", self.project, *chunks)[0], 1)

    def test_doctor_still_offline(self):
        code, result, _ = self.cli("doctor")
        self.assertEqual(code, 0)
        self.assertFalse(result["network_used"])
        self.assertFalse(result["models_called"])


if __name__ == "__main__":
    unittest.main()
