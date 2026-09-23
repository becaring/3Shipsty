"""Reviewed generic Xenos adaptations; no BattleShip VI/postprocess policy.
Derived from inspected prepare_graphics_xdk.py native_core prefix.
"""
from prepare_configuration import once as replace_once

def native_core(original):
    # Import rendering production mechanics only; omit donor diagnostic scenes,
    # synthetic validation draws, old callback table and SoH frame-audit hooks.
    text = original[:original.index("const char* requestedRuntimeCapture;")]
    end = original[original.index("void End() {"):original.index("void SoH_RequestRuntimeFramebufferCheck")]
    end = replace_once(end, "    CheckRuntimeFramebufferRestore();\n", "")
    text += end
    shutdown = original[original.index("void SoH_ShutdownGraphics() {"):original.index("void SoH_GetTextureUploadCounts")]
    text += shutdown
    text = text[text.index("IDirect3DDevice9* soh_device;"):]
    text = '#include "services.h"\n#include "shader_provider.h"\n#include "shader_cache.h"\n#include "xenos_backend.h"\n#include "metrics.h"\n#include <xgraphics.h>\n#include <vectorintrinsics.h>\n#include <stddef.h>\n#include <stdio.h>\n#include <map>\n#include <algorithm>\nnamespace Fast {\n' + text
    text = text.replace("SoH_", "Smash360_").replace("soh_device", "smash_device")
    text = text.replace("used_textures", "usedTextures").replace("num_inputs", "numInputs")
    text = text.replace("std::map<std::pair<uint64_t, uint32_t>, ShaderProgram*>", "std::map<ShaderProgramKey, ShaderProgram*>")
    text = text.replace("std::map<std::pair<uint64_t,uint32_t>, ShaderProgram*>", "std::map<ShaderProgramKey, ShaderProgram*>")
    text = text.replace("std::map<std::pair<uint64_t,uint32_t>,ShaderProgram*>", "std::map<ShaderProgramKey,ShaderProgram*>")
    start = text.index("// Retain SoH's generated combiner")
    stop = text.index("GfxClipParameters ClipParameters()")
    text = text[:start] + text[stop:]
    text = replace_once(text, "ShaderProgram* CreateShader(uint64_t id0, uint32_t id1)", "ShaderProgram* CreateShader(const ShaderProgramKey& key)")
    text = replace_once(text, "    gfx_cc_get_features(id0, id1, &shader->features);\n    std::string source = XboxShader(shader->features, shader->floats);", """    std::string source, hlsl, error;
    if(!Smash360_BuildFast3DShader(key,shader->features,shader->floats,hlsl,error) ||
       !Smash360_LowerShader(hlsl,source,error)) {
        Smash360_Log("Fast3D shader generation/lowering failed: %s",error.c_str());
        delete shader; return NULL;
    }""")
    text = text.replace("shaders[std::make_pair(id0,id1)]", "shaders[key]")
    text = replace_once(text, '    const double compileStart=Smash360_Time();', '')
    text = replace_once(text, '    const double elapsed=Smash360_Time()-compileStart;', '')
    text = replace_once(text, '    if(elapsed>=.008) Smash360_Log("HITCH shader=%016I64x/%08x compile_create_ms=%.3f",id0,id1,elapsed*1000);', '')
    text = replace_once(text, "ShaderProgram* Lookup(uint64_t id0, uint32_t id1)", "ShaderProgram* Lookup(const ShaderProgramKey& key)")
    text = text.replace("shaders.find(std::make_pair(id0,id1))", "shaders.find(key)")
    # All six texture bindings own resources and sampler state. Position/UV and
    # three-point parameter layout still uses the authoritative two base tiles.
    text = replace_once(text,"uint32_t selected[2];","uint32_t selected[6];")
    text = replace_once(text,"int selected_fb[2] = {-1, -1};","int selected_fb[6] = {-1,-1,-1,-1,-1,-1};")
    text = text.replace("DWORD sampler[2][5]", "DWORD sampler[6][5]").replace("bool sampler_valid[2]", "bool sampler_valid[6]").replace("unsigned sampler_key[2]", "unsigned sampler_key[6]")
    text = replace_once(text,"native_state.sampler_valid[0]=native_state.sampler_valid[1]=false;","for(int i=0;i<6;++i)native_state.sampler_valid[i]=false;")
    # Current Fast3D adds six texture-size registers at c8..c13. They need the
    # same exact-value reuse and external-state invalidation as donor c0..c2.
    text = replace_once(text,"    __declspec(align(16)) float constants[12];",
        "    __declspec(align(16)) float constants[12];\n    __declspec(align(16)) float binding_constants[24];\n    bool binding_constants_valid;")
    text = replace_once(text,"    native_state.constants_valid=false;native_state.alpha_valid=false;",
        "    native_state.constants_valid=false;native_state.alpha_valid=false;\n    native_state.binding_constants_valid=false;")
    text = replace_once(text,"template<int tile> void ApplySamplerSlot",
        'void SetNativeBindingConstants(const float* values) { Shipyard_Check(xenos_device->SetPixelShaderConstantF(8,values,6),"binding constants"); }\n\ntemplate<int tile> void ApplySamplerSlot')
    text = replace_once(text,"    if(tile==0)return smash_device->SetTexture(0,texture);\n    return smash_device->SetTexture(1,texture);", "    return smash_device->SetTexture(tile,texture);")
    text = replace_once(text,"    if(tile==0)ApplySamplerSlot<0>(sampler);else ApplySamplerSlot<1>(sampler);", """    switch(tile) {
    case 0:ApplySamplerSlot<0>(sampler);break;case 1:ApplySamplerSlot<1>(sampler);break;
    case 2:ApplySamplerSlot<2>(sampler);break;case 3:ApplySamplerSlot<3>(sampler);break;
    case 4:ApplySamplerSlot<4>(sampler);break;case 5:ApplySamplerSlot<5>(sampler);break;
    default:Smash360_Fatal("texture sampler index",E_INVALIDARG);
    }""")
    text = text.replace("tile > 1", "tile > 5")
    text = text.replace("for (int i=0;i<2;++i) if (selected_fb[i]", "for (int i=0;i<6;++i) if (selected_fb[i]")
    text = text.replace("for(int i=0;i<2;++i)if(selected_fb[i]", "for(int i=0;i<6;++i)if(selected_fb[i]")
    text = replace_once(text,"void RebindSampledTextures() {\n    for (int i=0;i<2;++i)","void RebindSampledTextures() {\n    for (int i=0;i<6;++i)")
    text = text.replace("SetNativeTexture(0,NULL);SetNativeTexture(1,NULL);", "for(int binding=0;binding<6;++binding)SetNativeTexture(binding,NULL);")
    text = replace_once(text,"void Depth(bool test,bool write) { smash_device->SetRenderState(D3DRS_ZENABLE,test); smash_device->SetRenderState(D3DRS_ZWRITEENABLE,write); smash_device->SetRenderState(D3DRS_ZFUNC,D3DCMP_LESSEQUAL); }", "void Depth(bool test,bool write) { smash_device->SetRenderState(D3DRS_ZENABLE,test||write); smash_device->SetRenderState(D3DRS_ZWRITEENABLE,write); smash_device->SetRenderState(D3DRS_ZFUNC,test?D3DCMP_LESSEQUAL:D3DCMP_ALWAYS); }")
    text = replace_once(text,"    SetNativeConstants(constants);\n    ApplyAlpha();", """    SetNativeConstants(constants);
    __declspec(align(16)) float binding_info[24]={0};
    for(int binding=0;binding<6;++binding) {
        if(selected_fb[binding]>=0) {const Framebuffer& b=buffers[selected_fb[binding]];binding_info[binding*4]=b.shader_width;binding_info[binding*4+1]=b.shader_height;}
        else if(selected[binding]<textures.size()) {const Texture& t=textures[selected[binding]];binding_info[binding*4]=t.shader_width;binding_info[binding*4+1]=t.shader_height;}
        if(binding>=2) {
            const int base=binding%2;
            if(selected_fb[base]>=0)ApplySampler(binding,buffers[selected_fb[base]].sampler);
            else if(selected[base]<textures.size())ApplySampler(binding,textures[selected[base]].sampler);
        }
    }
    SetNativeBindingConstants(binding_info);
    ApplyAlpha();""")
    text = replace_once(text, "void Clear() {\n    if(!live_framebuffer) {buffers[active_fb].stored=false;buffers[active_fb].depth_stored=false;}\n    BeginFramebuffer();\n    ClearFramebufferTargets(D3DCLEAR_TARGET|(buffers[active_fb].depth?D3DCLEAR_ZBUFFER|D3DCLEAR_STENCIL:0));\n    buffers[active_fb].dirty=true;\n}", """void Clear(bool color,bool depth) {
    if(!color && !depth)return;
    ++framebuffer_clear_count;
    if(!live_framebuffer && !framebuffer_clear_reuse_disabled) {
        Framebuffer& b=buffers[active_fb];
        // SoH's discard-before-full-clear optimization, preserving current
        // Fast3D's independent attachment contract. Color-only clears must
        // still restore depth. Depth-only clears retain every color sample.
        if(depth) {
            if(b.stored && b.depth_stored)framebuffer_depth_restore_avoided+=b.samples;
            b.depth_stored=false;
        }
        if(color && (depth || !b.depth)) {
            if(b.stored)framebuffer_restore_avoided+=b.samples;
            b.stored=false;
        }
    }
    BeginFramebuffer();
    const DWORD flags=(color?D3DCLEAR_TARGET:0)|((depth&&buffers[active_fb].depth)?D3DCLEAR_ZBUFFER|D3DCLEAR_STENCIL:0);
    if(flags)ClearFramebufferTargets(flags);
    buffers[active_fb].dirty=true;
}""")
    text = replace_once(text,"pp.PresentationInterval=Smash360_HeadroomEnabled()?D3DPRESENT_INTERVAL_IMMEDIATE:D3DPRESENT_INTERVAL_ONE;", "pp.PresentationInterval=D3DPRESENT_INTERVAL_ONE;")
    # XDK XShow UI requires a live D3D device and continuing presentation before
    # storage/config loading. Split creation only; normal Fast3D Init still owns
    # surface capture, restore shaders, state defaults and framebuffer setup.
    display_begin=text.index('    IDirect3D9* d3d=Direct3DCreate9(D3D_SDK_VERSION);')
    display_end=text.index('    Smash360_Check(smash_device->GetRenderTarget(0,&presentation_color)',display_begin)
    display_creation=text[display_begin:display_end]
    display_creation=replace_once(display_creation,
        '    IDirect3D9* d3d=Direct3DCreate9(D3D_SDK_VERSION);',
        '    IDirect3D9* d3d=Direct3DCreate9(D3D_SDK_VERSION);\n    if(!d3d)Smash360_Fatal("Direct3DCreate9",E_FAIL);')
    text=text[:display_begin]+'    InitializeDisplay();\n'+text[display_end:]
    text=replace_once(text,'void Init() {',
        'void InitializeDisplay() {\n    if(smash_device)return;\n'+display_creation+
        '    Smash360_Log("Xenos native display ready before system UI");\n}\nvoid Init() {')
    text = replace_once(text,"    Smash360_ReserveAssetMemory((uint64_t)XGNextMultiple(width,32)*XGNextMultiple(height,32)*4*\n        ((retain_color?0:1+(samples>1?samples:0))+(depth?samples:0)));", "    // No SoH asset cache exists here; XDK allocation failure remains fatal.")
    return text
