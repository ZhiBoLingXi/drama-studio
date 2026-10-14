"""function-map: check (v0/v1), merge, topics, defects build on a synthetic box thread."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/checks/function_map.py")]


def candidate(cid, status, **extra):
    out = {"candidateId": cid, "origin": "designed", "status": status, "steps": [{"stepId": f"{cid}.s1", "who": "老陈", "did": "去仓库"}],
           "ledgerDeps": [{"depId": f"{cid}.d1", "kind": "procedure", "claim": "拒收件退回寄件人", "assertion": "stated", "entryId": "L-proc-001"},
                          {"depId": f"{cid}.d2", "kind": "knowledge", "claim": "仓管记得签收人", "assertion": "required_unstated", "entryId": None}]}
    out.update(extra)
    return out


def fmap():
    return {"threads": [{"threadId": "T-box", "functions": [
        {"functionId": "F-box-1", "status": "selected", "episodesInScope": [3, "4A"], "candidates": [
            candidate("F-box-1.A", "rejected", rejectedBecause="站不住"),
            candidate("F-box-1.B", "selected", losesFunctions=[], closes=[{"defectId": "X-1", "confirmedBy": "rc/closes.json#RC-B-1"}])]},
        {"functionId": "F-box-2", "status": "open", "outOfScope": "第 20 集后", "candidates": [candidate("F-box-2.A", "candidate")]}]}]}


def record(check_id, target_id, answers, **extra):
    out = {"checkId": check_id, "target": {"kind": "candidate", "id": target_id}, "answers": answers, "outcome": "pass"}
    out.update(extra)
    return out


LB = {"q": 4, "landsOn": "F-box-1.B.s1 快递没退回", "holds": "notHolds", "reason": "按规矩要退回", "defectKey": "X-2",
      "defectKind": ["contradicts_reality"], "loadBearing": True, "loadBearingBasis": "stated_in_record",
      "disposition": {"to": "license_pending", "ref": ["L-proc-001"]}}


class FunctionMap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "rc").mkdir()
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [LB, {"q": 1, "landsOn": "s1", "holds": "holds", "reason": "成立"}]))
        self.write("rc/closes.json", {"items": [{"record": "RC-B-1", "defectId": "X-1", "verdict": "confirmed"}]})
        self.write("ledger.json", {"entries": [{"id": "L-proc-001", "kind": "procedure", "status": "license_pending"},
                                               {"id": "L-proc-old", "kind": "procedure", "status": "retired", "retiresInto": ["L-proc-001"]}]})
        self.write("dq.json", {"entries": [{"id": "DQ-1", "default": "keep"}, {"id": "DQ-2", "default": None}]})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, doc):
        path = self.dir / name
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def run_tool(self, *args):
        result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True, cwd=self.dir)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def v1(self, doc=None, *extra):
        return self.run_tool("check", self.write("fm.json", doc or fmap()), "--stage", "v1", "--rc-dir", "rc", "--ledger", "ledger.json",
                             "--decisions", "dq.json", "--records-base", ".", *extra)

    def test_v1_clean_map_passes(self):
        code, out = self.v1()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["counts"]["loadBearingNotHoldsChecked"], 1)
        self.assertIn("reproduceCommand", out)

    def test_v1_selected_cannot_lose_functions(self):
        doc = fmap()
        doc["threads"][0]["functions"][0]["candidates"][1]["losesFunctions"] = [{"functionId": "F-box-2"}]
        code, out = self.v1(doc)
        self.assertEqual(code, 2)
        self.assertIn("losesFunctions", out["errors"][0])

    def test_v1_open_function_only_out_of_scope(self):
        doc = fmap()
        del doc["threads"][0]["functions"][1]["outOfScope"]
        self.assertIn("open", self.v1(doc)[1]["errors"][0])
        scope = self.write("scope.json", {"functionsOutOfScope": [{"functionId": "F-box-2"}]})
        self.assertEqual(self.v1(doc, "--scope", scope)[0], 0)

    def test_v1_closes_confirmed_by_must_resolve_to_confirmed(self):
        self.write("rc/closes.json", {"items": [{"record": "RC-B-1", "defectId": "X-1", "verdict": "still_there"}]})
        code, out = self.v1()
        self.assertEqual(code, 2)
        self.assertIn("still_there", out["errors"][0])
        doc = fmap()
        doc["threads"][0]["functions"][0]["candidates"][1]["closes"] = [{"defectId": "X-1"}]
        self.assertIn("confirmedBy", self.v1(doc)[1]["errors"][0])

    def test_v1_record_found_by_target_not_by_filename(self):
        (self.dir / "rc/RC-B-1.json").rename(self.dir / "rc/whatever.json")
        self.assertEqual(self.v1()[0], 0)
        doc = fmap()
        doc["threads"][0]["functions"][0]["candidates"][1]["candidateId"] = "F-box-1.C"
        self.assertIn("找不到这个候选的追问单记录", " ".join(self.v1(doc)[1]["errors"]))

    def test_v1_selected_deps_need_dep_id_and_assertion(self):
        doc = fmap()
        doc["threads"][0]["functions"][0]["candidates"][1]["ledgerDeps"][0]["assertion"] = None
        self.assertIn("assertion", self.v1(doc)[1]["errors"][0])

    def test_v1_origin_most_user(self):
        doc = fmap()
        cand = doc["threads"][0]["functions"][0]["candidates"][1]
        cand["steps"][0]["origin"] = "user_given_modified"
        self.assertIn("决定 #4", self.v1(doc)[1]["errors"][0])
        cand["origin"] = "user_given_modified"
        self.assertEqual(self.v1(doc)[0], 0)
        doc["threads"][0]["functions"][1]["candidates"][0]["steps"][0]["origin"] = "user_given"
        code, out = self.v1(doc)
        self.assertEqual(code, 0)  # not selected: reported in notes only
        self.assertTrue(out["notes"])

    def test_v1_load_bearing_disposition(self):
        bad = dict(LB, disposition={"to": "license_pending", "ref": ["L-proc-404"]})
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [bad]))
        self.assertIn("L-proc-404", self.v1()[1]["errors"][0])
        retired = dict(LB, disposition={"to": "license", "ref": "L-proc-old"})  # followed through retiresInto
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [retired]))
        self.assertEqual(self.v1()[0], 0)
        no_default = dict(LB, disposition={"to": "decision_queue", "ref": "DQ-2"})
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [no_default]))
        self.assertIn("default", self.v1()[1]["errors"][0])
        left_open = dict(LB, disposition={"to": "leaves_open", "ref": None})
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [left_open]))
        self.assertIn("leaves_open", self.v1()[1]["errors"][0])
        missing = dict(LB, disposition=None)
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [missing]))
        self.assertEqual(self.v1()[0], 2)

    def test_v1_ref_remap(self):
        moved = dict(LB, disposition={"to": "license_pending", "ref": "L-proc-gone"})
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [moved]))
        self.assertEqual(self.v1()[0], 2)
        self.assertEqual(self.v1(None, "--ref-remap", "L-proc-gone=L-proc-001")[0], 0)

    def test_v1_superseded_record_is_skipped(self):
        bad = dict(LB, disposition=None)
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [bad]))
        self.write("rc/RC-B2-1.json", record("RC-B2-1", "F-box-1.B（第二轮）", [LB], supersedes="rc/RC-B-1.json"))
        code, out = self.v1()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["counts"]["supersededCheckIds"], ["RC-B-1"])

    def test_v0_selected_needs_clean_inquiry_record(self):
        doc = fmap()
        doc["threads"][0]["functions"][1]["candidates"][0]["status"] = "candidate"
        cand = doc["threads"][0]["functions"][0]["candidates"][1]
        cand["inquiryRef"] = "RC-B-1"
        code, out = self.run_tool("check", self.write("fm.json", doc), "--rc-dir", "rc")
        self.assertEqual(code, 2)
        self.assertIn("notHolds", out["errors"][0])
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [{"q": 1, "landsOn": "s1", "holds": "holds", "reason": "成立"}]))
        self.assertEqual(self.run_tool("check", self.write("fm.json", doc), "--rc-dir", "rc")[0], 0)

    def test_structure_rules(self):
        doc = fmap()
        fn = doc["threads"][0]["functions"][0]
        fn["candidates"][0]["rejectedBecause"] = ""
        fn["candidates"][1]["status"] = "candidate"
        doc["threads"][0]["functions"].append(copy.deepcopy(doc["threads"][0]["functions"][1]))
        errors = " ".join(self.run_tool("check", self.write("fm.json", doc), "--rc-dir", "rc")[1]["errors"])
        for needle in ("rejectedBecause", "恰有一个", "重复"):
            self.assertIn(needle, errors)

    def test_merge_and_refuse_duplicate_functions(self):
        (self.dir / "threads").mkdir()
        self.write("threads/T-b.json", {"threadId": "T-b", "functions": [{"functionId": "F-b-1"}]})
        self.write("threads/T-a.json", {"threadId": "T-a", "functions": [{"functionId": "F-a-1"}]})
        code, out = self.run_tool("merge", "threads", "--out", "merged.json")
        self.assertEqual(code, 0, out)
        merged = json.loads((self.dir / "merged.json").read_text(encoding="utf-8"))
        self.assertEqual([t["threadId"] for t in merged["threads"]], ["T-a", "T-b"])
        self.write("threads/T-c.json", {"threadId": "T-c", "functions": [{"functionId": "F-a-1"}]})
        code, out = self.run_tool("merge", "threads", "--out", "merged2.json")
        self.assertEqual(code, 2)
        self.assertFalse((self.dir / "merged2.json").exists())

    def test_topics_merge_procedure_and_required_unstated(self):
        doc = fmap()
        code, out = self.run_tool("topics", self.write("fm.json", doc))
        self.assertEqual(code, 0)
        by_entry = {t["entryId"]: t for t in out["topics"]}
        self.assertEqual(sorted(by_entry["L-proc-001"]["candidates"]), ["F-box-1.B", "F-box-2.A"])  # rejected A left out
        self.assertEqual(by_entry["L-proc-001"]["episodes"], [3, "4A"])
        self.assertEqual(by_entry[None]["assertions"], ["required_unstated"])
        self.assertEqual(out["counts"]["topics"], 2)
        code, out = self.run_tool("topics", self.write("fm.json", doc), "--include-rejected")
        self.assertIn("F-box-1.A", {c for t in out["topics"] for c in t["candidates"]})

    def test_defects_build_register_from_dispositions(self):
        open_gap = {"q": 5, "landsOn": "F-box-1.B.s2 仓管凭什么记得", "holds": "notHolds", "reason": "没写", "defectKey": "X-3",
                    "loadBearing": True, "loadBearingBasis": "记录原话说功能靠它", "disposition": None}
        light = {"q": 6, "landsOn": "s3", "holds": "notHolds", "reason": "小事", "loadBearing": False}
        self.write("rc/RC-B-1.json", record("RC-B-1", "F-box-1.B", [LB, open_gap, light]))
        code, out = self.run_tool("defects", "build", "--records", "rc")
        self.assertEqual(code, 0)
        by_id = {d["defectId"]: d for d in out["defects"]}
        self.assertEqual(by_id["X-2"]["disposition"]["to"], "license")
        self.assertEqual(by_id["X-2"]["loadBearingBasis"], ["stated_in_record"])
        self.assertEqual((by_id["X-3"]["disposition"], by_id["X-3"]["loadBearingWhy"]), ("open", "记录原话说功能靠它"))
        self.assertEqual(by_id["RC-B-1#q6"]["disposition"]["to"], "leaves_open")
        self.assertEqual(out["counts"]["loadBearingOpen"], 1)
        code, out = self.run_tool("defects", "build", "--records", "rc", "--out", "register.json")
        register = json.loads((self.dir / "register.json").read_text(encoding="utf-8"))
        self.assertEqual(register["schemaVersion"], "drama-studio/defect-register/v0")


if __name__ == "__main__":
    unittest.main()
