#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <float.h>
#include "fast3d/projection_cache.h"

struct Vertex { float x, y, w; };
static Shipyard::Fast3D::ProjectionValueCache sModernCullProjection[68];

static __declspec(noinline) float Original(Vertex* v1, Vertex* v2, Vertex* v3) {
// ORIGINAL_BODY
    return cross;
}

static __declspec(noinline) float Projected(Vertex* v1, Vertex* v2, Vertex* v3,
                       uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx) {
// PROJECTED_BODY
    return cross;
}

static uint32_t Next(uint32_t& state) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

static float Finite(uint32_t bits) {
    const uint32_t value = (bits & 0x807fffffU) | 0x3f000000U;
    float result;
    std::memcpy(&result, &value, 4);
    return result;
}

static float Bits(uint32_t bits) {
    float value;
    std::memcpy(&value, &bits, 4);
    return value;
}

int main() {
    uint32_t seed = 0x9462a3b1U;
    Vertex vertices[68] = {};
    for (unsigned mode = 0; mode != 4; ++mode) {
        unsigned previous;
        _controlfp_s(&previous, mode << 8, _MCW_RC);
        vertices[0] = {1.0f, 0.7f, 3.0f};
        vertices[1] = {2.0f, 0.3f, 7.0f};
        vertices[2] = {4.0f, 0.9f, 11.0f};
        const float modeOriginal = Original(&vertices[0], &vertices[1], &vertices[2]);
        const float modeProjected = Projected(&vertices[0], &vertices[1], &vertices[2], 0, 1, 2);
        if (std::memcmp(&modeOriginal, &modeProjected, 4) != 0) {
            uint32_t first, second;
            std::memcpy(&first, &modeOriginal, 4);
            std::memcpy(&second, &modeProjected, 4);
            std::printf("cull FPSCR mismatch mode=%u original=%08x projected=%08x cache-mode=%u active=%u\n",
                        mode, first, second, sModernCullProjection[0].roundingMode,
                        Shipyard::Fast3D::ProjectionRoundingMode());
            return 1;
        }
        const uint32_t edges[] = {0, 0x80000000U, 0x7f800000U,
                                  0xff800000U, 0x7fc01234U, 0x7f7fffffU};
        for (unsigned edge = 0; edge != sizeof(edges) / sizeof(edges[0]); ++edge) {
            vertices[0].w = Bits(edges[edge]);
            const float original = Original(&vertices[0], &vertices[1], &vertices[2]);
            const float projected = Projected(&vertices[0], &vertices[1], &vertices[2], 0, 1, 2);
            if ((original <= 0) != (projected <= 0) ||
                (original >= 0) != (projected >= 0)) {
                std::printf("exceptional cull mismatch mode=%u edge=%u\n", mode, edge);
                return 1;
            }
        }
        for (unsigned i = 0; i != 65536; ++i) {
            const uint8_t a = static_cast<uint8_t>(Next(seed) % 68);
            const uint8_t b = static_cast<uint8_t>(Next(seed) % 68);
            const uint8_t c = static_cast<uint8_t>(Next(seed) % 68);
            for (unsigned k = 0; k != 3; ++k) {
                Vertex& vertex = vertices[k == 0 ? a : k == 1 ? b : c];
                vertex.x = Finite(Next(seed));
                vertex.y = Finite(Next(seed));
                vertex.w = Finite(Next(seed));
            }
            Vertex* v1 = &vertices[a];
            Vertex* v2 = &vertices[b];
            Vertex* v3 = &vertices[c];
            for (unsigned repeat = 0; repeat != 2; ++repeat) {
                const float original = Original(v1, v2, v3);
                const float projected = Projected(v1, v2, v3, a, b, c);
                if (std::memcmp(&original, &projected, 4) != 0) {
                    std::printf("cull mismatch mode=%u case=%u repeat=%u\n", mode, i, repeat);
                    return 1;
                }
            }
        }
    }
    std::puts("modern cull original/projected 524288 cases");
}
