"""Full current Fast3dWindow and native presentation, without another game loop."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_resource_manager import syntax

OWN=ROOT/'platform/shipyard/presentation'
OUT=ROOT/'scratch/presentation-xdk'


def transform(name,text):
    if name.endswith('/Fast3dWindow.h'):
        text=text.replace(' override','').replace('mInterpreter = nullptr;','mInterpreter;')
        text=once(text,'#include "interpreter.h"','#include "fast/interpreter.h"')
        text=once(text,'#include "FastMouseStateManager.h"','#include "fast/FastMouseStateManager.h"')
        text=once(text,'  private:','  private:\n    void InitializeInterpreter();')
    elif name.endswith('/FastMouseStateManager.h'):
        text=text.replace(' override','')
        text=once(text,'  public:','  public:\n    FastMouseStateManager() : mCursorVisibleSeconds(3) {}')
        text=once(text,'mCursorVisibleSeconds = 3;','mCursorVisibleSeconds;')
    elif name.endswith('/Fast3dWindow.cpp'):
        for backend in ('sdl','dxgi','opengl','metal','direct3d_common','direct3d11'):
            text=once(text,'#include "fast/backends/gfx_'+backend+'.h"','')
        text='#include "window_xenos.h"\n#include "xenos_backend.h"\n'+text
        signature='    : Ship::Window(gui, mouseStateManager) {'
        text=once(text,signature,signature+'\n    InitializeInterpreter();\n}\n\nvoid Fast3dWindow::InitializeInterpreter() {')
        start=text.index('#ifdef _WIN32');end=text.index('\n}',start)
        text=text[:start]+'    AddAvailableWindowBackend(Ship::WindowBackend::FAST3D_XENOS);'+text[end:]
        text=once(text,': Fast3dWindow(gui, std::make_shared<FastMouseStateManager>()) {\n}',
                  ': Ship::Window(gui, std::make_shared<FastMouseStateManager>()) { InitializeInterpreter();\n}')
        text=once(text,': Fast3dWindow(std::make_shared<Ship::Gui>(guiWindows)) {\n}',
                  ': Ship::Window(std::make_shared<Ship::Gui>(guiWindows), std::make_shared<FastMouseStateManager>()) { InitializeInterpreter();\n}')
        text=once(text,': Fast3dWindow(std::vector<std::shared_ptr<Ship::GuiWindow>>()) {\n}',
                  ': Ship::Window(std::make_shared<Ship::Gui>(std::vector<std::shared_ptr<Ship::GuiWindow>>()), std::make_shared<FastMouseStateManager>()) { InitializeInterpreter();\n}')
        # Context destroys a window whose Init throws. Interpreter records its
        # APIs at the start of Init; a constructed but uninitialized one has none.
        text=once(text,'    mInterpreter->Destroy();','    GetGui()->ShutDownImGui(this);\n    if (mInterpreter->mWapi) mInterpreter->Destroy();')
        text=once(text,'    InitWindowManager();','    // Native presentation surface is fixed at 720p; internal game resolution remains upstream-owned.\n    isFullscreen=true; width=1280; height=720; posX=posY=0;\n    InitWindowManager();')
        text=once(text,'switch (GetWindowBackend()) {','switch (GetWindowBackend().GetValue()) {\n        case Ship::WindowBackend::FAST3D_XENOS:\n            mWindowManagerApi=new GfxWindowBackendXenos();\n            mRenderingApi=new GfxRenderingAPIXenos();\n            break;')
        text=once(text,'            SPDLOG_ERROR("Could not load the correct rendering backend");\n            break;',
                  '            throw std::runtime_error("Could not load the configured rendering backend");')
        for typename in ('Ship::Coords','Ship::CoordsF'):
            for method in (('GetMousePos','GetMouseDelta') if typename=='Ship::Coords' else ('GetMouseWheel',)):
                begin=text.index(typename+' Fast3dWindow::'+method+'()');end=text.index('\n}',begin)
                region=text[begin:end]
                text=text[:begin]+once(region,'    return { x, y };','    '+typename+' result={x,y}; return result;')+text[end:]
    return syntax(text)


def prepare():
    pending={}
    lock=json.loads((OWN/'sources.lock.json').read_text())
    for name,sha in lock['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=sha:raise ValueError('Presentation source drift '+name)
        pending[name]=transform(name,text)
    api=(ROOT/'scratch/fast3d-xdk/generated/include/fast/backends/gfx_window_manager_api.h').read_text()
    begin=api.index('  public:');end=api.index('  protected:',begin)
    decl=api[begin:end]
    decl,count=re.subn(r'    GfxWindowBackend\(\) :[^\n]+\n','',decl)
    if count!=1:raise ValueError('Window base constructor drift')
    decl=once(decl,'virtual ~GfxWindowBackend() {};','GfxWindowBackendXenos();')
    decl=decl.replace(' = 0','')
    pending['include/window_xenos.h']='#pragma once\n#include "fast/backends/gfx_window_manager_api.h"\n#include "pacing.h"\nnamespace Fast {\nclass GfxWindowBackendXenos : public GfxWindowBackend {\n'+decl+'  private:\n    void (*mAllKeysUp)();\n    uint32_t mRefreshRate;\n    Shipyard::PresentationPacing mPacing;\n};\n}\n'
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def includes():
    from prepare_input import includes as input_includes
    return [OUT/'generated/include',OWN,ROOT/'platform/shipyard/xenos',ROOT/'scratch/xenos-xdk/generated',
            ROOT/'scratch/fast3d-xdk/generated/include',ROOT/'scratch/imgui-xdk/generated',
            ROOT/'scratch/gui-resources-xdk/generated/include']+input_includes()


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
           '/DCONTROLLERBUTTONS_T=uint32_t','/Dnssv_CONFIG_SELECT_STRING_VIEW=1',
           '/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h'),'/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in includes()]
    rows=[]
    for source in [OUT/'generated/src/fast/Fast3dWindow.cpp',OUT/'generated/src/fast/FastMouseStateManager.cpp',OWN/'window_xenos.cpp']:
        obj=folder/(source.stem+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command))
        print(source.name+': '+str(result.returncode))
        if result.returncode:print('\n'.join(l for l in result.stdout.splitlines() if 'error ' in l)[:3500])
        elif struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not Xenon')
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
