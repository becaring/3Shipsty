"""Primary native ImGui renderer and controller bindings on current ImGui."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
OWN=ROOT/'platform/shipyard/native-imgui'
OUT=ROOT/'scratch/native-imgui-xdk'


def prepare():
    donors={}
    for name,row in json.loads((OWN/'donor.lock.json').read_text()).items():
        raw=(OWN/'donor'/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Native ImGui donor changed '+name)
        donors[name]=raw.decode('utf-8-sig').replace('\r\n','\n')
    text=donors['imgui_xenos.cpp']
    text=once(text,'#include "platform.h"\n','')
    text=once(text,'#include "fast3d_float.h"\n','')
    text=text.replace('SoH_BeginNativeDraw','Fast::BeginNativeGuiDraw').replace('SoH_InvalidateNativeState','Fast::InvalidateNativeGuiState')
    text=text.replace('SoH_','Shipyard_').replace('soh_device','Fast::xenos_device').replace('SoH360_Xenos','Shipyard_Xenos')
    # Current backend capability is released along with its concrete objects.
    text=once(text,'ImGui::GetIO().BackendRendererName=NULL;',
              'ImGui::GetIO().BackendRendererName=NULL;ImGui::GetIO().BackendFlags&=~ImGuiBackendFlags_RendererHasVtxOffset;')
    platform=donors['imgui_platform.cpp']
    begin=platform.index('void Button(ImGuiIO&');end=platform.index('\n',platform.index('void Axis(ImGuiIO&',begin))
    helpers=platform[begin:end]
    begin=platform.index('    Button(io,ImGuiKey_GamepadStart,nav,');end=platform.index('    NativeKeyboard(io,buttons);',begin)
    binding=platform[begin:end]
    for old,new in [('pointerMode&&menu?0:state.Gamepad.sThumbLX','pad.leftX'),('pointerMode&&menu?0:state.Gamepad.sThumbLY','pad.leftY'),
                    ('state.Gamepad.bLeftTrigger','pad.leftTrigger'),('state.Gamepad.bRightTrigger','pad.rightTrigger')]:binding=once(binding,old,new)
    binding='    WORD nav=pad.buttons;\n    Button(io,ImGuiKey_GamepadBack,nav,XINPUT_GAMEPAD_BACK);\n'+binding
    pending={'imgui_xenos.cpp':text,'gamepad_bindings.inc':helpers+'\nvoid BindGamepad(ImGuiIO& io,const ShipyardInputRawPad& pad){\n'+binding+'}\n'}
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/DNOMINMAX','/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in [OWN,OUT/'generated',ROOT/'scratch/imgui-xdk/generated',ROOT/'platform/shipyard/xenos',ROOT/'platform/shipyard']]
    rows=[]
    for source in [OUT/'generated/imgui_xenos.cpp',OWN/'platform_frame.cpp']:
        obj=folder/(source.stem+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command));print(source.name+': '+str(result.returncode))
        if result.returncode:print('\n'.join(l for l in result.stdout.splitlines() if 'error ' in l)[:3500])
        elif struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not Xenon')
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
