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
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
OUT = ROOT / 'scratch/soh-resources-xdk'
OWN = ROOT / 'platform/shipyard/soh-resources'
NAMES = ('Background', 'PlayerAnimation', 'Text', 'Array', 'Cutscene',
         'Animation', 'AudioSequence', 'AudioSoundFont', 'CollisionHeader', 'Path', 'SkeletonLimb', 'Scene', 'Skeleton')
SCENE_COMMANDS = ('EndMarker', 'SetActorList', 'SetAlternateHeaders', 'SetCameraSettings', 'SetCollisionHeader',
                  'SetCsCamera', 'SetCutscenes', 'SetEchoSettings', 'SetEntranceList', 'SetExitList',
                  'SetLightingSettings', 'SetLightList', 'SetMesh', 'SetObjectList', 'SetPathways',
                  'SetRoomBehavior', 'SetRoomList', 'SetSkyboxModifier', 'SetSkyboxSettings', 'SetSoundSettings',
                  'SetSpecialObjects', 'SetStartPositionList', 'SetTimeSettings', 'SetTransitionActorList', 'SetWindSettings')


def transform(name, text):
    if '/type/' in name and name.endswith('.h') and Path(name).stem in NAMES:
        typename = Path(name).stem
        element = {'Background': 'uint8_t', 'PlayerAnimation': 'int16_t', 'Text': 'MessageEntry',
                   'Array': 'void', 'Cutscene': 'uint32_t', 'Animation': 'AnimationData',
                   'AudioSequence': 'Sequence', 'AudioSoundFont': 'SoundFont',
                   'CollisionHeader': 'CollisionHeaderData', 'Path': 'PathData',
                   'SkeletonLimb': 'SkeletonLimbData', 'Scene': 'void', 'Skeleton': 'SkeletonData'}[typename]
        text = once(text, 'using Resource::Resource;', typename + '(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::Resource<' + element + '>(initData) {}')
    if name.endswith('/Array.h'):
        # XDK instantiates vector's destructor at the explicit forwarding constructor.
        text = once(text, '#include <ship/resource/Resource.h>', '#include <ship/resource/Resource.h>\n#include <fast/lus_gbi.h>')
    if name.endswith(('/Array.h', '/Cutscene.h', '/SohResourceType.h', '/Animation.h', '/SkeletonLimb.h', '/Skeleton.h')):
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
    if name.endswith('/Skeleton.h'):
        text=once(text,'inline static const std::string sOtr = "__OTR__";','static const std::string sOtr;')
    if name.endswith('/Skeleton.cpp'):
        text=once(text,'#include "soh/OTRGlobals.h"','// No OTRGlobals symbols are used by this complete patcher.')
        text=once(text,'#include "libultraship/libultraship.h"','#include <ship/Context.h>')
        text=once(text,'#include "macros.h"','#include "z64.h"\n#include "macros.h"')
        text=once(text,'namespace SOH {','namespace SOH {\nconst std::string SkeletonPatcher::sOtr = "__OTR__";')
        text=once(text,'switch (type)','switch (type.GetValue())')
        text=text.replace('path.starts_with(sOtr)','Shipyard::Resources::starts_with(path,sOtr)').replace('path.starts_with(Ship::IResource::gAltAssetPrefix)','Shipyard::Resources::starts_with(path,Ship::IResource::gAltAssetPrefix)')
        lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
        text='#include "resources/runtime_support.h"\n'+lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    if name.endswith('/SkeletonFactory.cpp'):
        text=once(text,'#include <libultraship/libultraship.h>','#include <ship/Context.h>\n#include <ship/resource/ResourceManager.h>')
        text=text.replace('(uint32_t)skeleton->type','static_cast<uint32_t>(skeleton->type.GetValue())').replace('(uint8_t)skeleton->type','static_cast<uint8_t>(skeleton->type.GetValue())')
        text=text.replace('(uint8_t)skel->type','static_cast<uint8_t>(skel->type.GetValue())')
    if name.endswith('/PathLogger.h'):
        text = once(text, '#include "soh/OTRGlobals.h"', '#include <libultraship/bridge/consolevariablebridge.h>')
    if name.endswith('/SceneCommandLoggers.h'):
        text = once(text, '#include "soh/OTRGlobals.h"', '#include <libultraship/bridge/consolevariablebridge.h>')
    if name.endswith('/SceneCommand.h'):
        text = '#include "soh-resources/enum.h"\n' + text
        text = re.sub(r'enum class SceneCommandID : uint8_t \{(.*?)\n\};',
                      lambda m: strong_enum('SceneCommandID', m[1]).replace('Shipyard::Binary::ScopedEnum', 'Shipyard::SohResources::ByteEnum'),
                      text, flags=re.S)
        text = once(text, 'using IResource::IResource;',
                    'ISceneCommand(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::IResource(initData) {}')
        text = once(text, 'using ISceneCommand::ISceneCommand;',
                    'SceneCommand(std::shared_ptr<Ship::ResourceInitData> initData) : ISceneCommand(initData) {}\n'
                    '    SceneCommand() : ISceneCommand() {}')
        text += '\nnamespace std { template<> struct hash<SOH::SceneCommandID> {\n'
        text += 'size_t operator()(const SOH::SceneCommandID& value) const { return value.GetValue(); }\n}; }\n'
    if '/type/scenecommand/' in name and Path(name).stem in SCENE_COMMANDS and name.endswith('.h'):
        typename, element = re.search(r'class (\w+)(?: final)? : public SceneCommand<([^>]+)>', text).groups()
        body = re.search(r'class ' + typename + r'(?: final)? : public SceneCommand<[^>]+> \{(.*?)\n\};', text, re.S)[1]
        members = re.findall(r'^    [^\n;{}]+ (\w+);$', body, re.M)
        # The inherited original default is implicit: make_shared<T>() first
        # zero-initializes its payload. Preserve that value-initialized state.
        defaults = ''.join(', ' + member + '()' for member in members)
        text = once(text, 'using SceneCommand::SceneCommand;',
                    typename + '(std::shared_ptr<Ship::ResourceInitData> initData) : SceneCommand<' + element + '>(initData) {}\n'
                    '    ' + typename + '() : SceneCommand<' + element + '>()' + defaults + ' {}')
    if '/importer/scenecommand/' in name and name.endswith('.cpp'):
        # These factories use Context/ResourceManager, or no umbrella symbols at all.
        text = re.sub(r'#include [<"]libultraship/libultraship.h[>"]',
                      '#include <ship/Context.h>\n#include <ship/resource/ResourceManager.h>' if 'Ship::Context::' in text
                      else '// No symbols from the umbrella header are used.', text)
    if name.endswith('/SceneFactory.h'):
        text = text.replace('static inline std::unordered_map', 'static std::unordered_map')
    if name.endswith('/SceneFactory.cpp'):
        text = once(text, 'namespace SOH {', 'namespace SOH {\n'
                    'std::unordered_map<SceneCommandID, std::shared_ptr<SceneCommandFactoryBinaryV0>> ResourceFactoryBinarySceneV0::sceneCommandFactories;\n'
                    'std::unordered_map<SceneCommandID, std::shared_ptr<SceneCommandFactoryXMLV0>> ResourceFactoryXMLSceneV0::sceneCommandFactories;')
        text = text.replace('std::to_string(index)', 'Shipyard::SohResources::UIntToString(index)')
        text = text.replace('(uint32_t)cmdID', 'static_cast<uint32_t>(cmdID.GetValue())')
        match = re.search(r'std::vector<std::string> commandNames = \{(.*?)\n\};', text, re.S)
        if not match: raise ValueError('Scene command name table drift')
        text = once(text, match[0], 'static const char* const commandNameValues[] = {' + match[1] + '\n};\n'
                    'std::vector<std::string> commandNames(commandNameValues, commandNameValues + sizeof(commandNameValues) / sizeof(commandNameValues[0]));')
    if name.endswith('/AudioSample.h'):
        text = once(text, 'using Resource::Resource;', 'AudioSample(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::Resource<Sample>(initData), tuning(-1.0f) {}')
        text = once(text, 'AudioSample() : Resource(std::shared_ptr<Ship::ResourceInitData>())', 'AudioSample() : Resource(std::shared_ptr<Ship::ResourceInitData>()), tuning(-1.0f)')
        text = once(text, 'float tuning = -1.0f;', 'float tuning;')
    if name.endswith('/AudioSampleFactory.cpp'):
        text='#include "async/detached.h"\n#include "soh-resources/format.h"\n#include <ship/utils/binarytools/endianness.h>\n'+text
        text=once(text,'#include "z64.h"','// Only the actual codec/medium declarations are needed from game audio headers.')
        text=once(text,'#include "z64audio.h"','#include "soh/resource/audio_enums.h"')
        match=re.search(r'typedef enum class OggType \{(.*?)\} OggType;',text,re.S)
        if not match:raise ValueError('Ogg type inventory drift')
        text=once(text,match[0],strong_enum('OggType',match[1]))
        text=once(text,'switch (GetOggType(&fileData))','switch (GetOggType(&fileData).GetValue())')
        text=text.replace('[[maybe_unused]] ','').replace('snprintf(', 'Shipyard::SohResources::snprintf(')
        text,count=re.subn(r'(?m)^(\s*)\.(data|pos|size) = ',r'\1',text)
        if count!=3:raise ValueError('Ogg file-data initializer drift')
        for worker,args in [('Mp3','audioSample, sampleFile'),('Flac','audioSample, sampleFile'),('Ogg','audioSample, sampleFile, initData')]:
            text=once(text,'std::thread fileDecoderThread = std::thread('+worker+'DecoderWorker, '+args+');\n            fileDecoderThread.detach();',
                      'Shipyard::Async::launch_detached(['+args+']() { '+worker+'DecoderWorker('+args+'); });')
        # The mixer consumes native int16 PCM: aLoadBuffer copies bytes directly
        # into the native signed-sample array. Only Vorbis requests an explicit
        # byte order; dr_* decode APIs already produce native signed samples.
        text=once(text,'ov_read(&vf, dataBuff, 4096, 0, 2, 1, &bitStream)',
                  'ov_read(&vf, dataBuff, 4096, Ship::Endianness::Native == Ship::Endianness::Big ? 1 : 0, 2, 1, &bitStream)')
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
    paths = [base / 'soh', verified('tinyxml2'), verified('dr-libs'), ROOT/'scratch/vorbis-xdk/source/include',
             ROOT/'scratch/codec-xdk/include', ROOT / 'soh/include', ROOT / 'soh', ROOT/'soh/assets']
    if projected:
        paths[1:1]=[ROOT/'scratch/game-xdk/full/source/soh',ROOT/'scratch/game-xdk/full/source/soh/include']
        paths += [PLATFORM_BASE / 'sources', ROOT / 'scratch/fast3d-xdk/generated/include', ROOT / 'platform/shipyard/game/include',
                  ROOT / 'scratch/console-variables-xdk/generated/include', ROOT / 'scratch/audio-xdk/generated/include',
                  ROOT / 'scratch/resource-manager-xdk/generated/include', ROOT / 'scratch/async-xdk/generated']
    return paths + resources['includes'](projected) + [ROOT / 'libultraship/include']


def units(base):
    return [Path(base) / 'soh/soh/resource' / folder / (n + suffix + '.cpp')
            for n in NAMES for folder, suffix in (('type', ''), ('importer', 'Factory'))] + [
                Path(base) / 'soh/soh/resource/logging/PathLogger.cpp',
                Path(base) / 'soh/soh/resource/type/AudioSample.cpp',
                Path(base) / 'soh/soh/resource/importer/AudioSampleFactory.cpp'] + scene_units(base)


def scene_units(base):
    return [Path(base) / 'soh/soh/resource' / folder / (n + suffix + '.cpp')
            for n in SCENE_COMMANDS for folder, suffix in (('type/scenecommand', ''), ('importer/scenecommand', 'Factory'))] + [
                Path(base) / 'soh/soh/resource/importer/scenecommand/SceneCommandFactory.cpp',
                Path(base) / 'soh/soh/resource/logging/SceneCommandLoggers.cpp']


def build(scene_only=False,sample_only=False,skeleton_only=False):
    prepare()
    folder = OUT / 'xdk'; folder.mkdir(parents=True, exist_ok=True)
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags = ['/nologo', '/c', '/TP', '/EHsc', '/GR', '/MT', '/D_XBOX', '/D_XBOX_VER=200', '/DNOMINMAX','/DF3DEX_GBI_2','/DINCLUDE_MPQ_SUPPORT','/DCONTROLLERBUTTONS_T=uint32_t',
             '/DSPDLOG_ACTIVE_LEVEL=0', '/I' + str(sdk / 'include/xbox')]
    flags += ['/FI' + str(ROOT / 'scratch/configuration-xdk/generated/include/compile_definitions.h')]
    flags += ['/I' + str(p) for p in includes(True)]
    records = []
    sources = units(OUT / 'generated') if not scene_only else scene_units(OUT / 'generated') + [
        OUT / 'generated/soh/soh/resource/type/Scene.cpp', OUT / 'generated/soh/soh/resource/importer/SceneFactory.cpp']
    if sample_only:sources=[p for p in units(OUT/'generated') if p.stem in ('AudioSample','AudioSampleFactory')]+[PLATFORM_BASE/'sources/async/detached.cpp']
    if skeleton_only:sources=[p for p in units(OUT/'generated') if p.stem in ('Skeleton','SkeletonFactory')]
    for source in sources + [OWN / 'xdk_abi.cpp']:
        obj = folder / (source.stem + '.obj')
        command = [str(sdk / 'bin/win32/cl.exe')] + flags + [str(source), '/Fo' + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix('.log'), result.stdout + result.stderr)
        label=('shipyard/'+source.relative_to(PLATFORM_BASE).as_posix()
               if source.is_relative_to(PLATFORM_BASE) else source.relative_to(ROOT).as_posix())
        records.append(dict(source=label, exit=result.returncode, command=command,
                            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                            object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest() if not result.returncode else None))
        if not result.returncode and struct.unpack_from('<H', obj.read_bytes())[0] != 0x1f2:
            raise ValueError('Not a Xenon object')
    stable(folder / ('skeleton-build.json' if skeleton_only else 'sample-build.json' if sample_only else 'scene-build.json' if scene_only else 'build.json'), json.dumps(records, indent=2) + '\n')
    for row in records: print(str(row['exit']) + ' ' + row['source'])
    if any(r['exit'] for r in records): raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--build-scene', action='store_true')
    parser.add_argument('--build-sample', action='store_true')
    parser.add_argument('--build-skeleton', action='store_true')
    args = parser.parse_args()
    if args.build or args.build_scene or args.build_sample or args.build_skeleton: build(args.build_scene,args.build_sample,args.build_skeleton)
    else: prepare()
