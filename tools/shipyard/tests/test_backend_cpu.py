"""Execute extracted backend functions against a recording device; no GPU claims."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Reuse host helpers without importing test_binary's target-platform resolver.
helpers = ast.parse(Path(__file__).with_name('test_binary.py').read_text())
helpers.body = [node for node in helpers.body if isinstance(node, ast.FunctionDef)
                and node.name in ('host_environment', 'invoke')]
exec(compile(helpers, 'test_binary.py', 'exec'))

ROOT = Path(__file__).resolve().parents[3]


def function(source, signature):
    begin = source.index(signature)
    brace = source.index('{', begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    functions = '\n'.join(function(source, name) for name in (
        'void InvalidateNativeState()',
        *(['HRESULT WriteNativeTexture('] if 'HRESULT WriteNativeTexture(' in source else []),
        'HRESULT SetNativeTexture(',
        'void SelectTexture(', 'void ApplyAlpha()'))
    fixture = r'''
#include <cassert>
#include <vector>
typedef int HRESULT;
typedef unsigned DWORD;
enum { S_OK=0, E_INVALIDARG=-1, TRUE=1, D3DBLEND_SRCALPHA=4,
 D3DBLEND_INVSRCALPHA=5, D3DBLENDOP_ADD=6, D3DBLEND_ZERO=7, D3DBLEND_ONE=8,
 D3DRS_ALPHABLENDENABLE, D3DRS_SRCBLEND, D3DRS_DESTBLEND, D3DRS_BLENDOP,
 D3DRS_COLORWRITEENABLE, D3DRS_SEPARATEALPHABLENDENABLE, D3DRS_SRCBLENDALPHA,
 D3DRS_DESTBLENDALPHA, D3DRS_BLENDOPALPHA };
#define SUCCEEDED(x) ((x)>=0)
struct IDirect3DTexture9 {};
struct Device {
 int binds=0, writes=0; bool fail=false;
 IDirect3DTexture9* bound[6]={}; unsigned state[32]={};
 HRESULT SetTexture(int slot, IDirect3DTexture9* p) {
  ++binds; if(fail)return -1; bound[slot]=p; return S_OK;
 }
 void SetRenderState(int key, unsigned value){++writes;state[key]=value;}
} device, *xenos_device=&device;
struct Native {
 bool texture_valid[6]={}; IDirect3DTexture9* texture[6]={};
 bool sampler_valid[6]={}, constants_valid=false, alpha_valid=false,
 binding_constants_valid=false; unsigned alpha_mode=0;
 void *vertex=0,*pixel=0,*declaration=0;
} native_state;
struct Certificate { void Invalidate(){} } sampler_certificate;
bool draw_state_prepared=false;
struct Texture { IDirect3DTexture9* native; int sampler; };
std::vector<Texture> textures;
unsigned selected[6]={}; int selected_fb[6]={-1,-1,-1,-1,-1,-1};
int upload_tile=0, samplerCalls=0;
void ApplySampler(int, int){++samplerCalls;}
void Shipyard_Fatal(const char*, HRESULT){assert(false);}
void Shipyard_Check(HRESULT hr,const char*){assert(hr>=0);}
bool requested_alpha=false,color_writes=true;
struct Shader {int features;} *current_shader=0;
unsigned mode=0;
unsigned NativeAlphaMode(bool,const int*){return mode;}
'''
    fixture += functions
    fixture += r'''
int main(){
 IDirect3DTexture9 a,b;
 assert(SetNativeTexture(0,&a)==S_OK);
 assert(SetNativeTexture(0,&a)==S_OK && device.binds==1);
 assert(SetNativeTexture(1,&a)==S_OK && device.binds==2);
 InvalidateNativeState();
 SetNativeTexture(0,&a); assert(device.binds==3);
 SetNativeTexture(0,0); SetNativeTexture(0,0); assert(device.binds==4);
 device.fail=true; assert(SetNativeTexture(0,&b)<0);
 device.fail=false; SetNativeTexture(0,&b); assert(device.binds==6);
 assert(SetNativeTexture(-1,&a)==E_INVALIDARG);
 assert(SetNativeTexture(6,&a)==E_INVALIDARG);
 textures.push_back(Texture{&a,1});
 SelectTexture(0,0); draw_state_prepared=true;
 int before=device.binds;
 SelectTexture(0,0); assert(draw_state_prepared && device.binds==before);
 assert(samplerCalls==2 && upload_tile==0);
 textures[0].native=&b;
 SelectTexture(0,0); assert(!draw_state_prepared && device.bound[0]==&b);
 draw_state_prepared=true; selected_fb[0]=1;
 SelectTexture(0,0); assert(!draw_state_prepared && selected_fb[0]==-1);
 InvalidateNativeState(); draw_state_prepared=true;
 SelectTexture(0,0); assert(!draw_state_prepared);
 InvalidateNativeState(); mode=0; ApplyAlpha(); assert(device.writes==9);
 mode=1; ApplyAlpha(); assert(device.writes==11);
 ApplyAlpha(); assert(device.writes==11);
 mode=2; ApplyAlpha(); assert(device.writes==13);
 assert(device.state[D3DRS_COLORWRITEENABLE]==7);
 color_writes=false; native_state.alpha_valid=false; ApplyAlpha();
 assert(device.writes==22 && device.state[D3DRS_COLORWRITEENABLE]==0);
 InvalidateNativeState(); ApplyAlpha(); assert(device.writes==31);
}
'''
    folder = ROOT / 'scratch/xenon-cpu-audit/backend/host'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'contract.cpp'
    path.write_text(fixture)
    compiler, env = host_environment()
    invoke([compiler, '/nologo', '/std:c++20', '/EHsc', str(path),
            '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')],
           folder, 'build', env)
    invoke([folder / 'contract.exe'], folder, 'run')
    print('Backend binding and alpha semantic contracts pass.')


if __name__ == '__main__':
    main()
