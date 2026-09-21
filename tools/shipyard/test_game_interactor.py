"""Execute the actual current registry algorithms on original/projected headers."""
import json
import runpy
import subprocess
import struct
from prepare_game_interactor import ROOT,OWN,OUT,BASE,prepare,includes,call_sites
from prepare_soh_resources import includes as resource_includes
from prepare_archives import stable

def main():
    prepare();compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();records=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        if not projected:
            text=(ROOT/BASE/'GameInteractor.h').read_text().replace('#include "libultraship/libultraship.h"','#include <libultraship/bridge.h>\n#include <string>')
            stable(folder/'GameInteractor.h',text)
        body=(OWN/'contract.cpp').read_text()
        if projected:body=call_sites(body,(OWN/'contract.cpp').relative_to(ROOT).as_posix())
        stable(folder/'contract.cpp',body)
        cross='#include "GameInteractor.h"\nHOOK_ID RegisterCrossTranslationUnit(GameInteractor* gi,int* value) {return gi->RegisterGameHook<GameInteractor::OnSceneInit>([value](int16_t n){*value+=n;});}\n'
        if projected:cross=call_sites(cross,'platform/shipyard/game-interactor/cross.cpp')
        stable(folder/'cross.cpp',cross)
        paths=([OUT/'generated'/BASE]+includes()) if projected else [folder,ROOT/BASE]+resource_includes(False)
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/DNOMINMAX','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t']
        if not projected:command+=['/Zc:preprocessor']
        command+=['/I'+str(p) for p in paths]+[str(folder/'contract.cpp'),str(folder/'cross.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(folder/'build.log')
        result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
        row=dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);stable(folder/'run.json',json.dumps(row,indent=2)+'\n');records.append(row);assert result.returncode==0,row
    assert records[0]['stdout']==records[1]['stdout']
    native=[];recipe=json.loads((OUT/'xdk/build.json').read_text())[0]['command'];flags=recipe[:-2]
    for name in ('contract','cross'):
        source=OUT/'host-projected'/(name+'.cpp');obj=OUT/'xdk'/('test_'+name+'.obj')
        command=flags+['/I'+str(OUT/'generated'/BASE),str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(OUT/'xdk'/('test_'+name+'.log'),result.stdout+result.stderr)
        assert result.returncode==0,OUT/'xdk'/('test_'+name+'.log')
        assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
        native.append(dict(command=command,exit=result.returncode))
    stable(OUT/'verification.json',json.dumps(dict(cases=records,native=native,target_runtime_executed=False,actual_game_services_executed=False),indent=2)+'\n');print(records[0]['stdout'])
if __name__=='__main__':main()
