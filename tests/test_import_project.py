import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/drama-studio/scripts/drama_tools.py"
MCP = ROOT / "tests/fixtures/mcp"
SNAPSHOT = "sha256:9be0b1334077ad7e1332d825fd08104054c31f4aa4ddf273c1234f5f2521d390"  # the real fixture save's snapshot
PROJECT_ID = "4e6556ac97654bf781977"
EMPTY_LISTING = MCP / "08-reconcile-list.response.json"
FILES = {
    "episodes/ep-01.md": "场1-1 日 内 客厅\n\n△林夏推门。\n林夏：“我回来了……”\n",
    "episodes/第2集.md": "第二集正文\r\n保留 CRLF 与“弯引号”。\n",
    "episodes/01-10-v1.md": "合并稿",
    "planning/ep-01-outline.md": "第一集集纲",
    "planning/characters.md": "人物小传",
    "planning/characters-v1.md": "旧人物小传",
    "planning/experiments/r01-a.md": "探索片段",
    "reviews/ep-01-review.md": "第一集评审",
    "reference/season1.md": "对标拉片",
    "deliveries/hand-off.md": "交付包",
    "research/positioning.md": "定位",
    "research/notes.md": "研究笔记",
}


def tool(*args):
    return subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True)


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


class ImportProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "old-drama"
        self.assertEqual(tool("init-project", self.project, "--title", "旧项目").returncode, 0)
        for name, text in FILES.items():
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        self.bind(PROJECT_ID)
        self.out = self.base / "requests"

    def bind(self, project_id):
        path = self.project / ".drama/project.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["remoteProjectId"] = project_id
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def listing(self, rows, name="list.json"):
        path = self.base / name
        path.write_text(json.dumps({"schemaVersion": "mali-tool-result/v1", "ok": True,
                                    "data": {"records": rows, "nextCursorId": None, "adoptionStatus": "not_resolved"},
                                    "recovery": {"action": "none", "retrySafe": False}, "transport": {"status": 200}}), encoding="utf-8")
        return path

    def run_json(self, *args, code=0):
        run = tool(*args)
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        return json.loads(run.stdout) if code != 1 else json.loads(run.stderr)

    def apply(self, listing=EMPTY_LISTING, out=None, code=0, extra=()):
        return self.run_json("import-project", "apply", self.project, "--listing", listing, "--out", out or self.out,
                             "--producer", "external_ai", "--input-snapshot-id", SNAPSHOT, *extra, code=code)

    def test_preview_writes_nothing_and_maps_by_convention(self):
        before = snapshot(self.project)
        result = self.run_json("import-project", "preview", self.project, "--listing", EMPTY_LISTING)
        self.assertEqual(snapshot(self.project), before)  # same files, same sha256, nothing added
        self.assertTrue(result["read_only"])
        mapped = {item["source"]: (item["slot"], item["kind"], item["episodeRef"]) for item in result["create"]}
        self.assertEqual(mapped, {
            "episodes/ep-01.md": ("ep-01-draft", "episode_draft", "ep-01"),
            "episodes/第2集.md": ("ep-02-draft", "episode_draft", "ep-02"),
            "planning/ep-01-outline.md": ("ep-01-outline", "episode_outline", "ep-01"),
            "planning/characters.md": ("characters", "characters", None),
            "reviews/ep-01-review.md": ("ep-01-review", "review", "ep-01"),
            "research/positioning.md": ("positioning", "research", None)})
        skipped = {item["source"] for item in result["skipped"]}
        self.assertEqual(skipped, {"PROJECT.md", "episodes/01-10-v1.md", "planning/characters-v1.md", "planning/experiments/r01-a.md",
                                   "reference/season1.md", "deliveries/hand-off.md", "research/notes.md"})
        self.assertTrue(all(item["reason"] for item in result["skipped"]))
        self.assertFalse(any(name.startswith(".drama") for name in skipped))

    def test_same_slot_from_two_files_is_skipped(self):
        (self.project / "episodes/ep001.md").write_text("另一份第一集", encoding="utf-8")
        result = self.run_json("import-project", "preview", self.project, "--listing", EMPTY_LISTING)
        self.assertNotIn("ep-01-draft", {item["slot"] for item in result["create"]})
        reasons = [item["reason"] for item in result["skipped"] if item["source"] in ("episodes/ep001.md", "episodes/ep-01.md")]
        self.assertEqual(len(reasons), 2)
        self.assertIn("同一 slot", reasons[0])

    def test_remote_revision_is_a_conflict_in_preview_and_apply(self):
        listing = self.listing([{"id": "a1", "slot": "ep-01-draft", "kind": "episode_draft", "episodeRef": "ep-01", "revision": 1},
                                {"id": "a2", "slot": "ep-01-draft", "kind": "episode_draft", "episodeRef": "ep-01", "revision": 3},
                                {"id": "a3", "slot": "unrelated", "kind": "research", "revision": 1}])
        preview = self.run_json("import-project", "preview", self.project, "--listing", listing)
        self.assertEqual([(c["slot"], c["remoteRevision"], c["source"], c["remoteSlots"]) for c in preview["conflicts"]],
                         [("ep-01-draft", 3, "episodes/ep-01.md", ["ep-01-draft"])])
        self.assertNotIn("ep-01-draft", {item["slot"] for item in preview["create"]})
        applied = self.apply(listing)
        self.assertEqual([c["slot"] for c in applied["conflicts"]], ["ep-01-draft"])
        slots = {json.loads(path.read_text(encoding="utf-8"))["slot"] for path in self.out.glob("*.json")}
        self.assertNotIn("ep-01-draft", slots)
        self.assertEqual(len(slots), 5)

    def test_three_digit_remote_episode_slot_conflicts_with_two_digit_local_slot(self):
        listing = self.listing([{"id": "a1", "slot": "ep-001-draft", "kind": "episode_draft", "episodeRef": "ep-001", "revision": 2},
                                {"id": "a2", "slot": "ep-0002", "kind": "episode_draft", "revision": 1},
                                {"id": "a3", "slot": "ep-001-outlines", "kind": "episode_outline", "revision": 1}])
        preview = self.run_json("import-project", "preview", self.project, "--listing", listing)
        conflicts = {c["slot"]: (c["remoteRevision"], c["remoteSlots"]) for c in preview["conflicts"]}
        self.assertEqual(conflicts, {"ep-01-draft": (2, ["ep-001-draft"])})
        self.assertIn("ep-01-draft", {c["slot"] for c in self.apply(listing)["conflicts"]})
        self.assertNotIn("ep-01-draft", {json.loads(p.read_text(encoding="utf-8"))["slot"] for p in self.out.glob("*.json")})
        self.assertIn("ep-01-outline", {item["slot"] for item in preview["create"]})  # different suffix is a different slot

    def test_apply_writes_one_request_per_item_and_only_into_out(self):
        before = snapshot(self.project)
        preview = self.run_json("import-project", "preview", self.project, "--listing", EMPTY_LISTING)
        result = self.apply()
        self.assertEqual(snapshot(self.project), before)
        files = sorted(self.out.glob("*"))
        self.assertEqual(len(files), len(preview["create"]))
        self.assertEqual(sorted(r["source"] for r in result["requests"]), sorted(i["source"] for i in preview["create"]))
        for request in result["requests"]:
            save = json.loads(Path(request["path"]).read_text(encoding="utf-8"))
            source = (self.project / request["source"]).read_bytes()
            self.assertEqual(save["body"].encode("utf-8"), source)  # verbatim, CRLF and quotes kept
            self.assertEqual("sha256:" + hashlib.sha256(source).hexdigest(), request["bodySha256"])
            self.assertEqual((save["project_id"], save["expected_revision"], save["producer"], save["input_snapshot_id"]),
                             (PROJECT_ID, 0, "external_ai", SNAPSHOT))
            self.assertEqual(save["request_id"], request["requestId"])
            self.assertEqual(Path(request["path"]).name, save["request_id"] + ".json")
            expected = {"project_id", "slot", "kind", "expected_revision", "body", "producer", "input_snapshot_id", "request_id"}
            self.assertEqual(set(save) - {"episode_ref"}, expected)
            self.assertEqual("episode_ref" in save, save["kind"] in ("episode_draft", "episode_outline", "review"))

    def test_out_inside_project_is_excluded_and_project_folders_refused(self):
        inside = self.project / "import-requests"
        self.apply(out=inside)
        again = self.run_json("import-project", "preview", self.project, "--listing", EMPTY_LISTING)
        self.assertFalse(any(item["source"].startswith("import-requests/") for item in again["create"]))
        self.assertTrue(any(item["source"].startswith("import-requests/") for item in again["skipped"]))
        self.assertTrue(all(r["existing"] for r in self.apply(out=inside)["requests"]))  # apply never scans its own --out
        for folder in ("episodes", ".drama", "."):
            error = self.apply(out=self.project / folder, code=1)
            self.assertIn("--out", error["error"])

    def test_request_id_is_stable_and_content_determined(self):
        first = {r["source"]: r["requestId"] for r in self.apply()["requests"]}
        bytes_first = {p.name: p.read_bytes() for p in self.out.glob("*.json")}
        second = self.apply()
        self.assertEqual({r["source"]: r["requestId"] for r in second["requests"]}, first)
        self.assertTrue(all(r["existing"] for r in second["requests"]))
        self.assertEqual({p.name: p.read_bytes() for p in self.out.glob("*.json")}, bytes_first)
        other = self.apply(out=self.base / "elsewhere")
        self.assertEqual({r["source"]: r["requestId"] for r in other["requests"]}, first)  # does not depend on time or folder
        (self.project / "planning/characters.md").write_text("人物小传（改）", encoding="utf-8")
        changed = {r["source"]: r["requestId"] for r in self.apply(out=self.base / "changed")["requests"]}
        self.assertNotEqual(changed["planning/characters.md"], first["planning/characters.md"])
        self.assertTrue(changed["planning/characters.md"].startswith("import-characters-"))
        self.assertEqual(changed["episodes/ep-01.md"], first["episodes/ep-01.md"])

    def test_differing_existing_request_file_is_refused(self):
        result = self.apply()
        victim = Path(result["requests"][0]["path"])
        victim.write_text("{}", encoding="utf-8")
        before = snapshot(self.out)
        refused = self.apply(code=2)
        self.assertEqual(refused["status"], "refused")
        self.assertEqual(snapshot(self.out), before)

    def test_missing_remote_project_id_is_an_error(self):
        for value in (None, ""):
            self.bind(value)
            error = self.apply(code=1)
            self.assertIn("remoteProjectId", error["error"])
            self.assertFalse(self.out.exists())

    def test_producer_and_snapshot_are_required(self):
        base = ["import-project", "apply", self.project, "--listing", EMPTY_LISTING, "--out", self.out]
        self.assertEqual(tool(*base, "--input-snapshot-id", SNAPSHOT).returncode, 2)  # argparse: --producer missing
        self.assertEqual(tool(*base, "--producer", "external_ai").returncode, 2)
        self.assertEqual(tool(*base, "--producer", "claude", "--input-snapshot-id", SNAPSHOT).returncode, 2)
        self.apply(code=1, extra=("--input-snapshot-id", "ctx-123"))
        self.assertFalse(self.out.exists())

    def test_incomplete_or_error_listing_is_an_error(self):
        page = json.loads(self.listing([]).read_text(encoding="utf-8"))
        page["data"]["nextCursorId"] = "a9"
        partial = self.base / "page1.json"
        partial.write_text(json.dumps(page), encoding="utf-8")
        self.assertEqual(tool("import-project", "preview", self.project, "--listing", partial).returncode, 1)
        result = self.run_json("import-project", "preview", self.project, "--listing", partial, "--listing", EMPTY_LISTING)
        self.assertEqual(result["listing"]["pages"], 2)
        self.assertEqual(tool("import-project", "preview", self.project, "--listing", MCP / "06-requestid-conflict.response.json").returncode, 1)

    def test_real_listing_fixture_parses(self):
        result = self.run_json("import-project", "preview", self.project, "--listing", MCP / "04-list.response.json")
        self.assertEqual(result["listing"], {"pages": 1, "rows": 1, "slots": 1})
        self.assertEqual(result["conflicts"], [])

    def test_apply_input_records_a_receipt_that_passes_contract_check(self):
        result = self.apply()
        request = next(r for r in result["requests"] if r["source"] == "episodes/ep-01.md")
        save = json.loads(Path(request["path"]).read_text(encoding="utf-8"))
        response = json.loads((MCP / "02-save.response.json").read_text(encoding="utf-8"))
        record = response["data"]["record"]  # the real save response, re-pointed at this request
        record.update(slot=save["slot"], kind=save["kind"], episodeRef=save["episode_ref"], body=save["body"],
                      requestId=save["request_id"], projectId=save["project_id"], inputSnapshotId=save["input_snapshot_id"])
        saved = self.base / "save.response.json"
        saved.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        recorded = self.run_json("receipt", "record", self.project, saved, "--operation", "save_story_artifact",
                                 "--request-id", save["request_id"], "--input", request["path"])
        self.assertEqual((recorded["status"], recorded["receipt"]["outcome"]), ("written", "confirmed"))
        receipt_path = self.project / ".drama/receipts" / f"{save['request_id']}.json"
        check = tool("contract-check", "remote-receipt", receipt_path)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertTrue(json.loads(check.stdout)["passed"])
        self.assertEqual(json.loads(receipt_path.read_text(encoding="utf-8"))["localRef"]["id"], "slot:ep-01-draft")


if __name__ == "__main__":
    unittest.main()
