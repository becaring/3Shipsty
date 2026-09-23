"""Bitwise differential of 9.2.3's actual original/projected packing loop."""

import pathlib
import re
import runpy
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'platform/shipyard/fast3d'))
import vertex_packing


def main():
    source = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
    projected = vertex_packing.transform(source)
    begin = vertex_packing.START
    end = vertex_packing.END
    original_body = source[source.index(begin):source.index(end, source.index(begin))]
    projected_start = '    float* shipyardVertexOutput = mBufVbo + mBufVboLen;'
    projected_body = projected[projected.index(projected_start):projected.index(end, projected.index(projected_start))]
    # Preserve complete output expressions and branch structure. Only the
    # intended writes/conversions may differ between these extracted methods.
    restored = projected_body.replace('    float* shipyardVertexOutput = mBufVbo + mBufVboLen;\n', '')
    restored = restored.replace('    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);\n\n', '')
    restored = restored.replace('*shipyardVertexOutput++', 'mBufVbo[mBufVboLen++]')
    restored = re.sub(r'Shipyard::Fast3D::UnitColor\(([^()]*)\)', r'\1 / 255.0f', restored)
    if restored != original_body:
        raise AssertionError('Non-packing statement changed')
    folder = ROOT / 'scratch/fast3d-xdk/vertex-packing'
    folder.mkdir(parents=True, exist_ok=True)
    header = folder / 'fast3d/unit_color.h'
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(vertex_packing.color_header(), encoding='utf-8')
    template = pathlib.Path(__file__).with_name('test_vertex_packing_contract.cpp').read_text(encoding='utf-8')
    code = template.replace('// ORIGINAL_LOOP', original_body).replace('// PROJECTED_LOOP', projected_body)
    contract = folder / 'contract.cpp'
    contract.write_text(code, encoding='utf-8')
    environment = runpy.run_path(str(pathlib.Path(__file__).with_name('test_binary.py')))
    compiler, env = environment['host_environment']()
    invoke = environment['invoke']
    invoke([compiler, '/nologo', '/O2', '/fp:precise', '/EHsc', '/MD',
            '/I' + str(folder), '/Fe:' + str(folder / 'contract.exe'),
            contract], folder, 'host-compile', env)
    print(invoke([folder / 'contract.exe'], folder, 'host-run', env)['stdout'].strip())
    xdk = pathlib.Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    invoke([xdk / 'bin/win32/cl.exe', '/nologo', '/c', '/O2', '/EHsc',
            '/D_XBOX', '/D_XBOX_VER=200', '/I' + str(xdk / 'include/xbox'),
            '/I' + str(folder), '/Fo' + str(folder / 'contract-xdk.obj'),
            contract], folder, 'xdk-compile')
    print('PASS XDK projected packing object')


if __name__ == '__main__':
    main()
