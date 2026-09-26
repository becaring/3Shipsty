"""Original/current Config behavioral differential with isolated declarations.

GetWindowBackend is excluded only from this host unit audit because it requires
a live Context/window. The complete production Config TU is compiled separately.
"""
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
OUT=ROOT/'scratch/configuration-xdk'
from cpp_ast import PARSER,walk
from prepare_game import release_cvars


def host(projected):
    env=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
    compiler,environment=env['ENV'].host_environment()
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(parents=True,exist_ok=True)
    source=OUT/'generated' if projected else ROOT/'libultraship'
    body=(source/'src/ship/config/Config.cpp').read_bytes()
    definitions=[n for n in walk(PARSER.parse(body).root_node) if n.type=='function_definition'
                 and n.child_by_field_name('declarator').text.decode().split('(')[0].strip()=='Config::GetWindowBackend']
    if len(definitions)!=1:raise ValueError('Config audit selector drift')
    node=definitions[0];body=body[:node.start_byte]+b'\n'+body[node.end_byte:]
    body=body.replace(b'#include "ship/Context.h"',b'#include <spdlog/spdlog.h>')
    body=body.replace(b'#include "ship/window/Window.h"',b'')
    if projected:
        # Only conditional method code selects Xbox here. Header dependencies
        # were included as real host APIs above; no fake platform class exists.
        body=body.replace(b'namespace Ship {',
                          b'namespace Shipyard { namespace Platform { void RecordBootStage(const char*, bool) {} } }\n#define _XBOX\nnamespace Ship {',1)
    audit=folder/'config-method-audit.cpp';audit.write_bytes(body)
    if projected:
        includes=[OUT/'generated/include',ROOT/'scratch/audio-xdk/generated/include',ROOT/'scratch/resource-manager-xdk/generated/include',
                  PLATFORM_BASE,PLATFORM_BASE/'sources']+env['includes'](True)
        sources=[audit,ROOT/'scratch/resource-manager-xdk/generated/src/ship/utils/StringHelper.cpp',
                 PLATFORM_BASE/'sources/json/json.cpp',PLATFORM_BASE/'sources/filesystem/filesystem.cpp',
                 PLATFORM_BASE/'sources/storage/atomic_file.cpp',
                 PLATFORM_BASE / 'sources/async/native.cpp',PLATFORM_BASE/'sources/clock/chrono.cpp',
                 ROOT/'platform/shipyard/logging/environment.cpp']
    else:
        # Preserve the entire real Config declaration; replace unrelated class
        # includes with exact original enum declarations and a forward name.
        header=(ROOT/'libultraship/include/ship/config/Config.h').read_text()
        audio=re.search(r'enum class AudioBackend \{[^}]+\};',(ROOT/'libultraship/include/ship/audio/Audio.h').read_text())[0]
        window=re.search(r'enum class WindowBackend \{[^}]+\};',(ROOT/'libultraship/include/ship/window/Window.h').read_text())[0]
        header=header.replace('#include "ship/audio/Audio.h"','#include "ship/audio/AudioChannelsSetting.h"\nnamespace Ship { '+audio+' }')
        header=header.replace('#include "ship/window/Window.h"','namespace Ship { '+window+' class Config; }')
        path=folder/'include/ship/config/Config.h';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(header)
        includes=[folder/'include']+env['includes'](False)
        sources=[audit,ROOT/'libultraship/src/ship/utils/StringHelper.cpp']
    definitions=folder/'definitions.h';definitions.write_text('#pragma once\n'+''.join('#define '+n+' "'+v+'"\n' for n,v in release_cvars().items()))
    command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0','/FI'+str(definitions)]
    if projected:command+=['/DSHIPYARD_PROJECTED_CONFIG_TEST','/DSHIPYARD_AUDIO_TEST','/Dnssv_CONFIG_SELECT_STRING_VIEW=1']
    command+=['/I'+str(p) for p in includes]+[str(p) for p in sources]+[str(Path(__file__).with_name('test_config_contract.cpp')),
              '/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'config.exe')]
    result=subprocess.run(command,env=environment,cwd=ROOT,capture_output=True,text=True)
    (folder/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('See '+str(folder/'build.log'))
    result=subprocess.run([str(folder/'config.exe'),str(folder/'settings.json')],cwd=folder,capture_output=True,text=True)
    (folder/'verification.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr,
         scope='Current Config methods excluding live-window backend selection',target_runtime_executed=False),indent=2)+'\n')
    if result.returncode:raise RuntimeError('Config contract failed: '+result.stderr)
    return result.stdout


if __name__=='__main__':
    original=host(False);projected=host(True)
    if original!=projected:raise RuntimeError('Original/projected Config behavior differs')
    print('Current Config nested values, arrays, copies, erasure, version updates, file save/reload and malformed fallback agree; native audio/backend metadata checks pass')
