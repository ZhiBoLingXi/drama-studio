"""drama_tools D6-1 wiring: every new subcommand is reachable, prints JSON with a drama_tools reproduceCommand, and the
contract-check context flags, episode-check --speech and dup-check --list-hits reach their modules. Synthetic fixtures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
TEXT = "# 第3集\n\n场3-1 镇口小卖部 上午\n△刘叔递过一包烟。\n刘叔：你那箱子，该不会也在里头？\n老陈（愣住）：哪个仓库？\n"
COMMANDS = ["ledger", "plan-check", "season-plan-check", "capacity", "decision", "function-map", "defects build", "check-answers",
            "retell-check", "answers-consistency", "dialogue-plan-check", "plan-text-consistency", "dialogue-diagnose",
            "feedback-ingest", "corpus segment", "corpus label", "corpus filter", "corpus lexicon", "corpus rate"]


def run(*args, cwd=None):
    result = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


class D6CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.text = self.base / "ep-003.md"
        self.text.write_text(TEXT, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def json(self, *args):
        code, out, err = run(*args, cwd=self.base)
        return code, json.loads(out or err)

    def test_every_new_subcommand_answers_help(self):
        for command in COMMANDS:
            code, out, err = run(*command.split(), "--help")
            self.assertEqual(code, 0, f"{command}: {err}")
            self.assertIn("usage:", out, command)

    def test_unknown_corpus_command_is_an_input_error(self):
        code, out, err = run("corpus", "fetch")
        self.assertEqual(code, 1)
        self.assertIn("segment", json.loads(err)["error"])

    def test_reproduce_command_is_the_drama_tools_form(self):
        code, out = self.json("capacity", "text", "ep-003.md", "--media", EXAMPLES / "media-profile.json")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["reproduceCommand"],
                         f"python3 -B {TOOL} capacity text {self.text.resolve()} --media {EXAMPLES / 'media-profile.json'}")
        again = subprocess.run(out["reproduceCommand"].split(), capture_output=True, text=True)
        self.assertEqual((again.returncode, json.loads(again.stdout)["estimateSecA"]), (0, out["estimateSecA"]))

    def test_defects_build_reproduces_as_defects_build(self):
        code, out = self.json("defects", "build", "--records", EXAMPLES / "answers.json")
        self.assertEqual(code, 0, out)
        self.assertIn(f"{TOOL} defects build --records ", out["reproduceCommand"])

    def test_dup_check_list_hits(self):
        source = self.base / "source.md"
        source.write_text("刘叔：你那箱子，该不会也在里头？\n", encoding="utf-8")
        code, out = self.json("dup-check", "--list-hits", "--k", "8", "--new", self.text, "--source", source)
        self.assertEqual(code, 0, out)
        self.assertGreater(out["hitCount"], 0)
        self.assertIsNone(out["passed"])
        self.assertTrue(out["reproduceCommand"].startswith(f"python3 -B {TOOL} dup-check --list-hits --k 8"))
        code, old = self.json("dup-check", "--new", self.text, "--source", source)
        self.assertNotIn("hits", old)

    def test_episode_check_speech_is_opt_in(self):
        code, out = self.json("episode-check", self.text, "--speech")
        self.assertEqual(code, 0, out)
        self.assertIn("speech_chars", out["episodes"][0]["speech"])
        code, plain = self.json("episode-check", self.text)
        self.assertNotIn("speech", plain["episodes"][0])

    def test_contract_check_cards_context(self):
        answers = EXAMPLES / "answers.json"
        code, out = self.json("contract-check", "answers", answers)
        self.assertEqual(code, 0, out)
        self.assertTrue(any("--cards" in note for note in out["notEvaluated"]))
        card = json.loads((EXAMPLES / "knowledge-card.json").read_text(encoding="utf-8"))
        card.update(cardId="K1-tuijian", coverage="empty")
        cards = self.base / "cards"
        cards.mkdir()
        (cards / "K1-tuijian@r1.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        code, out = self.json("contract-check", "answers", answers, "--cards", cards)
        self.assertEqual(code, 2)
        self.assertTrue(any("empty card" in error for error in out["errors"]), out["errors"])
        self.assertTrue(out["reproduceCommand"].endswith(f"contract-check answers {answers} --cards {cards}"))

    def test_contract_check_records_context(self):
        fmap, record = EXAMPLES / "function-map.json", json.loads((EXAMPLES / "answers.json").read_text(encoding="utf-8"))
        good = self.base / "rc-good.json"
        good.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        code, out = self.json("contract-check", "function-map", fmap, "--records", good)
        self.assertEqual((code, out["notEvaluated"]), (0, []), out)
        del record["answers"][1]["disposition"]
        bad = self.base / "rc-bad.json"
        bad.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        code, out = self.json("contract-check", "function-map", fmap, "--records", bad)
        self.assertEqual(code, 2)
        self.assertTrue(any("without a disposition" in error for error in out["errors"]), out["errors"])

    def test_contract_check_without_context_flags_is_unchanged(self):
        code, out = self.json("contract-check", "task", EXAMPLES / "task.json")
        self.assertEqual(out["reproduceCommand"], f"python3 -B {TOOL} contract-check task {(EXAMPLES / 'task.json').absolute()}")

    def test_new_commands_run_with_the_network_blocked(self):
        script = ("import runpy, socket, sys\n"
                  "def refuse(*a, **k):\n    raise OSError('network blocked in test')\n"
                  "socket.socket = refuse\nsocket.create_connection = refuse\n"
                  f"sys.argv = [{str(TOOL)!r}, 'capacity', 'text', {str(self.text)!r}, '--media', {str(EXAMPLES / 'media-profile.json')!r}]\n"
                  f"sys.path.insert(0, {str(TOOL.parent)!r})\n"
                  f"runpy.run_path({str(TOOL)!r}, run_name='__main__')\n")
        result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("estimateSecA", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
