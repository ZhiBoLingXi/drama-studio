import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/drama-studio"
TOOL = SKILL / "scripts/drama_tools.py"

# Build drama_tools' real argparse tree without running a command: stop at parse_args and print every command path.
LIST_COMMANDS = """
import argparse, json, runpy, sys
class Stop(Exception):
    pass
seen = {}
def capture(self, *args, **kwargs):
    seen["parser"] = self
    raise Stop
argparse.ArgumentParser.parse_args = capture
tool = sys.argv[1]
sys.argv = [tool]
sys.path.insert(0, str(__import__("pathlib").Path(tool).parent))
try:
    runpy.run_path(tool, run_name="__main__")
except Stop:
    pass
def walk(parser, prefix):
    paths = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                paths.extend(walk(sub, prefix + [name]) or [prefix + [name]])
    return paths
print(json.dumps([" ".join(path) for path in walk(seen["parser"], [])]))
"""


def section(text, heading):
    return text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]


class SkillToolListTests(unittest.TestCase):
    def commands(self):
        run = subprocess.run([sys.executable, "-B", "-c", LIST_COMMANDS, str(TOOL)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_every_subcommand_is_listed_in_skill_md(self):
        commands = self.commands()
        for expected in ("doctor", "context-pack", "status", "impact", "receipt record", "receipt cache", "knowledge search",
                         "import-project apply"):
            self.assertIn(expected, commands)
        tools = section((SKILL / "SKILL.md").read_text(encoding="utf-8"), "## 随包工具")
        missing = [command for command in commands if f"drama_tools.py {command}" not in tools]
        self.assertEqual(missing, [], "SKILL.md 的随包工具清单缺少这些子命令")

    def test_each_listed_command_exists(self):
        commands = set(self.commands())
        tools = section((SKILL / "SKILL.md").read_text(encoding="utf-8"), "## 随包工具")
        unknown = []
        for line in tools.splitlines():
            match = re.match(r"\| `drama_tools\.py ([a-z-]+)(?: ([a-z-]+))?", line)
            if match and match.group(1) not in commands and f"{match.group(1)} {match.group(2)}" not in commands:
                unknown.append(line)
        self.assertEqual(unknown, [], "SKILL.md 列出了不存在的子命令")


class SkillRoutingTests(unittest.TestCase):
    def test_writing_route_points_to_the_workstation_flow(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        rows = [line for line in section(text, "## 选择当前阶段").splitlines() if line.startswith("| ")]
        writing = [row for row in rows if "写作" in row.split("|")[1]]
        self.assertEqual(len(writing), 1, writing)
        self.assertIn("(references/writing.md#工位流程)", writing[0])
        self.assertIn("(references/workstations/season-run.md)", writing[0])
        self.assertNotIn("实验性", text)
        steps = section(text, "## 一次完整创作")
        for needle in ("init-project", "status", "context-pack --role author", "reader_effect", "封存", "定向修订一次",
                       "receipt record", "not_sent", "run-handoff", "离线降级"):
            self.assertIn(needle, steps, needle)

    def test_writing_md_starts_with_the_workstation_steps(self):
        text = (SKILL / "references/writing.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## .+$", text, re.M)
        self.assertEqual(headings[:2], ["## 工位流程", "## 离线与单代理降级"])
        flow = section(text, "## 工位流程")
        steps = [line for line in flow.splitlines() if re.match(r"\d+\. ", line)]
        self.assertEqual(len(steps), 8)
        for needle in ("init-project", "drama_tools.py status", "--role author", "reader_effect", "sha256", "changeProposals",
                       "receipt record", "receipt cache", "not_sent", ".drama/runs/", "contract-check"):
            self.assertIn(needle, flow, needle)

    def test_offline_fallback_names_the_real_constraints(self):
        offline = section((SKILL / "references/writing.md").read_text(encoding="utf-8"), "## 离线与单代理降级")
        for needle in ("`local_file`", "`.drama/`", "`.drama/cache/`", "`runs/`", '"not_sent"', "contract-check remote-receipt",
                       "`serial_self_review`", "claimsIndependence", "--config", "未写入 mali-story"):
            self.assertIn(needle, offline, needle)

    def test_season_run_carries_the_batch_rules(self):
        text = (SKILL / "references/workstations/season-run.md").read_text(encoding="utf-8")
        for needle in ("一个写者", "前一批保存", "精修", "先上报", "像后补", "cmp", "fingerprint", "--reconciles",
                       "不换新 requestId", "临时文件", "跨段对账"):
            self.assertIn(needle, text, needle)
        self.assertNotIn("docs/", text)  # the installed skill has no docs/ folder
        index = (SKILL / "references/workstations/README.md").read_text(encoding="utf-8")
        self.assertIn("(season-run.md)", index)


if __name__ == "__main__":
    unittest.main()
