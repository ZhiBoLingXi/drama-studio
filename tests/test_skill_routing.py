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
        self.assertIn("(references/workstation-season-run.md)", writing[0])
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
        self.assertEqual(len(steps), 10)
        for needle in ("init-project", "drama_tools.py status", "--role author", "reader_effect", "sha256", "changeProposals",
                       "receipt record", "receipt cache", "not_sent", ".drama/runs/", "contract-check", "season-check",
                       # D6-3 (plan §4.4 exit condition) changed this on purpose: dialogue_author, dialogue_read (the retired
                       # dialogue pass and dialogue read) were needles; the steps now go through C5a and the C6 reads
                       "runs/state/after-ep-", "一集一个作者运行", "dialogue_designer", "cold_reader", "situation_checker"):
            self.assertIn(needle, flow, needle)

    def test_offline_fallback_names_the_real_constraints(self):
        offline = section((SKILL / "references/writing.md").read_text(encoding="utf-8"), "## 离线与单代理降级")
        for needle in ("`local_file`", "`.drama/`", "`.drama/cache/`", "`runs/`", '"not_sent"', "contract-check remote-receipt",
                       "`serial_self_review`", "claimsIndependence", "--config", "未写入 mali-story"):
            self.assertIn(needle, offline, needle)

    def test_season_run_carries_the_batch_rules(self):
        text = (SKILL / "references/workstation-season-run.md").read_text(encoding="utf-8")
        for needle in ("一个写者", "前一批保存", "精修", "先上报", "像后补", "cmp", "fingerprint", "--reconciles",
                       "不换新 requestId", "临时文件", "跨段对账"):
            self.assertIn(needle, text, needle)
        self.assertNotIn("docs/", text)  # the installed skill has no docs/ folder
        index = (SKILL / "references/workstations.md").read_text(encoding="utf-8")
        self.assertIn("(workstation-season-run.md)", index)


class DialogueLayerRoutingTests(unittest.TestCase):
    """D6-3: writing.md no longer has the dialogue pass or the dialogue read as steps; the tool table names --legacy-dialogue."""

    def test_writing_steps_have_no_dialogue_pass_or_read(self):
        flow = section((SKILL / "references/writing.md").read_text(encoding="utf-8"), "## 工位流程")
        steps = [line for line in flow.splitlines() if re.match(r"\d+\. ", line)]
        for retired in ("台词遍", "台词读"):
            self.assertFalse([s for s in steps if retired in s], retired)

    def test_tool_table_names_the_legacy_flag(self):
        tools = section((SKILL / "SKILL.md").read_text(encoding="utf-8"), "## 随包工具")
        row = next(line for line in tools.splitlines() if "drama_tools.py season-check" in line)
        self.assertIn("--legacy-dialogue", row)


class OutlineLayerRoutingTests(unittest.TestCase):
    """D6-2: the outline layer (C3a -> C3b -> C3c -> C4) is the default route; C3 is split into three workstation files."""

    def test_planning_route_reads_planning_and_the_outline_layer(self):
        rows = [line for line in section((SKILL / "SKILL.md").read_text(encoding="utf-8"), "## 选择当前阶段").splitlines()
                if line.startswith("| ") and "原创选题" in line.split("|")[1]]
        self.assertEqual(len(rows), 1, rows)
        for needle in ("(references/planning.md)", "(references/outline-layer.md)"):
            self.assertIn(needle, rows[0], needle)

    def test_full_run_step_six_goes_c3a_to_c4(self):
        steps = section((SKILL / "SKILL.md").read_text(encoding="utf-8"), "## 一次完整创作")
        six = next(line for line in steps.splitlines() if line.startswith("6. "))
        positions = [six.find(name) for name in ("C3a", "C3b", "C3c", "C4")]
        self.assertTrue(all(p >= 0 for p in positions) and positions == sorted(positions), six)
        for needle in ("(references/outline-layer.md)", "决定队列", "plan-check"):
            self.assertIn(needle, six, needle)

    def test_c3_is_three_files_linked_from_the_index(self):
        folder = SKILL / "references"
        index = (folder / "workstations.md").read_text(encoding="utf-8")
        for name in ("workstation-c3a-function-map.md", "workstation-c3b-ledger.md", "workstation-c3c-season-plan.md"):
            self.assertTrue((folder / name).is_file(), name)
            self.assertIn(f"({name})", index, name)
        self.assertFalse((folder / "workstation-c3-structure.md").exists())
        stale = [str(path.relative_to(SKILL)) for path in SKILL.rglob("*.md") if "c3-structure.md" in path.read_text(encoding="utf-8")]
        self.assertEqual(stale, [], "仍链到已删的 c3-structure.md")
        self.assertTrue((SKILL / "references/outline-layer.md").is_file())

    def test_writing_step_three_has_no_key_choice_hard_item(self):
        flow = section((SKILL / "references/writing.md").read_text(encoding="utf-8"), "## 工位流程")
        three = next(line for line in flow.splitlines() if line.startswith("3. "))
        self.assertNotIn("关键选择", three)
        for needle in ("plan-check", "capacity.status", "(outline-layer.md"):
            self.assertIn(needle, three, needle)


if __name__ == "__main__":
    unittest.main()
