"""Consumer boundary for Shipyard's source-locked BS projection."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
OUT = ROOT / 'scratch/async-xdk'
SPEC = importlib.util.spec_from_file_location('shipyard_async', ROOT / 'tools/shipyard/prepare_async.py')
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)


class AsyncGeneration(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='contract-', dir=OUT)
        self.work = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def outputs(self, folder):
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}

    def test_repeat_and_lf_crlf_equivalence(self):
        data = GEN.SOURCE.read_bytes().replace(b'\r\n', b'\n')
        lf, crlf = self.work / 'lf.hpp', self.work / 'crlf.hpp'
        lf.write_bytes(data)
        crlf.write_bytes(data.replace(b'\n', b'\r\n'))
        first, second = self.work / 'first', self.work / 'second'
        GEN.main(lf, first)
        original = self.outputs(first)
        GEN.main(lf, first)
        self.assertEqual(original, self.outputs(first))
        GEN.main(crlf, second)
        self.assertEqual(original, self.outputs(second))

    def test_drift_does_not_overwrite_valid_output(self):
        target = self.work / 'output'
        GEN.main(GEN.SOURCE, target)
        before = self.outputs(target)
        source = self.work / 'drift.hpp'
        source.write_bytes(GEN.SOURCE.read_bytes() + b'// drift\n')
        with self.assertRaisesRegex(ValueError, 'Refusing changed BS source'):
            GEN.main(source, target)
        self.assertEqual(before, self.outputs(target))

    def test_output_restricted_to_owned_scratch(self):
        with self.assertRaisesRegex(ValueError, 'owned scratch'):
            GEN.main(GEN.SOURCE, ROOT / 'libultraship')

    def test_manifest_and_source_authority(self):
        output = self.work / 'manifest'
        manifest = GEN.main(GEN.SOURCE, output)
        self.assertEqual(manifest, json.loads((output / 'provenance.json').read_text()))
        source = (output / 'BS_thread_pool.hpp').read_text()
        self.assertIn('Shipyard::Async::joining_thread', source)
        self.assertNotIn('Smash360', source)


if __name__ == '__main__':
    unittest.main()
