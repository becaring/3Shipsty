"""Execute real queue/DMA methods, native timer ownership and clock conversion."""
import hashlib
import json
import runpy
import struct
import subprocess
from prepare_libultra import ROOT,OWN,OUT,prepare,transform
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable

def public_symbols(path):
    data=path.read_bytes();machine,sections,stamp,pointer,count,opt,flags=struct.unpack_from('<HHIIIHH',data)
    assert machine==0x1f2
    i=0;strings=pointer+count*18;result=[]
    while i<count:
        pos=pointer+i*18;name=data[pos:pos+8]
        if name[:4]==b'\0'*4:
            offset=struct.unpack_from('<I',name,4)[0];name=data[strings+offset:data.index(b'\0',strings+offset)]
        else:name=name.split(b'\0')[0]
        value,section,kind,storage,aux=struct.unpack_from('<IhHBB',data,pos+8)
        if storage==2 and section>0 and name.startswith((b'os',b'__os',b'__lus',b'Resource',b'Controller',b'Gfx',b'IsResource')):result.append(name.decode('ascii'))
        i+=1+aux
    return result

def ownership():
    own={symbol:p.name for p in (OUT/'xdk').glob('*.obj') for symbol in public_symbols(p)}
    game=list((ROOT/'scratch/game-xdk/full/objects').glob('*.obj'));assert len(game)==696
    collisions=[]
    for path in game:
        for symbol in public_symbols(path):
            if symbol in own:collisions.append((symbol,own[symbol],path.relative_to(ROOT).as_posix()))
    expected={'osCreatePiManager','osWritebackDCache','osInvalICache','osInvalDCache','osWritebackDCacheAll'}
    assert {x[0] for x in collisions}==expected
    assert all(x[2].endswith('/soh__soh__stubs.obj') for x in collisions)
    result=dict(selected_game_objects=len(game),public_c_symbols=own,expected_unextracted_archive_collisions=collisions)
    stable(OUT/'ownership.json',json.dumps(result,indent=2)+'\n')
    return result

def main():
    prepare();envmod=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'));compiler,env=envmod['host_environment']()
    outputs=[];records=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        sources=[]
        for stem in ('os_mesg','os_pi','os_vm','os_cache'):
            name='src/libultraship/libultra/'+stem+'.cpp'
            if projected:path=OUT/'generated'/name
            else:
                # Identical header narrowing only, not method projection. No
                # Context, renderer or resource providers are substituted.
                text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
                text=text.replace('#include "libultraship/libultraship.h"','#include "libultraship/libultra.h"\n#include <cstring>')
                path=folder/(stem+'.cpp');stable(path,text)
            sources.append(path)
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/I'+str(ROOT/'libultraship/include'),'/Fe:'+str(folder/'contract.exe'),'/Fo:'+str(folder)+'/']+[str(p) for p in sources+[OWN/'contract.cpp']]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'compile.log',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Build failed '+str(folder/'compile.log'))
        result=subprocess.run([str(folder/'contract.exe')],cwd=folder,capture_output=True,text=True)
        record=dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);records.append(record)
        if result.returncode:raise RuntimeError(str(record))
        outputs.append(result.stdout)
    assert outputs[0]==outputs[1]
    folder=OUT/'host-native-timer';folder.mkdir(exist_ok=True)
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/I'+str(ROOT/'platform/shipyard'),'/I'+str(PLATFORM_BASE/'sources'),'/Fe:'+str(folder/'contract.exe'),'/Fo:'+str(folder)+'/']+[str(p) for p in [PLATFORM_BASE/'sources/libultra/clock.cpp',PLATFORM_BASE/'sources/libultra/timer.cpp',OWN/'timer_contract.cpp',PLATFORM_BASE/'sources/async/native.cpp',PLATFORM_BASE/'sources/clock/chrono.cpp']]
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'compile.log',result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Timer build failed '+str(folder/'compile.log'))
    result=subprocess.run([str(folder/'contract.exe')],cwd=folder,capture_output=True,text=True,timeout=15)
    record=dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);records.append(record)
    if result.returncode:raise RuntimeError(str(record))
    # All methods and overloads remain. SDL discovery and timing are the only
    # behavior boundaries; method counting guards against accidental trimming.
    parser=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))
    method_counts={}
    for name in json.loads((OUT/'manifest.json').read_text()):
        original=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig');projected=transform(name,original)
        def methods(text):
            return [n.child_by_field_name('declarator').text.decode().replace('Uint32','uint32_t') for n in parser['walk'](parser['PARSER'].parse(text.encode()).root_node) if n.type=='function_definition']
        assert methods(original)==methods(projected),(name,methods(original),methods(projected))
        method_counts[name]=len(methods(original))
    stable(OUT/'verification.json',json.dumps(dict(cases=records,method_counts=method_counts,ownership=ownership(),native_objects={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'xdk').glob('*.obj')},target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0]+records[-1]['stdout']);print('Full production method counts:',method_counts)

if __name__=='__main__':main()
