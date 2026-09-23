"""Native ABI plus host pixel/cache boundaries; never claims GPU execution."""
from pathlib import Path
import json
import runpy
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from prepare_xenos import prepare,OUT,OWN
from prepare_archives import stable

def main():
    prepare();folder=OUT/'host';folder.mkdir(exist_ok=True)
    env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')));compiler,environment=env['host_environment']()
    text='''#include "pixels.h"
#include "shader_provider.h"
#include "xenos_backend.h"
#include <type_traits>
#include <map>
#include <cstdio>
#include <stdexcept>
#define CHECK(c) do{if(!(c))throw std::runtime_error(#c);}while(0)
static_assert(!std::is_abstract<Fast::GfxRenderingAPIXenos>::value,"missing current rendering virtual method");
int main(){
    for(unsigned v=0;v<256;++v)for(unsigned alpha=0;alpha<256;++alpha){
        unsigned five=(31*v+124)/255;
        CHECK(Shipyard::Xenos::PackReadbackPixel((alpha<<24)|(v<<16))==((five<<11)|(alpha?1:0)));
        CHECK(Shipyard::Xenos::PackReadbackPixel((alpha<<24)|(v<<8))==((five<<6)|(alpha?1:0)));
        CHECK(Shipyard::Xenos::PackReadbackPixel((alpha<<24)|v)==((five<<1)|(alpha?1:0)));
    }
    CHECK(Shipyard::Xenos::PackReadbackPixel(0xffffffff)==0xffff);
    std::map<Fast::ShaderProgramKey,int> variants;
    for(unsigned id=0;id<16;++id)for(unsigned option=0;option<16;++option)for(int filter=0;filter<3;++filter)for(int srgb=0;srgb<2;++srgb){
        Fast::ShaderProgramKey key={uint64_t(id)<<60,uint32_t(option)<<28,static_cast<Fast::FilteringMode>(filter),srgb!=0};
        CHECK(variants.insert(std::make_pair(key,static_cast<int>(variants.size()))).second);
    }
    CHECK(variants.size()==1536);
    std::puts("196608 ARGB/RGB5551 channel-alpha cases and 1536 full-width shader identities pass; current interface is concrete");
}
'''
    stable(folder/'contract.cpp',text)
    flags=['/nologo','/std:c++20','/EHsc','/MD']+['/I'+str(p) for p in [OWN,OUT/'generated',ROOT/'scratch/fast3d-xdk/generated/include',ROOT/'scratch/imgui-xdk/generated',ROOT/'scratch/graphics-xdk/include']]
    env['invoke']([compiler]+flags+[folder/'contract.cpp','/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')],folder,'build',environment)
    result=env['invoke']([folder/'contract.exe'],folder,'run')
    generated=(OUT/'generated/native.cpp').read_text()
    begin=generated.index('void SetNativeBindingConstants(')
    end=generated.index('\n}',begin)+2
    assert 'native_state.binding_constants_valid=false;' in generated
    binding='''#include <cstring>
#include <cstdio>
#include <stdexcept>
struct NativeState { float binding_constants[24]; bool binding_constants_valid; } native_state = {};
struct Device {
    int writes = 0;
    float values[24] = {};
    int SetPixelShaderConstantF(int start, const float* values, int count) {
        if (start != 8 || count != 6) return -1;
        std::memcpy(this->values, values, sizeof(this->values));
        ++writes;
        return 0;
    }
} device, *xenos_device = &device;
void Shipyard_Check(int result, const char*) { if (result) throw std::runtime_error("SDK write"); }
''' + generated[begin:end] + '''
int main() {
    float values[24] = {};
    SetNativeBindingConstants(values);
    SetNativeBindingConstants(values);
    if (device.writes != 1) return 1;
    values[23] = 640.0f;
    SetNativeBindingConstants(values);
    SetNativeBindingConstants(values);
    if (device.writes != 2 || device.values[23] != 640.0f) return 2;
    native_state.binding_constants_valid = false;
    SetNativeBindingConstants(values);
    if (device.writes != 3) return 3;
    values[0] = -0.0f;
    SetNativeBindingConstants(values);
    if (device.writes != 4) return 4;
    std::puts("binding constants: reuse, change, invalidation, exact bits pass");
}
'''
    stable(folder/'binding_contract.cpp',binding)
    env['invoke']([compiler,'/nologo','/std:c++20','/EHsc','/MD',folder/'binding_contract.cpp',
                   '/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'binding_contract.exe')],folder,'build-binding',environment)
    binding_result=env['invoke']([folder/'binding_contract.exe'],folder,'run-binding')
    stable(OUT/'verification.json',json.dumps(dict(host_output=result['stdout']+binding_result['stdout'],
                                                  target_runtime_executed=False),indent=2)+'\n')
    print(result['stdout'])
    print(binding_result['stdout'])
if __name__=='__main__':main()
