"""Scene syntax regressions; measurements never certify editorial quality."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"


class SceneFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "screenplay.md"

    def check(self, text, *args):
        self.path.write_text(text, encoding="utf-8")
        before = self.path.read_bytes()
        result = subprocess.run([sys.executable, "-B", str(TOOL), "episode-check",
                                 str(self.path), *args], capture_output=True, text=True)
        self.assertEqual(self.path.read_bytes(), before)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def test_markdown_and_legacy_have_equal_measurements(self):
        measurements = []
        for prefix in ("场", "### "):
            code, data = self.check(f"## 第11集\n{prefix}11-1 医院 病房 黎明 内\n"
                                    "人物：甲、乙\n△甲扶起椅子。\n甲：等我。\n---\n"
                                    f"{prefix}11-2 医院 大厅 后半夜 内\n△乙收起信。\n乙：走吧。\n")
            self.assertEqual(code, 0)
            ep = data["episodes"][0]
            self.assertEqual(ep["scenes"], 2)
            self.assertEqual(ep["locations"], 2)
            self.assertEqual(ep["speaker_changes"], 0)
            self.assertEqual(ep["warnings"], [])
            self.assertEqual(ep["parse_coverage"], {"scene_headers": "complete", "location_labels": "complete", "body_lines": "complete"})
            self.assertIsNone(data["passed"])
            self.assertEqual(data["review_status"], "not_run")
            self.assertEqual(data["schema_version"], 2)
            measurements.append(ep)
        self.assertEqual(measurements[0], measurements[1])

    def test_actual_time_labels_are_supported(self):
        for time in ("日", "夜", "黎明", "后半夜", "暮"):
            with self.subTest(time=time):
                code, data = self.check(f"# 第1集\n### 1-1 门口 {time} 外\n△她推门。\n", "--max-locations", "1")
                self.assertEqual(code, 0)
                self.assertEqual(data["constraint_status"], "met")

    def test_incomplete_markdown_header_cannot_pass_budget(self):
        for heading in ("### 1-1 门口", "### 1-1", "### 1_1 门口 日 外", "场1/1 门口 日 外"):
            with self.subTest(heading=heading):
                code, data = self.check(f"# 第1集\n{heading}\n△她推门。\n", "--max-locations", "1")
                self.assertEqual(code, 2)
                self.assertEqual(data["constraint_status"], "not_evaluable")
                self.assertIsNone(data["passed"])
                self.assertNotEqual(data["episodes"][0]["parse_coverage"]["location_labels"], "complete")

    def test_unrecognized_time_is_not_guessed_as_a_location(self):
        code, data = self.check("# 第1集\n### 1-1 医院 病房 内\n△她推门。\n", "--max-locations", "1")
        self.assertEqual(code, 2)
        self.assertEqual(data["constraint_status"], "not_evaluable")

    def test_partial_second_scene_invalidates_location_count(self):
        code, data = self.check("# 第1集\n### 1-1 门口 日 外\n甲：走。\n### 1-2 库房\n乙：好。\n", "--max-locations", "1")
        self.assertEqual(code, 2)
        self.assertEqual(data["episodes"][0]["scenes"], 2)
        self.assertEqual(data["episodes"][0]["speaker_changes"], 0)
        self.assertEqual(data["constraint_status"], "not_evaluable")

    def test_wrong_episode_and_duplicate_scene_ids_are_errors(self):
        for text in ("# 第1集\n### 2-1 门口 日 外\n△她推门。",
                     "# 第1集\n场1-1 门口 日 外\n△她推门。\n### 01-01 内室 夜 内\n△她坐下。"):
            with self.subTest(text=text):
                code, data = self.check(text)
                self.assertEqual(code, 1)
                self.assertFalse(data["ok"])

    def test_chinese_episode_and_padded_scene_ids_match(self):
        code, data = self.check("## 第十一集\n### 011-01 门口 日 外\n△她推门。")
        self.assertEqual(code, 0)
        self.assertEqual(data["episodes"][0]["scenes"], 1)

    def test_scene_number_must_be_positive(self):
        code, data = self.check("# 第1集\n### 1-0 门口 日 外\n△她推门。")
        self.assertEqual(code, 1)
        self.assertFalse(data["ok"])

    def test_scene_header_and_characters_are_not_body(self):
        code, data = self.check("# 第1集\n### 1-1 门口 日 外\n人物：甲\n---\n")
        self.assertEqual(code, 1)
        self.assertFalse(data["ok"])

    def test_scene_before_episode_is_not_counted(self):
        code, data = self.check("### 99-1 门口 日 外\n# 第1集\n### 1-1 内室 夜 内\n△她坐下。")
        self.assertEqual(code, 0)
        self.assertEqual(data["episodes"][0]["scenes"], 1)

    def test_quoted_scene_is_not_counted_or_used_to_certify(self):
        code, data = self.check("# 第1集\n### 1-1 门口 日 外\n△她推门。\n> ### 1-2 仓库 日 内\n", "--max-locations", "1")
        self.assertEqual(code, 2)
        self.assertEqual(data["episodes"][0]["scenes"], 1)
        self.assertEqual(data["constraint_status"], "not_evaluable")

    def test_fenced_examples_cannot_create_episodes(self):
        code, data = self.check("# 第1集\n### 1-1 门口 日 外\n△她推门。\n```md\n# 第2集\n场2-1 仓库 日 内\n△她离开。\n```\n")
        self.assertEqual(code, 1)
        self.assertFalse(data["ok"])

    def test_unknown_body_remains_visible(self):
        code, data = self.check("# 第1集\n### 1-1 门口 日 外\n她绕到背后。\n", "--max-locations", "1")
        self.assertEqual(code, 2)
        self.assertEqual(data["episodes"][0]["parse_coverage"]["body_lines"], "partial")

    def test_no_scene_remains_unknown(self):
        code, data = self.check("# 第1集\n△她推门。")
        self.assertEqual(code, 0)
        self.assertEqual(data["episodes"][0]["parse_coverage"]["scene_headers"], "unknown")
        self.assertIsNone(data["passed"])


if __name__ == "__main__":
    unittest.main()
