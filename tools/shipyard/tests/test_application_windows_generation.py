"""Keep collision geometry's positional tuple reads out of variant lowering."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import prepare_application_windows as generation


class CollisionTupleTests(unittest.TestCase):
    def test_real_sphere_face_tuple_reads_keep_std_get(self):
        name = generation.DEBUG + 'colViewer.cpp'
        original = (ROOT / name).read_text(encoding='utf-8-sig')
        projected = generation.project(name, original)
        pattern = r'std::get<([012])>\(faces\[faceIndex\]\)'
        self.assertEqual(re.findall(pattern, original), ['0', '1', '2'])
        self.assertEqual(re.findall(pattern, projected), re.findall(pattern, original))
        self.assertNotRegex(projected, r'xbox_compat::get<[012]>')


if __name__ == '__main__':
    unittest.main()
