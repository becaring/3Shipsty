#include "fast/interpreter.h"
#include "fast3d/vertex_transform.h"
#include "fast3d/numeric.h"
#include "fast3d/clip_quantize.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <float.h>
#include <limits>

unsigned shipyard_test_vector_stores = 0;
static unsigned aspectCalls;
static unsigned normalCalls;
static float CountNormal(int8_t value) { ++normalCalls; return (float)value; }
static unsigned lightColorCalls[MAX_LIGHTS];
static float CountLightColor(unsigned light, uint8_t value) {
    ++lightColorCalls[light]; return (float)value;
}
static float CountAspect(uint32_t width, uint32_t height) {
    ++aspectCalls;
    return (float)width / (float)height;
}

namespace Ship { namespace Math {
// EXTRACTED_CLAMP
}}

namespace Fast {
static_assert(sizeof(F3DVtx) == 16, "Modern source vertex stride");
static_assert(sizeof(LoadedVertex) == Shipyard::Fast3D::ClipVertexStride,
              "Modern published clip layout");
#define HARNESS(name) struct name { \
    RSP* mRsp; bool mFbActive; XYWidthHeight mCurDimensions; \
    static void NormalizeVector(float v[3]); \
    static void TransposedMatrixMul(float res[3], const float a[3], const float b[4][4]); \
    void CalculateNormalDir(const F3DLight_t* light, float coeffs[3]); \
    float AdjXForAspectRatio(float x) const; \
    void GfxSpVertex(size_t n_vertices, size_t dest_index, const F3DVtx* vertices); \
};
HARNESS(Original)
HARNESS(Projected)
#undef HARNESS
// EXTRACTED_METHODS
}

static void require(bool passed, const char* message) {
    if (!passed) { std::fprintf(stderr, "FAIL %s\n", message); std::exit(1); }
}
static float fromBits(unsigned bits) {
    float value; std::memcpy(&value, &bits, sizeof(value)); return value;
}

static unsigned runCase(unsigned variant, unsigned seed) {
    Fast::RSP a = {};
    a.modelview_matrix_stack_size = 1;
    a.current_num_lights = 1;
    a.texture_scaling_factor.s = a.texture_scaling_factor.t = 65535;
    for (unsigned axis=0; axis<4; ++axis) {
        a.MP_matrix[axis][axis] = 1.0f;
        a.modelview_matrix_stack[0][axis][axis] = 1.0f;
    }
    a.MP_matrix[3][3] = 32.0f;
    a.geometry_mode = (seed & 1 ? G_FOG : 0);
    a.fog_mul = 73;
    a.fog_offset = 16;
    // All exceptional coefficients force the authoritative scalar fallback.
    if (variant == 1) a.MP_matrix[0][0] = fromBits(1);          // subnormal
    if (variant == 2) a.MP_matrix[1][2] = fromBits(0x7fc01234); // qNaN
    if (variant == 3) a.MP_matrix[2][1] = fromBits(0x7f800000); // infinity
    if (variant == 4) a.MP_matrix[0][0] = fromBits(0x75ffffff); // upper edge
    if (variant == 5) a.MP_matrix[0][0] = fromBits(0x76000000); // above bound
    if (variant == 6) a.MP_matrix[0][0] = fromBits(0x0bffffff); // below bound
    if (variant == 7) a.MP_matrix[0][0] = fromBits(0x0c000000); // lower edge
    if (variant == 8) a.MP_matrix[3][2] = -64.0f; // Modern near plane ignored
    if (variant == 9) a.MP_matrix[3][0] = -64.0f; // left clip
    if (variant == 10) a.MP_matrix[3][0] = 64.0f; // right clip
    if (variant == 11) a.MP_matrix[3][1] = -64.0f; // bottom clip
    if (variant == 12) a.MP_matrix[3][1] = 64.0f; // top clip
    if (variant == 13) a.MP_matrix[3][2] = 64.0f; // far clip
    if (variant == 25) a.MP_matrix[3][2] = -64.0f; // non-nearest rounding and near plane
    if (variant == 26) a.MP_matrix[3][0] = 64.0f; // opposite non-nearest mode
    if (variant >= 31) {
        a.geometry_mode |= G_LIGHTING;
        a.current_num_lights = 2 + seed % 4;
        a.current_lights[0].l.col[0] = (uint8_t)seed;
        a.current_lights[0].l.col[1] = (uint8_t)(seed * 7);
        a.current_lights[0].l.col[2] = (uint8_t)(255 - seed);
        a.current_lights_coeffs[0][0] = 0.5f;
        a.current_lights_coeffs[0][1] = -0.25f;
        a.current_lights_coeffs[0][2] = 0.75f;
        for (unsigned light = 1; light < a.current_num_lights - 1; ++light) {
            a.current_lights[light] = a.current_lights[0];
            a.current_lights_coeffs[light][light % 3] = 0.5f;
        }
        if (variant == 32) {
            a.geometry_mode |= G_LIGHTING_POSITIONAL;
            a.current_lights[0].p.unk3 = 1;
            a.current_lights[0].p.pos[0] = 20;
        }
        if (variant >= 33) {
            a.geometry_mode |= G_TEXTURE_GEN;
            a.current_lookat_coeffs[0][0] = 1.0f;
            a.current_lookat_coeffs[1][1] = 1.0f;
            if (variant == 34) a.geometry_mode |= G_TEXTURE_GEN_LINEAR;
        }
        if (variant == 36) { a.current_num_lights = 1; a.geometry_mode &= ~G_TEXTURE_GEN; }
        if (variant == 37) a.current_num_lights = 1;
        if (variant == 39) {
            a.lights_changed = true;
            for (unsigned light=0; light<a.current_num_lights-1; ++light) a.current_lights[light].l.dir[0] = 127;
            a.lookat[0].dir[0] = 127; a.lookat[1].dir[1] = 127;
        }
    }
    Fast::RSP b = a;
    Fast::F3DVtx av[68] = {}, bv[68] = {};
    for (unsigned i=0;i<68;++i) {
        av[i].v.ob[0] = (short)((int)seed * 13 + (int)i * 271 - 1500);
        av[i].v.ob[1] = (short)((int)seed * 7 - (int)i * 119 + 234);
        av[i].v.ob[2] = (short)((int)seed * 23 + (int)i * 67 - 777);
        av[i].v.tc[0] = (short)(i * 123);
        av[i].v.tc[1] = (short)(-((int)i * 97));
        av[i].v.cn[0] = (unsigned char)(seed+i);
        av[i].v.cn[1] = (unsigned char)(seed+2*i);
        av[i].v.cn[2] = (unsigned char)(seed+3*i);
        av[i].v.cn[3] = (unsigned char)(seed+4*i);
    }
    std::memcpy(bv, av, sizeof(av));
    alignas(16) unsigned char unevenA[sizeof(av)+2], unevenB[sizeof(bv)+2];
    std::memcpy(unevenA+2, av, sizeof(av));
    std::memcpy(unevenB+2, bv, sizeof(bv));
    unsigned count = 8, dest = 3;
    const Fast::F3DVtx* left = av;
    const Fast::F3DVtx* right = bv;
    if (variant == 14) count = 0;
    if (variant == 15) { count = 1; dest = 67; }
    if (variant == 16) { count = 64; dest = 0; }
    if (variant == 17) { count = 65; dest = 0; }
    if (variant == 18) { count = 2; dest = 66; } // valid backing, beyond optimized range
    if (variant == 19) { count = 8; dest = 60; } // full RSP backing, batch rejected
    if (variant == 20) { count = 0; left = nullptr; right = nullptr; }
    if (variant == 21) { left = (const Fast::F3DVtx*)a.loaded_vertices;
                         right = (const Fast::F3DVtx*)b.loaded_vertices; }
    if (variant == 22) { left = (const Fast::F3DVtx*)&a.MP_matrix[0][0];
                         right = (const Fast::F3DVtx*)&b.MP_matrix[0][0]; count = 1; }
    if (variant == 23) { left = (const Fast::F3DVtx*)(unevenA+2);
                         right = (const Fast::F3DVtx*)(unevenB+2); } // aligned for shorts, not VMX
    if (variant == 24) { count = 1; dest = 64; }
    if (variant == 35) { left = (const Fast::F3DVtx*)a.loaded_vertices;
                         right = (const Fast::F3DVtx*)b.loaded_vertices; }
    if (variant == 38) { count = 65; dest = 0; }
    std::memset(a.loaded_vertices, 0xa5, sizeof(a.loaded_vertices));
    std::memset(b.loaded_vertices, 0xa5, sizeof(b.loaded_vertices));
    // Rebind aliases after poisoning the same source bytes in each RSP.
    Fast::Original original = {&a, (seed & 2) != 0, {1280, 720}};
    if (variant == 27) original.mCurDimensions.width = 0;
    if (variant == 28) original.mCurDimensions.height = 0;
    if (variant == 29) original.mCurDimensions.width = original.mCurDimensions.height = 0;
    if (variant == 30) { original.mCurDimensions.width = 1921; original.mCurDimensions.height = 1087; }
    Fast::Projected projected = {&b, original.mFbActive, original.mCurDimensions};
    unsigned previousRound = _controlfp(0, 0) & _MCW_RC;
    if (variant == 25 || variant == 26)
        _controlfp(variant == 25 ? _RC_UP : _RC_DOWN, _MCW_RC);
    aspectCalls = 0;
    normalCalls = 0;
    std::memset(lightColorCalls, 0, sizeof(lightColorCalls));
    original.GfxSpVertex(count, dest, left);
    unsigned originalNormalCalls = normalCalls;
    unsigned originalLightColorCalls[MAX_LIGHTS];
    std::memcpy(originalLightColorCalls, lightColorCalls, sizeof(lightColorCalls));
    require(aspectCalls == (original.mFbActive ? 0 : count), "original aspect evaluation count changed");
    unsigned storesBefore = shipyard_test_vector_stores;
    aspectCalls = 0;
    normalCalls = 0;
    std::memset(lightColorCalls, 0, sizeof(lightColorCalls));
    projected.GfxSpVertex(count, dest, right);
    const bool aspectBatch = right != nullptr && count > 0 && count <= MAX_VERTICES &&
        dest <= MAX_VERTICES && count <= MAX_VERTICES - dest &&
        Shipyard::Fast3D::VertexSourceDisjoint(right, count * sizeof(Fast::F3DVtx), &b, sizeof(b));
    require(aspectCalls == (original.mFbActive ? 0 : (aspectBatch ? 1 : count)),
            "projected aspect denominator must evaluate once per eligible packet");
    if (aspectBatch && (b.geometry_mode & G_LIGHTING) &&
        (b.current_num_lights > 1 || (b.geometry_mode & G_TEXTURE_GEN)))
        require(normalCalls == 3 * count, "normal conversion must occur once per vertex component");
    else
        require(normalCalls == originalNormalCalls, "normal fallback evaluation changed");
    for (unsigned light=0; light<MAX_LIGHTS; ++light) {
        unsigned expected = aspectBatch ? (originalLightColorCalls[light] ? 3 : 0) : originalLightColorCalls[light];
        require(lightColorCalls[light] == expected, "light color conversions must be lazy and once per light/packet");
    }
    _controlfp(previousRound, _MCW_RC);
    if (variant == 0 && seed == 0)
        require(shipyard_test_vector_stores > storesBefore, "eligible Modern batch must execute the shared VMX kernel");
    if (variant == 1 || variant == 2 || variant == 3 || variant == 5 || variant == 6 ||
        variant == 14 || variant == 17 || variant == 18 || variant == 19 ||
        variant == 20 || variant == 21 || variant == 22 || variant == 24 ||
        variant == 25 || variant == 26)
        require(shipyard_test_vector_stores == storesBefore, "ineligible Modern batch must retain scalar fallback");
    if (std::memcmp(&a, &b, sizeof(a)) != 0) {
        std::fprintf(stderr, "variant=%u seed=%u count=%u dest=%u\n", variant, seed, count, dest);
        for (unsigned j=0;j<sizeof(a);++j) if (((const unsigned char*)&a)[j]!=((const unsigned char*)&b)[j]) {
            std::fprintf(stderr,"first RSP byte offset=%u original=%02x projected=%02x\n",j,
                         ((const unsigned char*)&a)[j],((const unsigned char*)&b)[j]);break;
        }
        require(false, "authoritative RSP vs projected RSP mismatch");
    }
    if (variant == 8 && count && seed == 0)
        require((b.loaded_vertices[dest].clip_rej & 16) == 0, "Modern near plane disabled");
    return 1;
}

static void countTransformLoop(void* value) { ++*static_cast<unsigned*>(value); }

static void testTransformPhaseBoundary() {
    alignas(16) Fast::F3DVtx input[8] = {};
    alignas(16) float matrix[4][4] = {};
    alignas(16) float plain[8][4] = {};
    alignas(16) float observed[8][4] = {};
    for (unsigned i = 0; i < 4; ++i) matrix[i][i] = 1.0f;
    for (unsigned i = 0; i < 8; ++i) input[i].v.ob[0] = (short)(i * 19 - 47);
    unsigned transitions = 0;
    Shipyard::Fast3D::TransformPhaseHook hook = {countTransformLoop, &transitions};
    require(Shipyard::Fast3D::TransformPositions(input, 8, matrix, plain), "plain transform rejected");
    require(Shipyard::Fast3D::TransformPositionsProfiled(input, 8, matrix, observed, false, 16, &hook),
            "probed transform rejected");
    require(transitions == 1, "loop boundary must fire once after valid setup");
    require(std::memcmp(plain, observed, sizeof(plain)) == 0, "probe changed vertex output");
    matrix[0][0] = fromBits(0x7fc01234);
    transitions = 0;
    std::memset(observed, 0xa5, sizeof(observed));
    require(!Shipyard::Fast3D::TransformPositionsProfiled(input, 8, matrix, observed, false, 16, &hook),
            "invalid matrix accepted");
    require(transitions == 0, "rejected setup must not enter vertex loop");
    for (unsigned i = 0; i < sizeof(observed); ++i)
        require(reinterpret_cast<const unsigned char*>(observed)[i] == 0xa5,
                "rejected setup changed vertex output");
}

int main() {
    testTransformPhaseBoundary();
    unsigned cases = 0;
    for (unsigned seed=0; seed<256; ++seed)
        for (unsigned variant=0; variant<=39; ++variant)
            cases += runCase(variant, seed);
    std::printf("PASS Modern GfxSpVertex differential: %u full-RSP cases\n", cases);
}
