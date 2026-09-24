"""Modern cull arithmetic against its Shipyard projection cache adapter."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

from tools.shipyard.tests.test_binary import host_environment
from tools.shipyard.platform_base import resolve

ROOT = Path(__file__).resolve().parents[3]
BASE = resolve(ROOT)
PROJECTION = ROOT / 'platform/shipyard/fast3d/cull_projection.py'
START = '        float dx1 = '
END = '        if ((v1->w < 0)'


class ModernCullProjectionTests(unittest.TestCase):
    def test_original_and_cached_arithmetic_under_all_rounding_modes(self):
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = runpy.run_path(str(PROJECTION))['transform'](source)
        self.assertIn('#include "fast3d/projection_cache.h"', projected)

        def body(text):
            tri = text.split('void Interpreter::GfxSpTri1(', 1)[1]
            return tri[tri.index(START):tri.index(END)]

        original_body = body(source)
        projected_body = projected.split('void Interpreter::GfxSpTri1(', 1)[1].split(
            '        // MODERN CULL CACHE BEGIN\n', 1)[1].split(
                '        // MODERN CULL CACHE END\n', 1)[0]
        contract = Path(__file__).with_name('test_cull_projection_contract.cpp').read_text()
        contract = contract.replace('// ORIGINAL_BODY', original_body)
        contract = contract.replace('// PROJECTED_BODY', projected_body)
        compiler, environment = host_environment()
        with tempfile.TemporaryDirectory(prefix='modern-cull-projection-') as folder:
            out = Path(folder)
            file = out / 'contract.cpp'
            file.write_text(contract)
            built = subprocess.run([str(compiler), '/nologo', '/std:c++20', '/O2',
                                    '/fp:precise', '/EHsc', '/MD',
                                    '/I' + str(BASE / 'sources'), str(file),
                                    '/Fe:' + str(out / 'contract.exe')],
                                   cwd=out, env=environment, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(out / 'contract.exe')], cwd=out,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn('modern cull original/projected 524288 cases', ran.stdout)


if __name__ == '__main__':
    unittest.main()
