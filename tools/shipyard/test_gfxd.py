"""Compare every full pinned libgfxd TU before/after its C compatibility projection."""
import hashlib
import json
import runpy
import subprocess
from prepare_gfxd import ROOT,OWN,OUT,UNITS,prepare,lower_tables,lower_c
from prepare_archives import stable
from dependency_sources import verified

def main():
    prepare();envmod=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'));compiler,env=envmod['host_environment']();records=[];outputs=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        source=OUT/'source' if projected else verified('libgfxd');objects=[]
        flags=[str(compiler),'/nologo','/TC','/std:c11','/Zc:preprocessor','/MD','/O2','/DNOMINMAX','/I'+str(source),'/I'+str(ROOT/'platform/shipyard')]
        if projected:flags+=['/D_XBOX']  # Execute the actual CRT formatting boundary on the host as well.
        commands=[]
        for name in UNITS+['contract.c']:
            path=OWN/name if name=='contract.c' else source/name;obj=folder/(path.stem+'.obj')
            if projected and name!='contract.c':
                pre=folder/(path.stem+'.i');command=flags+['/P','/Fi'+str(pre),str(path)]
                result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/(path.stem+'.pre.log'),result.stdout+result.stderr)
                if result.returncode:raise RuntimeError('Preprocess failed '+str(path))
                # Host C11 headers contain unrelated boolean typedef machinery.
                # Exercise the semantic table projection here; the separately
                # verified generic C89 scope pass runs in the native recipe.
                data=lower_tables(pre.read_bytes());path=folder/name;path.write_bytes(data)
            command=flags+['/c',str(path),'/Fo'+str(obj)];commands.append(command)
            result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/(path.stem+'.log'),result.stdout+result.stderr)
            if result.returncode:raise RuntimeError('Build failed '+str(folder/(path.stem+'.log')))
            objects.append(str(obj))
        command=[str(compiler),'/nologo','/MD']+objects+['/Fe:'+str(folder/'contract.exe')]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'link.log',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Link failed '+str(folder))
        result=subprocess.run([str(folder/'contract.exe')],cwd=folder,capture_output=True,text=True)
        record=dict(commands=commands,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);stable(folder/'run.json',json.dumps(record,indent=2)+'\n')
        if result.returncode:raise RuntimeError(str(record))
        records.append(record);outputs.append(result.stdout)
    assert outputs[0]==outputs[1]
    stable(OUT/'verification.json',json.dumps(dict(cases=records,native_objects={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'xdk').glob('*.obj')},target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0])
if __name__=='__main__':main()
