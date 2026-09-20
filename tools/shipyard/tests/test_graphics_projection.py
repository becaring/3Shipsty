import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('graphics', ROOT / 'tools/shipyard/prepare_graphics.py')
graphics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(graphics)


class GraphicsProjectionTests(unittest.TestCase):
    def test_pinned_inputs_and_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            report = graphics.prepare(out=out)
            self.assertEqual(report['shader_key_widths'], [64, 32])
            api = (out / 'include/fast/backends/gfx_rendering_api.h').read_text()
            self.assertIn('CreateAndLoadNewShader(uint64_t shaderId0, uint32_t shaderId1)', api)
            self.assertNotIn('ShaderProgramKey', api)
            self.assertNotIn(' = default;', api)
            self.assertNotIn('mSrgbMode = false', api)
            self.assertIn('mSrgbMode(false)', api)
            decoder = (out / 'cc_features.cpp').read_text()
            original = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text()
            self.assertIn(graphics.decoder_function(original), decoder)
            self.assertNotIn('Smash360_', (out / 'shader_lower.cpp').read_text())

    def test_rejects_source_drift(self):
        with self.assertRaisesRegex(ValueError, 'source drift'):
            graphics.check_source(b'changed source', '0' * 64, 'test')

    def test_rejects_ambiguous_projection_anchor(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            graphics.replace_once('duplicated duplicated', 'duplicated', 'replacement')

    def test_all_virtual_contracts_preserved(self):
        for name in ('gfx_rendering_api.h', 'gfx_window_manager_api.h'):
            text = (ROOT / 'libultraship/include/fast/backends' / name).read_text()
            projected = graphics.lower_api(text, 'GfxRenderingAPI' if name == 'gfx_rendering_api.h' else 'GfxWindowBackend')
            self.assertEqual(graphics.virtual_contracts(text), graphics.virtual_contracts(projected))


if __name__ == '__main__':
    unittest.main()
