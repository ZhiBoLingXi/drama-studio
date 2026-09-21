import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.args = argparse.Namespace(host="codex", scope="user", project=None,
                                       skills_dir=str(self.base / "installed"), upgrade=False)

    def test_plan_does_not_write(self):
        self.assertEqual(installer.plan(self.args)["action"], "install")
        self.assertFalse((self.base / "installed").exists())

    def test_standalone_install_verify_and_repeat(self):
        result = installer.install(self.args)
        target = Path(result["destination"])
        verified = installer.verify(self.args)
        self.assertTrue(verified["matches_checkout"])
        self.assertEqual(verified["remote_mcp"], "not_checked")
        self.assertEqual(installer.install(self.args)["action"], "unchanged")
        run = subprocess.run([sys.executable, "-B", str(target / "scripts/drama_tools.py"),
                              "init-project", str(self.base / "story"), "--title", "新剧"],
                             cwd=self.base, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIsNone(json.loads(run.stdout)["state"]["remoteProjectId"])

    def test_unowned_directory_is_preserved(self):
        target = installer.destination(self.args)
        target.mkdir(parents=True)
        (target / "mine.md").write_text("mine")
        with self.assertRaises(installer.InstallError):
            installer.install(self.args)
        self.assertEqual((target / "mine.md").read_text(), "mine")

    def test_modified_install_is_preserved(self):
        target = Path(installer.install(self.args)["destination"])
        original = target / "SKILL.md"
        original.write_text("user edits")
        self.args.upgrade = True
        with self.assertRaises(installer.InstallError):
            installer.install(self.args)
        self.assertEqual(original.read_text(), "user edits")

    def test_added_file_is_preserved(self):
        target = Path(installer.install(self.args)["destination"])
        (target / "my-notes.md").write_text("private")
        with self.assertRaises(installer.InstallError):
            installer.install(self.args)

    def test_upgrade_retains_previous_version(self):
        target = Path(installer.install(self.args)["destination"])
        old = (target / "SKILL.md").read_bytes()
        clone = self.base / "new-source"
        shutil.copytree(installer.SOURCE, clone)
        (clone / "SKILL.md").write_bytes(old + b"\nUpdated instructions.\n")
        with patch.object(installer, "SOURCE", clone):
            self.assertEqual(installer.plan(self.args)["action"], "upgrade_required")
            with self.assertRaises(installer.InstallError):
                installer.install(self.args)
            self.args.upgrade = True
            result = installer.install(self.args)
            self.assertEqual(result["action"], "upgraded")
            self.assertEqual((Path(result["backup"]) / "SKILL.md").read_bytes(), old)
            self.assertTrue(installer.verify(self.args)["matches_checkout"])

    def test_symlink_target_rejected(self):
        target = installer.destination(self.args)
        target.parent.mkdir()
        target.symlink_to(installer.SOURCE, target_is_directory=True)
        with self.assertRaises(installer.InstallError):
            installer.install(self.args)

    def test_lock_is_preserved(self):
        target = installer.destination(self.args)
        target.parent.mkdir()
        lock = target.parent / ".drama-studio-install.lock"
        lock.write_text("another process")
        with self.assertRaises(installer.InstallError):
            installer.install(self.args)
        self.assertEqual(lock.read_text(), "another process")

    def test_project_scope_and_cloud_boundary(self):
        self.args.skills_dir = None
        self.args.scope = "project"
        with self.assertRaises(installer.InstallError):
            installer.destination(self.args)
        self.args.project = str(self.base)
        self.assertEqual(installer.destination(self.args), self.base / ".agents/skills/drama-studio")
        self.args.host = "claude-code"
        self.assertEqual(installer.destination(self.args), self.base / ".claude/skills/drama-studio")
        self.args.host = "chatgpt"
        with self.assertRaises(installer.InstallError):
            installer.destination(self.args)

    def test_package_is_self_contained_and_repeatable(self):
        archive = self.base / "skill.zip"
        result = installer.package(archive, "workbuddy")
        self.assertEqual(result["host_import"], "not_checked")
        self.assertEqual(installer.package(archive, "workbuddy")["action"], "unchanged")
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(set(bundle.namelist()), set(installer.inventory(installer.SOURCE)))
            text = bundle.read("SKILL.md").decode()
            for field in ("description_zh:", "description_en:", "version:", "author:"):
                self.assertIn(field, text.split("---")[1])
            self.assertIn("references/provenance.md", bundle.namelist())
            bundle.extractall(self.base / "extracted")
        result = subprocess.run([sys.executable, "-B", str(self.base / "extracted/scripts/drama_tools.py"), "doctor"],
                                cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.assertRaises(installer.InstallError):
            installer.package(archive, "generic")


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def run_tool(self, *args):
        result = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)],
                                cwd=self.base, capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def test_existing_project_is_never_overwritten(self):
        project = self.base / "project"
        self.assertEqual(self.run_tool("init-project", project, "--title", "新剧")[0], 0)
        state = (project / ".drama/project.json").read_bytes()
        self.assertEqual(self.run_tool("init-project", project, "--title", "改名")[0], 1)
        self.assertEqual((project / ".drama/project.json").read_bytes(), state)

    def test_identical_copy_fails_and_independent_text_passes(self):
        sample = ROOT / "examples/sample-episode.md"
        code, result = self.run_tool("dup-check", "--new", sample, "--source", sample)
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        self.assertEqual(self.run_tool("dup-check", "--new", sample, "--source", ROOT / "examples/sample-reference.md")[0], 0)

    def test_missing_reference_is_not_silently_skipped(self):
        sample = ROOT / "examples/sample-episode.md"
        code, result = self.run_tool("dup-check", "--new", sample, "--source", sample, self.base / "missing.md")
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])

    def test_short_corpus_cannot_pass(self):
        path = self.base / "short.md"
        path.write_text("中文")
        self.assertEqual(self.run_tool("dup-check", "--new", path, "--source", path)[0], 1)

    def test_invalid_thresholds_rejected(self):
        sample = ROOT / "examples/sample-episode.md"
        for args in (("--k", "0"), ("--threshold", "nan"), ("--threshold", "101")):
            with self.subTest(args=args):
                self.assertEqual(self.run_tool("dup-check", "--new", sample, "--source", sample, *args)[0], 1)
        for value in ("nan", "inf", "-1"):
            self.assertEqual(self.run_tool("episode-check", sample, "--min-delta-ratio", value)[0], 1)

    def test_short_episode_fails_quality_counts(self):
        code, result = self.run_tool("episode-check", ROOT / "examples/sample-episode.md")
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])

    def test_duplicate_episode_titles_rejected(self):
        path = self.base / "episodes.md"
        path.write_text("# 第1集\n片段\n# 第1集\n另一片段\n")
        code, result = self.run_tool("episode-check", path)
        self.assertEqual(code, 1)
        self.assertIn("重复", result["error"])

    def test_unrecognized_episode_format_rejected(self):
        path = self.base / "invalid.md"
        path.write_text("无标题正文")
        self.assertEqual(self.run_tool("episode-check", path)[0], 1)


if __name__ == "__main__":
    unittest.main()
