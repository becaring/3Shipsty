"""The active Fast3D projection must invoke the physical Shipyard lowerer."""
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import prepare_fast3d


class OpcodeOwnershipTests(unittest.TestCase):
    def test_empty_opcode_table_is_rejected(self):
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        changed, count = re.subn(r'(static constexpr UcodeHandler rdpHandlers = \{).*?(\n\};)',
                                 r'\1\n\2', source, count=1, flags=re.S)
        self.assertEqual(count, 1)
        with self.assertRaisesRegex(ValueError, 'Empty opcode table'):
            prepare_fast3d.opcode_tables(changed)

    def test_current_interpreter_depends_on_shipyard_lowerer(self):
        from xbox360_platform import fast3d_opcode
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        with patch.object(fast3d_opcode, 'lower', side_effect=RuntimeError('shared opcode lowerer reached')):
            with self.assertRaisesRegex(RuntimeError, 'shared opcode lowerer reached'):
                prepare_fast3d.opcode_tables(source)

    def test_current_triangle_split_depends_on_shipyard(self):
        from xbox360_platform import fast3d_triangle_split
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        with patch.object(fast3d_triangle_split, 'transform', side_effect=RuntimeError('shared triangle split reached')):
            with self.assertRaisesRegex(RuntimeError, 'shared triangle split reached'):
                prepare_fast3d.triangle_split(source)

    def test_member_defaults_depend_on_shipyard_collector(self):
        with patch.object(prepare_fast3d, 'collect_member_defaults',
                          side_effect=RuntimeError('shared member collector reached')):
            with self.assertRaisesRegex(RuntimeError, 'shared member collector reached'):
                prepare_fast3d.member_defaults('struct State { int count = 4; };', 'State')

    def test_triangle_split_preserves_cull_prefix_and_emission_body(self):
        from xbox360_platform import fast3d_triangle_split
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = prepare_fast3d.triangle_split(source)
        start = source.index(fast3d_triangle_split.SIGNATURE)
        end = source.index(fast3d_triangle_split.NEXT_METHOD, start)
        original = source[start:end]
        transformed = projected[start:projected.index(fast3d_triangle_split.NEXT_METHOD, start)]
        boundary = prepare_fast3d.TRIANGLE_SPLIT_BOUNDARY
        self.assertEqual(transformed.split('    XboxEmitTriangle(', 1)[0], original.split(boundary, 1)[0])
        self.assertIn(original.split(boundary, 1)[1], transformed)
        self.assertEqual(transformed.count(boundary), 1)

    def test_texture_binding_uses_physical_tracker(self):
        header = (ROOT / 'libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected_header = prepare_fast3d.header(header)[0]
        projected_source = prepare_fast3d.texture_bindings(source)
        self.assertIn('#include "fast3d/texture_bindings.h"', projected_header)
        self.assertIn('Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES>', projected_header)
        self.assertIn('mXboxTextureBindings.NeedsSelect(i,node,it->second.texture_id,sampler)', projected_source)
        self.assertIn('mXboxTextureBindings.NeedsSampler(i,desiredSampler)', projected_source)
        self.assertIn('mXboxTextureBindings.SamplerChanged(i,desiredSampler)', projected_source)

    def test_triangle_certificate_uses_physical_header_and_modern_traits(self):
        header = (ROOT / 'libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        projected = prepare_fast3d.header(header)[0]
        self.assertIn('#include "fast3d/triangle_traits.h"', projected)
        self.assertIn('#include "fast3d/triangle_pipeline.h"', projected)
        self.assertIn('XboxTrianglePipelineKey mXboxPipelineKey;', projected)
        self.assertFalse((ROOT / 'platform/shipyard/fast3d/triangle_pipeline.h').exists())


if __name__ == '__main__':
    unittest.main()
