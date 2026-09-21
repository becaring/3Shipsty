#include "shader_provider.h"
#include <exception>
void gfx_cc_get_features(uint64_t,uint32_t,CCFeatures*);
bool Shipyard_BuildFast3DShader(const Fast::ShaderProgramKey& key,CCFeatures& features,size_t& floats,std::string& hlsl,std::string& error) {
    try {
        gfx_cc_get_features(key.shaderId0,key.shaderId1,&features);
        hlsl=Fast::gfx_direct3d_common_build_shader(floats,features,false,key.filteringMode==Fast::FILTER_THREE_POINT,key.srgbMode);
        error.clear();return true;
    }catch(const std::exception& failure){hlsl.clear();floats=0;error=failure.what();return false;}
}
