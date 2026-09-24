"""Owned modern binarytools differential and native-XDK object validation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
OUT = ROOT / 'scratch/binary-xdk'
TESTS = Path(__file__).parent
NAMES = ('BinaryReader', 'BinaryWriter', 'MemoryStream', 'Stream')
XDK = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')


def invoke(command, folder, label, env=None, success=True):
    result = subprocess.run(list(map(str, command)), cwd=folder, env=env,
                            capture_output=True, text=True)
    record = {'command': list(map(str, command)), 'cwd': str(folder),
              'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    (folder / (label + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    if success and result.returncode:
        raise AssertionError(f'{label} failed: {result.stdout}{result.stderr}')
    return record


def host_environment():
    msvc = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.43.34808')
    sdk = Path('C:/Program Files (x86)/Windows Kits/10')
    env = os.environ.copy()
    env['PATH'] = str(msvc / 'bin/Hostx64/x64') + os.pathsep + env['PATH']
    env['INCLUDE'] = ';'.join(map(str, [msvc / 'include'] + [sdk / 'Include/10.0.26100.0' / p for p in ('ucrt', 'shared', 'um')]))
    env['LIB'] = ';'.join(map(str, [msvc / 'lib/x64'] + [sdk / 'Lib/10.0.26100.0' / p / 'x64' for p in ('ucrt', 'um')]))
    return msvc / 'bin/Hostx64/x64/cl.exe', env


def fixture_paths():
    folder = OUT / 'fixtures'; folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, order in (('little', '<'), ('big', '>')):
        values = (-42, 240, -12345, 0xfedc, -123456789, 0xfedcba98,
                  -0x0102030405060708, 0xfedcba9876543210, 1.5, -1234.125,
                  float('inf'), -float('inf'), -0.0, -0.0, 0x7fc00000, 0x7ff8000000000000)
        data = struct.pack(order + 'bBhHiIqQfdfdfdIQ', *values)
        data += struct.pack(order + 'i', 3) + b'abcxy\0z'
        path = folder / (name + '.bin'); path.write_bytes(data); paths.append(path)
    return paths


def host(label, source):
    folder = OUT / label; folder.mkdir(parents=True, exist_ok=True)
    compiler, env = host_environment()
    command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/GR', '/MD', '/W4',
               '/I' + str(source / 'include'), '/I' + str(ROOT / 'platform/shipyard'),
               '/I' + str(PLATFORM_BASE / 'sources'),
               '/Fe:' + str(folder / 'contract.exe'), '/Fo:' + str(folder) + '/',
               TESTS / 'test_binary_contract.cpp']
    command += [source / 'src/ship/utils/binarytools' / (name + '.cpp') for name in NAMES]
    if label == 'host-generated':
        command.insert(1, '/DSHIPYARD_PROJECTED')
    invoke(command, folder, 'compile', env)
    return invoke([folder / 'contract.exe', *fixture_paths()], folder, 'run')['stdout']


def xdk(label, source, expected_success):
    folder = OUT / label; folder.mkdir(parents=True, exist_ok=True)
    base = [XDK / 'bin/win32/cl.exe', '/nologo', '/EHsc', '/GR', '/D_XBOX', '/D_XBOX_VER=200',
            '/I' + str(XDK / 'include/xbox'), '/I' + str(source / 'include'),
            '/I' + str(ROOT / 'platform/shipyard'), '/I' + str(PLATFORM_BASE / 'sources')]
    records = []
    for name in NAMES:
        record = invoke(base + ['/c', '/Fo' + str(folder / (name + '.obj')),
                                 source / 'src/ship/utils/binarytools' / (name + '.cpp')],
                        folder, name, success=expected_success)
        records.append(record)
    for label, flags, path in [('endian-preprocess', ['/EP', '/TC'], TESTS / 'test_binary_endian.c'),
                               ('contract', ['/c', '/Fo' + str(folder / 'contract.obj')], TESTS / 'test_binary_xdk.cpp')]:
        records.append(invoke(base + flags + [path], folder, label, success=expected_success))
    if not expected_success:
        assert all(r['returncode'] != 0 for r in records), 'expected original XDK failures'
        assert 'Original endian detection fails' in records[-2]['stderr'] + records[-2]['stdout']
    else:
        invoke(base + ['/c', '/TC', '/Fo' + str(folder / 'endian.obj'), TESTS / 'test_binary_endian.c'], folder, 'endian-compile')
        for path in folder.glob('*.obj'):
            assert struct.unpack_from('<H', path.read_bytes())[0] == 0x1f2, 'not PowerPC BE COFF'
    return records


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    original = host('host-original', ROOT / 'libultraship')
    if args.baseline_only:
        xdk('xdk-original', ROOT / 'libultraship', False)
        print('Original host contract passes; original XDK TUs and endian detection fail as expected.')
        return
    generated = OUT / 'generated'
    assert (generated / 'manifest.json').exists(), 'binary projection has not been implemented'
    projected = host('host-generated', generated)
    assert original == projected, 'original/projected host behavior differs'
    xdk('xdk-generated', generated, True)
    evidence = {'original_host': original, 'generated_host': projected,
                'target_runtime_executed': False, 'native_objects': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (OUT / 'xdk-generated').glob('*.obj')}}
    (OUT / 'verification.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('Host original/projected differential passes; four real XDK TUs and contracts compile to PPC BE objects.')


if __name__ == '__main__':
    main()
