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
NAMES = ('Background', 'PlayerAnimation', 'Text', 'Array', 'Cutscene',
         'Animation', 'AudioSequence', 'AudioSoundFont', 'CollisionHeader', 'Path', 'SkeletonLimb')


def transform(name, text):
    if '/type/' in name and name.endswith('.h') and Path(name).stem in NAMES:
        typename = Path(name).stem
        element = {'Background': 'uint8_t', 'PlayerAnimation': 'int16_t', 'Text': 'MessageEntry',
                   'Array': 'void', 'Cutscene': 'uint32_t', 'Animation': 'AnimationData',
                   'AudioSequence': 'Sequence', 'AudioSoundFont': 'SoundFont',
                   'CollisionHeader': 'CollisionHeaderData', 'Path': 'PathData',
                   'SkeletonLimb': 'SkeletonLimbData'}[typename]
        text = once(text, 'using Resource::Resource;', typename + '(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::Resource<' + element + '>(initData) {}')
    if name.endswith('/Array.h'):
        # XDK instantiates vector's destructor at the explicit forwarding constructor.
        text = once(text, '#include <ship/resource/Resource.h>', '#include <ship/resource/Resource.h>\n#include <fast/lus_gbi.h>')
    if name.endswith(('/Array.h', '/Cutscene.h', '/SohResourceType.h', '/Animation.h', '/SkeletonLimb.h')):
        text = re.sub(r'enum class (\w+) \{(.*?)\n\};', lambda m: strong_enum(m[1], m[2]), text, flags=re.S)
        text = '#include "binary/compat.h"\n' + text
    if name.endswith(('/Array.cpp', '/ArrayFactory.cpp')):
        text = text.replace('switch (ArrayType)', 'switch (ArrayType.GetValue())')
        text = text.replace('switch (ArrayScalarType)', 'switch (ArrayScalarType.GetValue())')
        text = text.replace('switch (array->ArrayScalarType)', 'switch (array->ArrayScalarType.GetValue())')
    if name.endswith('/Animation.cpp'):
        text = once(text, 'switch (type)', 'switch (type.GetValue())')
    if name.endswith('/SkeletonLimb.cpp'):
        text = once(text, 'switch (limbType)', 'switch (limbType.GetValue())')
    if name.endswith('/SkeletonLimbFactory.cpp'):
        text = once(text, '#include "libultraship/libultraship.h"', '// No symbols from the umbrella header are used.')
        text = once(text, 'static_cast<int32_t>(skeletonLimb->skinSegmentType)', 'skeletonLimb->skinSegmentType.GetValue()')
    if name.endswith('/PathLogger.h'):
        text = once(text, '#include "soh/OTRGlobals.h"', '#include <libultraship/bridge/consolevariablebridge.h>')
    if name.endswith('/AudioSample.h'):
        text = once(text, 'using Resource::Resource;', 'AudioSample(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::Resource<Sample>(initData), tuning(-1.0f) {}')
        text = once(text, 'AudioSample() : Resource(std::shared_ptr<Ship::ResourceInitData>())', 'AudioSample() : Resource(std::shared_ptr<Ship::ResourceInitData>()), tuning(-1.0f)')
        text = once(text, 'float tuning = -1.0f;', 'float tuning;')
    if name.endswith('/AudioSequenceFactory.cpp'):
        text = re.sub(r'static_assert\((std::is_fundamental[^;]+)\);', r'static_assert(\1, "Instruction arguments must be fundamental");', text)
        text = text.replace('constexpr ', 'const ').replace('0b11', '3')
    if name.endswith('/AudioSoundFontFactory.cpp'):
        text = '#include "soh-resources/format.h"\n' + text
        text = text.replace('snprintf(', 'Shipyard::SohResources::snprintf(')
        text = re.sub(r'(?<!std::)\b(static_pointer_cast|dynamic_pointer_cast)<', r'std::\1<', text)
        text = once(text, '#include <z64.h>', '// The factory uses only the audio enum declarations below.')
        text = once(text, '#include "z64audio.h"', '#include "soh/resource/audio_enums.h"\n#include <ship/utils/binarytools/endianness.h>')
        text = once(text, '.delay = (s16)element->IntAttribute("Delay"),', '(s16)element->IntAttribute("Delay"),')
        text = once(text, '.arg = (s16)element->IntAttribute("Arg"),', '(s16)element->IntAttribute("Arg"),')
        # Envelope storage is big-endian bytes, including values parsed from XML.
        text = text.replace('BSWAP16(env.delay)', 'BE16SWAP(env.delay)').replace('BSWAP16(env.arg)', 'BE16SWAP(env.arg)')
    if name.endswith('/AudioSoundFont.cpp'):
        lower_ranges = runpy.run_path(str(ROOT / 'platform/shipyard/imgui/projection.py'))['lower_ranges']
        text = lower_ranges(text.encode(), 'Shipyard::Resources::begin', 'Shipyard::Resources::end').decode()
        text = '#include "resources/runtime_support.h"\n' + text
    # Typed reads and mixed-width cutscene helpers remain intact; the XML envelope
    # conversion above is the explicit native-to-BE byte storage boundary.
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
        if name == 'soh/include/z64audio.h':
            # Actual upstream enum declarations, without the unrelated game-wide structs.
            enums = [re.search(r'typedef enum \{[^{}]*\} ' + n + ';', text)[0]
                     for n in ('SampleMedium', 'SampleCodec', 'AudioCacheType')]
            pending['soh/soh/resource/audio_enums.h'] = '#pragma once\n' + '\n\n'.join(enums) + '\n'
        else:
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
    paths = [base / 'soh', verified('tinyxml2'), ROOT / 'soh/include', ROOT / 'soh']
    if projected:
        paths += [ROOT / 'scratch/fast3d-xdk/generated/include', ROOT / 'platform/shipyard/game/include',
                  ROOT / 'scratch/console-variables-xdk/generated/include', ROOT / 'scratch/audio-xdk/generated/include',
                  ROOT / 'scratch/resource-manager-xdk/generated/include', ROOT / 'scratch/async-xdk/generated']
    return paths + resources['includes'](projected) + [ROOT / 'libultraship/include']


def units(base):
    return [Path(base) / 'soh/soh/resource' / folder / (n + suffix + '.cpp')
            for n in NAMES for folder, suffix in (('type', ''), ('importer', 'Factory'))] + [
                Path(base) / 'soh/soh/resource/logging/PathLogger.cpp']


def build():
    prepare()
    folder = OUT / 'xdk'; folder.mkdir(parents=True, exist_ok=True)
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags = ['/nologo', '/c', '/TP', '/EHsc', '/GR', '/MT', '/D_XBOX', '/D_XBOX_VER=200', '/DNOMINMAX',
             '/DSPDLOG_ACTIVE_LEVEL=0', '/I' + str(sdk / 'include/xbox')]
    flags += ['/FI' + str(ROOT / 'scratch/configuration-xdk/generated/include/compile_definitions.h')]
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
