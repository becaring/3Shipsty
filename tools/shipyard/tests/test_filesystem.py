"""Host standard-library differential, logical Xbox cwd and real XDK objects."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/filesystem-xdk'
OWN = ROOT / 'platform/shipyard/filesystem'
TEST = Path(__file__).with_name('test_filesystem_contract.cpp')
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
    compiler, env = ENV.host_environment(); results = {}
    for label, define in [('upstream', '/DSHIPYARD_ORIGINAL'), ('generated', '/DSHIPYARD_PROJECTED'),
                          ('logical', '/DSHIPYARD_TEST_LOGICAL_CWD')]:
        folder = OUT / ('host-' + label); folder.mkdir(parents=True, exist_ok=True)
        command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/W4', define,
                   '/I' + str(OWN), '/I' + str(OUT / 'generated'),
                   '/Fe:' + str(folder / 'contract.exe'), '/Fo:' + str(folder) + '/', TEST]
        if label != 'upstream':
            command += [OWN / 'filesystem.cpp', ROOT / 'platform/shipyard/async/native.cpp']
        run(command, folder, 'compile', env)
        # Kept as evidence; all fixture mutations are inside owned scratch only.
        fixture = Path(tempfile.mkdtemp(prefix='fixture-', dir=folder))
        (fixture / 'link-target').mkdir(); (fixture / 'link-area').mkdir()
        run(['cmd.exe', '/c', 'mklink', '/J', fixture / 'link-area/link', fixture / 'link-target'], folder, 'link-fixture')
        results[label] = run([folder / 'contract.exe', fixture], folder, 'run')['stdout']
    assert len(set(results.values())) == 1, 'host filesystem contract differs'
    folder = OUT / 'xdk'; folder.mkdir(parents=True, exist_ok=True)
    base = [ENV.XDK / 'bin/win32/cl.exe', '/nologo', '/c', '/EHsc', '/D_XBOX', '/D_XBOX_VER=200',
            '/I' + str(ENV.XDK / 'include/xbox'), '/I' + str(OWN), '/I' + str(OUT / 'generated')]
    objects = {}
    for source in [OWN / 'filesystem.cpp', TEST]:
        obj = folder / (source.stem + '.obj')
        run(base + ['/Fo' + str(obj), source], folder, source.stem)
        assert struct.unpack_from('<H', obj.read_bytes())[0] == 0x1f2, 'expected PPC BE object'
        objects[obj.name] = hashlib.sha256(obj.read_bytes()).hexdigest()
    (OUT / 'verification.json').write_text(json.dumps({'host': results, 'xdk_objects': objects,
            'target_runtime_executed': False}, indent=2) + '\n', encoding='utf-8')
    print('Host differential and logical cwd pass; filesystem and real Directory contract compile to PPC BE objects.')


if __name__ == '__main__': main()
