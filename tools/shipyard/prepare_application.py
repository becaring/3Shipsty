"""Project the real OTRGlobals declaration and coupled constructor defaults.

The complete application source is retained but not yet claimed compiled. Its
build integration stays blocked until the real service/header closure is ready.
"""
import argparse
import hashlib
import json
import re
import subprocess
import struct
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_enhancements import includes as enhancement_includes
from prepare_resource_manager import syntax
from prepare_binary import strong_enum
from cpp_ast import PARSER, walk

OWN=ROOT/'platform/shipyard/application';OUT=ROOT/'scratch/application-xdk'

def function(text, name):
    matches=[n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator') is not None and n.child_by_field_name('declarator').text.decode().split('(')[0].strip()==name]
    if len(matches)!=1:raise ValueError('Application function inventory changed: '+name)
    return matches[0]

def platform_source(source):
    # Retain the desktop extraction body behind the explicit PC boundary.
    node=function(source,'OTRGlobals::RunExtract');body=node.child_by_field_name('body')
    raw=source.encode();start=body.start_byte+1;end=body.end_byte-1
    source=(raw[:start]+('\n#ifdef _XBOX\n'+(OWN/'runtime_preflight.inc').read_text()+'\n#else\n').encode()+raw[start:end]+b'\n#endif\n'+raw[end:]).decode()
    source=once(source,'#if not defined(__SWITCH__) && not defined(__WIIU__)\n#include "Extractor/Extract.h"','#if !defined(_XBOX) && !defined(__SWITCH__) && !defined(__WIIU__)\n#include "Extractor/Extract.h"')
    for include in ('atomic','optional'):
        source=once(source,'#include <'+include+'>','#ifndef _XBOX\n#include <'+include+'>\n#endif')
    source=once(source,'#include <filesystem>','#include "filesystem/filesystem.h"')
    source=source.replace('std::filesystem::','xbox_compat::filesystem::')
    # IsSubpath and the temporary permission test belong solely to PC extraction.
    for name in ('IsSubpath','PathTestCleanup'):
        node=function(source,name);raw=source.encode();source=(raw[:node.start_byte]+b'#ifndef _XBOX\n'+node.text+b'\n#endif'+raw[node.end_byte:]).decode()
    source=source.replace('std::unique_lock<std::mutex>','Shipyard::Async::unique_lock<Shipyard::Async::mutex>')
    source=once(source,'audio.thread = std::thread(OTRAudio_Thread);','audio.thread = Shipyard::Async::make_thread(OTRAudio_Thread);')
    source=once(source,'    while (audio.running) {','    while (true) { // running is checked under audio.mutex below. No unlocked cross-thread read.')
    source=once(source,'return { INT16_MAX, INT16_MAX, INT16_MAX };','OTRVersion absent = { INT16_MAX, INT16_MAX, INT16_MAX }; return absent;')
    # Stop libultra timer callbacks before Context/game queues can be torn down.
    source=once(source,'    OTRAudio_Exit();','    OTRAudio_Exit();\n    Shipyard::Libultra::StopTimers();')
    return '#include "application/archive_preflight.h"\n#include "context/platform.h"\n#include "libultra/platform.h"\n'+source
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={}
    for name,expected in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Application source drift '+name)
        texts[name]=text
    header=texts['soh/soh/OTRGlobals.h'];source=texts['soh/soh/OTRGlobals.cpp']
    defaults=re.findall(r'    ImFont\* (\w+) = nullptr;',header)
    if len(defaults)!=8:raise ValueError('OTRGlobals font default inventory changed')
    for member in defaults:header=once(header,'ImFont* '+member+' = nullptr;','ImFont* '+member+';')
    header=once(header,'#include "Enhancements/savestates.h"','class SaveStateMgr;')
    header=once(header,'#include "Enhancements/randomizer/randomizer.h"','class Randomizer;\nnamespace Rando {class Context;}\nstruct ImFont;')
    header=once(header,'#include "Enhancements/randomizer/settings.h"','// Only the forward-declared randomizer owner is used by this class declaration.')
    source=once(source,'#include "OTRGlobals.h"','#include "OTRGlobals.h"\n#include "Enhancements/savestates.h"\n#include "Enhancements/randomizer/settings.h"')
    source=once(source,'OTRGlobals::OTRGlobals() {','OTRGlobals::OTRGlobals() : '+', '.join(member+'(nullptr)' for member in defaults)+' {')
    audio=syntax(texts['soh/soh/OTRAudio.h']).replace('#include <condition_variable>','#include "async/native.h"')
    audio=audio.replace('std::thread thread','Shipyard::Async::joining_thread thread').replace('std::condition_variable','Shipyard::Async::condition_variable')
    stable(OUT/'generated/soh/soh/OTRAudio.h',audio)
    states=syntax(texts['soh/soh/Enhancements/savestates.h'])
    states=re.sub(r'enum class (SaveStateReturn|RequestType) \{(.*?)\};',lambda m:strong_enum(m[1],m[2]),states,flags=re.S)
    states=once(states,'    SaveStateMgr& operator=(const SaveStateMgr& rhs) = delete;\n    SaveStateMgr(const SaveStateMgr& rhs) = delete;','  private:\n    SaveStateMgr& operator=(const SaveStateMgr& rhs);\n    SaveStateMgr(const SaveStateMgr& rhs);\n  public:')
    states='#include "binary/compat.h"\n'+states
    stable(OUT/'generated/soh/soh/Enhancements/savestates.h',states)
    stable(OUT/'generated/soh/soh/OTRGlobals.h',header)
    source=platform_source(source)
    stable(OUT/'generated/soh/soh/OTRGlobals.cpp',source)
    generated={p.relative_to(OUT/'generated').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'generated').rglob('*') if p.is_file()}
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],constructor_default_members=defaults,generated_sha256=generated,
        helpers={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OWN.iterdir() if p.suffix in ('.h','.inc')},
        full_application_compiled=False,boundary_probes_are_production_units=False),indent=2)+'\n')
def includes():return [OUT/'generated/soh']+enhancement_includes()
def probe():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    source=folder/'declaration.cpp';stable(source,'#include "soh/OTRGlobals.h"\ntypedef char owner_layout[(sizeof(OTRGlobals)==80)?1:-1];\n')
    recipe=json.loads((ROOT/'scratch/game-interactor-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    recipe.insert(1,'/I'+str(OUT/'generated/soh'));obj=folder/'declaration.obj';command=recipe+[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'declaration.log',result.stdout+result.stderr)
    stable(folder/'declaration.json',json.dumps(dict(command=command,exit=result.returncode,production_application_compiled=False),indent=2)+'\n')
    if result.returncode:print(result.stdout);raise SystemExit(1)
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    print('Complete OTRGlobals class declaration: 80-byte Xenon layout; coupled full constructor projection retained, not yet compiled')

def boundary_probe():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    source=(OUT/'generated/soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
    version=re.search(r'typedef struct \{\s*uint16_t major;\s*uint16_t minor;\s*uint16_t patch;\s*\} OTRVersion;',source)
    if version is None:raise ValueError('Version record inventory changed')
    names=['CheckAndCreateModFolder','ReadPortVersionFromOTR','DetectOTRVersion','VerifyArchiveVersion','OTRGlobals::RunExtract','OTRAudio_Thread','OTRAudio_Init','OTRAudio_Exit']
    prelude='''#include "soh/OTRGlobals.h"
#include "soh/OTRAudio.h"
#include "soh/Enhancements/savestates.h"
#include <ship/resource/archive/O2rArchive.h>
#include <ship/utils/binarytools/MemoryStream.h>
#include <ship/utils/binarytools/BinaryReader.h>
#include "filesystem/filesystem.h"
#include "application/archive_preflight.h"
#include "context/platform.h"
#include <fstream>
#include <climits>
#include "z64.h"
#include "macros.h"
#include "variables.h"
#include "functions.h"
#include "soh/ResourceManagerHelpers.h"
extern "C" void AudioPlayer_Play(const uint8_t*, uint32_t);
extern "C" void AudioMgr_CreateNextAudioBuffer(s16*, u32);
extern "C" int AudioPlayer_Buffered(void);
extern "C" int AudioPlayer_GetDesiredBuffered(void);
extern unsigned short gBuildVersionMajor;
extern bool sohArchiveVersionMatch;
'''
    prelude+=version[0]+'\nstatic OTRVersion DetectOTRVersion(std::string,bool);\nstatic bool VerifyArchiveVersion(OTRVersion);\n'
    bodies='\n'.join(function(source,n).text.decode() for n in names)
    path=folder/'startup_boundaries.cpp';stable(path,prelude+bodies+'\n')
    flags=json.loads((ROOT/'scratch/soh-ui-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    flags[1:1]=['/I'+str(OUT/'generated/soh'),'/I'+str(ROOT/'scratch/libzip-xdk/generated')]
    obj=path.with_suffix('.obj');command=flags+[str(path),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(path.with_suffix('.log'),result.stdout+result.stderr)
    stable(folder/'boundary-probe.json',json.dumps(dict(command=command,exit=result.returncode,methods=names,production_unit=False,
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest() if not result.returncode else None),indent=2)+'\n')
    print('Real startup archive boundaries and audio/save-state declarations:',result.returncode)
    if result.returncode:print('\n'.join(s for s in result.stdout.splitlines() if 'error ' in s)[:5000]);raise SystemExit(1)
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2

def build():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/soh-ui-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    roots=[OUT/'generated/soh']+[Path(f[2:])/'soh' for f in flags if f.startswith('/I') and f.endswith('generated\\soh')]+[ROOT/'soh/soh']
    flags[1:1]=['/I'+str(p) for p in roots]
    source=OUT/'generated/soh/soh/OTRGlobals.cpp';obj=folder/'OTRGlobals.obj';command=flags+[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
    stable(folder/'build.json',json.dumps([dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=result.returncode)],indent=2)+'\n')
    print('Complete OTRGlobals.cpp:',result.returncode)
    if result.returncode:print('\n'.join(s for s in result.stdout.splitlines() if 'error ' in s)[:6000]);raise SystemExit(1)
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',action='store_true');p.add_argument('--boundary-probe',action='store_true');p.add_argument('--build',action='store_true');args=p.parse_args()
    if args.build:build()
    elif args.boundary_probe:boundary_probe()
    elif args.probe:probe()
    else:prepare()
