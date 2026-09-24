"""Validate retained BS algorithms and real native async primitives, no XEX."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
BASE = resolve(ROOT)
OUT = ROOT / 'scratch/async-xdk'
TEST = Path(__file__).with_name('test_async_contract.cpp')
SPEC = importlib.util.spec_from_file_location('binary_environment', Path(__file__).with_name('test_binary.py'))
ENV = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(ENV)


def run(command, folder, name, env=None, success=True):
    result = subprocess.run(list(map(str, command)), cwd=folder, env=env, text=True,
                            capture_output=True, timeout=45)
    record = {'command': list(map(str, command)), 'cwd': str(folder), 'returncode': result.returncode,
              'stdout': result.stdout, 'stderr': result.stderr}
    (folder / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    if success and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return record


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--upstream-only', action='store_true'); args = parser.parse_args()
    native = (BASE / 'sources/async/native.cpp').read_text(encoding='utf-8')
    pinned = native[native.index('DWORD WINAPI joining_thread::run'):native.index('joining_thread::joining_thread(joining_thread&&')]
    assert pinned.index('XSetThreadProcessor(GetCurrentThread(), processor)') < pinned.index('entry(argument)')
    assert 'TerminateThread(' not in pinned, 'XDK has no recoverable native thread termination API'
    generated = OUT / 'generated'
    assert (generated / 'BS_thread_pool.hpp').exists(), 'async projection not implemented'
    compiler, env = ENV.host_environment()
    results = {}
    for label, includes, define in [('upstream', ROOT / 'platform/shipyard/thread-pool/upstream', '/DTEST_UPSTREAM'),
                                    ('generated', generated, '/DSHIPYARD_PROJECTED')]:
        folder = OUT / ('host-' + label); folder.mkdir(parents=True, exist_ok=True)
        command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/W4', define,
                   '/I' + str(includes), '/I' + str(BASE / 'sources'), '/I' + str(ROOT / 'platform/shipyard'),
                   '/Fe:' + str(folder / 'contract.exe'), '/Fo:' + str(folder) + '/',
                   TEST, BASE / 'sources/async/native.cpp']
        run(command, folder, 'compile', env)
        results[label] = run([folder / 'contract.exe'], folder, 'run')['stdout']
        death = run([folder / 'contract.exe', '--detached-throws'], folder, 'detached-exception', success=False)
        assert death['returncode'] == 73, 'detached exception must terminate as pinned BS does'
        if args.upstream_only: return
    assert results['upstream'] == results['generated'], 'pool behavior differs'
    folder = OUT / 'xdk'; folder.mkdir(parents=True, exist_ok=True)
    base = [ENV.XDK / 'bin/win32/cl.exe', '/nologo', '/c', '/EHsc', '/D_XBOX', '/D_XBOX_VER=200',
            '/I' + str(ENV.XDK / 'include/xbox'), '/I' + str(generated),
            '/I' + str(BASE / 'sources'), '/I' + str(ROOT / 'platform/shipyard')]
    objects = {}
    for source in [BASE / 'sources/async/native.cpp', TEST]:
        obj = folder / (source.stem + '.obj')
        run(base + ['/Fo' + str(obj), source], folder, source.stem)
        assert struct.unpack_from('<H', obj.read_bytes())[0] == 0x1f2, 'expected PPC BE object'
        objects[obj.name] = hashlib.sha256(obj.read_bytes()).hexdigest()
    (OUT / 'verification.json').write_text(json.dumps({'host': results, 'xdk_objects': objects,
            'target_runtime_executed': False}, indent=2) + '\n', encoding='utf-8')
    print('Host original/projected pool concurrency contract passes; native async and contract compile to PPC BE objects.')


if __name__ == '__main__': main()
