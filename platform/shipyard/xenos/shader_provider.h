#pragma once
#include "fast/cc_features.h"
#include "fast/backends/gfx_rendering_api.h"
#include "shader_lower.h"
#include <string>

namespace Fast {
// Internal cache identity; the release's virtual API remains uint64/uint32.
struct ShaderProgramKey {
    uint64_t shaderId0;
    uint32_t shaderId1;
    FilteringMode filteringMode;
    bool srgbMode;
    bool operator<(const ShaderProgramKey& rhs) const {
        if(shaderId0!=rhs.shaderId0)return shaderId0<rhs.shaderId0;
        if(shaderId1!=rhs.shaderId1)return shaderId1<rhs.shaderId1;
        if(filteringMode!=rhs.filteringMode)return filteringMode<rhs.filteringMode;
        return srgbMode<rhs.srgbMode;
    }
};
std::string gfx_direct3d_common_build_shader(size_t&,const CCFeatures&,bool,bool,bool);
}
bool Shipyard_BuildFast3DShader(const Fast::ShaderProgramKey&,CCFeatures&,size_t&,std::string&,std::string&);
