"""decision: add (from a run-handoff or one entry), list, decide (only with the person's words), check."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/checks/decision.py")]


def entry(eid="DQ-1", **extra):
    out = {"id": eid, "kind": "setting_conflict", "question": "箱子是签收还是拒收",
           "options": [{"optionId": "keep", "text": "保持签收", "losesFunctions": []},
                       {"optionId": "refuse", "text": "改成拒收", "losesFunctions": [{"functionId": "F-box-2"}]}],
           "default": "keep", "defaultReason": "不让功能句落空", "affects": ["F-box-1"], "status": "pending", "humanWords": None}
    out.update(extra)
    return out


HANDOFF = {"runId": "run-7", "workstation": "C4", "changeProposals": [
    {"targetLayer": "C3", "problem": "第 3 集仓管凭什么知道签收人", "evidence": {"kind": "local_file", "id": "plan.json", "revision": None},
     "proposedChange": "补一条仓管的登记簿", "unknownScope": "第 4 集", "needsDecision": True, "default": "apply", "defaultReason": "改动最小"},
    {"targetLayer": "C4", "problem": "措辞", "evidence": {"kind": "local_file", "id": "plan.json", "revision": None},
     "proposedChange": "换个说法", "unknownScope": "", "needsDecision": False}]}


class Decision(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.queue = self.dir / "decisions.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        path = self.dir / name
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def run_tool(self, *args):
        result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def check(self, entries):
        return self.run_tool("check", self.write("q.json", {"entries": entries}))

    def test_check_clean_queue(self):
        code, out = self.check([entry()])
        self.assertEqual((code, out["passed"], out["errors"]), (0, True, []))
        self.assertIn("reproduceCommand", out)

    def test_check_default_must_exist_and_lose_no_function(self):
        code, out = self.check([entry(default="refuse")])
        self.assertEqual(code, 2)
        self.assertIn("losesFunctions", out["errors"][0])
        code, out = self.check([entry(default="other")])
        self.assertIn("不在 options", out["errors"][0])
        code, out = self.check([entry(default=None)])
        self.assertIn("default 为空", out["errors"][0])

    def test_check_not_evaluable_placeholder_is_allowed(self):
        e = entry()
        e["options"][0]["losesFunctions"] = "not_evaluable：范围外未核"
        self.assertEqual(self.check([e])[0], 0)

    def test_check_kind_ids_and_decided_words(self):
        code, out = self.check([entry(kind="season"), entry()])
        joined = " ".join(out["errors"])
        self.assertIn("kind='season'", joined)
        self.assertIn("重复", joined)
        code, out = self.check([entry(status="decided", decision="keep")])
        self.assertIn("humanWords", out["errors"][0])
        self.assertEqual(self.check([entry(status="decided", decision="keep", humanWords="就签收")])[0], 0)

    def test_add_from_handoff_registers_and_skips(self):
        code, out = self.run_tool("add", self.queue, "--from-handoff", self.write("h.json", HANDOFF))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["added"], ["DQ-run-7-1"])
        self.assertEqual(len(out["skipped"]), 1)
        doc = json.loads(self.queue.read_text(encoding="utf-8"))
        added = doc["entries"][0]
        self.assertEqual((added["kind"], added["default"], [o["optionId"] for o in added["options"]]), ("upstream_change", "apply", ["apply", "keep"]))
        self.assertEqual(self.run_tool("check", self.queue)[0], 0)

    def test_add_from_handoff_without_default_writes_nothing(self):
        handoff = json.loads(json.dumps(HANDOFF))
        del handoff["changeProposals"][0]["default"]
        code, out = self.run_tool("add", self.queue, "--from-handoff", self.write("h.json", handoff))
        self.assertEqual((code, out["written"]), (2, False))
        self.assertFalse(self.queue.exists())

    def test_add_entry_refuses_duplicates(self):
        e = self.write("e.json", entry())
        self.assertEqual(self.run_tool("add", self.queue, "--entry", e)[0], 0)
        code, out = self.run_tool("add", self.queue, "--entry", e)
        self.assertEqual(code, 2)
        self.assertIn("已在队列里", out["refused"][0])

    def test_decide_needs_human_words_and_never_overwrites(self):
        self.write("decisions.json", {"entries": [entry()]})
        code, out = self.run_tool("decide", self.queue, "--id", "DQ-1", "--option", "refuse", "--human-words", " ")
        self.assertEqual((code, out["written"]), (2, False))
        code, out = self.run_tool("decide", self.queue, "--id", "DQ-1", "--option", "refuse", "--human-words", "改成拒收，F-box-2 我另想", "--decided-by", "主创")
        self.assertEqual(code, 0, out)
        doc = json.loads(self.queue.read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual((doc["status"], doc["decision"], doc["decidedBy"]), ("decided", "refuse", "主创"))
        code, out = self.run_tool("decide", self.queue, "--id", "DQ-1", "--option", "keep", "--human-words", "又改主意")
        self.assertEqual(code, 2)

    def test_list_filters_status(self):
        self.write("decisions.json", {"entries": [entry(), entry("DQ-2", status="decided", decision="keep", humanWords="好")]})
        code, out = self.run_tool("list", self.queue, "--status", "pending")
        self.assertEqual([r["id"] for r in out["entries"]], ["DQ-1"])


if __name__ == "__main__":
    unittest.main()
