"""Modern combiner lookup split against its pinned two-field behavior."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
BASE = resolve(ROOT)
sys.path.insert(0, str(BASE / 'python'))
sys.path.insert(0, str(BASE / 'tests'))
from xbox360_platform import combiner_lookup
from combiner_lookup_contract import exercise
import prepare_fast3d


class ModernCombinerLookupTests(unittest.TestCase):
    def test_real_two_field_lookup_and_adapter(self):
        header = (ROOT / 'libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        generated_header, _, _ = prepare_fast3d.header(header)
        self.assertIn('XboxLookupColorCombinerCold(const ColorCombinerKey& key);', generated_header)
        self.assertIs(prepare_fast3d.combiner_lookup.transform, combiner_lookup.transform)
        exercise(self, source, header, combiner_lookup.transform(source),
                 ROOT / 'scratch/fast3d-combiner-lookup-contract',
                 ('{1,2}', '{1,4}', '{2,2}', '{2,4}'))


if __name__ == '__main__':
    unittest.main()
