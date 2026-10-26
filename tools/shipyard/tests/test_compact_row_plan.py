"""Check the projected compact emitter against the reference byte stream."""

import os
from pathlib import Path
import test_compact_triangles as contracts
from compact_row_plan_projection import effective_source


class CompactRowPlan(contracts.CompactTriangles):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.environ.get('FAST3D_CONTRACT_SOURCE'):
            cls.source = Path(os.environ['FAST3D_CONTRACT_SOURCE']).read_text()
        if 'bool compactPack[3]' not in cls.source:
            cls.source = effective_source(cls.source)
        cls.out = cls.out.parent / 'compact-row-plan-contract'
        cls.out.mkdir(parents=True, exist_ok=True)

    def test_cached_triangles_skip_material_plan(self):
        fixture = self.indexed_fixture(contracts.NONADJACENT_MAIN)
        fixture = fixture.replace('const LoadedVertex input[3],bool is_rect)',
                                  'const LoadedVertex input[3],bool is_rect,const unsigned* indices=NULL)')
        for i in range(3):
            fixture = fixture.replace('&input[' + str(i) + ']',
                                      '&input[indices ? indices[' + str(i) + '] : ' + str(i) + ']')
        fixture = 'static unsigned materialPlans;\n' + fixture
        fixture = fixture.replace('    unsigned char shipyardPlanKind[16];',
                                  '    ++materialPlans;\n    unsigned char shipyardPlanKind[16];')
        fixture = fixture.replace('    assert(expected.size()==b.submitted.size());',
                                  '    assert(materialPlans == 6);\n    assert(expected.size()==b.submitted.size());')
        self.run_fixture('cached-plan-count', fixture)


if __name__ == '__main__':
    import unittest
    unittest.main()
