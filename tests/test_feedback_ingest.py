import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts"

TEXT = "# 第1集\n场1-1 镇上仓库 日 内\n人物：老陈、王姨\n老陈：别碰！\n王姨：烧了算了。\n老陈：钥匙给你。\n"


def lark_export(*comments):
    data = {f"c{i}": {"data": (f'<comment comment-id="{i}" block-id="b"><quote>{quote}</quote>'
                                + "".join(f'<msg user="编剧">{m}</msg>' for m in msgs) + "</comment>")}
            for i, (quote, msgs) in enumerate(comments, start=1)}
    return {"ok": True, "data": {"document": {"reference_map": {"comments": data}}}}


class FeedbackIngestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.text = self.write("text.md", TEXT)

    def write(self, name, value):
        path = self.dir / name
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def ingest(self, path, *args):
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "feedback_ingest.py"), str(path), *map(str, args)],
                             capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_lark_comments_become_project_writer_notes_with_levels(self):
        path = self.write("c.json", lark_export(("老陈：别碰！", ["别碰什么？要交代动作的宾语。"]),
                                                 ("王姨：烧了算了。", ["没看懂在烧什么，讲清楚。"]),
                                                 ("老陈：钥匙给你。", ["老陈：抽屉钥匙给你。"])))
        before = sorted(p.name for p in self.dir.iterdir())
        code, result = self.ingest(path, "--text", self.text)
        self.assertEqual(code, 0)
        notes = result["writerNotes"]
        self.assertTrue(all(n["scope"]["level"] == "project" for n in notes))
        self.assertEqual([n["level"] for n in notes], ["info_carriage", "info_carriage", "line"])
        self.assertEqual([n["attachesTo"]["lineRef"] for n in notes], [4, 5, 6])
        self.assertEqual(notes[2]["humanSuggestion"], "老陈：抽屉钥匙给你。")
        self.assertEqual(notes[0]["signalQuality"], "low")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)
        self.assertIn("feedback_ingest.py", result["reproduceCommand"])

    def test_routing_and_recurrence_drafts(self):
        path = self.write("c.json", lark_export(("老陈：别碰！", ["要交代宾语"]), ("王姨：烧了算了。", ["没看懂"]),
                                                 ("老陈：钥匙给你。", ["老陈：抽屉钥匙给你。"])))
        _, result = self.ingest(path)
        kinds = [(d["kind"], d["status"]) for d in result["derivedDrafts"]]
        self.assertIn(("humanPositive", "listed_not_written"), kinds)
        recurring = [d for d in result["derivedDrafts"] if d["status"] == "drafted_on_recurrence"]
        self.assertEqual({(d["kind"], d["groupedBy"], len(d["fromNotes"])) for d in recurring},
                         {("conventionDraft", "info_carriage", 2), ("questionDraft", "info_carriage", 2)})

    def test_single_note_does_not_draft_and_unknown_is_unrouted(self):
        path = self.write("c.json", {"comments": [{"commentId": "x1", "quote": "老陈：别碰！", "text": "嗯……再想想"}]})
        _, result = self.ingest(path)
        self.assertEqual(result["unrouted"], [result["writerNotes"][0]["noteId"]])
        self.assertEqual(result["derivedDrafts"], [])

    def test_explicit_level_routes_procedure_to_ledger_and_k1(self):
        path = self.write("c.json", {"comments": [{"commentId": "x1", "quote": "老陈：钥匙给你。", "text": "取件要本人",
                                                   "level": "procedure"}]})
        _, result = self.ingest(path)
        self.assertEqual({d["kind"] for d in result["derivedDrafts"]}, {"ledgerProposal", "k1Draft"})
        bad = self.write("bad.json", {"comments": [{"quote": "x", "text": "y", "level": "vibes"}]})
        self.assertEqual(self.ingest(bad)[0], 1)

    def test_conflicting_suggestions_on_same_line(self):
        path = self.write("c.json", {"comments": [{"commentId": "a", "quote": "老陈：钥匙给你。", "suggestion": "老陈：拿着。"},
                                                  {"commentId": "b", "quote": "老陈：钥匙给你。", "suggestion": "老陈：钥匙，拿好。"}]})
        _, result = self.ingest(path, "--text", self.text)
        a, b = result["writerNotes"]
        self.assertEqual((a["conflictsWith"], b["conflictsWith"]), ([b["noteId"]], [a["noteId"]]))

    def test_revised_text_diff_and_verbatim_record(self):
        revised = self.write("rev.md", TEXT.replace("老陈：别碰！", "老陈：别碰开关！") + "王姨：哎。\n")
        _, result = self.ingest(revised, "--original", self.text, "--author", "编剧")
        self.assertEqual([(n["level"], n["levelBasis"]) for n in result["writerNotes"]], [("line", "diff"), ("exchange", "diff")])
        self.assertEqual(result["writerNotes"][0]["attachesTo"]["lineRef"], 4)
        self.assertEqual(result["writerNotes"][0]["author"], "编剧")
        record = self.write("said.md", "# 原话\n\n> 老陈：别碰！\n这里得说清楚碰什么 [level: info_carriage]\n\n就这么定了，不拆集\n")
        _, result = self.ingest(record)
        self.assertEqual([(n["level"], n["levelBasis"]) for n in result["writerNotes"]],
                         [("info_carriage", "explicit"), ("decision", "lexicon")])
        self.assertEqual(result["writerNotes"][0]["quotedText"], "老陈：别碰！")


if __name__ == "__main__":
    unittest.main()
