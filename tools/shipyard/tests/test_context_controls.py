"""Current Console method audit and full GfxDebugger differential.

Console::Run needs live Context and is explicitly excluded from this host audit.
Complete production TUs compile separately; no Context implementation is replaced.
"""
from pathlib import Path
import runpy
import subprocess
import sys
import json

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_context import prepare,OUT
from prepare_archives import stable
from cpp_ast import PARSER,walk


def main():
    prepare();env=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
    compiler,environment=env['ENV'].host_environment();outputs=[];records=[]
    for projected in (False,True):
        folder=OUT/('host-controls-projected' if projected else 'host-controls-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else ROOT/'libultraship'
        includes=[base/'include']+env['includes'](projected)
        # Same complete current Context declaration with its unused Audio
        # implementation include narrowed to the exact settings declaration.
        for path in ('ship/Context.h','ship/audio/AudioSettings.h'):
            stable(folder/'include'/path,(ROOT/'scratch/resource-manager-xdk/generated/include'/path).read_text())
        includes=[folder/'include']+includes+[ROOT/'scratch/imgui-xdk/generated',ROOT/'platform/shipyard',PLATFORM_BASE/'sources',ROOT/'scratch/resource-manager-xdk/generated/include']
        console=(base/'src/ship/debug/Console.cpp').read_bytes()
        definitions=[n for n in walk(PARSER.parse(console).root_node) if n.type=='function_definition'
                     and n.child_by_field_name('declarator').text.startswith(b'Console::Run(')]
        if len(definitions)!=1:raise ValueError('Console audit selector drift')
        node=definitions[0];console=console[:node.start_byte]+console[node.end_byte:]
        audit=folder/'console-method-audit.cpp';audit.write_bytes(console)
        sources=[audit,base/'src/fast/debug/GfxDebugger.cpp',
                 (ROOT/'scratch/resource-manager-xdk/generated' if projected else ROOT/'libultraship')/'src/ship/utils/StringHelper.cpp']
        if projected:sources += [PLATFORM_BASE / 'sources/async/native.cpp',PLATFORM_BASE/'sources/clock/chrono.cpp',ROOT/'platform/shipyard/logging/environment.cpp']
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0']
        if projected:command+=['/Dnssv_CONFIG_SELECT_STRING_VIEW=1']
        command+=['/I'+str(p) for p in includes]+[str(p) for p in sources]+[str(Path(__file__).with_name('test_context_controls.cpp')),
                  '/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'controls.exe')]
        result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True)
        stable(folder/'build.log',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('See '+str(folder/'build.log'))
        result=subprocess.run([str(folder/'controls.exe')],cwd=folder,capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Context controls contract failed: '+result.stderr)
        outputs.append(result.stdout);records.append(dict(command=command,exit=result.returncode,stdout=result.stdout))
    if outputs[0]!=outputs[1]:raise RuntimeError('Original/projected controls behavior differs')
    stable(OUT/'controls-verification.json',json.dumps(dict(cases=records,target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0])


if __name__=='__main__':main()
