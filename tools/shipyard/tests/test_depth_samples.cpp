#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <set>
#include <unordered_map>
#include <utility>
#include "fast3d/depth_samples.h"

static size_t allocations;
void* operator new(size_t bytes) { ++allocations; if (void* p = std::malloc(bytes)) return p; throw std::bad_alloc(); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, size_t) noexcept { std::free(p); }
struct hash_pair_ff {
    size_t operator()(const std::pair<float, float>& p) const {
        return std::hash<float>()(p.first) ^ (std::hash<float>()(p.second) << 1);
    }
};
typedef uint32_t DWORD;
typedef int32_t LONG;
struct POINT { LONG x, y; };
struct RECT { LONG left, top, right, bottom; };
struct D3DLOCKED_RECT { void* pBits; };
struct XGTEXTURE_DESC { unsigned Format; };
const unsigned D3DLOCK_READONLY = 1;
const int E_FAIL = -1, FALSE = 0;
struct Trace {
    unsigned validate, finish, begin, lock, unlock, untile, busy, initialized;
    bool operator==(const Trace& rhs) const { return std::memcmp(this, &rhs, sizeof(*this)) == 0; }
} trace;
struct IDirect3DTexture9 {
    unsigned seed;
    int IsBusy() { ++trace.busy; return seed & 1; }
    int LockRect(unsigned, D3DLOCKED_RECT* lock, const void*, unsigned flags) {
        assert(flags == D3DLOCK_READONLY); ++trace.lock; lock->pBits = this; return 0;
    }
    void UnlockRect(unsigned) { ++trace.unlock; }
};
struct Framebuffer {
    IDirect3DTexture9* depth_samples[1];
    uint32_t width, height, samples;
    bool depth_stored;
} buffers[2];
struct Published { IDirect3DTexture9* texture; int framebuffer; uint32_t width, height; } published_depth;
struct Timing {
    uint64_t depthReadTicks, depthLockTicks;
    unsigned depthReadCalls, depthLockCalls, depthSamples;
    unsigned depthBusyCalls, depthBusy1080Calls, depthIdleCalls, depthIdle1080Calls;
} timing_counts;
bool live_framebuffer, timing_enabled = true, detailed_timing_enabled = true;
int active_fb;
struct NativeTimingScope {
    NativeTimingScope(uint64_t& ticks, unsigned& calls) { ++ticks; ++calls; }
};
void ValidateFramebuffer(int id) { assert(id >= 0 && id < 2); ++trace.validate; }
void FinishFramebuffer() {
    ++trace.finish;
    if (live_framebuffer) buffers[active_fb].depth_stored = true;
    live_framebuffer = false;
}
void BeginFramebuffer() { ++trace.begin; live_framebuffer = true; }
void Shipyard_Fatal(const char*, int) { assert(false); }
void Shipyard_Check(int status, const char*) { assert(status == 0); }
void Shipyard_Log(const char*, ...) { ++trace.initialized; }
void XGGetTextureDesc(IDirect3DTexture9*, unsigned, XGTEXTURE_DESC* desc) { desc->Format = 24; }
unsigned XGGetGpuFormat(unsigned format) { return format; }
void XGUntileTextureLevel(unsigned width, unsigned height, unsigned, unsigned, unsigned, DWORD* value,
                          size_t stride, const POINT* destination, void* pixels, const RECT* source) {
    assert(stride == sizeof(DWORD) && destination->x == 0 && destination->y == 0);
    assert(source->left >= 0 && source->right <= int(width) && source->top >= 0 && source->bottom <= int(height));
    auto texture = static_cast<IDirect3DTexture9*>(pixels);
    *value = (texture->seed * 2654435761u) ^ (unsigned(source->left) * 91771u) ^ (unsigned(source->top) * 7919u);
    ++trace.untile;
}
// ORIGINAL
// ARRAY

IDirect3DTexture9 target = {57}, published = {98};
void Setup(unsigned mode) {
    trace = {}; timing_counts = {};
    active_fb = int(mode & 1);
    buffers[0] = { {&target}, 1280, 720, 1, (mode & 2) != 0 };
    buffers[1] = { {&target}, 1920, 1080, 4, (mode & 2) != 0 };
    published_depth = {(mode & 4) ? &published : nullptr, int(mode & 1), 640, 480};
    live_framebuffer = (mode & 8) != 0;
}
unsigned batchReads, batchSamples, revision;
uint16_t Value(float x, float y) { return uint16_t(int(x * 13 + y * 7) + revision * 17); }
void ReadFixture(int id, ModernDepthSample* samples, size_t count) {
    assert(id == 2 && count <= 64); ++batchReads; batchSamples += unsigned(count);
    for (size_t i = 0; i < count; ++i) samples[i].depth = Value(samples[i].x, samples[i].y);
}
int main() {
    unsigned compared = 0;
    for (unsigned mode = 0; mode < 16; ++mode) {
        for (unsigned count = 0; count <= 160; ++count) {
            std::set<std::pair<float, float>> coords;
            ModernDepthSample samples[160];
            for (unsigned i = 0; i < count; ++i) {
                float x = float(int(i * 127 % 2300) - 100) + 0.25f;
                float y = float(int(i * 167 % 1250) - 90) + 0.5f;
                coords.insert({x, y}); samples[i] = {x, y, 0};
            }
            Setup(mode);
            auto expected = PixelDepth(int(mode & 1), coords);
            Trace before = trace;
            Timing oldTiming = timing_counts;
            bool oldLive = live_framebuffer;
            Setup(mode);
            size_t allocated = allocations;
            PixelDepthSamples(int(mode & 1), samples, count);
            assert(allocations == allocated && trace == before && live_framebuffer == oldLive);
            assert(std::memcmp(&oldTiming, &timing_counts, sizeof(oldTiming)) == 0);
            for (unsigned i = 0; i < count; ++i) {
                assert(samples[i].depth == expected.at({samples[i].x, samples[i].y})); ++compared;
            }
        }
    }
    ModernDepthSamples cache;
    for (unsigned frame = 0; frame < 1000; ++frame) {
        cache.Clear(); revision = frame; batchReads = batchSamples = 0;
        const size_t allocated = allocations;
        for (unsigned i = 0; i < 33; ++i) { cache.Prepare(float(i), float(i + 1)); cache.Prepare(float(i), float(i + 1)); }
        assert(cache.Read(2, 0, 1, ReadFixture) == Value(0, 1));
        assert(batchReads == 1 && batchSamples == 33);
        ++revision;
        for (unsigned i = 0; i < 33; ++i)
            assert(cache.Read(2, float(i), float(i + 1), ReadFixture) == uint16_t(Value(float(i), float(i + 1)) - 17));
        assert(batchReads == 1 && allocations == allocated);
        assert(cache.Read(2, 55, 56, ReadFixture) == Value(55, 56));
        assert(batchReads == 2 && batchSamples == 34 && allocations == allocated);
    }
    cache.Clear(); revision = 99; batchReads = batchSamples = 0;
    for (unsigned i = 0; i < 150; ++i) cache.Prepare(float(i), float(i));
    for (unsigned i = 0; i < 150; ++i) assert(cache.Read(2, float(i), float(i), ReadFixture) == Value(float(i), float(i)));
    assert(batchReads == 3 && batchSamples == 150);
    cache.Clear(); batchReads = batchSamples = 0;
    cache.Prepare(-0.0f, 0); cache.Prepare(0, -0.0f);
    assert(cache.Read(2, 0, 0, ReadFixture) == Value(0, 0));
    assert(batchReads == 1 && batchSamples == 1);
    printf("%u native depth samples matched; 1000 allocation-free sun/light batches and overflow passed\n", compared);
}
