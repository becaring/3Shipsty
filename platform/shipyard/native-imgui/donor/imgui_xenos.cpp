#include "platform.h"
#include "imgui_xenos.h"
#include "fast3d_float.h"
#include <d3dx9.h>
#include <stddef.h>

namespace {
IDirect3DVertexShader9* vertex_shader;
IDirect3DPixelShader9* pixel_shader;
IDirect3DVertexDeclaration9* vertex_declaration;
IDirect3DStateBlock9* saved_state;
ImTextureID font_texture;
struct Vertex { float x,y,u,v,r,g,b,a; };
std::vector<Vertex> vertices;
ID3DXBuffer* Compile(const char* source, const char* entry, const char* profile) {
    ID3DXBuffer* code = NULL; ID3DXBuffer* errors = NULL;
    HRESULT result = D3DXCompileShader(source, (UINT)strlen(source), NULL, NULL, entry, profile, 0, &code, &errors, NULL);
    if (errors) { SoH_Log("ImGui shader: %s", (const char*)errors->GetBufferPointer()); errors->Release(); }
    SoH_Check(result, "ImGui shader compile"); return code;
}
void Setup(const ImDrawData* data) {
    SoH_InvalidateNativeState();
    D3DVIEWPORT9 viewport = {0,0,(DWORD)(data->DisplaySize.x*data->FramebufferScale.x),(DWORD)(data->DisplaySize.y*data->FramebufferScale.y),0,1};
    soh_device->SetViewport(&viewport);
    soh_device->SetRenderState(D3DRS_VIEWPORTENABLE,TRUE);
    soh_device->SetRenderState(D3DRS_HALFPIXELOFFSET,TRUE);
    soh_device->SetVertexDeclaration(vertex_declaration);
    soh_device->SetVertexShader(vertex_shader); soh_device->SetPixelShader(pixel_shader);
    float transform[4] = {2.0f/data->DisplaySize.x, -2.0f/data->DisplaySize.y,
        -1.0f-2.0f*data->DisplayPos.x/data->DisplaySize.x,
        1.0f+2.0f*data->DisplayPos.y/data->DisplaySize.y};
    // As with framebuffer restores, Xenos applies the half-pixel adjustment.
    // The desktop D3D9 translation would offset glyphs and the game image twice.
    soh_device->SetVertexShaderConstantF(0,transform,1);
    soh_device->SetRenderState(D3DRS_ZENABLE,FALSE);
    soh_device->SetRenderState(D3DRS_ZWRITEENABLE,FALSE);
    soh_device->SetRenderState(D3DRS_ALPHATESTENABLE,FALSE);
    soh_device->SetRenderState(D3DRS_ALPHABLENDENABLE,TRUE);
    soh_device->SetRenderState(D3DRS_SRCBLEND,D3DBLEND_SRCALPHA);
    soh_device->SetRenderState(D3DRS_DESTBLEND,D3DBLEND_INVSRCALPHA);
    soh_device->SetRenderState(D3DRS_BLENDOP,D3DBLENDOP_ADD);
    soh_device->SetRenderState(D3DRS_SEPARATEALPHABLENDENABLE,TRUE);
    soh_device->SetRenderState(D3DRS_SRCBLENDALPHA,D3DBLEND_ONE);
    soh_device->SetRenderState(D3DRS_DESTBLENDALPHA,D3DBLEND_INVSRCALPHA);
    soh_device->SetRenderState(D3DRS_BLENDOPALPHA,D3DBLENDOP_ADD);
    soh_device->SetRenderState(D3DRS_CULLMODE,D3DCULL_NONE);
    soh_device->SetRenderState(D3DRS_FILLMODE,D3DFILL_SOLID);
    soh_device->SetRenderState(D3DRS_SCISSORTESTENABLE,TRUE);
    soh_device->SetRenderState(D3DRS_STENCILENABLE,FALSE);
    soh_device->SetRenderState(D3DRS_COLORWRITEENABLE,15);
    // Xenos gamma conversion is selected by the surface/texture format. These
    // UI resources use linear A8R8G8B8, so there is no desktop sRGB state here.
    soh_device->SetSamplerState(0,D3DSAMP_MINFILTER,D3DTEXF_LINEAR);
    soh_device->SetSamplerState(0,D3DSAMP_MAGFILTER,D3DTEXF_LINEAR);
    soh_device->SetSamplerState(0,D3DSAMP_MIPFILTER,D3DTEXF_NONE);
    soh_device->SetSamplerState(0,D3DSAMP_ADDRESSU,D3DTADDRESS_CLAMP);
    soh_device->SetSamplerState(0,D3DSAMP_ADDRESSV,D3DTADDRESS_CLAMP);
    SoH_InvalidateNativeState();
}
}
ImTextureID SoH_ImGuiUploadRGBA(const unsigned char* pixels,int width,int height) {
    if (!pixels || width<=0 || height<=0 || width>4096 || height>4096) SoH_Fatal("ImGui texture dimensions",E_INVALIDARG);
    IDirect3DTexture9* texture = NULL;
    SoH_Check(soh_device->CreateTexture(width,height,1,0,D3DFMT_LIN_A8R8G8B8,D3DPOOL_DEFAULT,&texture,NULL),"ImGui texture");
    D3DLOCKED_RECT lock; SoH_Check(texture->LockRect(0,&lock,NULL,0),"ImGui texture upload");
    for (int y=0;y<height;++y) {
        DWORD* row=(DWORD*)((BYTE*)lock.pBits+y*lock.Pitch);
        for (int x=0;x<width;++x) {
            const unsigned char* p=pixels+(y*width+x)*4;
            row[x]=((DWORD)p[3]<<24)|((DWORD)p[0]<<16)|((DWORD)p[1]<<8)|p[2];
        }
    }
    texture->UnlockRect(0); return (ImTextureID)texture;
}
void SoH_ImGuiDestroyTexture(ImTextureID texture) { if (texture) ((IDirect3DTexture9*)texture)->Release(); }
void SoH_ImGuiRendererInit() {
    SoH_InvalidateNativeState();
    static const char* source =
        "float4 transform : register(c0);\n"
        "struct VertexIn {float2 position:POSITION;float2 uv:TEXCOORD0;float4 color:COLOR0;};\n"
        "struct VertexOut {float4 position:POSITION;float2 uv:TEXCOORD0;float4 color:COLOR0;};\n"
        "VertexOut VSMain(VertexIn v){VertexOut o;o.position=float4(v.position*transform.xy+transform.zw,0,1);o.uv=v.uv;o.color=v.color;return o;}\n"
        "sampler2D image:register(s0);\n"
        "float4 PSMain(VertexOut v):COLOR0{return tex2D(image,v.uv)*v.color;}\n";
    ID3DXBuffer* code=Compile(source,"VSMain","vs_3_0");
    SoH_Check(soh_device->CreateVertexShader((DWORD*)code->GetBufferPointer(),&vertex_shader),"ImGui vertex shader");code->Release();
    code=Compile(source,"PSMain","ps_3_0");
    SoH_Check(soh_device->CreatePixelShader((DWORD*)code->GetBufferPointer(),&pixel_shader),"ImGui pixel shader");code->Release();
    D3DVERTEXELEMENT9 declaration[]={
        {0,0,D3DDECLTYPE_FLOAT2,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_POSITION,0},
        {0,8,D3DDECLTYPE_FLOAT2,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_TEXCOORD,0},
        {0,16,D3DDECLTYPE_FLOAT4,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_COLOR,0},D3DDECL_END()};
    SoH_Check(soh_device->CreateVertexDeclaration(declaration,&vertex_declaration),"ImGui vertex declaration");
    SoH_Check(soh_device->CreateStateBlock(D3DSBT_ALL,&saved_state),"ImGui state preservation");
    ImGuiIO& io=ImGui::GetIO();unsigned char* pixels;int width,height;
    io.Fonts->GetTexDataAsRGBA32(&pixels,&width,&height);
    // The atlas stores native ImU32/IM_COL32 values. Image decoders supply
    // RGBA bytes; those representations differ on big-endian PowerPC.
    std::vector<unsigned char> rgba((size_t)width*height*4);
    const ImU32* packed=(const ImU32*)pixels;
    for(size_t i=0;i<(size_t)width*height;++i) {
        rgba[i*4+0]=(unsigned char)(packed[i]>>IM_COL32_R_SHIFT);
        rgba[i*4+1]=(unsigned char)(packed[i]>>IM_COL32_G_SHIFT);
        rgba[i*4+2]=(unsigned char)(packed[i]>>IM_COL32_B_SHIFT);
        rgba[i*4+3]=(unsigned char)(packed[i]>>IM_COL32_A_SHIFT);
    }
    font_texture=SoH_ImGuiUploadRGBA(&rgba[0],width,height);io.Fonts->SetTexID(font_texture);
    io.BackendRendererName="SoH360_Xenos";
    io.BackendFlags|=ImGuiBackendFlags_RendererHasVtxOffset;
}
void SoH_ImGuiRender(ImDrawData* data) {
    if (!data || data->DisplaySize.x<=0 || data->DisplaySize.y<=0 || !data->TotalVtxCount) return;
    SoH_BeginNativeDraw();
    saved_state->Capture(); Setup(data);
    for (int listIndex=0;listIndex<data->CmdListsCount;++listIndex) {
        const ImDrawList* list=data->CmdLists[listIndex];vertices.resize(list->VtxBuffer.Size);
        for (int i=0;i<list->VtxBuffer.Size;++i) {
            const ImDrawVert& v=list->VtxBuffer[i]; Vertex& out=vertices[i];
            out.x=v.pos.x;out.y=v.pos.y;out.u=v.uv.x;out.v=v.uv.y;
            out.r=SoH_FloatUnitU8((uint8_t)(v.col>>IM_COL32_R_SHIFT));out.g=SoH_FloatUnitU8((uint8_t)(v.col>>IM_COL32_G_SHIFT));
            out.b=SoH_FloatUnitU8((uint8_t)(v.col>>IM_COL32_B_SHIFT));out.a=SoH_FloatUnitU8((uint8_t)(v.col>>IM_COL32_A_SHIFT));
        }
        for (int i=0;i<list->CmdBuffer.Size;++i) {
            const ImDrawCmd& cmd=list->CmdBuffer[i];
            if (cmd.UserCallback) {
                SoH_InvalidateNativeState();
                if (cmd.UserCallback==ImDrawCallback_ResetRenderState) Setup(data);
                else cmd.UserCallback(list,&cmd);
                SoH_InvalidateNativeState();
                continue;
            }
            ImVec2 min((cmd.ClipRect.x-data->DisplayPos.x)*data->FramebufferScale.x,(cmd.ClipRect.y-data->DisplayPos.y)*data->FramebufferScale.y);
            ImVec2 max((cmd.ClipRect.z-data->DisplayPos.x)*data->FramebufferScale.x,(cmd.ClipRect.w-data->DisplayPos.y)*data->FramebufferScale.y);
            if (min.x<0)min.x=0;if(min.y<0)min.y=0;
            float width=data->DisplaySize.x*data->FramebufferScale.x,height=data->DisplaySize.y*data->FramebufferScale.y;
            if(max.x>width)max.x=width;if(max.y>height)max.y=height;
            if(max.x<=min.x || max.y<=min.y || !cmd.ElemCount)continue;
            if(cmd.IdxOffset+cmd.ElemCount>(unsigned)list->IdxBuffer.Size || cmd.VtxOffset>=vertices.size())
                SoH_Fatal("ImGui draw bounds",E_FAIL);
            RECT scissor={(LONG)min.x,(LONG)min.y,(LONG)max.x,(LONG)max.y};soh_device->SetScissorRect(&scissor);
            soh_device->SetTexture(0,(IDirect3DTexture9*)cmd.GetTexID());
            SoH_InvalidateNativeState();
            soh_device->DrawIndexedPrimitiveUP(D3DPT_TRIANGLELIST,0,(UINT)vertices.size()-cmd.VtxOffset,
                cmd.ElemCount/3,list->IdxBuffer.Data+cmd.IdxOffset,sizeof(ImDrawIdx)==2?D3DFMT_INDEX16:D3DFMT_INDEX32,
                &vertices[cmd.VtxOffset],sizeof(Vertex));
        }
    }
    saved_state->Apply();
    SoH_InvalidateNativeState();
}
void SoH_ImGuiRendererShutdown() {
    SoH_InvalidateNativeState();
    if (ImGui::GetCurrentContext()) {ImGui::GetIO().Fonts->SetTexID(NULL);ImGui::GetIO().BackendRendererName=NULL;}
    SoH_ImGuiDestroyTexture(font_texture);font_texture=NULL;
    if(saved_state){saved_state->Release();saved_state=NULL;}
    if(vertex_declaration){vertex_declaration->Release();vertex_declaration=NULL;}
    if(vertex_shader){vertex_shader->Release();vertex_shader=NULL;}
    if(pixel_shader){pixel_shader->Release();pixel_shader=NULL;}
    std::vector<Vertex>().swap(vertices);
}
