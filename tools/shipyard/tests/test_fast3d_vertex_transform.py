"""Modern's actual GfxSpVertex vs its Shipyard projection, on a host VMX model.

The model executes the canonical VMX source with scalar host intrinsics; the
native compile below separately checks the real PPC adapter translation unit.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'platform/shipyard/fast3d'))
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import vertex_transform
from platform_base import resolve
from test_binary import host_environment, invoke
from prepare_window import includes as window_includes

SHIPYARD = resolve(ROOT) / 'sources'
SOURCE = ROOT / 'libultraship/src/fast/interpreter.cpp'
OUT = ROOT / 'scratch/fast3d-xdk/modern-transform-proof'
MODEL = HERE / 'vmx_model'
XDK = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')


def method(source, signature):
    begin = source.index(signature)
    opening = source.index('{', begin)
    depth = 0
    for end in range(opening, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return source[begin:end + 1]
    raise AssertionError('Unclosed authoritative method: ' + signature)


def contract_source(original, projected):
    signatures = ('void Interpreter::NormalizeVector(',
                  'void Interpreter::TransposedMatrixMul(',
                  'void Interpreter::CalculateNormalDir(',
                  'float Interpreter::AdjXForAspectRatio(',
                  'void Interpreter::GfxSpVertex(')
    functions = []
    for name, source in (('Original', original), ('Projected', projected)):
        for signature in signatures:
            functions.append(method(source, signature).replace('Interpreter::', name + '::'))
    clamp = method((ROOT / 'libultraship/src/ship/utils/Utils.cpp').read_text(encoding='utf-8-sig'),
                   'float clamp(')
    template = (HERE / 'test_fast3d_vertex_transform.cpp').read_text()
    return (template.replace('// EXTRACTED_CLAMP', clamp)
                    .replace('// EXTRACTED_METHODS', '\n\n'.join(functions)))


class ModernVertexTransformProof(unittest.TestCase):
    def test_complete_modern_composition(self):
        OUT.mkdir(parents=True, exist_ok=True)
        original = SOURCE.read_text(encoding='utf-8-sig')
        projected = vertex_transform.transform(original)
        self.assertIn('ClipVertices(&mRsp->loaded_vertices[shipyardTransformFirst],\n'
                      '                                      n_vertices, false)', projected)
        self.assertIn('// if (z < -w) d->clip_rej |= 16; // CLIP_NEAR', original)
        self.assertEqual(projected.count('Shipyard::Fast3D::TransformPositions('), 1)
        source = contract_source(original, projected)
        generated = OUT / 'contract.cpp'
        generated.write_text(source)
        compiler, environment = host_environment()
        includes = (MODEL, ROOT / 'libultraship/include',
                    ROOT / 'scratch/imgui-xdk/generated', ROOT / 'platform/shipyard',
                    SHIPYARD)
        # The same complete header used by the Modern interpreter supplies
        # F3DVtx, LoadedVertex, RSP, geometry bits, and MAX_VERTICES.
        command = [compiler, '/nologo', '/std:c++20', '/O2', '/fp:precise',
                   '/EHsc', '/MD', '/DNOMINMAX']
        command += ['/I' + str(path) for path in includes]
        command += [generated, SHIPYARD / 'fast3d/vertex_transform.cpp',
                    SHIPYARD / 'fast3d/clip_quantize.cpp',
                    '/Fe:' + str(OUT / 'contract.exe')]
        invoke(command, OUT, 'host-compile', environment)
        output = invoke([OUT / 'contract.exe'], OUT, 'host-run', environment)['stdout']
        self.assertIn('PASS Modern GfxSpVertex differential', output)
        # Negative control: a changed Modern near-plane policy must be caught
        # by the same full-state fixture, not only by a source-text assertion.
        marker = 'n_vertices, false);'
        self.assertEqual(source.count(marker), 1)
        mutant = OUT / 'near-plane-mutant.cpp'
        mutant.write_text(source.replace(marker, 'n_vertices, true);'))
        mutant_command = [mutant if part == generated else part for part in command]
        mutant_command[-1] = '/Fe:' + str(OUT / 'near-plane-mutant.exe')
        invoke(mutant_command, OUT, 'near-plane-mutant-compile', environment)
        rejected = invoke([OUT / 'near-plane-mutant.exe'], OUT,
                          'near-plane-mutant-run', environment, success=False)
        self.assertNotEqual(rejected['returncode'], 0,
                            'Near-plane policy mutation escaped the differential')
        self.assertIn('authoritative RSP vs projected RSP mismatch', rejected['stderr'])
        print(output.strip())

    def test_native_modern_adapter_compiles(self):
        # A fresh object directly from the current generated interpreter; this
        # test is intentionally separate from the host VMX behavioral model.
        generated = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'
        self.assertTrue(generated.is_file(), 'Generate Modern Fast3D before native compile')
        text = generated.read_text()
        self.assertIn('Shipyard::Fast3D::TransformPositions(', text)
        self.assertIn('n_vertices, false)', text)
        self.assertEqual(hashlib.sha256(SOURCE.read_text(encoding='utf-8-sig').encode()).hexdigest(),
                         json.loads((ROOT / 'platform/shipyard/fast3d/sources.lock.json').read_text())
                         ['sources']['src/fast/interpreter.cpp'])
        OUT.mkdir(parents=True, exist_ok=True)
        flags = ['/nologo', '/c', '/TP', '/EHsc', '/GR', '/MT', '/D_XBOX',
                 '/D_XBOX_VER=200', '/DNOMINMAX', '/DSPDLOG_ACTIVE_LEVEL=0',
                 '/Dnssv_CONFIG_SELECT_STRING_VIEW=1',
                 '/FI' + str(ROOT / 'scratch/configuration-xdk/generated/include/compile_definitions.h'),
                 '/I' + str(XDK / 'include/xbox')]
        paths = [ROOT / 'scratch/fast3d-xdk/generated/include',
                 ROOT / 'scratch/gui-resources-xdk/generated/include',
                 ROOT / 'scratch/context-xdk/generated/include',
                 *window_includes(), ROOT / 'scratch/async-xdk/generated']
        flags += ['/I' + str(path) for path in paths]
        obj = OUT / 'interpreter-fresh.obj'
        invoke([XDK / 'bin/win32/cl.exe', *flags, generated, '/Fo' + str(obj)],
               OUT, 'xdk-interpreter-compile')
        self.assertEqual(struct.unpack_from('<H', obj.read_bytes())[0], 0x1f2,
                         'Fresh Modern interpreter object must be PowerPC BE COFF')
        print('PASS fresh complete Modern Fast3D interpreter PPC object')


if __name__ == '__main__':
    unittest.main()
