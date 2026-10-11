"""Run the generated texture handler and native depth reader against their prior behavior."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
import texture_replay_projection as texture
from test_material_replay import compile_run

BASE = resolve(ROOT)
SOURCE = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'


def method(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2]


class TextureDepthReplayTests(unittest.TestCase):
    def test_generated_texture_command_equivalence_and_lifetime(self):
        text = SOURCE.read_text()
        slow = method(text, 'static __declspec(noinline) bool ModernResolveTextureHash(')
        reference = slow.replace('ModernResolveTextureHash', 'ReferenceTextureHash')
        reference = reference.replace('            if (sModernTextureReplays)\n'
                                      '                sModernTextureReplays->Store(gfx, hash, fileName, texFlags, rawTexMetadata);\n', '')
        wrapper = method(text, 'bool gfx_set_timg_otr_hash_handler_custom(')
        fixture = Path(__file__).with_name('test_texture_replay.cpp').read_text()
        fixture = fixture.replace('// GENERATED', texture.HELPERS + '\n' + reference + '\n' + slow + '\n' + wrapper)
        compile_run(self, fixture)

    def test_invalidation_and_native_build_routes(self):
        text = SOURCE.read_text()
        for signature in ('void Interpreter::TextureCacheClear()', 'void Interpreter::TextureCacheDelete(',
                          'void Interpreter::RunGuiOnly()'):
            self.assertIn('ModernClearTextureReplays();', method(text, signature))
        self.assertIn('delete sModernTextureReplays;', method(text, 'Interpreter::~Interpreter()'))
        for signature, call in [('void ModernVertexReuseBeginBatch(', 'ModernBeginTextureReplays(replayCount);'),
                                ('void ModernVertexReuseEndBatch(', 'ModernEndTextureReplays();')]:
            body = method(text, signature)
            self.assertLess(body.index(call), body.index('return;'))
        self.assertEqual(text.count('mXboxDepthSamples.Clear();'), 2)
        self.assertNotIn('mGetPixelDepthPending', text)
        self.assertNotIn('mGetPixelDepthCached', text)
        receipt = json.loads((ROOT / 'scratch/xenos-xdk/xdk/build.json').read_text())
        native = [row for row in receipt if row['source'].endswith('/core.cpp')]
        self.assertEqual(len(native), 1)
        self.assertEqual(native[0]['source'], 'shipyard/sources/xenos/core.cpp')
        self.assertEqual(native[0]['exit'], 0)


if __name__ == '__main__':
    unittest.main()
