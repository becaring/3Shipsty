#include "fast/interpreter.h"
#include <cstdio>
#include <cstdlib>

using namespace Fast;

struct TestBackend {
    GfxClipParameters clip;
    GfxClipParameters GetClipParameters() const { return clip; }
};

struct TestOwner {
    RDP rdp;
    RSP rsp;
    RenderingState rendering;
    TestBackend backend;
    RDP* mRdp;
    RSP* mRsp;
    RenderingState& mRenderingState;
    TestBackend* mRapi;
    TestOwner() : rdp(), rsp(), rendering(), backend(), mRdp(&rdp), mRsp(&rsp),
                  mRenderingState(rendering), mRapi(&backend) {
        backend.clip.z_is_from_0_to_1 = true;
        backend.clip.invertY = false;
    }
};

static void require(bool ok, const char* message) {
    if (!ok) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}

int main() {
    TestOwner owner;
    ColorCombiner comb = {};
    comb.usedTextures[0] = true;
    comb.usedTextures[1] = false;
    XboxTrianglePipelineResult result = {};
    result.comb = &comb;
    XboxTrianglePipelineKey key;
    key.Capture(owner, result);
    require(key.Matches(owner), "unchanged modern state did not certify");
#define CHANGE(field, value) { auto prior=(field); (field)=(value); require(!key.Matches(owner), #field " missed"); (field)=prior; require(key.Matches(owner), #field " restore missed"); }
    for (unsigned bit=0; bit<64; ++bit) CHANGE(owner.rdp.combine_mode, uint64_t(1)<<bit);
    for (unsigned bit=0; bit<32; ++bit) {
        CHANGE(owner.rdp.other_mode_l, uint32_t(1)<<bit);
        CHANGE(owner.rdp.other_mode_h, uint32_t(1)<<bit);
    }
    CHANGE(owner.rdp.loaded_texture[0].size_bytes, 37u);
    CHANGE(owner.rdp.loaded_texture[0].line_size_bytes, 5u);
    CHANGE(owner.rdp.loaded_texture[0].full_image_line_size_bytes, 7u);
    CHANGE(owner.rdp.loaded_texture[0].orig_size_bytes, 39u);
    unsigned char* tile = reinterpret_cast<unsigned char*>(&owner.rdp.texture_tile[0]);
    for (unsigned i=0; i<sizeof(owner.rdp.texture_tile[0]); ++i) {
        tile[i]^=1;
        require(!key.Matches(owner), "modern active tile byte missed");
        tile[i]^=1;
    }
    unsigned char* rendering = reinterpret_cast<unsigned char*>(&owner.rendering);
    for (unsigned i=0; i<sizeof(owner.rendering); ++i) {
        rendering[i]^=1;
        require(!key.Matches(owner), "modern rendering-state byte missed");
        rendering[i]^=1;
    }
    owner.rdp.current_shader.enabled = true;
    require(!key.Matches(owner), "modern shader enable missed");
    key.Capture(owner, result);
    require(key.Matches(owner), "enabled modern shader did not certify");
    owner.rdp.current_shader.id = 13;
    require(!key.Matches(owner), "modern shader id missed");
    owner.rdp.current_shader.id = 0;
    owner.rdp.current_shader.type = 2;
    require(!key.Matches(owner), "modern shader type missed");
    owner.rdp.current_shader.type = 0;
    owner.backend.clip.invertY = true;
    require(!key.Matches(owner), "modern backend clip missed");
    owner.backend.clip.invertY = false;
    owner.rdp.textures_changed[0] = true;
    require(!key.Matches(owner), "used dirty texture reused");
    owner.rdp.textures_changed[0] = false;
    owner.rdp.textures_changed[1] = true;
    require(key.Matches(owner), "unused dirty texture blocked reuse");
    comb.usedTextures[0] = false;
    comb.usedTextures[1] = true;
    owner.rdp.textures_changed[1] = false;
    owner.rdp.first_tile_index = 2;
    key.Capture(owner, result);
    require(key.Matches(owner), "modern tile index did not certify");
    owner.rdp.texture_tile[3].uls = 1.0f;
    require(!key.Matches(owner), "modern second tile not tracked");
    owner.rdp.texture_tile[3].uls = 0.0f;
    owner.rdp.texture_tile[2].uls = 1.0f;
    require(key.Matches(owner), "modern unused first tile affected second slot");
    owner.rdp.texture_tile[2].uls = 0.0f;
    owner.rdp.first_tile_index = 7;
    key.Capture(owner, result);
    require(!key.valid, "out-of-range modern tile certified");
    std::puts("PASS modern triangle certificate trait/key mutations");
}
