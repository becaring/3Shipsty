"""Execute Modern's actual shader-state block before and after projection."""
import runpy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent / 'LibUltraShip+Fast3D360'
PROJECTION = ROOT / 'platform/shipyard/fast3d/shader_metadata_projection.py'


def struct_body(source, name):
    start = source.index('struct ' + name + ' {')
    return source[start:source.index('\n};', start) + 3]


class ModernShaderMetadataTests(unittest.TestCase):
    def test_real_state_block_lifetime_and_dynamic_clip(self):
        source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        header = (ROOT / 'libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        projector = runpy.run_path(str(PROJECTION)) if PROJECTION.exists() else dict(
            transform=lambda value: value, header=lambda value: value)
        projected = projector['transform'](source)
        projected_header = projector['header'](header)
        self.assertIn('Shipyard::Fast3D::ShaderMetadataCache<16>', projected_header)
        self.assertIn('#include "fast3d/shader_metadata_cache.h"', projected_header)
        self.assertNotIn('xboxShaderInfoBackend', projected_header)
        functions = []
        for name, text in [('Original', source), ('Projected', projected)]:
            start = text.index('    struct ShaderProgram* prg = comb->prg[tm];')
            stop = text.index('    for (int i = 0; i < 3; i++) {', start)
            functions.append('void ' + name + '::Phase(unsigned tm,bool use_alpha) {\n'
                             'ColorCombiner* comb=&At();\n' + text[start:stop] +
                             'result.inputs=numInputs;result.used[0]=usedTextures[0];'
                             'result.used[1]=usedTextures[1];result.clip=clip_parameters;\n}\n')
            init = text.split('    mRapi->Init();', 1)[1].split('    mRapi->UpdateFramebufferParameters(', 1)[0]
            functions.append('void ' + name + '::Init(Backend* api) {mRapi=api;mRapi->Init();\n' + init + '}\n')
        old = struct_body(header, 'ColorCombiner').replace('ColorCombiner', 'OriginalCombiner')
        new = struct_body(projected_header, 'ColorCombiner').replace('ColorCombiner', 'ProjectedCombiner')
        fixture = Path(__file__).with_name('test_fast3d_shader_metadata.cpp').read_text()
        fixture = fixture.replace('// EXTRACTED_COMBINERS', old + '\n' + new)
        fixture = fixture.replace('// EXTRACTED_FUNCTIONS', '\n'.join(functions))
        compiler = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.43.34808/bin/Hostx64/x64/cl.exe')
        msvc = compiler.parents[3]
        sdk = Path('C:/Program Files (x86)/Windows Kits/10')
        environment = os.environ.copy()
        environment['PATH'] = str(compiler.parent) + os.pathsep + environment['PATH']
        environment['INCLUDE'] = ';'.join(map(str, [msvc / 'include'] +
            [sdk / 'Include/10.0.26100.0' / p for p in ('ucrt', 'shared', 'um')]))
        environment['LIB'] = ';'.join(map(str, [msvc / 'lib/x64'] +
            [sdk / 'Lib/10.0.26100.0' / p / 'x64' for p in ('ucrt', 'um')]))
        roots = [ROOT / 'libultraship/include', ROOT / 'platform/shipyard', BASE / 'sources',
                 BASE / 'sources/value_types', ROOT / 'scratch/gui-resources-xdk/generated/include',
                 ROOT / 'scratch/imgui-xdk/generated',
                 ROOT / 'scratch/deps/spdlog/include', ROOT / 'platform/shipyard/json/upstream/include']
        with tempfile.TemporaryDirectory(prefix='modern-shader-metadata-', dir=ROOT / 'scratch') as directory:
            folder = Path(directory)
            cpp = folder / 'contract.cpp'
            exe = folder / 'contract.exe'
            cpp.write_text(fixture)
            command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/DNOMINMAX']
            command += ['/I' + str(path) for path in roots]
            command += [str(cpp), '/Fe:' + str(exe)]
            built = subprocess.run(command, cwd=directory, env=environment, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS modern shader metadata differential', result.stdout)
