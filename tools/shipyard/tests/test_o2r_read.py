"""Contrast the pinned upstream O2R reader with its XDK integrity projection."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from cpp_ast import PARSER, walk
import prepare_resource_manager
from platform_base import resolve


def load_method(source):
    definitions = [node for node in walk(PARSER.parse(source.read_bytes()).root_node)
                   if node.type == 'function_definition'
                   and node.child_by_field_name('declarator').text.decode() ==
                   'O2rArchive::LoadFile(const std::string& filePath)']
    if len(definitions) != 1:
        raise AssertionError(f'Expected one O2R path reader in {source}')
    return definitions[0].text


def main():
    original = ROOT / 'libultraship/src/ship/resource/archive/O2rArchive.cpp'
    lock = json.loads((prepare_resource_manager.OWN / 'runtime-sources.lock.json').read_text())
    pinned = lock['sources']['src/ship/resource/archive/O2rArchive.cpp']
    if hashlib.sha256(original.read_text(encoding='utf-8-sig').encode()).hexdigest() != pinned:
        raise AssertionError('O2R upstream source no longer matches the stable release pin')
    prepare_resource_manager.prepare()
    compiler, environment = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    folder = ROOT / 'scratch/resource-manager-xdk/host-o2r-read'
    contract = Path(__file__).with_name('test_o2r_read_contract.cpp')
    base = resolve(ROOT)
    projected = prepare_resource_manager.OUT / 'generated/src/ship/resource/archive/O2rArchive.cpp'
    for label, source in [('original', original), ('projected', projected)]:
        target = folder / label
        target.mkdir(parents=True, exist_ok=True)
        method = load_method(source)
        support = []
        if label == 'projected':
            declaration = b'Shipyard::Async::mutex sXboxZipMutex;'
            assert source.read_bytes().count(declaration) == 1
            method = b'namespace {\n' + declaration + b'\n}\n' + method
            support = ['/DNOMINMAX', '/FI' + str(base / 'sources/async/native.h'),
                       '/I' + str(base / 'sources'), str(base / 'sources/async/native.cpp')]
        (target / 'method.inc').write_bytes(method)
        command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD',
                   *(['/DSHIPYARD_PROJECTED'] if label == 'projected' else []),
                   '/I' + str(target), str(contract), *support, '/Fe:' + str(target / 'contract.exe')]
        build = subprocess.run(command, cwd=target, env=environment, capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError(f'{label} contract compile failed:\n{build.stdout}{build.stderr}')
        run = subprocess.run([str(target / 'contract.exe')], cwd=target,
                             capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(f'{label} contract failed:\n{run.stdout}{run.stderr}')
        print(label + ': ' + run.stdout.strip())


if __name__ == '__main__':
    main()
