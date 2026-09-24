#include "shader_provider.h"
void gfx_cc_get_features(uint64_t,uint32_t,CCFeatures*);
void Shipyard_DecodeFast3DFeatures(const Fast::ShaderProgramKey& key,CCFeatures* features) {
    gfx_cc_get_features(key.shaderId0,key.shaderId1,features);
}
