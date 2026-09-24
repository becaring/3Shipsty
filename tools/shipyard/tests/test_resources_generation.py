"""Determinism, line mapping and fail-closed tests for resource leaf generation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('resource_projection',ROOT/'tools/shipyard/prepare_resources.py')
GEN=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(GEN)


class Generation(unittest.TestCase):
    def setUp(self):
        scratch=ROOT/'scratch/resources-xdk';scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.output=self.root/'generated'
        lock=json.loads((GEN.BASE/'sources.lock.json').read_text())
        for rel in lock['sources']:
            dest=self.source/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/'libultraship'/rel).read_bytes())

    def tearDown(self):self.temp.cleanup()
    def generate(self):return GEN.generate(self.source,self.output)

    def test_deterministic_and_mapping(self):
        first=self.generate();saved={str(p.relative_to(self.output)):p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(first,self.generate())
        self.assertEqual(saved,{str(p.relative_to(self.output)):p.read_bytes() for p in self.output.rglob('*') if p.is_file()})
        for relative,record in first['files'].items():
            generated=(self.output/relative).read_text()
            original=GEN.normalize((self.source/relative).read_bytes()).splitlines(keepends=True)
            for edit in record['edits']:
                self.assertEqual(original[edit['source_line']-1],edit['original'])
                self.assertIn('#line '+str(edit['source_line']+1)+' "libultraship/'+relative+'"',generated)

    def test_newlines_and_bom(self):
        first=self.generate()
        for p in self.source.rglob('*'):
            if p.is_file():p.write_bytes(b'\xef\xbb\xbf'+GEN.normalize(p.read_bytes()).replace('\n','\r\n').encode())
        self.assertEqual(first,self.generate())

    def test_changed_source_is_rejected_before_output(self):
        target=self.source/'src/ship/resource/factory/BlobFactory.cpp'
        target.write_bytes(target.read_bytes()+b'\n// changed\n')
        with self.assertRaisesRegex(ValueError,'Source hash mismatch'):self.generate()
        self.assertFalse(self.output.exists())

    def test_generation_uses_shared_variant_without_local_helper(self):
        self.generate()
        text=(self.output/'include/ship/resource/File.h').read_text()
        self.assertIn('#include <xbox_compat/variant.h>',text)
        self.assertIn('xbox_compat::variant<',text)

    def test_output_outside_scratch_rejected(self):
        with self.assertRaisesRegex(ValueError,'owned scratch'):
            GEN.generate(self.source,ROOT/'platform/shipyard/resources/should-not-exist')

if __name__=='__main__':unittest.main()
