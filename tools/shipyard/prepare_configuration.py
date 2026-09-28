"""Current Config with narrow declarations and native backend registration."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_filesystem import project_boundary
from platform_base import resolve as resolve_platform_base

OUT=ROOT/'scratch/configuration-xdk'
OWN=ROOT/'platform/shipyard/configuration'


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Config source drift: '+old[:80])
    return text.replace(old,new)


def transform(name,text):
    if name.endswith('/Config.h'):
        text=once(text,'#include "ship/window/Window.h"','#include "ship/window/WindowBackend.h"')
        text=once(text,'namespace Ship {','namespace Ship {\nclass Config;')
    if name.endswith('/Window.h'):
        text=text.replace('#include <filesystem>','')
        text=once(text,'#include "ship/window/gui/Gui.h"','#include "ship/window/WindowBackend.h"')
        text=once(text,'#include "ship/window/MouseStateManager.h"','')
        text=once(text,'enum class WindowBackend { FAST3D_DXGI_DX11, FAST3D_SDL_OPENGL, FAST3D_SDL_METAL, WINDOW_BACKEND_COUNT };',
                  'class Gui;\nclass GuiWindow;\nclass MouseStateManager;')
        text=once(text,'int32_t mLastScancode = -1;','int32_t mLastScancode; // Initialized by the projected Window constructors.')
    if name.endswith('/Config.h'):
        helper=runpy.run_path(str(resolve_platform_base(ROOT)/'python/xbox360_platform/config_leaf_lookup.py'))
        text=helper['project_header'](text)
    if name.endswith('/Config.cpp'):
        text=project_boundary('libultraship/'+name,text)
        text=once(text,'#include <any>','#include <iterator>\n#include "ship/window/Window.h"\n#include "resources/runtime_support.h"\n#include "context/platform.h"\n#include "storage/atomic_file.h"')
        text=once(text,'mIsNewInstance(false) {\n    Reload();',
                  'mIsNewInstance(false) {\n    mPath = fs::path(mPath).make_preferred().string();\n    Reload();')
        text=once(text,'''    std::ofstream file(mPath);
    mNestedJson = mFlattenedJson.unflatten();
    file << mNestedJson.dump(4);''',
                  '''    if (mPath == "None") return;
    mNestedJson = mFlattenedJson.unflatten();
    Shipyard::Storage::WriteAtomicFile(fs::path(mPath), mNestedJson.dump(4));''')
        text=once(text,'                } else if (gjson2->contains(dot)) {',
                  '''                } else {
                    if (!gjson2->contains(dot)) (*gjson2)[dot] = nlohmann::json::object();''')
        # The local stream is never observed again and is destroyed immediately;
        # only its complete JSON result or caught parse failure is observable.
        text=once(text,'nlohmann::json::parse(ifs)',
                  'nlohmann::json::parse(std::string((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>()))')
        text=once(text,'if (nlohmann::json tmp = Nested(key); tmp.is_array()) {',
                  'nlohmann::json tmp = Nested(key);\n    if (tmp.is_array()) {')
        text=once(text,'auto [_, emplaced] = mVersionUpdaters.emplace(versionUpdater->GetVersion(), versionUpdater);\n    return emplaced;',
                  'return mVersionUpdaters.insert(std::make_pair(versionUpdater->GetVersion(), versionUpdater)).second;')
        text=once(text,'for (auto [_, versionUpdater] : mVersionUpdaters) {',
                  'for (auto entry : mVersionUpdaters) {\n        auto versionUpdater=entry.second;')
        text=once(text,'            versionUpdater->Update(this);',
                  '''#ifdef _XBOX
            char stage[40];
            _snprintf_s(stage, sizeof(stage), _TRUNCATE, "config-v%u-begin", versionUpdater->GetVersion());
            Shipyard::Platform::RecordBootStage(stage, false);
#endif
            versionUpdater->Update(this);
#ifdef _XBOX
            _snprintf_s(stage, sizeof(stage), _TRUNCATE, "config-v%u-done", versionUpdater->GetVersion());
            Shipyard::Platform::RecordBootStage(stage, false);
#endif''')
        text=once(text,'    }\n    Save();\n}\n\nConfigVersionUpdater::ConfigVersionUpdater',
                  '''    }
#ifdef _XBOX
    Shipyard::Platform::RecordBootStage("config-save-begin", false);
#endif
    Save();
#ifdef _XBOX
    Shipyard::Platform::RecordBootStage("config-save-done", false);
#endif
}

ConfigVersionUpdater::ConfigVersionUpdater''')
        # Native audio backend selection replaces unsupported desktop choices,
        # while preserving the explicit upstream null/error fallback.
        begin=text.index('AudioBackend Config::GetCurrentAudioBackend() {')
        end=text.index('\nAudioChannelsSetting Config::GetCurrentAudioChannelsSetting()',begin)
        block=text[begin:end]
        split=block.index('    if (backendName == "wasapi")')
        block=block[:split]+'#ifdef _XBOX\n    if (backendName == "null") return AudioBackend::NUL;\n    return AudioBackend::XAUDIO2;\n#else\n'+block[split:]
        position=block.rfind('\n}')
        block=block[:position]+'\n#endif'+block[position:]
        text=text[:begin]+block+text[end:]
        text=once(text,'switch (backend) {\n        case AudioBackend::WASAPI:',
                  'switch (backend.GetValue()) {\n        case AudioBackend::XAUDIO2:\n            SetString("Window.AudioBackend", "xaudio2");\n            break;\n        case AudioBackend::WASAPI:')
        text=once(text,'switch (backend) {\n        case WindowBackend::FAST3D_DXGI_DX11:',
                  'switch (backend.GetValue()) {\n        case WindowBackend::FAST3D_XENOS:\n            SetString("Window.Backend.Name", "Xenos");\n            break;\n        case WindowBackend::FAST3D_DXGI_DX11:')
        text=text.replace('static_cast<int>(backend)','backend.GetValue()')
        text=once(text,'#ifdef ENABLE_DX11\n    return WindowBackend::FAST3D_DXGI_DX11;',
                  '#ifdef _XBOX\n    return WindowBackend::FAST3D_XENOS;\n#endif\n#ifdef ENABLE_DX11\n    return WindowBackend::FAST3D_DXGI_DX11;')
        lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
        text=lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
        helper=runpy.run_path(str(resolve_platform_base(ROOT)/'python/xbox360_platform/config_leaf_lookup.py'))
        text=helper['project_source'](text)
    return text


def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());pending={}
    for name,expected in lock['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Configuration input drift: '+name)
        pending[name]=transform(name,text)
    pending['include/ship/window/WindowBackend.h']='''#pragma once
#include "binary/compat.h"
namespace Ship {
struct WindowBackend : Shipyard::Binary::ScopedEnum<WindowBackend> {
    enum Value { FAST3D_DXGI_DX11, FAST3D_SDL_OPENGL, FAST3D_SDL_METAL, FAST3D_XENOS, WINDOW_BACKEND_COUNT };
    WindowBackend() {}
    WindowBackend(Value value) : Shipyard::Binary::ScopedEnum<WindowBackend>(value) {}
    explicit WindowBackend(int value) : Shipyard::Binary::ScopedEnum<WindowBackend>(value) {}
};
}
'''
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    from prepare_game import release_cvars
    cvar_header=OUT/'generated/include/compile_definitions.h'
    stable(cvar_header,'#pragma once\n'+''.join('#define '+name+' "'+value+'"\n' for name,value in release_cvars().items()))
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    cvar_header=OUT/'generated/include/compile_definitions.h'
    env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_resources.py'))
    includes=[OUT/'generated/include',ROOT/'scratch/audio-xdk/generated/include',ROOT/'scratch/resource-manager-xdk/generated/include']+env['includes'](True)+[ROOT/'libultraship/include']
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
             '/FI'+str(cvar_header),'/I'+str(sdk/'include/xbox')]+['/I'+str(p) for p in includes]
    source=OUT/'generated/src/ship/config/Config.cpp';obj=folder/'Config.obj';command+=[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'Config.log',result.stdout+result.stderr)
    stable(folder/'build.json',json.dumps(dict(command=command,exit=result.returncode),indent=2)+'\n')
    if result.returncode:raise SystemExit(result.returncode)
    if struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not a Xenon object')
    print('Actual current Config compiles for Xenon')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
