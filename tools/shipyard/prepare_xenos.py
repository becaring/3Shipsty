"""Primary proven Xenos mechanics adapted to the exact current rendering API."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once

OWN=ROOT/'platform/shipyard/xenos'
OUT=ROOT/'scratch/xenos-xdk'


def prepare():
    from prepare_fast3d import prepare as prepare_current_interfaces
    prepare_current_interfaces()
    sources={}
    for name,row in json.loads((OWN/'donor.lock.json').read_text()).items():
        if 'sha256' not in row:continue
        raw=(OWN/'donor'/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Xenos donor drift '+name)
        sources[name]=raw.decode('utf-8-sig').replace('\r\n','\n')
    text=runpy.run_path(str(OWN/'projection.py'))['native_core'](sources['gfx_xenos.cpp'])
    text=text.replace('Smash360_','Shipyard_').replace('smash_device','xenos_device').replace('SoH','Shipyard').replace('SOH_','SHIPYARD_')
    # Shader persistence is an optional optimization deferred until modern
    # storage owns its path/worker. Runtime always invokes the real XDK compiler.
    text=once(text,'#include "shader_cache.h"','')
    text=once(text,'ID3DXBuffer *code = Shipyard_LoadShaderCode(source,entry,profile), *errors = NULL;\n    if(code)return code;',
              'ID3DXBuffer *code = NULL, *errors = NULL;')
    text=once(text,'    Shipyard_StoreShaderCode(source,entry,profile,code);\n','')
    text=once(text,'ShaderProgram* shader = new ShaderProgram();','ShaderProgram* shader = new ShaderProgram();\n    shader->key=key;')
    text=once(text,'struct ShaderProgram {','struct ShaderProgram {\n    ShaderProgramKey key;')
    text=once(text,'        delete shader; return NULL;','        delete shader; Shipyard_Fatal(error.c_str(),E_FAIL);')
    text=once(text,'std::vector<Framebuffer> buffers;','std::vector<Framebuffer> buffers;\n'
              'bool framebuffer_clear_reuse_disabled=false;\nunsigned framebuffer_clear_count,framebuffer_restore_avoided,framebuffer_depth_restore_avoided;')
    text=once(text,'static_assert(__alignof(NativeStateCache)>=16 && offsetof(NativeStateCache,constants)%16==0,\n              "native pixel constants must be 16-byte aligned");',
              'typedef char NativeConstantsAligned[(__alignof(NativeStateCache)>=16 && offsetof(NativeStateCache,constants)%16==0)?1:-1];')
    text=once(text,'    __declspec(align(16)) float binding_constants[24];\n    bool binding_constants_valid;','')
    text=once(text,'    native_state.binding_constants_valid=false;','')
    extension=sources['native_extensions.inc']
    begin=extension.index('void CopyRegion(');end=extension.index('\n}\n\nvoid InitializeNativeDisplay()',begin)
    extension='namespace {\n'+extension[begin:end]+'\n}\n'
    extension=extension.replace('Smash360_','Shipyard_').replace('smash_device','xenos_device')
    begin=extension.index('            const unsigned r=');end=extension.index('\n        }',begin)
    extension=extension[:begin]+'            rgba16[(size_t)y*width+x]=Shipyard::Xenos::PackReadbackPixel(p);'+extension[end:]
    text=once(text,'#include "services.h"','#include "services.h"\n#include "pixels.h"')
    # Current rectangular copy requires a caller-supplied quad; all old full
    # copies retain their original default quad.
    text=once(text,'uint32_t height,DWORD sample_mask) {','uint32_t height,DWORD sample_mask,const float* copy_quad=NULL) {')
    text=once(text,'D3DPT_TRIANGLELIST,2,quad,4*sizeof(float)','D3DPT_TRIANGLELIST,2,copy_quad?copy_quad:quad,4*sizeof(float)')
    text+='\n'+extension+'\n'+(OWN/'api.inc').read_text()+'\n} // namespace Fast\n'
    # Build the concrete declaration directly from the pinned current interface.
    api=(ROOT/'scratch/fast3d-xdk/generated/include/fast/backends/gfx_rendering_api.h').read_text()
    begin=api.index('  public:');end=api.index('  protected:',begin)
    declarations=api[begin:end].replace('virtual ~GfxRenderingAPI() {}','virtual ~GfxRenderingAPIXenos();').replace(' = 0','')
    declarations,count=re.subn(r'    GfxRenderingAPI\(\) :[^\n]+\n','',declarations)
    if count!=1:raise ValueError('Current API base constructor drift')
    declarations=declarations.replace('~GfxRenderingAPIXenos();;','~GfxRenderingAPIXenos();')
    header='#pragma once\n#include "fast/backends/gfx_rendering_api.h"\nnamespace Fast {\nclass GfxRenderingAPIXenos : public GfxRenderingAPI {\n'+declarations+'};\n}\n'
    pending={'native.cpp':text,'xenos_backend.h':header}
    for name,value in pending.items():stable(OUT/'generated'/name,value)
    stable(OUT/'manifest.json',json.dumps(dict(outputs={n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},disk_shader_cache_integrated=False),indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    from prepare_window import includes
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0','/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in [OUT/'generated',OWN,ROOT/'scratch/fast3d-xdk/generated/include',ROOT/'scratch/imgui-xdk/generated',ROOT/'scratch/graphics-xdk/include']+includes()]
    rows=[]
    for source in [OUT/'generated/native.cpp',OWN/'shader_provider.cpp',OWN/'services.cpp']:
        obj=folder/(source.stem+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command))
        print(source.name+': '+str(result.returncode))
        if result.returncode:print('\n'.join(l for l in result.stdout.splitlines() if 'error ' in l)[:3500])
        elif struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not Xenon')
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
