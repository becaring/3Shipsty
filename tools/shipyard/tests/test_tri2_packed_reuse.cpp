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

static void runPack(float*& output, uint8_t index, unsigned material,
                    uint32_t w, bool lod, unsigned width) {
    // Include non-arithmetic payloads: copying must retain NaN and signed-zero bits.
    for (unsigned j = 0; j < width; ++j) {
        uint32_t word = j == 0 ? 0x80000000u : j == 1 ? 0x7fc01234u :
            (0x3e800000u ^ (unsigned(index) << 12) ^ (material << 4) ^ j);
        if (lod && j == width - 1) word = w;
        memcpy(output++, &word, sizeof(word));
    }
}

static int runScenario(unsigned run, unsigned* totalCopied) {
    float baseline[16384], cached[16384];
    float* plain = baseline;
    float* fast = cached;
    ModernTri2PackedReuse reuse;
    unsigned material = 3, width = 4 + (run % 30);
    uint32_t w = 0x45678000u;
    bool lod = (run & 1) != 0;
    unsigned copied = 0;
    for (unsigned tri = 0; tri < 128; ++tri) {
        const unsigned event = next() >> 26;
        bool pipeline = true;
        if (event == 0) { ++material; pipeline = false; }
        if (event == 1) w ^= 0x1000u;
        if (event == 2) reuse.Reset(); // A non-triangle command or buffer flush.
        if (event == 3) { width = 4 + (next() >> 24) % 30; pipeline = false; }
        const bool eligible = reuse.CanReuse(size_t(fast - cached), pipeline, lod, w);
        if (!eligible) reuse.Reset();
        uint8_t indices[3];
        size_t starts[3];
        for (unsigned i = 0; i < 3; ++i) {
            indices[i] = uint8_t(next() >> 24);
            if (run & 2) indices[i] &= 15;
            starts[i] = size_t(fast - cached);
            runPack(plain, indices[i], material, w, lod, width);
            if (eligible && reuse.CopyVertex(indices[i], fast, cached)) ++copied;
            else runPack(fast, indices[i], material, w, lod, width);
        }
        reuse.Capture(indices, starts, size_t(fast - cached), w);
    }
    if (size_t(plain - baseline) != size_t(fast - cached) ||
        memcmp(baseline, cached, size_t(plain - baseline) * sizeof(float))) return 1;
    *totalCopied += copied;
    return 0;
}

static int guards() {
    ModernTri2PackedReuse reuse;
    const uint8_t indices[3] = {0, 127, 255};
    const size_t starts[3] = {0, 4, 8};
    float buffer[64] = {}, *output = buffer + 12;
    reuse.Capture(indices, starts, 12, 0);
    if (reuse.CanReuse(0, true, false, 0) ||
        reuse.CanReuse(11, true, false, 0)) return 1;
    reuse.generation = 0xffffffffu;
    reuse.Reset();
    if (reuse.CopyVertex(0, output, buffer)) return 2;
    const uint8_t other[3] = {1, 2, 3};
    reuse.Capture(other, starts, 12, 0);
    if (reuse.CopyVertex(255, output, buffer)) return 3;
    const size_t bad[3] = {12, 16, 21};
    reuse.Capture(indices, bad, 25, 0);
    if (reuse.valid || reuse.CopyVertex(1, output, buffer)) return 4;
    return 0;
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
    unsigned runCopied = 0;
    for (unsigned run = 0; run < 2048; ++run)
        if (runScenario(run, &runCopied)) return 30;
    if (!runCopied || guards()) return 31;
    printf("PASS TRI2 run differential triangles=262144 copied_vertices=%u guards=pass\n", runCopied);
    return 0;
}
