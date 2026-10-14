"""ledger: init/merge/apply/replay/check/diff/knows/view/stats on a synthetic small-town ledger."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/checks/ledger.py")]


def run(*args, cwd=None):
    result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True, cwd=cwd)
    out = result.stdout if result.stdout.strip() else result.stderr
    try:
        return result.returncode, json.loads(out)
    except json.JSONDecodeError:
        return result.returncode, out


def common(eid, kind, title, **fields):
    entry = {"id": eid, "kind": kind, "title": title, "origin": "designed", "status": "asserted", "introducedAt": "pre",
             "realityRef": [], "inquiryRef": [], "dependents": [], "patchCount": 0, "history": []}
    entry.update(fields)
    return entry


def base_entries():
    return [
        common("L-tl-001", "timeline", "老陈去仓库问箱子", when="第3天上午", who="老陈", where="镇仓库", did="去仓库问箱子",
               didNot=None, why="想知道箱子去哪了", knownTo=["老陈"]),
        common("L-obj-001", "object", "木箱在阁楼", object="木箱", holder="王姨", location="王姨家阁楼", howItGotThere="签收",
               state="封着", visibleTo=["王姨"]),
        common("L-kn-001", "knowledge", "王姨知道箱子在阁楼", who="王姨", knows="箱子在阁楼", since="pre", how="自己签收",
               notKnows=["老陈在找箱子"]),
        common("L-money-001", "money", "老陈付的运费", amount="三百元", **{"from": "老陈"}, to="镇快递点", account="现金",
               whoCanMove=["老陈"], trace="收据", procedureRef=None),
        common("L-proc-001", "procedure", "快递拒收后退回", name="快递拒收后退回", realWorldRule="无法投递的退回寄件人",
               nextNecessaryMove=None, realityRef=["K1-tuihui"], usedIn=["F-box-1"]),
        common("L-ag-001", "agenda", "王姨想瞒住箱子", party="王姨", goal="瞒住箱子", means="藏阁楼", constraints="老陈常来",
               nextMove="搬走", validFrom="pre", validTo=None, emptyFields=["validTo"]),
    ]


def new_knowledge(eid, who, knows, since, how="在场（自己做的）"):
    return common(eid, "knowledge", f"{who}知道{knows}", introducedAt="ep3", who=who, knows=knows, since=since, how=how, notKnows=[])


class Workspace:
    def __init__(self, root):
        self.root = Path(root)

    def write(self, name, doc):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def ledger(self, entries=None, name="ledger-ep000.json"):
        return self.write(name, {"schemaVersion": "drama-studio/ledger-entry/v0", "rev": "ep000", "track": "pre",
                                 "entries": base_entries() if entries is None else entries})

    def delta(self, name, episode, writes, track="planned"):
        return self.write(name, {"episode": episode, "track": track, "reads": [], "writes": writes})


def write(entry_id, change, supported="3-1.b1", reason="测试"):
    return {"entryId": entry_id, "change": change, "reason": reason, "supportedBy": supported}


class LedgerCheckRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, entries=None, *extra):
        return run("check", self.ws.ledger(entries), *extra)

    def rule(self, out, name):
        return out["rules"][name]

    def test_clean_ledger_passes_every_rule(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(out["passed"])
        self.assertIn("reproduceCommand", out)
        for name in ("schema-basic", "money-closed", "contested-zero", "refs-exist", "license-has-words"):
            self.assertEqual(self.rule(out, name)["status"], "pass", name)

    def test_schema_basic_timeline_needs_did_or_did_not(self):
        entries = base_entries()
        entries[0]["did"] = None
        code, out = self.check(entries)
        self.assertEqual(code, 2)
        self.assertIn("did 与 didNot", json.dumps(self.rule(out, "schema-basic")["items"], ensure_ascii=False))

    def test_schema_basic_state_subtype(self):
        entries = base_entries()
        entries.append(common("L-tl-st-1", "timeline", "王姨是监护人", subtype="state", stateOf="王姨与阿禾", state="监护人",
                              validFrom="pre", validTo=None, knownTo=["王姨"]))
        code, out = self.check(entries)
        self.assertEqual(self.rule(out, "schema-basic")["status"], "pass", out)
        entries[-1]["stateOf"] = ""
        del entries[-1]["validFrom"]
        code, out = self.check(entries)
        items = json.dumps(self.rule(out, "schema-basic")["items"], ensure_ascii=False)
        self.assertEqual(code, 2)
        self.assertIn("stateOf", items)
        self.assertIn("validFrom", items)

    def test_schema_basic_origin_user_given_modified_allowed(self):
        entries = base_entries()
        entries[1]["origin"] = "user_given_modified"
        self.assertEqual(self.rule(self.check(entries)[1], "schema-basic")["status"], "pass")
        entries[1]["origin"] = "guessed"
        self.assertEqual(self.rule(self.check(entries)[1], "schema-basic")["status"], "fail")

    def test_delta_applies(self):
        good = self.ws.delta("d3.json", 3, [write("new", new_knowledge("L-kn-3", "老陈", "箱子被退回", "ep3 3-1.b1"))])
        code, out = self.check(None, "--delta", good)
        self.assertEqual(self.rule(out, "delta-applies")["status"], "pass", out)
        bad = self.ws.delta("d3b.json", 3, [write("L-missing", {"state": "开了"})])
        code, out = self.check(None, "--delta", bad)
        self.assertEqual(code, 2)
        self.assertIn("L-missing", json.dumps(self.rule(out, "delta-applies")["items"], ensure_ascii=False))

    def test_object_single_chain(self):
        entries = base_entries()
        twin = copy.deepcopy(entries[1])
        twin["id"] = "L-obj-002"
        code, out = self.check(entries + [twin])
        self.assertEqual(self.rule(out, "object-single-chain")["status"], "fail")
        twin["status"] = "retired"
        code, out = self.check(entries + [twin])
        self.assertEqual(self.rule(out, "object-single-chain")["status"], "pass")
        moved = self.ws.delta("d.json", 3, [{"entryId": "L-obj-001", "change": {"holder": "老陈"}, "reason": "拿走"}])
        code, out = self.check(None, "--delta", moved)
        self.assertIn("supportedBy 为空", json.dumps(self.rule(out, "object-single-chain")["items"], ensure_ascii=False))

    def test_object_single_chain_registered_contest_only_reported_pre_select(self):
        entries = base_entries()
        twin = copy.deepcopy(entries[1])
        twin["id"] = "L-obj-002"
        for e, other in ((entries[1], "L-obj-002"), (twin, "L-obj-001")):
            e.update(status="contested", conflictsWith=[other], conflictNotes=[{"with": other, "note": "两种写法", "conflictKind": "source_variant"}])
        code, out = self.check(entries + [twin], "--stage", "pre-select")
        self.assertEqual(self.rule(out, "object-single-chain")["status"], "report")
        self.assertEqual(code, 0)
        code, out = self.check(entries + [twin])
        self.assertEqual(self.rule(out, "object-single-chain")["status"], "fail")

    def test_knowledge_monotonic(self):
        bad = self.ws.delta("d.json", 3, [write("L-kn-001", {"status": "retired"})])
        self.assertEqual(self.rule(self.check(None, "--delta", bad)[1], "knowledge-monotonic")["status"], "fail")
        good = self.ws.delta("d2.json", 3, [write("L-kn-001", {"status": "retired", "event": "forgot"})])
        self.assertEqual(self.rule(self.check(None, "--delta", good)[1], "knowledge-monotonic")["status"], "pass")

    def test_money_closed_empty_fields_register_not_exempt(self):
        # D6-2 decision §5 #6 changed this on purpose: a field listed in emptyFields used to fail money-closed; now it is
        # accounted for, passes and stays listed under registeredEmpty. An empty field not listed still fails.
        entries = base_entries()
        entries[3].update(trace=None, emptyFields=["trace"])
        code, out = self.check(entries)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.rule(out, "money-closed")["status"], "pass")
        self.assertEqual(self.rule(out, "money-closed")["registeredEmpty"], ["L-money-001: trace"])
        self.assertEqual(self.rule(out, "schema-basic")["status"], "pass")
        entries[3].update(emptyFields=[])
        code, out = self.check(entries)
        self.assertEqual(code, 2)
        self.assertEqual(self.rule(out, "money-closed")["status"], "fail")
        code, out = self.check(entries, "--stage", "pre-select")
        self.assertEqual(self.rule(out, "money-closed")["status"], "report")
        entries[3].update(trace="no_trace", traceReason="现金没有凭据", emptyFields=[])
        self.assertEqual(self.rule(self.check(entries)[1], "money-closed")["status"], "pass")
        entries[3].update(traceReason="")
        self.assertEqual(self.rule(self.check(entries)[1], "money-closed")["status"], "fail")

    def test_planned_vs_actual_lists_differences_only(self):
        p = self.ws.delta("p.json", 3, [write("L-obj-001", {"state": "开了"})])
        a = self.ws.delta("a.json", 3, [write("L-obj-001", {"state": "还封着"})], track="actual")
        code, out = self.check(None, "--delta", p, "--delta", a)
        r = self.rule(out, "planned-vs-actual")
        self.assertEqual(r["status"], "report")
        self.assertIn("L-obj-001", r["items"][0]["diff"])
        same = self.ws.delta("a2.json", 3, [write("L-obj-001", {"state": "开了"})], track="actual")
        self.assertEqual(self.rule(self.check(None, "--delta", p, "--delta", same)[1], "planned-vs-actual")["items"], [])

    def test_unverified_count_reports(self):
        entries = base_entries()
        entries[4].update(status="unverified", notFound=["没查到退回时限"], dependents=[{"functionId": "F-box-1", "episodes": [3]}])
        code, out = self.check(entries)
        r = self.rule(out, "unverified-count")
        self.assertEqual((r["status"], r["items"][0]["id"]), ("report", "L-proc-001"))
        self.assertEqual(code, 0)

    def test_patch_cap(self):
        entries = base_entries()
        entries[1]["patchCount"] = 2
        d = self.ws.delta("d.json", 3, [write("L-obj-001", {"state": "开了"})])
        self.assertEqual(self.rule(self.check(entries, "--delta", d)[1], "patch-cap")["status"], "fail")
        entries[1]["patchCount"] = None
        self.assertEqual(self.rule(self.check(entries, "--delta", d)[1], "patch-cap")["status"], "pass")

    def contested_pair(self):
        entries = base_entries()
        twin = copy.deepcopy(entries[0])
        twin.update(id="L-tl-002", did="没去仓库")
        for e, other in ((entries[0], "L-tl-002"), (twin, "L-tl-001")):
            e.update(status="contested", conflictsWith=[other], conflictNotes=[{"with": other, "note": "去没去", "conflictKind": "world"}])
        return entries + [twin]

    def test_contested_zero(self):
        code, out = self.check(self.contested_pair())
        r = self.rule(out, "contested-zero")
        self.assertEqual((code, r["status"], r["items"]["countByConflictKind"]), (2, "fail", {"world": 2}))
        code, out = self.check(self.contested_pair(), "--stage", "pre-select")
        self.assertEqual((code, self.rule(out, "contested-zero")["status"]), (0, "report"))

    def test_contested_zero_scope_exemption_needs_registered_decision(self):
        entries = self.contested_pair()
        entries[0].update(conflictsOutOfScope=["L-tl-002"], decisionRef="DQ-1")
        scope = self.ws.write("scope.json", {"ledgerEntries": [{"id": "L-tl-001"}]})
        queue = self.ws.write("dq.json", {"entries": [{"id": "DQ-1", "default": "keep"}]})
        code, out = self.check(entries, "--scope", scope, "--decisions", queue)
        r = self.rule(out, "contested-zero")
        self.assertEqual(r["status"], "report", out)
        self.assertEqual(r["items"]["exemptConflictsOutOfScopeIds"], ["L-tl-001"])
        code, out = self.check(entries, "--scope", scope, "--decisions", self.ws.write("dq2.json", {"entries": []}))
        self.assertEqual(self.rule(out, "contested-zero")["status"], "fail")

    def fmap(self, dep_entry, status="selected"):
        return self.ws.write("fm.json", {"threads": [{"threadId": "T-box", "functions": [{"functionId": "F-box-1", "status": "selected", "candidates": [
            {"candidateId": "F-box-1.A", "status": status, "steps": [{"stepId": "s1"}],
             "ledgerDeps": [{"depId": "d1", "kind": "timeline", "claim": "他去过仓库", "entryId": dep_entry}]}]}]}]})

    def test_why_missing(self):
        entries = base_entries()
        entries[0].update(why=None, whyMissing=True)
        code, out = self.check(entries, "--function-map", self.fmap("L-tl-001"))
        self.assertEqual(self.rule(out, "why-missing")["status"], "fail")
        entries[0]["whyMissingImpact"] = "选定实现不靠他为什么去"
        code, out = self.check(entries, "--function-map", self.fmap("L-tl-001"))
        self.assertEqual(self.rule(out, "why-missing")["status"], "report")

    def test_refs_exist(self):
        entries = base_entries()
        entries[0]["conflictsWith"] = ["L-obj-001"]
        code, out = self.check(entries)
        self.assertIn("没有反向列出", json.dumps(self.rule(out, "refs-exist")["items"], ensure_ascii=False))
        entries[1]["conflictsWith"] = ["L-tl-001"]
        self.assertEqual(self.rule(self.check(entries)[1], "refs-exist")["status"], "pass")
        cards = self.root_cards()
        code, out = self.check(None, "--cards", cards)
        self.assertEqual(self.rule(out, "refs-exist")["status"], "pass", out)
        entries = base_entries()
        entries[4]["realityRef"] = ["K1-none"]
        self.assertEqual(self.rule(self.check(entries, "--cards", cards)[1], "refs-exist")["status"], "fail")

    def root_cards(self):
        cards = Path(self.tmp.name) / "cards"
        cards.mkdir()
        (cards / "K1-tuihui@r1.json").write_text(json.dumps({"cardId": "K1-tuihui"}), encoding="utf-8")
        return cards

    def test_refs_exist_dependents_function_ids(self):
        entries = base_entries()
        entries[0]["dependents"] = [{"functionId": "F-box-9", "episodes": [3]}]
        code, out = self.check(entries, "--function-map", self.fmap("L-tl-001"))
        self.assertEqual(self.rule(out, "refs-exist")["status"], "fail")
        entries[0]["dependents"] = [{"functionId": "F-box-1", "episodes": [3]}, "F-box-1"]
        self.assertEqual(self.rule(self.check(entries, "--function-map", self.fmap("L-tl-001"))[1], "refs-exist")["status"], "pass")

    def test_license_has_words(self):
        entries = base_entries()
        entries[4]["status"] = "accepted_license"
        self.assertEqual(self.rule(self.check(entries)[1], "license-has-words")["status"], "fail")
        entries[4]["humanWords"] = "就这么写，观众不会较真"
        self.assertEqual(self.rule(self.check(entries)[1], "license-has-words")["status"], "pass")

    def test_procedure_open_reports(self):
        entries = base_entries()
        entries[4]["nextNecessaryMove"] = {"mandated": "通知寄件人", "customary": None}
        r = self.rule(self.check(entries)[1], "procedure-open")
        self.assertEqual((r["status"], r["items"]), ("report", ["L-proc-001"]))
        entries[4]["status"] = "verified"
        self.assertEqual(self.rule(self.check(entries)[1], "procedure-open")["items"], [])

    def test_selected_deps_not_contested(self):
        entries = self.contested_pair()
        fm = self.ws.write("fm2.json", {"threads": [{"threadId": "T", "functions": [
            {"functionId": "F-1", "candidates": [{"candidateId": "F-1.A", "status": "selected", "ledgerDeps": [{"entryId": "L-tl-001"}]}]},
            {"functionId": "F-2", "candidates": [{"candidateId": "F-2.A", "status": "selected", "ledgerDeps": [{"entryId": "L-tl-002"}]}]}]}]})
        self.assertEqual(self.rule(self.check(entries, "--function-map", fm, "--stage", "pre-select")[1], "selected-deps-not-contested")["status"], "fail")
        self.assertEqual(self.rule(self.check(entries, "--function-map", self.fmap("L-tl-001"), "--stage", "pre-select")[1],
                                   "selected-deps-not-contested")["status"], "pass")

    def test_not_asked_not_verified(self):
        entries = base_entries()
        entries[4].update(notAsked=True, status="verified")
        self.assertEqual(self.rule(self.check(entries)[1], "not-asked-not-verified")["status"], "fail")
        entries[4]["status"] = "asserted"
        self.assertEqual(self.rule(self.check(entries)[1], "not-asked-not-verified")["status"], "pass")

    def test_retired_user_given_justified(self):
        entries = base_entries()
        entries[1].update(status="retired", origin="user_given")
        self.assertEqual(self.rule(self.check(entries)[1], "retired-user-given-justified")["status"], "fail")
        entries[1]["retiredBy"] = "layer_choice"
        self.assertEqual(self.rule(self.check(entries)[1], "retired-user-given-justified")["status"], "pass")
        entries[1]["retiredBy"] = "whim"
        self.assertEqual(self.rule(self.check(entries)[1], "retired-user-given-justified")["status"], "fail")

    def test_scope_moves_out_of_scope_items(self):
        entries = base_entries()
        entries[4]["status"] = "accepted_license"
        scope = self.ws.write("scope.json", ["L-tl-001"])
        code, out = self.check(entries, "--scope", scope)
        r = self.rule(out, "license-has-words")
        self.assertEqual((r["status"], r["outOfScopeItems"]), ("pass", ["L-proc-001"]))

    def test_several_deltas_with_int_and_letter_episodes_do_not_crash(self):
        d5 = self.ws.delta("d5.json", 5, [write("new", new_knowledge("L-kn-5", "老陈", "箱子在阁楼", "ep5 5-1.b1"), "5-1.b1")])
        d6 = self.ws.delta("d6A.json", "6A", [write("L-kn-5", {"how": "王姨说漏嘴"}, "6A-1.b1")])
        a6 = self.ws.delta("a6A.json", "6A", [write("L-kn-5", {"how": "自己看见"}, "6A-1.b1")], track="actual")
        code, out = self.check(None, "--delta", d6, "--delta", d5, "--delta", a6)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["deltas"], ["ep6A.planned", "ep5.planned", "ep6A.actual"])
        self.assertEqual(out["rules"]["planned-vs-actual"]["items"][0]["episode"], "6A")

    def test_missing_ledger_is_input_error(self):
        code, out = run("check", Path(self.tmp.name) / "nope.json")
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])


class LedgerReplayKnows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)
        self.base = self.ws.ledger()
        self.d5 = self.ws.delta("d5.json", 5, [write("new", new_knowledge("L-kn-5", "老陈", "箱子在阁楼", "ep5 5-1.b2", how="王姨说漏嘴"), "5-1.b2")])
        self.d6a = self.ws.delta("d6A.json", "6A", [write("L-obj-001", {"holder": "老陈", "location": "老陈家"}, "6A-1.b1")])
        self.d6b = self.ws.delta("d6B.json", "6B", [write("L-obj-001", {"state": "开了"}, "6B-1.b1")])

    def tearDown(self):
        self.tmp.cleanup()

    def test_replay_orders_episodes_and_matches_apply_chain(self):
        out_path = Path(self.tmp.name) / "replay.json"
        code, out = run("replay", self.base, "--delta", self.d6b, "--delta", self.d5, "--delta", self.d6a, "--at", "6B", "--out", out_path)
        self.assertEqual(code, 0, out)
        self.assertEqual([s["episode"] for s in out["steps"]], [5, "6A", "6B"])
        chain = Path(self.tmp.name) / "chain.json"
        run("apply", self.base, "--delta", self.d5, "--delta", self.d6a, "--delta", self.d6b, "--out", chain)
        replayed = json.loads(out_path.read_text(encoding="utf-8"))["entries"]
        applied = json.loads(chain.read_text(encoding="utf-8"))["entries"]
        self.assertEqual(replayed, applied)

    def test_replay_stops_at_episode(self):
        code, out = run("replay", self.base, "--delta", self.d6b, "--delta", self.d5, "--delta", self.d6a, "--at", "6A")
        self.assertEqual([s["episode"] for s in out["steps"]], [5, "6A"])
        self.assertEqual(out["notReplayed"], ["6B"])

    def test_replay_actual_track_lists_planned_fallback(self):
        a5 = self.ws.delta("a5.json", 5, [write("new", new_knowledge("L-kn-5", "老陈", "箱子在阁楼", "ep5 5-1.b3", how="自己看见"), "5-1.b3")],
                           track="actual")
        code, out = run("replay", self.base, "--delta", self.d5, "--delta", a5, "--delta", self.d6a, "--at", "6A", "--track", "actual")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["plannedFallback"], ["6A"])
        self.assertEqual([s["track"] for s in out["steps"]], ["actual", "planned"])

    def test_replay_md_exports_entry_state(self):
        code, out = run("replay", self.base, "--delta", self.d5, "--at", "5", "--md")
        self.assertEqual(code, 0)
        self.assertIn("# 入口状态：ledger@ep5.planned", out)
        self.assertIn("## 谁知道什么", out)
        self.assertIn("王姨说漏嘴", out)

    def test_replay_two_deltas_same_episode_track_is_input_error(self):
        code, out = run("replay", self.base, "--delta", self.d5, "--delta", self.d5, "--at", "5")
        self.assertEqual(code, 1)

    def test_knows_at_episode_filters_later_since(self):
        p6 = Path(self.tmp.name) / "l6.json"
        later = self.ws.delta("d7.json", 7, [write("new", new_knowledge("L-kn-7", "老陈", "签收人是王姨", "ep7 7-1.b1"), "7-1.b1")])
        run("apply", self.base, "--delta", self.d5, "--delta", later, "--out", p6)
        code, out = run("knows", p6, "--who", "老陈", "--at", "6A")
        ids = [k["entryId"] for k in out["knows"]]
        self.assertIn("L-kn-5", ids)
        self.assertNotIn("L-kn-7", ids)
        self.assertIn("L-tl-001", ids)  # derived from timeline knownTo

    def plan(self, writes):
        return self.ws.write("plan.json", {"episode": "6A", "events": {"scenes": [
            {"sceneId": "6A-1", "present": ["老陈", "王姨"], "beats": [{"beatId": "6A-1.b1"}, {"beatId": "6A-1.b2"}]},
            {"sceneId": "6A-2", "present": ["老陈"], "beats": [{"beatId": "6A-2.b1"}]}]},
            "ledgerDelta": {"episode": "6A", "track": "planned", "reads": [], "writes": writes}})

    def test_knows_by_scene_applies_scene_writes_before_snapshot(self):
        # A write that only appends beat timing to an older entry must be used in its own scene;
        # a write that only changes state must not hide the entry from people who already saw it.
        entries = base_entries()
        entries[1]["visibleTo"] = ["王姨", "老陈"]
        base = self.ws.ledger(entries, name="l.json")
        plan = self.plan([
            write("L-tl-001", {"knownToSince": {"老陈": "6A-1.b2"}}, "6A-1.b2"),
            write("L-obj-001", {"state": "开了"}, "6A-1.b1"),
            write("new", new_knowledge("L-kn-6", "老陈", "签收人是王姨", {"签收": "6A-1.b1", "签收人": "6A-2.b1"}, how="王姨说"), "6A-1.b1"),
        ])
        code, out = run("knows", base, "--episode-plan", plan)
        self.assertEqual(code, 0, out)
        s1, s2 = out["scenes"]
        ids1 = [k["entryId"] for k in s1["byPerson"]["老陈"]["knows"]]
        self.assertNotIn("L-tl-001", ids1)  # timed inside this scene: not known before it
        self.assertIn("L-obj-001", ids1)  # state-only write does not hide an earlier sighting
        self.assertNotIn("L-kn-6", ids1)
        parts2 = [k.get("part") for k in s2["byPerson"]["老陈"]["knows"] if k["entryId"] == "L-kn-6"]
        self.assertEqual(parts2, ["签收"])  # nested since judged part by part
        within = {w["beatId"]: w["newlyKnown"] for w in s1["withinScene"]}
        self.assertIn({"entryId": "L-tl-001", "who": "老陈"}, within["6A-1.b2"])
        self.assertIn({"entryId": "L-kn-6", "who": "老陈", "aspect": "签收"}, within["6A-1.b1"])

    def test_knows_pre_value_with_beat_in_note_is_before_episode(self):
        entries = base_entries()
        entries.append(new_knowledge("L-kn-9", "老陈", "去年的登记", {"旧登记": "pre（去年十一月；本集 6A-1.b2 翻出）"}, how="手里的登记"))
        code, out = run("knows", self.ws.ledger(entries, name="l.json"), "--episode-plan", self.plan([]))
        s1 = out["scenes"][0]
        self.assertIn("L-kn-9", [k["entryId"] for k in s1["byPerson"]["老陈"]["knows"]])
        self.assertNotIn("L-kn-9", [i["entryId"] for w in s1["withinScene"] for i in w["newlyKnown"]])

    def test_knows_only_leading_beat_counts(self):
        entries = base_entries()
        entries.append(new_knowledge("L-kn-9", "老陈", "签收人", "ep6A 6A-2.b1（注：6A-1.b1 只是提了一句）", how="王姨说"))
        code, out = run("knows", self.ws.ledger(entries, name="l.json"), "--episode-plan", self.plan([]))
        s1, s2 = out["scenes"]
        self.assertNotIn("L-kn-9", [k["entryId"] for k in s1["byPerson"]["老陈"]["knows"]])
        self.assertEqual(s2["withinScene"], [{"beatId": "6A-2.b1", "newlyKnown": [{"entryId": "L-kn-9", "who": "老陈"}]}])

    def test_knows_ignores_retired_entries(self):
        entries = base_entries()
        entries[2]["status"] = "retired"
        code, out = run("knows", self.ws.ledger(entries, name="l.json"), "--who", "王姨")
        self.assertNotIn("L-kn-001", [k["entryId"] for k in out["knows"]])

    def test_knows_episode_plan_excludes_who(self):
        code, out = run("knows", self.base, "--episode-plan", self.plan([]), "--who", "老陈")
        self.assertEqual(code, 1)


class LedgerMergeAndViews(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_writes_empty_ledger_and_never_overwrites(self):
        target = Path(self.tmp.name) / "ledger-ep000.json"
        code, out = run("init", "--out", target)
        self.assertEqual((code, json.loads(target.read_text(encoding="utf-8"))["entries"]), (0, []))
        code, out = run("init", "--out", target)
        self.assertEqual(code, 1)

    def test_merge_amendments_across_parts_and_same_procedure(self):
        a, b = base_entries()[:3], base_entries()[3:]
        b[1]["defectKey"] = "退回没写"
        b[1]["nextNecessaryMove"] = "通知寄件人"
        twin = copy.deepcopy(b[1])
        twin.update(id="L-proc-002", status="verified")
        twin.pop("defectKey")
        pa = self.ws.write("part-a.json", {"part": "a", "rev": "ep000", "entries": a,
                                           "amendments": [{"entryId": "L-proc-001", "add": {"inquiryRefAdd": ["RC-1"], "statusChange": {"to": "unverified", "note": "没查到"}}}]})
        pb = self.ws.write("part-b.json", {"part": "b", "entries": b + [twin]})
        out_path = Path(self.tmp.name) / "merged.json"
        code, out = run("merge", pa, pb, "--out", out_path, "--same-procedure", "L-proc-001,L-proc-002")
        self.assertEqual(code, 0, out)
        merged = {e["id"]: e for e in json.loads(out_path.read_text(encoding="utf-8"))["entries"]}
        proc = merged["L-proc-001"]
        self.assertEqual((proc["status"], proc["inquiryRef"], proc["defectKeys"]), ("unverified", ["RC-1"], ["退回没写"]))
        self.assertEqual(proc["nextNecessaryMove"]["legacyText"], "通知寄件人")
        self.assertEqual((proc["sameProcedureAs"], merged["L-proc-002"]["sameProcedureAs"]), (["L-proc-002"], ["L-proc-001"]))
        self.assertEqual(out["statusMismatch"], [{"pair": ["L-proc-001", "L-proc-002"], "statusA": "unverified", "statusB": "verified"}])

    def test_merge_refuses_duplicate_ids_and_reports_type_conflicts(self):
        pa = self.ws.write("a.json", {"entries": base_entries()[:2]})
        pb = self.ws.write("b.json", {"entries": base_entries()[1:3]})
        code, out = run("merge", pa, pb, "--out", Path(self.tmp.name) / "m.json")
        self.assertEqual(code, 2)
        self.assertFalse((Path(self.tmp.name) / "m.json").exists())
        entries = base_entries()
        entries[4]["realityRef"] = "K1-tuihui"  # string where the other part wrote a list
        extra = common("L-proc-009", "procedure", "另一程序", name="x", realWorldRule="y", nextNecessaryMove=None,
                       realityRef=["K1-x"], usedIn=["F-box-1"])
        code, out = run("merge", self.ws.write("c.json", {"entries": entries}), self.ws.write("d.json", {"entries": [extra]}),
                        "--out", Path(self.tmp.name) / "m2.json")
        self.assertEqual(code, 0)
        self.assertIn("realityRef", [c["field"] for c in out["fieldTypeConflicts"]])

    def test_diff_view_stats(self):
        a = self.ws.ledger()
        entries = base_entries()
        entries[1]["holder"] = "老陈"
        b = self.ws.ledger(entries + [common("L-tl-st-1", "timeline", "监护", subtype="state", stateOf="王姨", state="监护人",
                                             validFrom="pre", validTo=None, knownTo=[])], name="b.json")
        code, out = run("diff", a, b)
        self.assertEqual((out["added"], list(out["changed"])), (["L-tl-st-1"], ["L-obj-001"]))
        code, out = run("view", b, "--blank-period")
        self.assertEqual(code, 0)
        self.assertIn("王姨：监护人", out["markdown"])
        code, out = run("stats", b)
        self.assertEqual((out["entriesTotal"], out["stateSubtypeCount"]), (7, 1))


if __name__ == "__main__":
    unittest.main()
