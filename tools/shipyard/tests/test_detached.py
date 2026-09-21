"""Compare the native detached worker with real std::thread lifetime semantics."""
import json
from pathlib import Path
import subprocess
from test_binary import host_environment

ROOT=Path(__file__).resolve().parents[3]
def main():
    compiler,env=host_environment();out=ROOT/'scratch/async-xdk/detached-contract';results=[]
    for original in (True,False):
        folder=out/('original' if original else 'projected');folder.mkdir(parents=True,exist_ok=True)
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD','/I'+str(ROOT/'platform/shipyard'),str(ROOT/'platform/shipyard/async/detached_contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        if original:command+=['/DTEST_UPSTREAM']
        else:command+=[str(ROOT/'platform/shipyard/async/detached.cpp'),str(ROOT/'platform/shipyard/async/native.cpp')]
        build=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
        (folder/'build.log').write_text(build.stdout+build.stderr)
        assert build.returncode==0,folder/'build.log'
        result=subprocess.run([str(folder/'contract.exe')],capture_output=True,text=True,timeout=45)
        death=subprocess.run([str(folder/'contract.exe'),'--throws'],capture_output=True,text=True,timeout=15)
        row=dict(original=original,command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr,uncaught_exception_exit=death.returncode)
        (folder/'run.json').write_text(json.dumps(row,indent=2)+'\n')
        assert result.returncode==0,row
        assert death.returncode==73,row
        results.append(row)
    assert results[0]['stdout']==results[1]['stdout']
    (out/'verification.json').write_text(json.dumps(dict(cases=results,target_runtime_executed=False),indent=2)+'\n')
    print(results[0]['stdout'])
if __name__=='__main__':main()
