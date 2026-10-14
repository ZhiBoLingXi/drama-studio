"""D6-3 walkthrough fixes (docs/d6/d6-3-decisions.md §6, the T items): one passing and one failing case per rule.

Synthetic fixtures from schemas/examples/ and the season-check fixtures. Numbers in comments follow the decision table.
"""
import copy
import hashlib
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
sys.path.insert(0, str(Path(__file__).parent))
from checks import contract_check as contracts  # noqa: E402
from checks import ledger as L  # noqa: E402
from checks.episode_check import SCENE_DETAIL_RE  # noqa: E402
from test_season_check import Season, run  # noqa: E402
from test_season_check_d6 import DialogueLayer, put  # noqa: E402


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    text = proc.stdout if proc.stdout.lstrip().startswith("{") else proc.stderr
    return proc.returncode, json.loads(text)


class LayerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.season = Season(self.root, voice=False, dialogue_read=False)
        self.layer = DialogueLayer(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        self.layer.write()
        code, out = run("season-check", self.root, "--episodes", "2-3")
        return out, {f["rule"] for f in out["failures"]}

    def drop(self, prefix):
        for n in (2, 3):
            self.layer.records[n] = {k: v for k, v in self.layer.records[n].items() if not k.startswith(prefix)}
        for path in (self.root / ".drama/checks").glob(f"{prefix}*"):
            path.unlink()


class NoCorpus(LayerCase):  # 1, 2
    def no_corpus(self):
        self.layer.target["corpusManifest"] = None
        self.layer.target["noCorpusReason"] = "新项目，还没有语料"

    def test_without_a_corpus_the_13_char_tier_is_not_evaluable(self):
        self.no_corpus()
        self.drop("dup13")
        out, rules = self.check()
        self.assertEqual(rules, set(), out["failures"])
        self.assertEqual(out["perEpisode"]["3"]["dupTwoTier"]["13"], "not_evaluable（本项目无语料）")
        listed = out["dialogueLayerRules"]["dup-two-tier"]  # re-run N1: the skipped tier shows beside passed
        self.assertEqual((listed["status"], listed["notEvaluatedTiers"], listed["notEvaluatedTiersOn"]), ("passed", ["13"], ["第2集", "第3集"]))

    def test_with_a_corpus_the_13_char_tier_is_still_owed(self):
        out, rules = self.check()
        self.assertNotIn("notEvaluatedTiers", out["dialogueLayerRules"]["dup-two-tier"])
        self.drop("dup13")
        out, rules = self.check()
        self.assertEqual(rules, {"dup-two-tier"})

    def test_the_8_char_tier_is_owed_only_when_the_plan_cites_corpus_samples(self):
        self.no_corpus()
        self.drop("dup8")
        out, rules = self.check()  # the example plan cites corpus positives
        self.assertEqual(rules, {"dup-two-tier"})
        for plan in self.layer.plans.values():
            for scene in plan["scenes"]:
                for topic in scene["topics"]:
                    topic["exemplars"] = {"no_exemplar": "本项目无语料"}
        out, rules = self.check()
        self.assertEqual(rules, set(), out["failures"])

    def test_a_null_corpus_manifest_needs_a_reason(self):
        doc = example("dialogue-target")
        doc["corpusManifest"] = None
        self.assertTrue(any("noCorpusReason" in e for e in contracts.check_contract("dialogue-target", doc)))
        doc["noCorpusReason"] = "新项目，还没有语料"
        self.assertEqual(contracts.check_contract("dialogue-target", doc), [])

    def test_a_null_media_profile_is_allowed(self):  # 17
        doc = example("dialogue-target")
        doc["mediaProfile"] = None
        self.assertEqual(contracts.check_contract("dialogue-target", doc), [])


class AgendaOwnerKnows(unittest.TestCase):  # 3
    def entries(self):
        agenda = {"id": "L-ag-001", "kind": "agenda", "title": "孙老师不愿电梯井挡住南窗", "party": "孙老师", "status": "asserted",
                  "goal": "不让电梯井挡窗", "validFrom": "pre"}
        return {"L-ag-001": agenda}

    def test_the_owner_knows_her_own_agenda_and_others_do_not(self):
        known = L.knows_for_person(self.entries(), "孙老师")["knows"]
        self.assertEqual([k["entryId"] for k in known], ["L-ag-001"])
        self.assertEqual(L.knows_for_person(self.entries(), "周敏")["knows"], [])

    def test_scene_aware_knows_counts_the_agenda_too(self):
        known = L.knows_scene_aware(self.entries(), "孙老师", {"1-3": 0}, "1-3")["knows"]
        self.assertEqual([k["entryId"] for k in known], ["L-ag-001"])

    def test_an_agenda_that_starts_later_is_not_known_yet(self):
        entries = self.entries()
        entries["L-ag-001"]["validFrom"] = "ep5"
        self.assertEqual(L.knows_for_person(entries, "孙老师", at="3")["knows"], [])


class ConsistencyByDraft(LayerCase):  # 6
    def situation(self, n, name, file):
        doc = copy.deepcopy(self.layer.records[n][f"situation-ep-{n:03d}-a.json"])
        doc["checkId"] = name
        doc["target"] = {"kind": "episode_text", "episode": n, "file": file}
        self.layer.records[n][f"{name}.json"] = doc

    def test_checks_of_two_drafts_need_no_consistency_record(self):
        for n in (2, 3):
            self.layer.records[n][f"situation-ep-{n:03d}-a.json"]["target"]["file"] = f"runs/b1/ep-{n:03d}.md"
            self.situation(n, f"DC-{n}-r1", self.season.final(n))
        out, rules = self.check()
        self.assertNotIn("consistency-record", rules)

    def test_two_checks_of_the_same_draft_still_do(self):
        for n in (2, 3):
            self.layer.records[n][f"situation-ep-{n:03d}-a.json"]["target"]["file"] = self.season.final(n)
            self.situation(n, f"DC-{n}-b", self.season.final(n))
        out, rules = self.check()
        self.assertIn("consistency-record", rules)


class RevisionListCast(LayerCase):  # 8
    def fixlist(self, text):
        self.layer.records[3]["revision-list-ep-003.json"] = {"schema": "revision-list/v0-pilot", "target": {"episode": 3},
                                                              "items": [{"id": "RV-1", "problem": "称呼", "action": text}]}

    def test_with_the_cast_only_a_cast_name_opens_a_line(self):
        self.fixlist("照表写：这一来回只承载 I1-f1")
        self.assertNotIn("fixlist-no-lines", self.check()[1])
        self.fixlist("顺序：先叫人再说事")  # not a label word, not a cast member: no line with the cast known
        self.assertNotIn("fixlist-no-lines", self.check()[1])
        self.fixlist("老陈：箱子早送到了。")
        self.assertIn("fixlist-no-lines", self.check()[1])

    def test_without_a_cast_the_heuristic_skips_the_new_labels(self):
        doc = example("revision-list")
        doc["items"][0]["action"] = "照表写：这一来回只承载 I1-f1"
        self.assertEqual(contracts.check_contract("revision-list", doc), [])
        doc["items"][0]["action"] = "刘叔：箱子早送到了。"
        self.assertTrue(contracts.check_contract("revision-list", doc))


class HandoffDecisionRefs(unittest.TestCase):  # re-run N2
    def check(self, refs, with_queue=True):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            doc = example("run-handoff")
            doc["decisionRefs"] = refs
            (base / "h.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            (base / "q.json").write_text(json.dumps(example("decision-queue"), ensure_ascii=False), encoding="utf-8")
            return tool("contract-check", "run-handoff", base / "h.json", *(["--decisions", base / "q.json"] if with_queue else []))

    def test_a_reference_to_a_queued_decision_passes(self):
        known = example("decision-queue")["entries"][0]["id"]
        self.assertEqual(self.check([known])[0], 0)

    def test_an_unknown_decision_fails(self):
        code, out = self.check(["DQ-404"])
        self.assertEqual(code, 2, out)
        self.assertIn("DQ-404", " ".join(out["errors"]))

    def test_without_the_queue_it_is_noted_not_judged(self):
        code, out = self.check(["DQ-404"], with_queue=False)
        self.assertEqual(code, 0, out)
        self.assertIn("decision-refs", " ".join(out["notEvaluated"]))


class BundledLexicon(unittest.TestCase):  # 9
    def pack(self, ident):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            (base / "proj/.drama").mkdir(parents=True)
            task, selection = base / "t.json", base / "s.json"
            task.write_text(json.dumps(example("task"), ensure_ascii=False), encoding="utf-8")
            selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
                {"ref": {"kind": "local_file", "id": ident, "revision": None}, "partition": "project_facts", "required": True,
                 "reason": "禁词表"}]}, ensure_ascii=False), encoding="utf-8")
            return tool("context-pack", base / "proj", "--task", task, "--selection", selection, "--role", "author",
                        "--budget", 200000, "--dry-run")

    def test_the_genre_lexicon_packs_by_id(self):
        code, out = self.pack("lexicon:genre-lexicon@v1")
        self.assertEqual(code, 0, out)

    def test_an_unknown_lexicon_is_an_input_error(self):
        self.assertEqual(self.pack("lexicon:genre-lexicon@v9")[0], 1)


class ReviewLayers(unittest.TestCase):  # 11
    def test_findings_may_name_c5a_or_c5b_and_c5_stays_valid(self):
        for layer in ("C5a", "C5b", "C5"):
            doc = example("review-record")
            doc["findings"][0]["layer"] = layer
            self.assertEqual(contracts.check_contract("review-record", doc), [], layer)
        doc["findings"][0]["layer"] = "C5c"
        self.assertTrue(contracts.check_contract("review-record", doc))


class InterruptedAt(unittest.TestCase):  # 12, and re-run N3: interruptedAt sits on the interrupted exchange
    def run_check(self, by, text="场3-2 镇仓库柜台 中午 内\n老陈：我那箱子，三年前——\n仓管：早退了。\n", legacy=False):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            (base / "ep.md").write_text(text, encoding="utf-8")
            plan = example("dialogue-plan")
            topic = plan["scenes"][0]["topics"][0]
            if legacy:
                topic["interruptedBy"] = {"by": by, "atExchange": "X-T1-01"}
            else:
                topic["exchanges"][0]["interruptedAt"] = "X-T1-01"
                topic["interruptedBy"] = {"by": by} if by else None
            ptmap = {"text": str(base / "ep.md"), "exchangeToLines": {"X-T1-01": [2], "X-T1-02": [3]},
                     "lineToPlan": [{"line": 2, "kind": "dialogue", "exchangeId": "X-T1-01"},
                                    {"line": 3, "kind": "dialogue", "exchangeId": "X-T1-02", "closerOf": "T1-s1"}]}
            for name, doc in (("plan.json", plan), ("map.json", ptmap), ("ep-plan.json", example("episode-plan"))):
                (base / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            code, out = tool("plan-text-consistency", base / "map.json", "--dialogue-plan", base / "plan.json",
                             "--episode-plan", base / "ep-plan.json")
            return out["rules"]["interrupted-by"]

    def test_the_interrupter_speaks_next_and_the_interrupted_need_not_finish(self):
        self.assertEqual(self.run_check("仓管"), {"status": "report", "items": [], "notEvaluable": []})

    def test_someone_else_cutting_in_is_reported(self):
        self.assertTrue(self.run_check("王姨")["items"])

    def test_without_a_named_interrupter_the_interrupted_speaker_must_not_carry_on(self):
        self.assertEqual(self.run_check(None)["items"], [])
        same = "场3-2 镇仓库柜台 中午 内\n老陈：我那箱子，三年前——\n老陈：寄的。\n"
        self.assertTrue(self.run_check(None, text=same)["items"])

    def test_the_older_at_exchange_spelling_is_read(self):
        self.assertEqual(self.run_check("仓管", legacy=True)["notEvaluable"], [])
        self.assertTrue(self.run_check("王姨", legacy=True)["items"])

    def test_the_bundled_example_uses_the_tool_s_command_and_status_words(self):
        doc = example("plan-text-consistency")
        self.assertIn("--dialogue-plan", doc["reproduceCommand"])
        self.assertTrue({r["status"] for r in doc["rules"].values()} <= {"pass", "fail", "report"})


class SealedInside(LayerCase):  # 13
    def first_read(self):
        path = next(p for p in sorted((self.root / ".drama/reviews").glob("*.json"))
                    if json.loads(p.read_text(encoding="utf-8"))["firstReadWithoutAuthorNotes"])
        return path, json.loads(path.read_text(encoding="utf-8"))

    def seal(self, doc):
        body = json.dumps({k: v for k, v in doc.items() if k != "sealedSha256"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()

    def test_a_seal_inside_the_record_counts(self):
        path, doc = self.first_read()
        path.with_suffix(".sha256").unlink()
        doc["sealedSha256"] = self.seal(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        out, rules = self.check()
        self.assertNotIn("first-read-sealed", rules)

    def test_a_wrong_seal_does_not(self):
        path, doc = self.first_read()
        path.with_suffix(".sha256").unlink()
        doc["sealedSha256"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        out, rules = self.check()
        self.assertIn("first-read-sealed", rules)

    def test_an_outline_review_is_not_a_first_read_of_the_text(self):
        review = example("review-record")
        review.update(reviewId="outline-3", firstReadWithoutAuthorNotes=True, findings=[], preserved=[],
                      target={"kind": "local_file", "id": "planning/episodes/episode-plan-003.json", "revision": None},
                      readingScope=[{"kind": "local_file", "id": ".drama/checks/RC-ep003-moves.json", "revision": None}])
        review.pop("additionalTargets", None)
        put(self.root, ".drama/reviews/outline-3.json", review)
        out, _ = self.check()
        self.assertNotIn("outline-3", out["perEpisode"]["3"]["firstRead"])
        self.assertFalse([w for w in out["warnings"] if w["rule"] == "first-read-sealed"])


class SituationCheckShape(unittest.TestCase):  # 14
    def record(self, answers):
        return {"schemaVersion": "drama-studio/answers/v0", "checkId": "DC-1", "target": {"kind": "topic", "ids": ["T1"]},
                "questionsVersion": "dialogue-check-questions@v1", "answers": answers, "outcome": "pass"}

    def test_both_anchors_and_an_unquoted_n_a(self):
        answers = [{"q": 1, "landsOn": "T1", "quoteRef": {"line": 3, "quote": "早退了"}, "holds": "holds", "reason": "对"},
                   {"q": 15, "holds": "n/a", "reason": "本项目无语料样本"}]
        self.assertEqual(contracts.check_contract("answers", self.record(answers)), [])

    def test_a_judged_answer_still_quotes_its_line(self):
        answers = [{"q": 1, "landsOn": "T1", "holds": "holds", "reason": "对"}]
        self.assertTrue(any("quoteRef" in e for e in contracts.check_contract("answers", self.record(answers))))

    def test_defect_kinds_outside_the_question_set_s_words_are_reported(self):
        with tempfile.TemporaryDirectory() as base:
            answers = [{"q": 1, "quoteRef": {"line": 3, "quote": "早退了"}, "holds": "notHolds", "reason": "情绪没进句子",
                        "defectKind": ["emotion_not_in_line_shape", "made_up_kind"]}]
            doc = dict(self.record(answers), outcome="fail", askedSubset=[1], promptVersion={"id": "x", "version": "v1"})
            path = Path(base) / "dc.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            code, out = tool("check-answers", path)
            reports = [r for r in out["records"][0]["reports"] if r["rule"] == "defect-kind-vocabulary"]
            self.assertEqual(len(reports), 1)
            self.assertIn("made_up_kind", reports[0]["detail"])
            self.assertNotIn("emotion_not_in_line_shape']", reports[0]["detail"])


class RetellSource(unittest.TestCase):  # 15
    def test_events_may_say_which_line_and_what_kind(self):
        doc = example("retell-record")
        doc["events"][0].update(sourceLine={"line": 3, "quote": "孙老师（六十多岁，退休语文老师）"}, sourceKind="heading")
        self.assertEqual(contracts.check_contract("retell-record", doc), [])
        doc["events"][0]["sourceKind"] = "guess"
        self.assertTrue(contracts.check_contract("retell-record", doc))


class PlanTextMapKinds(unittest.TestCase):  # 18
    def test_line_kinds_are_a_closed_list(self):
        doc = example("plan-text-map")
        for kind in ("title", "scene", "cast", "action", "dialogue", "other"):
            doc["lineToPlan"][0]["kind"] = kind
            self.assertEqual(contracts.check_contract("plan-text-map", doc), [], kind)
        doc["lineToPlan"][0]["kind"] = "header"
        self.assertTrue(contracts.check_contract("plan-text-map", doc))


class HeadingTimeWords(unittest.TestCase):  # 19
    def test_day_and_order_words_around_a_time_are_read(self):
        for heading, place in (("一至六楼各户门口 次日晚 内", "一至六楼各户门口"), ("101门口 次日晚稍后 内", "101门口"),
                               ("楼道 当天傍晚 外", "楼道")):
            match = SCENE_DETAIL_RE.fullmatch(heading)
            self.assertTrue(match, heading)
            self.assertEqual(match.group(1), place)

    def test_unknown_time_tokens_still_do_not_become_a_place(self):
        self.assertIsNone(SCENE_DETAIL_RE.fullmatch("楼道 三更半夜 内"))


class CapacityTextTarget(unittest.TestCase):  # 20: --target-sec > the episode plan's capacity.targetSec > media profile
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.text = self.base / "ep.md"
        self.text.write_text("场1-1 楼道 日 内\n周敏：妈，我回来了。\n", encoding="utf-8")
        plan = example("episode-plan")
        plan["capacity"]["targetSec"] = 120
        self.plan = self.base / "plan.json"
        self.plan.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def target(self, *args):
        code, out = tool("capacity", "text", self.text, *args)
        self.assertEqual(code, 0, out)
        return out["targetSec"], out["targetSecSource"]

    def test_the_order_of_the_sources(self):
        self.assertEqual(self.target("--target-sec", "90", "--episode-plan", self.plan), (90.0, "argument"))
        self.assertEqual(self.target("--episode-plan", self.plan), (120, "episode_plan"))
        self.assertEqual(self.target(), (58.0, "default_media_profile"))

    def test_a_plan_without_a_target_falls_back_to_the_profile(self):
        plan = json.loads(self.plan.read_text(encoding="utf-8"))
        del plan["capacity"]["targetSec"]
        self.plan.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        media = self.base / "media.json"
        media.write_text(json.dumps(example("media-profile"), ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.target("--episode-plan", self.plan, "--media", media), (120, "media_profile"))


if __name__ == "__main__":
    unittest.main()
