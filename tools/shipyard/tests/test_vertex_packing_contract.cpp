#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "fast3d/unit_color.h"
#include "fast3d/coordinate.h"

struct RGBA { uint8_t r, g, b, a; };
struct Vertex { float x, y, z, w; int16_t u, v; RGBA color; };
struct Tile { int shifts, shiftt; float uls, ult; };
struct RDP {
    Tile texture_tile[2];
    uint32_t other_mode_h, other_mode_l;
    RGBA fog_color, grayscale_color, prim_color, env_color;
    uint8_t prim_lod_fraction;
    uint32_t first_tile_index;
};
struct Combiner { uint8_t shader_input_mapping[2][7]; };
enum {
    G_MDSFT_TEXTFILT = 12, G_TF_POINT = 0, G_TL_LOD = 1 << 16,
    G_CCMUX_PRIMITIVE = 3, G_CCMUX_SHADE = 4, G_CCMUX_ENVIRONMENT = 5,
    G_CCMUX_PRIMITIVE_ALPHA = 10, G_CCMUX_ENV_ALPHA = 12,
    G_CCMUX_PRIM_LOD_FRAC = 14, G_CCMUX_LOD_FRACTION = 13,
    G_ACMUX_PRIM_LOD_FRAC = 6
};
struct Clip { bool z_is_from_0_to_1, invertY; };
static unsigned boundCalls;
static float CountBound(uint32_t bound, uint32_t dimension) {
    ++boundCalls;
    return (bound - 0.5f) / dimension;
}
struct Harness {
    Vertex* v_arr[3]; Vertex* v1; RDP* mRdp; Combiner* comb;
    bool use_fog, use_grayscale, use_alpha, is_rect;
    Clip clip_parameters;
    bool usedTextures[2];
    uint32_t tex_width[2], tex_height[2], tex_width2[2], tex_height2[2];
    uint32_t tm; uint8_t numInputs;
    float* mBufVbo; size_t mBufVboLen;
    void Original(); void Projected();
};
void Harness::Original() {
// ORIGINAL_LOOP
}
void Harness::Projected() {
// PROJECTED_LOOP
}
static uint32_t randomState = 0x9f88e2adU;
static uint32_t Next() { randomState = 1664525U * randomState + 1013904223U; return randomState; }
static RGBA Color() {
    RGBA c = {(uint8_t)Next(), (uint8_t)Next(), (uint8_t)Next(), (uint8_t)Next()};
    return c;
}
int main() {
    for (unsigned i = 0; i < 256; ++i) {
        volatile uint8_t input = (uint8_t)i;
        volatile float divisor = 255.0f;
        float expected = input / divisor;
        float actual = Shipyard::Fast3D::UnitColor(input);
        if (memcmp(&expected, &actual, sizeof(float))) {
            printf("unit color mismatch %u\n", i); return 1;
        }
    }
    const uint8_t rgbSelectors[] = {G_CCMUX_PRIMITIVE, G_CCMUX_SHADE,
        G_CCMUX_ENVIRONMENT, G_CCMUX_PRIMITIVE_ALPHA, G_CCMUX_ENV_ALPHA,
        G_CCMUX_PRIM_LOD_FRAC, G_CCMUX_LOD_FRACTION, 0};
    const uint8_t alphaSelectors[] = {G_CCMUX_PRIMITIVE, G_CCMUX_SHADE,
        G_CCMUX_ENVIRONMENT, G_CCMUX_LOD_FRACTION, G_ACMUX_PRIM_LOD_FRAC, 0};
    for (unsigned n = 0; n < 65536; ++n) {
        Vertex vertices[3]; RDP rdp = {}; Combiner combiner = {}; Harness a = {};
        float original[512], projected[512];
        memset(original, 0xa5, sizeof(original));
        memset(projected, 0xa5, sizeof(projected));
        a.mBufVbo = original; a.mBufVboLen = 7; a.mRdp = &rdp; a.comb = &combiner;
        a.use_fog = !!(n & 1); a.use_grayscale = !!(n & 2);
        a.use_alpha = !!(n & 4); a.is_rect = !!(n & 8);
        a.clip_parameters.invertY = !!(n & 16);
        a.clip_parameters.z_is_from_0_to_1 = !!(n & 32);
        a.tm = (n >> 6) & 15; a.numInputs = (n >> 10) % 8;
        a.usedTextures[0] = !!(n & 8192); a.usedTextures[1] = !!(n & 16384);
        for (unsigned i = 0; i < 3; ++i) {
            Vertex& v = vertices[i];
            v.x = (int16_t)Next(); v.y = (int16_t)Next();
            v.z = (int16_t)Next(); v.w = float(1 + Next() % 7000);
            v.u = (int16_t)Next(); v.v = (int16_t)Next(); v.color = Color();
            a.v_arr[i] = &v;
        }
        a.v1 = &vertices[0];
        rdp.other_mode_h = (n % 3) << G_MDSFT_TEXTFILT;
        rdp.other_mode_l = (n & 1) ? G_TL_LOD : 0;
        rdp.fog_color = Color(); rdp.grayscale_color = Color();
        rdp.prim_color = Color(); rdp.env_color = Color();
        rdp.prim_lod_fraction = (uint8_t)Next();
        for (unsigned t = 0; t < 2; ++t) {
            rdp.texture_tile[t].shifts = (n + t) % 16;
            rdp.texture_tile[t].shiftt = (n / 16 + t) % 16;
            rdp.texture_tile[t].uls = (int16_t)Next();
            rdp.texture_tile[t].ult = (int16_t)Next();
            a.tex_width[t] = 1 + Next() % 2048;
            a.tex_height[t] = 1 + Next() % 1024;
            a.tex_width2[t] = Next() % 2048;
            a.tex_height2[t] = Next() % 1024;
        }
        for (int j = 0; j < 7; ++j) {
            combiner.shader_input_mapping[0][j] = rgbSelectors[(n + j) % 8];
            combiner.shader_input_mapping[1][j] = alphaSelectors[(n + j) % 6];
        }
        Harness b = a; b.mBufVbo = projected;
        unsigned expectedBounds = 0;
        for (unsigned t = 0; t < 2; ++t) {
            if (a.usedTextures[t]) {
                expectedBounds += !!(a.tm & (1 << (2 * t)));
                expectedBounds += !!(a.tm & (1 << (2 * t + 1)));
            }
        }
        boundCalls = 0;
        a.Original();
        if (boundCalls != 3 * expectedBounds) {
            printf("original bound count mismatch %u: %u/%u\n", n, boundCalls, 3 * expectedBounds);
            return 3;
        }
        boundCalls = 0;
        b.Projected();
        if (boundCalls != expectedBounds) {
            printf("projected bound count mismatch %u: %u/%u\n", n, boundCalls, expectedBounds);
            return 4;
        }
        if (a.mBufVboLen != b.mBufVboLen || memcmp(original, projected, sizeof(original))) {
            printf("packing mismatch %u len %u/%u\n", n,
                   (unsigned)a.mBufVboLen, (unsigned)b.mBufVboLen);
            return 2;
        }
    }
    puts("PASS 256 exact colors and 65536 9.2.3 original/projected vertex streams");
    return 0;
}
