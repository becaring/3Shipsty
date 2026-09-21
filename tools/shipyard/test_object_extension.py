"""Differential of the reached any contract and the complete real registry."""
import json
import runpy
import struct
import subprocess
from prepare_object_extension import ROOT,OUT,OWN,BASE,prepare
from prepare_archives import stable

def main():
    prepare();compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();results=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else ROOT
        header=(base/BASE/'ObjectExtension.h').read_text().replace('#include <libultraship/libultraship.h>','#include <cassert>')
        stable(folder/'ObjectExtension.h',header);stable(folder/'ObjectExtension.cpp',(base/BASE/'ObjectExtension.cpp').read_text())
        stable(folder/'registry.cpp','extern "C" void ObjectExtension_Free(const void*);\n'+(OWN/'registry_contract.cpp').read_text())
        for name in ('any','registry'):
            sources=[OWN/'contract.cpp'] if name=='any' else [folder/'registry.cpp',folder/'ObjectExtension.cpp']
            command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD','/I'+str(ROOT/'platform/shipyard'),'/I'+str(folder),'/I'+str(ROOT/'scratch/enhancements-xdk/generated/soh')]
            if not projected:command+=['/DTEST_UPSTREAM']
            command += [str(p) for p in sources]+['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/(name+'.exe'))]
            result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/(name+'.build.log'),result.stdout+result.stderr)
            assert result.returncode==0,folder/(name+'.build.log')
            result=subprocess.run([str(folder/(name+'.exe'))],cwd=ROOT,capture_output=True,text=True)
            row=dict(projected=projected,name=name,command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);results.append(row)
            stable(folder/(name+'.run.json'),json.dumps(row,indent=2)+'\n');assert result.returncode==0,row
    for name in ('any','registry'):assert [r['stdout'] for r in results if r['name']==name][0]==[r['stdout'] for r in results if r['name']==name][1]
    sdk=__import__('pathlib').Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/TP','/EHsc','/GR','/MT','/D_XBOX','/I'+str(sdk/'include/xbox'),'/I'+str(ROOT/'platform/shipyard'),str(OWN/'contract.cpp'),'/Fo'+str(OUT/'xdk/any_contract.obj')]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(OUT/'xdk/any_contract.log',result.stdout+result.stderr);assert result.returncode==0,OUT/'xdk/any_contract.log'
    assert struct.unpack_from('<H',(OUT/'xdk/any_contract.obj').read_bytes())[0]==0x1f2
    stable(OUT/'verification.json',json.dumps(dict(cases=results,native=command,target_runtime_executed=False),indent=2)+'\n');print('\n'.join(r['stdout'].strip() for r in results[:2]))
if __name__=='__main__':main()
