"""Full current resource classes/factories plus exact stb, original/projected."""
from pathlib import Path
import runpy
import subprocess
import sys
import json
import zlib
import struct

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from prepare_gui_resources import prepare,OUT
from prepare_archives import stable
from dependency_sources import verified


def main():
    prepare();env=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
    compiler,environment=env['ENV'].host_environment();outputs=[];records=[]
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    fixture=OUT/'rgba-fixture.png'
    fixture.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,6,0,0,0))+
                        chunk(b'IDAT',zlib.compress(bytes([0,255,0,0,255,0,255,0,128,0,0,0,255,0,1,2,3,4])))+chunk(b'IEND',b''))
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else ROOT/'libultraship'
        resources=ROOT/'scratch/resources-xdk/generated' if projected else ROOT/'libultraship'
        binary=ROOT/'scratch/binary-xdk/generated' if projected else ROOT/'libultraship'
        includes=[base/'include',verified('stb')]+env['includes'](projected)
        sources=[base/'src/ship/window/gui/resource'/(n+'.cpp') for n in ('Font','FontFactory','GuiTexture','GuiTextureFactory')]
        sources += [base/'src/fast/resource/type/Texture.cpp',resources/'src/ship/resource/Resource.cpp',resources/'src/ship/resource/ResourceFactoryBinary.cpp']
        sources += [binary/'src/ship/utils/binarytools'/(n+'.cpp') for n in ('BinaryReader','BinaryWriter','MemoryStream','Stream')]
        sources += [OUT/'generated/stb_impl.c']
        if projected:sources += [ROOT/'platform/shipyard/async/native.cpp',ROOT/'platform/shipyard/logging/chrono/chrono.cpp',ROOT/'platform/shipyard/logging/environment.cpp']
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0']
        command+=['/I'+str(p) for p in includes]+[str(p) for p in sources]+[str(Path(__file__).with_name('test_gui_resources_contract.cpp')),
                  '/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'resources.exe')]
        result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True)
        stable(folder/'build.log',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('See '+str(folder/'build.log'))
        result=subprocess.run([str(folder/'resources.exe'),str(fixture)],cwd=folder,capture_output=True,text=True)
        stable(folder/'run.json',json.dumps(dict(exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2)+'\n')
        if result.returncode:raise RuntimeError('GUI resources contract failed '+str(result.returncode)+': '+result.stderr)
        outputs.append(result.stdout);records.append(dict(command=command,exit=result.returncode,stdout=result.stdout))
    if outputs[0]!=outputs[1]:raise RuntimeError('Original/projected GUI resources behavior differs')
    stable(OUT/'verification.json',json.dumps(dict(cases=records,target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0])


if __name__=='__main__':main()
