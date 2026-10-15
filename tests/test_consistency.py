import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts/checks"


class ConsistencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def run_pair(self, a, b):
        paths = []
        for name, value in (("a.json", a), ("b.json", b)):
            path = self.dir / name
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            paths.append(str(path))
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "consistency.py"), *paths], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_four_states_by_question_and_line(self):
        prompt = {"files": [{"path": "brief.md", "sha256": "sha256:0"}]}
        a = {"promptVersion": prompt, "answers": [{"q": 1, "quoteRef": {"line": 7}, "holds": "holds"},
                                                  {"q": 2, "quoteRef": {"line": 9}, "holds": "holds"},
                                                  {"q": 3, "quoteRef": {"line": 10}, "holds": "notHolds"}]}
        b = {"promptVersion": prompt, "answers": [{"q": 1, "quoteRef": {"line": 7}, "holds": "holds"},
                                                  {"q": 2, "quoteRef": {"line": 9}, "holds": "notHolds"},
                                                  {"q": 4, "quoteRef": {"line": 20}, "holds": "holds"}]}
        code, result = self.run_pair(a, b)
        self.assertEqual(code, 0)
        self.assertEqual(result["counts"], {"agree": 1, "disagree": 1, "only_a": 1, "only_b": 1})
        self.assertEqual(result["agreementRate"], 0.5)
        self.assertEqual(result["notes"], [])
        self.assertIsNone(result["passed"])
        self.assertIn("consistency.py", result["reproduceCommand"])

    def test_reality_check_aligns_on_leading_id_not_wording(self):
        a = {"answers": [{"q": 1, "landsOn": "F-town-1.A.s1 老陈取箱子", "holds": "holds"}]}
        b = {"answers": [{"q": 1, "landsOn": "F-town-1.A.s1 老陈去镇上取件", "holds": "holds"}]}
        _, result = self.run_pair(a, b)
        self.assertEqual(result["counts"]["agree"], 1)
        self.assertEqual(result["rows"][0]["alignBy"], "landsOnId")

    def test_different_prompt_versions_are_noted(self):
        a = {"promptVersion": "v1", "answers": []}
        b = {"promptVersion": "v2", "answers": []}
        _, result = self.run_pair(a, b)
        self.assertTrue(result["notes"])

    def test_missing_answers_is_input_error(self):
        self.assertEqual(self.run_pair({}, {"answers": []})[0], 1)


if __name__ == "__main__":
    unittest.main()
