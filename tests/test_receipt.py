import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_contradictory_responses_are_unparseable(self):
        flagged = fixture("02-save.response.json")
        flagged["isError"] = True
        status = fixture("02-save.response.json")
        status["structuredContent"]["transport"]["status"] = 500
        for label, value in [("isError with ok", flagged), ("status >= 400 with ok", status)]:
            with self.subTest(label):
                with self.assertRaises(receipt.Unparseable):
                    receipt.parse_response(value, "save_story_artifact")

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
        self.assertEqual(json.loads(written["notes"])["slotCheck"], "record.slot matched --input slot (S)")
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
        self.assertEqual(result["warnings"], [])  # a refused call carries only the refusal
        self.assertEqual(sha_file(self.receipts / "d1-save-2.json"), before)

    def test_invalid_existing_receipt_is_never_a_replay(self):
        self.save()
        path = self.receipts / "d1-save-2.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["extra"] = True
        for label, content in [("fails contract-check", json.dumps(tampered)), ("not an object", "[]"), ("not JSON", "{")]:
            with self.subTest(label):
                path.write_text(content, encoding="utf-8")
                result = self.save()
                self.assertEqual((result["passed"], result["status"]), (False, "invalid_existing"))
                self.assertIn("receipt show", result["error"])
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_publish_race_is_re_evaluated_as_replay_or_conflict(self):
        self.save()
        mine = (self.receipts / "d1-save-2.json").read_bytes()
        (self.receipts / "d1-save-2.json").unlink()
        real = os.link
        for label, input_name, status in [("same input", "02-save.input.json", "replay"),
                                          ("different input", "02-save.changed-input.json", "conflict")]:
            with self.subTest(label):
                def link(src, dst):
                    Path(dst).write_bytes(mine)  # another writer publishes first
                    return real(src, dst)
                with mock.patch("os.link", link):
                    result = self.save(input_name=input_name)
                self.assertEqual(result["status"], status)
                self.assertEqual((self.receipts / "d1-save-2.json").read_bytes(), mine)
                self.assertEqual([p.name for p in self.receipts.iterdir()], ["d1-save-2.json"])
                (self.receipts / "d1-save-2.json").unlink()

    def test_publish_falls_back_when_hard_links_are_unsupported(self):
        with mock.patch("os.link", side_effect=PermissionError("links not supported")):
            result = self.save()
            self.assertEqual(result["status"], "written")
            self.assertEqual(json.loads((self.receipts / "d1-save-2.json").read_text(encoding="utf-8")), result["receipt"])
            self.assertEqual(self.save()["status"], "replay")
            taken = self.receipts / "taken.json"
            taken.write_text("mine", encoding="utf-8")
            self.assertFalse(receipt.publish_new(taken, b"theirs"))
        self.assertEqual(taken.read_text(encoding="utf-8"), "mine")
        self.assertEqual(sorted(p.name for p in self.receipts.iterdir()), ["d1-save-2.json", "taken.json"])

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

    def test_utf8_bom_files_are_read(self):
        response, request = Path(self.temp.name) / "bom.json", Path(self.temp.name) / "bom-input.json"
        response.write_bytes(b"\xef\xbb\xbf" + (FIXTURES / "02-save.response.json").read_bytes())
        request.write_bytes(b"\xef\xbb\xbf" + (FIXTURES / "02-save.input.json").read_bytes())
        result = self.save(response, "d1-save-2", request)
        self.assertEqual(result["receipt"]["outcome"], "confirmed")
        self.assertEqual(result["receipt"]["inputFingerprint"], receipt.input_fingerprint(fixture("02-save.input.json")))
        chunks = []
        for name in CHUNKS:
            chunk = Path(self.temp.name) / name
            chunk.write_bytes(b"\xef\xbb\xbf" + (FIXTURES / name).read_bytes())
            chunks.append(str(chunk))
        self.assertTrue(receipt.cache(str(self.project), chunks + [str(FIXTURES / "03-get.response.json")])["passed"])

    def test_contradictory_response_records_unknown(self):
        value = fixture("02-save.response.json")
        value["isError"] = True
        path = Path(self.temp.name) / "contradictory.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        result = self.save(path)
        self.assertEqual((result["receipt"]["outcome"], result["receipt"]["retryAllowed"]), ("unknown", False))
        self.assertIn("contradict", result["receipt"]["evidence"])

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

    def test_confirmed_save_whose_record_slot_differs_from_the_input_is_refused(self):
        def variant(label, **changes):
            data = fixture("02-save.input.json")
            data.update(changes)
            path = Path(self.temp.name) / label
            path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}, ensure_ascii=False), encoding="utf-8")
            return path
        for label, path in [("other slot", variant("other.json", slot="ep-04-outline")), ("no slot", variant("none.json", slot=None))]:
            for response in ("02-save.response.json", "02-save-bare.response.json"):
                with self.subTest(label=label, response=response):
                    with self.assertRaisesRegex(ValueError, "record.slot is 'ep-03-outline'"):
                        self.save(response, "d1-save-2", path)
                    self.assertFalse(self.receipts.exists() and any(self.receipts.iterdir()))
        run = subprocess.run([sys.executable, "-B", str(TOOL), "receipt", "record", str(self.project), str(FIXTURES / "02-save.response.json"),
                              "--operation", "save_story_artifact", "--request-id", "d1-save-2", "--input", str(variant("cli.json", slot="ep-04-outline"))],
                             capture_output=True, text=True)
        self.assertEqual((run.returncode, run.stdout), (1, ""))
        self.assertIn("ep-04-outline", json.loads(run.stderr)["error"])
        self.assertFalse(self.receipts.exists() and any(self.receipts.iterdir()))
        # nothing to compare when the outcome is unknown: the receipt records the input's slot as before
        unknown = self.record("05-unknown.response.json", "save_story_artifact", "d1-save-2", variant("unknown.json", slot="ep-04-outline"))
        self.assertEqual((unknown["receipt"]["outcome"], unknown["receipt"]["localRef"]["id"]), ("unknown", "slot:ep-04-outline"))
        self.assertEqual(receipt.cache(str(self.project), [str(FIXTURES / name) for name in CHUNKS], slot="ep-04-outline",
                                       kind="episode_outline", episode_ref="ep-03")["entry"]["slotSource"], "host")

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

    def list_input(self, **changes):
        data = fixture("04-list.input.json")
        data.update(changes)
        data = {k: v for k, v in data.items() if v is not None}
        path = Path(self.temp.name) / f"list-{len(changes)}-{abs(hash(json.dumps(changes)))}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def list_response(self, mutate_rows, label):
        value = fixture("04-list.response.json")
        data = value["structuredContent"]["data"]
        data["records"] = mutate_rows(data["records"])
        path = Path(self.temp.name) / label
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def test_list_needs_a_newer_row_in_the_slot_from_the_same_snapshot(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        cases = {"empty list": lambda rows: [],
                 "only older revisions": lambda rows: [rows[0]],
                 "other slot": lambda rows: [dict(row, slot="ep-04-outline") for row in rows],
                 "other snapshot": lambda rows: [dict(row, inputSnapshotId="sha256:" + "0" * 64) for row in rows]}
        for label, mutate_rows in cases.items():
            with self.subTest(label):
                response = self.list_response(mutate_rows, f"{label}.json")
                result = self.record(response, "list_story_artifacts", "d1-list-3", "04-list.input.json", reconciles="d1-save-3")
                self.assertEqual((result["passed"], result["status"]), (False, "reconcile_refused"))
                self.assertIn("re-send the identical save", result["error"].lower())
                self.assertFalse((self.receipts / "d1-list-3.json").exists())
        result = self.record("04-list.response.json", "list_story_artifacts", "d1-list-3", "04-list.input.json", reconciles="d1-save-3")
        notes = json.loads(result["receipt"]["notes"])
        self.assertEqual((notes["matchedArtifactId"], notes["matchedRevision"]), ("c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d", 2))
        self.assertIn("(M)", notes["check"])

    def test_reconcilers_need_evidence(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        self.save()  # confirmed d1-save-2
        self.record(Path(self.temp.name) / "missing.json", "get_story_artifact", "get-lost", self.input_as("03-get.input.json", "get-lost"))
        broken = json.loads((self.receipts / "d1-save-3.json").read_text(encoding="utf-8"))
        broken.update(requestId="d1-save-8", retryAllowed=True)
        (self.receipts / "d1-save-8.json").write_text(json.dumps(broken), encoding="utf-8")
        missing = Path(self.temp.name) / "missing.json"
        cases = {"unknown list response": (missing, "list_story_artifacts", "d1-save-3", "04-list.input.json"),
                 "unknown get response": (missing, "get_story_artifact", "d1-save-3", "07-reconcile-get.input.json"),
                 "target is not unknown": ("04-list.response.json", "list_story_artifacts", "d1-save-2", "04-list.input.json"),
                 "target fails contract-check": ("04-list.response.json", "list_story_artifacts", "d1-save-8", "04-list.input.json"),
                 "target is not a save": ("04-list.response.json", "list_story_artifacts", "get-lost", "04-list.input.json"),
                 "list project differs": ("04-list.response.json", "list_story_artifacts", "d1-save-3", self.list_input(project_id="other-project")),
                 "list slot differs": ("04-list.response.json", "list_story_artifacts", "d1-save-3", self.list_input(slot="ep-04-outline")),
                 "list without slot": ("04-list.response.json", "list_story_artifacts", "d1-save-3", self.list_input(slot=None))}
        for label, (response, operation, target, input_name) in cases.items():
            with self.subTest(label):
                result = self.record(response, operation, "reconciler-1", input_name, reconciles=target)
                self.assertFalse(result["passed"], result)
                self.assertFalse((self.receipts / "reconciler-1.json").exists())
        result = receipt.pending(str(self.project))
        self.assertEqual([item["requestId"] for item in result["pending"]], ["d1-save-3"])
        self.assertEqual([item["requestId"] for item in result["read_only_unknown"]], ["get-lost"])

    def test_reconciles_needs_an_existing_local_receipt_and_a_reconciling_operation(self):
        with self.assertRaises(ValueError):
            self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        with self.assertRaises(ValueError):
            self.record("01-writing-context.response.json", "get_writing_context", "d1-ctx-1", "01-writing-context.input.json", reconciles="d1-save-3")

    def test_confirmed_resend_is_not_swallowed_as_replay(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        before = sha_file(self.receipts / "d1-save-3.json")
        result = self.record("10-resend-save.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        self.assertEqual((result["passed"], result["status"]), (False, "outcome_differs"))
        self.assertEqual((result["existingOutcome"], result["newOutcome"]), ("unknown", "confirmed"))
        self.assertIn("--reconciles", result["error"])
        self.assertEqual(sha_file(self.receipts / "d1-save-3.json"), before)

    def resend(self, response="10-resend-save.response.json", input_path="05-unknown.input.json"):
        return self.record(response, "save_story_artifact", "d1-save-3.resend-1", input_path, reconciles="d1-save-3")

    def test_identical_resend_reconciles_the_unknown_save(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        result = self.resend()
        self.assertTrue(result["passed"], result)
        doc = result["receipt"]
        self.assertEqual((doc["outcome"], doc["remote"]["revision"]), ("confirmed", 2))
        self.assertEqual(doc["localRef"], {"kind": "remote_receipt", "id": "d1-save-3", "revision": None})
        self.assertIn("(S)", doc["notes"])
        self.assertEqual(doc["inputFingerprint"], receipt.input_fingerprint(fixture("05-unknown.input.json")))
        self.assertEqual(check_contract("remote-receipt", doc), [])

    def test_non_confirmed_resend_is_recorded_but_resolves_nothing(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        for index, response in enumerate(["05-unknown.response.json", "06-conflict.response.json"], 1):
            with self.subTest(response):
                result = self.record(response, "save_story_artifact", f"d1-save-3.resend-{index}", "05-unknown.input.json", reconciles="d1-save-3")
                self.assertTrue(result["passed"], result)
                self.assertNotEqual(result["receipt"]["outcome"], "confirmed")
                self.assertIn("does not resolve", json.loads(result["receipt"]["notes"])["check"])
        pending = receipt.pending(str(self.project))
        self.assertEqual([item["requestId"] for item in pending["pending"]], ["d1-save-3"])
        self.assertEqual(pending["pending"][0]["unconfirmedAttempts"], ["d1-save-3.resend-1", "d1-save-3.resend-2"])
        self.assertEqual(pending["resolved_verified"], [])
        changed = fixture("05-unknown.input.json")
        changed["body"] += "！"
        changed_path = Path(self.temp.name) / "changed.json"
        changed_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        self.assertFalse(self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3.resend-9", changed_path, reconciles="d1-save-3")["passed"])

    def test_resend_script_checks(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        changed = fixture("05-unknown.input.json")
        changed["body"] += "！"
        changed_path = Path(self.temp.name) / "changed.json"
        changed_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        cases = {"input request_id is not the original": ("10-resend-save.response.json", self.input_as("05-unknown.input.json", "d1-save-3.resend-1")),
                 "input differs from the unknown save": ("10-resend-save.response.json", changed_path),
                 "record.requestId is not the original": ("02-save.response.json", FIXTURES / "05-unknown.input.json")}
        for label, (response, input_path) in cases.items():
            with self.subTest(label):
                result = self.resend(response, input_path)
                self.assertFalse(result["passed"])
                self.assertFalse((self.receipts / "d1-save-3.resend-1.json").exists())


class ContainmentTests(ProjectCase):
    def outside(self, name):
        path = Path(self.temp.name) / "outside" / name
        path.mkdir(parents=True)
        return path

    def test_symlinked_folders_outside_the_project_are_refused(self):
        (self.project / ".drama/receipts").symlink_to(self.outside("receipts"), target_is_directory=True)
        (self.project / ".drama/cache").symlink_to(self.outside("cache"), target_is_directory=True)
        calls = {"record": lambda: self.save(), "pending": lambda: receipt.pending(str(self.project)),
                 "show": lambda: receipt.show(str(self.project), "d1-save-2"),
                 "cache": lambda: receipt.cache(str(self.project), [str(FIXTURES / name) for name in CHUNKS] + [str(FIXTURES / "03-get.response.json")])}
        for label, call in calls.items():
            with self.subTest(label):
                with self.assertRaisesRegex(ValueError, "outside the project"):
                    call()
        self.assertEqual(list((Path(self.temp.name) / "outside").rglob("*.*")), [])

    def test_symlinked_receipt_file_outside_the_project_is_refused(self):
        self.receipts.mkdir()
        elsewhere = self.outside("files") / "d1-save-2.json"
        elsewhere.write_text("{}", encoding="utf-8")
        (self.receipts / "d1-save-2.json").symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError, "outside the project"):
            self.save()
        with self.assertRaisesRegex(ValueError, "outside the project"):
            receipt.show(str(self.project), "d1-save-2")
        self.assertEqual(elsewhere.read_text(encoding="utf-8"), "{}")


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
        self.assertEqual((result["resolved_verified"], result["resolved_host_judged"]), (["d1-save-3"], []))

    def test_resolutions_are_split_by_strength_and_need_a_confirmed_reconciler(self):
        self.unknown_save()
        self.record("04-list.response.json", "list_story_artifacts", "d1-list-3", "04-list.input.json", reconciles="d1-save-3")
        result = receipt.pending(str(self.project))
        self.assertEqual((result["resolved_verified"], result["resolved_host_judged"], result["pending"]), ([], ["d1-save-3"], []))
        # a hand-written unconfirmed reconciler resolves nothing
        forged = json.loads((self.receipts / "d1-list-3.json").read_text(encoding="utf-8"))
        forged.update(requestId="d1-list-4", outcome="unknown", retryAllowed=False)
        forged["localRef"]["id"] = "d1-save-9"
        (self.receipts / "d1-list-4.json").write_text(json.dumps(forged), encoding="utf-8")
        nine = json.loads((self.receipts / "d1-save-3.json").read_text(encoding="utf-8"))
        nine["requestId"] = "d1-save-9"
        (self.receipts / "d1-save-9.json").write_text(json.dumps(nine), encoding="utf-8")
        result = receipt.pending(str(self.project))
        self.assertEqual([item["requestId"] for item in result["pending"]], ["d1-save-9"])
        self.assertEqual([item["requestId"] for item in result["read_only_unknown"]], ["d1-list-4"])

    def test_pending_re_verifies_stored_reconciliation_evidence(self):
        self.unknown_save()
        self.record("07-reconcile-get.response.json", "get_story_artifact", "d1-reconcile-3", "07-reconcile-get.input.json", reconciles="d1-save-3")
        good = json.loads((self.receipts / "d1-reconcile-3.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(good["notes"])["observedRequestId"], "d1-save-3")
        (self.receipts / "d1-reconcile-3.json").unlink()
        forged_notes = dict(json.loads(good["notes"]), observedRequestId="someone-else")
        cases = {"forged-id": dict(good, notes=json.dumps(forged_notes)),
                 "other-project": dict(good, remote=dict(good["remote"], projectId="other-project"))}
        for name, doc in cases.items():
            (self.receipts / f"{name}.json").write_text(json.dumps(dict(doc, requestId=name)), encoding="utf-8")
        result = receipt.pending(str(self.project))
        self.assertEqual(result["resolved_verified"], [])
        self.assertEqual([item["requestId"] for item in result["pending"]], ["d1-save-3"])
        reasons = {Path(item["path"]).stem: " ".join(item["errors"]) for item in result["invalid"]}
        self.assertIn("observedRequestId", reasons["forged-id"])
        self.assertIn("projectId", reasons["other-project"])

    def test_prepare_story_context_unknown_is_unreconcilable(self):
        prepare = Path(self.temp.name) / "prepare.json"
        prepare.write_text(json.dumps({"project_id": "2f70c1e9fad74f35ae27f"}), encoding="utf-8")
        self.record(Path(self.temp.name) / "missing.json", "prepare_story_context", "prep-1", prepare)
        result = receipt.pending(str(self.project))
        self.assertEqual((result["pending"], result["read_only_unknown"]), ([], []))
        self.assertEqual(result["unreconcilable_unknown"], [{
            "requestId": "prep-1", "operation": "prepare_story_context", "projectId": "2f70c1e9fad74f35ae27f", "retryAllowed": False,
            "note": "prepare_story_context has no requestId lookup; re-read the context state (get_writing_context) before any retry"}])

    def test_read_only_unknowns_get_no_save_style_steps(self):
        self.unknown_save()
        self.record(Path(self.temp.name) / "missing.json", "read_story_artifact", "read-lost",
                    self.input_as("07-reconcile-get.input.json", "read-lost"))
        result = receipt.pending(str(self.project))
        self.assertEqual([item["requestId"] for item in result["pending"]], ["d1-save-3"])
        self.assertEqual(result["read_only_unknown"], [{"requestId": "read-lost", "operation": "read_story_artifact",
                                                        "projectId": "2f70c1e9fad74f35ae27f", "retryAllowed": False,
                                                        "note": "re-read; no write to reconcile"}])

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
        self.assertEqual(set(entry), {"path", "artifactId", "slot", "kind", "episodeRef", "revision", "sha256", "serverFingerprint", "verified", "operation", "readAt", "slotSource"})
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

    def test_empty_chunk_at_the_end_is_accepted(self):
        def at_end(value):
            data = value["structuredContent"]["data"]
            end = data["totalCharacters"]
            data.update(offset=end, text="", nextOffset=None, atEnd=True, coveredRange={"from": end, "to": end})
        empty = self.variant(CHUNKS[3], at_end, "empty-end.json")
        result = self.cache(*CHUNKS, empty, "03-get.response.json")
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["entry"]["verified"])
        self.assertEqual(self.cached.read_bytes(), self.body.encode("utf-8"))

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
        downgrade = self.cache("03-get.response.json")  # a later get must not shadow the verified read
        self.assertEqual((downgrade["status"], downgrade["manifestAppended"], downgrade["entry"]["verified"]), ("unchanged", False, True))
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_published_files_are_world_readable(self):
        self.save()
        self.cache(*CHUNKS, "03-get.response.json")
        with mock.patch("os.link", side_effect=PermissionError("links not supported")):
            self.save("05-unknown.response.json", "d1-save-3", "05-unknown.input.json")
        for path in (self.receipts / "d1-save-2.json", self.receipts / "d1-save-3.json", self.cached, self.manifest):
            with self.subTest(path.name):
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_metadata_must_match_existing_entries(self):
        self.cache(*CHUNKS, "03-get.response.json")
        before = self.manifest.read_bytes()
        meta = {"slot": "ep-03-outline", "kind": "episode_outline", "episode_ref": "ep-03"}
        for key, value, field in [("slot", "other-slot", "slot"), ("kind", "episode_draft", "kind"), ("episode_ref", "ep-99", "episodeRef")]:
            with self.subTest(field):
                result = self.cache(*CHUNKS, **dict(meta, **{key: value}))
                self.assertFalse(result["passed"])
                self.assertIn(field, result["error"])
                self.assertIn(value, result["error"])
                self.assertEqual(self.manifest.read_bytes(), before)

    def test_verified_read_after_get_only_is_appended_last(self):
        self.cache("03-get.response.json")
        result = self.cache(*CHUNKS, "03-get.response.json")
        self.assertEqual((result["status"], result["manifestAppended"]), ("unchanged", True))
        entries = json.loads(self.manifest.read_text(encoding="utf-8"))["entries"]
        self.assertEqual([entry["verified"] for entry in entries], [False, True])

    def test_existing_cache_with_different_bytes_is_refused(self):
        self.cache_dir.mkdir()
        self.cached.write_bytes("别人的内容".encode("utf-8"))
        result = self.cache(*CHUNKS, "03-get.response.json")
        self.assertFalse(result["passed"])
        self.assertEqual(self.cached.read_bytes(), "别人的内容".encode("utf-8"))
        self.assertFalse(self.manifest.exists())

    def racing_link(self, content):
        """os.link that lets another writer publish `content` first, as a concurrent process would."""
        real = os.link
        def link(src, dst):
            Path(dst).write_bytes(content)
            return real(src, dst)
        return mock.patch("os.link", link)

    def test_cache_file_race_is_refused_not_overwritten(self):
        with self.racing_link("别人的内容".encode("utf-8")):
            result = self.cache(*CHUNKS, "03-get.response.json")
        self.assertFalse(result["passed"])
        self.assertEqual(self.cached.read_bytes(), "别人的内容".encode("utf-8"))
        self.assertEqual([p.name for p in self.cache_dir.iterdir()], [self.cached.name])  # no temp or lock left

    def test_held_manifest_lock_stops_the_cache(self):
        self.cache_dir.mkdir()
        lock = self.cache_dir / "manifest.json.lock"
        lock.write_text("other", encoding="utf-8")
        with mock.patch.object(receipt, "LOCK_TIMEOUT", 0.1):
            with self.assertRaises(ValueError) as caught:
                self.cache(*CHUNKS, "03-get.response.json")
        self.assertIn("manifest.json.lock", str(caught.exception))
        self.assertTrue(lock.exists())  # never auto-deleted
        self.assertNothingCached()
        lock.unlink()
        self.assertTrue(self.cache(*CHUNKS, "03-get.response.json")["passed"])
        self.assertFalse(lock.exists())

    META = {"slot": "ep-03-outline", "kind": "episode_outline", "episode_ref": "ep-03"}

    def entries(self):
        return json.loads(self.manifest.read_text(encoding="utf-8"))["entries"]

    def test_slot_source_is_record_when_a_get_response_is_given(self):
        self.assertEqual(self.cache(*CHUNKS, "03-get.response.json")["entry"]["slotSource"], "record")
        self.assertEqual(self.cache("03-get.response.json")["entry"]["slotSource"], "record")
        self.assertEqual([entry["slotSource"] for entry in self.entries()], ["record"])

    def test_slot_source_is_host_when_only_chunks_and_no_save_receipt(self):
        result = self.cache(*CHUNKS, **self.META)
        self.assertEqual((result["passed"], result["entry"]["slotSource"]), (True, "host"))
        self.assertTrue(any("slotSource" in warning and "get_story_artifact" in warning for warning in result["warnings"]))
        self.assertEqual(self.cache(*CHUNKS, "03-get.response.json")["warnings"], [])

    def test_slot_source_is_receipt_when_a_confirmed_save_receipt_agrees(self):
        self.save()
        result = self.cache(*CHUNKS, **self.META)
        self.assertEqual((result["passed"], result["entry"]["slotSource"], result["warnings"]), (True, "receipt", []))

    def test_slot_disagreeing_with_the_save_receipt_is_refused(self):
        self.save()
        result = self.cache(*CHUNKS, **dict(self.META, slot="ep-04-outline"))
        self.assertEqual((result["passed"], result["status"]), (False, "refused"))
        for needle in ("ep-04-outline", "ep-03-outline", "d1-save-2"):
            self.assertIn(needle, result["error"])
        self.assertNothingCached()

    def test_only_a_valid_confirmed_save_of_the_same_artifact_vouches_for_the_slot(self):
        self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")  # unknown: no artifactId
        self.record("03-get.response.json", "get_story_artifact", "d1-get-1", "03-get.input.json")  # a read, not a save
        self.save()
        path = self.receipts / "d1-save-2.json"
        good = json.loads(path.read_text(encoding="utf-8"))
        cases = {"fails contract-check": dict(good, extra=True),
                 "other artifact": dict(good, remote=dict(good["remote"], artifactId="c41d2b7a-8e5f-4a3b-b6d9-0f1e2a3b4c5d")),
                 "other revision": dict(good, remote=dict(good["remote"], revision=2)),
                 "other project": dict(good, remote=dict(good["remote"], projectId="other-project")),
                 "not confirmed": dict(good, outcome="rejected_other"),
                 "written before the slot check existed": dict(good, notes=json.dumps({k: v for k, v in json.loads(good["notes"]).items() if k != "slotCheck"})),
                 "no notes at all": {k: v for k, v in good.items() if k != "notes"}}
        for index, (label, doc) in enumerate(cases.items()):
            with self.subTest(label):
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                result = self.cache(*CHUNKS, **self.META)
                self.assertEqual((result["passed"], result["entry"]["slotSource"]), (True, "host"))
                self.assertEqual(len(self.entries()), 1)

    def test_save_response_without_record_slot_yields_a_receipt_that_does_not_vouch(self):
        def no_slot(value):
            del value["structuredContent"]["data"]["record"]["slot"]
        result = self.save(self.variant("02-save.response.json", no_slot, "no-slot.json"))
        self.assertEqual((result["passed"], result["receipt"]["outcome"]), (True, "confirmed"))
        self.assertEqual(result["receipt"]["localRef"]["id"], "slot:ep-03-outline")  # still the input's claim
        self.assertNotIn("slotCheck", json.loads(result["receipt"]["notes"]))
        self.assertTrue(any("record.slot" in warning for warning in result["warnings"]))
        cached = self.cache(*CHUNKS, **self.META)
        self.assertEqual(cached["entry"]["slotSource"], "host")
        self.assertEqual(self.cache(*CHUNKS, **dict(self.META, slot="ep-04-outline"))["passed"], False)  # metadata clash, not a receipt clash
        self.assertEqual(self.cache(*CHUNKS, "03-get.response.json")["entry"]["slotSource"], "record")

    def test_unknown_and_resent_saves_carry_no_slot_check(self):
        unknown = self.record("05-unknown.response.json", "save_story_artifact", "d1-save-3", "05-unknown.input.json")
        self.assertNotIn("slotCheck", json.loads(unknown["receipt"]["notes"]))
        resent = self.record("10-resend-save.response.json", "save_story_artifact", "d1-save-3.resend-1", "05-unknown.input.json", reconciles="d1-save-3")
        self.assertEqual(json.loads(resent["receipt"]["notes"])["slotCheck"], "record.slot matched --input slot (S)")

    def test_host_warning_follows_the_strongest_source_recorded_for_the_path(self):
        self.cache("03-get.response.json")  # unverified, slot from the record
        result = self.cache(*CHUNKS, **self.META)  # verified read appended with a host-declared slot
        self.assertEqual((result["manifestAppended"], result["entry"]["slotSource"], result["entry"]["verified"]), (True, "host", True))
        self.assertEqual(result["warnings"], [])
        self.assertEqual([entry["slotSource"] for entry in self.entries()], ["record", "host"])

    def test_stronger_slot_source_is_appended_and_earlier_entries_never_change(self):
        self.assertTrue(self.cache(*CHUNKS, **self.META)["manifestAppended"])
        first = self.entries()
        self.save()
        upgraded = self.cache(*CHUNKS, **self.META)
        self.assertEqual((upgraded["status"], upgraded["manifestAppended"], upgraded["entry"]["slotSource"]), ("unchanged", True, "receipt"))
        strongest = self.cache(*CHUNKS, "03-get.response.json")
        self.assertEqual((strongest["manifestAppended"], strongest["entry"]["slotSource"]), (True, "record"))
        entries = self.entries()
        self.assertEqual([entry["slotSource"] for entry in entries], ["host", "receipt", "record"])
        self.assertEqual(entries[:1], first)
        self.assertEqual(len({(entry["path"], entry["sha256"], entry["slot"], entry["verified"]) for entry in entries}), 1)
        before = self.manifest.read_bytes()
        for weaker in (lambda: self.cache(*CHUNKS, **self.META), lambda: self.cache("03-get.response.json")):
            result = weaker()
            self.assertEqual((result["manifestAppended"], result["entry"]["slotSource"]), (False, "record"))
            self.assertEqual(self.manifest.read_bytes(), before)

    def test_get_after_a_host_declared_read_adds_the_slot_source_and_keeps_verification(self):
        self.cache(*CHUNKS, **self.META)
        result = self.cache("03-get.response.json")
        self.assertTrue(result["manifestAppended"])
        host, record = self.entries()
        self.assertEqual((host["slotSource"], host["verified"]), ("host", True))
        self.assertEqual({key: record[key] for key in ("slotSource", "verified", "serverFingerprint", "sha256", "operation")},
                         {"slotSource": "record", "verified": True, "serverFingerprint": self.fingerprint,
                          "sha256": self.fingerprint, "operation": "read_story_artifact"})

    FIXED = {"slot": "ep-03-outline", "kind": "episode_outline", "episodeRef": "ep-03"}
    WRONG = dict(META, slot="ep-99-outline")
    DRAFT = dict(META, kind="episode_draft")

    def earlier(self):
        """The manifest bytes up to the end of its last entry: exactly what an append has to leave untouched."""
        data = self.manifest.read_bytes()
        return data[:data.rindex(b"\n  ]")]

    def reset(self):
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        shutil.rmtree(self.receipts, ignore_errors=True)

    def assertCorrected(self, wrong, weak, fix, source):
        """Cache `wrong` metadata from the `weak` source, run `fix`, and expect one correcting entry after the untouched earlier ones."""
        first = self.cache(*CHUNKS, **wrong)
        self.assertEqual((first["passed"], first["entry"]["slotSource"]), (True, weak), first)
        earlier, count = self.earlier(), len(self.entries())
        result = fix()
        self.assertEqual((result["passed"], result["status"], result["manifestAppended"], result["entry"]["slotSource"]),
                         (True, "unchanged", True, source), result)
        self.assertTrue(self.manifest.read_bytes().startswith(earlier))
        entries = self.entries()
        self.assertEqual(len(entries), count + 1)
        self.assertEqual({key: entries[-1][key] for key in self.FIXED}, self.FIXED)
        self.assertEqual({key: receipt.effective_entries(entries)[0][key] for key in self.FIXED}, self.FIXED)
        self.assertEqual((result["verified"], entries[-1]["verified"], entries[-1]["serverFingerprint"]), (True, True, self.fingerprint))
        return result

    def assertRefusedUnchanged(self, result, before, *needles):
        self.assertEqual((result["passed"], result["status"]), (False, "refused"), result)
        for needle in (*needles, "nothing written"):
            self.assertIn(needle, result["error"], needle)
        for advice in ("by hand", "remove the wrong"):  # the manifest is append-only: nobody is told to edit it
            self.assertNotIn(advice, result["error"])
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_effective_entries_are_the_strongest_ranked_and_an_absent_or_odd_source_counts_as_host(self):
        host, legacy, odd = {"slotSource": "host", "slot": "a"}, {"slot": "b"}, {"slotSource": "trusted-by-me", "slot": "c"}
        saved, record, again = {"slotSource": "receipt", "slot": "d"}, {"slotSource": "record", "slot": "e"}, {"slotSource": "record", "slot": "f"}
        self.assertEqual(receipt.effective_entries([]), [])
        self.assertEqual(receipt.effective_entries([host, legacy, odd]), [host, legacy, odd])
        self.assertEqual(receipt.effective_entries([host, saved, legacy]), [saved])
        self.assertEqual(receipt.effective_entries([record, saved, host, again]), [record, again])

    def test_record_corrects_a_wrong_host_declared_slot_by_appending(self):
        result = self.assertCorrected(self.WRONG, "host", lambda: self.cache(*CHUNKS, "03-get.response.json"), "record")
        host, record = self.entries()
        self.assertEqual((host["slotSource"], host["slot"], record["slotSource"], record["slot"]), ("host", "ep-99-outline", "record", "ep-03-outline"))
        correction = [warning for warning in result["warnings"] if "ep-99-outline" in warning]
        self.assertEqual(len(correction), 1, result["warnings"])
        for needle in ("ep-03-outline", "host", "record", "kept"):
            self.assertIn(needle, correction[0])
        self.assertFalse(any("impact reports" in warning for warning in result["warnings"]))  # the slot is no longer only the host's word
        before = self.manifest.read_bytes()
        self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.WRONG), before, "ep-99-outline", "ep-03-outline", "'record'")  # host never corrects back
        again = self.cache(*CHUNKS, **self.META)
        self.assertEqual((again["manifestAppended"], again["entry"]["slotSource"], again["entry"]["slot"], again["warnings"]),
                         (False, "record", "ep-03-outline", []))
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_get_only_correction_after_a_verified_host_read_stays_verified(self):
        result = self.assertCorrected(self.WRONG, "host", lambda: self.cache("03-get.response.json"), "record")
        self.assertEqual((result["entry"]["operation"], result["entry"]["sha256"]), ("read_story_artifact", self.fingerprint))
        self.assertFalse(any("verified=false" in warning for warning in result["warnings"]))

    def test_kind_or_episode_ref_alone_is_corrected_and_receipt_corrects_host(self):
        get = lambda: self.cache(*CHUNKS, "03-get.response.json")  # noqa: E731
        for label, wrong in [("kind", self.DRAFT), ("episodeRef", dict(self.META, episode_ref="ep-99"))]:
            with self.subTest(label):
                result = self.assertCorrected(wrong, "host", get, "record")
                self.assertEqual(self.entries()[0]["slot"], "ep-03-outline")
                self.assertTrue(any(label in warning for warning in result["warnings"]))
                self.reset()
        with self.subTest("a confirmed save receipt corrects the host's slot"):
            def backed():
                self.save()
                return self.cache(*CHUNKS, **self.META)
            self.assertCorrected(self.WRONG, "host", backed, "receipt")
            self.assertEqual([(entry["slotSource"], entry["slot"]) for entry in self.entries()], [("host", "ep-99-outline"), ("receipt", "ep-03-outline")])
            self.reset()
        with self.subTest("the record corrects what a receipt-backed call said"):
            self.save()
            self.assertCorrected(self.DRAFT, "receipt", get, "record")
            self.assertEqual([(entry["slotSource"], entry["kind"]) for entry in self.entries()], [("receipt", "episode_draft"), ("record", "episode_outline")])

    def test_receipt_backed_call_corrects_only_the_slot_and_the_record_corrects_what_it_said(self):
        ref99 = dict(self.META, episode_ref="ep-99")
        both = lambda wrong: dict(wrong, slot="ep-99-outline")  # noqa: E731
        cases = [("kind, host entry wrong", self.DRAFT, self.META, "kind 'episode_draft'"), ("kind, this call wrong", self.META, self.DRAFT, "'episode_draft' (this call)"),
                 ("episodeRef, host entry wrong", ref99, self.META, "episodeRef 'ep-99'"), ("episodeRef, this call wrong", self.META, ref99, "'ep-99' (this call)"),
                 ("kind and slot", both(self.DRAFT), self.META, "slot 'ep-99-outline'"), ("episodeRef and slot", both(ref99), self.META, "slot 'ep-99-outline'")]
        for label, hosted, backed, needle in cases:
            with self.subTest(label):
                self.assertEqual(self.cache(*CHUNKS, **hosted)["entry"]["slotSource"], "host")
                before = self.manifest.read_bytes()
                self.save()
                self.assertRefusedUnchanged(self.cache(*CHUNKS, **backed), before, needle, "'host'", "'receipt'", "vouches only for the slot",
                                            "get_story_artifact", "kind or episodeRef")
                fixed = self.cache(*CHUNKS, "03-get.response.json")  # the record still corrects all three
                self.assertEqual((fixed["passed"], fixed["manifestAppended"], {key: fixed["entry"][key] for key in self.FIXED}), (True, True, self.FIXED))
                self.assertTrue(self.manifest.read_bytes().startswith(before[:before.rindex(b"\n  ]")]))
                self.reset()
        for label, wrong, field in [("kind", self.DRAFT, "kind"), ("episodeRef", ref99, "episodeRef")]:
            with self.subTest(f"record corrects a receipt-backed entry's {label}"):
                self.save()
                result = self.assertCorrected(wrong, "receipt", lambda: self.cache(*CHUNKS, "03-get.response.json"), "record")
                self.assertTrue(any(field in warning and "'receipt'" in warning for warning in result["warnings"]))
                self.reset()

    def test_equal_or_weaker_source_with_different_metadata_is_refused_and_names_the_existing_source(self):
        def other_slot(value):
            value["structuredContent"]["data"]["record"]["slot"] = "ep-99-outline"
        get = lambda: self.cache(*CHUNKS, "03-get.response.json")  # noqa: E731
        with self.subTest("host call against a record entry"):
            get()
            before = self.manifest.read_bytes()
            self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.WRONG), before, "slot 'ep-03-outline'", "'ep-99-outline'", "'record'", "'host'")
        with self.subTest("receipt-backed call against a record entry"):
            self.save()
            self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.DRAFT), before, "kind 'episode_outline'", "'episode_draft'", "'record'", "'receipt'")
        with self.subTest("second record against a record entry"):
            contrary = self.variant("03-get.response.json", other_slot, "other-slot-get.json")
            self.assertRefusedUnchanged(self.cache(contrary), before, "'ep-99-outline'", "'record'")
            self.reset()
        with self.subTest("host call against a receipt-backed entry"):
            self.save()
            self.assertEqual(self.cache(*CHUNKS, **self.META)["entry"]["slotSource"], "receipt")
            before = self.manifest.read_bytes()
            shutil.rmtree(self.receipts)  # without the receipt the same call is only the host's word
            self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.WRONG), before, "'ep-99-outline'", "'receipt'", "'host'", "get_story_artifact")
        with self.subTest("receipt-backed call against a receipt-backed entry"):
            self.save()
            self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.DRAFT), before, "'episode_draft'", "'receipt'")
            self.reset()
        with self.subTest("host call against a host entry"):
            self.cache(*CHUNKS, **self.META)
            before = self.manifest.read_bytes()
            self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.WRONG), before, "'ep-99-outline'", "'host'", "get_story_artifact")

    def test_refusal_says_what_actually_vouches_for_the_cached_values(self):
        with self.subTest("a receipt-backed entry's kind is the host's word"):
            self.save()
            self.assertEqual(self.cache(*CHUNKS, **self.DRAFT)["entry"]["slotSource"], "receipt")
            before = self.manifest.read_bytes()
            for label, call in [("receipt-backed call", lambda: self.cache(*CHUNKS, **self.META)),
                                ("host call", lambda: (shutil.rmtree(self.receipts), self.cache(*CHUNKS, **self.META))[1])]:
                result = call()
                self.assertRefusedUnchanged(result, before, "kind 'episode_draft'", "save receipt vouches for the slot", "kind and episodeRef were given by the host",
                                            "get_story_artifact")
                self.assertNotIn("come from slotSource 'receipt'", result["error"], label)
            self.reset()
        with self.subTest("a receipt-backed entry's slot does come from the receipt"):
            self.save()
            self.cache(*CHUNKS, **self.META)
            before = self.manifest.read_bytes()
            shutil.rmtree(self.receipts)
            self.assertRefusedUnchanged(self.cache(*CHUNKS, **self.WRONG), before, "come from slotSource 'receipt'", "this call's source is 'host'")
            self.reset()
        for label, source, needle in [("no slotSource", None, "has no slotSource (counts as host)"),
                                      ("unknown slotSource", "trusted-by-me", "unknown slotSource 'trusted-by-me' (counts as host)")]:
            with self.subTest(label):
                self.cache(*CHUNKS, **self.META)
                manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
                manifest["entries"][0].pop("slotSource")
                manifest["entries"][0].update({} if source is None else {"slotSource": source})
                self.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                before = self.manifest.read_bytes()
                result = self.cache(*CHUNKS, **self.WRONG)
                self.assertRefusedUnchanged(result, before, needle, "this call's source is 'host'")
                self.assertNotIn("slotSource 'host'", result["error"])
                fixed = self.cache(*CHUNKS, "03-get.response.json")
                self.assertTrue(fixed["passed"])
                self.assertEqual(fixed["warnings"], [])  # same metadata: nothing was corrected
                self.reset()

    def test_record_contradicting_a_save_receipt_about_the_slot_is_called_out_with_the_request_id(self):
        def other_slot(value):
            value["structuredContent"]["data"]["record"]["slot"] = "ep-99-outline"
        request = Path(self.temp.name) / "ep99.input.json"
        request.write_text(json.dumps(dict(fixture("02-save.input.json"), slot="ep-99-outline"), ensure_ascii=False), encoding="utf-8")
        saved = self.record(self.variant("02-save.response.json", other_slot, "ep99-save.json"), "save_story_artifact", "d1-save-2", request)
        self.assertEqual((saved["passed"], saved["receipt"]["localRef"]["id"]), (True, "slot:ep-99-outline"))
        self.assertEqual(self.cache(*CHUNKS, **self.WRONG)["entry"]["slotSource"], "receipt")
        earlier = self.earlier()
        result = self.cache(*CHUNKS, "03-get.response.json")
        self.assertEqual((result["passed"], result["manifestAppended"], result["entry"]["slot"]), (True, True, "ep-03-outline"))
        self.assertTrue(self.manifest.read_bytes().startswith(earlier))
        self.assertEqual(len(result["warnings"]), 2, result["warnings"])
        self.assertIn("corrects metadata", result["warnings"][0])
        for needle in ("disagree", "d1-save-2", "'ep-99-outline'", "'ep-03-outline'", "get_story_artifact record", "save receipt"):
            self.assertIn(needle, result["warnings"][1], needle)
        self.reset()
        self.save()  # the receipt agrees on the slot; only the host-given kind is corrected
        self.cache(*CHUNKS, **self.DRAFT)
        result = self.cache(*CHUNKS, "03-get.response.json")
        self.assertEqual([("corrects metadata" in warning, "disagree" in warning) for warning in result["warnings"]], [(True, False)])
        self.reset()
        self.cache(*CHUNKS, **self.WRONG)  # host against record is an ordinary correction
        self.assertEqual(len(self.cache(*CHUNKS, "03-get.response.json")["warnings"]), 1)

    def test_receipt_contradiction_warning_finds_the_receipt_when_the_record_has_no_project_id(self):
        record = dict(fixture("03-get.response.json")["structuredContent"]["data"]["record"], slot="ep-99-outline")
        del record["projectId"]
        bare = Path(self.temp.name) / "bare-get.json"
        bare.write_text(json.dumps({"record": record}, ensure_ascii=False), encoding="utf-8")
        for label, keep, present, absent in [("receipt on disk", True, ("(d1-save-2)",), ("no longer", "no matching")),
                                             ("receipt gone", False, ("no matching local save receipt was found",), ("no longer", "d1-save-2"))]:
            with self.subTest(label):
                self.save()
                self.assertEqual(self.cache(*CHUNKS, **self.META)["entry"]["slotSource"], "receipt")
                if not keep:
                    shutil.rmtree(self.receipts)
                result = self.cache(bare)
                self.assertEqual((result["passed"], result["manifestAppended"], result["entry"]["slot"]), (True, True, "ep-99-outline"), result)
                warning = next(warning for warning in result["warnings"] if "disagree" in warning)
                for needle in present:
                    self.assertIn(needle, warning)
                for needle in absent:
                    self.assertNotIn(needle, warning)
                self.reset()

    def test_malformed_manifest_values_are_refused_not_corrected_and_never_crash(self):
        chunks = [str(FIXTURES / name) for name in CHUNKS]
        for source in ("receipt", "host", None):
            for field, value in [("slot", ["ep-03-outline"]), ("slot", None), ("kind", {"a": 1}), ("episodeRef", 3)]:
                with self.subTest(source=source, field=field, value=value):
                    self.cache(*CHUNKS, **self.META)
                    manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
                    manifest["entries"][0].update({field: value, "slotSource": source})
                    self.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    before = self.manifest.read_bytes()
                    for call in ([*chunks, str(FIXTURES / "03-get.response.json")], [str(FIXTURES / "03-get.response.json")]):
                        run = subprocess.run([sys.executable, "-B", str(TOOL), "receipt", "cache", str(self.project), *call], capture_output=True, text=True)
                        self.assertEqual((run.returncode, run.stderr), (2, ""), run.stdout + run.stderr)
                        result = json.loads(run.stdout)
                        self.assertRefusedUnchanged(result, before, "is already cached with different metadata", field, "not written by this tool")
                    self.reset()

    def test_contradicting_strongest_entries_are_never_settled_by_an_equal_or_weaker_call(self):
        self.cache(*CHUNKS, "03-get.response.json")
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["entries"].append(dict(manifest["entries"][0], slot="ep-99-outline"))  # two record entries, two slots: not something this tool writes
        self.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = self.manifest.read_bytes()
        for label, call in [("record", lambda: self.cache(*CHUNKS, "03-get.response.json")), ("get only", lambda: self.cache("03-get.response.json")),
                            ("host, first slot", lambda: self.cache(*CHUNKS, **self.META)), ("host, second slot", lambda: self.cache(*CHUNKS, **self.WRONG))]:
            with self.subTest(label):
                self.assertRefusedUnchanged(call(), before, "'record'")

    def test_manifest_is_append_only_and_only_a_stronger_source_changes_the_effective_metadata_in_any_call_order(self):
        self.save()
        saved = (self.receipts / "d1-save-2.json").read_bytes()

        def call(backed, *names, **meta):
            def run():
                self.reset() if not self.manifest.exists() else shutil.rmtree(self.receipts, ignore_errors=True)
                if backed:
                    self.receipts.mkdir()
                    (self.receipts / "d1-save-2.json").write_bytes(saved)
                return self.cache(*names, **meta)
            return run
        calls = {"host, wrong slot": call(False, *CHUNKS, **self.WRONG), "host, right": call(False, *CHUNKS, **self.META),
                 "receipt, wrong kind": call(True, *CHUNKS, **self.DRAFT), "receipt, right": call(True, *CHUNKS, **self.META),
                 "get only": call(False, "03-get.response.json"), "chunks and get": call(False, *CHUNKS, "03-get.response.json")}
        appended = 0
        for order in itertools.permutations(calls):
            self.reset()
            for step, name in enumerate(order):
                exists = self.manifest.exists()
                before, earlier, old = (self.manifest.read_bytes(), self.earlier(), self.entries()) if exists else (None, b"", [])
                result = calls[name]()
                where = f"{order} step {step} ({name}): {result.get('error')}"
                if not result["passed"]:
                    self.assertEqual(self.manifest.read_bytes() if self.manifest.exists() else None, before, where)
                    continue
                new = self.entries()
                self.assertTrue(self.manifest.read_bytes().startswith(earlier), where)
                self.assertEqual(new[:len(old)], old, where)
                self.assertEqual(len(new) - len(old), int(result["manifestAppended"]), where)
                appended += len(new) - len(old)
                strongest, now = receipt.effective_entries(old), receipt.effective_entries(new)
                self.assertEqual(len({tuple(entry[key] for key in self.FIXED) for entry in now}), 1, where)  # this tool never writes a contradiction
                if strongest and receipt.slot_rank(new[-1]) <= receipt.slot_rank(strongest[0]):
                    self.assertEqual([{key: entry[key] for key in self.FIXED} for entry in now][:1],
                                     [{key: entry[key] for key in self.FIXED} for entry in strongest][:1], where)
                if any(entry["verified"] for entry in old):  # once verified, the last entry for the path stays verified
                    self.assertTrue(new[-1]["verified"], where)
            if any(receipt.slot_rank(entry) == 2 for entry in self.entries()):
                self.assertEqual({key: receipt.effective_entries(self.entries())[0][key] for key in self.FIXED}, self.FIXED, order)
        self.assertGreater(appended, len(calls))

    def test_refusal_of_a_slot_the_record_vouches_for_never_suggests_editing_the_manifest(self):
        self.cache(*CHUNKS, "03-get.response.json")
        plain = self.cache(*CHUNKS, **dict(self.META, slot="ep-04-outline"))
        self.assertFalse(plain["passed"])
        self.assertNotIn("by hand", plain["error"])

    def test_host_warning_follows_the_entry_that_is_returned(self):
        self.cache(*CHUNKS, "03-get.response.json")
        weaker = self.cache(*CHUNKS, **self.META)
        self.assertEqual((weaker["entry"]["slotSource"], weaker["warnings"]), ("record", []))
        self.save()
        self.manifest.unlink()
        self.assertEqual(self.cache(*CHUNKS, **self.META)["warnings"], [])  # receipt-backed

    def test_get_after_a_verified_read_reports_the_verification_it_returns(self):
        first = self.cache("03-get.response.json")
        self.assertEqual((first["verified"], first["entry"]["verified"], len(first["warnings"])), (False, False, 1))
        self.manifest.unlink()
        for label, read in [("record entry reused", lambda: self.cache(*CHUNKS, "03-get.response.json")),
                            ("verification carried over", lambda: self.cache(*CHUNKS, **self.META))]:
            with self.subTest(label):
                read_at = read()["entry"]["readAt"]
                with mock.patch.object(receipt, "_now", return_value="2030-01-01T00:00:00+00:00"):
                    result = self.cache("03-get.response.json")
                self.assertEqual((result["verified"], result["entry"]["verified"], result["entry"]["slotSource"]), (True, True, "record"))
                self.assertEqual(result["warnings"], [])
                self.assertEqual(result["entry"]["readAt"], read_at)  # the verified read happened then, not now
                self.assertEqual([entry["readAt"] for entry in self.entries()], [read_at] * len(self.entries()))
                self.manifest.unlink()

    def test_context_pack_still_reads_a_manifest_with_an_upgraded_entry(self):
        self.cache(*CHUNKS, **self.META)
        self.cache(*CHUNKS, "03-get.response.json")
        self.assertEqual(len(self.entries()), 2)
        selection = Path(self.temp.name) / "selection.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "remote_artifact", "id": ART1, "revision": 1}, "partition": "current_plan", "required": True, "reason": "测试"}]}),
            encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(TOOL), "context-pack", str(self.project), "--task",
                              str(ROOT / "skills/drama-studio/schemas/examples/task.json"), "--selection", str(selection),
                              "--role", "author", "--budget", "20000", "--dry-run"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)["omitted_count"], 0)

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
                        "--request-id", request_id, "--input", FIXTURES / input_name if isinstance(input_name, str) else input_name, *extra)

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

    def test_ac1_and_ac5_issue_20_reproduction_corrects_the_host_slot_and_a_host_call_cannot_correct_back(self):
        chunks, manifest = [FIXTURES / name for name in CHUNKS], self.project / ".drama/cache/manifest.json"
        wrong = ("--slot", "ep-99-outline", "--kind", "episode_outline", "--episode-ref", "ep-03")
        code, result, _ = self.cli("receipt", "cache", self.project, *chunks, *wrong)
        self.assertEqual((code, result["entry"]["slotSource"], result["entry"]["slot"]), (0, "host", "ep-99-outline"))
        first = manifest.read_bytes()
        code, result, _ = self.cli("receipt", "cache", self.project, *chunks, FIXTURES / "03-get.response.json")
        self.assertEqual((code, result["passed"], result["manifestAppended"], result["remote_verified"]), (0, True, True, False), result)
        self.assertEqual([(entry["slotSource"], entry["slot"]) for entry in json.loads(manifest.read_text(encoding="utf-8"))["entries"]],
                         [("host", "ep-99-outline"), ("record", "ep-03-outline")])
        self.assertTrue(manifest.read_bytes().startswith(first[:first.rindex(b"\n  ]")]))  # the first entry's bytes are unchanged
        corrected = manifest.read_bytes()
        code, result, _ = self.cli("receipt", "cache", self.project, *chunks, *wrong)
        self.assertEqual((code, result["passed"]), (2, False))
        for needle in ("ep-99-outline", "ep-03-outline", "'record'", "nothing written"):
            self.assertIn(needle, result["error"])
        self.assertEqual(manifest.read_bytes(), corrected)

    def test_odd_existing_files_fail_cleanly(self):
        self.receipts.mkdir()
        (self.receipts / "dangling.json").symlink_to(self.receipts / "nowhere.json")
        (self.receipts / "list.json").write_text("[]", encoding="utf-8")
        (self.receipts / "broken.json").write_text("{", encoding="utf-8")
        (self.receipts / "folder.json").mkdir()
        (self.project / ".drama/cache").mkdir()
        (self.project / ".drama/cache/manifest.json").write_text("[]", encoding="utf-8")
        chunks = [FIXTURES / name for name in CHUNKS]
        calls = [("record", "dangling", "02-save.response.json"), ("show", "dangling"), ("show", "list"), ("show", "broken"),
                 ("show", "folder"), ("pending",), ("reconcile", "list"), ("reconcile", "broken"), ("cache",)]
        for call in calls:
            with self.subTest(call):
                if call[0] == "record":
                    code, result, run = self.cli_record(call[2], call[1], self.input_as("02-save.input.json", call[1]))
                    self.assertIn("dangling symlink", result["error"])
                elif call[0] == "show":
                    code, _, run = self.cli("receipt", "show", self.project, call[1])
                elif call[0] == "pending":
                    code, result, run = self.cli("receipt", "pending", self.project)
                    self.assertEqual(sorted(Path(item["path"]).name for item in result["invalid"]),
                                     ["broken.json", "dangling.json", "folder.json", "list.json"])
                elif call[0] == "reconcile":
                    code, _, run = self.cli_record("07-reconcile-get.response.json", "rec-1", "07-reconcile-get.input.json",
                                                   "get_story_artifact", "--reconciles", call[1])
                else:
                    code, _, run = self.cli("receipt", "cache", self.project, *chunks, FIXTURES / "03-get.response.json")
                self.assertNotIn("Traceback", run.stderr)
                self.assertIn(code, (0, 1, 2) if call[0] == "pending" else (1, 2))

    def test_doctor_still_offline(self):
        code, result, _ = self.cli("doctor")
        self.assertEqual(code, 0)
        self.assertFalse(result["network_used"])
        self.assertFalse(result["models_called"])


class DocsTests(unittest.TestCase):
    ANCHOR = "../mali-story.md#候选保存与对账"

    def test_method_section_covers_the_contract(self):
        text = (ROOT / "skills/drama-studio/references/mali-story.md").read_text(encoding="utf-8")
        self.assertIn("\n## 候选保存与对账\n", text)
        section = text.split("## 候选保存与对账", 1)[1].split("\n## ", 1)[0]
        for needle in ("producer", "`codex`", "`human`", "slot", "episodeRef", "episode_draft", "series_outline",
                       "requestFingerprint", "inputFingerprint", "--reconciles", "receipt pending", "receipt cache",
                       "nextOffset", "保存不等于采用", "不换新 requestId", "expected_revision 已过期",
                       "同一 requestId 配了不同输入", ".resend-1", "resolved_verified", "resolved_host_judged", "read_only_unknown",
                       "unreconcilable_unknown", "prepare_story_context", "列表为空", "非 confirmed 的重发", "修订号大于"):
            self.assertIn(needle, section, needle)

    def test_docs_describe_slot_correction_and_never_advise_editing_the_manifest(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        method = (ROOT / "skills/drama-studio/references/mali-story.md").read_text(encoding="utf-8").split("## 候选保存与对账", 1)[1].split("\n## ", 1)[0]
        for label, text in (("README", readme), ("mali-story.md", method)):
            for needle in ("最强来源", "`record` > `receipt` > `host`", "纠正", "不改不删", "相同或更弱", "episodeRef", "保存回执只担保 slot"):
                self.assertIn(needle, text, f"{label}: {needle}")
            for advice in ("手工从", "去掉错误条目", "改不了那条条目", "删除条目", "删掉"):
                self.assertNotIn(advice, text, f"{label}: {advice}")
        for needle in ("最强来源的条目之间互相矛盾", "不再算作", "按纠正后的 slot", "宿主声明不能纠正", "三项与来源最强的条目比较",
                       "只从来源最强的条目读 `slot`", "来源相同或更弱的 `receipt cache` 调用被拒绝", "照旧算数", "requestId", "不提示拼写错误"):
            self.assertIn(needle, readme, needle)
        for needle in ("宿主只通过 `receipt` 工具写 manifest", "不手工修改"):
            self.assertIn(needle, method, needle)
        self.assertNotIn("不由人或宿主改动", method)
        self.assertNotIn("都从来源最强的条目取", readme)
        docstring = " ".join(receipt.effective_entries.__doc__.split())
        for needle in ("receipt cache compares slot, kind and episodeRef", "context-pack, impact and status read only the slot"):
            self.assertIn(needle, docstring)

    def test_workstation_steps_link_the_method(self):
        lines = (ROOT / "skills/drama-studio/references/workstations/README.md").read_text(encoding="utf-8").splitlines()
        steps = {line[:2]: line for line in lines if line[:2] in ("3.", "5.")}
        for step in ("3.", "5."):
            self.assertIn(self.ANCHOR, steps[step])
            self.assertIn("receipt", steps[step])

    def test_readme_shows_receipt_examples(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for command in ("receipt record", "receipt pending", "receipt cache", "receipt show"):
            self.assertIn(command, text)


REAL = ROOT / "tests/fixtures/mcp"
REAL_PROJECT = "4e6556ac97654bf781977"
REAL_SNAPSHOT = "sha256:9be0b1334077ad7e1332d825fd08104054c31f4aa4ddf273c1234f5f2521d390"
REAL_ARTIFACT = "5da998a0-b9c6-47ae-9635-ee08410bc0fc"


class RealFixtureTests(unittest.TestCase):
    """Responses captured from production mali-story v0.19.0 through Claude Code (#3, 2026-10-05).

    Claude Code surfaces a tool's text content: successes arrive as mali-tool-result/v1,
    errors as the bare dispatch envelope {status, headers, body}.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "proj"
        subprocess.run([sys.executable, "-B", str(TOOL), "init-project", str(self.project), "--title", "真实夹具"],
                       capture_output=True, text=True, check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, step, operation, request_id, response=None):
        response = response or REAL / f"{step}.response.json"
        run = subprocess.run([sys.executable, "-B", str(TOOL), "receipt", "record", str(self.project), str(response),
                              "--operation", operation, "--request-id", request_id, "--input", str(REAL / f"{step}.input.json")],
                             capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_fixtures_are_real_and_hold_no_credentials_or_user_ids(self):
        names = sorted(path.name for path in REAL.glob("*.json"))
        for step in ("01-writing-context", "02-save", "03-get", "04-list", "05-replay", "06-requestid-conflict", "07-stale-revision"):
            self.assertIn(f"{step}.input.json", names)
            self.assertIn(f"{step}.response.json", names)
        for path in REAL.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("_synthetic", text, path.name)
            self.assertNotRegex(text, r'(?i)"(access_?token|refresh_?token|cookie|authorization)"|Bearer ', path.name)
            self.assertNotRegex(text, r'"submittedByUserId":"[0-9a-f-]{36}"', path.name)

    def test_success_shape_is_tool_result_and_error_shape_is_dispatch_envelope(self):
        ok = receipt.parse_response(json.loads((REAL / "02-save.response.json").read_text(encoding="utf-8")), "save_story_artifact")
        self.assertEqual((ok["ok"], ok["httpStatus"], ok["shape"]), (True, 200, "mali-tool-result/v1"))
        self.assertEqual(ok["data"]["record"]["producer"], "external_ai")
        for step in ("06-requestid-conflict", "07-stale-revision"):
            bad = receipt.parse_response(json.loads((REAL / f"{step}.response.json").read_text(encoding="utf-8")), "save_story_artifact")
            self.assertEqual((bad["ok"], bad["httpStatus"], bad["errorCode"]), (False, 409, "VERSION_CONFLICT"), step)
            self.assertEqual(receipt.outcome_of(bad), ("rejected_conflict", False), step)

    def test_probe_sequence_produces_contract_checked_receipts(self):
        steps = [("01-writing-context", "get_writing_context", "d1-probe-ctx-1", 0, "written", "confirmed"),
                 ("02-save", "save_story_artifact", "d1-probe-save-1", 0, "written", "confirmed"),
                 ("03-get", "get_story_artifact", "d1-probe-get-1", 0, "written", "confirmed"),
                 ("04-list", "list_story_artifacts", "d1-probe-list-1", 0, "written", "confirmed"),
                 ("05-replay", "save_story_artifact", "d1-probe-save-1", 0, "replay", "confirmed"),
                 ("07-stale-revision", "save_story_artifact", "d1-probe-save-stale-1", 0, "written", "rejected_conflict")]
        for step, operation, request_id, code, status, outcome in steps:
            rc, out = self.record(step, operation, request_id)
            self.assertEqual((rc, out["status"], out["receipt"]["outcome"]), (code, status, outcome), step)
            self.assertEqual(check_contract("remote-receipt", out["receipt"]), [], step)
        saved = json.loads((self.project / ".drama/receipts/d1-probe-save-1.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["remote"], {"projectId": REAL_PROJECT, "artifactId": REAL_ARTIFACT, "revision": 1,
                                           "inputSnapshotId": REAL_SNAPSHOT})
        # Step 06 reuses the request id with other content: the local tool refuses it before any server answer counts.
        rc, out = self.record("06-requestid-conflict", "save_story_artifact", "d1-probe-save-1")
        self.assertEqual((rc, out["status"]), (2, "conflict"))

    def test_lost_long_save_is_unknown_and_pending(self):
        rc, out = self.record("08-save-long", "save_story_artifact", "d1-probe-save-long-1",
                              response=REAL / "08-save-long.response.json")
        self.assertEqual((rc, out["receipt"]["outcome"], out["receipt"]["retryAllowed"]), (0, "unknown", False))
        pending = receipt.pending(str(self.project))["pending"]
        self.assertEqual([(item["requestId"], item["slot"]) for item in pending], [("d1-probe-save-long-1", "d1-probe-long")])

    def test_identical_resend_reconciles_the_lost_save(self):
        # The session expired mid-save; listing the slot showed nothing, so the identical request was re-sent.
        self.record("08-save-long", "save_story_artifact", "d1-probe-save-long-1", response=REAL / "08-save-long.response.json")
        listing = receipt.parse_response(json.loads((REAL / "08-reconcile-list.response.json").read_text(encoding="utf-8")),
                                         "list_story_artifacts")
        self.assertEqual(listing["data"]["records"], [])
        rc, out = self.record("08-save-long", "save_story_artifact", "d1-probe-save-long-1.resend-1",
                              response=REAL / "08-save-long.resend.response.json")
        self.assertEqual(rc, 1)  # without --reconciles a re-send under a new id is an input error (request_id mismatch)
        self.assertIn("declares request_id", out["error"])
        run = subprocess.run([sys.executable, "-B", str(TOOL), "receipt", "record", str(self.project),
                              str(REAL / "08-save-long.resend.response.json"), "--operation", "save_story_artifact",
                              "--request-id", "d1-probe-save-long-1.resend-1", "--input", str(REAL / "08-save-long.input.json"),
                              "--reconciles", "d1-probe-save-long-1"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        state = receipt.pending(str(self.project))
        self.assertEqual((state["pending"], state["resolved_verified"]), ([], ["d1-probe-save-long-1"]))

    def test_chunked_read_caches_verified_text(self):
        chunks = [str(REAL / f"08-read-chunk-{n}.response.json") for n in (1, 2)]
        out = receipt.cache(str(self.project), [*chunks, str(REAL / "08-save-long.resend.response.json")])
        self.assertEqual((out["passed"], out["verified"], out["entry"]["slotSource"]), (True, True, "record"))
        cached = (self.project / out["entry"]["path"]).read_text(encoding="utf-8")
        self.assertEqual(len(cached), 4135)
        self.assertEqual(out["entry"]["sha256"], out["entry"]["serverFingerprint"])
        refused = receipt.cache(str(self.project), chunks[:1], slot="d1-probe-long", kind="research")
        self.assertEqual(refused["status"], "refused")


if __name__ == "__main__":
    unittest.main()
