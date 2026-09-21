"""Source authority, fail-closed validation and deterministic BS projection."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/async-xdk'
SPEC = importlib.util.spec_from_file_location('shipyard_async', ROOT / 'tools/shipyard/prepare_async.py')
GEN = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(GEN)


class AsyncGeneration(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='contract-', dir=OUT)
        self.work = Path(self.temporary.name)

    def tearDown(self): self.temporary.cleanup()

    def outputs(self, folder):
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}

    def test_repeat_and_lf_crlf_equivalence(self):
        data = GEN.normalized(GEN.SOURCE.read_bytes())
        lf, crlf = self.work / 'lf.hpp', self.work / 'crlf.hpp'
        lf.write_bytes(data); crlf.write_bytes(data.replace(b'\n', b'\r\n'))
        first, second = self.work / 'first', self.work / 'second'
        GEN.main(lf, first); original = self.outputs(first)
        GEN.main(lf, first); self.assertEqual(original, self.outputs(first))
        GEN.main(crlf, second); self.assertEqual(original, self.outputs(second))
        for raw in original.values(): self.assertNotIn(b'\r\n', raw)

    def test_drift_does_not_overwrite_valid_output(self):
        target = self.work / 'output'; GEN.main(GEN.SOURCE, target)
        before = self.outputs(target)
        source = self.work / 'drift.hpp'; source.write_bytes(GEN.SOURCE.read_bytes() + b'// drift\n')
        with self.assertRaisesRegex(SystemExit, 'Refusing changed BS source'):
            GEN.main(source, target)
        self.assertEqual(before, self.outputs(target))

    def test_helper_drift_before_output(self):
        for relative in GEN.HELPERS:
            target = self.work / 'platform/shipyard' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / 'platform/shipyard' / relative).read_bytes())
        target.write_bytes(target.read_bytes() + b'// unreviewed helper\n')
        saved = GEN.ROOT
        try:
            GEN.ROOT = self.work
            output = self.work / 'scratch/async-xdk/rejected'
            with self.assertRaisesRegex(ValueError, 'helper SHA-256 mismatch'):
                GEN.main(GEN.SOURCE, output)
            self.assertFalse(output.exists())
        finally: GEN.ROOT = saved

    def test_output_restricted_to_owned_scratch(self):
        with self.assertRaisesRegex(ValueError, 'owned scratch'):
            GEN.main(GEN.SOURCE, ROOT / 'libultraship')

    def test_manifest_and_source_authority(self):
        output = self.work / 'manifest'; manifest = GEN.main(GEN.SOURCE, output)
        self.assertEqual(manifest['source_commit'], '097aa718f25d44315cadb80b407144ad455ee4f9')
        self.assertEqual(manifest['helper_sha256'], GEN.HELPERS)
        self.assertEqual(manifest, json.loads((output / 'provenance.json').read_text()))
        source = (output / 'BS_thread_pool.hpp').read_text()
        self.assertIn('#line 1 "platform/shipyard/thread-pool/upstream/BS_thread_pool.hpp"', source)
        self.assertNotIn('Smash360', source)
        self.assertIn('Shipyard::Async::joining_thread', source)


if __name__ == '__main__': unittest.main()
