"""Actual current loader contract without any replacement Context or archive."""
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
OUT=ROOT/'scratch/resource-manager-xdk'


def main():
    env=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
    compiler,environment=env['ENV'].host_environment()
    folder=OUT/'host-loader';folder.mkdir(parents=True,exist_ok=True)
    includes=[OUT/'generated/include']+env['includes'](True)+[PLATFORM_BASE/'sources',ROOT/'scratch/async-xdk/generated',
              ROOT/'scratch/deps/tinyxml2', ROOT/'libultraship/include']
    flags=['/nologo','/std:c++20','/EHsc','/MD','/Gy','/Zc:inline','/DSPDLOG_ACTIVE_LEVEL=0','/DNOMINMAX','/Dnssv_CONFIG_SELECT_STRING_VIEW=1']
    flags+=['/I'+str(p) for p in includes]
    # This bounded unit audit extracts exact method definitions, as the shader
    # decoder audit does. It is never a production source or application path.
    # The complete TU is separately compiled by prepare_resource_manager.py.
    from cpp_ast import PARSER,walk
    complete=OUT/'generated/src/ship/resource/ResourceLoader.cpp'
    data=complete.read_bytes()
    selected={'ResourceLoader','~ResourceLoader','RegisterGlobalResourceFactories','RegisterResourceFactory',
              'DecodeASCII','GetFactory','CreateDefaultResourceInitData','GetResourceType','ReadResourceInitDataBinary'}
    edits=[];kept=[]
    for node in walk(PARSER.parse(data).root_node):
        if node.type!='function_definition':continue
        name=node.child_by_field_name('declarator').text.decode().split('(')[0].split('::')[-1]
        if name in selected:kept.append(name)
        else:edits.append((node.start_byte,node.end_byte))
    if set(kept)!=selected or len(kept)!=10:raise ValueError('Loader audit selection drift')
    for begin,end in reversed(edits):data=data[:begin]+b'\n'+data[end:]
    audit=folder/'loader-method-audit.cpp';audit.write_bytes(data)
    sources=[audit,Path(__file__).with_name('test_resource_loader_contract.cpp')]
    sources += [OUT/'generated/src/ship/utils/StringHelper.cpp',OUT/'generated/src/ship/utils/glob.c']
    # Select the actual projected function, excluding XDK CRT declarations
    # whose size_t/annotation ABI cannot be compiled by an x64 host compiler.
    nativeglob=(OUT/'xdk/utils__glob.c').read_bytes()
    definitions=[n for n in walk(PARSER.parse(nativeglob).root_node) if n.type=='function_definition'
                 and n.child_by_field_name('declarator').text.decode().split('(')[0].strip()=='glob_match']
    if len(definitions)!=1:raise ValueError('Projected glob definition drift')
    glob_audit=folder/'glob-method-audit.c'
    glob_audit.write_bytes(b'#include <stddef.h>\n#define glob_match projected_glob_match\n'+definitions[0].text)
    sources += [glob_audit]
    sources += [ROOT/'scratch/resources-xdk/generated/src/ship/resource'/n for n in env['NAMES']]
    sources += [ROOT/'scratch/binary-xdk/generated/src/ship/utils/binarytools'/(n+'.cpp') for n in ('BinaryReader','BinaryWriter','MemoryStream','Stream')]
    sources += [PLATFORM_BASE/'sources/json/json.cpp',ROOT/'platform/shipyard/logging/environment.cpp',
                PLATFORM_BASE/'sources/clock/chrono.cpp']
    sources += [PLATFORM_BASE/'sources/async/native.cpp']
    objects=[];records=[]
    for index,source in enumerate(sources):
        obj=folder/(str(index)+'-'+source.stem+'.obj');objects.append(obj)
        localflags=[f for f in flags if not (source.suffix=='.c' and f=='/std:c++20')]
        command=[str(compiler)]+localflags+(['/std:c11','/TC'] if source.suffix=='.c' else [])+['/c',str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,env=environment,cwd=ROOT,capture_output=True,text=True)
        obj.with_suffix('.log').write_text(result.stdout+result.stderr)
        records.append(dict(command=command,exit=result.returncode))
        if result.returncode: raise RuntimeError('See '+str(obj.with_suffix('.log')))
    # No invented Context or dummy resource manager definitions are linked.
    command=[str(compiler),'/nologo','/MD']+[str(p) for p in objects]+[
        str(ROOT/'scratch/libzip-xdk/host/tinyxml2.lib'),'/Fe:'+str(folder/'loader.exe'),'/link','/OPT:REF']
    result=subprocess.run(command,env=environment,cwd=folder,capture_output=True,text=True)
    (folder/'link.log').write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError('See loader link.log')
    result=subprocess.run([str(folder/'loader.exe')],cwd=folder,capture_output=True,text=True)
    (folder/'verification.json').write_text(json.dumps(dict(compiles=records,link=command,exit=result.returncode,
        stdout=result.stdout,stderr=result.stderr,target_runtime_executed=False,scope='Selected exact loader methods only',
        selected_methods=kept),indent=2)+'\n')
    print(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError('Resource loader contract failed')


if __name__=='__main__':main()
