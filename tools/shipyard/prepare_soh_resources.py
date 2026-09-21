"""Hash-locked full SoH leaf resource TUs for XDK, preserving archive formats."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable
from prepare_binary import strong_enum
from prepare_configuration import once
from prepare_resource_manager import syntax

OUT = ROOT / 'scratch/soh-resources-xdk'
OWN = ROOT / 'platform/shipyard/soh-resources'
NAMES = ('Background', 'PlayerAnimation', 'Text', 'Array', 'Cutscene')


def transform(name, text):
    if '/type/' in name and name.endswith('.h') and Path(name).stem in NAMES:
        typename = Path(name).stem
        element = {'Background': 'uint8_t', 'PlayerAnimation': 'int16_t', 'Text': 'MessageEntry',
                   'Array': 'void', 'Cutscene': 'uint32_t'}[typename]
        text = once(text, 'using Resource::Resource;', typename + '(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::Resource<' + element + '>(initData) {}')
    if name.endswith('/Array.h'):
        # XDK instantiates vector's destructor at the explicit forwarding constructor.
        text = once(text, '#include <ship/resource/Resource.h>', '#include <ship/resource/Resource.h>\n#include <fast/lus_gbi.h>')
    if name.endswith(('/Array.h', '/Cutscene.h', '/SohResourceType.h')):
        text = re.sub(r'enum class (\w+) \{(.*?)\n\};', lambda m: strong_enum(m[1], m[2]), text, flags=re.S)
        text = '#include "binary/compat.h"\n' + text
    if name.endswith(('/Array.cpp', '/ArrayFactory.cpp')):
        text = text.replace('switch (ArrayType)', 'switch (ArrayType.GetValue())')
        text = text.replace('switch (ArrayScalarType)', 'switch (ArrayScalarType.GetValue())')
        text = text.replace('switch (array->ArrayScalarType)', 'switch (array->ArrayScalarType.GetValue())')
    # No endian/body rewrites: typed reads and mixed-width cutscene helpers remain intact.
    text = syntax(text)
    guard = 'SHIPYARD_SOH_' + name.upper().replace('/', '_').replace('.', '_')
    if name.endswith('.h'):
        text = '#ifndef ' + guard + '\n#define ' + guard + '\n' + text + '\n#endif\n'
    return '// Generated from hash-locked Shipwright9.2.3; do not edit.\n' + text


def prepare(source_root=ROOT, output=OUT / 'generated'):
    output = Path(output).resolve()
    if not output.is_relative_to(OUT.resolve()):
        raise ValueError('SoH resource output must stay beneath its owned scratch directory')
    lock = json.loads((OWN / 'sources.lock.json').read_text())
    pending = {}
    for name, expected in lock['sources'].items():
        text = (Path(source_root) / name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError('SoH resource source drift: ' + name)
        pending[name] = transform(name, text)
    for name, text in pending.items():
        stable(output / name, text)
    manifest = {'source_commit': lock['source_commit'], 'source_sha256': lock['sources'],
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'generated_sha256': {n: hashlib.sha256(t.encode()).hexdigest() for n, t in pending.items()}}
    stable(output / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    return manifest


def includes(projected):
    resources = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_resources.py'))
    base = OUT / 'generated' if projected else ROOT
    paths = [base / 'soh', verified('tinyxml2')]
    if projected:
        paths += [ROOT / 'scratch/fast3d-xdk/generated/include', ROOT / 'platform/shipyard/game/include']
    return paths + resources['includes'](projected) + [ROOT / 'libultraship/include']


def units(base):
    return [Path(base) / 'soh/soh/resource' / folder / (n + suffix + '.cpp')
            for n in NAMES for folder, suffix in (('type', ''), ('importer', 'Factory'))]


def build():
    prepare()
    folder = OUT / 'xdk'; folder.mkdir(parents=True, exist_ok=True)
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags = ['/nologo', '/c', '/TP', '/EHsc', '/MT', '/D_XBOX', '/D_XBOX_VER=200', '/DNOMINMAX',
             '/DSPDLOG_ACTIVE_LEVEL=0', '/I' + str(sdk / 'include/xbox')]
    flags += ['/I' + str(p) for p in includes(True)]
    records = []
    for source in units(OUT / 'generated') + [OWN / 'xdk_abi.cpp']:
        obj = folder / (source.stem + '.obj')
        command = [str(sdk / 'bin/win32/cl.exe')] + flags + [str(source), '/Fo' + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix('.log'), result.stdout + result.stderr)
        records.append(dict(source=source.relative_to(ROOT).as_posix(), exit=result.returncode, command=command,
                            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                            object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest() if not result.returncode else None))
        if not result.returncode and struct.unpack_from('<H', obj.read_bytes())[0] != 0x1f2:
            raise ValueError('Not a Xenon object')
    stable(folder / 'build.json', json.dumps(records, indent=2) + '\n')
    for row in records: print(str(row['exit']) + ' ' + row['source'])
    if any(r['exit'] for r in records): raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    if parser.parse_args().build: build()
    else: prepare()
