import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts/drama_tools.py"


class ReferenceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "detail.json"
        self.detail = {"template": {"id": "test", "version": 1, "status": "ready", "episodesTotal": 2},
                       "content": {"episodeOutlines": [
                           {"episodeIndex": i, "outlineMd": "剧情", "rawMd": "原始分析", "hasOutline": True}
                           for i in (1, 2)]}}

    def run_check(self, value=None, *args):
        self.path.write_text(json.dumps(self.detail if value is None else value))
        run = subprocess.run([sys.executable, "-B", str(TOOL), "reference-check", str(self.path), *args], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_present_is_not_verified_or_quality_pass(self):
        code, result = self.run_check({"schemaVersion": "mali-tool-result/v1", "ok": True, "data": self.detail})
        self.assertEqual(code, 0)
        self.assertEqual(result["coverage_status"], "consistent_present")
        self.assertIsNone(result["passed"])
        self.assertFalse(result["source_video_verified"])

    def test_ready_with_missing_episode_is_not_complete(self):
        self.detail["content"]["episodeOutlines"].pop()
        code, result = self.run_check()
        self.assertEqual(code, 2)
        self.assertEqual(result["missing_rows"], [2])

    def test_nonempty_raw_with_missing_outline_and_stale_summary(self):
        self.detail["content"]["episodeOutlines"][1]["outlineMd"] = " "
        self.detail["template"]["seriesOutlineMd"] = "- episodesTotal: 1\n"
        code, result = self.run_check()
        self.assertEqual(code, 2)
        self.assertEqual(result["missing_outlines"], [2])
        self.assertEqual(result["missing_raw_evidence"], [])
        self.assertEqual({i["code"] for i in result["issues"]}, {"outline_flag_mismatch", "summary_count_mismatch"})

    def test_duplicate_cannot_fill_gap(self):
        self.detail["content"]["episodeOutlines"][1]["episodeIndex"] = 1
        code, result = self.run_check()
        self.assertEqual(code, 2)
        self.assertEqual(result["missing_rows"], [2])
        self.assertIn("duplicate_indices", [i["code"] for i in result["issues"]])

    def test_explicit_scope_and_new_process_detect_changed_file(self):
        _, old = self.run_check()
        self.detail["content"]["episodeOutlines"][0]["rawMd"] = ""
        code, new = self.run_check(None, "--expected-episodes", "3")
        self.assertEqual(code, 2)
        self.assertNotEqual(old["source_sha256"], new["source_sha256"])
        self.assertEqual(new["missing_raw_evidence"], [1, 3])

    def test_malformed_or_unavailable_is_error(self):
        for value in ([], {}, {"schemaVersion": "mali-tool-result/v1", "ok": False},
                      {"template": {"episodesTotal": True}, "content": {"episodeOutlines": []}}):
            with self.subTest(value=value):
                self.assertEqual(self.run_check(value)[0], 1)
        self.detail["content"]["episodeOutlines"][0]["episodeIndex"] = True
        self.assertEqual(self.run_check()[0], 1)


if __name__ == "__main__":
    unittest.main()
