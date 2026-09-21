"""Project the pinned 9.2.3 graphics interfaces/decoder for the XDK compiler.

This is an object-compilation boundary, not a substitute renderer. No reference
tree is read after the one-time donor import; production interpreter integration
and the real Prism/resource builder remain required.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'platform/shipyard/graphics'
OUT = ROOT / 'scratch/graphics-xdk'


def check_source(data, expected, name):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Pinned graphics source drift: ' + name)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected exactly one graphics anchor: ' + old[:80])
    return text.replace(old, new, 1)


def virtual_contracts(text):
    return re.findall(r'virtual\s+([^{};]+?)\s*(?:=\s*0|=\s*default|\{\s*\})\s*;', text)


def lower_api(text, name):
    text = replace_once(text, 'virtual ~' + name + '() = default;', 'virtual ~' + name + '() {};')
    defaults = []
    def move_default(match):
        defaults.append((match[2], match[3]))
        return match[1] + match[2] + ';'
    text = re.sub(r'(?m)^(    (?:int8_t|uint32_t|bool)\s+)(m\w+)\s*=\s*([^;\n]+);', move_default, text)
    expected = 7 if name == 'GfxRenderingAPI' else 3
    if len(defaults) != expected:
        raise ValueError('Unexpected graphics constructor defaults: ' + name)
    init = ', '.join(member + '(' + value + ')' for member, value in defaults)
    text = replace_once(text, 'class ' + name + ' {\n  public:',
                        'class ' + name + ' {\n  public:\n    ' + name + '() : ' + init + ' {}')
    if name == 'GfxRenderingAPI':
        text = text.replace('const auto hash', 'const size_t hash')
        if text.count('std::hash<float>{}') != 2:
            raise ValueError('Unexpected float hash implementation')
        text = text.replace('std::hash<float>{}', 'std::hash<float>()')
    return text


def decoder_function(text):
    start = text.index('void gfx_cc_get_features(uint64_t shader_id0, uint32_t shader_id1,')
    stop = text.index('\nextern "C" int gfx_create_framebuffer', start)
    return text[start:stop].rstrip() + '\n'


def feature_header(text, lower=True):
    start = text.index('enum {\n    SHADER_0,')
    stop = text.index('\nunion Gfx;', start)
    section = text[start:stop]
    # ColorCombinerKey belongs to the interpreter, not the standalone decoder.
    first = section.index('struct ColorCombinerKey {')
    last = section.index('#define SHADER_MAX_TEXTURES', first)
    section = section[:first] + section[last:]
    if lower:
        section = replace_once(section, 'enum class ShaderOpts {', 'struct ShaderOpts { enum Value {')
        section = replace_once(section, '    MAX\n};', '    MAX\n}; };')
    return '#pragma once\n#include <stdint.h>\n' + section + '\n'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def prepare(root=ROOT, out=OUT):
    lock = json.loads((root / 'platform/shipyard/graphics/source-lock.json').read_text(encoding='utf-8-sig'))
    inputs = {}
    # Validate every input before emitting anything.
    for name, digest in lock['inputs'].items():
        data = (root / name).read_bytes()
        check_source(data, digest, name)
        inputs[name] = data.decode('utf-8-sig').replace('\r\n', '\n')
    donor = lock['donor']
    data = (root / donor['local']).read_bytes()
    check_source(data, donor['sha256'], donor['local'])
    native = data.decode('utf-8-sig').replace('\r\n', '\n')
    for filename, classname in [('gfx_rendering_api.h', 'GfxRenderingAPI'),
                                ('gfx_window_manager_api.h', 'GfxWindowBackend')]:
        source = 'libultraship/include/fast/backends/' + filename
        text = inputs[source]
        lowered = lower_api(text, classname)
        if virtual_contracts(text) != virtual_contracts(lowered):
            raise ValueError('Virtual contract changed during projection')
        write(out / 'include/fast/backends' / filename, lowered)
        write(out / 'raw/include/fast/backends' / filename, text)
    patch = inputs['libultraship/cmake/dependencies/patches/imgui-fixes-and-config.patch']
    if '+#define ImTextureID void*' not in patch:
        raise ValueError('Missing pinned ImGui texture ABI')
    # This header only projects the config macro consumed by gfx_rendering_api.
    # It is not an ImGui library or an implementation of its public API.
    config = '#pragma once\n// ABI projection from pinned ImGui config patch; graphics probe only.\n#define ImTextureID void*\n'
    boolean = '#pragma once\n#ifndef __cplusplus\n#error Graphics projection requires C++; use the game C compatibility path for C99 bool.\n#endif\n'
    for include in (out / 'include', out / 'raw/include'):
        write(include / 'imconfig.h', config)
        write(include / 'stdbool.h', boolean)
    interp = inputs['libultraship/include/fast/interpreter.h']
    write(out / 'include/fast/cc_features.h', feature_header(interp))
    write(out / 'raw/include/fast/cc_features.h', feature_header(interp, lower=False))
    decoder = decoder_function(inputs['libultraship/src/fast/interpreter.cpp'])
    write(out / 'cc_features.cpp', '#include "fast/cc_features.h"\n' + decoder)
    for variant, lower in [('original', False), ('projected', True)]:
        write(out / ('decoder_' + variant + '.inc'), feature_header(interp, lower=lower) + decoder)
    # Preserve the original imported lowerer byte-for-byte under donor/.
    # Project only names and unrelated Smash profiling hooks in the output.
    native = replace_once(native, '#include "shader_provider.h"', '#include "shader_lower.h"')
    native = replace_once(native, '#ifdef _XBOX\n#include "../runtime/perf_trace.h"\n#endif\n', '')
    native = replace_once(native, '#ifdef _XBOX\n    Smash360PerfScope profileScope(SMASH_PERF_SHADER_LOWER);\n#endif\n', '')
    native = replace_once(native, 'bool Smash360_LowerShader(', 'bool Shipyard_LowerShader(')
    native = replace_once(native, '// Smash360 Xenos lowering ABI 2', '// Shipyard Xenos lowering ABI 1')
    write(out / 'shader_lower.cpp', native)
    write(out / 'include/shader_lower.h', '#pragma once\n#include <string>\nbool Shipyard_LowerShader(const std::string&, std::string&, std::string&);\n')
    # Keep exact current template bytes available for later real Prism work.
    write(out / 'shaders/default.shader.hlsl', inputs['libultraship/src/fast/shaders/directx/default.shader.hlsl'])
    outputs = [p for p in out.rglob('*') if p.is_file() and p.suffix in ('.cpp', '.h', '.hlsl', '.inc')]
    report = dict(schema=1, shader_key_widths=[64, 32], source_lock=lock,
                  outputs={p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(outputs)},
                  limitations=['No Xenos backend implementation yet', 'Decoder object is an exact source extraction, not the complete interpreter',
                               'Prism builder/resource service not compiled or linked', 'ImGui config header is ABI-only; real ImGui remains required'])
    write(out / 'manifest.json', json.dumps(report, indent=2) + '\n')
    return report


def compile_xdk(out=OUT, raw=False):
    xdk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
    includes = out / ('raw/include' if raw else 'include')
    dest = out / ('raw' if raw else 'compiled')
    dest.mkdir(parents=True, exist_ok=True)
    flags = [str(xdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/TP', '/D_XBOX', '/DNOMINMAX',
             '/EHsc', '/GR', '/MT', '/W4', '/I' + str(includes), '/I' + str(xdk / 'include/xbox')]
    sources = [BASE / 'interface_contract.cpp', out / 'cc_features.cpp']
    if not raw:
        sources.append(out / 'shader_lower.cpp')
    results = []
    for source in sources:
        command = flags + ['/Fo' + str(dest / (source.stem + '.obj')), str(source)]
        result = subprocess.run(command, capture_output=True, text=True)
        log = result.stdout + result.stderr
        write(dest / (source.stem + '.log'), log)
        results.append(dict(source=str(source), returncode=result.returncode, command=command))
        print(source.name + ': exit ' + str(result.returncode))
        if result.returncode:
            print(log[:5500])
    write(dest / 'compile-report.json', json.dumps(results, indent=2) + '\n')
    return all(item['returncode'] == 0 for item in results)


def differential_host(out=OUT):
    vcvars = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
    if not vcvars.is_file():
        raise FileNotFoundError('Host VS2022 toolchain is required: ' + str(vcvars))
    dest = out / 'host'
    dest.mkdir(parents=True, exist_ok=True)
    executable = dest / 'decoder_differential.exe'
    # Fixed task-owned batch path and measured toolchain; no destructive ops.
    command = ('@echo off\ncall "' + str(vcvars) + '" >nul\nif errorlevel 1 exit /b 1\n' +
               'cl /nologo /std:c++20 /EHsc /W4 /O2 /I"' + str(out / 'include') + '" /I"' + str(out) +
               '" /Fo"' + dest.as_posix() + '/" /Fe"' + str(executable) + '" "' +
               str(BASE / 'decoder_differential.cpp') + '" "' + str(out / 'shader_lower.cpp') +
               '"\nif errorlevel 1 exit /b 1\n"' + str(executable) + '"\n')
    batch = dest / 'run.cmd'
    write(batch, command)
    result = subprocess.run(['cmd.exe', '/d', '/c', str(batch)], cwd=dest, capture_output=True, text=True)
    write(dest / 'differential.log', result.stdout + result.stderr)
    write(dest / 'differential-report.json', json.dumps(dict(returncode=result.returncode,
          scope='Host original/projected current decoder and CCFeatures layout; not Xenos runtime or Prism expansion'), indent=2) + '\n')
    if result.returncode:
        print(result.stdout + result.stderr)
    else:
        for line in result.stdout.splitlines():
            if line.startswith('PASS '):
                print(line)
        print('Full host compiler diagnostics: ' + str(dest / 'differential.log'))
    return result.returncode == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--raw-probe', action='store_true')
    parser.add_argument('--differential', action='store_true')
    args = parser.parse_args()
    prepare()
    success = True
    if args.compile or args.raw_probe:
        success = compile_xdk(raw=args.raw_probe)
    if args.differential:
        success = differential_host() and success
    raise SystemExit(0 if success else 1)
