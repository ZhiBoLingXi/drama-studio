"""D6-2 walkthrough fixes (docs/d6/d6-2-decisions.md §5, the T items): one passing and one failing case per rule.

Synthetic fixtures from schemas/examples/ only. Numbers in test names follow the decision table.
"""
import copy
import importlib.util
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
from checks import contract_check as contracts  # noqa: E402
from checks import function_map  # noqa: E402


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args, cwd=None):
    run = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    text = run.stdout if run.stdout.lstrip().startswith("{") else run.stderr
    return run.returncode, (json.loads(text) if text.lstrip().startswith("{") else run.stdout), run.stderr


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, doc):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path


class FactCheckComparisonCards(unittest.TestCase):  # 1
    def snapshot(self, role, usage):
        doc = example("context-snapshot")
        doc["createdFor"]["role"] = role
        doc["items"][2]["usage"] = usage
        return contracts.check_contract("context-snapshot", doc)

    def test_fact_check_takes_comparison_only_cards(self):
        self.assertEqual(self.snapshot("fact_check", "comparison_only"), [])

    def test_fact_check_still_refuses_evaluation_only_and_authors_refuse_comparison_only(self):
        self.assertTrue(any("evaluation_only" in e for e in self.snapshot("fact_check", "evaluation_only")))
        self.assertTrue(any("comparison_only" in e for e in self.snapshot("author", "comparison_only")))


class CapacityDefaults(Temp):  # 2
    def test_no_media_and_no_corpus_use_the_bundled_default(self):
        code, out, _ = tool("capacity", "episode", EXAMPLES / "episode-plan.json")
        self.assertEqual(code, 0, out)
        self.assertEqual((out["basis"]["status"], out["basis"]["defaults"]), ("default_unmeasured", ["media", "exchangeMedianSec"]))
        self.assertEqual(out["basis"]["exchangeMedianSource"], "default_unmeasured")

    def test_given_values_say_given(self):
        media = self.write("media.json", example("media-profile"))
        code, out, _ = tool("capacity", "episode", EXAMPLES / "episode-plan.json", "--media", media, "--exchange-median-sec", 9)
        self.assertEqual((code, out["basis"]["status"], out["basis"]["defaults"]), (0, "given", []))

    def test_anime_without_a_measured_median_is_an_input_error(self):
        # D6-4 changed this on purpose: the bundled profile now carries a measured anime median (corpus defaults, n=31),
        # so anime no longer errors; a format the profile does not hold still does
        code, out, _ = tool("capacity", "episode", EXAMPLES / "episode-plan.json", "--format", "anime")
        self.assertEqual((code, out["basis"]["exchangeMedianSec"], out["basis"]["exchangeSampleN"]), (0, 12.0, 31))
        code, out, _ = tool("capacity", "episode", EXAMPLES / "episode-plan.json", "--format", "radio")
        self.assertEqual(code, 1, out)

    def test_the_default_profile_passes_contract_check(self):
        code, out, _ = tool("contract-check", "media-profile", ROOT / "skills/drama-studio/schemas/data/default-media-profile.json")
        self.assertEqual(code, 0, out)


class BlankPeriodView(Temp):  # 3, 24
    def test_a_function_map_gives_the_c3a_view_by_thread(self):
        doc = example("function-map")
        code, out, _ = tool("ledger", "view", self.write("fm.json", doc), "--blank-period")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["source"], "function_map")
        self.assertIn("D-box-k01", out["markdown"])
        self.assertNotIn("D-box-p01", out["markdown"])  # procedure deps go to retrieval, not to the blank-period view

    def test_a_file_with_neither_entries_nor_threads_is_an_input_error(self):
        code, out, _ = tool("ledger", "view", self.write("x.json", {"foo": 1}), "--blank-period")
        self.assertEqual(code, 1, out)

    def test_state_entries_are_grouped_under_their_state_of(self):
        ledger = example("ledger-entry")
        code, out, _ = tool("ledger", "view", self.write("l.json", ledger), "--blank-period")
        state = next(e for e in ledger["entries"] if e.get("subtype") == "state")
        self.assertIn(state["stateOf"], out["people"])
        self.assertNotIn("（未写 who）", out["people"])


class PromptVersion(Temp):  # 4
    def test_the_bundled_example_passes_check_answers(self):
        code, out, _ = tool("check-answers", EXAMPLES / "answers.json")
        self.assertEqual((code, out["records"][0]["errors"]), (0, []))

    def test_a_record_without_prompt_version_fails(self):
        doc = example("answers")
        del doc["promptVersion"]
        code, out, _ = tool("check-answers", self.write("a.json", doc))
        self.assertEqual(code, 2)
        self.assertIn("promptVersion", " ".join(out["records"][0]["errors"]))


class LedgerSchemaBasic(Temp):  # 5
    def check(self, mutate):
        ledger = example("ledger-entry")
        mutate({e["id"]: e for e in ledger["entries"]})
        code, out, _ = tool("ledger", "check", self.write("l.json", ledger))
        return out["rules"]["schema-basic"]

    def test_timeline_without_did_not_key_and_why_not_applicable_without_why_pass(self):
        def mutate(by_id):
            entry = by_id["L-tl-001"]
            entry.pop("didNot", None)
            entry.pop("why", None)
            entry["whyNotApplicable"] = "自然发生，谈不上为什么"
        self.assertEqual(self.check(mutate)["status"], "pass")

    def test_timeline_without_why_or_a_reason_still_fails(self):
        def mutate(by_id):
            by_id["L-tl-001"].pop("why", None)
            by_id["L-tl-001"].pop("whyNotApplicable", None)
        self.assertEqual(self.check(mutate)["status"], "fail")

    def test_the_schema_required_fields_are_the_required_fields(self):
        rule = self.check(lambda by_id: by_id["L-tl-001"].pop("history"))
        self.assertEqual(rule["status"], "fail")
        self.assertIn("缺必填字段 history", json.dumps(rule["items"], ensure_ascii=False))
        required = json.loads((ROOT / "skills/drama-studio/schemas/ledger-entry.schema.json").read_text(encoding="utf-8"))
        self.assertIn("history", required["$defs"]["entry"]["required"])

    def test_writer_revised_origin_is_valid_as_in_the_schema(self):
        self.assertEqual(self.check(lambda by_id: by_id["L-tl-001"].update(origin="writer_revised"))["status"], "pass")

    def test_the_bundled_example_passes_both_checks(self):
        self.assertEqual(self.check(lambda by_id: None)["status"], "pass")
        self.assertEqual(contracts.check_contract("ledger-entry", example("ledger-entry")), [])

    def test_the_state_subtype_still_needs_its_span(self):
        def mutate(by_id):
            state = next(e for e in by_id.values() if e.get("subtype") == "state")
            state.pop("validTo", None)
        rule = self.check(mutate)
        self.assertEqual(rule["status"], "fail")
        self.assertIn("validTo", json.dumps(rule["items"], ensure_ascii=False))
        self.assertEqual(self.check(lambda by_id: None)["status"], "pass")  # no knownTo on the example's state: fine


class AnswerRecordsRules(Temp):  # 7, 13, 19, 20
    def record(self, check_id, answers, outcome="fail", **extra):
        doc = example("answers")
        doc.update(checkId=check_id, answers=answers, outcome=outcome, askedSubset=sorted({a["q"] for a in answers}), **extra)
        return doc

    def gap(self, **extra):
        return {"q": 5, "landsOn": "F-box-1.A.s2", "holds": "notHolds", "reason": "说不通", "defectKey": "box-gap",
                "defectKind": ["internal_conflict"], **extra}

    def load_bearing(self, ref):
        return self.gap(loadBearing=True, loadBearingBasis="function_sentence_step", loadBearingWhy="功能句落空",
                        disposition={"to": "confirmed_gone", "ref": ref, "backfilledBy": "orchestrator"})

    def test_records_accept_a_folder(self):  # 7
        self.write("checks/RC-recheck.json", self.record("RC-recheck", [dict(self.gap(), holds="holds", reason="改后成立")], "pass"))
        original = self.write("RC-orig.json", self.record("RC-orig", [self.load_bearing("RC-recheck")]))
        code, out, _ = tool("check-answers", original, "--records", self.base / "checks")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["records"][0]["backfilledDispositions"][0]["by"], "orchestrator")

    def test_backfill_cannot_cite_the_record_itself(self):  # 13
        original = self.write("RC-orig.json", self.record("RC-orig", [self.load_bearing("RC-orig")]))
        code, out, _ = tool("check-answers", original, "--records", original)
        self.assertEqual(code, 2)
        self.assertIn("引用的是本记录", " ".join(out["records"][0]["errors"]))

    def test_backfill_cannot_cite_a_recheck_that_still_says_not_holds(self):  # 13
        self.write("checks/RC-recheck.json", self.record("RC-recheck", [self.gap()]))
        original = self.write("RC-orig.json", self.record("RC-orig", [self.load_bearing("RC-recheck")]))
        code, out, _ = tool("check-answers", original, "--records", self.base / "checks")
        self.assertEqual(code, 2)
        self.assertIn("仍判 notHolds", " ".join(out["records"][0]["errors"]))

    def test_only_light_gaps_allow_pass_with_unverified(self):  # 19
        light = self.record("RC-light", [self.gap(loadBearing=False)], "pass_with_unverified")
        self.assertEqual(contracts.check_contract("answers", light), [])
        code, out, _ = tool("check-answers", self.write("light.json", light))
        self.assertEqual(code, 0, out)
        heavy = self.record("RC-heavy", [self.load_bearing("RC-x")], "pass_with_unverified")
        self.assertTrue(any("outcome" in e for e in contracts.check_contract("answers", heavy)))
        code, out, _ = tool("check-answers", self.write("heavy.json", heavy))
        self.assertIn("outcome", " ".join(out["records"][0]["errors"]))

    def test_light_gaps_may_still_say_fail(self):  # 19
        self.assertEqual(contracts.check_contract("answers", self.record("RC-light", [self.gap(loadBearing=False)], "fail")), [])

    def test_a_record_over_several_moves_names_each_answer_subject(self):  # 20
        target = {"kind": "move", "id": "ep001.moves", "ids": ["M-1", "M-2"]}
        doc = self.record("RC-moves", [dict(self.gap(loadBearing=False), q=5)], "fail", target=target)
        self.assertTrue(any("names its subject" in e for e in contracts.check_contract("answers", doc)))
        code, out, _ = tool("check-answers", self.write("m.json", doc))
        self.assertIn("names its subject", " ".join(out["records"][0]["errors"]))
        doc["answers"][0]["subject"] = "M-3"
        self.assertTrue(any("not one of target.ids" in e for e in contracts.check_contract("answers", doc)))
        doc["answers"][0]["subject"] = "M-2"
        self.assertEqual(contracts.check_contract("answers", doc), [])

    def test_a_single_subject_record_needs_no_subject(self):  # 20
        self.assertEqual(contracts.check_contract("answers", example("answers")), [])


class ReRunSmalls(AnswerRecordsRules):  # re-run N2, N3, N6
    def test_a_backfilled_confirmed_gone_names_who_filled_it_in(self):  # N2
        self.write("checks/RC-recheck.json", self.record("RC-recheck", [dict(self.gap(), holds="holds", reason="改后成立")], "pass"))
        answer = self.load_bearing("RC-recheck")
        del answer["disposition"]["backfilledBy"]
        original = self.write("RC-orig.json", self.record("RC-orig", [answer]))
        code, out, _ = tool("check-answers", original, "--records", self.base / "checks")
        self.assertEqual(code, 2, out)
        self.assertIn("backfilledBy", " ".join(out["records"][0]["errors"]))
        code, out, _ = tool("check-answers", original)  # without --records the reference is not checked, the field still is
        self.assertIn("backfilledBy", " ".join(out["records"][0]["errors"]))

    def test_other_destinations_need_no_backfilled_by(self):  # N2
        answer = self.gap(loadBearing=True, loadBearingBasis="function_sentence_step", loadBearingWhy="功能句落空",
                          disposition={"to": "decision", "ref": "D-001"})
        code, out, _ = tool("check-answers", self.write("d.json", self.record("RC-d", [answer])))
        self.assertEqual(code, 0, out)

    def errata_check(self, **extra):
        doc = example("answers")
        doc.update(checkId="RC-errata-1", target={"kind": "errata_check", "id": "planning/function-map.json"}, answers=[],
                   outcome="pass", askedSubset=[4], errataConfirmed=[{"ref": "RC-box-1A#0", "fixed": True}])
        doc.update(extra)
        return doc

    def test_an_errata_recheck_may_answer_no_question(self):  # N3
        doc = self.errata_check()
        self.assertEqual(contracts.check_contract("answers", doc), [])
        code, out, _ = tool("check-answers", self.write("e.json", doc))
        self.assertEqual(code, 0, out)

    def test_only_an_errata_recheck_may_be_empty(self):  # N3
        doc = self.errata_check(errataConfirmed=[])
        self.assertTrue(any("answers: empty" in e for e in contracts.check_contract("answers", doc)))
        code, out, _ = tool("check-answers", self.write("e.json", doc))
        self.assertIn("errataConfirmed", " ".join(out["records"][0]["errors"]))
        empty = example("answers")
        empty["answers"] = []
        self.assertTrue(any("answers: empty" in e for e in contracts.check_contract("answers", empty)))

    def test_a_records_folder_reads_answer_records_only(self):  # N6
        self.write("checks/RC-recheck.json", self.record("RC-recheck", [dict(self.gap(), holds="holds", reason="改后成立")], "pass"))
        self.write("checks/check-answers.out.json", "")  # an output redirected into the folder, emptied by the shell
        self.write("checks/ledger-check.json", {"ok": True, "passed": True})
        original = self.write("RC-orig.json", self.record("RC-orig", [self.load_bearing("RC-recheck")]))
        code, out, _ = tool("check-answers", original, "--records", self.base / "checks")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(Path(item["file"]).name for item in out["recordsSkipped"]), ["check-answers.out.json", "ledger-check.json"])

    def test_a_file_named_directly_is_still_read_strictly(self):  # N6
        broken = self.write("broken.json", "")
        original = self.write("RC-orig.json", self.record("RC-orig", [self.load_bearing("RC-x")]))
        code, out, _ = tool("check-answers", original, "--records", broken)
        self.assertEqual(code, 1, out)


class RunWithoutSnapshot(Temp):  # 8
    def handoff(self, workstation, snapshot, **extra):
        doc = example("run-handoff")
        doc.update(workstation=workstation, contextSnapshotId=snapshot, changeProposals=[], **extra)
        doc.pop("additionalSnapshotIds", None)
        return contracts.check_contract("run-handoff", doc)

    def test_c1_and_c2_may_run_without_a_package_when_they_say_why(self):
        for station in ("C1", "C2"):
            self.assertEqual(self.handoff(station, None, noSnapshotReason="C1 不装包：只读用户简报"), [], station)

    def test_other_workstations_and_missing_reasons_fail(self):
        self.assertTrue(any("only C1/C2" in e for e in self.handoff("C4", None, noSnapshotReason="懒得装")))
        self.assertTrue(any("says why" in e for e in self.handoff("C2", None)))
        self.assertTrue(any("only a run whose contextSnapshotId is null" in e
                            for e in self.handoff("C2", "ctx-1", noSnapshotReason="多写了")))

    def test_status_shows_a_run_without_a_snapshot(self):
        project = self.base / "p"
        tool("init-project", project, "--title", "测")
        doc = example("run-handoff")
        doc.update(runId="run-c1", workstation="C1", contextSnapshotId=None, noSnapshotReason="C1 不装包", changeProposals=[], unfinished=[])
        doc.pop("additionalSnapshotIds", None)
        (project / ".drama/runs").mkdir()
        (project / ".drama/runs/run-c1.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(TOOL), "status", str(project)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("快照 无（C1 不装包）", run.stdout)


class PlanEventsExport(Temp):  # 9
    def setUp(self):
        super().setUp()
        self.project = self.base / "proj"
        (self.project / ".drama").mkdir(parents=True)
        plan = example("episode-plan")
        self.write("proj/planning/episodes/episode-plan-003.json", plan)

    def pack(self, name):
        task = example("task")
        selection = {"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": name, "revision": None}, "partition": "project_facts", "required": True, "reason": "测"}]}
        return tool("context-pack", self.project, "--task", self.write("t.json", task), "--selection", self.write("s.json", selection),
                    "--role", "cold_reader", "--budget", 100000, "--dry-run")

    def test_the_export_drops_design_fields(self):
        out_path = self.project / ".drama/checks/events-ep003.json"
        out_path.parent.mkdir(parents=True)
        code, out, _ = tool("plan-events", self.project / "planning/episodes/episode-plan-003.json", "--out", out_path)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["dropped"], ["beats[].picture", "beats[].saysFact"])
        export = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertNotIn("saysFact", json.dumps(export))
        self.assertNotIn("infoLedger", export)
        self.assertEqual(contracts.check_contract("episode-plan-events", export), [])

    def test_the_export_never_overwrites_different_bytes(self):
        out_path = self.write("proj/.drama/checks/events-ep003.json", "{}")
        code, out, _ = tool("plan-events", self.project / "planning/episodes/episode-plan-003.json", "--out", out_path)
        self.assertEqual(code, 1, out)

    def test_cold_reader_takes_the_export_and_refuses_the_whole_plan(self):
        tool("plan-events", self.project / "planning/episodes/episode-plan-003.json", "--out", self.project / ".drama/events-ep003.json")
        code, out, _ = self.pack(".drama/events-ep003.json")
        self.assertEqual(code, 0, out)
        code, out, _ = self.pack("planning/episodes/episode-plan-003.json")
        self.assertEqual(code, 2, out)
        self.assertIn("plan-events", " ".join(out["errors"]))
        plan = example("episode-plan")
        del plan["schemaVersion"]  # an unmarked plan is still a plan
        self.write("proj/runs/plan-003.json", plan)
        code, out, _ = self.pack("runs/plan-003.json")
        self.assertEqual(code, 2, out)


class TopicsSearchable(Temp):  # 15
    def topics(self, deps):
        doc = example("function-map")
        doc["threads"][0]["functions"][0]["candidates"][0]["ledgerDeps"] = deps
        code, out, _ = tool("function-map", "topics", self.write("fm.json", doc))
        return out

    def test_money_and_object_unstated_deps_are_asked_unless_marked_not_real_world(self):
        dep = {"depId": "D-1", "kind": "object", "claim": "无人领取的件放多久", "assertion": "required_unstated", "entryId": None}
        self.assertIn("无人领取的件放多久", json.dumps(self.topics([dep])["topics"], ensure_ascii=False))
        out = self.topics([dict(dep, realWorldRule=False)])
        self.assertNotIn("无人领取的件放多久", json.dumps(out["topics"], ensure_ascii=False))
        self.assertEqual(out["notSearchable"].get("object"), 1)

    def test_agenda_and_knowledge_deps_yield_no_topic(self):
        deps = [{"depId": "D-a", "kind": "agenda", "claim": "王姨想瞒住", "assertion": "required_unstated", "entryId": None},
                {"depId": "D-k", "kind": "knowledge", "claim": "王姨知道", "assertion": "required_unstated", "entryId": None}]
        out = self.topics(deps)
        self.assertNotIn("王姨", json.dumps(out["topics"], ensure_ascii=False))


class ErrataCleared(unittest.TestCase):  # 18
    def records(self, confirmed_by=None, fixed=True):
        first = {"checkId": "RC-1", "mapErrata": [{"where": "F-1.A", "what": "转述错了"}]}
        records = {"RC-1": (first, "RC-1.json")}
        if confirmed_by:
            records[confirmed_by] = ({"checkId": confirmed_by, "errataConfirmed": [{"ref": "RC-1#0", "fixed": fixed}]}, "x.json")
        return records

    def test_an_erratum_confirmed_by_another_record_is_cleared(self):
        self.assertEqual(function_map.errata_unconfirmed(self.records("RC-2")), ([], 1, []))

    def test_unconfirmed_self_confirmed_or_not_fixed_errata_stay(self):
        for records in (self.records(), self.records("RC-2", fixed=False)):
            unconfirmed, total, skipped = function_map.errata_unconfirmed(records)
            self.assertEqual((len(unconfirmed), total, skipped), (1, 1, []))
        own = self.records()
        own["RC-1"][0]["errataConfirmed"] = [{"ref": "RC-1#0", "fixed": True}]
        self.assertEqual(len(function_map.errata_unconfirmed(own)[0]), 1)

    def test_a_superseded_record_is_skipped_not_asked(self):
        self.assertEqual(function_map.errata_unconfirmed(self.records(), {"RC-1": "RC-1b"}), ([], 0, ["RC-1"]))
        marked = self.records()
        marked["RC-1"][0]["supersededBy"] = "RC-1b"
        self.assertEqual(function_map.errata_unconfirmed(marked), ([], 0, ["RC-1"]))

    def test_a_current_record_is_still_asked_when_another_is_superseded(self):
        records = self.records()
        records["RC-0"] = ({"checkId": "RC-0", "mapErrata": [{"what": "旧"}]}, "RC-0.json")
        unconfirmed, total, skipped = function_map.errata_unconfirmed(records, {"RC-0": "RC-1"})
        self.assertEqual(([ref for ref, _ in unconfirmed], total, skipped), (["RC-1#0"], 1, ["RC-0"]))

    def test_function_map_check_v1_reports_them(self):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            (base / "rc").mkdir()
            (base / "rc/RC-1.json").write_text(json.dumps(self.records()["RC-1"][0], ensure_ascii=False), encoding="utf-8")
            (base / "fm.json").write_text(json.dumps(example("function-map"), ensure_ascii=False), encoding="utf-8")
            code, out, _ = tool("function-map", "check", base / "fm.json", "--stage", "v1", "--rc-dir", base / "rc")
            self.assertEqual((out["counts"]["mapErrataUnconfirmed"], out["counts"]["skippedSuperseded"]), (1, []))
            self.assertTrue(any("RC-1#0" in e for e in out["errors"]))
            later = {"checkId": "RC-2", "supersedes": "RC-1", "answers": []}
            (base / "rc/RC-2.json").write_text(json.dumps(later, ensure_ascii=False), encoding="utf-8")
            code, out, _ = tool("function-map", "check", base / "fm.json", "--stage", "v1", "--rc-dir", base / "rc")
            self.assertEqual((out["counts"]["mapErrataUnconfirmed"], out["counts"]["skippedSuperseded"]), (0, ["RC-1"]))
            self.assertFalse(any("RC-1#0" in e for e in out["errors"]))


class BundledQuestionSet(Temp):  # 22
    def pack(self, ident):
        project = self.base / "proj"
        (project / ".drama").mkdir(parents=True, exist_ok=True)
        selection = {"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": ident, "revision": None}, "partition": "project_facts", "required": True, "reason": "问题单"}]}
        return tool("context-pack", project, "--task", self.write("t.json", example("task")), "--selection", self.write("s.json", selection),
                    "--role", "fact_check", "--budget", 200000, "--dry-run")

    def test_a_bundled_question_set_packs_by_id(self):
        code, out, _ = self.pack("question-set:reality-check-questions@v1")
        self.assertEqual(code, 0, out)
        self.assertIn("question-set:reality-check-questions@v1", " ".join(i["ref"] for i in out["items"]))

    def test_an_unknown_question_set_is_an_input_error(self):
        code, out, _ = self.pack("question-set:nope@v9")
        self.assertEqual(code, 1, out)


class LayoutAndReading(Temp):  # 23, 24, 25
    def test_init_project_makes_runs_and_knowledge_and_leaves_drama_alone(self):
        project = self.base / "p"
        tool("init-project", project, "--title", "测")
        self.assertTrue((project / "runs").is_dir() and (project / "knowledge").is_dir())
        self.assertEqual(sorted(p.name for p in (project / ".drama").iterdir()), ["project.json"])

    def test_status_does_not_call_a_handed_over_run_unfinished(self):
        project = self.base / "p"
        tool("init-project", project, "--title", "测")
        (project / ".drama/runs").mkdir()
        for run_id, state, minute in (("run-done", "finished", "00"), ("run-open", "running", "01"), ("run-latest", "finished", "02")):
            doc = example("run-handoff")
            doc.update(runId=run_id, contextSnapshotId=None, workstation="C1", noSnapshotReason="不装包", changeProposals=[],
                       status={"run": state, "goal": "partially_met"}, finishedAt=f"2026-10-15T10:{minute}:00+08:00")
            doc.pop("additionalSnapshotIds", None)
            (project / f".drama/runs/{run_id}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        code, out, _ = tool("status", project, "--json")
        self.assertEqual((out["runs"]["notFinished"], out["runs"]["finishedWithUnfinished"]), (["run-open"], ["run-latest", "run-done"]))
        text = subprocess.run([sys.executable, "-B", str(TOOL), "status", str(project)], capture_output=True, text=True).stdout
        self.assertIn("- 已结束、留有未完成项：run-done", text)
        self.assertIn("- 未结束：run-open", text)

    def retell(self, **extra):
        doc = example("retell-record")
        doc["target"] = {"kind": "episode_plan_events", "episode": 3, "file": ".drama/checks/events-ep003.json"}
        doc.update(extra)
        return self.write("retell.json", doc)

    def test_retell_reading_scope_may_name_the_one_file_read(self):
        code, out, _ = tool("retell-check", self.retell(readingScope=[".drama/checks/events-ep003.json"]), "--plan", EXAMPLES / "episode-plan.json")
        self.assertFalse([n for n in out["notes"] if "readingScope" in n])
        code, out, _ = tool("retell-check", self.retell(readingScope=["a.json", "b.json"]), "--plan", EXAMPLES / "episode-plan.json")
        self.assertTrue([n for n in out["notes"] if "readingScope" in n])
        code, out, _ = tool("retell-check", self.retell(readingScope=["episode_text"]), "--plan", EXAMPLES / "episode-plan.json")
        self.assertTrue([n for n in out["notes"] if "readingScope" in n])

    def test_a_paraphrased_closing_beat_counts_as_retold(self):
        plan = example("episode-plan")
        beat = plan["exit"]["closingEvent"]["beatRef"]
        for scene in plan["events"]["scenes"]:
            for b in scene["beats"]:
                if b["beatId"] == beat:
                    b["text"] = "关上门；门关上前，周敏看见她身后南窗台上一盆茉莉"
        plan_path = self.write("plan.json", plan)
        stops = "孙老师说完后关上门，门缝合上前周敏瞥见她南窗台上的一盆茉莉"
        code, out, _ = tool("retell-check", self.retell(stopsAt=stops), "--plan", plan_path)
        self.assertEqual(out["closingEvent"]["status"], "retold", out["closingEvent"])
        code, out, _ = tool("retell-check", self.retell(stopsAt="周敏回家做饭"), "--plan", plan_path)
        self.assertEqual(out["closingEvent"]["status"], "partial")


class OutlineLayerRulesListed(unittest.TestCase):  # 25
    def test_listed_only_in_the_outline_layer(self):
        sys.path.insert(0, str(Path(__file__).parent))
        from test_season_check import Outlines, Season, run
        from test_season_check_d6 import OutlineLayer
        with tempfile.TemporaryDirectory() as base:
            root = Path(base) / "proj"
            Outlines(Season(root))
            code, legacy = run("season-check", root, "--outline", "4-5")
            self.assertNotIn("outlineLayerRules", legacy)
            layer = OutlineLayer(root)
            layer.write()
            code, out = run("season-check", root, "--outline", "4-5")
            listed = out["outlineLayerRules"]
            self.assertEqual(sorted(listed), sorted(("outline-season-assigned", "outline-ledger-delta", "outline-capacity",
                                                     "outline-reality-refs", "outline-retell", "outline-decision-default",
                                                     "outline-patch-cap")))
            self.assertTrue(all(rule["status"] == "passed" for rule in listed.values()), listed)
            layer.plans[5]["capacity"]["status"] = "exceeds"
            layer.write()
            code, out = run("season-check", root, "--outline", "4-5")
            self.assertEqual(out["outlineLayerRules"]["outline-capacity"]["status"], "failed")
            self.assertEqual(out["outlineLayerRules"]["outline-retell"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
