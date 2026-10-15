import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKS = Path(__file__).resolve().parents[1] / "skills/drama-studio/scripts/checks"

QUESTIONS = {"id": "reality-check-questions", "version": "v1", "answerStates": ["holds", "notHolds", "not_evaluable", "n/a"],
             "questions": [{"q": 1, "text": "更省事的做法"}, {"q": 2, "text": "机构会不会出手"},
                           {"q": 3, "text": "去掉实现功能还成不成", "answerKind": "informational"}]}


def record():
    return {"schema": "reality-check/v0-pilot", "checkId": "RC-test-1", "target": {"kind": "candidate", "id": "F-town-1.A"},
            "questionsVersion": "reality-check-questions@v1", "promptVersion": {"files": [{"path": "brief.md", "sha256": "sha256:0"}]},
            "answers": [{"q": 1, "landsOn": "F-town-1.A.s1 老陈去镇上取箱子", "holds": "holds", "reason": "取件只要单据"},
                        {"q": 2, "landsOn": "F-town-1.A.s2 王姨不报案", "holds": "holds", "reason": "她不知道箱子在哪"},
                        {"q": 3, "landsOn": "F-town-1.A", "holds": "notHolds", "reason": "信息题，不计入"}],
            "outcome": "pass"}


def load_bearing_not_holds():
    return {"q": 2, "landsOn": "F-town-1.A.s2", "holds": "notHolds", "reason": "派出所会通知", "loadBearing": True,
            "loadBearingBasis": "has_downstream", "loadBearingWhy": "第 3 集要靠这一步",
            "disposition": {"to": "decision", "ref": "D-001"}}


class AnswersCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.questions = self.write("questions.json", QUESTIONS)

    def write(self, name, value):
        path = self.dir / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def run_check(self, *args):
        run = subprocess.run([sys.executable, "-B", str(CHECKS / "answers_check.py"), *map(str, args)],
                             capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def check(self, value, *extra):
        code, result = self.run_check(self.write("rc.json", value), "--questions", self.questions, *extra)
        return code, result, (result["records"][0] if "records" in result else None)

    def test_well_formed_record_passes_and_informational_question_is_not_counted(self):
        code, result, rec = self.check(record())
        self.assertEqual((code, result["passed"]), (0, True), rec["errors"])
        self.assertIn("answers_check.py", result["reproduceCommand"])

    def test_missing_question_fails(self):
        value = record()
        value["answers"] = value["answers"][:1] + value["answers"][2:]
        code, _, rec = self.check(value)
        self.assertEqual(code, 2)
        self.assertTrue(any("一条回答都没有" in e and "2" in e for e in rec["errors"]))

    def test_declared_subset_does_not_require_unasked_questions(self):
        value = record()
        value["answers"] = value["answers"][:1]
        value["askedSubset"] = [1]
        self.assertEqual(self.check(value)[0], 0)
        del value["askedSubset"]
        self.assertEqual(self.check(value, "--questions-subset", "1")[0], 0)

    def test_empty_landing_bad_state_and_empty_reason_fail(self):
        for field, bad in (("landsOn", " "), ("holds", "unverified"), ("reason", "")):
            value = record()
            value["answers"][0][field] = bad
            code, _, rec = self.check(value)
            self.assertEqual(code, 2, field)

    def test_missing_prompt_version_fails(self):
        value = record()
        del value["promptVersion"]
        code, _, rec = self.check(value)
        self.assertEqual(code, 2)
        self.assertTrue(any("promptVersion" in e for e in rec["errors"]))

    def test_outcome_must_match_answers(self):
        value = record()
        value["answers"][1] = load_bearing_not_holds()
        code, _, rec = self.check(value)
        self.assertEqual(code, 2)
        value["outcome"] = "fail"
        self.assertEqual(self.check(value)[0], 0)
        value["outcome"] = "fail_inherited"
        self.assertEqual(self.check(value)[0], 2)
        value["answers"][1]["inheritedFrom"] = "RC-test-0"
        self.assertEqual(self.check(value)[0], 0)

    def test_load_bearing_not_holds_needs_basis_and_disposition(self):
        value = record()
        value["outcome"] = "fail"
        value["answers"][1] = load_bearing_not_holds()
        self.assertEqual(self.check(value)[0], 0)
        for field, bad in (("loadBearingBasis", "写作方说承重"), ("disposition", {"to": "decision_queue", "ref": "D-001"}),
                           ("disposition", {"to": "license"}), ("disposition", None)):
            broken = copy.deepcopy(value)
            broken["answers"][1][field] = bad
            self.assertEqual(self.check(broken)[0], 2, (field, bad))

    def test_disposition_reference_checked_only_when_source_given(self):
        value = record()
        value["outcome"] = "fail"
        value["answers"][1] = load_bearing_not_holds()
        _, _, rec = self.check(value)
        self.assertEqual(rec["dispositionRefsNotChecked"][0]["ref"], "D-001")
        decisions = self.write("decisions.json", {"entries": [{"id": "D-002"}]})
        self.assertEqual(self.check(value, "--decisions", decisions)[0], 2)
        decisions = self.write("decisions.json", {"entries": [{"id": "D-001"}]})
        self.assertEqual(self.check(value, "--decisions", decisions)[0], 0)
        value["answers"][1]["disposition"]["ref"] = ["D-001", "D-003"]
        self.assertEqual(self.check(value, "--decisions", decisions)[0], 2)

    def test_missing_without_search_scope_is_reported_not_failed(self):
        value = record()
        value["answers"][0]["defectKind"] = ["missing"]
        code, _, rec = self.check(value)
        self.assertEqual(code, 0)
        self.assertEqual(rec["reports"][0]["rule"], "missing-without-search-scope")
        value["answers"][0]["searchScope"] = {"files": ["outline.md"], "method": "通读"}
        self.assertEqual(self.check(value)[2]["reports"], [])

    def test_dialogue_check_uses_quote_ref(self):
        questions = self.write("dq.json", {**QUESTIONS, "id": "dialogue-check-questions"})
        value = record()
        value.update(schema="dialogue-check/v0-pilot", questionsVersion="dialogue-check-questions@v1")
        for answer in value["answers"]:
            answer["quoteRef"] = {"line": 7, "quote": "老陈：箱子呢？"}
            del answer["landsOn"]
        code, result = self.run_check(self.write("dc.json", value), "--questions", questions)
        self.assertEqual(code, 0, result)
        value["answers"][0]["quoteRef"] = {}
        self.assertEqual(self.run_check(self.write("dc.json", value), "--questions", questions)[0], 2)

    def test_coverage_report_counts_steps_and_procedure_deps_only(self):
        fmap = self.write("fm.json", {"threads": [{"functions": [{"candidates": [{
            "candidateId": "F-town-1.A",
            "steps": [{"stepId": "F-town-1.A.s1"}, {"stepId": "F-town-1.A.s2"}, {"stepId": "F-town-1.A.s3"}],
            "ledgerDeps": [{"depId": "D-town-001", "kind": "procedure"}, {"depId": "D-town-002", "kind": "timeline"}]}]}]}]})
        code, _, rec = self.check(record(), "--function-map", fmap)
        self.assertEqual(code, 0)
        self.assertEqual(rec["coverage"]["itemsCounted"], 4)
        self.assertEqual({u["id"] for u in rec["coverage"]["uncovered"]}, {"F-town-1.A.s3", "D-town-001"})

    def test_cross_reports_same_landing_with_different_states(self):
        other = record()
        other["checkId"] = "RC-test-2"
        other["answers"][0]["holds"] = "notHolds"
        other["outcome"] = "fail"
        code, result = self.run_check(self.write("a.json", record()), self.write("b.json", other),
                                      "--questions", self.questions, "--cross")
        self.assertEqual(code, 0)
        self.assertEqual([(r["q"], r["landing"]) for r in result["cross"]["inconsistent"]], [(1, "F-town-1.A.s1")])

    def test_unknown_question_set_is_input_error(self):
        code, result = self.run_check(self.write("rc.json", {**record(), "questionsVersion": "nope@v9"}))
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
