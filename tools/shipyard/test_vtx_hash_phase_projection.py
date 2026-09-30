"""Check opcode 0x32 timing coverage on the selected projected interpreter."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtx_hash_phase_projection import transform


class VtxHashProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()

    def test_handler_routes_and_deferred_recursion(self):
        projected = transform(self.source)
        self.assertEqual(transform(projected), projected)
        handler = projected.split('bool gfx_vtx_hash_handler_custom(', 1)[1].split('\n}', 1)[0]
        deferred = projected.split('bool Interpreter::XboxTryDeferVertices(', 1)[1].split('\n}', 1)[0]
        vertex = projected.split('void Interpreter::GfxSpVertex(', 1)[1].split('\n}', 1)[0]
        self.assertEqual(handler.count('BeginVtxHash(sample);'), 1)
        self.assertEqual(handler.count('EndVtxHash(sample);'), 1)
        self.assertLess(handler.index('VtxHashLookup'), handler.index('GetResourceRawPointer(hash)'))
        self.assertIn('VtxHashPointer', handler)
        self.assertIn('VtxHashResolved', handler)
        self.assertIn('VtxHashMissing', handler)
        self.assertLess(deferred.index('VtxHashTransform'), deferred.index('GfxSpVertex(n_vertices, dest_index, vertices);'))
        self.assertLess(deferred.index('VtxHashInsert'), deferred.index('pending.source = vertices[i];'))
        self.assertLess(vertex.index('VtxHashDeferred'), vertex.index('XboxTryDeferVertices(n_vertices'))
        self.assertLess(vertex.index('XboxTryDeferVertices(n_vertices'), vertex.index('VtxHashTransform'))
        self.assertIn('sModernVtxHashSample->vmx = shipyardVectorPositions;', vertex)


if __name__ == '__main__':
    unittest.main()
