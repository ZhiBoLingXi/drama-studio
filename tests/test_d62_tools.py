"""D6-2 tools: init-project's planning/ layout, context-pack's planning/ local files and C4 author gate, and the
constraint blocklist on tasks. One passing and one failing case per S rule; synthetic fixtures from schemas/examples/."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
EXAMPLES = ROOT / "skills/drama-studio/schemas/examples"
BLOCKLIST = ROOT / "skills/drama-studio/schemas/data/constraint-blocklist.json"


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args):
    run = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    return run.returncode, json.loads(run.stdout or run.stderr) if (run.stdout or run.stderr).lstrip().startswith("{") else run.stdout


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()


class InitProjectTests(Temp):
    def test_new_project_gets_the_outline_layer_folders_empty(self):
        project = self.base / "new"
        code, _ = tool("init-project", project, "--title", "新剧")
        self.assertEqual(code, 0)
        for folder in ("planning", "planning/ledger", "planning/episodes"):
            with self.subTest(folder=folder):
                self.assertTrue((project / folder).is_dir())
        self.assertEqual(list((project / "planning/ledger").iterdir()) + list((project / "planning/episodes").iterdir()), [])

    def test_status_reads_new_and_old_layouts_alike(self):
        new = self.base / "new"
        tool("init-project", new, "--title", "新剧")
        old = self.base / "old"
        tool("init-project", old, "--title", "旧剧")
        for folder in ("planning/ledger", "planning/episodes"):
            (old / folder).rmdir()  # a 0.3.6-era project: planning/ without the D6-2 folders
        results = []
        for project in (new, old):
            code, out = tool("status", project, "--json")
            with self.subTest(project=project.name):
                self.assertEqual(code, 0, out)
            out.pop("project", None)
            results.append(out)
        self.assertEqual(results[0], results[1])


class PackCase(Temp):
    def setUp(self):
        super().setUp()
        self.project = self.base / "proj"
        (self.project / ".drama").mkdir(parents=True)
        self.task_doc = example("task")

    def write(self, name, doc):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def pack(self, role, names, partition="current_plan"):
        task = self.base / "task.json"
        task.write_text(json.dumps(self.task_doc, ensure_ascii=False), encoding="utf-8")
        selection = self.base / "sel.json"
        selection.write_text(json.dumps({"schemaVersion": "drama-studio/selection/v0", "items": [
            {"ref": {"kind": "local_file", "id": name, "revision": None}, "partition": partition, "required": True, "reason": "测试"}
            for name in names]}, ensure_ascii=False), encoding="utf-8")
        return tool("context-pack", self.project, "--task", task, "--selection", selection, "--role", role,
                    "--budget", 200000, "--dry-run")


class PlanningLocalFileTests(PackCase):
    def test_a_planning_file_packs_and_is_pinned_by_its_bytes(self):
        self.write("planning/season-plan.json", example("season-plan"))
        code, out = self.pack("fact_check", ["planning/season-plan.json"])
        self.assertEqual(code, 0, out)
        self.assertIn("local_file planning/season-plan.json", " ".join(item["ref"] for item in out["items"]))

    def test_escapes_from_planning_are_still_refused(self):
        self.write("notes.md", "不该装入")
        for name in ("planning/../notes.md", "planning", "../proj/planning/x.md"):
            with self.subTest(name=name):
                code, out = self.pack("fact_check", [name])
                self.assertEqual(code, 1, out)
        outside = self.base / "outside.md"
        outside.write_text("项目外", encoding="utf-8")
        (self.project / "planning").mkdir(exist_ok=True)
        (self.project / "planning/link.md").symlink_to(outside)
        code, out = self.pack("fact_check", ["planning/link.md"])
        self.assertEqual(code, 2, out)
        self.assertIn("resolves outside planning/", " ".join(out["errors"]))


class C4AuthorGateTests(PackCase):
    """A C4 author package in an outline-layer project holds the season plan and a ledger (outline-season-assigned,
    outline-ledger-delta); projects without outline-layer records keep the 0.4.0 behaviour."""

    def setUp(self):
        super().setUp()
        self.task_doc.update(workstation="C4", taskId="task-ep05-plan")
        self.write("planning/season-plan.json", example("season-plan"))
        self.write("planning/ledger/ledger-ep000.json", example("ledger-entry"))
        self.write("planning/function-map.json", example("function-map"))
        self.write("runs/notes-ep05.md", "第五集的笔记")

    def errors(self, out):
        return " ".join(out.get("errors", []))

    def test_with_season_plan_ledger_and_function_map_it_passes(self):
        code, out = self.pack("author", ["planning/season-plan.json", "planning/ledger/ledger-ep000.json", "planning/function-map.json"])
        self.assertEqual(code, 0, out)

    def test_without_the_function_map_it_exits_2(self):
        code, out = self.pack("author", ["planning/season-plan.json", "planning/ledger/ledger-ep000.json"])
        self.assertEqual(code, 2, out)
        self.assertIn("no function map", self.errors(out))

    def test_without_the_season_plan_it_exits_2(self):
        code, out = self.pack("author", ["planning/ledger/ledger-ep000.json"])
        self.assertEqual(code, 2, out)
        self.assertIn("no season plan", self.errors(out))
        self.assertNotIn("no ledger", self.errors(out))

    def test_without_the_ledger_it_exits_2(self):
        code, out = self.pack("author", ["planning/season-plan.json"])
        self.assertEqual(code, 2, out)
        self.assertIn("no ledger", self.errors(out))
        self.assertNotIn("no season plan", self.errors(out))

    def test_a_season_plan_file_not_in_the_package_does_not_count(self):
        code, out = self.pack("author", ["runs/notes-ep05.md"])
        self.assertEqual(code, 2, out)
        self.assertIn("no season plan", self.errors(out))
        self.assertIn("no ledger", self.errors(out))

    def test_a_task_with_layer_c4_is_gated_too(self):
        self.task_doc.update(workstation="C4", layer="C4")
        code, out = self.pack("author", ["runs/notes-ep05.md"])
        self.assertEqual(code, 2, out)

    def clear(self):
        for path in ("planning/season-plan.json", "planning/ledger/ledger-ep000.json", "planning/function-map.json"):
            (self.project / path).unlink(missing_ok=True)

    def test_each_outline_record_alone_switches_the_gate_on(self):
        for marker, doc in (("planning/season-plan.json", "season-plan"), ("planning/function-map.json", "function-map"),
                            ("planning/ledger/ledger-ep000.json", "ledger-entry"), ("planning/episodes/episode-plan-001.json", "episode-plan")):
            with self.subTest(marker=marker):
                self.clear()
                for other in ("planning/function-map.json", "planning/episodes/episode-plan-001.json"):
                    (self.project / other).unlink(missing_ok=True)
                self.write(marker, example(doc))
                code, out = self.pack("author", ["runs/notes-ep05.md"])
                self.assertEqual(code, 2, out)
                self.assertIn("no ledger", self.errors(out))

    def test_a_fresh_project_with_empty_folders_is_unchanged(self):
        self.clear()
        (self.project / "planning/episodes").mkdir(parents=True, exist_ok=True)  # what init-project leaves before C3a
        code, out = self.pack("author", ["runs/notes-ep05.md"])
        self.assertEqual(code, 0, out)

    def test_an_old_project_without_outline_records_is_unchanged(self):
        """planning/ holding only 0.3.6 framework files: the C4 package is what it would be with no planning/ at all."""
        self.clear()
        (self.project / "planning/ledger").rmdir()
        self.write("planning/framework-v1.md", "旧项目的框架")  # 0.3.6 projects have planning/ with markdown in it
        self.write("planning/outline-v1-ep001-060.md", "旧集纲")
        self.write("planning/episode-spec.json", {"episodes": 60})  # and loose JSON directly under planning/
        code, with_old = self.pack("author", ["runs/notes-ep05.md"])
        self.assertEqual(code, 0, with_old)
        import shutil
        shutil.rmtree(self.project / "planning")
        code, without = self.pack("author", ["runs/notes-ep05.md"])
        self.assertEqual(code, 0, without)
        self.assertEqual(with_old, without)

    def test_other_roles_and_workstations_are_not_gated(self):
        code, out = self.pack("fact_check", ["runs/notes-ep05.md"])
        self.assertEqual(code, 0, out)
        self.task_doc.update(workstation="C5")
        code, out = self.pack("author", ["runs/notes-ep05.md"])
        self.assertEqual(code, 0, out)


class ConstraintBlocklistTests(Temp):
    """contract-check task refuses 'do not touch the episode count' / 'revise only once' constraints whatever their origin."""

    def check(self, text, origin="writer"):
        doc = example("task")
        doc["constraints"] = [{"text": text, "origin": origin, **({"cite": "C1"} if origin in ("orchestrator", "target") else {})}]
        path = self.base / "task.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return tool("contract-check", "task", path)

    def test_every_structure_freeze_term_is_refused_by_the_cli(self):
        terms = next(c for c in json.loads(BLOCKLIST.read_text(encoding="utf-8"))["categories"] if c["id"] == "structure_freeze")["terms"]
        for term in terms:
            for origin in ("writer", "orchestrator", "target", "skill"):
                with self.subTest(term=term, origin=origin):
                    code, out = self.check(f"这一轮{term}，先交稿", origin)
                    self.assertEqual(code, 2, out)
                    self.assertIn("structure_freeze", " ".join(out["errors"]))

    def test_paraphrases_hit_the_patterns(self):
        for text in ("不改动集数", "不要变更标题", "别动集数", "禁止改标题", "只修一轮", "只改一遍就交", "只能修改一次", "不分成两集",
                     "第6集不拆成两集", "不要拆成两集", "不动★的位置"):
            with self.subTest(text=text):
                code, out = self.check(text)
                self.assertEqual(code, 2, out)
                self.assertIn("structure_freeze", " ".join(out["errors"]))

    def test_constraints_about_content_pass(self):
        for text in ("集数与拆集由季编排决定", "第6集拆成 6A、6B 两集", "改完回功能层换实现", "保留标题里的人名", "孩子对大人说话先叫人再说事",
                     "标题格式统一", "集数编号用三位数", "拆集写成 006A、006B", "改标题前先查重", "★位置由季编排定",
                     "不改人物关系", "只改第三场", "分两场写", "集数不定，按容量排", "每集结尾留钩子",
                     "修改时保持人物口吻一致", "拆分长场为两个短场"):
            with self.subTest(text=text):
                code, out = self.check(text)
                self.assertEqual(code, 0, out)
                self.assertTrue(out["passed"])


class NumericDialogueBlocklistTests(Temp):
    """v3: 字数／行数／句数／台词量 are no longer bare substrings; a number, or a verb making the measure a target, is."""

    check = ConstraintBlocklistTests.check

    def test_numeric_and_measure_target_directives_are_refused(self):
        for text in ("少40字", "比 e1 少 40 字", "删两句", "台词压到五行", "砍掉三句", "行数变化不超过 3 行", "每句不超过十个字",
                     "控制字数", "压缩台词量", "字数控制在 300 以内", "精简句数", "减少换人次数", "换人数保持原样"):
            with self.subTest(text=text):
                code, out = self.check(text)
                self.assertEqual(code, 2, out)
                self.assertIn("numeric_dialogue", " ".join(out["errors"]))

    def test_mentions_of_a_measure_that_set_no_target_pass(self):
        for text in ("字数统计仅供参考", "台词里不要出现数字", "集数编号用三位数", "行数按正文实际统计", "台词量由容量提案决定",
                     "多一个人在场", "删掉这场里重复的说明", "压低声音说", "少说废话，先接情绪"):
            with self.subTest(text=text):
                code, out = self.check(text)
                self.assertEqual(code, 0, out)

    def test_the_bare_measure_words_are_gone_and_the_version_is_v3(self):
        data = json.loads(BLOCKLIST.read_text(encoding="utf-8"))
        numeric = next(c for c in data["categories"] if c["id"] == "numeric_dialogue")
        # wording rulings #2 changed this on purpose: v4 narrows the count units to 字/行/句/来回; the terms are unchanged
        self.assertEqual((data["version"], numeric["terms"]), ("v4", ["换人数", "换人次数"]))


class PlanCheckCharactersTests(Temp):
    """plan-check --characters: prehistory events in the character pack need timeline ledger entries; report only."""

    def setUp(self):
        super().setUp()
        self.plan = self.base / "plan.json"
        self.plan.write_text(json.dumps(example("episode-plan"), ensure_ascii=False), encoding="utf-8")
        self.ledger = self.base / "ledger.json"
        self.ledger.write_text(json.dumps(example("ledger-entry"), ensure_ascii=False), encoding="utf-8")

    def check(self, name, content):
        pack = self.base / name
        pack.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")
        return tool("plan-check", self.plan, "--ledger", self.ledger, "--characters", pack)

    def test_events_with_timeline_entries_pass(self):
        code, out = self.check("pack.json", {"characters": [{"name": "老陈", "prehistory": [{"text": "三年前去过仓库", "ledgerRef": "L-tl-001"}]}]})
        self.assertEqual(out["rules"]["characters-prehistory"], {"status": "pass", "items": [], "events": 1})
        self.assertEqual(code, tool("plan-check", self.plan, "--ledger", self.ledger)[0])

    def test_missing_unknown_and_non_timeline_refs_are_reported_never_blocking(self):
        base_code, base = tool("plan-check", self.plan, "--ledger", self.ledger)
        code, out = self.check("pack.json", {"characters": [{"name": "老陈", "prehistory": [
            {"text": "三年里汇了钱"}, {"text": "签过一张单", "pending": True}, {"text": "去过省城", "ledgerRef": ["L-tl-999"]},
            {"text": "箱子在阁楼", "ledgerRef": "L-obj-001"}]}]})
        rule = out["rules"]["characters-prehistory"]
        self.assertEqual(rule["status"], "report")
        text = " ".join(rule["items"])
        for fragment in ("前史事件没有时间线账条目：老陈：三年里汇了钱", "（待定，交 C3b 登记）老陈：签过一张单", "L-tl-999 不在入口底账里",
                         "L-obj-001 是 object 条目，不是时间线"):
            self.assertIn(fragment, text)
        self.assertEqual((code, out["passed"]), (base_code, base["passed"]))

    def test_markdown_pack_reads_the_prehistory_section_only(self):
        code, out = self.check("pack.md", "# 老陈\n\n## 欲望\n- 找箱子\n\n## 共同前史\n- 三年前去过仓库（L-tl-001）\n- 三年里汇了钱\n"
                                          "- 签过一张单（待定）\n\n## 声音\n短句\n")
        rule = out["rules"]["characters-prehistory"]
        self.assertEqual(rule["events"], 3)
        self.assertEqual(len(rule["items"]), 2)
        self.assertIn("三年里汇了钱", rule["items"][0])
        self.assertTrue(rule["items"][1].startswith("（待定"))

    def test_without_characters_there_is_no_such_rule(self):
        code, out = tool("plan-check", self.plan, "--ledger", self.ledger)
        self.assertNotIn("characters-prehistory", out["rules"])


class LedgerReplayFolderTests(Temp):
    def setUp(self):
        super().setUp()
        ledger = example("ledger-entry")
        self.folder = self.base / "planning/ledger"
        self.folder.mkdir(parents=True)
        (self.folder / "ledger-ep000.json").write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        for episode, state in (("002", "开了"), ("001", "封着")):
            delta = {"schemaVersion": "drama-studio/ledger-delta/v0", "episode": episode, "track": "planned", "reads": ["L-obj-001"],
                     "writes": [{"entryId": "L-obj-001", "change": {"state": state}, "reason": "测试", "supportedBy": f"{int(episode)}-1.b1"}]}
            (self.folder / f"delta-ep{episode}.planned.json").write_text(json.dumps(delta, ensure_ascii=False), encoding="utf-8")

    def test_a_folder_replays_its_deltas_in_episode_order(self):
        code, out = tool("ledger", "replay", self.folder / "ledger-ep000.json", "--delta", self.folder, "--at", "2")
        self.assertEqual(code, 0, out)
        self.assertEqual([str(step["episode"]) for step in out["steps"]], ["001", "002"])
        files = [self.folder / "delta-ep001.planned.json", self.folder / "delta-ep002.planned.json"]
        code, by_file = tool("ledger", "replay", self.folder / "ledger-ep000.json", "--delta", files[1], "--delta", files[0], "--at", "2")
        self.assertEqual([s["delta"] for s in out["steps"]], [s["delta"] for s in by_file["steps"]])

    def test_a_folder_without_deltas_is_an_input_error(self):
        empty = self.base / "empty"
        empty.mkdir()
        code, out = tool("ledger", "replay", self.folder / "ledger-ep000.json", "--delta", empty, "--at", "2")
        self.assertEqual(code, 1, out)
        self.assertIn("delta-*.json", out["error"])

    def md(self, *args):
        run = subprocess.run([sys.executable, "-B", str(TOOL), "ledger", "replay", str(self.folder / "ledger-ep000.json"),
                              "--delta", str(self.folder), "--md", *map(str, args)], capture_output=True, text=True)
        return run.returncode, run.stdout, run.stderr

    def test_md_says_which_episodes_fell_back_to_the_planned_track(self):
        code, out, err = self.md("--at", "2", "--track", "actual")
        self.assertEqual(code, 0, err)
        self.assertIn("## 重放说明", out)
        self.assertIn("plannedFallback）：001、002", out)
        code, out, err = self.md("--at", "2")
        self.assertNotIn("## 重放说明", out)

    def test_md_with_apply_errors_writes_them_and_exits_2(self):
        bad = json.loads((self.folder / "delta-ep002.planned.json").read_text(encoding="utf-8"))
        bad["writes"][0]["entryId"] = "L-nope-404"
        (self.folder / "delta-ep002.planned.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        code, out, err = self.md("--at", "2")
        self.assertEqual(code, 2)
        self.assertIn("应用出错", out)
        self.assertIn("L-nope-404", err)


class C6TaskTargetTests(Temp):
    def check(self, doc):
        path = self.base / "task.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return tool("contract-check", "task", path)

    def test_outline_side_reads_need_no_dialogue_target(self):
        for kind in ("episode_plan", "function_map", "ledger", "season_plan"):
            doc = example("task")
            doc.update(workstation="C6", layer="C6", target={"kind": kind, "episode": "005"})
            with self.subTest(kind=kind):
                self.assertEqual(self.check(doc)[0], 0)

    def test_text_reads_and_untargeted_c6_tasks_still_need_it(self):
        for target in ({"kind": "episode_text"}, None):
            doc = example("task")
            doc.update(workstation="C6", layer="C6")
            if target:
                doc["target"] = target
            with self.subTest(target=target):
                code, out = self.check(doc)
                self.assertEqual(code, 2, out)
                self.assertIn("dialogueTarget", " ".join(out["errors"]))

    def test_the_outline_exemption_is_c6_only(self):
        doc = example("task")
        doc.update(layer="C5b", target={"kind": "episode_plan"})
        self.assertEqual(self.check(doc)[0], 2)


class PlanReviewCitesTests(Temp):
    """A review of an episode plan in the D6-2 layout (planning/episodes/) needs cites on every finding that is not a
    preference; reviews of anything else keep the 0.4.0 rule (a cite-less finding without kind is allowed)."""

    def review(self, target, findings):
        doc = example("review-record")
        doc["target"] = {"kind": "local_file", "id": target, "revision": None}
        doc.pop("additionalTargets", None)
        doc["findings"] = findings
        # D6-3 changed this fixture on purpose: a review of an episode plan keeps only human-sourced preserved items, and
        # the example's plain-string item is the pre-D6-3 form
        doc["preserved"] = [{"item": item, "noteId": "WN-001"} for item in doc.get("preserved", [])]
        path = self.base / "review.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return tool("contract-check", "review-record", path)

    def finding(self, **extra):
        return {"id": "f1", "category": "goal", "layer": "C4", "claim": "第5拍的动机没交代", "evidence": [], "severity": "revise", **extra}

    def test_plan_review_finding_without_cites_fails(self):
        code, out = self.review("planning/episodes/episode-plan-005.json", [self.finding()])
        self.assertEqual(code, 2, out)
        self.assertIn("episode plan", " ".join(out["errors"]))

    def test_plan_review_with_cites_or_preference_passes(self):
        for finding in (self.finding(kind="finding", cites={"ledgerId": "L-tl-001"}), self.finding(cites={"functionId": "F-1"}),
                        self.finding(kind="preference")):
            with self.subTest(finding=finding):
                code, out = self.review("planning/episodes/episode-plan-005.json", [finding])
                self.assertEqual(code, 0, out)

    def test_other_reviews_keep_the_old_rule(self):
        code, out = self.review("runs/plan/outline-005.md", [self.finding()])
        self.assertEqual(code, 0, out)


class OutlineRulesSeeEpisodePlansTests(Temp):
    """The old outline rules recognise C4's JSON plans under planning/episodes/ (by schema marker) in an outline-layer
    project: a C4 run writing them is outline-run, a review targeting them is outline-review, a receipt saves them."""

    leave_out = ()
    late_records = False

    def build(self, folder="planning/episodes", marker=True):
        sys.path.insert(0, str(Path(__file__).parent))  # discover -s tests imports it bare; -m tests.x needs the path
        from test_season_check import Season
        self.root = self.base / "proj"
        s = Season(self.root)
        s.write("runs/state/after-ep-003.md", "入口：第3集后")
        names = [f"{folder}/episode-plan-{n:03d}.json" for n in (4, 5)]

        def records():
            s.write("planning/season-plan.json", json.dumps(example("season-plan"), ensure_ascii=False))
            s.write("planning/ledger/ledger-ep000.json", json.dumps(example("ledger-entry"), ensure_ascii=False))
            s.write("planning/function-map.json", json.dumps(example("function-map"), ensure_ascii=False))
            for n, name in zip((4, 5), names):
                plan = example("episode-plan")
                plan["episode"] = n
                if not marker:
                    del plan["schemaVersion"]
                s.write(name, json.dumps(plan, ensure_ascii=False))
        if not self.late_records:
            records()

        items = [("project_facts", "runs/C2/out.md"), ("project_facts", "runs/C3/out.md"), ("project_facts", "runs/input/outline-003.md"),
                 ("project_facts", "runs/state/after-ep-003.md"), ("current_plan", "planning/season-plan.json"),
                 ("current_plan", "planning/ledger/ledger-ep000.json"), ("current_plan", "planning/function-map.json")]
        items = [item for item in items if item[1] not in self.leave_out]
        s.handoff("C4", "c4-plans", items, [s.ref(name) for name in names])
        if self.late_records:
            records()
        targets = [s.ref(name) for name in names]
        review = {"schemaVersion": "drama-studio/review-record/v0", "reviewId": "plan-review", "target": targets[0],
                  "additionalTargets": targets[1:], "readingScope": targets, "context": "independent", "claimsIndependence": False,
                  "firstReadWithoutAuthorNotes": False, "findings": [], "goalAssessments": []}
        s.write(".drama/reviews/plan-review.json", json.dumps(review, ensure_ascii=False))
        code, out = tool("season-check", self.root, "--outline", "4-5", "--allow-offline")
        return out, {f["rule"] for f in out["failures"]}

    def test_plans_under_planning_episodes_are_found(self):
        out, rules = self.build()
        self.assertFalse(rules & {"outline-run", "outline-review", "outline-snapshot", "outline-characters", "outline-structure",
                                  "outline-sequential", "outline-previous"}, out["failures"])
        self.assertEqual(out["perOutline"]["4"]["run"], "c4-plans")
        self.assertEqual(out["perOutline"]["5"]["reviews"], ["plan-review"])

    def test_outline_structure_follows_the_c4_package_checklist(self):
        # a C4 run packed before the project's outline records existed (context-pack's gate was not on yet)
        self.leave_out = ("planning/season-plan.json", "planning/ledger/ledger-ep000.json", "planning/function-map.json")
        self.late_records = True
        out, rules = self.build()
        structure = [f["message"] for f in out["failures"] if f["rule"] == "outline-structure"]
        self.assertEqual(len(structure), 2, out["failures"])
        for fragment in ("季编排", "功能地图", "底账当前修订"):
            self.assertIn(fragment, structure[0])

    def test_a_file_without_the_episode_plan_marker_is_not_a_plan(self):
        out, rules = self.build(marker=False)
        self.assertIn("outline-run", rules)

    def test_plans_outside_the_layer_folders_are_not_found(self):
        out, rules = self.build(folder="runs/plans")
        self.assertIn("outline-run", rules)


if __name__ == "__main__":
    unittest.main()
