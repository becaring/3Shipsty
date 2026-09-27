#include "fast3d/tri2_packed_reuse.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static unsigned computed;
static uint32_t seed = 0x327ab10du;
static uint32_t next() { seed = seed * 1664525u + 1013904223u; return seed; }
static uint32_t bits(float value) { uint32_t out; memcpy(&out, &value, 4); return out; }

static void pack(float*& output, uint8_t index, unsigned material, float firstW, bool lod) {
    ++computed;
    const float x = float(index * 19 - 31);
    const float u = float(index * 97 - 111) / 32.0f;
    *output++ = x;
    *output++ = u / float(1 + material);
    *output++ = float((index * 17 + material) & 255) / 255.0f;
    *output++ = lod ? (firstW - 3000.0f) / 3000.0f : float(material);
}

static int scenario(const uint8_t first[3], const uint8_t second[3],
                    bool lod, bool changeFirstW, bool changePipeline, bool flush) {
    float baseline[128], cached[128];
    memset(baseline, 0xa5, sizeof(baseline));
    memset(cached, 0xa5, sizeof(cached));
    float* plain = baseline;
    float* fast = cached;
    const unsigned firstMaterial = 3, secondMaterial = changePipeline ? 7 : firstMaterial;
    const float firstW = 3219.0f, secondW = changeFirstW ? 5137.0f : firstW;
    for (int i = 0; i < 3; ++i) pack(plain, first[i], firstMaterial, firstW, lod);
    for (int i = 0; i < 3; ++i) pack(plain, second[i], secondMaterial, secondW, lod);
    const unsigned baselineComputed = computed;
    computed = 0;
    ModernTri2PackedReuse reuse;
    reuse.Reset();
    size_t starts[3];
    for (int i = 0; i < 3; ++i) {
        starts[i] = size_t(fast - cached);
        pack(fast, first[i], firstMaterial, firstW, lod);
    }
    reuse.Capture(first, starts, size_t(fast - cached), bits(firstW));
    const float* materialInputs[2][ModernTri2PackedReuse::kMaterialInputs] = {};
    materialInputs[0][0] = cached + starts[0] + 3;
    reuse.CaptureMaterials(materialInputs, cached, 1, false);
    materialInputs[0][0] = 0;
    if (flush) reuse.Reset();
    const bool eligible = reuse.CanReuse(size_t(fast - cached), !changePipeline,
                                         lod, bits(secondW));
    unsigned copied = 0;
    for (int i = 0; i < 3; ++i) {
        if (eligible && reuse.CopyVertex(second[i], fast, cached)) {
            if (i == 0) {
                reuse.RestoreMaterials(materialInputs, cached, 1, false);
                if (materialInputs[0][0] != cached + starts[0] + 3) return -4;
            }
            ++copied;
        } else {
            pack(fast, second[i], secondMaterial, secondW, lod);
            if (i == 0) materialInputs[0][0] = fast - 1;
        }
    }
    if (size_t(plain - baseline) != size_t(fast - cached) ||
        memcmp(baseline, cached, size_t(plain - baseline) * sizeof(float))) return -1;
    if (baselineComputed != 6 || computed + copied != 6) return -2;
    if ((flush || changePipeline || (lod && changeFirstW)) && copied) return -3;
    if (!materialInputs[0][0]) return -5;
    return int(copied);
}

int main() {
    const uint8_t first[3] = {1, 2, 3};
    const uint8_t quad[3] = {1, 3, 4};
    computed = 0;
    if (scenario(first, quad, false, false, false, false) != 2) return 11;
    computed = 0;
    if (scenario(first, quad, true, true, false, false) != 0) return 12;
    computed = 0;
    if (scenario(first, quad, false, true, false, false) != 2) return 13;
    computed = 0;
    if (scenario(first, quad, false, false, true, false) != 0) return 14;
    computed = 0;
    if (scenario(first, quad, false, false, false, true) != 0) return 15;
    unsigned cases = 0, reused = 0;
    for (unsigned n = 0; n < 65536; ++n) {
        uint8_t a[3], b[3];
        for (int i = 0; i < 3; ++i) a[i] = uint8_t(next() % 24);
        for (int i = 0; i < 3; ++i) b[i] = uint8_t(next() % 24);
        // Include deliberate quad-like overlap and arbitrary permutations.
        if (n & 1) { b[0] = a[0]; b[1] = a[2]; }
        computed = 0;
        int result = scenario(a, b, !!(n & 2), !!(n & 4), !!(n & 8), !!(n & 16));
        if (result < 0 || result > 3) return 20;
        reused += unsigned(result);
        ++cases;
    }
    printf("PASS TRI2 packed reuse differential cases=%u copied_vertices=%u quad_compute=4/6\n",
           cases, reused);
    return 0;
}
