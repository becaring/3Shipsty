"""Fail-closed locks and reproducible cross-newline source projection."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('shipyard_binary', ROOT / 'tools/shipyard/prepare_binary.py')
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)
OUT = ROOT / 'scratch/binary-xdk'


class BinaryGeneration(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='contract-', dir=OUT)
        self.work = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def source_copy(self, name, newline):
        folder = self.work / name
        for relative in GEN.INPUTS:
            path = folder / relative; path.parent.mkdir(parents=True, exist_ok=True)
            raw = GEN.normalized((ROOT / 'libultraship' / relative).read_bytes())
            path.write_bytes(raw.replace(b'\n', newline))
        return folder

    def outputs(self, folder):
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}

    def test_deterministic_lf_crlf_and_relative_mapping(self):
        first, second = self.work / 'out-lf', self.work / 'out-crlf'
        GEN.generate(self.source_copy('lf', b'\n'), first)
        before = self.outputs(first)
        GEN.generate(self.work / 'lf', first)
        self.assertEqual(before, self.outputs(first))
        GEN.generate(self.source_copy('crlf', b'\r\n'), second)
        self.assertEqual(before, self.outputs(second))
        for name, raw in before.items():
            self.assertNotIn(b'\r\n', raw)
            if name.endswith(('.h', '.cpp')):
                self.assertIn(b'#line 1 "libultraship/', raw)
                self.assertNotIn(b'D:/', raw)
                self.assertNotIn(b'Smash360', raw)

    def test_last_source_drift_writes_nothing(self):
        source = self.source_copy('drift', b'\n')
        path = source / list(GEN.INPUTS)[-1]
        path.write_bytes(path.read_bytes() + b'// unreviewed drift\n')
        target = self.work / 'rejected'
        with self.assertRaisesRegex(ValueError, 'source SHA-256 mismatch'):
            GEN.generate(source, target)
        self.assertFalse(target.exists())

    def test_anchor_drift_fails_even_without_lock_check(self):
        relative = 'src/ship/utils/binarytools/MemoryStream.cpp'
        raw = GEN.normalized((ROOT / 'libultraship' / relative).read_bytes())
        raw = raw.replace(b'mBufferSize = 0;', b'mBufferSize = 1;', 1)
        with self.assertRaisesRegex(ValueError, 'default MemoryStream constructor changed'):
            GEN.transform(relative, raw, Path('libultraship') / relative)

    def test_helper_drift_rejected_before_output(self):
        helper_dir = self.work / 'platform/shipyard/binary'
        helper_dir.mkdir(parents=True)
        for name in GEN.HELPERS:
            (helper_dir / name).write_bytes((ROOT / 'platform/shipyard/binary' / name).read_bytes())
        path = helper_dir / 'compat.h'; path.write_bytes(path.read_bytes() + b'// drift\n')
        saved_root = GEN.ROOT
        try:
            GEN.ROOT = self.work
            target = self.work / 'scratch/binary-xdk/rejected'
            with self.assertRaisesRegex(ValueError, 'helper SHA-256 mismatch'):
                GEN.generate(ROOT / 'libultraship', target)
            self.assertFalse(target.exists())
        finally:
            GEN.ROOT = saved_root

    def test_outside_owned_scratch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'owned scratch'):
            GEN.generate(ROOT / 'libultraship', ROOT / 'libultraship')

    def test_manifest_covers_owned_source_and_helpers(self):
        target = self.work / 'manifest'
        result = GEN.generate(ROOT / 'libultraship', target)
        self.assertEqual(set(result['files']), set(GEN.INPUTS))
        self.assertEqual(result['helper_sha256'], GEN.HELPERS)
        self.assertEqual(result['libultraship_commit'], 'fdcaf6336776d24a6408d016b0a52243f108f250')
        self.assertEqual(json.loads((target / 'manifest.json').read_text()), result)


if __name__ == '__main__':
    unittest.main()
