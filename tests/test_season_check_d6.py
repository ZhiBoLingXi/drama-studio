"""season-check D6-1: the outline-layer and dialogue-layer rule sets beside the legacy ones, chosen per project.

Synthetic fixtures only: the compliant legacy season and outlines of test_season_check, plus the D6 records built from
schemas/examples/ (小镇、老陈的编造例子). Each new rule has one breaking change that reports that rule alone.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_season_check import Outlines, Season, run

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def put(root, name, doc):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


class OutlineLayer:
    """planning/ records for outlines 4-5: season plan, two episode plans, ledger, decisions, function map, plan retells."""

    def __init__(self, root: Path):
        self.root = root
        season = example("season-plan")
        season["episodes"] = [dict(season["episodes"][0], episode=n) for n in (4, 5)]
        self.season = season
        self.plans = {}
        for n in (4, 5):
            plan = example("episode-plan")
            plan["episode"] = n
            self.plans[n] = plan
        self.ledger = example("ledger-entry")
        self.decisions = example("decision-queue")
        self.function_map = example("function-map")
        self.retells = {}
        for n in (4, 5):
            retell = example("retell-record")
            retell["target"] = {"kind": "episode_plan_events", "episode": n, "file": f"planning/episode-plans/ep-{n:03d}.json"}
            self.retells[n] = retell

    def write(self, season=True):
        if season:
            put(self.root, "planning/season-plan.json", self.season)
        for n, plan in self.plans.items():
            put(self.root, f"planning/episode-plans/ep-{n:03d}.json", plan)
        put(self.root, "planning/ledger/ledger-ep000.json", self.ledger)
        put(self.root, "planning/decisions.json", self.decisions)
        put(self.root, "planning/function-map.json", self.function_map)
        for n, retell in self.retells.items():
            put(self.root, f".drama/checks/retell-plan-{n:03d}.json", retell)


class OutlineLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        Outlines(Season(self.root))
        self.layer = OutlineLayer(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, season=True):
        self.layer.write(season)
        code, out = run("season-check", self.root, "--outline", "4-5")
        return code, out, {f["rule"] for f in out["failures"]}

    def test_without_a_season_plan_the_legacy_rules_run(self):
        code, out, rules = self.check(season=False)
        self.assertEqual((code, rules), (0, set()))
        self.assertNotIn("ruleSet", out)
        self.assertNotIn("episodeRuleSet", out)

    def test_compliant_outline_layer_passes(self):
        code, out, rules = self.check()
        self.assertEqual((code, out["ruleSet"], rules), (0, "outline-layer", set()), out["failures"])
        self.assertNotIn("episodeRuleSet", out)
        self.assertEqual(out["perOutline"]["4"]["episodePlans"], ["planning/episode-plans/ep-004.json"])
        self.assertEqual(out["perOutline"]["4"]["unverifiedRealityRefs"], 0)

    def test_legacy_outline_rules_still_run_in_the_outline_layer(self):
        (self.root / ".drama/reviews/outline-review.json").unlink()
        code, out, rules = self.check()
        self.assertEqual((code, rules), (2, {"outline-review"}))

    def test_episode_not_in_the_season_plan(self):
        self.layer.season["episodes"] = self.layer.season["episodes"][:1]
        self.assertEqual(self.check()[2], {"outline-season-assigned"})

    def test_missing_episode_plan(self):
        del self.layer.plans[5]
        code, out, rules = self.check()
        self.assertEqual(rules, {"outline-ledger-delta"})
        self.assertEqual(out["failedOutlines"], [5])

    def test_delta_write_without_scene_support(self):
        self.layer.plans[5]["ledgerDelta"]["writes"][0]["supportedBy"] = "9-9.b9"
        self.assertEqual(self.check()[2], {"outline-ledger-delta"})

    def test_capacity_must_fit_or_name_a_proposal_with_a_default(self):
        self.layer.plans[4]["capacity"]["status"] = "exceeds"
        self.assertEqual(self.check()[2], {"outline-capacity"})
        self.layer.plans[4]["capacity"]["status"] = "proposal:D-404"
        self.assertEqual(self.check()[2], {"outline-capacity"})
        self.layer.plans[4]["capacity"]["status"] = "proposal:D-001"
        self.assertEqual(self.check()[2], set())

    def test_reality_refs_exist_and_are_not_contested(self):
        self.layer.plans[4]["realityRefs"] = ["L-proc-404"]
        self.assertEqual(self.check()[2], {"outline-reality-refs"})
        self.layer.plans[4]["realityRefs"] = ["L-tl-001"]
        self.assertEqual(self.check()[2], {"outline-reality-refs"})

    def test_unverified_reality_refs_are_counted_not_failed(self):
        self.layer.ledger["entries"][0]["status"] = "unverified"
        code, out, rules = self.check()
        self.assertEqual((rules, out["perOutline"]["5"]["unverifiedRealityRefs"]), (set(), 1))

    def test_plan_needs_a_cold_retell_of_its_events(self):
        del self.layer.retells[5]
        self.assertEqual(self.check()[2], {"outline-retell"})
        self.layer.retells[5] = copy.deepcopy(self.layer.retells[4])
        self.layer.retells[5]["target"]["kind"] = "episode_text"
        self.layer.retells[5]["target"]["episode"] = 5
        self.assertEqual(self.check()[2], {"outline-retell"})

    def test_pending_decision_needs_a_default(self):
        self.layer.decisions["entries"][0]["default"] = None
        self.assertEqual(self.check()[2], {"outline-decision-default"})

    def test_patch_cap(self):
        self.layer.function_map["threads"][0]["functions"][0]["candidates"][0]["patchCount"] = 2
        self.assertEqual(self.check()[2], set())
        self.layer.function_map["threads"][0]["functions"][0]["candidates"][0]["patchCount"] = 3
        self.assertEqual(self.check()[2], {"outline-patch-cap"})
        self.layer.function_map["threads"][0]["functions"][0]["candidates"][1]["patchCount"] = 5  # rejected: history only
        self.layer.function_map["threads"][0]["functions"][0]["candidates"][0]["patchCount"] = 0
        self.assertEqual(self.check()[2], set())


TEXT = "场1-1 冰面 日\n大凤提他后领。\n大凤：走踩实的道儿。\n"


class DialogueLayer:
    """Records for written episodes 2-3: dialogue plans, target, plan-text map, cold retell, situation checks, hit lists."""

    def __init__(self, root: Path):
        self.root = root
        self.target = example("dialogue-target")
        self.plans, self.records = {}, {}
        for n in (2, 3):
            plan = example("dialogue-plan")
            plan["episode"] = n
            self.plans[n] = plan
            text = f"runs/b1/ep-{n:03d}.d.md"
            ptc = example("plan-text-consistency")
            ptc.update(plan=f"planning/dialogue-plans/ep-{n:03d}.json", text=text)
            retell = example("retell-record")
            retell["target"] = {"kind": "episode_text", "episode": n, "file": text}
            check = {"schemaVersion": "drama-studio/answers/v0", "checkId": f"DC-{n}", "target": {"kind": "episode_text", "episode": n},
                     "questionsVersion": "dialogue-check-questions@v1", "answers": [], "outcome": "pass"}
            tool = "python3 -B /skill/scripts/drama_tools.py"
            self.records[n] = {
                f"plan-text-{n:03d}.json": ptc, f"retell-ep-{n:03d}.json": retell, f"situation-ep-{n:03d}-a.json": check,
                f"dup8-ep-{n:03d}.json": {"k": 8, "hits": [], "reproduceCommand": f"{tool} dup-check --list-hits --k 8 --new {text}"},
                f"dup13-ep-{n:03d}.json": {"k": 13, "hits": [], "reproduceCommand": f"{tool} dup-check --list-hits --k 13 --new {text}"},
                f"genre-ep-{n:03d}.json": {"hitCount": 0, "hits": [], "reproduceCommand": f"{tool} corpus lexicon {text} --project-genre 现实"},
            }

    def write(self):
        put(self.root, "planning/dialogue-target.json", self.target)
        for n, plan in self.plans.items():
            put(self.root, f"planning/dialogue-plans/ep-{n:03d}.json", plan)
        for records in self.records.values():
            for name, doc in records.items():
                put(self.root, f".drama/checks/{name}", doc)


class DialogueLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.season = Season(self.root, voice=False, dialogue_read=False)
        self.layer = DialogueLayer(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, write=True):
        if write:
            self.layer.write()
        code, out = run("season-check", self.root, "--episodes", "2-3")
        return code, out, {f["rule"] for f in out["failures"]}

    def test_without_dialogue_plans_the_legacy_dialogue_rules_run(self):
        # D6-3 decision §2 changed this on purpose: the three old rules ran by default; now only with --legacy-dialogue
        code, out = run("season-check", self.root, "--episodes", "2-3", "--legacy-dialogue")
        rules = {f["rule"] for f in out["failures"]}
        self.assertEqual(rules, {"voice-card", "dialogue-read"})
        self.assertNotIn("episodeRuleSet", out)

    def test_compliant_dialogue_layer_passes_and_drops_the_three_old_rules(self):
        code, out, rules = self.check()
        self.assertEqual((code, out["episodeRuleSet"], rules), (0, "dialogue-layer", set()), out["failures"])
        self.assertNotIn("ruleSet", out)
        self.assertEqual(out["perEpisode"]["3"]["dialoguePlans"], ["planning/dialogue-plans/ep-003.json"])
        self.assertIn("constraint-origin", {w["rule"] for w in out["warnings"]})

    def test_missing_or_invalid_dialogue_plan(self):
        del self.layer.plans[3]
        code, out, rules = self.check()
        self.assertEqual((rules, out["failedEpisodes"]), ({"dialogue-plan"}, [3]))

    def test_dialogue_plan_must_pass_contract_check(self):
        del self.layer.plans[3]["scenes"]
        self.assertEqual(self.check()[2], {"dialogue-plan"})

    def test_target_ref(self):
        self.layer.plans[3]["basedOn"] = {"episodePlan": "episode-plan-003"}
        self.assertEqual(self.check()[2], {"target-ref"})
        self.layer.plans[3]["basedOn"]["target"] = "other-target@v1"
        self.assertEqual(self.check()[2], {"target-ref"})

    def drop(self, prefix):
        del self.layer.records[3][next(name for name in self.layer.records[3] if name.startswith(prefix))]

    def test_plan_text_align(self):
        self.drop("plan-text")
        self.assertEqual(self.check()[2], {"plan-text-align"})

    def test_cold_retell(self):
        self.drop("retell")
        self.assertEqual(self.check()[2], {"cold-retell"})

    def test_situation_check(self):
        self.drop("situation")
        self.assertEqual(self.check()[2], {"situation-check"})

    def test_two_situation_checks_need_a_consistency_record(self):
        second = dict(self.layer.records[3]["situation-ep-003-a.json"], checkId="DC-3b")
        self.layer.records[3]["situation-ep-003-b.json"] = second
        self.assertEqual(self.check()[2], {"consistency-record"})
        self.layer.records[3]["consistency-ep-003.json"] = {
            "counts": {}, "reproduceCommand": "python3 -B /skill/scripts/drama_tools.py answers-consistency a.json b.json"}
        self.assertEqual(self.check()[2], set())

    def test_dup_two_tier(self):
        self.drop("dup13")
        self.assertEqual(self.check()[2], {"dup-two-tier"})

    def test_genre_lexicon(self):
        self.drop("genre")
        self.assertEqual(self.check()[2], {"genre-lexicon"})

    def test_fixlist_no_lines(self):
        fixlist = {"schema": "revision-list/v0-pilot", "target": {"episode": 3}, "items": [{"issue": "第 1 场收尾太快", "cites": ["T1"]}]}
        self.layer.records[3]["revision-list-ep-003.json"] = fixlist
        self.assertEqual(self.check()[2], set())
        # D6-3 walkthrough #8 changed this on purpose: with the episode's cast on record (the dialogue plan's speakers, here
        # 老陈 and 仓管) only a cast member's name opens a dialogue line; the fixture's 大凤 is not in that plan
        fixlist["items"].append({"issue": "改成这句", "replacement": "老陈：别回头，跟紧了。"})
        self.assertEqual(self.check()[2], {"fixlist-no-lines"})

    def task(self, constraints):
        doc = {"schemaVersion": "drama-studio/task/v0", "taskId": "c5-ep3", "layer": "C5b", "constraints": constraints}
        put(self.root, ".drama/tasks/c5-ep3.json", doc)

    def test_constraint_origin(self):
        self.task([{"text": "按台词目标约定 C2 处理称呼", "origin": "orchestrator", "cite": "town-dialogue-target@v0.1#C2"}])
        code, out, rules = self.check()
        self.assertEqual(rules, set())
        self.assertNotIn("3", [w["scope"][1:-1] for w in out["warnings"] if w["rule"] == "constraint-origin"])
        self.task([{"text": "按台词目标约定 C2 处理称呼", "origin": "orchestrator", "cite": None}])
        self.assertEqual(self.check()[2], {"constraint-origin"})

    def test_no_numeric_dialogue_constraint(self):
        self.task([{"text": "每句不超过十个字", "origin": "user"}])
        self.assertEqual(self.check()[2], {"no-numeric-dialogue-constraint"})

    def test_retell_after_revise(self):
        s = self.season
        s.handoff("C6", "c6-cold-3", [("project_facts", s.final(3))], [], role="cold_reader")
        s.handoff("C5", "c5-ep3-fix", [("project_facts", s.final(3))], [s.ref(s.final(3))], role="dialogue_author")
        self.assertEqual(self.check()[2], {"retell-after-revise"})
        s.handoff("C6", "c6-cold-3b", [("project_facts", s.final(3))], [], role="cold_reader")
        self.assertEqual(self.check()[2], set())


if __name__ == "__main__":
    unittest.main()
