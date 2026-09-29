"""Bitwise differential of 9.2.3's actual original/projected packing loop."""

import pathlib
import re
import runpy
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'platform/shipyard/fast3d'))
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import vertex_packing
from platform_base import resolve


def main():
    source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
    projected = vertex_packing.transform(source)
    if projected.count('Shipyard::Fast3D::Coordinate(') != 0 or projected.count(']->Apply(v_arr[i]->') != 2:
        raise AssertionError('Modern must use the shared per-triangle UV axes for both axes')
    if projected.count('Shipyard::Fast3D::CoordinateAxis shipyardAxisStorage[2][2];') != 1:
        raise AssertionError('Modern UV axes must be prepared once before the packing loop')
    if projected.count('#include "fast3d/coordinate.h"') != 1:
        raise AssertionError('Modern coordinate include must resolve through Shipyard')
    begin = vertex_packing.START
    end = vertex_packing.END
    original_body = source[source.index(begin):source.index(end, source.index(begin))]
    projected_start = '    float* shipyardVertexOutput = mBufVbo + mBufVboLen;'
    projected_body = projected[projected.index(projected_start):projected.index(end, projected.index(projected_start))]
    # Preserve complete output expressions and branch structure. Only the
    # intended writes/conversions may differ between these extracted methods.
    restored = projected_body.replace('    float* shipyardVertexOutput = mBufVbo + mBufVboLen;\n', '')
    # Hoisted preludes (UV axes first, then clamp bounds, colors and material
    # inputs) all sit between the cursor and the loop.
    prelude_begin = restored.index('    Shipyard::Fast3D::CoordinateAxis shipyardAxisStorage[2][2];')
    restored = restored[:prelude_begin] + restored[restored.index(begin, prelude_begin):]
    restored = restored.replace('shipyardClampS[t]', '(tex_width2[t] - 0.5f) / tex_width[t]')
    restored = restored.replace('shipyardClampT[t]', '(tex_height2[t] - 0.5f) / tex_height[t]')
    restored = re.sub(r'                // Begin shared invariant material reuse\.\n.*?                // End shared invariant material reuse\.\n', '', restored, flags=re.S)
    for name, field, channels in [('shipyardFog', 'fog_color', 'rgb'), ('shipyardGrayscale', 'grayscale_color', 'rgba')]:
        for index, channel in enumerate(channels):
            restored = restored.replace('%s[%d]' % (name, index),
                'Shipyard::Fast3D::UnitColor(mRdp->%s.%s)' % (field, channel))
    restored = restored.replace('    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);\n\n', '')
    restored = restored.replace('*shipyardVertexOutput++', 'mBufVbo[mBufVboLen++]')
    restored = re.sub(r'Shipyard::Fast3D::UnitColor\(([^()]*)\)', r'\1 / 255.0f', restored)
    # The only allowed non-mechanical edit is the exact UV arithmetic block.
    uv_start = '            float u = v_arr[i]->u / 32.0f;'
    uv_end = '            bool clampS = tm & (1 << 2 * t);'
    original_uv = original_body[original_body.index(uv_start):original_body.index(uv_end)]
    projected_uv = restored[restored.index('            mBufVbo[mBufVboLen++] = shipyardCoordinateS[t]'):restored.index(uv_end)]
    restored = restored.replace(projected_uv, original_uv, 1)
    if restored != original_body:
        raise AssertionError('Non-packing statement changed')
    folder = ROOT / 'scratch/fast3d-xdk/vertex-packing'
    folder.mkdir(parents=True, exist_ok=True)
    base = resolve(ROOT)
    header = base / 'sources/fast3d/unit_color.h'
    if not header.is_file():
        raise AssertionError('Canonical unit-color header missing')
    if not (base / 'sources/fast3d/coordinate.h').is_file():
        raise AssertionError('Canonical coordinate header missing')
    if (ROOT / 'scratch/fast3d-xdk/generated/include/fast3d/unit_color.h').exists():
        raise AssertionError('Generated unit-color header shadows Shipyard')
    if (ROOT / 'scratch/fast3d-xdk/generated/include/fast3d/coordinate.h').exists():
        raise AssertionError('Generated coordinate header shadows Shipyard')
    template = pathlib.Path(__file__).with_name('test_vertex_packing_contract.cpp').read_text(encoding='utf-8')
    def counted(body):
        body = body.replace('switch (comb->shader_input_mapping[k][j])', 'switch (CountSelector(comb->shader_input_mapping[k][j]))')
        body = re.sub(r'(Shipyard::Fast3D::UnitColor\(mRdp->(?:fog_color|grayscale_color)\.[rgba]\))', r'CountMaterial(\1)', body)
        body = re.sub(r'(mRdp->(?:fog_color|grayscale_color)\.[rgba] / 255\.0f)', r'CountMaterial(\1)', body)
        return body.replace('(tex_width2[t] - 0.5f) / tex_width[t]',
                            'CountBound(tex_width2[t], tex_width[t])').replace(
                            '(tex_height2[t] - 0.5f) / tex_height[t]',
                            'CountBound(tex_height2[t], tex_height[t])')
    code = template.replace('// ORIGINAL_LOOP', counted(original_body)).replace('// PROJECTED_LOOP', counted(projected_body))
    contract = folder / 'contract.cpp'
    contract.write_text(code, encoding='utf-8')
    environment = runpy.run_path(str(pathlib.Path(__file__).with_name('test_binary.py')))
    compiler, env = environment['host_environment']()
    invoke = environment['invoke']
    invoke([compiler, '/nologo', '/O2', '/fp:precise', '/EHsc', '/MD',
            '/I' + str(header.parent.parent), '/Fe:' + str(folder / 'contract.exe'),
            contract], folder, 'host-compile', env)
    print(invoke([folder / 'contract.exe'], folder, 'host-run', env)['stdout'].strip())
    xdk = pathlib.Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    invoke([xdk / 'bin/win32/cl.exe', '/nologo', '/c', '/O2', '/EHsc',
            '/D_XBOX', '/D_XBOX_VER=200', '/I' + str(xdk / 'include/xbox'),
            '/I' + str(header.parent.parent), '/Fo' + str(folder / 'contract-xdk.obj'),
            contract], folder, 'xdk-compile')
    print('PASS XDK projected packing object')


if __name__ == '__main__':
    main()
