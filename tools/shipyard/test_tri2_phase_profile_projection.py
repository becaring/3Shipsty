"""TRI2 phase sampling boundaries without changing triangle execution."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tri2_pair_projection import transform


class Tri2PhaseProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()

    def test_handler_and_both_triangles_have_disjoint_phase_boundaries(self):
        changed = transform(self.source)
        self.assertEqual(transform(changed), changed)
        handler = changed.split('bool gfx_tri2_handler_f3dex(', 1)[1].split('\n}', 1)[0]
        cull = changed.split('void Interpreter::GfxSpTri1(', 1)[1].split('\n}', 1)[0]
        emitter = changed.split('void Interpreter::XboxEmitTriangle(', 1)[1].split('\n}', 1)[0]
        self.assertIn('BeginTri2(sample);', handler)
        self.assertIn('EndTri2(sample);', handler)
        self.assertLess(cull.index('Tri2Materialize'), cull.index('XboxMaterializeVertex(vtx1_idx);'))
        self.assertLess(cull.index('Tri2Pipeline'), cull.index('XboxEmitTriangle(vtx1_idx'))
        self.assertLess(cull.index('XboxEmitTriangle(vtx1_idx'), cull.index('Tri2Cull'))
        self.assertLess(emitter.index('XboxPrepareTrianglePipeline();'), emitter.index('Tri2Pack'))
        self.assertLess(emitter.index('Tri2Flush'), emitter.index('        Flush();'))
        self.assertIn('sModernTri2Sample', changed)


if __name__ == '__main__':
    unittest.main()
