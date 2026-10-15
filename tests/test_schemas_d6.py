"""D6-1 contracts: one passing and one failing case per script-enforced (S) rule, on synthetic examples."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
SCHEMAS = ROOT / "skills/drama-studio/schemas"
spec = importlib.util.spec_from_file_location("contract_check", ROOT / "skills/drama-studio/scripts/checks/contract_check.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)

D6 = ["function-map", "ledger-entry", "ledger-delta", "question-set", "answers", "season-plan", "episode-plan",
      "decision-queue", "media-profile", "dialogue-exchange", "corpus-manifest", "contrast-pair", "dialogue-plan",
      "dialogue-target", "writer-note", "retell-record", "plan-text-consistency", "defect-register"]


def example(name):
    return json.loads((SCHEMAS / "examples" / f"{name}.json").read_text(encoding="utf-8"))


class Case(unittest.TestCase):
    def ok(self, name, doc, context=None):
        self.assertEqual(contracts.check_contract(name, doc, context), [])

    def bad(self, name, doc, fragment, context=None):
        errors = contracts.check_contract(name, doc, context)
        self.assertTrue(any(fragment in error for error in errors), errors)


class SchemaFilesTests(Case):
    def test_every_d6_object_has_a_schema_and_a_passing_example(self):
        for name in D6:
            with self.subTest(name=name):
                self.assertIn(name, contracts.schema_names())
                self.ok(name, example(name))

    def test_d6_schemas_carry_no_quota_or_band_properties(self):
        for name in ("media-profile", "dialogue-plan", "dialogue-target", "plan-text-consistency", "season-plan", "episode-plan"):
            text = (SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8")
            for word in ('"within"', '"outside"', '"estimates"', '"acceptedBand"', '"hardRules"', '"turnsPerMinute"'):
                self.assertNotIn(word, text, name)

    def test_bundled_question_sets_pass_and_mark_informational_questions(self):
        sets = contracts.question_sets()
        self.assertEqual(sorted(sets), ["dialogue-check-questions@v1", "reality-check-questions@v1"])
        for key, doc in sets.items():
            self.ok("question-set", doc)
        reality = {q["q"]: q["answerKind"] for q in sets["reality-check-questions@v1"]["questions"]}
        self.assertEqual(sorted(q for q, kind in reality.items() if kind == "informational"), [14, 15])
        self.assertEqual(len(reality), 16)
        self.assertEqual(len(sets["dialogue-check-questions@v1"]["questions"]), 17)

    def test_blocklist_names_its_sources_and_both_categories(self):
        data = contracts.load_data("constraint-blocklist")
        self.assertEqual([c["id"] for c in data["categories"]], ["structure_freeze", "numeric_dialogue"])
        for category in data["categories"]:
            self.assertTrue(category["source"].strip())

    def test_checks_run_with_the_network_cut(self):
        import socket
        from unittest import mock
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network used")):
            for name in contracts.schema_names():
                contracts.check_contract_detailed(name, example(name))

    def test_contract_module_uses_only_the_standard_library(self):
        import ast
        source = (ROOT / "skills/drama-studio/scripts/checks/contract_check.py").read_text(encoding="utf-8")
        modules = {alias.name.split(".")[0] for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names}
        modules |= {node.module.split(".")[0] for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
        self.assertLessEqual(modules, {"__future__", "datetime", "json", "pathlib", "re"})


class FunctionMapTests(Case):
    def fn(self, doc):
        return doc["threads"][0]["functions"][0]

    def test_dropped_function_needs_cost(self):
        doc = example("function-map")
        fn = self.fn(doc)
        fn["status"], fn["candidates"][0]["status"] = "dropped", "rejected"
        fn["candidates"][0]["rejectedBecause"] = ["主创删线"]
        self.bad("function-map", doc, "droppedCost")
        fn["droppedCost"] = "F-box-1 落空；第 3、4 集受影响"
        self.ok("function-map", doc)

    def test_selected_candidate_cannot_lose_functions(self):
        doc = example("function-map")
        self.fn(doc)["candidates"][0]["losesFunctions"] = [{"functionId": "F-box-2", "half": "感"}]
        self.bad("function-map", doc, "cannot select it")

    def test_rejected_candidate_needs_reason(self):
        doc = example("function-map")
        self.fn(doc)["candidates"][1]["rejectedBecause"] = []
        self.bad("function-map", doc, "needs rejectedBecause")

    def test_selected_function_has_exactly_one_selected_candidate(self):
        doc = example("function-map")
        self.fn(doc)["candidates"][1]["status"] = "selected"
        self.bad("function-map", doc, "exactly one selected candidate")

    def test_dep_and_step_ids_are_unique_within_a_candidate(self):
        doc = example("function-map")
        candidate = self.fn(doc)["candidates"][0]
        candidate["ledgerDeps"].append(copy.deepcopy(candidate["ledgerDeps"][0]))
        self.bad("function-map", doc, "depId D-box-p01 repeats")
        doc = example("function-map")
        candidate = self.fn(doc)["candidates"][0]
        candidate["steps"][1]["stepId"] = candidate["steps"][0]["stepId"]
        self.bad("function-map", doc, "stepId F-box-1.A.s1 repeats")

    def test_candidate_origin_is_the_most_user_given_step_origin_and_old_form_is_named(self):
        doc = example("function-map")
        self.fn(doc)["candidates"][0]["origin"] = "designed"
        self.bad("function-map", doc, "most user-given")
        detail = contracts.check_contract_detailed("function-map", doc)
        self.assertTrue(detail["failedOnlyOnLegacyForms"])
        self.fn(doc)["candidates"][0]["steps"][0]["origin"] = "user_given_modified"
        self.fn(doc)["candidates"][0]["origin"] = "user_given_modified"
        self.ok("function-map", doc)

    def test_closed_defect_needs_a_confirming_record(self):
        doc = example("function-map")
        self.fn(doc)["candidates"][0]["closes"] = [{"defectId": "X-1"}]
        self.bad("function-map", doc, "confirmedBy")
        self.fn(doc)["candidates"][0]["closes"] = [{"defectId": "X-1", "confirmedBy": "RC-box-1B"}]
        self.ok("function-map", doc)

    def test_selected_candidate_record_has_no_open_load_bearing_gap(self):
        doc, record = example("function-map"), example("answers")
        self.ok("function-map", doc, {"records": {"RC-box-1A": record}})
        del record["answers"][1]["disposition"]
        self.bad("function-map", doc, "without a disposition", {"records": {"RC-box-1A": record}})
        self.assertTrue(contracts.check_contract_detailed("function-map", doc)["notEvaluated"])


class LedgerTests(Case):
    def entry(self, doc, entry_id):
        return next(e for e in doc["entries"] if e["id"] == entry_id)

    def test_origin_is_required(self):
        doc = example("ledger-entry")
        del doc["entries"][0]["origin"]
        self.bad("ledger-entry", doc, ".origin: required")

    def test_conflicts_are_listed_both_ways_unless_acknowledged_out_of_scope(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-tl-002")["conflictsWith"] = []
        self.entry(doc, "L-tl-002")["status"] = "asserted"
        self.bad("ledger-entry", doc, "does not list it back")
        self.entry(doc, "L-tl-002")["conflictsOutOfScope"] = ["L-tl-001"]
        self.ok("ledger-entry", doc)
        doc = example("ledger-entry")
        self.entry(doc, "L-tl-002")["conflictsWith"] = []
        self.entry(doc, "L-tl-002")["status"] = "asserted"
        self.entry(doc, "L-tl-001").update(status="retired", decisionRef="D-002")
        self.ok("ledger-entry", doc)

    def test_contested_entry_names_the_conflict_and_its_kind(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-tl-002")["conflictKind"] = None
        del self.entry(doc, "L-tl-002")["conflictKind"]
        self.bad("ledger-entry", doc, "needs a conflictKind")
        doc = example("ledger-entry")
        self.entry(doc, "L-proc-001")["status"] = "contested"
        self.bad("ledger-entry", doc, "names what it conflicts with")

    def test_accepted_license_needs_human_words(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-obj-001")["status"] = "accepted_license"
        self.bad("ledger-entry", doc, "humanWords")
        self.entry(doc, "L-obj-001")["humanWords"] = "这个就这么留着，观众信"
        self.ok("ledger-entry", doc)

    def test_license_covers_only_contradicts_reality_gaps(self):
        doc = example("ledger-entry")
        self.ok("ledger-entry", doc, {"defectKinds": {"box-no-notice": ["contradicts_reality"]}})
        self.bad("ledger-entry", doc, "contradicts_reality", {"defectKinds": {"box-no-notice": ["motive"]}})
        notes = contracts.check_contract_detailed("ledger-entry", doc)["notEvaluated"]
        self.assertTrue(any("license-on-contradicts-reality" in note for note in notes))

    def test_retiring_a_user_given_entry_needs_a_reference(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-tl-003")["status"] = "retired"
        self.bad("ledger-entry", doc, "retiring a user-given entry")
        self.entry(doc, "L-tl-003")["retiresInto"] = ["L-tl-004"]
        self.ok("ledger-entry", doc)

    def test_not_asked_entry_cannot_be_verified(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-proc-001")["notAsked"] = True
        self.bad("ledger-entry", doc, "notAsked")

    def test_state_subtype_lives_under_timeline(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-tl-003")["kind"] = "knowledge"
        self.bad("ledger-entry", doc, "subtype state")

    def test_string_next_necessary_move_is_a_legacy_form(self):
        doc = example("ledger-entry")
        self.entry(doc, "L-proc-001")["nextNecessaryMove"] = "退回前通知寄件人"
        detail = contracts.check_contract_detailed("ledger-entry", doc)
        self.assertTrue(detail["errors"] and detail["failedOnlyOnLegacyForms"], detail)
        self.assertTrue(any("nextNecessaryMove" in hint for hint in detail["legacyForms"]))

    def test_delta_new_entry_is_complete_and_supported(self):
        doc = example("ledger-delta")
        del doc["writes"][1]["change"]["title"]
        self.bad("ledger-delta", doc, "complete entry")
        doc = example("ledger-delta")
        del doc["writes"][0]["supportedBy"]
        self.bad("ledger-delta", doc, "supportedBy")
        doc = example("ledger-delta")
        doc["writes"].append(copy.deepcopy(doc["writes"][1]))
        self.bad("ledger-delta", doc, "created twice")

    def test_delta_rejects_free_text_changes(self):
        doc = example("ledger-delta")
        doc["writes"][0]["change"] = "把位置改成仓库"
        self.bad("ledger-delta", doc, "expected object")
        doc["writes"][0]["change"] = {}
        self.bad("ledger-delta", doc, "change is empty")


class QuestionAndAnswerTests(Case):
    def test_question_set_numbers_are_unique_and_drafts_name_their_note(self):
        doc = example("question-set")
        doc["questions"][1]["q"] = 1
        self.bad("question-set", doc, "q 1 repeats")
        doc = example("question-set")
        del doc["questions"][2]["noteId"]
        self.bad("question-set", doc, "noteId")

    def test_a_project_may_add_but_not_remove_questions(self):
        base = contracts.question_sets()["reality-check-questions@v1"]
        trimmed = copy.deepcopy(base)
        trimmed["questions"] = trimmed["questions"][:-1]
        self.bad("question-set", trimmed, "not remove", {"baseQuestionSet": base})
        grown = copy.deepcopy(base)
        grown["questions"].append({"q": 17, "text": "新问", "answerKind": "tristate", "source": "writer-note WN-9", "addedIn": "v1-project"})
        self.ok("question-set", grown, {"baseQuestionSet": base})

    def test_missing_answer_kind_is_a_legacy_form(self):
        doc = example("question-set")
        for question in doc["questions"]:
            del question["answerKind"]
        self.assertTrue(contracts.check_contract_detailed("question-set", doc)["failedOnlyOnLegacyForms"])

    def test_each_answer_has_exactly_one_anchor_and_one_kind_per_record(self):
        doc = example("answers")
        doc["answers"][0]["quoteRef"] = {"line": 3, "quote": "三年前就退了"}
        self.bad("answers", doc, "exactly one anchor")
        doc = example("answers")
        del doc["answers"][0]["landsOn"]
        self.bad("answers", doc, "exactly one anchor")

    def test_asked_subset_names_real_questions_and_old_spelling_is_named(self):
        doc = example("answers")
        self.ok("answers", doc)
        doc["askedSubset"] = [4, 99]
        self.bad("answers", doc, "askedSubset: [99]")
        doc = example("answers")
        doc["scopeOfQuestions"] = doc.pop("askedSubset")
        self.assertIn("scopeOfQuestions → askedSubset", contracts.check_contract_detailed("answers", doc)["legacyForms"])

    def test_retell_fact_refs_have_a_fixed_shape(self):
        doc = example("retell-record")
        self.ok("retell-record", doc)
        doc["factRefs"][0]["status"] = "kind_of"
        self.bad("retell-record", doc, "not in")
        doc = example("retell-record")
        del doc["factRefs"][0]["retellRefs"]
        self.bad("retell-record", doc, "retellRefs: required")

    def test_neutral_question_examples_keep_the_v1_wording(self):
        data = contracts.question_sets()["reality-check-questions@v1"]
        self.assertTrue(data["examplesNote"].strip())
        self.assertNotIn("挂锁", json.dumps(data, ensure_ascii=False))

    def test_question_must_exist_in_the_cited_set(self):
        doc = example("answers")
        doc["answers"][0]["q"] = 40
        self.bad("answers", doc, "not in reality-check-questions@v1")

    def test_not_holds_carries_defect_key_and_known_kind(self):
        doc = example("answers")
        del doc["answers"][1]["defectKey"]
        self.bad("answers", doc, "defectKey")
        doc = example("answers")
        doc["answers"][1]["defectKind"] = ["vibes"]
        self.bad("answers", doc, "defectKind 'vibes'")

    def test_load_bearing_not_holds_has_a_legal_destination(self):
        doc = example("answers")
        del doc["answers"][1]["disposition"]
        self.bad("answers", doc, "needs a disposition")
        doc["answers"][1]["disposition"] = {"to": "leaves_open"}
        self.bad("answers", doc, "cannot be left open")
        doc["answers"][1]["disposition"] = {"to": "license", "ref": None}
        self.bad("answers", doc, "must cite")
        doc["answers"][1]["disposition"] = {"to": "license", "ref": "L-obj-001"}
        self.ok("answers", doc)
        doc["answers"][1]["loadBearing"] = False
        del doc["answers"][1]["disposition"]
        self.ok("answers", doc)

    def test_not_evaluable_says_why(self):
        doc = example("answers")
        del doc["answers"][2]["because"]
        self.bad("answers", doc, "not_evaluable says why")

    def test_informational_questions_stay_out_of_the_outcome(self):
        doc = example("answers")
        doc["answers"] = [doc["answers"][0], {"q": 14, "landsOn": "F-box-1.A", "holds": "notHolds", "reason": "能换", "defectKey": "k"}]
        doc["outcome"] = "pass"
        self.ok("answers", doc)
        doc["outcome"] = "fail"
        self.bad("answers", doc, "informational questions do not count")

    def test_outcome_follows_the_answers_and_inherited_gaps(self):
        doc = example("answers")
        doc["outcome"] = "pass"
        self.bad("answers", doc, "disagrees")
        doc = example("answers")
        doc["answers"][1]["inheritedFrom"] = "RC-up-1"
        self.bad("answers", doc, "fail_inherited")
        doc["outcome"] = "fail_inherited"
        self.ok("answers", doc)

    def test_empty_card_cannot_back_a_holds_answer(self):
        doc = example("answers")
        self.ok("answers", doc, {"cards": {"K1-tuijian": "sourced"}})
        self.bad("answers", doc, "empty card", {"cards": {"K1-tuijian": "empty"}})

    def test_closes_need_a_confirming_record_and_patched_gaps_do_not_count(self):
        doc = example("answers")
        doc["closes"] = [{"defectId": "X-9"}]
        self.bad("answers", doc, "confirmedBy")
        doc["closes"] = [{"defectId": "box-liu-never-saw", "confirmedBy": "RC-box-1B"}]
        doc["answers"][1]["patch"] = "added_explanation"
        self.bad("answers", doc, "patch")

    def test_dialogue_check_uses_quote_ref_without_outline_only_fields(self):
        doc = {"checkId": "DC-1", "target": {"kind": "episode_text", "file": "drafts/ep-003.md"},
               "questionsVersion": "dialogue-check-questions@v1", "outcome": "fail",
               "answers": [{"q": 1, "quoteRef": {"line": 12, "quote": "三年前就退了"}, "holds": "notHolds", "reason": "没要到",
                            "loadBearing": True, "defectKind": ["speaker_basis_missing"]}]}
        self.ok("answers", doc)

    def test_list_kind_and_queue_disposition_are_legacy_forms(self):
        doc = example("answers")
        doc["answers"][1]["kind"] = doc["answers"][1].pop("defectKind")
        doc["answers"][1]["disposition"] = {"to": "decision_queue", "ref": "D-001"}
        detail = contracts.check_contract_detailed("answers", doc)
        self.assertTrue(detail["errors"] and detail["failedOnlyOnLegacyForms"], detail)


class PlanTests(Case):
    def test_exceeding_season_episode_must_pick_an_action(self):
        doc = example("season-plan")
        doc["episodes"][1]["capacity"]["action"] = None
        self.bad("season-plan", doc, "needs an action")
        doc = example("season-plan")
        doc["episodes"][1]["capacity"]["actionDetail"] = "拆不拆待定"
        self.bad("season-plan", doc, "待定")

    def test_season_episodes_are_unique_across_spellings(self):
        doc = example("season-plan")
        doc["episodes"][1]["episode"] = "ep003"
        self.bad("season-plan", doc, "appears twice")

    def test_episode_plan_nine_required_fields(self):
        for field in ("episode", "title", "entry", "functions", "events", "moves", "infoLedger", "ledgerDelta", "exit", "capacity"):
            doc = example("episode-plan")
            del doc[field]
            with self.subTest(field=field):
                self.bad("episode-plan", doc, f"$.{field}: required")
        doc = example("episode-plan")
        for optional in ("presence", "realityRefs", "threads", "pending", "summary"):
            del doc[optional]
        self.ok("episode-plan", doc)

    def test_closing_event_is_the_last_beat(self):
        doc = example("episode-plan")
        doc["exit"]["closingEvent"]["beatRef"] = "3-1.b1"
        self.bad("episode-plan", doc, "not the last beat")

    def test_fact_carrier_and_delta_support_point_into_this_episode(self):
        doc = example("episode-plan")
        doc["infoLedger"][0]["facts"][0]["carrierBeat"] = "9-9.b9"
        self.bad("episode-plan", doc, "carrierBeat 9-9.b9")
        doc = example("episode-plan")
        doc["ledgerDelta"]["writes"][0]["supportedBy"] = "场 3-2"
        self.bad("episode-plan", doc, "supportedBy 场 3-2")
        doc = example("episode-plan")
        doc["ledgerDelta"]["episode"] = 4
        self.bad("episode-plan", doc, "differs from the plan")

    def test_capacity_status_is_fits_or_a_proposal(self):
        doc = example("episode-plan")
        doc["capacity"]["status"] = "exceeds"
        self.bad("episode-plan", doc, "does not match")
        doc["capacity"]["status"] = "proposal:D-002"
        self.ok("episode-plan", doc)

    def test_decision_default_is_an_option_that_keeps_functions(self):
        doc = example("decision-queue")
        doc["entries"][0]["default"] = "maybe"
        self.bad("decision-queue", doc, "not one of the optionIds")
        doc["entries"][0]["default"] = "rewrite"
        self.bad("decision-queue", doc, "drops function sentences")
        doc["entries"][0]["options"][1]["losesFunctions"] = "not_evaluable（范围外未核）"
        self.ok("decision-queue", doc)
        doc["entries"][0]["default"] = ""
        self.bad("decision-queue", doc, "shorter than 1")

    def test_decided_entry_needs_human_words_and_kind_is_in_vocabulary(self):
        doc = example("decision-queue")
        doc["entries"][0]["status"] = "decided"
        self.bad("decision-queue", doc, "humanWords")
        doc = example("decision-queue")
        doc["entries"][0]["kind"] = "season"
        self.bad("decision-queue", doc, "not in")


class DialogueTests(Case):
    def topic(self, doc):
        return doc["scenes"][0]["topics"][0]

    def test_media_profile_rejects_quota_fields(self):
        doc = example("media-profile")
        doc["formatDefault"]["live"]["turnsPerMinute"] = 14
        self.bad("media-profile", doc, "turnsPerMinute")
        doc = example("media-profile")
        doc["projectValue"] = {"speechRateCharsPerMin": 170, "linesPerMinuteBand": [10, 14]}
        self.bad("media-profile", doc, "linesPerMinuteBand")

    def test_dialogue_plan_has_no_estimates(self):
        doc = example("dialogue-plan")
        doc["estimates"] = {"voicedLines": 30}
        self.bad("dialogue-plan", doc, "$.estimates")

    def test_dialogue_plan_info_is_carried_and_references_resolve(self):
        doc = example("dialogue-plan")
        doc["infoLedger"][0]["carriedBy"] = {"exchangeIds": []}
        self.bad("dialogue-plan", doc, "carried by no exchange")
        doc["infoLedger"][0]["carriedBy"] = {"exchangeIds": [], "pictureReason": {"why": "她一个人在后门外，没有对象"}}
        self.ok("dialogue-plan", doc)
        doc = example("dialogue-plan")
        doc["infoLedger"][0]["carriedBy"]["exchangeIds"] = ["X-none"]
        self.bad("dialogue-plan", doc, "unknown exchanges")
        doc = example("dialogue-plan")
        self.topic(doc)["exchanges"][0]["carries"] = ["I9-f9"]
        self.bad("dialogue-plan", doc, "not in infoLedger factIds")

    def test_dialogue_plan_shape_reason_cites_the_situation(self):
        doc = example("dialogue-plan")
        self.topic(doc)["shape"]["citesSituation"] = []
        self.topic(doc)["shape"]["reason"] = "这样写好看"
        self.bad("dialogue-plan", doc, "must cite the situation")

    def test_dialogue_plan_segments_have_two_sides_and_known_ids(self):
        doc = example("dialogue-plan")
        self.topic(doc)["segments"][0]["between"].append("刘叔")
        self.bad("dialogue-plan", doc, "at most 2")
        doc = example("dialogue-plan")
        self.topic(doc)["exchanges"][0]["segmentId"] = "T9-s9"
        self.bad("dialogue-plan", doc, "unknown segment")
        doc = example("dialogue-plan")
        del self.topic(doc)["segments"][0]["closer"]
        self.bad("dialogue-plan", doc, "closer: required")

    def test_dialogue_target_has_no_bands_and_conventions_cite_notes(self):
        doc = example("dialogue-target")
        doc["acceptedBand"] = {"turns": [10, 14]}
        self.bad("dialogue-target", doc, "acceptedBand")
        doc = example("dialogue-target")
        doc["conventions"][0]["sourceNotes"] = []
        self.bad("dialogue-target", doc, "at least 1")

    def test_exchange_scope_walkthrough_and_fingerprint(self):
        doc = example("dialogue-exchange")
        doc["scope"]["level"] = "studio"
        self.bad("dialogue-exchange", doc, "mali_story_template")
        doc["origin"] = {"kind": "mali_story_template"}
        self.ok("dialogue-exchange", doc)
        doc = example("dialogue-exchange")
        del doc["walkthrough"]
        self.bad("dialogue-exchange", doc, "walkthrough: required")
        doc = example("dialogue-exchange")
        del doc["localSha256"]
        self.bad("dialogue-exchange", doc, "local_fingerprint")
        doc = example("dialogue-exchange")
        doc["startMs"] = 99999
        self.bad("dialogue-exchange", doc, "after endMs")

    def test_manifest_lists_each_episode_once(self):
        doc = example("corpus-manifest")
        doc["episodes"].append(copy.deepcopy(doc["episodes"][0]))
        self.bad("corpus-manifest", doc, "listed twice")

    def test_contrast_pair_and_writer_note_stay_project_private(self):
        doc = example("contrast-pair")
        doc["scope"]["level"] = "studio"
        self.bad("contrast-pair", doc, "must equal 'project'")
        doc = example("writer-note")
        doc["scope"]["level"] = "studio"
        self.bad("writer-note", doc, "must equal 'project'")

    def test_contrast_pair_needs_why_not_here_and_old_placement_is_named(self):
        doc = example("contrast-pair")
        doc["negative"]["whyNotHere"] = doc.pop("whyNotHere")
        self.bad("contrast-pair", doc, "whyNotHere: required")
        self.assertTrue(contracts.check_contract_detailed("contrast-pair", doc)["failedOnlyOnLegacyForms"])

    def test_writer_note_needs_a_source(self):
        doc = example("writer-note")
        del doc["source"]
        self.bad("writer-note", doc, "source: required")

    def test_retell_reads_one_item_and_records_the_prompt(self):
        doc = example("retell-record")
        doc["readingScope"].append("planning/episode-plan-003.json")
        self.bad("retell-record", doc, "exactly one item")
        doc = example("retell-record")
        del doc["promptVersion"]
        self.bad("retell-record", doc, "promptVersion: required")
        self.assertTrue(contracts.check_contract_detailed("retell-record", doc)["failedOnlyOnLegacyForms"])

    def test_consistency_record_has_no_band_and_explains_inconsistency(self):
        doc = example("plan-text-consistency")
        doc["rules"]["speaker-sequence"]["within"] = True
        self.bad("plan-text-consistency", doc, "within")
        doc = example("plan-text-consistency")
        doc["topics"][0]["note"] = ""
        self.bad("plan-text-consistency", doc, "says where")

    def test_defect_register_is_generated_and_derived_from_records(self):
        doc = example("defect-register")
        del doc["generatedBy"]
        self.bad("defect-register", doc, "generatedBy: required")
        doc = example("defect-register")
        doc["defects"][0]["records"] = []
        self.bad("defect-register", doc, "at least one answer record")
        doc = example("defect-register")
        doc["defects"][0]["disposition"] = {"to": "leaves_open", "ref": None}
        self.bad("defect-register", doc, "cannot be left open")


class ExtendedContractTests(Case):
    def test_task_constraints_hit_either_blocklist_whatever_the_origin(self):
        for text, category in (("不动集数，只改一次", "structure_freeze"), ("标题不变", "structure_freeze"),
                               ("每句不超过 15 个字", "numeric_dialogue"), ("台词控制在 40 句以内", "numeric_dialogue"),
                               ("换人数保持原样", "numeric_dialogue")):
            for origin in ("writer", "skill"):
                doc = example("task")
                doc["constraints"] = [{"text": text, "origin": origin}]
                with self.subTest(text=text, origin=origin):
                    self.bad("task", doc, category)
        doc = example("task")
        doc["constraints"] = [{"text": "孩子对大人说话先叫人再说事", "origin": "target", "cite": "C1"}]
        self.ok("task", doc)

    def test_orchestrator_constraint_cites_a_target_clause(self):
        doc = example("task")
        doc["constraints"] = [{"text": "先接情绪再说事", "origin": "orchestrator"}]
        self.bad("task", doc, "must cite")

    def test_dialogue_layer_task_cites_the_dialogue_target(self):
        doc = example("task")
        doc["layer"] = "C5a"
        self.bad("task", doc, "dialogueTarget")
        doc["dialogueTarget"] = {"targetId": "town-dialogue-target", "revision": "v0.1"}
        self.ok("task", doc)

    def test_review_finding_without_cites_is_a_preference(self):
        doc = example("review-record")
        self.ok("review-record", doc)
        doc["findings"][0]["kind"] = "finding"
        self.bad("review-record", doc, "must be kind: preference")
        doc["findings"][0]["kind"] = "preference"
        self.ok("review-record", doc)
        doc["findings"][0].update(kind="finding", cites={"ledgerId": "L-obj-001"})
        self.ok("review-record", doc)

    def test_review_adjudications_name_known_findings(self):
        doc = example("review-record")
        doc["adjudications"] = [{"findingIds": ["nope"], "decision": "按目标 C1", "reason": "两条冲突，目标优先"}]
        self.bad("review-record", doc, "unknown finding ids")
        doc["adjudications"][0]["findingIds"] = [doc["findings"][0]["id"]]
        self.ok("review-record", doc)

    def test_handoff_accepts_a_structured_ledger_delta_and_read_scope(self):
        doc = example("run-handoff")
        doc["readScope"] = ["planning/episode-plan-003.json"]
        doc["stateChangeProposals"].append({"claim": "老陈知道箱子已退", "evidence": doc["outputs"][0],
                                            "ledgerDelta": example("ledger-delta")})
        for key in ("schemaVersion", "unknowns", "formatNotes"):
            doc["stateChangeProposals"][-1]["ledgerDelta"].pop(key, None)
        self.ok("run-handoff", doc)
        doc["stateChangeProposals"][-1]["ledgerDelta"]["track"] = "maybe"
        self.bad("run-handoff", doc, "not in")

    def test_cold_reader_package_takes_one_project_fact(self):
        doc = example("context-snapshot")
        doc["createdFor"]["role"] = "cold_reader"
        self.bad("context-snapshot", doc, "cold_reader")
        doc = example("selection")
        doc["role"] = "cold_reader"
        doc["items"] = [item for item in doc["items"] if item["partition"] == "project_facts"][:1]
        self.ok("selection", doc)
        doc["items"].append(copy.deepcopy(doc["items"][0]))
        doc["items"][-1]["ref"]["id"] = "other-page"
        self.bad("selection", doc, "exactly one project_facts")

    def test_knowledge_card_coverage_matches_its_rules(self):
        doc = example("knowledge-card")
        doc["coverage"] = "empty"
        doc["content"]["rules"] = [{"text": "满期退回", "support": "sourced"}]
        self.bad("knowledge-card", doc, "empty card")
        doc["content"]["rules"][0]["support"] = "not_found"
        self.ok("knowledge-card", doc)
        doc["coverage"] = "sourced"
        self.bad("knowledge-card", doc, "a sourced card")
        doc["content"]["rules"].append({"text": "期满前通知", "support": "sourced"})
        doc["evidence"]["sources"] = [{"sourceId": "S-1", "location": "条文摘录", "versionOrDate": "2026-10-15", "sourceTier": "official"}]
        doc["content"].update(caseFacts=["一例"], distanceFromOurs=["不是亲属"])
        self.ok("knowledge-card", doc)


class StreamBAlignmentTests(Case):
    def test_empty_and_mixed_track_ledgers_are_valid(self):
        doc = example("ledger-entry")
        doc["entries"], doc["track"] = [], "mixed"
        self.ok("ledger-entry", doc)
        doc["track"] = "sideways"
        self.bad("ledger-entry", doc, "not in")

    def test_season_capacity_may_cite_a_decision(self):
        doc = example("season-plan")
        doc["episodes"][1]["capacity"].update(action="drop_function", decisionRef="D-003")
        self.ok("season-plan", doc)
        doc["episodes"][1]["capacity"]["decisionRef"] = 3
        self.bad("season-plan", doc, "expected string/null")

    def test_decided_entry_records_the_chosen_option(self):
        doc = example("decision-queue")
        doc["entries"][0].update(status="decided", humanWords="留着，观众信", decision="keep")
        self.ok("decision-queue", doc)
        doc["entries"][0]["decision"] = "something-else"
        self.bad("decision-queue", doc, "chosen optionId")
        del doc["entries"][0]["decision"]
        self.bad("decision-queue", doc, "chosen optionId")

    def test_handoff_change_proposal_can_carry_its_default(self):
        doc = example("run-handoff")
        doc["changeProposals"][0].update(kind="upstream_change", options=[{"optionId": "keep", "text": "照旧"}],
                                         default="keep", defaultReason="不替主创改上游", decisionId="D-004")
        self.ok("run-handoff", doc)
        doc["changeProposals"][0]["default"] = "rewrite"
        self.bad("run-handoff", doc, "not one of its options")

    def test_defect_register_counts_and_conflicting_disposition(self):
        doc = example("defect-register")
        doc["counts"] = {"defects": 1}
        doc["defects"][0]["disposition"] = {"to": "conflicting", "dispositions": [{"checkId": "RC-box-1A", "to": "decision"}]}
        self.ok("defect-register", doc)
        doc["defects"][0]["disposition"]["dispositions"] = []
        self.bad("defect-register", doc, "conflicting disposition")

    def test_writer_revised_is_an_origin(self):
        doc = example("function-map")
        candidate = doc["threads"][0]["functions"][0]["candidates"][1]
        candidate["origin"] = "writer_revised"
        candidate["steps"][0]["origin"] = "writer_revised"
        self.ok("function-map", doc)
        candidate["origin"] = "ghost_written"
        self.bad("function-map", doc, "not in")


class CliTests(unittest.TestCase):
    def cli(self, name, path):
        run = subprocess.run([sys.executable, "-B", str(TOOL), "contract-check", name, str(path)], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_new_contract_exit_codes_and_reproduce_command(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            path.write_text(json.dumps(example("season-plan"), ensure_ascii=False), encoding="utf-8")
            code, result = self.cli("season-plan", path)
            self.assertEqual((code, result["passed"]), (0, True))
            self.assertIn("contract-check season-plan", result["reproduceCommand"])
            doc = example("season-plan")
            doc["episodes"][1]["capacity"]["action"] = None
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            code, result = self.cli("season-plan", path)
            self.assertEqual((code, result["passed"]), (2, False))
            for forbidden in ("within", "outside", "score"):
                self.assertNotIn(forbidden, result)

    def test_jsonl_files_are_checked_line_by_line(self):
        good, bad = example("dialogue-exchange"), example("dialogue-exchange")
        del bad["walkthrough"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "exchanges.jsonl"
            path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in (good, bad)) + "\n", encoding="utf-8")
            result = contracts.run_contract_check("dialogue-exchange", str(path))
        self.assertFalse(result["passed"])
        self.assertTrue(all(error.startswith("line 2: ") for error in result["errors"]), result["errors"])

    def test_legacy_only_failure_is_reported_as_such(self):
        doc = example("retell-record")
        del doc["promptVersion"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "retell.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            code, result = self.cli("retell-record", path)
        self.assertEqual(code, 2)
        self.assertTrue(result["failedOnlyOnLegacyForms"])
        self.assertTrue(result["legacyForms"])


if __name__ == "__main__":
    unittest.main()
