// Compile contracts against the actual projected public headers. No backend
// implementation or successful draw is fabricated by this translation unit.
#include "fast/backends/gfx_rendering_api.h"
#include "fast/backends/gfx_window_manager_api.h"
#include "fast/cc_features.h"

typedef char ShaderId64IsEightBytes[sizeof(uint64_t) == 8 ? 1 : -1];
typedef char ShaderId32IsFourBytes[sizeof(uint32_t) == 4 ? 1 : -1];
typedef char CombinerComponentsAreInts[sizeof(((CCFeatures*)0)->c[0][0][0]) == sizeof(int) ? 1 : -1];
typedef char SixTextureBindings[SHADER_MAX_TEXTURES == 6 ? 1 : -1];

void Shipyard_CheckGraphicsSignatures() {
    Fast::ShaderProgram* (Fast::GfxRenderingAPI::*create)(uint64_t, uint32_t) =
        &Fast::GfxRenderingAPI::CreateAndLoadNewShader;
    Fast::ShaderProgram* (Fast::GfxRenderingAPI::*lookup)(uint64_t, uint32_t) =
        &Fast::GfxRenderingAPI::LookupShader;
    void (Fast::GfxRenderingAPI::*clear)(bool, bool) = &Fast::GfxRenderingAPI::ClearFramebuffer;
    void (Fast::GfxRenderingAPI::*read)(int, uint32_t, uint32_t, uint16_t*) =
        &Fast::GfxRenderingAPI::ReadFramebufferToCPU;
    void (Fast::GfxRenderingAPI::*copy)(int, int, int, int, int, int, int, int, int, int) =
        &Fast::GfxRenderingAPI::CopyFramebuffer;
    void* (Fast::GfxRenderingAPI::*texture)(int) = &Fast::GfxRenderingAPI::GetTextureById;
    void (*decoder)(uint64_t, uint32_t, CCFeatures*) = &gfx_cc_get_features;
    void (Fast::GfxWindowBackend::*init)(const char*, const char*, bool, uint32_t, uint32_t, int32_t, int32_t) =
        &Fast::GfxWindowBackend::Init;
    (void)create; (void)lookup; (void)clear; (void)read; (void)copy; (void)texture; (void)decoder; (void)init;
}
