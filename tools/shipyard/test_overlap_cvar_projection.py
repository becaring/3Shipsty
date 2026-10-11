"""Exercise frozen renderer reads against the selected typed CVar projection."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OverlapCvarProjectionTests(unittest.TestCase):
    def test_all_readers_use_owned_snapshot(self):
        from prepare_console_variables import transform

        header_name = "include/ship/config/ConsoleVariable.h"
        source_name = "src/ship/config/ConsoleVariable.cpp"
        header = transform(
            header_name, (ROOT / "libultraship" / header_name).read_text()
        )
        source = transform(
            source_name, (ROOT / "libultraship" / source_name).read_text()
        )
        self.assertIn("void CaptureSnapshot(Snapshot& snapshot) const;", header)
        self.assertIn("void UseSnapshot(const Snapshot* snapshot) const;", header)
        self.assertEqual(
            source.count("const Snapshot& variables = ReadVariables();"), 6
        )
        self.assertIn(
            "copy->String = original.String ? strdup(original.String) : nullptr;",
            source,
        )
        self.assertIn("std::shared_ptr<CVar>& copy = snapshot[cursor->first];", source)
        self.assertNotIn("snapshot.clear();", source)
        self.assertIn("overlapSnapshotOwner == this && overlapSnapshot", source)


if __name__ == "__main__":
    unittest.main()
