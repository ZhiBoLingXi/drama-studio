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


if __name__ == "__main__":
    unittest.main()
