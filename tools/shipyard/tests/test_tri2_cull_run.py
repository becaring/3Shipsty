"""Compile the emitted run certificate against original cull arithmetic."""

from pathlib import Path
import runpy
import subprocess
import sys
import unittest

from test_tri2_packed_reuse import host_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
from tri2_cull_run_projection import transform


class Tri2CullRun(unittest.TestCase):
    def test_exact_arithmetic_and_callback_resets(self):
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = runpy.run_path(str(ROOT / 'platform/shipyard/fast3d/cull_projection.py'))['transform'](source)
        original = source.split('void Interpreter::GfxSpTri1(', 1)[1]
        original = original[original.index('        float dx1 = '):original.index('        if ((v1->w < 0)')]
        cull = projected.split('// MODERN CULL CACHE BEGIN\n', 1)[1].split('// MODERN CULL CACHE END', 1)[0]
        token = '        const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();\n'
        cull = '    ' + token.lstrip() + cull.replace(token, '')
        fixture_source = '''#include "application/command_profile.h"
void Interpreter::Flush() {
}
__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline() {
}
void ScopeBoundaries() {
            owner->mXboxPairPacked.Reset();
            owner->mXboxPairPacked.Reset();
}
void Interpreter::GfxSpTri1() {
''' + cull + '\n}\n'
        emitted = transform(fixture_source)
        self.assertEqual(transform(emitted), emitted)
        emitted = emitted.split('void Interpreter::GfxSpTri1() {', 1)[1].split('\n}', 1)[0]
        emitted = emitted.replace('Shipyard::Fast3D::ProjectionRoundingMode()', 'ReadRounding()')
        fixture = Path(__file__).with_suffix('.cpp').read_text()
        fixture = fixture.replace('/* ORIGINAL */', original).replace('/* PROJECTED */', emitted)
        out = ROOT / 'scratch/fast3d-xdk/tri2-cull-run'
        out.mkdir(parents=True, exist_ok=True)
        path = out / 'contract.cpp'
        path.write_text(fixture)
        compiler, environment = host_environment()
        exe = out / 'contract.exe'
        command = [str(compiler), '/nologo', '/O2', '/fp:strict', '/EHsc', '/MD',
                   '/I' + str(ROOT / 'platform/shipyard'), '/I' + str(resolve(ROOT) / 'sources'),
                   str(path), '/Fe:' + str(exe)]
        built = subprocess.run(command, cwd=out, env=environment, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
