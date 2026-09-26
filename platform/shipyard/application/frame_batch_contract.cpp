#include <cassert>
#include <cstdio>
#include <memory>
#include <unordered_map>
#include <vector>

static unsigned allocations;
template<class T> struct CountAllocator : std::allocator<T> {
    template<class U> struct rebind { typedef CountAllocator<U> other; };
    CountAllocator() {}
    template<class U> CountAllocator(const CountAllocator<U>&) {}
    T* allocate(size_t count) { ++allocations; return std::allocator<T>().allocate(count); }
    void deallocate(T* value, size_t count) { std::allocator<T>().deallocate(value, count); }
};
struct Mtx {};
typedef float MtxF;
typedef std::unordered_map<Mtx*, MtxF> Map;
static Mtx key;
static unsigned calls;
Map FrameInterpolation_Interpolate(float step) {
    ++calls;
    return Map{{&key, step}};
}

int main() {
    unsigned maxAllocations = 0;
    unsigned cases = 0;
    for (int fps = 20; fps <= 60; ++fps) {
        for (int original_fps = 20; original_fps <= 60; original_fps += 10) {
            for (int initial = 1 - original_fps; initial <= 0; ++initial) {
                allocations = calls = 0;
                int time = initial;
                std::vector<Map, CountAllocator<Map>> mtx_replacements;
                // SCHEDULING_BLOCK
                const unsigned expected = unsigned((fps - initial) / original_fps);
                assert(mtx_replacements.size() == expected);
                unsigned expectedCalls = 0;
                for (unsigned i = 0; i < expected; ++i) {
                    const int tick = initial + int(i + 1) * original_fps;
                    if (tick == fps) {
                        assert(mtx_replacements[i].empty());
                    } else {
                        ++expectedCalls;
                        assert(mtx_replacements[i].size() == 1);
                        assert(mtx_replacements[i].at(&key) == float(tick) / fps);
                    }
                }
                assert(calls == expectedCalls);
                assert(time == initial + int(expected) * original_fps - fps);
                if (allocations > maxAllocations) maxAllocations = allocations;
                assert(allocations <= ALLOCATION_LIMIT);
                ++cases;
            }
        }
    }
    std::printf("schedule cases=%u max vector allocations=%u\n", cases, maxAllocations);
}
