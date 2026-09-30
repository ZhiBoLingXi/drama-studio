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


if __name__ == "__main__":
    unittest.main()
