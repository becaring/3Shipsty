"""Actual Prism/builder differential with a test-only template input boundary."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import subprocess
import argparse

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from prepare_prism import prepare,OUT
from prepare_archives import stable
from prepare_configuration import once
from dependency_sources import verified
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)


def audit(text,projected):
    # Only the host audit replaces live Context resource acquisition. Production
    # shader_builder.cpp retains both complete real LoadResource paths and abort.
    start=text.index(('xbox_compat' if projected else 'std')+'::optional<std::string> dx_include_fs')
    end=text.index('std::string gfx_direct3d_common_build_shader',start)
    typ='xbox_compat' if projected else 'std'
    text=text[:start]+typ+'::optional<std::string> dx_include_fs(const std::string& path) { return AuditInclude(path); }\n\n'+text[end:]
    start=text.index('    auto init = std::make_shared<Ship::ResourceInitData>();')
    end=text.index('    processor.load(*shader);',start)+len('    processor.load(*shader);')
    text=text[:start]+'    processor.load(AuditTemplate);'+text[end:]
    for include in ('ship/Context.h','ship/resource/ResourceManager.h','ship/resource/type/Shader.h','ship/resource/ResourceType.h'):
        text=once(text,'#include "'+include+'"\n','')
    text=once(text,'#include "fast/interpreter.h"','#include "fast/cc_features.h"\n#include "audit.h"')
    return text


def compile_shaders():
    folder=OUT/'shader-objects';folder.mkdir(exist_ok=True)
    compiler=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/fxc.exe')
    seen=set();rows=[]
    for path in sorted((OUT/'host-projected').glob('*-xenos.hlsl')):
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        if sha in seen:continue
        seen.add(sha)
        for profile,entry in [('vs_3_0','VSMain'),('ps_3_0','PSMain')]:
            obj=folder/(path.stem+'.'+profile+'.bin')
            command=[str(compiler),'/nologo','/T',profile,'/E',entry,'/Fo',str(obj),str(path)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
            stable(obj.with_suffix('.log'),result.stdout+result.stderr)
            rows.append(dict(source=path.name,sha256=sha,profile=profile,exit=result.returncode,command=command))
    stable(OUT/'shader-compile-results.json',json.dumps(rows,indent=2)+'\n')
    failed=[r for r in rows if r['exit']]
    print('XDK shader compilation: '+str(len(rows)-len(failed))+' passed, '+str(len(failed))+' failed')
    if failed:raise RuntimeError('See shader-compile-results.json and shader-objects/*.log')


def main():
    prepare();env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')))
    compiler,environment=env['host_environment']();results=[]
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else verified('prism')/'src'
        original=OUT/('generated' if projected else 'reference')/'shader_builder.cpp'
        stable(folder/'builder-audit.cpp',audit(original.read_text(encoding='utf-8'),projected))
        namespace='xbox_compat' if projected else 'std'
        stable(folder/'audit.h','#pragma once\nextern std::string AuditTemplate;\n'+namespace+'::optional<std::string> AuditInclude(const std::string&);\nnamespace Fast {\nstd::string gfx_direct3d_common_build_shader(size_t&,const CCFeatures&,bool,bool,bool);\n}\n')
        resources=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
        paths=[base,folder,ROOT/'scratch/graphics-xdk/include',PLATFORM_BASE/'sources/graphics',PLATFORM_BASE/'sources',PLATFORM_BASE/'sources/value_types']+resources['includes'](projected)
        flags=['/nologo','/std:c++20','/utf-8','/EHsc','/MD','/O2','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0']
        if projected:flags+=['/DSHIPYARD_PROJECTED']
        common=[compiler]+flags+['/I'+str(p) for p in paths]
        invoke=folder/'invoke.obj'
        env['invoke'](common+['/TC','/c',base/'prism/utils/invoke.c','/Fo'+str(invoke)],folder,'invoke',environment)
        sources=[base/'prism'/n for n in ('lexer.cpp','ast.cpp','processor.cpp','utils/gv.cpp')]
        sources += [folder/'builder-audit.cpp',ROOT/'scratch/graphics-xdk/cc_features.cpp',resolve_platform_base(ROOT)/'sources/graphics/shader_lower.cpp',Path(__file__).with_name('test_prism_contract.cpp')]
        if projected:sources += [PLATFORM_BASE / 'sources/async/native.cpp',PLATFORM_BASE/'sources/clock/chrono.cpp',ROOT/'platform/shipyard/logging/environment.cpp']
        env['invoke'](common+sources+[invoke,'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')],folder,'build',environment)
        result=env['invoke']([folder/'contract.exe',ROOT/'libultraship/src/fast/shaders/directx/default.shader.hlsl'],folder,'run')
        results.append(result['stdout'])
    if results[0]!=results[1]:raise ValueError('Original/projected Prism or builder differs')
    a={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'host-original').glob('*.hlsl')}
    b={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'host-projected').glob('*.hlsl')}
    if a!=b:raise ValueError('Expanded/lowered shader byte mismatch')
    stable(OUT/'verification.json',json.dumps(dict(host_output=results[0],shader_hashes=b,target_runtime_executed=False,resource_loader_executed=False),indent=2)+'\n')
    print(results[0])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--shaders-only',action='store_true');args=parser.parse_args()
    if args.shaders_only:compile_shaders()
    else:main();compile_shaders()
