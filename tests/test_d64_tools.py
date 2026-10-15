"""D6-4 tools: corpus fetch bookkeeping, corpus agree (double run), corpus defaults (recomputed statistics),
feedback-ingest full routing, and the packing and contract rules that come with them.

Fabricated fixtures only (no network, no real corpus); one passing and one failing case per S rule.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/drama-studio/scripts"
TOOL = SCRIPTS / "drama_tools.py"
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "checks/corpus"))
from checks import contract_check as contracts  # noqa: E402
import defaults as corpus_defaults  # noqa: E402


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    text = proc.stdout if proc.stdout.lstrip().startswith("{") else proc.stderr
    return proc.returncode, json.loads(text) if text.strip() else {}


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path


class CorpusFetch(Temp):
    def setUp(self):
        super().setUp()
        templates = [{"templateId": f"T{i}", "episodes": list(range(1, 15)), "snapshotIds": {"1": f"snap-T{i}-1"}} for i in range(1, 5)]
        self.ledger = self.base / "ledger.json"
        code, out = tool("corpus", "fetch", "plan", self.write("templates.json", templates), "--out", self.ledger)
        self.assertEqual((code, out["items"]), (0, 30))  # 3 series x 10 episodes, the pilot read

    def record(self, template, episode, response):
        return tool("corpus", "fetch", "record", self.ledger, "--template", template, "--episode", episode,
                    "--response", self.write(f"r-{template}-{episode}-{len(response)}.json", response))

    def budget(self, label, credits, receipts, mode="configured"):
        return tool("corpus", "fetch", "budget", self.ledger, "--label", label,
                    "--reading", self.write(f"b-{label}.json", {"data": {"budgetMode": mode, "availableCredits": credits}}),
                    "--receipts", self.write(f"rc-{label}.json", {"receipts": [{"receiptId": r} for r in receipts]}))

    def test_a_plan_is_never_rebuilt(self):
        code, out = tool("corpus", "fetch", "plan", self.write("t2.json", [{"templateId": "X", "episodesTotal": 3}]), "--out", self.ledger)
        self.assertEqual(code, 1)

    def test_snapshot_checks_and_the_break_list(self):
        code, out = self.record("T1", 1, {"data": {"snapshotId": "snap-T1-1"}})
        self.assertEqual(out["call"]["snapshotCheck"], "match")
        self.record("T1", 2, {"error": {"code": "RESOURCE_NOT_FOUND"}})
        self.record("T1", 3, {"error": "timeout"})
        self.record("T1", 3, {"error": "timeout"})
        self.record("T1", 3, {"error": "timeout"})
        code, out = tool("corpus", "fetch", "resume", self.ledger)
        self.assertEqual(out["done"], 1)
        self.assertEqual([(r["templateId"], r["episodeIndex"]) for r in out["retry"]], [("T1", 2)])
        self.assertEqual([(r["templateId"], r["episodeIndex"]) for r in out["givenUp"]], [("T1", 3)])
        self.assertEqual(len(out["pending"]), 27)
        code, out = self.record("T2", 1, {"data": {"snapshotId": "snap-OTHER"}})
        self.assertEqual(out["call"]["snapshotCheck"], "snapshot_mismatch")
        code, out = tool("corpus", "fetch", "verify", self.ledger)
        self.assertEqual(code, 2)
        self.assertEqual(out["snapshotMismatches"][0]["templateId"], "T2")

    def test_billing_signals(self):
        self.budget("before", 100, [])
        self.record("T1", 1, {"data": {"snapshotId": "snap-T1-1"}})
        self.budget("after", 100, [])
        code, out = tool("corpus", "fetch", "verify", self.ledger)
        self.assertEqual((code, out["billing"]), (0, "no_change_seen"))
        self.budget("after-2", 100, ["R-1"])
        code, out = tool("corpus", "fetch", "verify", self.ledger)
        self.assertEqual((code, out["billing"], out["observation"]["receiptIds"]), (2, "deduction_seen", ["R-1"]))

    def test_unconfigured_budget_is_unconfirmed_not_clean(self):
        self.budget("before", None, [], mode="unconfigured")
        self.budget("after", None, [], mode="unconfigured")
        code, out = tool("corpus", "fetch", "verify", self.ledger)
        self.assertEqual((code, out["billing"]), (0, "unconfirmed"))
        self.assertEqual(out["observation"]["budgetReadings"][0]["budgetMode"], "unconfigured")


class CorpusAgree(Temp):
    def row(self, ident, run1, run2, **extra):
        return {"exchangeId": ident, "quality": {"transcript": "ok", "label": "ok"}, "labelRuns": {"run1": run1, "run2": run2},
                "lines": [{"t0": 0, "t1": 1, "speaker": "甲", "text": "嗯"}, {"t0": 1, "t1": 2, "speaker": "乙", "text": "好"}], **extra}

    def labels(self):
        same = {"function": "问清", "relation": "大人对孩子", "infoMode": ["问答"]}
        rows = [self.row("E1", same, same),
                self.row("E2", {"function": "请求", "relation": "亲人-父母子女", "infoMode": ["问答"]},
                         {"function": "求助", "relation": "大人对孩子", "infoMode": ["问答", "追问链"]}),
                self.row("E3", {"function": "训斥", "relation": "对手", "infoMode": ["问答"]},
                         {"function": "安抚", "relation": "对手", "infoMode": ["问答"]}),
                {"exchangeId": "E4", "quality": {"label": "ok"}}]
        return self.write("x.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

    def test_synonyms_and_the_more_specific_relation_agree(self):
        code, out = tool("corpus", "agree", self.labels())
        self.assertEqual((code, out["compared"], out["notDoubleRun"]), (0, 3, 1))
        e2 = next(r for r in out["records"] if r["exchangeId"] == "E2")
        self.assertEqual((e2["labelConfidence"], e2["converged"]["relation"], e2["converged"]["function"]), ("high", "亲人-父母子女", "请求"))
        self.assertEqual(out["low"], ["E3"])

    def test_low_labels_are_written_and_kept_out_of_the_filter_pass_list(self):
        out_path = self.base / "agreed.jsonl"
        code, out = tool("corpus", "agree", self.labels(), "--out", out_path)
        self.assertEqual(code, 0)
        rows = {json.loads(l)["exchangeId"]: json.loads(l) for l in out_path.read_text(encoding="utf-8").splitlines()}
        self.assertEqual((rows["E3"]["quality"]["label"], rows["E1"]["labelConfidence"]), ("low", "high"))
        code, filtered = tool("corpus", "filter", out_path)
        reasons = {r["exchangeId"]: r["reasons"] for r in filtered["results"]}
        self.assertIn("label_low", reasons["E3"])
        self.assertNotIn("label_low", reasons["E1"])
        self.assertEqual(tool("corpus", "agree", self.labels(), "--out", out_path)[0], 1)  # never overwrites


class CorpusDefaults(unittest.TestCase):
    def rows(self):
        def ex(genre, fmt, text, start, end, episode):
            return {"templateId": f"{genre}-T", "episodeIndex": episode, "series": {"genre": genre, "format": fmt}, "startMs": start, "endMs": end,
                    "lines": [{"speaker": "糯糯", "text": text}, {"speaker": "师父", "text": "嗯"}]}
        return [ex("仙侠/萌宝", "anime", "为师今天带你下山历练", 0, 12000, 1), ex("仙侠/萌宝", "anime", "为师说了下山要小心", 0, 8000, 2),
                ex("仙侠/萌宝", "anime", "下山之前先拜师门", 0, 10000, 3), ex("现实/家庭", "live", "妈，我下班了", 0, 6000, 1)]

    def test_exchange_medians_carry_n(self):
        self.assertEqual(corpus_defaults.exchange_medians(self.rows()),
                         {"anime": {"value": 10.0, "n": 3, "source": "measured_corpus"}, "live": {"value": 6.0, "n": 1, "source": "measured_corpus"}})

    def test_lexicon_confirms_words_and_proposes_candidates_without_names(self):
        lexicon = {"lists": [{"fromGenre": "仙侠／古装玄幻", "words": ["为师", "下山", "金丹"]},
                             {"fromGenre": "霸总／都市言情", "words": ["总裁"]}]}
        xianxia, bazong = corpus_defaults.lexicon_stats(self.rows(), lexicon)
        self.assertEqual((xianxia["confirmed"], xianxia["notSeen"]), (["下山", "为师"], ["金丹"]))
        self.assertTrue(all("糯" not in c["word"] for c in xianxia["candidates"]))
        self.assertEqual((bazong["evaluable"], bazong["n"]["exchanges"]), (False, 0))

    def test_the_bundled_files_carry_n(self):
        media = json.loads((ROOT / "skills/drama-studio/schemas/data/default-media-profile.json").read_text(encoding="utf-8"))
        self.assertTrue(all("n" in v for v in media["formatDefault"].values()))
        self.assertTrue(all("n" in v for v in media["exchangeMedianSec"].values()))
        lexicon = json.loads((ROOT / "skills/drama-studio/schemas/data/genre-lexicon.json").read_text(encoding="utf-8"))
        self.assertTrue(all("n" in entry["measured"] for entry in lexicon["lists"]))
        self.assertTrue(all("candidates" not in entry["measured"] for entry in lexicon["lists"]))  # no corpus words beyond the lists


class FeedbackRouting(Temp):
    NOTES = """# 批注（编造）

### n1

> 刘叔：东西在那边。

- 「东西」「那边」是什么没交代，观众看不懂。

### n2

> 仓管：寄件人签了字就能退。

- 这个程序不是这样走的：退件要寄件人本人带身份证来，签字不够。

### n3

> 王姨：就这么办吧。

- 就这么定了，第 6 集不加夜戏。
"""

    def ingest(self, *args):
        return tool("feedback-ingest", *args)

    def test_a_note_becomes_a_negative_and_a_procedure_note_a_ledger_proposal(self):
        out = self.base / "derived"
        code, result = self.ingest(self.write("notes.md", self.NOTES), "--out", out)
        self.assertEqual(code, 0, result)
        levels = [n["level"] for n in result["writerNotes"]]
        self.assertEqual(levels, ["info_carriage", "procedure", "decision"])
        negatives = [json.loads(l) for l in (out / "negatives.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(negatives[0]["fromNotes"], [result["writerNotes"][0]["noteId"]])
        proposals = [json.loads(l) for l in (out / "ledger-proposals.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(proposals[0]["fromNotes"], [result["writerNotes"][1]["noteId"]])
        self.assertTrue((out / "k1-drafts.jsonl").is_file())
        queue = json.loads((out / "decisions.json").read_text(encoding="utf-8"))
        self.assertEqual(contracts.check_contract("decision-queue", queue), [])
        self.assertEqual(queue["entries"][0]["status"], "decided")

    def test_purge_by_note_id_and_no_overwrite(self):
        out = self.base / "derived"
        code, result = self.ingest(self.write("notes.md", self.NOTES), "--out", out)
        procedure = result["writerNotes"][1]["noteId"]
        code, purged = self.ingest("--purge", procedure, "--out", out)
        self.assertEqual(purged["removed"], {"k1-drafts.jsonl": 1, "ledger-proposals.jsonl": 1})
        self.assertEqual((out / "ledger-proposals.jsonl").read_text(encoding="utf-8"), "")
        self.assertEqual(self.ingest(self.write("notes.md", self.NOTES), "--out", out)[0], 1)  # --out not empty

    def test_a_reality_review_s_procedure_answers_route_to_the_ledger(self):
        record = example("answers")
        record["answers"][1]["landsOn"] = "D-box-p01 无人领取的件满期退回"
        code, result = self.ingest(self.write("rc.json", record), "--out", self.base / "rc")
        self.assertEqual([n["level"] for n in result["writerNotes"]], ["procedure"])
        self.assertEqual(result["derivedCounts"]["ledgerProposal"], 1)

    def test_contrast_pair_drafts_pass_contract_check_and_studio_ones_do_not(self):
        comments = {"comments": [{"commentId": "a", "quote": "老陈：钥匙给你。", "text": "这两句话题跳了",
                                  "suggestion": "老陈：抽屉钥匙给你。"}]}
        out = self.base / "pairs"
        self.ingest(self.write("c.json", comments), "--out", out)
        pair = json.loads((out / "contrast-pairs.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(contracts.check_contract("contrast-pair", pair), [])
        pair["scope"] = {"level": "studio"}  # a record holding the project's own sentences cannot go studio-wide
        self.assertTrue(any("project" in e for e in contracts.check_contract("contrast-pair", pair)))
        note = example("writer-note")
        note["scope"] = {"level": "studio"}
        self.assertTrue(contracts.check_contract("writer-note", note))


class TargetRevision(Temp):
    def test_a_bumped_target_has_a_changelog_and_tasks_on_the_old_revision_still_pass(self):
        notes = "\n".join(f"### n{i}\n\n> 刘叔：东西在那边。\n\n- 宾语没交代，观众看不懂。\n" for i in (1, 2))
        target = self.write("target.json", example("dialogue-target"))
        out = self.base / "derived"
        code, result = tool("feedback-ingest", self.write("notes.md", notes), "--out", out, "--target", target)
        self.assertEqual(code, 0, result)
        bumped = json.loads((out / "dialogue-target.v0.2.json").read_text(encoding="utf-8"))
        self.assertEqual(contracts.check_contract("dialogue-target", bumped), [])
        self.assertEqual((bumped["changelog"][-1]["revision"], bumped["changelog"][-1]["from"]), ("v0.2", "v0.1"))
        self.assertTrue(all(c["sourceNotes"] for c in bumped["conventions"]))
        task = example("task")
        task.update(layer="C5b", dialogueTarget={"targetId": "town-dialogue-target", "revision": "v0.1"})
        self.assertEqual(contracts.check_contract("task", task), [])
        self.assertEqual(example("dialogue-target")["revision"], "v0.1")  # the old file is untouched

    def test_a_changelog_without_this_revision_fails(self):
        doc = example("dialogue-target")
        doc["revision"] = "v0.2"
        self.assertTrue(any("changelog" in e for e in contracts.check_contract("dialogue-target", doc)))
        doc["changelog"].insert(0, {"revision": "v0.2", "change": "新增约定 C2"})  # newest first, as D6-0 wrote it
        self.assertEqual(contracts.check_contract("dialogue-target", doc), [])


class UnsourcedNotPacked(Temp):
    def test_a_contrast_pair_without_a_source_is_refused(self):
        sys.path.insert(0, str(Path(__file__).parent))
        import test_context_pack_d6 as packs
        case = packs.D6PackTests("test_two_positives_and_one_pair_per_topic")
        case.setUp()
        try:
            case.write("runs/contrast-pairs.jsonl", json.dumps({"pairId": "CP-01", "whyNotHere": "x"}, ensure_ascii=False) + "\n")
            code, out = case.sample_pack(20000)
            self.assertEqual(code, 1, out)
            self.assertIn("无来源", out["error"])
        finally:
            case.tearDown()


class CorpusRootPackable(Temp):
    """corpus/ at the project root is a sample root (D6-4 decisions §2); runs/<...>/corpus stays readable."""

    def case(self):
        sys.path.insert(0, str(Path(__file__).parent))
        import test_context_pack_d6 as packs
        case = packs.D6PackTests("test_two_positives_and_one_pair_per_topic")
        case.setUp()
        self.addCleanup(case.tearDown)
        return case

    def pack_with(self, case, exemplars):
        items = [("current_plan", "runs/plan/episode-plan-003.json"), ("current_plan", "runs/plan/dialogue-plan-003.json")]
        return case.pack("dialogue_designer", items, 20000, "--exemplars", str(exemplars),
                         "--contrast-pairs", str(case.project / "runs/contrast-pairs.jsonl"))

    def test_corpus_at_the_project_root_and_under_runs_are_both_packed(self):
        case = self.case()
        case.write("corpus/exchanges.jsonl", (case.project / "runs/corpus/exchanges.jsonl").read_text(encoding="utf-8"))
        for path in (case.project / "corpus/exchanges.jsonl", case.project / "runs/corpus/exchanges.jsonl"):
            code, out = self.pack_with(case, path)
            self.assertEqual(code, 0, out.get("errors"))
            self.assertIn("sample T1 正例 EX-0001", [i["ref"] for i in out["items"]])

    def test_a_folder_that_is_not_a_sample_root_is_refused(self):
        case = self.case()
        case.write("corpora/exchanges.jsonl", (case.project / "runs/corpus/exchanges.jsonl").read_text(encoding="utf-8"))
        code, out = self.pack_with(case, case.project / "corpora/exchanges.jsonl")
        self.assertEqual(code, 1, out)
        self.assertIn("corpus/", out["error"])


if __name__ == "__main__":
    unittest.main()
