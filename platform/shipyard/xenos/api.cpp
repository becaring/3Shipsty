#include "xenos_backend.h"
#include "xenos/core.h"
#include "xenos/shader_variant.h"
#include "native_display.h"
#include "services.h"
#include "xenos/shader_cache.h"
#include "io/shader_worker.h"

namespace Fast {
namespace {
bool shaderSrgb=false;
ShaderProgramKey CurrentKey(uint64_t first,uint32_t second) {
    ShaderProgramKey key={first,second,ShipyardXenos::GetTextureFilter(),shaderSrgb};
    return key;
}
ShaderProgram* CurrentVariant(ShaderProgram* program) {
    if(!program)return NULL;
    const ShaderProgramKey original=ShipyardXenos::ShaderKey(program);
    const ShaderProgramKey key=CurrentKey(original.shaderId0,original.shaderId1);
    return Shipyard::Xenos::ResolveShaderVariant(program,original,key,
        ShipyardXenos::LookupShader,ShipyardXenos::CreateShader);
}
}
void InitializeNativeDisplay(){ShipyardXenos::InitializeDisplay();}
HRESULT PresentNativeStartupUI(){return ShipyardXenos::PresentStartupUI();}
void BeginNativeGuiDraw(){ShipyardXenos::BeginGuiDraw();}
void InvalidateNativeGuiState(){ShipyardXenos::InvalidateGuiState();}
void ShutdownNativeDisplay(){Shipyard::IO::ShutdownShaderWrites();ShipyardXenos::Shutdown();}
GfxRenderingAPIXenos::~GfxRenderingAPIXenos(){ShutdownNativeDisplay();}
const char* GfxRenderingAPIXenos::GetName(){return "Xenos";}
int GfxRenderingAPIXenos::GetMaxTextureSize(){return 4096;}
GfxClipParameters GfxRenderingAPIXenos::GetClipParameters(){return ShipyardXenos::ClipParameters();}
void GfxRenderingAPIXenos::UnloadShader(ShaderProgram* p){ShipyardXenos::UnloadShader(p);}
void GfxRenderingAPIXenos::LoadShader(ShaderProgram* p){ShipyardXenos::LoadShader(CurrentVariant(p));}
ShaderProgram* GfxRenderingAPIXenos::CreateAndLoadNewShader(uint64_t a,uint32_t b){return ShipyardXenos::CreateShader(CurrentKey(a,b));}
ShaderProgram* GfxRenderingAPIXenos::LookupShader(uint64_t a,uint32_t b){return ShipyardXenos::LookupShader(CurrentKey(a,b));}
void GfxRenderingAPIXenos::ShaderGetInfo(ShaderProgram* p,uint8_t* n,bool used[2]){ShipyardXenos::ShaderInfo(p,n,used);}
uint32_t GfxRenderingAPIXenos::NewTexture(){return ShipyardXenos::NewTexture();}
void GfxRenderingAPIXenos::SelectTexture(int slot,uint32_t id){ShipyardXenos::SelectTexture(slot,id);}
void GfxRenderingAPIXenos::UploadTexture(const uint8_t* p,uint32_t w,uint32_t h){ShipyardXenos::UploadTexture(p,w,h);}
void GfxRenderingAPIXenos::SetSamplerParameters(int slot,bool linear,uint32_t s,uint32_t t){ShipyardXenos::SetSamplerParameters(slot,linear,s,t);}
void GfxRenderingAPIXenos::SetDepthTestAndMask(bool test,bool write){ShipyardXenos::SetDepthTestAndMask(test,write);}
void GfxRenderingAPIXenos::SetZmodeDecal(bool decal){ShipyardXenos::SetZmodeDecal(decal);}
void GfxRenderingAPIXenos::SetViewport(int x,int y,int w,int h){ShipyardXenos::SetViewport(x,y,w,h);}
void GfxRenderingAPIXenos::SetScissor(int x,int y,int w,int h){ShipyardXenos::SetScissor(x,y,w,h);}
void GfxRenderingAPIXenos::SetUseAlpha(bool alpha){ShipyardXenos::SetUseAlpha(alpha);}
void GfxRenderingAPIXenos::DrawTriangles(float v[],size_t count,size_t tris){ShipyardXenos::DrawTriangles(v,count,tris);}
void InitializeGuiForXenos();
void GfxRenderingAPIXenos::Init(){
    const Shipyard::IO::ShaderWorkerConfig worker={"shader-cache",3,
        Shipyard::Xenos::WriteShaderCacheRecord,Shipyard_Log,Shipyard_Fatal};
    if(!Shipyard::IO::ConfigureShaderWorker(&worker))
        Shipyard_Fatal("shader worker configuration",E_UNEXPECTED);
    // Offline-compiled shaders (tools/shipyard/build_shader_pack.py); combinations
    // it lacks compile once and persist in the appendable cache below.
    Shipyard::Xenos::ConfigureShaderPack("game:\\shaders\\3shipsty.shaderpack");
    const Shipyard::Xenos::ShaderCacheConfig config={"game:\\config\\3shipsty-shaders.cache",2,
        Shipyard::IO::QueueShaderRecord};
    if(!Shipyard::Xenos::ConfigureShaderCache(config))
        Shipyard_Fatal("shader cache configuration",E_UNEXPECTED);
    const ShipyardXenos::ShaderCacheOps cache={Shipyard::Xenos::LoadShaderCode,
        Shipyard::Xenos::StoreShaderCode};
    ShipyardXenos::SetShaderCache(&cache);
    ShipyardXenos::Init();InitializeGuiForXenos();
}
void GfxRenderingAPIXenos::OnResize(){ShipyardXenos::Resize();}
void GfxRenderingAPIXenos::StartFrame(){Shipyard::IO::PollShaderWrites();ShipyardXenos::StartFrame();}
void GfxRenderingAPIXenos::EndFrame(){ShipyardXenos::EndFrame();}
void GfxRenderingAPIXenos::FinishRender(){ShipyardXenos::FinishRender();}
int GfxRenderingAPIXenos::CreateFramebuffer(){return ShipyardXenos::CreateFramebuffer();}
void GfxRenderingAPIXenos::UpdateFramebufferParameters(int id,uint32_t w,uint32_t h,uint32_t msaa,bool flip,bool target,bool depth,bool read){ShipyardXenos::UpdateFramebuffer(id,w,h,msaa,flip,target,depth,read);}
void GfxRenderingAPIXenos::StartDrawToFramebuffer(int id,float noise){ShipyardXenos::StartDrawToFramebuffer(id,noise);}
void GfxRenderingAPIXenos::CopyFramebuffer(int dst,int src,int sx0,int sy0,int sx1,int sy1,int dx0,int dy0,int dx1,int dy1){ShipyardXenos::CopyFramebuffer(dst,src,sx0,sy0,sx1,sy1,dx0,dy0,dx1,dy1);}
void GfxRenderingAPIXenos::ClearFramebuffer(bool color,bool depth){ShipyardXenos::ClearFramebuffer(color,depth);}
void GfxRenderingAPIXenos::ReadFramebufferToCPU(int id,uint32_t w,uint32_t h,uint16_t* p){ShipyardXenos::ReadFramebufferToCPU(id,w,h,p);}
void GfxRenderingAPIXenos::ResolveMSAAColorBuffer(int dst,int src){ShipyardXenos::ResolveMSAAColorBuffer(dst,src);}
std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff> GfxRenderingAPIXenos::GetPixelDepth(int id,const std::set<std::pair<float,float> >& xy){return ShipyardXenos::GetPixelDepth(id,xy);}
void* GfxRenderingAPIXenos::GetFramebufferTextureId(int id){return ShipyardXenos::GetFramebufferTextureId(id);}
void GfxRenderingAPIXenos::SelectTextureFb(int id){ShipyardXenos::SelectTextureFb(id);}
void GfxRenderingAPIXenos::DeleteTexture(uint32_t id){ShipyardXenos::DeleteTexture(id);}
extern "C" void gfx_texture_cache_clear();
void GfxRenderingAPIXenos::SetTextureFilter(FilteringMode mode){ShipyardXenos::SetTextureFilter(mode);gfx_texture_cache_clear();if(ShipyardXenos::CurrentShader())LoadShader(ShipyardXenos::CurrentShader());}
FilteringMode GfxRenderingAPIXenos::GetTextureFilter(){return ShipyardXenos::GetTextureFilter();}
void GfxRenderingAPIXenos::SetSrgbMode(){mSrgbMode=true;shaderSrgb=true;if(ShipyardXenos::CurrentShader())LoadShader(ShipyardXenos::CurrentShader());}
ImTextureID GfxRenderingAPIXenos::GetTextureById(int id){return ShipyardXenos::GetTextureById(id);}
}
