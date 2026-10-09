"""season-check: per-episode evidence that a season run followed the workstation flow (#64)."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/drama_tools.py")]


def run(*args):
    result = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout or result.stderr)


class Season:
    """A two-episode run (2-3) after a given episode 1, built through context-pack like a host would."""

    def __init__(self, root: Path, batch_author=False, same_state=False, usage_copied=False, receipt="confirmed",
                 sealed=True, blind_first=True):
        self.root, self.clock = root, 0
        subprocess.run(TOOL + ["init-project", str(root), "--title", "季检"], check=True, capture_output=True)
        self.local = json.loads((root / ".drama/project.json").read_text(encoding="utf-8"))["localId"]
        self.write("runs/input/ep-001.md", "第一集正文")
        self.write("runs/input/outline-002.md", "第二集集纲")
        self.write("runs/input/outline-003.md", "第三集集纲")
        self.write("runs/state/after-ep-001.md", "入口：第1集后，故事第3天")
        self.write("runs/state/after-ep-002.md", "入口：第1集后，故事第3天" if same_state else "入口：第2集后，翠兰拿到钱")
        for station in ("C1", "C2", "C3"):
            self.write(f"runs/{station}/out.md", station)
            self.handoff(station, f"{station.lower()}-1", [], [self.ref(f"runs/{station}/out.md")])
        self.handoff("C4", "c4-1", [], [self.ref("runs/input/outline-002.md"), self.ref("runs/input/outline-003.md")])
        usage = {"source": "estimated", "calls": 1, "chars": 900, "tokens": None}
        self.write("runs/b1/ep-002.md", "第二集正文")
        if batch_author:
            self.write("runs/b1/ep-003.md", "第三集正文")
            self.handoff("C5", "c5-ep2", self.items(2), [self.ref("runs/b1/ep-002.md"), self.ref("runs/b1/ep-003.md")],
                         usage=usage, proposals=1)
        else:
            self.handoff("C5", "c5-ep2", self.items(2), [self.ref("runs/b1/ep-002.md")], usage=usage, proposals=1)
            self.write("runs/b1/ep-003.md", "第三集正文")
            self.handoff("C5", "c5-ep3", self.items(3), [self.ref("runs/b1/ep-003.md")],
                         usage=usage if usage_copied else dict(usage, chars=950))
        reader = [("project_facts", f"runs/{p}.md") for p in ("input/ep-001", "b1/ep-002", "b1/ep-003")]
        self.handoff("C6", "c6-first", reader, [], role="reader_effect")
        self.review("b1-first", blind_first, sealed)
        self.review("b1-second", False, False)
        for n in (2, 3):
            if receipt:
                self.receipt(n, receipt)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def ref(name):
        return {"kind": "local_file", "id": name, "revision": None}

    def items(self, n):
        prev = "runs/input/ep-001.md" if n == 2 else "runs/b1/ep-002.md"
        return [("current_plan", f"runs/input/outline-{n:03d}.md"), ("project_facts", prev),
                ("project_facts", f"runs/state/after-ep-{n - 1:03d}.md")]

    def handoff(self, station, run_id, items, outputs, role="author", usage=None, proposals=0):
        self.clock += 1
        task = {"schemaVersion": "drama-studio/task/v0", "taskId": run_id, "kind": "draft", "workstation": station,
                "project": {"localId": self.local, "remoteProjectId": None}, "goal": "测试", "nonGoals": [],
                "readScope": [], "writeScope": [], "authorization": {"source": "user_message", "scope": "测试"},
                "revisionBudget": 1, "status": {"run": "finished", "goal": "met", "adoption": "none"}}
        selection = {"schemaVersion": "drama-studio/selection/v0", "sourceSnapshotId": None, "unknowns": [],
                     "items": [{"ref": self.ref(name), "partition": part, "required": True, "reason": "测试"} for part, name in items]}
        self.write(f"runs/tasks/{run_id}.task.json", json.dumps(task, ensure_ascii=False))
        self.write(f"runs/tasks/{run_id}.selection.json", json.dumps(selection, ensure_ascii=False))
        code, out = run("context-pack", self.root, "--task", self.root / f"runs/tasks/{run_id}.task.json",
                        "--selection", self.root / f"runs/tasks/{run_id}.selection.json", "--role", role, "--budget", 5000)
        assert code == 0, out
        doc = {"schemaVersion": "drama-studio/run-handoff/v0", "runId": run_id, "taskId": run_id, "workstation": station,
               "methodVersion": "0.1", "contextSnapshotId": out["snapshot_id"], "additionalSnapshotIds": [],
               "finishedAt": f"2026-10-09T10:{self.clock:02d}:00+08:00",
               "host": {"name": "test", "model": None, "usage": usage or {"source": "unknown"}},
               "outputs": outputs, "changeProposals": [], "status": {"run": "finished", "goal": "met"},
               "stateChangeProposals": [{"claim": "翠兰拿到钱", "evidence": outputs[0]} for _ in range(proposals)],
               "unfinished": [], "nextAction": "继续"}
        self.write(f".drama/runs/{run_id}.json", json.dumps(doc, ensure_ascii=False))

    def review(self, review_id, blind, sealed):
        targets = [self.ref("runs/b1/ep-002.md"), self.ref("runs/b1/ep-003.md")]
        doc = {"schemaVersion": "drama-studio/review-record/v0", "reviewId": review_id, "target": targets[0],
               "additionalTargets": targets[1:], "readingScope": [self.ref("runs/input/ep-001.md"), *targets],
               "context": "independent", "claimsIndependence": False, "firstReadWithoutAuthorNotes": blind,
               "findings": [], "goalAssessments": []}
        body = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        (self.root / f".drama/reviews").mkdir(parents=True, exist_ok=True)
        (self.root / f".drama/reviews/{review_id}.json").write_bytes(body)
        if sealed:
            self.write(f".drama/reviews/{review_id}.sha256", hashlib.sha256(body).hexdigest() + f"  {review_id}.json\n")

    def receipt(self, n, outcome):
        doc = {"schemaVersion": "drama-studio/remote-receipt/v0", "operation": "create_page", "requestId": f"ep{n:03d}-r1",
               "inputFingerprint": "sha256:" + "a" * 64, "localRef": self.ref(f"runs/b1/ep-{n:03d}.md"),
               "remote": {"projectId": None, "pageId": None, "revision": None, "inputSnapshotId": None},
               "outcome": outcome, "retryAllowed": False, "observedAt": "2026-10-09T11:00:00+08:00", "evidence": "测试"}
        if outcome == "confirmed":
            doc["remote"] = {"projectId": "p1", "pageId": f"page-{n}", "revision": 1, "inputSnapshotId": None}
        self.write(f".drama/receipts/ep{n:03d}-r1.json", json.dumps(doc, ensure_ascii=False))


class SeasonCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, *extra, **season):
        Season(self.root, **season)
        return run("season-check", self.root, "--episodes", "2-3", *extra)

    def rules(self, out):
        return {f["rule"] for f in out["failures"]}

    def test_a_compliant_run_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out["failures"])
        self.assertTrue(out["passed"])
        self.assertEqual(out["perEpisode"]["3"]["authorRun"], "c5-ep3")
        self.assertFalse(out["remote_verified"])

    def test_receipts_pass_contract_check(self):
        Season(self.root)
        for path in (self.root / ".drama/receipts").glob("*.json"):
            code, out = run("contract-check", "remote-receipt", path)
            self.assertTrue(out["passed"], out)

    def test_ten_episodes_in_one_author_run_fail(self):
        code, out = self.check(batch_author=True)
        self.assertEqual(code, 2)
        self.assertIn("one-episode-per-author-run", self.rules(out))

    def test_state_record_not_updated_fails(self):
        code, out = self.check(same_state=True)
        self.assertEqual(code, 2)
        self.assertEqual(self.rules(out), {"state-updated"})

    def test_copied_usage_fails(self):
        code, out = self.check(usage_copied=True)
        self.assertEqual(self.rules(out), {"usage-copied"})

    def test_not_sent_fails_unless_offline_was_agreed(self):
        code, out = self.check(receipt="not_sent")
        self.assertEqual(self.rules(out), {"saved"})
        code, out = run("season-check", self.root, "--episodes", "2-3", "--allow-offline")
        self.assertEqual(code, 0, out["failures"])
        self.assertEqual({w["rule"] for w in out["warnings"]}, {"saved"})

    def test_missing_receipt_fails(self):
        code, out = self.check(receipt=None)
        self.assertEqual(self.rules(out), {"saved"})

    def test_first_read_must_be_blind_and_sealed(self):
        code, out = self.check(sealed=False)
        self.assertEqual(self.rules(out), {"first-read-sealed"})
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        code, out = self.check(blind_first=False)
        self.assertEqual(self.rules(out), {"first-read"})

    def test_missing_upstream_and_c4_fail(self):
        Season(self.root)
        for name in ("c1-1", "c4-1"):
            (self.root / f".drama/runs/{name}.json").unlink()
        code, out = run("season-check", self.root, "--episodes", "2-3")
        self.assertEqual(self.rules(out), {"upstream", "c4"})

    def test_bad_range_is_an_input_error(self):
        Season(self.root)
        code, out = run("season-check", self.root, "--episodes", "5-3")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
