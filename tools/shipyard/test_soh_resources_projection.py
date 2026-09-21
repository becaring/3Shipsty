"""Projection determinism and fail-closed source drift; writes only owned scratch."""
import json
from pathlib import Path
import tempfile
import unittest
from prepare_soh_resources import ROOT, OUT, OWN, prepare, transform
from cpp_ast import PARSER, walk


class Projection(unittest.TestCase):
    def test_all_production_functions_retained(self):
        lock = json.loads((OWN / 'sources.lock.json').read_text())
        for name in lock['sources']:
            if not name.endswith('.cpp'):
                continue
            original = (ROOT / name).read_text(encoding='utf-8-sig')
            def signatures(text):
                return [n.text.decode().split('{', 1)[0].strip()
                        for n in walk(PARSER.parse(text.encode()).root_node)
                        if n.type == 'function_definition']
            self.assertEqual(signatures(original), signatures(transform(name, original)), name)

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

    def test_source_provenance_and_audio_endian(self):
        lock = json.loads((OWN / 'sources.lock.json').read_text())
        self.assertEqual(lock['source_commit'], 'cb71e22a79bc5d1f688fa881795bbd93094895fc')
        name = 'soh/soh/resource/importer/AudioSoundFontFactory.cpp'
        source = (ROOT / name).read_text(encoding='utf-8-sig')
        projected = transform(name, source)
        self.assertEqual(projected.count('BE16SWAP('), 6)
        self.assertNotIn('BSWAP16(', projected)
        name = 'soh/soh/resource/importer/AudioSequenceFactory.cpp'
        source = (ROOT / name).read_text(encoding='utf-8-sig')
        projected = transform(name, source)
        self.assertIn('writer.SetEndianness(Ship::Endianness::Big);', projected)
        self.assertEqual(source.count('ReadResource('), projected.count('ReadResource('))


if __name__ == '__main__': unittest.main()
