"""Interrupted regeneration must reuse verified stages without clearing them."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import regenerate_all as regeneration


class ResumeReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log_dir = self.root / "scratch/final-regeneration"
        self.log_dir.mkdir(parents=True)
        self.old_root, self.old_stages = regeneration.ROOT, regeneration.STAGES
        regeneration.ROOT = self.root
        regeneration.STAGES = [("first.py", []), ("second.py", ["--build"])]
        self.addCleanup(self.restore)

    def restore(self):
        regeneration.ROOT, regeneration.STAGES = self.old_root, self.old_stages

    def row(self, number, script, options, exit_code=0):
        log = self.log_dir / f"{number:02d}-{Path(script).stem}.log"
        log.write_text(f"stage {number}\n", encoding="utf-8")
        return {"script": script, "options": options, "exit": exit_code,
                "log": log.relative_to(self.root).as_posix(),
                "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}

    def test_resume_failed_last_stage_without_repeating_prefix(self):
        receipt = {"stages": [self.row(1, "first.py", []),
                              self.row(2, "second.py", ["--build"], 1)]}
        self.assertEqual(regeneration.completed_prefix(receipt, self.log_dir), 1)
        self.assertEqual(len(receipt["stages"]), 1)

    def test_rejects_changed_log(self):
        row = self.row(1, "first.py", [])
        (self.log_dir / "01-first.log").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "log drift"):
            regeneration.completed_prefix({"stages": [row]}, self.log_dir)

    def test_rejects_changed_stage_order(self):
        row = self.row(1, "first.py", [])
        row["script"] = "other.py"
        with self.assertRaisesRegex(ValueError, "stage order"):
            regeneration.completed_prefix({"stages": [row]}, self.log_dir)

    def test_scoped_git_preflight_keeps_global_config_unchanged(self):
        self.restore()
        env = regeneration.scoped_git_environment()
        self.assertGreaterEqual(int(env["GIT_CONFIG_COUNT"]), 1)
        self.assertIn(regeneration.ROOT.resolve().as_posix(), env.values())

    def test_source_lock_preflight_catches_shared_header_drift(self):
        source = self.root / "soh/soh/SohGui/UIWidgets.hpp"
        source.parent.mkdir(parents=True)
        source.write_text("button option\n", encoding="utf-8")
        lock = self.root / "platform/shipyard/soh-ui/sources.lock.json"
        lock.parent.mkdir(parents=True)
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        lock.write_text(json.dumps({"sources": {"soh/soh/SohGui/UIWidgets.hpp": expected},
                                    "producer": {"files": {"soh/soh/SohGui/UIWidgets.hpp": "0" * 64}}}),
                        encoding="utf-8")
        self.assertEqual(regeneration.preflight_source_locks(), 1)
        source.write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source lock drift"):
            regeneration.preflight_source_locks()


if __name__ == "__main__":
    unittest.main()
