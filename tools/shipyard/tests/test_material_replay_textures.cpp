#include "fast/interpreter.h"
#include "fast3d/material_memo.h"
#include <cstdio>
#include <cstdlib>
using namespace Fast;
#undef TEXTURE_CACHE_MAX_SIZE
#define TEXTURE_CACHE_MAX_SIZE 8
struct TextureOwner;
// NODE_HELPERS
struct Backend {
    std::vector<unsigned> calls;
    unsigned next;
    Backend() : next(1) {}
    unsigned NewTexture() { calls.push_back(1000 + next); return next++; }
    void SelectTexture(int slot, unsigned id) { calls.push_back(2000 + slot * 100 + id); }
    void SetSamplerParameters(int slot, bool filter, unsigned cms, unsigned cmt) {
        calls.push_back(3000 + slot * 100 + filter * 16 + cms * 4 + cmt);
    }
};
struct TextureOwner {
    struct Cache {
        TextureCacheMap map;
        std::list<TextureCacheMapIter> lru;
        std::vector<unsigned> free_texture_ids;
    } mTextureCache;
    RenderingState mRenderingState;
    Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES> mXboxTextureBindings;
    Backend backend;
    Backend* mRapi;
    unsigned finds;
    TextureOwner() : mRenderingState(), mRapi(&backend), finds(0) {}
    void Flush() { backend.calls.push_back(4000); }
    TextureCacheMap::iterator Find(const TextureCacheKey& key) {
        ++finds;
        return mTextureCache.map.find(key);
    }
    bool Original(int i, const TextureCacheKey& key) { // ORIGINAL
    }
    bool Cached(int i, const TextureCacheKey& key) { // CACHED
    }
    void Invalidate(unsigned kind, const uint8_t* address) {
        sModernTextureNodes.Clear();
        mXboxTextureBindings.Invalidate();
        if (kind == 2) return;
        for (auto it = mTextureCache.lru.begin(); it != mTextureCache.lru.end();) {
            auto node = it->it;
            if (!kind || node->first.texture_addr == address) {
                mTextureCache.free_texture_ids.push_back(node->second.texture_id);
                mTextureCache.map.erase(node);
                it = mTextureCache.lru.erase(it);
            } else ++it;
        }
    }
};
static void require(bool okay, const char* what) {
    if (!okay) { fprintf(stderr, "FAIL %s\n", what); exit(1); }
}
static void compare(const TextureOwner& a, const TextureOwner& b) {
    require(a.backend.calls == b.backend.calls, "native calls or flush order changed");
    require(a.mTextureCache.free_texture_ids == b.mTextureCache.free_texture_ids, "texture ID retirement changed");
    require(a.mTextureCache.map.size() == b.mTextureCache.map.size(), "cache size differs");
    auto x = a.mTextureCache.lru.begin(), y = b.mTextureCache.lru.begin();
    for (; x != a.mTextureCache.lru.end(); ++x, ++y) {
        require(x->it->first == y->it->first, "LRU order differs");
        require(x->it->second.texture_id == y->it->second.texture_id, "selected texture differs");
    }
}
static unsigned randomState = 0x8b11;
static unsigned next() {
    randomState ^= randomState << 13;
    randomState ^= randomState >> 17;
    return randomState ^= randomState << 5;
}
int main() {
    static uint8_t addresses[512], palettes[32];
    TextureOwner original, cached;
    for (unsigned n = 0; n < 20000; ++n) {
        const unsigned op = next() % 40;
        if (op < 3) {
            const uint8_t* address = addresses + next() % 32;
            original.Invalidate(op, address);
            cached.Invalidate(op, address);
        } else {
            TextureCacheKey key = {};
            key.texture_addr = addresses + next() % 32;
            key.palette_addrs[0] = palettes + next() % 4;
            key.palette_addrs[1] = palettes + next() % 4;
            key.fmt = next() % 4;
            key.siz = next() % 4;
            key.palette_index = next() % 16;
            key.size_bytes = next() % 4096;
            const unsigned slot = next() % 2;
            require(original.Original(slot, key) == cached.Cached(slot, key), "lookup hit result changed");
        }
        compare(original, cached);
        original.backend.calls.clear();
        cached.backend.calls.clear();
    }
    original.Invalidate(0, NULL);
    cached.Invalidate(0, NULL);
    TextureCacheKey keys[2] = {};
    keys[0].texture_addr = addresses;
    keys[1].texture_addr = addresses + 128;
    for (unsigned i = 0; i < 2; ++i) {
        original.Original(0, keys[i]);
        cached.Cached(0, keys[i]);
    }
    const unsigned warmed = cached.finds;
    for (unsigned replay = 0; replay < 3; ++replay) {
        original.mXboxTextureBindings.Invalidate();
        cached.mXboxTextureBindings.Invalidate();
        for (unsigned draw = 0; draw < 100; ++draw) {
            const TextureCacheKey& key = keys[draw & 1];
            require(original.Original(0, key) == cached.Cached(0, key), "replay result differs");
            compare(original, cached);
        }
    }
    require(cached.finds == warmed, "replay repeated texture map lookup");
    require(original.finds >= cached.finds + 300, "lookup reuse not exercised");
    puts("PASS 20000 texture operations: native flush/bind order, LRU, palette keys, eviction, deletion and replay reuse");
}
