"""Differential for Modern's own texture geometry arithmetic and Shipyard storage."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

from tools.shipyard.tests.test_binary import host_environment
from tools.shipyard.platform_base import resolve

ROOT = Path(__file__).resolve().parents[3]
BASE = resolve(ROOT)
PROJECTION = ROOT / 'platform/shipyard/fast3d/material_cache_projection.py'


class MaterialCacheProjectionTests(unittest.TestCase):
    def test_modern_geometry_formula_and_key_mutations(self):
        projection = runpy.run_path(str(PROJECTION))
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = projection['transform'](source)
        self.assertIn('#include "fast3d/material_value_cache.h"', projected)
        tri = source.split('void Interpreter::GfxSpTri1(', 1)[1]
        original_body = tri[tri.index('            uint8_t cms ='):
                            tri.index('            if (mRenderingState.mTextures[i] == nullptr)')]
        changed = projected.split('void Interpreter::GfxSpTri1(', 1)[1]
        projected_body = changed[changed.index('            uint8_t cms ='):
                                 changed.index('            if (mRenderingState.mTextures[i] == nullptr)')]
        helpers = projected.split('// MODERN MATERIAL CACHE BEGIN\n', 1)[1].split(
            '// MODERN MATERIAL CACHE END', 1)[0]
        helpers = helpers.replace('// TEST REBUILD GEOMETRY', '++rebuilds;')
        contract = Path(__file__).with_name('test_material_cache_contract.cpp').read_text()
        contract = contract.replace('// GENERATED_HELPERS', helpers)
        contract = contract.replace('// ORIGINAL_BODY', original_body)
        contract = contract.replace('// PROJECTED_BODY', projected_body)
        compiler, environment = host_environment()
        with tempfile.TemporaryDirectory(prefix='modern-material-cache-') as folder:
            out = Path(folder)
            file = out / 'contract.cpp'
            file.write_text(contract)
            command = [str(compiler), '/nologo', '/std:c++20', '/O2', '/fp:precise',
                       '/EHsc', '/MD', '/I' + str(BASE / 'sources'), str(file),
                       '/Fe:' + str(out / 'contract.exe')]
            built = subprocess.run(command, cwd=out, env=environment,
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(out / 'contract.exe')], cwd=out,
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn('original/projected Modern geometry', ran.stdout)


if __name__ == '__main__':
    unittest.main()
