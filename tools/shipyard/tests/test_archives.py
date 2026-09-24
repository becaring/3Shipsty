"""Run native-boundary libzip on the actual official/extracted modern archives."""
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
OUT = ROOT / 'scratch/libzip-xdk'


def main():
    helpers = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))
    compiler, env = helpers['host_environment']()
    folder = OUT / 'host'
    command = [str(compiler), '/nologo', '/EHsc', '/MD', '/DNOMINMAX',
               '/I' + str(OUT / 'generated'), '/I' + str(ROOT / 'platform/shipyard'),
               '/I' + str(PLATFORM_BASE), '/I' + str(PLATFORM_BASE / 'sources'),
               '/I' + str(ROOT / 'scratch/deps/zlib'),
               str(Path(__file__).with_name('test_archives_contract.cpp')),
               str(PLATFORM_BASE / 'sources/filesystem/filesystem.cpp'),
               str(PLATFORM_BASE / 'sources/async/native.cpp'),
               str(folder / 'zip.lib'), str(folder / 'zlib.lib'), 'advapi32.lib',
               '/Fe:' + str(folder / 'archives.exe'), '/Fo:' + str(folder) + '/']
    result = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True)
    (folder / 'contract-build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('See contract-build.log')
    execution = subprocess.run([str(folder / 'archives.exe'), str(ROOT / 'scratch/assets/official-9.2.3'), str(folder / 'update-test.o2r')], cwd=folder, capture_output=True, text=True)
    evidence = dict(command=command, stdout=execution.stdout, stderr=execution.stderr,
                    exit=execution.returncode, target_runtime_executed=False)
    (OUT / 'archive-verification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(execution.stdout)
    if execution.returncode:
        raise RuntimeError('Archive contract failed: ' + str(execution.returncode))
    for path in (OUT / 'xdk').glob('*.obj'):
        assert struct.unpack_from('<H', path.read_bytes())[0] == 0x1f2, path


if __name__ == '__main__':
    main()
