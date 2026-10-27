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
EXAMPLES = ROOT / "skills/drama-studio/examples"
spec = importlib.util.spec_from_file_location("contract_check", ROOT / "skills/drama-studio/scripts/contract_check.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


class ContractShapeTests(unittest.TestCase):
    def assertRejected(self, name, document, fragment):
        errors = contracts.check_contract(name, document)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_every_schema_has_an_example_that_passes(self):
        names = contracts.schema_names()
        self.assertEqual(names, sorted(path.stem for path in EXAMPLES.glob("*.json")))
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(contracts.check_contract(name, example(name)), [])

    def test_schema_version_matches_id(self):
        for name in contracts.schema_names():
            schema = contracts.load_schema(name)
            self.assertEqual(schema["$id"], schema["properties"]["schemaVersion"]["const"])

    def test_missing_field_unknown_field_and_bad_enum(self):
        doc = example("task")
        del doc["goal"]
        self.assertRejected("task", doc, "$.goal: required")
        doc = example("task")
        doc["quality_passed"] = True
        self.assertRejected("task", doc, "quality_passed: not allowed")
        doc = example("task")
        doc["status"]["run"] = "done"
        self.assertRejected("task", doc, "not in")

    def test_wrong_version_and_fingerprint_are_rejected(self):
        doc = example("remote-receipt")
        doc["schemaVersion"] = "drama-studio/remote-receipt/v9"
        self.assertRejected("remote-receipt", doc, "must equal")
        doc = example("remote-receipt")
        doc["inputFingerprint"] = "sha256:XYZ"
        self.assertRejected("remote-receipt", doc, "does not match")

    def test_boolean_is_not_an_integer(self):
        doc = example("task")
        doc["revisionBudget"] = True
        self.assertRejected("task", doc, "expected integer")


class ScriptRuleTests(unittest.TestCase):
    def assertRejected(self, name, document, fragment):
        errors = contracts.check_contract(name, document)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_shared_knowledge_scope_is_not_enabled(self):
        doc = example("knowledge-card")
        doc["scope"]["level"] = "studio"
        self.assertRejected("knowledge-card", doc, "not enabled in this version")

    def test_non_synthetic_knowledge_needs_a_source(self):
        doc = example("knowledge-card")
        doc["evidence"]["nature"] = "observation"
        self.assertRejected("knowledge-card", doc, "needs at least one exact source")

    def test_budget_overflow_is_not_silently_truncated(self):
        doc = example("context-snapshot")
        doc["budget"]["limit"] = 100
        self.assertRejected("context-snapshot", doc, "exceed limit")

    def test_omitted_required_material_cannot_be_complete(self):
        doc = example("context-snapshot")
        doc["omitted"][0]["required"] = True
        self.assertRejected("context-snapshot", doc, "cannot be complete")
        doc["completeness"] = "incomplete"
        self.assertEqual(contracts.check_contract("context-snapshot", doc), [])

    def test_evaluation_material_stays_out_of_author_packages(self):
        doc = example("context-snapshot")
        doc["items"][2]["usage"] = "evaluation_only"
        self.assertRejected("context-snapshot", doc, "evaluation_only")
        doc["items"][2]["usage"] = "comparison_only"
        self.assertRejected("context-snapshot", doc, "comparison_only")

    def test_required_material_must_pin_revision_and_not_repeat(self):
        doc = example("context-snapshot")
        doc["items"][0]["ref"]["revision"] = None
        self.assertRejected("context-snapshot", doc, "exact revision")
        doc = example("context-snapshot")
        doc["items"].append(copy.deepcopy(doc["items"][0]))
        self.assertRejected("context-snapshot", doc, "duplicate reference")

    def test_mixed_revisions_and_inverted_range_are_rejected(self):
        doc = example("context-snapshot")
        extra = copy.deepcopy(doc["items"][1])
        extra["ref"]["revision"] = 2
        extra["ref"]["range"] = {"start": 0, "end": 100}
        doc["items"].append(extra)
        self.assertRejected("context-snapshot", doc, "mixed revisions")
        doc = example("context-snapshot")
        doc["items"][1]["ref"]["range"] = {"start": 900, "end": 10}
        self.assertRejected("context-snapshot", doc, "start is after end")
        doc = example("context-snapshot")
        doc["omitted"][0]["ref"]["range"] = {"start": 9, "end": 1}
        self.assertRejected("context-snapshot", doc, "omitted[0]: range")

    def test_every_contract_accepts_unknowns(self):
        for name in contracts.schema_names():
            doc = example(name)
            doc["unknowns"] = ["远端项目 ID 未知"]
            self.assertEqual(contracts.check_contract(name, doc), [], name)

    def test_knowledge_cannot_masquerade_as_project_fact(self):
        doc = example("context-snapshot")
        doc["items"][2]["partition"] = "project_facts"
        self.assertRejected("context-snapshot", doc, "cannot be packed as project facts")

    def test_reader_effect_package_excludes_author_plan(self):
        doc = example("context-snapshot")
        doc["createdFor"]["role"] = "reader_effect"
        self.assertRejected("context-snapshot", doc, "reader_effect")

    def test_fact_finding_needs_evidence_and_self_review_is_not_independent(self):
        doc = example("review-record")
        doc["findings"][0]["evidence"] = []
        self.assertRejected("review-record", doc, "needs quoted evidence")
        doc = example("review-record")
        doc["claimsIndependence"] = True
        self.assertRejected("review-record", doc, "cannot claim independence")

    def test_change_proposal_must_go_upstream(self):
        doc = example("run-handoff")
        doc["changeProposals"][0]["targetLayer"] = "C5"
        self.assertRejected("run-handoff", doc, "upstream layer")
        doc["workstation"] = "C6"
        self.assertEqual(contracts.check_contract("run-handoff", doc), [])

    def test_estimated_usage_cannot_state_tokens(self):
        doc = example("run-handoff")
        doc["host"]["usage"]["tokens"] = 1200
        self.assertRejected("run-handoff", doc, "host-reported")

    def test_unknown_remote_outcome_blocks_blind_retry(self):
        doc = example("remote-receipt")
        doc["retryAllowed"] = True
        self.assertRejected("remote-receipt", doc, "reconciled by requestId")

    def test_confirmed_save_needs_remote_identity(self):
        doc = example("remote-receipt")
        doc["outcome"] = "confirmed"
        self.assertRejected("remote-receipt", doc, "artifactId and revision")
        doc["remote"].update(artifactId="art-ep21-draft", revision=1)
        self.assertEqual(contracts.check_contract("remote-receipt", doc), [])

    def test_local_fields_cannot_certify_adoption(self):
        doc = example("task")
        doc["status"]["adoption"] = "adopted_remote"
        self.assertRejected("task", doc, "remote_receipt reference")

    def test_local_file_is_not_adoption_evidence(self):
        doc = example("task")
        doc["status"]["adoption"] = "adopted_remote"
        doc["adoptionEvidence"] = {"kind": "local_file", "id": "approved.md", "revision": None}
        self.assertRejected("task", doc, "remote_receipt reference")
        doc["adoptionEvidence"] = {"kind": "remote_receipt", "id": "req-adopt-1", "revision": None}
        self.assertEqual(contracts.check_contract("task", doc), [])

    def test_unsent_request_is_recordable_without_inventing_remote_ids(self):
        doc = example("remote-receipt")
        doc["outcome"] = "not_sent"
        doc["remote"] = {"projectId": None, "artifactId": None, "revision": None, "inputSnapshotId": None}
        self.assertEqual(contracts.check_contract("remote-receipt", doc), [])
        doc["remote"]["artifactId"] = ""
        self.assertRejected("remote-receipt", doc, "unsent request")
        doc = example("remote-receipt")
        doc["remote"]["projectId"] = None
        self.assertRejected("remote-receipt", doc, "must name its project")

    def test_no_authorization_means_no_write_scope(self):
        doc = example("task")
        doc["authorization"]["source"] = "none"
        self.assertRejected("task", doc, "nothing may be written")


class ContractCliTests(unittest.TestCase):
    def run_cli(self, name, document):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "doc.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", str(TOOL), "contract-check", name, str(path)], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout or run.stderr)

    def test_pass_does_not_claim_remote_or_adoption(self):
        code, result = self.run_cli("task", example("task"))
        self.assertEqual(code, 0)
        self.assertTrue(result["passed"])
        self.assertFalse(result["remote_verified"])
        self.assertFalse(result["adoption_verified"])

    def test_violation_exits_2_and_bad_json_exits_1(self):
        doc = example("context-snapshot")
        doc["budget"]["limit"] = 1
        code, result = self.run_cli("context-snapshot", doc)
        self.assertEqual(code, 2)
        self.assertFalse(result["passed"])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text("{", encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", str(TOOL), "contract-check", "task", str(path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)


class D6ExtensionTests(unittest.TestCase):
    """D6-1: the six extended contracts keep their old examples valid; data files ship next to the schemas."""

    def test_extended_contracts_still_accept_their_d0_examples(self):
        for name in ("task", "review-record", "run-handoff", "context-snapshot", "selection", "knowledge-card"):
            self.assertEqual(contracts.check_contract(name, example(name)), [], name)

    def test_data_files_are_bundled_beside_the_schemas(self):
        spec_install = importlib.util.spec_from_file_location("install", ROOT / "scripts/install.py")
        install = importlib.util.module_from_spec(spec_install)
        spec_install.loader.exec_module(install)
        files = install.inventory(install.SOURCE)
        for name in ("reality-check-questions.json", "dialogue-check-questions.json", "constraint-blocklist.json"):
            self.assertIn(f"data/{name}", files)


if __name__ == "__main__":
    unittest.main()
