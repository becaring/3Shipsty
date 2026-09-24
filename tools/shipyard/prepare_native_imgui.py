"""Verify and compile the shared Xenos ImGui renderer with Xbox input bindings."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from platform_base import resolve as resolve_platform_base
OWN=ROOT/'platform/shipyard/native-imgui'
OUT=ROOT/'scratch/native-imgui-xdk'


def prepare():
    platform_base=resolve_platform_base(ROOT)
    for name,row in json.loads((OWN/'donor.lock.json').read_text()).items():
        raw=(platform_base/row['platform_base']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Native ImGui donor changed '+name)
    source=platform_base/'sources/imgui/imgui_xenos.cpp'
    stable(OUT/'manifest.json',json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()},indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/DNOMINMAX','/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in [OWN,OUT/'generated',ROOT/'scratch/imgui-xdk/generated',ROOT/'platform/shipyard/xenos',ROOT/'platform/shipyard',resolve_platform_base(ROOT)/'sources/imgui',resolve_platform_base(ROOT)/'sources']]
    rows=[]
    for source in [resolve_platform_base(ROOT)/'sources/imgui/imgui_xenos.cpp',resolve_platform_base(ROOT)/'sources/imgui/platform_frame.cpp',OWN/'platform_adapter.cpp']:
        obj=folder/(source.stem+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        rows.append(dict(source=str(source),exit=result.returncode,command=command));print(source.name+': '+str(result.returncode))
        if result.returncode:print('\n'.join(l for l in result.stdout.splitlines() if 'error ' in l)[:3500])
        elif struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not Xenon')
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
