#include "fast/interpreter.h"
#include "fast3d/material_memo.h"
#include <cstdio>
#include <cstdlib>
using namespace Fast;
struct ModeOwner;
// MODE_HELPERS
struct ModeResult {
    ColorCombiner* comb;
    uint64_t id;
    bool alpha, fog, grayscale;
};
struct ModeOwner {
    RDP rdp;
    RDP* mRdp;
    std::map<ColorCombinerKey, ColorCombiner> pool;
    unsigned lookups;
    ModeOwner() : rdp(), mRdp(&rdp), lookups(0) {}
    ColorCombiner* LookupOrCreateColorCombiner(const ColorCombinerKey& key) {
        ++lookups;
        return &pool[key];
    }
    ModeResult Original() { // ORIGINAL
    }
    ModeResult Cached() { // CACHED
    }
};
static void require(bool okay, const char* what) {
    if (!okay) { fprintf(stderr, "FAIL %s\n", what); exit(1); }
}
static unsigned state = 0x4c11db7;
static unsigned next() {
    state ^= state << 13;
    state ^= state >> 17;
    return state ^= state << 5;
}
static void compare(ModeOwner& owner) {
    const ModeResult a = owner.Original(), b = owner.Cached();
    require(a.comb == b.comb && a.id == b.id && a.alpha == b.alpha &&
        a.fog == b.fog && a.grayscale == b.grayscale, "decoded material differs");
    const unsigned before = owner.lookups;
    const ModeResult c = owner.Cached();
    require(c.comb == a.comb && owner.lookups == before, "mode hit repeated combiner lookup");
}
int main() {
    static_assert(sizeof(sModernModes) == sizeof(void*), "cache arrays must stay outside Xenon TLS");
    ModeOwner owners[2];
    for (unsigned i = 0; i < 65536; ++i) {
        ModeOwner& owner = owners[i & 1];
        owner.rdp.combine_mode = (uint64_t(next()) << 32) | next();
        owner.rdp.other_mode_l = next();
        owner.rdp.other_mode_h = next();
        owner.rdp.grayscale = !!(i & 1);
        owner.rdp.current_shader.enabled = !!(i & 2);
        owner.rdp.current_shader.id = short(next() & 32767);
        owner.rdp.loaded_texture[0].masked = !!(i & 4);
        owner.rdp.loaded_texture[1].masked = !!(i & 8);
        owner.rdp.loaded_texture[0].blended = !!(i & 16);
        owner.rdp.loaded_texture[1].blended = !!(i & 32);
        compare(owner);
    }
    ModeOwner& owner = owners[0];
    owner.rdp = RDP();
    compare(owner);
    for (unsigned bit = 0; bit < 64; ++bit) {
        owner.rdp.combine_mode = uint64_t(1) << bit;
        compare(owner);
    }
    for (unsigned bit = 0; bit < 32; ++bit) {
        owner.rdp.other_mode_l = 1U << bit;
        compare(owner);
        owner.rdp.other_mode_h = 1U << bit;
        compare(owner);
    }
    sModernModes.Release();
    require(!sModernModes.entries, "release retained storage");
    owner.pool.clear();
    compare(owner);
    owner.rdp = RDP();
    owner.Cached();
    owner.rdp.combine_mode = 1;
    owner.Cached();
    unsigned warmed = owner.lookups;
    for (unsigned replay = 0; replay < 3; ++replay)
        for (unsigned draw = 0; draw < 1000; ++draw) {
            owner.rdp.combine_mode = draw & 1;
            owner.Cached();
        }
    require(owner.lookups == warmed, "mode lookup repeated across replays");
    puts("PASS 65536 mode combinations, bit mutations, owner/reset boundaries and three replay reuse");
}
