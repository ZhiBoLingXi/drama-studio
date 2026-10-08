"""Receipts and cache against real mali-story v0.20.0 page responses (tests/fixtures/mcp-pages, recorded 2026-10-08)."""
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ["python3", "-B", str(ROOT / "skills/drama-studio/scripts/drama_tools.py")]
FIX = ROOT / "tests/fixtures/mcp-pages"
PAGE = "76681133-9e48-4010-b9ff-4d7dfb4e69dd"


def run(*args):
    r = subprocess.run(TOOL + [str(a) for a in args], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout or r.stderr)


class RealPageFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = pathlib.Path(self.tmp.name) / "proj"
        subprocess.run(TOOL + ["init-project", str(self.project), "--title", "页面实测"], check=True, capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, stem, operation, request_id):
        return run("receipt", "record", self.project, FIX / f"{stem}.response.json", "--operation", operation,
                   "--request-id", request_id, "--input", FIX / f"{stem}.input.json")

    def test_writes_are_confirmed_with_page_and_revision(self):
        for stem, op, rid, rev in (("01-create", "create_page", "d5-page-probe-create", 1),
                                   ("02-update", "update_page", "d5-page-probe-update-r2", 2),
                                   ("07-restore", "restore_page", "d5-page-probe-restore-r1", 3)):
            code, out = self.record(stem, op, rid)
            self.assertEqual(code, 0, out)
            self.assertEqual(out["receipt"]["outcome"], "confirmed")
            self.assertEqual(out["receipt"]["remote"]["pageId"], PAGE)
            self.assertEqual(out["receipt"]["remote"]["revision"], rev)

    def test_bare_409_envelope_is_a_rejected_conflict(self):
        code, out = self.record("03-update-stale", "update_page", "d5-page-probe-update-stale")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["receipt"]["outcome"], "rejected_conflict")
        code, pending = run("receipt", "pending", self.project)
        self.assertEqual(pending["pending"], [])

    def test_chunked_read_caches_verified_by_fingerprint(self):
        code, out = run("receipt", "cache", self.project, FIX / "04-read-1.response.json", FIX / "04-read-2.response.json",
                        "--title", "页面探测（#34）")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["verified"])
        self.assertEqual(out["entry"]["path"], f".drama/cache/{PAGE}@r2.md")

    def test_receipts_pass_contract_check(self):
        self.record("01-create", "create_page", "d5-page-probe-create")
        self.record("03-update-stale", "update_page", "d5-page-probe-update-stale")
        for f in (self.project / ".drama/receipts").glob("*.json"):
            code, out = run("contract-check", "remote-receipt", f)
            self.assertTrue(out["passed"], (f.name, out))

    def test_fixture_fingerprints_match_the_text(self):
        import hashlib
        a = json.loads((FIX / "04-read-1.response.json").read_text(encoding="utf-8"))["data"]
        b = json.loads((FIX / "04-read-2.response.json").read_text(encoding="utf-8"))["data"]
        body = a["text"] + b["text"]
        self.assertEqual("sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest(), a["fingerprint"])


if __name__ == "__main__":
    unittest.main()
