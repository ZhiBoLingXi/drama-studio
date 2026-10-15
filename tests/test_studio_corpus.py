"""Studio-level corpus cache (plan §8 #1, confirmed 2026-10-15): `<studio root>/corpus/` beside STUDIO.md.

context-pack --studio-corpus, contract-check of studio corpus objects, and corpus label/agree/defaults/fetch run on a
studio corpus folder. Fabricated fixtures only; one passing and one failing case per S rule. Without --studio-corpus
the old tests (test_context_pack_d6, test_d64_tools, test_corpus) cover the unchanged behaviour.
"""
import json
import os
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
from checks import contract_check as contracts, context_pack  # noqa: E402
import test_context_pack_d6 as packs  # noqa: E402
from test_corpus import raw_md, write_episode  # noqa: E402

STUDIO = {"scope": {"level": "studio"}, "origin": {"kind": "mali_story_template"}}


def example(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def tool(*args):
    proc = subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)
    text = proc.stdout if proc.stdout.lstrip().startswith("{") else proc.stderr
    return proc.returncode, json.loads(text) if text.strip() else {}


def jsonl(rows):
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"


class Studio(unittest.TestCase):
    """A project (the D6-1 sample fixture) and, beside it, a studio root with STUDIO.md and corpus/."""

    def setUp(self):
        self.case = packs.D6PackTests("test_two_positives_and_one_pair_per_topic")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.studio = self.case.base / "studio"
        self.corpus = self.studio / "corpus"
        self.corpus.mkdir(parents=True)
        (self.studio / "STUDIO.md").write_text("# 工作室（编造）\n", encoding="utf-8")

    def samples(self, name="exchanges.jsonl", **extra):
        path = self.corpus / name
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{**packs.exchange(f"EX-000{i}", "甲说了一句话" * i), **STUDIO, **extra} for i in range(1, 5)]
        path.write_text(jsonl(rows), encoding="utf-8")
        return path

    def pack(self, exemplars, *extra, contrast=None):
        items = [("current_plan", "runs/plan/episode-plan-003.json"), ("current_plan", "runs/plan/dialogue-plan-003.json")]
        return self.case.pack("dialogue_designer", items, 20000, "--exemplars", str(exemplars),
                              "--contrast-pairs", str(contrast or self.case.project / "runs/contrast-pairs.jsonl"), *extra)


class StudioPacking(Studio):
    def test_samples_are_packed_from_the_studio_corpus(self):
        code, out = self.pack(self.samples(), "--studio-corpus", self.corpus)
        self.assertEqual(code, 0, out.get("error") or out.get("errors"))
        self.assertIn("sample T1 正例 EX-0001", [i["ref"] for i in out["items"]])
        self.assertIn("sample T2 对照对 CP-01", [i["ref"] for i in out["items"]])  # contrast pairs still come from the project
        self.assertTrue(out["samples"]["fromStudioCorpus"])
        ident = context_pack._sample_file(self.case.project, str(self.corpus / "exchanges.jsonl"), "--exemplars", self.corpus.resolve())[0]
        self.assertEqual(ident, "studio-corpus/exchanges.jsonl")  # the packed ref names the studio corpus, not a project path

    def test_without_the_flag_a_studio_file_is_refused_as_before(self):
        code, out = self.pack(self.samples())
        self.assertEqual(code, 1, out)
        self.assertIn("must be a file inside", out["error"])

    def test_a_studio_record_from_a_project_source_is_refused(self):
        code, out = self.pack(self.samples(origin={"kind": "writer_project"}), "--studio-corpus", self.corpus)
        self.assertEqual(code, 1, out)
        self.assertIn("mali_story_template", out["error"])
        code, out = self.pack(self.samples(scope={"level": "project"}), "--studio-corpus", self.corpus)
        self.assertEqual(code, 1, out)
        self.assertIn("scope.level: studio", out["error"])

    def test_dot_dot_and_a_symlink_out_of_the_studio_corpus_are_refused(self):
        outside = self.case.base / "outside.jsonl"
        outside.write_text(self.samples().read_text(encoding="utf-8"), encoding="utf-8")
        code, out = self.pack(self.corpus / ".." / ".." / "outside.jsonl", "--studio-corpus", self.corpus)
        self.assertEqual(code, 1, out)
        link = self.corpus / "link.jsonl"
        os.symlink(outside, link)
        code, out = self.pack(link, "--studio-corpus", self.corpus)
        self.assertEqual(code, 1, out)
        self.assertIn("must be a file inside", out["error"])

    def test_the_folder_must_be_corpus_beside_studio_md(self):
        self.samples()
        (self.studio / "STUDIO.md").unlink()
        code, out = self.pack(self.corpus / "exchanges.jsonl", "--studio-corpus", self.corpus)
        self.assertEqual(code, 1, out)
        self.assertIn("STUDIO.md", out["error"])

    def test_contrast_pairs_and_dialogue_plans_stay_project_files(self):
        self.samples()
        pairs = self.corpus / "contrast-pairs.jsonl"
        pairs.write_text((self.case.project / "runs/contrast-pairs.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        code, out = self.pack(self.corpus / "exchanges.jsonl", "--studio-corpus", self.corpus, contrast=pairs)
        self.assertEqual(code, 1, out)
        self.assertIn("contrast pairs stay project-level", out["error"])
        plan = self.corpus / "dialogue-plan.json"
        plan.write_text(json.dumps(self.case.dialogue_plan, ensure_ascii=False), encoding="utf-8")
        code, out = self.pack(plan, "--studio-corpus", self.corpus)
        self.assertEqual(code, 1, out)
        self.assertIn("dialogue plan", out["error"])


class StudioContracts(unittest.TestCase):
    def test_a_studio_manifest_needs_template_origin(self):
        doc = example("corpus-manifest")
        doc.update(STUDIO)
        self.assertEqual(contracts.check_contract("corpus-manifest", doc), [])
        doc["origin"] = {"kind": "writer_project"}
        self.assertTrue(any("studio" in e for e in contracts.check_contract("corpus-manifest", doc)))
        del doc["origin"]
        self.assertTrue(any("studio" in e for e in contracts.check_contract("corpus-manifest", doc)))

    def test_a_studio_exchange_needs_template_origin(self):
        doc = example("dialogue-exchange")
        doc.update(STUDIO)
        self.assertEqual(contracts.check_contract("dialogue-exchange", doc), [])
        doc["origin"] = {"kind": "writer_project"}
        self.assertTrue(any("studio" in e for e in contracts.check_contract("dialogue-exchange", doc)))

    def test_project_records_stay_project_level(self):
        for name in ("contrast-pair", "writer-note", "knowledge-card"):
            doc = example(name)
            doc["scope"] = dict(doc.get("scope") or {}, level="studio")
            self.assertTrue(contracts.check_contract(name, doc), name)


class StudioCorpusCommands(Studio):
    def label_row(self, **extra):
        row = {"exchangeId": "T1-e01-01", "templateId": "T1", "episodeIndex": 1, "lineStart": 0, "lineEnd": 1, "about": "测试",
               "situation": {"speakerWants": "x", "listenerKnows": "y", "relation": "师徒", "powerDirection": "down",
                             "addresseeIsChild": False, "emotion": {"a": "怒", "b": "怕"}, "function": {"primary": "训斥"},
                             "infoMode": ["问答"], "audienceLearns": "z"},
               "walkthrough": "w", "quality": {"transcript": "ok", "label": "ok", "note": ""}}
        return {**row, **extra}

    def test_label_in_the_studio_corpus_takes_template_data_only(self):
        good = self.corpus / "labels" / "good.jsonl"
        good.parent.mkdir()
        good.write_text(jsonl([self.label_row(**STUDIO)]), encoding="utf-8")
        code, out = tool("corpus", "label", good)
        self.assertEqual((code, out["scope"], out["formatIssueCount"]), (0, "studio", 0))
        bad = self.corpus / "labels" / "bad.jsonl"
        bad.write_text(jsonl([self.label_row()]), encoding="utf-8")
        code, out = tool("corpus", "label", bad)
        self.assertEqual(code, 2)
        self.assertEqual(out["rows"][0]["formatIssues"][-1]["code"], "studio_not_template_data")

    def agree_rows(self, **extra):
        same = {"function": "问清", "relation": "师徒", "infoMode": ["问答"]}
        return [{"exchangeId": "E1", "labelRuns": {"run1": same, "run2": same}, "quality": {"label": "ok"}, **extra}]

    def test_agree_runs_on_the_studio_corpus_and_refuses_project_rows(self):
        path = self.corpus / "agree.jsonl"
        path.write_text(jsonl(self.agree_rows(**STUDIO)), encoding="utf-8")
        code, out = tool("corpus", "agree", path, "--out", self.corpus / "agreed.jsonl")
        self.assertEqual((code, out["scope"], out["compared"]), (0, "studio", 1))
        self.assertEqual(json.loads((self.corpus / "agreed.jsonl").read_text(encoding="utf-8"))["scope"], {"level": "studio"})
        path.write_text(jsonl(self.agree_rows()), encoding="utf-8")
        self.assertEqual(tool("corpus", "agree", path)[0], 1)
        project = self.case.base / "project-labels.jsonl"
        project.write_text(jsonl(self.agree_rows()), encoding="utf-8")
        self.assertEqual(tool("corpus", "agree", project)[1]["scope"], "project")
        self.assertEqual(tool("corpus", "agree", project, "--out", self.corpus / "from-project.jsonl")[0], 1)

    def test_defaults_runs_on_the_studio_corpus_and_refuses_project_rows(self):
        text = raw_md([("00:00.000", "00:20.000", "场景说明。")], [("00:00.000", "00:10.000", "张三", "", "一二三四五六七八九十")])
        write_episode(self.corpus / "raw" / "T1" / "ep-001.json", "T1", 1, text)
        row = {"exchangeId": "E1", "templateId": "T1", "episodeIndex": 1, "series": {"genre": "现实", "format": "live"},
               "startMs": 0, "endMs": 10000, "lines": [{"speaker": "张三", "text": "一二三四五六七八九十"}]}
        (self.corpus / "exchanges.jsonl").write_text(jsonl([dict(row, **STUDIO)]), encoding="utf-8")
        code, out = tool("corpus", "defaults", self.corpus)
        self.assertEqual((code, out.get("scope")), (0, "studio"), out)
        (self.corpus / "exchanges.jsonl").write_text(jsonl([row]), encoding="utf-8")
        code, out = tool("corpus", "defaults", self.corpus)
        self.assertEqual(code, 1, out)

    def test_a_fetch_ledger_in_the_studio_corpus_is_studio_level(self):
        templates = self.case.base / "templates.json"
        templates.write_text(json.dumps([{"templateId": "T1", "episodesTotal": 3}]), encoding="utf-8")
        code, out = tool("corpus", "fetch", "plan", templates, "--out", self.corpus / "fetch-ledger.json")
        self.assertEqual((code, out["scope"]), (0, "studio"))
        ledger = json.loads((self.corpus / "fetch-ledger.json").read_text(encoding="utf-8"))
        self.assertEqual((ledger["scope"], ledger["origin"]), ({"level": "studio"}, {"kind": "mali_story_template"}))
        self.assertEqual(tool("corpus", "fetch", "verify", self.corpus / "fetch-ledger.json")[1]["scope"], "studio")
        code, out = tool("corpus", "fetch", "plan", templates, "--out", self.case.base / "ledger.json")
        self.assertEqual((code, out["scope"]), (0, "project"))


if __name__ == "__main__":
    unittest.main()
