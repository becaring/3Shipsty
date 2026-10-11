"""Execute generated material reuse against the uncached calculations and native effects."""
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import material_replay_projection as replay
import prepare_fast3d
from test_binary import host_environment
from platform_base import resolve
from prepare_window import includes

BASE = resolve(ROOT)
SOURCE = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'


def compile_run(test, source):
    compiler, environment = host_environment()
    roots = [ROOT / 'scratch/fast3d-xdk/generated/include', ROOT / 'platform/shipyard',
             BASE / 'sources', ROOT / 'scratch/gui-resources-xdk/generated/include', *includes()]
    with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as folder:
        out = Path(folder)
        (out / 'contract.cpp').write_text(source)
        command = [str(compiler), '/nologo', '/std:c++20', '/O2', '/fp:precise', '/EHsc', '/MD', '/DNOMINMAX']
        command += ['/I' + str(path) for path in roots]
        command += [str(out / 'contract.cpp'), '/Fe:' + str(out / 'contract.exe')]
        built = subprocess.run(command, cwd=out, env=environment, capture_output=True, text=True)
        test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(out / 'contract.exe')], cwd=out, capture_output=True, text=True, timeout=60)
        test.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        print(ran.stdout.strip())


class MaterialReplayTests(unittest.TestCase):
    def test_generated_geometry_matches_original_with_multiple_materials(self):
        source = SOURCE.read_text()
        helper = source.split('// MODERN MATERIAL CACHE BEGIN\n', 1)[1].split('// MODERN MATERIAL CACHE END', 1)[0]
        helper = helper.replace('// TEST REBUILD GEOMETRY', '++rebuilds;')
        helper = re.sub(r'static void ModernReleaseMaterialMemos\(\) \{.*?\n\}', '', helper, flags=re.DOTALL)
        projection = runpy.run_path(str(ROOT / 'platform/shipyard/fast3d/material_cache_projection.py'))
        original = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = projection['transform'](original)

        def geometry(text):
            tri = text.split('void Interpreter::GfxSpTri1(', 1)[1]
            return tri[tri.index('            uint8_t cms ='):tri.index('            if (mRenderingState.mTextures[i] == nullptr)')]

        fixture = Path(__file__).with_name('test_material_cache_contract.cpp').read_text()
        fixture = '#include "fast3d/material_memo.h"\n' + fixture
        fixture = fixture.replace('// GENERATED_HELPERS', helper)
        fixture = fixture.replace('// ORIGINAL_BODY', geometry(original)).replace('// PROJECTED_BODY', geometry(projected))
        fixture = fixture.replace('rebuilds == beforeMutation + 1', 'rebuilds <= beforeMutation + 1')
        # A repeated prior state may now hit; the differential still compares every output.
        fixture = fixture.replace('rebuilds == beforeRoundChange + 1', 'rebuilds <= beforeRoundChange + 1')
        fixture = fixture.replace('    unsigned savedRound =', '''    RDP first = {}, second = {};
    first.texture_tile[0].line_size_bytes = 32;
    first.loaded_texture[0].orig_size_bytes = 1024;
    second = first;
    second.texture_tile[0].line_size_bytes = 64;
    Compare(first, 0, 0);
    Compare(second, 0, 0);
    const unsigned warmed = rebuilds;
    for (unsigned replay = 0; replay < 3; ++replay)
        for (unsigned draw = 0; draw < 1000; ++draw) {
            Compare(first, 0, 0);
            Compare(second, 0, 0);
        }
    require(rebuilds == warmed, "alternating materials reuse geometry across replays");
    unsigned savedRound =''')
        compile_run(self, fixture)

    def test_generated_mode_decoding_matches_original(self):
        source = SOURCE.read_text()
        start = source.index('    const uint64_t cc_id = mRdp->combine_mode;')
        end = source.index('    if (xboxPrepSample.sampled)', start)
        cached = source[start:end]
        original = cached.split('// MODERN MODE MISS BEGIN\n', 1)[1].split('// MODERN MODE MISS END', 1)[0]
        finish = 'return ModeResult{comb, cc_id, use_alpha, use_fog, use_grayscale};'
        fixture = Path(__file__).with_name('test_material_replay_modes.cpp').read_text()
        helpers = replay.HELPERS.split('struct ModernTextureNodeKey', 1)[0].replace('Interpreter', 'ModeOwner')
        fixture = fixture.replace('// MODE_HELPERS', helpers)
        fixture = fixture.replace('// ORIGINAL', 'const uint64_t cc_id = mRdp->combine_mode;\n' + original + finish)
        fixture = fixture.replace('// CACHED', cached + finish)
        compile_run(self, fixture)

    def test_generated_texture_lookup_preserves_native_effects(self):
        original = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        original = prepare_fast3d.texture_bindings(original)
        source = SOURCE.read_text()

        def lookup(text):
            start = text.index('bool Interpreter::TextureCacheLookup(')
            end = text.index('\nstd::string Interpreter::GetBaseTexturePath', start)
            body = text[start:end].split('{', 1)[1].rsplit('}', 1)[0]
            body = re.sub(r'^\s*ModernFrameProfile::[^\n]+\n', '\n', body, flags=re.MULTILINE)
            body = body.replace('mXboxPipelineKey.valid=false, ', '')
            body = body.replace(', mXboxPipelineKey.valid=false', '')
            body = body.replace('mTextureCache.map.find(key)', 'Find(key)')
            return body

        fixture = Path(__file__).with_name('test_material_replay_textures.cpp').read_text()
        fixture = 'static volatile unsigned gModernMaterialReplayControl[1] = { 1 };\n' + fixture
        helpers = 'struct ModernTextureNodeKey' + replay.HELPERS.split('struct ModernTextureNodeKey', 1)[1]
        fixture = fixture.replace('// NODE_HELPERS', helpers.replace('Interpreter', 'TextureOwner'))
        fixture = fixture.replace('// ORIGINAL', lookup(original)).replace('// CACHED', lookup(source))
        compile_run(self, fixture)

    def test_every_node_removal_invalidates_borrows(self):
        source = SOURCE.read_text()
        self.assertIn('Interpreter::~Interpreter() {\n    ModernReleaseMaterialMemos();', source)
        for name in ('sModernModes', 'sModernTextureNodes', 'sModernGeometry0', 'sModernGeometry1'):
            self.assertIn(name + '.Release();', source)
        for signature in ('void Interpreter::TextureCacheClear() {',
                          'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {'):
            body = source.split(signature, 1)[1].split('\n}', 1)[0]
            self.assertIn('sModernTextureNodes.Clear();', body)
        eviction = source.split('if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {', 1)[1]
        self.assertLess(eviction.index('sModernTextureNodes.Clear();'), eviction.index('mTextureCache.map.erase(it);'))
        self.assertEqual(source.count('mTextureCache.map.erase('), 2)
        self.assertEqual(source.count('mTextureCache.map.clear();'), 1)


if __name__ == '__main__':
    unittest.main()
