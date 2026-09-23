"""Project the complete current archive/loader/cache classes, never substitutes."""
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
from prepare_filesystem import project_boundary, transform as directory_transform
from cpp_ast import PARSER, walk

OUT = ROOT / 'scratch/resource-manager-xdk'
OWN = ROOT / 'platform/shipyard/resources'
UNITS = ['resource/ResourceLoader.cpp', 'resource/ResourceManager.cpp',
         *['resource/archive/' + n + '.cpp' for n in ('Archive', 'ArchiveManager', 'O2rArchive', 'FolderArchive', 'OtrArchive')],
         'utils/StringHelper.cpp', 'utils/Utils.cpp', 'utils/glob.c', 'utils/StrHash64.cpp']


def once(text, old, new):
    if text.count(old) != 1: raise ValueError('Expected exact single source pattern: ' + old[:90])
    return text.replace(old, new)


def syntax(text):
    # These are contextual specifiers, also legal identifiers. A textual
    # replacement corrupts e.g. EntranceHints' overrideIndex and data.override.
    raw = text.encode('utf-8')
    specifiers = [n for n in walk(PARSER.parse(raw).root_node)
                  if n.type == 'virtual_specifier' and n.text in (b'override', b'final')]
    for node in sorted(specifiers, key=lambda n: n.start_byte, reverse=True):
        start = node.start_byte - (raw[node.start_byte-1:node.start_byte] == b' ')
        raw = raw[:start] + raw[node.end_byte:]
    text = raw.decode('utf-8')
    text = text.replace('std::variant<', 'Shipyard::Resources::variant<').replace('std::get<', 'Shipyard::Resources::get<')
    text = text.replace('std::holds_alternative<', 'Shipyard::Resources::holds_alternative<').replace('std::bad_variant_access', 'Shipyard::Resources::bad_variant_access')
    text = text.replace('#include <variant>', '#include "resources/variant.h"').replace('#include <mutex>', '#include "async/native.h"')
    text = text.replace('#include <thread>', '#include "thread-pool/native_support.h"')
    for name in ('mutex', 'lock_guard', 'shared_future', 'promise'):
        text = text.replace('std::' + name, 'Shipyard::Async::' + name)
    text = text.replace('std::thread::hardware_concurrency()', 'Shipyard::Async::hardware_concurrency()')
    return text


def transform(name, original):
    if name.endswith(('/glob.c','/glob.h')): return original
    text = syntax(original)
    if '<filesystem>' in original or '__has_include' in original:
        text = syntax(project_boundary('libultraship/' + name, original))
    if name.endswith('/Context.h'):
        text = once(text, '#include "ship/audio/Audio.h"', '#include "ship/audio/AudioSettings.h"')
        text = once(text, 'class Console;', 'class Audio;\nclass Console;')
        text = text.replace('archivePaths = {}', 'archivePaths = std::vector<std::string>()')
        text = text.replace('validHashes = {}', 'validHashes = std::unordered_set<uint32_t>()')
        text = text.replace('audioSettings = {}', 'audioSettings = AudioSettings()').replace('Context() = default;', 'Context() {}')
    if name.endswith('/ResourceManager.h'):
        text=once(text, '    ~ResourceManager();',
                  '    ~ResourceManager();\n'
                  '    // Stop external producers and retain Context strongly while draining.\n'
                  '    // Application thread only; never call from this pool.\n'
                  '    void WaitForPendingTasks();')
        for old,new in [('Owner = 0', 'Owner'), ('Parent = nullptr','Parent'), ('Path = ""','Path'),
                        ('mAltAssetsEnabled = false','mAltAssetsEnabled'), ('mDefaultCacheOwner = 0','mDefaultCacheOwner'),
                        ('mDefaultCacheArchive = nullptr','mDefaultCacheArchive')]: text=text.replace(old,new)
        text=once(text, 'typedef enum class ResourceLoadError { None, NotCached, NotFound } ResourceLoadError;',
                  'struct ResourceLoadError : Shipyard::Binary::ScopedEnum<ResourceLoadError> {\n'
                  'enum Value { None, NotCached, NotFound };\nResourceLoadError() {}\n'
                  'ResourceLoadError(Value value) : Shipyard::Binary::ScopedEnum<ResourceLoadError>(value) {}\n};')
    if name.endswith('/ResourceManager.cpp'):
        text=once(text, 'ResourceManager::~ResourceManager() {',
                  'void ResourceManager::WaitForPendingTasks() {\n'
                  '    if (mThreadPool != nullptr) {\n'
                  '        // BS wait treats a paused queue as complete. Accepted jobs\n'
                  '        // must run and release their captures while Context is alive.\n'
                  '        mThreadPool->unpause();\n'
                  '        mThreadPool->wait();\n'
                  '    }\n'
                  '}\n\n'
                  'ResourceManager::~ResourceManager() {\n'
                  '    WaitForPendingTasks();\n'
                  '    // mMutex follows the pool in declaration order. Join the actual\n'
                  '    // pool before automatic member destruction reaches that mutex.\n'
                  '    mThreadPool.reset();')
        text=once(text, '#include "ship/config/ConsoleVariable.h"', '// No ConsoleVariable symbols are used by this TU.')
        text=once(text, 'ResourceManager::ResourceManager() {', 'ResourceManager::ResourceManager() : mAltAssetsEnabled(false), mDefaultCacheOwner(0), mDefaultCacheArchive(nullptr) {')
        text=once(text,
                  '    auto resource = LoadResourceAsync(identifier, loadExact, BS::pr::highest, initData).get();',
                  '    // Synchronous cached callers need no promise, future or worker handoff.\n'
                  '    // GetCachedResource applies the same alt-asset and dirty checks as\n'
                  '    // the first step of LoadResourceAsync; misses retain its path.\n'
                  '    auto cachedResource = GetCachedResource(identifier, loadExact);\n'
                  '    if (cachedResource != nullptr) {\n'
                  '        return cachedResource;\n'
                  '    }\n'
                  '    auto resource = LoadResourceAsync(identifier, loadExact, BS::pr::highest, initData).get();')
        text=text.replace('std::hash<std::string>{}', 'std::hash<std::string>()').replace('std::hash<std::uintptr_t>{}', 'std::hash<uintptr_t>()')
        text=re.sub(r'\{ (\w+), (identifier\.Owner|filter\.Owner|mDefaultCacheOwner), (identifier\.Parent|filter\.Parent|mDefaultCacheArchive) \}',r'ResourceIdentifier(\1, \2, \3)',text)
        text=text.replace('{ { searchMask }, {}, mDefaultCacheOwner, mDefaultCacheArchive }',
                          'ResourceFilter(std::list<std::string>(1, searchMask), std::list<std::string>(), mDefaultCacheOwner, mDefaultCacheArchive)')
        text=text.replace('identifier.Path.starts_with(IResource::gAltAssetPrefix)', 'Shipyard::Resources::starts_with(identifier.Path, IResource::gAltAssetPrefix)')
    if name.endswith('/ResourceLoader.cpp'):
        text=text.replace('ResourceFactoryKey key{ .resourceFormat = format, .resourceType = type, .resourceVersion = version };',
                          'ResourceFactoryKey key = { format, type, version };')
    if name.endswith('/ResourceLoader.h'):
        text=text.replace('#include "ResourceType.h"', '#include "ship/resource/ResourceType.h"')
    if name.endswith(('/Archive.cpp', '/O2rArchive.cpp', '/OtrArchive.cpp')):
        text=text.replace('#include "ship/window/Window.h"', '#include "ship/resource/ResourceManager.h"')
    if name.endswith('/O2rArchive.cpp'):
        # libzip may return a positive partial chunk. Keep the pinned upstream
        # source intact and complete the declared entry in the XDK projection.
        text=once(text,
                  '    // Filesize 0, no logging needed\n'
                  '    if (zipEntryStat.size == 0) {\n'
                  '        SPDLOG_TRACE("Failed to load file {}; filesize 0", filePath, GetPath());\n'
                  '        return nullptr;\n'
                  '    }',
                  '    // Filesize 0, no logging needed\n'
                  '    if (zipEntryStat.size == 0) {\n'
                  '        SPDLOG_TRACE("Failed to load file {}; filesize 0", filePath, GetPath());\n'
                  '        return nullptr;\n'
                  '    }\n'
                  '    if (zipEntryStat.size > std::vector<char>().max_size()) {\n'
                  '        SPDLOG_TRACE("Failed to load file {}; filesize too large", filePath, GetPath());\n'
                  '        return nullptr;\n'
                  '    }')
        text=once(text,
                  '    fileToLoad->Buffer = std::make_shared<std::vector<char>>(zipEntryStat.size);\n\n'
                  '    if (zip_fread(zipEntryFile, fileToLoad->Buffer->data(), zipEntryStat.size) < 0) {\n'
                  '        SPDLOG_TRACE("Error reading file {} in zip archive  {}.", filePath, GetPath());\n'
                  '    }',
                  '    fileToLoad->Buffer = std::make_shared<std::vector<char>>(static_cast<size_t>(zipEntryStat.size));\n\n'
                  '    zip_uint64_t bytesRead = 0;\n'
                  '    while (bytesRead < zipEntryStat.size) {\n'
                  '        const zip_uint64_t remaining = zipEntryStat.size - bytesRead;\n'
                  '        const auto chunk = zip_fread(zipEntryFile, fileToLoad->Buffer->data() + static_cast<size_t>(bytesRead),\n'
                  '                                     remaining);\n'
                  '        if (chunk <= 0 || static_cast<zip_uint64_t>(chunk) > remaining) {\n'
                  '            SPDLOG_TRACE("Error reading file {} in zip archive  {}.", filePath, GetPath());\n'
                  '            zip_fclose(zipEntryFile);\n'
                  '            return nullptr;\n'
                  '        }\n'
                  '        bytesRead += static_cast<zip_uint64_t>(chunk);\n'
                  '    }')
    if name.endswith('/ArchiveManager.cpp'):
        text=text.replace('dynamic_pointer_cast<Archive>', 'std::dynamic_pointer_cast<Archive>')
        text=text.replace('mValidGameVersions.contains(archive->GetGameVersion())', 'Shipyard::Resources::contains(mValidGameVersions, archive->GetGameVersion())')
        text=text.replace('Init(archivePaths, {});', 'Init(archivePaths, std::unordered_set<uint32_t>());')
        text=text.replace('std::vector<std::string> fileList = {};','std::vector<std::string> fileList;')
        text=text.replace('ListFiles(includes, {});', 'ListFiles(includes, std::list<std::string>());')
        text=text.replace('std::list<std::string> includes = {};','std::list<std::string> includes;')
        text=once(text, 'for (const auto& p : xbox_compat::filesystem::directory_iterator(archivePath)) {',
                  'for (xbox_compat::filesystem::directory_iterator cursor(archivePath), finish; cursor != finish; ++cursor) {\nconst xbox_compat::filesystem::directory_entry& p=*cursor;')
        text=once(text, 'for (const auto& [hash, path] : mHashes) {',
                  'for (const auto& entry : mHashes) {\nconst uint64_t& hash=entry.first; const std::string& path=entry.second;')
        text=once(text, 'for (auto& [hash, filename] : *fileList.get()) {',
                  'for (auto& entry : *fileList.get()) {\nconst uint64_t& hash=entry.first; std::string& filename=entry.second;')
    if name.endswith('/Directory.h'): text=directory_transform(original).replace('#include "filesystem.h"','#include "filesystem/filesystem.h"')
    if name.endswith('/Utils.cpp'):
        text=once(text, 'if constexpr (sizeof(size_t) >= 8)', 'if (sizeof(size_t) >= 8)')
    if name.endswith('/FileHelper.h'):
        # XDK streams accept native narrow paths, not filesystem::path objects.
        text=text.replace('file(filePath,', 'file(filePath.string(),')
        # These two overloads already accept std::string.
        text=text.replace('std::ofstream file(filePath.string(), std::ios::binary);', 'std::ofstream file(filePath, std::ios::binary);')
        text=once(text, 'static void WriteAllBytes(const fs::path& filePath, const std::vector<uint8_t>& data) {\n        std::ofstream file(filePath,',
                  'static void WriteAllBytes(const fs::path& filePath, const std::vector<uint8_t>& data) {\n        std::ofstream file(filePath.string(),')
    if name.endswith(('/StringHelper.h','/StringHelper.cpp')):
        text=text.replace('#include <string_view>', '#include <nonstd/string_view.hpp>').replace('std::string_view','nonstd::string_view')
        text=text.replace('std::strtoull(', '_strtoui64(')
        text= text.replace('std::equal(a.begin(), a.end(), b.begin(), b.end(),',
                           '(a.size() == b.size()) && std::equal(a.begin(), a.end(), b.begin(),')
    if name.endswith('/OtrArchive.cpp'):
        text=text.replace('std::string_view','nonstd::string_view').replace('std::string(line);','std::string(line.data(), line.size());')
    # Only container lookups (not JSON) in these locked current TUs.
    text=re.sub(r'\b(mResourceTypes|mFactories|mResourceCache|mValidGameVersions|mHashes|mFileToArchive|mDirectories)\.contains\(([^()]*)\)',
                r'Shipyard::Resources::contains(\1, \2)',text)
    lower_ranges=runpy.run_path(str(ROOT / 'platform/shipyard/imgui/projection.py'))['lower_ranges']
    text=lower_ranges(text.encode(), 'Shipyard::Resources::begin', 'Shipyard::Resources::end').decode()
    return '#include "resources/runtime_support.h"\n'+text


def prepare_lifecycle():
    """Update only the two canonical ResourceManager lifecycle projections."""
    lock=json.loads((OWN/'runtime-sources.lock.json').read_text())
    for name,expected in lock['helpers'].items():
        if hashlib.sha256((ROOT/name).read_text(encoding='utf-8-sig').encode()).hexdigest()!=expected:
            raise ValueError('Resource projection helper drift: '+name)
    manifest_path=OUT/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    for name in ['include/ship/resource/ResourceManager.h','src/ship/resource/ResourceManager.cpp']:
        original=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(original.encode()).hexdigest()!=lock['sources'][name]:
            raise ValueError('Resource source drift: '+name)
        projected=transform(name,original)
        stable(OUT/'generated'/name,projected)
        manifest[name]=hashlib.sha256(projected.encode()).hexdigest()
    stable(manifest_path,json.dumps(manifest,indent=2)+'\n')


def prepare():
    lock=json.loads((OWN/'runtime-sources.lock.json').read_text())
    for name,expected in lock['helpers'].items():
        if hashlib.sha256((ROOT/name).read_text(encoding='utf-8-sig').encode()).hexdigest()!=expected:
            raise ValueError('Resource projection helper drift: '+name)
    pending={}
    for name,expected in lock['sources'].items():
        original=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(original.encode()).hexdigest()!=expected: raise ValueError('Source drift: '+name)
        pending[name]=transform(name,original)
    # Extract the actual value type, avoiding Audio's unnecessary transitive
    # backend headers in Context. AudioPlayer will consume this same definition.
    original=(ROOT/'libultraship/include/ship/audio/AudioPlayer.h').read_text()
    if hashlib.sha256(original.encode()).hexdigest()!=lock['audio_player_sha256']: raise ValueError('AudioSettings source drift')
    block=re.search(r'struct AudioSettings \{.*?\n\};', original, re.S)[0]
    members=re.findall(r'^    (\w+) (\w+) = ([^;]+);',block,re.M)
    if len(members)!=4: raise ValueError('AudioSettings members changed')
    block=re.sub(r' = [^;]+;', ';',block)
    block=block.replace('struct AudioSettings {','struct AudioSettings {\n    AudioSettings() : '+', '.join(n+'('+v+')' for t,n,v in members)+' {}')
    pending['include/ship/audio/AudioSettings.h']='#pragma once\n#include <stdint.h>\n#include "ship/audio/AudioChannelsSetting.h"\nnamespace Ship {\n'+block+'\n}\n'
    channels=(ROOT/'libultraship/include/ship/audio/AudioChannelsSetting.h').read_text()
    if hashlib.sha256(channels.encode()).hexdigest()!=lock['audio_channels_sha256']:raise ValueError('Audio channels declaration drift')
    pending['include/ship/audio/AudioChannelsSetting.h']=channels
    # Exact official string_view backport; no injection into namespace std.
    view=verified('string-view-lite')
    pending['include/nonstd/string_view.hpp']=(view/'include/nonstd/string_view.hpp').read_text()
    for name,text in pending.items(): stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({name:hashlib.sha256(text.encode()).hexdigest() for name,text in pending.items()},indent=2)+'\n')


def build():
    prepare()
    env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_resources.py'))
    inc=[OUT/'generated/include',ROOT/'platform/shipyard/game/include']+env['includes'](True)+[ROOT/'scratch/async-xdk/generated',ROOT/'scratch/libzip-xdk/generated',
         ROOT/'scratch/deps/tinyxml2', ROOT/'scratch/stormlib-xdk/generated/src', ROOT/'libultraship/include']
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    folder=OUT/'xdk'; folder.mkdir(parents=True,exist_ok=True)
    flags=['/nologo','/c','/EHsc', '/GR','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DINCLUDE_MPQ_SUPPORT','/DSPDLOG_ACTIVE_LEVEL=0',
           '/Dnssv_CONFIG_SELECT_STRING_VIEW=1','/I'+str(sdk/'include/xbox')]+['/I'+str(p) for p in inc]
    records=[]
    for name in UNITS:
        source=OUT/'generated/src/ship'/name
        obj=folder/(name.replace('/','__').rsplit('.',1)[0]+'.obj')
        if source.suffix=='.c':
            # Keep real C semantics (glob uses a local named `class`). Reuse
            # the already-verified semantic C projection after preprocessing.
            preprocessed=obj.with_suffix('.i')
            precommand=[str(sdk/'bin/win32/cl.exe')]+[f for f in flags if f!='/c']+['/TC','/P','/Fi'+str(preprocessed),str(source)]
            result=subprocess.run(precommand,cwd=ROOT,capture_output=True,text=True)
            stable(obj.with_suffix('.preprocess.log'),result.stdout+result.stderr)
            if result.returncode: raise RuntimeError('C preprocessing failed: '+name)
            from prepare_game import lower_c
            projected,statistics=lower_c(preprocessed.read_bytes())
            source=obj.with_suffix('.c'); source.write_bytes(projected)
        command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        records.append(dict(source=name,exit=result.returncode,command=command))
        if not result.returncode and struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2: raise ValueError('Not a Xenon object')
    stable(folder/'report.json',json.dumps(records,indent=2)+'\n')
    for record in records: print(str(record['exit'])+' '+record['source'])
    if any(r['exit'] for r in records): raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');parser.add_argument('--lifecycle-only',action='store_true');args=parser.parse_args()
    if args.build and args.lifecycle_only:parser.error('Choose --build or --lifecycle-only')
    if args.lifecycle_only:prepare_lifecycle()
    elif args.build:build()
    else:prepare()
