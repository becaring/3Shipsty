"""Real ShipInit and native variadic boundary contracts, without game substitutes."""
import json
import runpy
import struct
import subprocess
from prepare_enhancements import ROOT,OWN,OUT,prepare,transform,includes
from prepare_archives import stable
def main():
    prepare();compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();rows=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        paths=includes() if projected else [ROOT/'soh',ROOT/'platform/shipyard']
        for name in ('init','varargs'):
            original=(OWN/(name+'_contract.cpp')).read_text()
            text=transform((OWN/(name+'_contract.cpp')).relative_to(ROOT).as_posix(),original) if projected and name=='init' else original
            source=folder/(name+'.cpp');stable(source,text)
            command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD']+['/I'+str(p) for p in paths]
            if not projected:command+=['/DTEST_UPSTREAM']
            command+=[str(source),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/(name+'.exe'))]
            result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/(name+'.build.log'),result.stdout+result.stderr);assert result.returncode==0,folder/(name+'.build.log')
            result=subprocess.run([str(folder/(name+'.exe'))],cwd=ROOT,capture_output=True,text=True)
            row=dict(projected=projected,name=name,command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);rows.append(row);stable(folder/(name+'.run.json'),json.dumps(row,indent=2)+'\n');assert result.returncode==0,row
    for name in ('init','varargs'):assert [r['stdout'] for r in rows if r['name']==name][0]==[r['stdout'] for r in rows if r['name']==name][1]
    recipe=json.loads((ROOT/'scratch/game-interactor-xdk/xdk/build.json').read_text())[0]['command'][:-2];recipe.insert(1,'/I'+str(OUT/'generated/soh'));native=[]
    for name in ('init','varargs'):
        obj=OUT/'xdk'/('test_'+name+'.obj');command=recipe+['/I'+str(OUT/'generated/soh'),str(OUT/'host-projected'/(name+'.cpp')),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr);assert result.returncode==0,obj.with_suffix('.log')
        assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;native.append(dict(command=command,exit=result.returncode))
    stable(OUT/'verification.json',json.dumps(dict(host=rows,native=native,actual_game_cheats_executed=False,target_runtime_executed=False),indent=2)+'\n');print('\n'.join(r['stdout'].strip() for r in rows[:2]))
if __name__=='__main__':main()
