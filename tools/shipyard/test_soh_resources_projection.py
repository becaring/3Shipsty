"""Projection determinism and fail-closed source drift; writes only owned scratch."""
import json
from pathlib import Path
import tempfile
import unittest
from prepare_soh_resources import ROOT, OUT, OWN, prepare, transform


class Projection(unittest.TestCase):
    def test_deterministic(self):
        one = prepare()
        paths = [OUT / 'generated' / n for n in one['generated_sha256']]
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(one, prepare())
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths})

    def test_drift_is_atomic(self):
        lock = json.loads((OWN / 'sources.lock.json').read_text())
        with tempfile.TemporaryDirectory(dir=OUT) as root:
            source = Path(root) / 'source'; output = Path(root) / 'output'
            for name in lock['sources']:
                dest = source / name; dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((ROOT / name).read_bytes())
            last = source / list(lock['sources'])[-1]
            last.write_text(last.read_text() + '\n// input drift\n')
            with self.assertRaisesRegex(ValueError, 'source drift'):
                prepare(source, output)
            self.assertFalse(output.exists())

    def test_cutscene_endian_helpers_are_verbatim(self):
        name = 'soh/soh/resource/importer/CutsceneFactory.cpp'
        text = (ROOT / name).read_text()
        helpers = text[text.index('static inline'):text.index('namespace SOH')]
        self.assertIn(helpers, transform(name, text))
        self.assertEqual(helpers.count('GetEndianness() != Ship::Endianness::Native'), 3)


if __name__ == '__main__': unittest.main()
