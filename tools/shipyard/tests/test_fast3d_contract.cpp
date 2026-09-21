#include "methods.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <limits>

static bool first(Fast::F3DGfx**) { return false; }
static bool last(Fast::F3DGfx**) { return true; }

int main() {
    Fast::Interpreter gfx;
    assert(gfx.mRsp && gfx.mRdp && gfx.mBufVbo);
    assert(gfx.mPrevCombiner==gfx.mColorCombinerPool.end());
    assert(gfx.mMsaaLevel==1 && !gfx.mTexUploadBuffer && !gfx.mWapi && !gfx.mRapi);
    assert(!gfx.mBufVboLen && !gfx.mBufVboNumTris && !gfx.mRendersToFb && !gfx.mFbActive);
    assert(!gfx.mRenderingState.mShaderProgram && !gfx.mRenderingState.alpha_blend);
    for (int i=0;i<SHADER_MAX_TEXTURES;++i) assert(!gfx.mRenderingState.mTextures[i]);
    for (int i=0;i<16;++i) assert(!gfx.mSegmentPointers[i]);
    for (int i=0;i<11;++i) for(int j=0;j<4;++j) for(int k=0;k<4;++k) assert(gfx.mRsp->modelview_matrix_stack[i][j][k]==0);
    assert(!gfx.mRsp->geometry_mode && !gfx.mRsp->modelview_matrix_stack_size && !gfx.mRsp->current_num_lights);
    assert(!gfx.mRsp->current_shader.enabled && !gfx.mRsp->current_shader.id && !gfx.mRsp->current_shader.type);
    assert(!gfx.mRdp->other_mode_l && !gfx.mRdp->other_mode_h && !gfx.mRdp->combine_mode);
    assert(!gfx.mRdp->texture_to_load.addr && !gfx.mRdp->texture_to_load.raw_tex_metadata.width);
    assert(gfx.mRdp->texture_to_load.raw_tex_metadata.h_byte_scale==1 && gfx.mRdp->texture_to_load.raw_tex_metadata.v_pixel_scale==1);
    for (int i=0;i<2;++i) {
        assert(!gfx.mRdp->loaded_texture[i].addr && !gfx.mRdp->loaded_texture[i].size_bytes);
        assert(!gfx.mRdp->loaded_texture[i].raw_tex_metadata.resource && !gfx.mRdp->loaded_texture[i].raw_tex_metadata.height);
        assert(gfx.mRdp->loaded_texture[i].raw_tex_metadata.type==Fast::TextureType::Error);
        assert(gfx.mRdp->loaded_texture[i].raw_tex_metadata.h_byte_scale==1 && gfx.mRdp->loaded_texture[i].raw_tex_metadata.v_pixel_scale==1);
        assert(!gfx.mRdp->textures_changed[i] && !gfx.mRdp->palettes[i]);
    }
    for (int i=0;i<8;++i) assert(!gfx.mRdp->texture_tile[i].fmt && !gfx.mRdp->texture_tile[i].uls && !gfx.mRdp->texture_tile[i].palette);
    ColorCombinerKey key={0,0}, other={0,1}; assert(key<other && !(other<key) && !(key==other));
    other.combine_mode=1;other.options=0;assert(key<other);
    Fast::TextureCacheKey tk={}; Fast::TextureCacheKey tk2=tk;
    assert(tk==tk2);
    uint8_t bytes[4]={};
#define DIFFERENT(member,value) tk2=tk; tk2.member=value; assert(!(tk==tk2))
    DIFFERENT(texture_addr,bytes);DIFFERENT(palette_addrs[0],bytes);DIFFERENT(palette_addrs[1],bytes);
    DIFFERENT(fmt,1);DIFFERENT(siz,1);DIFFERENT(palette_index,1);DIFFERENT(size_bytes,1);
#undef DIFFERENT
    Fast::GfxExecStack stack; Fast::F3DGfx commands[4]={};
    stack.start(commands);assert(stack.currCmd()==commands);
    stack.openDisp("test",42);assert(stack.getDisp().size()==1 && stack.getDisp()[0].line==42);
    stack.closeDisp();assert(stack.getDisp().empty());stack.stop();
#ifdef SHIPYARD_PROJECTED
    const Fast::UcodeEntry entries[]={{-1,"first",first},{0,"zero",first},{-1,"last",last}};
    Fast::UcodeHandler table(entries,3);
#else
    Fast::UcodeHandler table({{-1,{"first",first}},{0,{"zero",first}},{-1,{"last",last}}});
#endif
    for (int i=0;i<256;++i) assert(table.contains(static_cast<int8_t>(i))==(i==0 || i==255));
    assert(table.at(-1).second==last && std::strcmp(table.at(-1).first,"last")==0);
    assert(table.at(1).first==nullptr && table.at(1).second==nullptr);
    for (uint32_t w=0;w<1025;w+=7) for(uint32_t h=0;h<800;h+=13) {
        gfx.mCurDimensions.width=w;gfx.mCurDimensions.height=h;
        uint32_t width=317,height=239;
        gfx.AdjustWidthHeightForScale(width,height,320,240);
        uint32_t expectedW=static_cast<uint32_t>(std::round(317*(w/320.0f)));
        uint32_t expectedH=static_cast<uint32_t>(std::round(239*(h/240.0f)));
        assert(width==(expectedW?expectedW:1) && height==(expectedH?expectedH:1));
    }
    double samples[]={0.,-0.,.5,-.5,1.5,-1.5,.49999999999999994,-.49999999999999994,4503599627370495.5,
        std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()};
    for (int i=0;i<sizeof(samples)/sizeof(samples[0]);++i) {
        double got=Shipyard::Fast3D::Round(samples[i]),want=std::round(samples[i]);
        assert((std::isnan(got)&&std::isnan(want)) || (got==want && std::signbit(got)==std::signbit(want)));
    }
    float lo=-1,hi=1,zero=-0.0f,nan=std::numeric_limits<float>::quiet_NaN();
    assert(&Shipyard::Fast3D::Clamp(zero,lo,hi)==&zero);
    assert(&Shipyard::Fast3D::Clamp(nan,lo,hi)==&nan);
    std::puts("Fast3D state, cache keys, stack, opcode domain and scale/math contracts pass");
}
