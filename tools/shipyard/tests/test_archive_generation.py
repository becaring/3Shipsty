import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
import dependency_sources
import prepare_archives


class ArchiveGeneration(unittest.TestCase):
    def test_deterministic_projection(self):
        first = prepare_archives.prepare()
        second = prepare_archives.prepare()
        self.assertEqual(first, second)
        self.assertIn("zip_open.c", first["units"])
        self.assertIn("zip_close.c", first["units"])

    def test_committed_receipt_and_source_drift_rejected(self):
        original = dependency_sources.ROOT
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as name:
            root = Path(name)
            (root / "scratch/deps/example").mkdir(parents=True)
            (root / "platform/shipyard").mkdir(parents=True)
            source = root / "scratch/deps/example/file.c"
            source.write_bytes(b"original")
            receipt = root / "scratch/deps/example-receipt.json"
            receipt.write_text(json.dumps(dict(files={"file.c": hashlib.sha256(source.read_bytes()).hexdigest()})))
            (root / "platform/shipyard/dependencies.lock.json").write_text(
                json.dumps({"example": {"receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}})
            )
            dependency_sources.ROOT = root
            try:
                self.assertEqual(dependency_sources.verified("example"), source.parent)
                source.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "source drift"):
                    dependency_sources.verified("example")
                receipt.write_text("{}")
                with self.assertRaisesRegex(ValueError, "receipt drift"):
                    dependency_sources.verified("example")
            finally:
                dependency_sources.ROOT = original


if __name__ == "__main__":
    unittest.main()
