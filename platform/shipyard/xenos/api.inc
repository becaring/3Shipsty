// Genuine current virtual interface. Helpers above own only native mechanics.
extern "C" void gfx_texture_cache_clear();
static bool shaderSrgb=false;
static ShaderProgramKey CurrentKey(uint64_t a,uint32_t b){ShaderProgramKey k={a,b,filtering,shaderSrgb};return k;}
static ShaderProgram* CurrentVariant(ShaderProgram* p){
    if(!p)return NULL;
    ShaderProgramKey key=CurrentKey(p->key.shaderId0,p->key.shaderId1);
    ShaderProgram* found=Lookup(key);return found?found:CreateShader(key);
}
void InitializeNativeDisplay(){InitializeDisplay();}
HRESULT PresentNativeStartupUI(){
    // XAM owns the overlay; Fast3D framebuffers are not initialized yet.
    if(!xenos_device || !buffers.empty())return E_UNEXPECTED;
    HRESULT result=xenos_device->Clear(0,NULL,D3DCLEAR_TARGET|D3DCLEAR_ZBUFFER|D3DCLEAR_STENCIL,0xff000000,1,0);
    if(FAILED(result))return result;
    return xenos_device->Present(NULL,NULL,NULL,NULL);
}
void BeginNativeGuiDraw(){BeginFramebuffer();}
void InvalidateNativeGuiState(){InvalidateNativeState();}
void ShutdownNativeDisplay(){Shipyard_ShutdownGraphics();}
GfxRenderingAPIXenos::~GfxRenderingAPIXenos(){Shipyard_ShutdownGraphics();}
const char* GfxRenderingAPIXenos::GetName(){return "Xenos";}
int GfxRenderingAPIXenos::GetMaxTextureSize(){return 4096;}
GfxClipParameters GfxRenderingAPIXenos::GetClipParameters(){return ClipParameters();}
void GfxRenderingAPIXenos::UnloadShader(ShaderProgram* p){::Fast::UnloadShader(p);}
void GfxRenderingAPIXenos::LoadShader(ShaderProgram* p){::Fast::LoadShader(CurrentVariant(p));}
ShaderProgram* GfxRenderingAPIXenos::CreateAndLoadNewShader(uint64_t a,uint32_t b){return CreateShader(CurrentKey(a,b));}
ShaderProgram* GfxRenderingAPIXenos::LookupShader(uint64_t a,uint32_t b){return Lookup(CurrentKey(a,b));}
void GfxRenderingAPIXenos::ShaderGetInfo(ShaderProgram* p,uint8_t* n,bool used[2]){ShaderInfo(p,n,used);}
uint32_t GfxRenderingAPIXenos::NewTexture(){return ::Fast::NewTexture();}
void GfxRenderingAPIXenos::SelectTexture(int slot,uint32_t id){::Fast::SelectTexture(slot,id);}
void GfxRenderingAPIXenos::UploadTexture(const uint8_t* p,uint32_t w,uint32_t h){Upload(p,w,h);}
void GfxRenderingAPIXenos::SetSamplerParameters(int slot,bool linear,uint32_t s,uint32_t t){Sampler(slot,linear,s,t);}
void GfxRenderingAPIXenos::SetDepthTestAndMask(bool test,bool write){Depth(test,write);}
void GfxRenderingAPIXenos::SetZmodeDecal(bool decal){Decal(decal);}
void GfxRenderingAPIXenos::SetViewport(int x,int y,int w,int h){Viewport(x,y,w,h);}
void GfxRenderingAPIXenos::SetScissor(int x,int y,int w,int h){Scissor(x,y,w,h);}
void GfxRenderingAPIXenos::SetUseAlpha(bool alpha){Alpha(alpha);}
void GfxRenderingAPIXenos::DrawTriangles(float v[],size_t count,size_t tris){Draw(v,count,tris);}
void InitializeGuiForXenos();
void GfxRenderingAPIXenos::Init(){::Fast::Init();InitializeGuiForXenos();}
void GfxRenderingAPIXenos::OnResize(){Resize();}
void GfxRenderingAPIXenos::StartFrame(){Start();}
void GfxRenderingAPIXenos::EndFrame(){End();}
void GfxRenderingAPIXenos::FinishRender(){Finish();}
int GfxRenderingAPIXenos::CreateFramebuffer(){return NewFramebuffer();}
void GfxRenderingAPIXenos::UpdateFramebufferParameters(int id,uint32_t w,uint32_t h,uint32_t msaa,bool flip,bool target,bool depth,bool read){UpdateFramebuffer(id,w,h,msaa,flip,target,depth,read);}
void GfxRenderingAPIXenos::StartDrawToFramebuffer(int id,float noise){BindFramebuffer(id,noise);}
void GfxRenderingAPIXenos::CopyFramebuffer(int dst,int src,int sx0,int sy0,int sx1,int sy1,int dx0,int dy0,int dx1,int dy1){CopyRegion(dst,src,sx0,sy0,sx1,sy1,dx0,dy0,dx1,dy1);}
void GfxRenderingAPIXenos::ClearFramebuffer(bool color,bool depth){Clear(color,depth);}
void GfxRenderingAPIXenos::ReadFramebufferToCPU(int id,uint32_t w,uint32_t h,uint16_t* p){ReadColor(id,w,h,p);}
void GfxRenderingAPIXenos::ResolveMSAAColorBuffer(int dst,int src){ResolveMSAA(dst,src);}
std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff> GfxRenderingAPIXenos::GetPixelDepth(int id,const std::set<std::pair<float,float> >& xy){return PixelDepth(id,xy);}
void* GfxRenderingAPIXenos::GetFramebufferTextureId(int id){return FramebufferImage(id);}
void GfxRenderingAPIXenos::SelectTextureFb(int id){SelectFramebuffer(id);}
void GfxRenderingAPIXenos::DeleteTexture(uint32_t id){::Fast::DeleteTexture(id);}
void GfxRenderingAPIXenos::SetTextureFilter(FilteringMode mode){Filter(mode);gfx_texture_cache_clear();if(current_shader)LoadShader(current_shader);}
FilteringMode GfxRenderingAPIXenos::GetTextureFilter(){return GetFilter();}
void GfxRenderingAPIXenos::SetSrgbMode(){mSrgbMode=true;shaderSrgb=true;if(current_shader)LoadShader(current_shader);}
ImTextureID GfxRenderingAPIXenos::GetTextureById(int id){
    if(id<0 || (size_t)id>=textures.size())Shipyard_Fatal("GUI texture index",E_INVALIDARG);
    return textures[id].native;
}
