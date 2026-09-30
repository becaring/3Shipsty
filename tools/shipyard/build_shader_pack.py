"""Build the prebuilt Xenos shader pack offline, without running the game.

    python tools/shipyard/build_shader_pack.py [--archive <o2r> ...] [--jobs N]

Archives default to the verified official 9.2.3 extraction (scratch/assets/
official-9.2.3: oot.o2r and soh.o2r). Deploy the output next to the XEX as
game:\\shaders\\3shipsty.shaderpack.

Stages, each parallel across --jobs worker processes (default: every logical
CPU):
  1. harvest shader keys from every display list in the archives and from the
     game's C sources (shader_pack_harvest.py);
  2. generate the lowered HLSL for each key with the same feature decoder,
     Prism builder and lowering the XEX uses (shader_pack_sources.cpp, built
     like tests/test_prism.py's projected host binary);
  3. compile each distinct source for vs_3_0/VSMain and ps_3_0/PSMain with the
     XDK's fxc.exe, the offline front end of the D3DX compiler the runtime
     calls with default flags;
  4. write the pack (Shipyard sources/xenos/shader_pack.h): each program key
     with its vertex float count and vertex/pixel microcode, which the runtime
     keeps resident and uses without generating, lowering or compiling.
Intermediate files live in scratch/shader-pack and make reruns incremental.
"""
import argparse
import hashlib
import json
import os
import re
import runpy
import struct
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dependency_sources import ROOT
from platform_base import resolve as resolve_platform_base
import shader_pack_harvest as harvest

OUT = ROOT / 'scratch/shader-pack'
TOOLS = ROOT / 'tools/shipyard'
PLATFORM_BASE = resolve_platform_base(ROOT)
SDK = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
PROFILES = (('vs_3_0', 'VSMain'), ('ps_3_0', 'PSMain'))
TEMPLATE = ROOT / 'libultraship/src/fast/shaders/directx/default.shader.hlsl'
PACK_MAGIC, PACK_VERSION = 0x5348504B, 2
# FilteringMode: the builder only distinguishes three-point from the rest.
FILTERS = {'three-point': 1, 'linear': 0}


def sdk_define(header, name):
    match = re.search(r'#define\s+' + name + r'\s+(\d+)', (SDK / header).read_text(errors='replace'))
    if not match:
        raise ValueError(name + ' not found in ' + header)
    return int(match.group(1))


def host():
    return runpy.run_path(str(TOOLS / 'tests/test_binary.py'))


def run(command, folder, label, env):
    return host()['invoke'](command, folder, label, env)


def defined_macros():
    names = set()
    for header in (ROOT / 'libultraship/include/libultraship/libultra').glob('*.h'):
        names |= set(re.findall(r'^\s*#\s*define\s+(\w+)', header.read_text(errors='replace'), re.M))
    return names


def c_state():
    folder = OUT / 'c-state'
    folder.mkdir(parents=True, exist_ok=True)
    roots = [ROOT / 'soh/src', ROOT / 'soh/soh']
    z_rcp = ROOT / 'soh/src/code/z_rcp.c'
    calls = harvest.c_calls(roots, defined_macros())
    program = folder / 'dump.cpp'
    program.write_text(harvest.dump_program(harvest.setup_table(z_rcp), calls), encoding='utf-8')
    compiler, env = host()['host_environment']()
    executable = folder / 'dump.exe'
    run([compiler, '/nologo', '/EHsc', '/MD', '/O1', '/DF3DEX_GBI_2', '/I' + str(ROOT / 'libultraship/include'),
         program, '/Fe:' + str(executable)], folder, 'build', env)
    output = run([executable], folder, 'run', env)['stdout']
    setups, modes, records = harvest.c_seeds(output, z_rcp, roots)
    print('C sources: %d constant state calls, %d setup lists, %d modes' % (len(calls), len(setups), len(modes)))
    return setups, modes, records


def build_generator():
    """tests/test_prism.py's projected host build, with the pack generator as main."""
    runpy.run_path(str(TOOLS / 'prepare_prism.py'))['prepare']()
    runpy.run_path(str(TOOLS / 'prepare_graphics.py'))['prepare']()
    prism = ROOT / 'scratch/prism-xdk'
    audit = runpy.run_path(str(TOOLS / 'tests/test_prism.py'))['audit']
    folder = OUT / 'generator'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'builder-audit.cpp').write_text(
        audit((prism / 'generated/shader_builder.cpp').read_text(encoding='utf-8'), True), encoding='utf-8')
    (folder / 'audit.h').write_text(
        '#pragma once\nextern std::string AuditTemplate;\n'
        'xbox_compat::optional<std::string> AuditInclude(const std::string&);\n'
        'namespace Fast {\nstd::string gfx_direct3d_common_build_shader(size_t&,const CCFeatures&,bool,bool,bool);\n}\n',
        encoding='utf-8')
    env_module = host()
    compiler, env = env_module['host_environment']()
    resources = runpy.run_path(str(TOOLS / 'tests/test_resources.py'))
    base = prism / 'generated'
    paths = [base, folder, ROOT / 'scratch/graphics-xdk/include', PLATFORM_BASE / 'sources/graphics',
             PLATFORM_BASE / 'sources', PLATFORM_BASE / 'sources/value_types'] + resources['includes'](True)
    flags = ['/nologo', '/std:c++20', '/utf-8', '/EHsc', '/MD', '/O2', '/DNOMINMAX', '/DSPDLOG_ACTIVE_LEVEL=0',
             '/DSHIPYARD_PROJECTED']
    common = [compiler] + flags + ['/I' + str(p) for p in paths]
    invoke = folder / 'invoke.obj'
    run(common + ['/TC', '/c', base / 'prism/utils/invoke.c', '/Fo' + str(invoke)], folder, 'invoke', env)
    sources = [base / 'prism' / n for n in ('lexer.cpp', 'ast.cpp', 'processor.cpp', 'utils/gv.cpp')]
    sources += [folder / 'builder-audit.cpp', ROOT / 'scratch/graphics-xdk/cc_features.cpp',
                PLATFORM_BASE / 'sources/graphics/shader_lower.cpp', TOOLS / 'shader_pack_sources.cpp',
                PLATFORM_BASE / 'sources/async/native.cpp', PLATFORM_BASE / 'sources/clock/chrono.cpp',
                ROOT / 'platform/shipyard/logging/environment.cpp']
    executable = folder / 'shader_pack_sources.exe'
    run(common + sources + [invoke, '/Fo:' + str(folder) + '/', '/Fe:' + str(executable)], folder, 'build', env)
    return executable


def generate(executable, keys, filters, jobs):
    """Shard keys across jobs generator processes; returns {(id0, id1, tp, srgb): (floats, source path)}."""
    lines = ['%016x %08x %d 0' % (id0, id1, tp) for id0, id1 in sorted(keys) for tp in filters]
    folder = OUT / 'generate'
    folder.mkdir(parents=True, exist_ok=True)
    processes = []
    for shard in range(jobs):
        part = lines[shard::jobs]
        if not part:
            continue
        keys_file = folder / ('keys-%02d.txt' % shard)
        keys_file.write_text('\n'.join(part) + '\n', encoding='ascii')
        out = OUT / 'sources' / ('%02d' % shard)
        out.mkdir(parents=True, exist_ok=True)
        processes.append((out, subprocess.Popen([str(executable), str(TEMPLATE), str(keys_file), str(out)],
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
    sources, failures = {}, []
    for out, process in processes:
        stdout, stderr = process.communicate()
        if process.returncode:
            raise RuntimeError('shader source generator failed: ' + stderr)
        for line in stdout.splitlines():
            parts = line.split(' ', 6)
            if parts[0] == 'K':
                sources[(int(parts[1], 16), int(parts[2], 16), int(parts[3]), int(parts[4]))] = \
                    (int(parts[5]), out / (parts[6] + '.hlsl'))
            elif parts[0] == 'F':
                failures.append(line)
    (OUT / 'lowering-failures.txt').write_text('\n'.join(failures) + '\n', encoding='utf-8')
    return sources


def compile_sources(paths, jobs):
    """fxc for every distinct source and profile; returns {(name, profile): code}."""
    fxc = SDK / 'bin/win32/fxc.exe'
    folder = OUT / 'code'
    folder.mkdir(parents=True, exist_ok=True)
    unique = {}
    for path in paths:
        unique.setdefault(path.stem, path)

    def one(item):
        (name, path), (profile, entry) = item
        target = folder / (name + '.' + profile + '.bin')
        if not target.is_file():
            result = subprocess.run([str(fxc), '/nologo', '/T', profile, '/E', entry, '/Fo', str(target) + '.tmp',
                                     str(path)], capture_output=True, text=True)
            if result.returncode:
                return (name, profile), None, result.stdout + result.stderr
            os.replace(str(target) + '.tmp', target)
        return (name, profile), target.read_bytes(), None

    work = [(pair, profile) for pair in sorted(unique.items()) for profile in PROFILES]
    code, errors = {}, []
    with ThreadPoolExecutor(jobs) as pool:
        for key, data, error in pool.map(one, work):
            if data is None:
                errors.append('%s %s\n%s' % (key[0], key[1], error))
            else:
                code[key] = data
    (OUT / 'compile-failures.txt').write_text('\n'.join(errors) + '\n', encoding='utf-8')
    return code


def program_checksum(id0, id1, flags, floats, vertex, pixel):
    """CRC-32 over the key, float count and both blobs, as shader_cache.cpp verifies it."""
    crc = zlib.crc32(struct.pack('>QIII', id0, id1, flags, floats))
    crc = zlib.crc32(vertex, crc)
    return zlib.crc32(pixel, crc) & 0xFFFFFFFF


def write_pack(programs, path):
    """programs: {(shaderId0, shaderId1, flags): (floats, vertex code, pixel code, lowered source)}.

    Layout per Shipyard sources/xenos/shader_pack.h (version 2). The smallest
    key is the probe: its lowered source's SHA-256 lets the runtime prove the
    XEX still generates what the pack was compiled from.
    """
    header_bytes, entry_bytes = 64, 40
    keys = sorted(programs)
    if not keys:
        raise ValueError('no shader programs to pack')
    offsets, blobs = {}, []
    position = header_bytes + entry_bytes * len(keys)

    def place(code):
        nonlocal position
        if len(code) % 4:
            raise ValueError('microcode size is not a multiple of 4')
        digest = hashlib.sha256(code).digest()
        if digest not in offsets:
            offsets[digest] = position
            blobs.append(code)
            position += len(code)
        return offsets[digest]

    index = bytearray()
    for id0, id1, flags in keys:
        floats, vertex, pixel, _ = programs[(id0, id1, flags)]
        index += struct.pack('>QIIIIIIII', id0, id1, flags, floats, place(vertex), len(vertex), place(pixel),
                             len(pixel), program_checksum(id0, id1, flags, floats, vertex, pixel))
    probe_source = programs[keys[0]][3]
    data = bytearray(struct.pack('>8I', PACK_MAGIC, PACK_VERSION, sdk_define('include/xbox/xdk.h', '_XDK_VER'),
                                 sdk_define('include/xbox/d3dx9core.h', 'D3DX_SDK_VERSION'), len(keys), 0, 0, 0))
    data += hashlib.sha256(probe_source).digest()
    data += index
    for blob in blobs:
        data += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(data))
    return len(keys), len(blobs), len(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--archive', action='append', help='O2R archive (repeatable)')
    parser.add_argument('--out', type=Path, default=OUT / '3shipsty.shaderpack')
    parser.add_argument('--jobs', type=int, default=harvest.default_jobs())
    parser.add_argument('--filters', default='three-point,linear',
                        help='texture filter settings to cover: three-point, linear (linear also covers none)')
    args = parser.parse_args()
    filters = [FILTERS[name] for name in args.filters.split(',')]
    if not args.archive:
        official = ROOT / 'scratch/assets/official-9.2.3'
        args.archive = [str(official / 'oot.o2r'), str(official / 'soh.o2r')]
    OUT.mkdir(parents=True, exist_ok=True)

    setups, modes, c_records = c_state()
    lists, records = harvest.display_list_records([Path(a) for a in args.archive], args.jobs)
    print('archives: %d display lists, %d distinct draw states' % (lists, len(records)))
    keys = harvest.expand(records | c_records, setups, modes, args.jobs)
    print('shader keys: %d' % len(keys))
    executable = build_generator()
    sources = generate(executable, keys, filters, args.jobs)
    code = compile_sources(set(path for _, path in sources.values()), args.jobs)
    programs, incomplete = {}, 0
    for (id0, id1, tp, srgb), (floats, path) in sources.items():
        vertex, pixel = code.get((path.stem, 'vs_3_0')), code.get((path.stem, 'ps_3_0'))
        if vertex is None or pixel is None:
            incomplete += 1
            continue
        programs[(id0, id1, tp | (srgb << 1))] = (floats, vertex, pixel, path.read_bytes())
    count, blobs, size = write_pack(programs, args.out)
    report = dict(archives=args.archive, display_lists=lists, draw_states=len(records), keys=len(keys),
                  sources=len(set(path for _, path in sources.values())), programs=count,
                  programs_without_code=incomplete, unique_microcode=blobs, bytes=size,
                  filters=args.filters, jobs=args.jobs)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('shader pack: %d programs, %d unique microcode blobs, %.1f MiB -> %s' %
          (count, blobs, size / 1048576.0, args.out))


if __name__ == '__main__':
    main()
