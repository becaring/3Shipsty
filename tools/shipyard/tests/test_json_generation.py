import unittest,runpy,json,hashlib,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
M=runpy.run_path(str(ROOT/'tools/shipyard/prepare_json.py'))
from cpp_ast import PARSER, walk


def cpp_tokens(text):
    return [(node.type, node.text) for node in walk(PARSER.parse(text.encode()).root_node)
            if not node.children]

class GenerationTests(unittest.TestCase):
    def test_deterministic(self):
        one=M['generate']();two=M['generate']();self.assertEqual(one,two)
    def test_shared_outputs_reproducible_from_clean_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch/json-xdk') as folder:
            output=Path(folder)
            first=M['generate'](output=output)
            shared=first['shipyard']
            expected={
                **{Path(name).stem+'.hpp':record['output_sha256'] for name,record in shared['algorithms'].items()},
                **{'stream_writer.hpp':record['output_sha256'] for record in shared['streams'].values()},
                **shared['ordered']['generated_sha256'],
            }
            self.assertEqual(len(expected),5)
            for name,digest in expected.items():
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),digest)
            (output/'lexer.hpp').write_bytes(b'corrupt generated output')
            second=M['generate'](output=output)
            self.assertEqual(first,second)
            for name,digest in expected.items():
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),digest)
    def test_reject_output_escape(self):
        with self.assertRaisesRegex(ValueError,'output must remain'):M['generate'](output=ROOT/'scratch/not-json')
    def test_reject_changed_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch/json-xdk') as folder:
            source=Path(folder);p=source/'include/nlohmann/detail/input/lexer.hpp';p.parent.mkdir(parents=True);p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'lexer source mismatch'):M['generate'](source=source)
    def test_actual_save_template_source_still_matches(self):
        evidence=json.loads((Path(__file__).parent/'test_json/save-template-source.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT/evidence['source']).read_bytes()).hexdigest(),evidence['sha256'])
        source=(ROOT/evidence['source']).read_text();contract=(Path(__file__).parent/'test_json/modern_save_contract.cpp').read_text()
        for name in evidence['methods']:
            start=source.index('    template <typename T> void '+name);opening=source.index(' {',start)+1;depth=1;end=opening+1
            while depth:
                if source[end]=='{':depth+=1
                elif source[end]=='}':depth-=1
                end+=1
            expected = cpp_tokens(source[start:end])
            selected = cpp_tokens(contract)
            self.assertTrue(any(selected[i:i + len(expected)] == expected for i in range(len(selected))),
                            'Save template tokens changed: ' + name)
    def test_actual_enum_sources_and_probe(self):
        manifest=M['generate']()['containers']
        self.assertEqual(len(manifest['source_sha256']),3)
        probe=(M['OUT']/'modern_enum_contract.cpp').read_text()
        evidence=json.loads((M['BACKEND']/'container-consumer-source.json').read_text())
        for line in evidence['consumer_statements']:self.assertIn(line,probe)
        self.assertIn('RC_LINKS_POCKET',probe)
        self.assertIn('RCSHOW_SAVED',probe)
    def test_stream_sources_and_reached_statements(self):
        evidence=json.loads((M['BACKEND']/'stream-consumer-source.json').read_text())
        probe=(Path(__file__).parent/'test_json/stream_contract.cpp').read_text()
        for rel,record in evidence['sources'].items():
            source=ROOT/rel
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),record['sha256'])
            for statement in record['statements']:
                self.assertIn(statement,source.read_text())
                self.assertIn(statement,probe)
        manifest=M['generate']()['shipyard']['streams']
        self.assertIn('detail/output/serializer.hpp',manifest)
    def test_reject_changed_serializer_source(self):
        generator=runpy.run_path(str(M['PLATFORM_BASE']/'python/xbox360_platform/json/generate_streams.py'))['generate']
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch/json-xdk') as folder:
            source=Path(folder);p=source/'include/nlohmann/detail/output/serializer.hpp'
            p.parent.mkdir(parents=True);p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'serializer source mismatch'):
                generator(source,M['OUT'])
    def test_ordered_generation_and_consumer_projection(self):
        manifest=M['generate']()
        self.assertTrue(manifest['shipyard']['ordered']['distinct_from_sorted_json'])
        generated=M['OUT']
        original=(generated/'ordered_consumer_original.cpp').read_text()
        for statement in manifest['ordered_consumers']['extracted_statements']:
            self.assertIn(statement,original)
        self.assertIn('ordered_object(entranceMembers',(generated/'ordered_consumer_projected.cpp').read_text())
    def test_reject_changed_ordered_consumer(self):
        generator=runpy.run_path(str(M['BACKEND']/'generate_ordered_consumers.py'))['generate']
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch/json-xdk') as folder:
            evidence=json.loads((M['BACKEND']/'ordered-consumer-source.json').read_text())
            source=Path(folder);first=next(iter(evidence['sources']))
            p=source/first;p.parent.mkdir(parents=True);p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'ordered consumer SHA-256 mismatch'):
                generator(M['OUT'],source)
    def test_reject_changed_ordered_map(self):
        generator=runpy.run_path(str(M['PLATFORM_BASE']/'python/xbox360_platform/json/generate_ordered.py'))['generate']
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch/json-xdk') as folder:
            source=Path(folder);p=source/'include/nlohmann/ordered_map.hpp'
            p.parent.mkdir(parents=True);p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'ordered_map source mismatch'):
                generator(source,M['OUT'])
    def test_reject_changed_enum_source(self):
        generator=runpy.run_path(str(M['BACKEND']/'generate_containers.py'))['generate']
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch/json-xdk') as folder:
            evidence=json.loads((M['BACKEND']/'container-consumer-source.json').read_text())
            source=Path(folder);first=next(iter(evidence['sources']))
            p=source/first;p.parent.mkdir(parents=True);p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'consumer SHA-256 mismatch'):
                generator(M['OUT'],source)
if __name__=='__main__':unittest.main()
