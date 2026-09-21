"""Actual complete GuiElement implementation differential; native shared classes compile separately."""
from pathlib import Path
import runpy
import subprocess
import sys
import json

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from prepare_window import prepare,OUT


def main():
    prepare()
    env=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
    compiler,environment=env['ENV'].host_environment();outputs=[];records=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else ROOT/'libultraship'
        source=base/'src/ship/window/gui/GuiElement.cpp'
        if not projected:
            # Include isolation only: every original constructor/method remains.
            text=source.read_text().replace('#include "ship/Context.h"','').replace('#include "ship/config/ConsoleVariable.h"','')
            source=folder/'GuiElement.cpp';source.write_text(text)
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/I'+str(base/'include'),str(source),
                 str(Path(__file__).with_name('test_gui_element_contract.cpp')),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'element.exe')]
        result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True)
        (folder/'build.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('See '+str(folder/'build.log'))
        result=subprocess.run([str(folder/'element.exe')],cwd=folder,capture_output=True,text=True)
        if result.returncode:raise RuntimeError('GUI element contract failed: '+result.stderr)
        outputs.append(result.stdout);records.append(dict(command=command,exit=result.returncode,stdout=result.stdout))
    if outputs[0]!=outputs[1]:raise RuntimeError('Original/projected GUI element behavior differs')
    (OUT/'verification.json').write_text(json.dumps(dict(cases=records,target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0])


if __name__=='__main__':main()
