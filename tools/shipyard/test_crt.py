"""Compare actual CRT providers to the host standard library; inspect PPC output."""
import json, runpy, subprocess
from prepare_crt import ROOT, OWN, OUT, SDK, UNITS, sha, stable, build

def main():
    build()
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']()
    folder=OUT/'host';folder.mkdir(exist_ok=True)
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/O2','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',
        '/DSHIPYARD_CRT_ROUNDF=shipyard_roundf','/DSHIPYARD_CRT_TRUNCF=shipyard_truncf',
        '/DSHIPYARD_CRT_NEARBYINTF=shipyard_nearbyintf','/DSHIPYARD_CRT_SNPRINTF=shipyard_snprintf',
        '/DSHIPYARD_CRT_VSNPRINTF=shipyard_vsnprintf']
    command += [str(OWN/n) for n in UNITS]+[str(ROOT/'platform/shipyard/crt/contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
    stable(folder/'build.log',result.stdout+result.stderr);assert not result.returncode,folder/'build.log'
    result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
    stable(folder/'run.log',result.stdout+result.stderr);assert not result.returncode,result.stdout+result.stderr
    native=json.loads((OUT/'xdk/build.json').read_text())
    for row in native:
        assert row['exit']==0 and row['source_sha256']==sha(OWN/row['source'].split('/')[-1])
    disasm=subprocess.run([str(SDK/'bin/win32/dumpbin.exe'),'/disasm',str(OUT/'xdk/float.obj')],capture_output=True,text=True)
    assert not disasm.returncode
    stable(OUT/'xdk/float.disasm.txt',disasm.stdout)
    # Native finite branches are integer operations plus exact float loads/stores.
    assert 'frnd' not in disasm.stdout and 'fctiw' not in disasm.stdout
    assert 'fadds' in disasm.stdout and all(n+':' in disasm.stdout for n in ('roundf','truncf','nearbyintf'))
    symbols=subprocess.run([str(SDK/'bin/win32/dumpbin.exe'),'/symbols',str(OUT/'xdk/float.obj'),str(OUT/'xdk/format.obj')],capture_output=True,text=True)
    assert not symbols.returncode;stable(OUT/'xdk/symbols.txt',symbols.stdout)
    for symbol in ('roundf','truncf','nearbyintf','snprintf','Shipyard_Vsnprintf'):
        assert any('External' in line and 'UNDEF' not in line and '| '+symbol==line[line.find('| '):] for line in symbols.stdout.splitlines()),symbol
    stable(OUT/'verification.json',json.dumps(dict(host=dict(command=command,exit=result.returncode,output=result.stdout),
        native=native,disassembly_sha256=sha(OUT/'xdk/float.disasm.txt'),xenia_execution=False,hardware_execution=False),indent=2)+'\n')
    print(result.stdout.strip())

if __name__=='__main__':main()
