#include <cassert>
#include <cstdint>
#include <cstdio>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include "resources/texture_hash_cache.h"
#include "fast3d/texture_replay.h"

namespace Fast {
enum TextureType { Error, Image };
struct Texture {
    void* ImageData;
    unsigned Flags;
    uint16_t Width, Height;
    float HByteScale, VPixelScale;
    TextureType Type;
    bool dirty;
    Texture(unsigned id) : ImageData(reinterpret_cast<void*>(uintptr_t(0x10000 + id * 256))), Flags(id),
        Width(uint16_t(id + 1)), Height(uint16_t(id + 2)), HByteScale(1.25f), VPixelScale(0.5f), Type(Image), dirty(false) {}
    bool IsDirty() const { return dirty; }
};
}
struct RawTexMetadata {
    uint16_t width = 0, height = 0;
    float h_byte_scale = 1, v_pixel_scale = 1;
    std::shared_ptr<Fast::Texture> resource;
    Fast::TextureType type = Fast::Error;
};
namespace Ship {
struct ArchiveManager {
    unsigned epoch = 1, checks = 0, lookups = 0;
    std::map<uint64_t, std::string> paths;
    unsigned GetXboxHashEpoch() { ++checks; return epoch; }
    const char* HashToCString(uint64_t hash) {
        ++lookups;
        auto it = paths.find(hash);
        return it == paths.end() ? nullptr : it->second.c_str();
    }
};
struct ResourceManager {
    unsigned generation = 1, checks = 0, loads = 0;
    std::shared_ptr<ArchiveManager> archive = std::make_shared<ArchiveManager>();
    std::map<std::string, std::shared_ptr<Fast::Texture>> resources;
    unsigned GetXboxLookupGeneration() { ++checks; return generation; }
    std::shared_ptr<ArchiveManager> GetArchiveManager() { return archive; }
    std::shared_ptr<Fast::Texture> LoadResourceProcess(const char* path) {
        ++loads;
        auto it = resources.find(path);
        return it == resources.end() ? nullptr : it->second;
    }
};
}
struct F3DGfx { struct { uintptr_t w0, w1; } words; };
#define C0(shift, bits) ((cmd->words.w0 >> (shift)) & ((uintptr_t(1) << (bits)) - 1))
unsigned errors = 0;
#define SPDLOG_ERROR(...) (++errors)
namespace ModernFrameProfile {
enum { TextureHashFinal, TextureHashOwningCache, TextureHashLoader };
struct TextureHashSample { bool sampled = false; };
void BeginTextureHash(TextureHashSample&) {}
void EndTextureHash(TextureHashSample&) {}
void AdvanceTextureHash(TextureHashSample&, int) {}
bool CaptureResourceLookups() { return false; }
void ObserveTextureHashCache(bool) {}
}
struct State {
    unsigned format = 0, size = 0, width = 0, flags = 0;
    const void* pixels = nullptr;
    RawTexMetadata metadata;
    std::string path;
    bool operator==(const State& other) const {
        return format == other.format && size == other.size && width == other.width && flags == other.flags &&
            pixels == other.pixels && path == other.path && metadata.width == other.metadata.width &&
            metadata.height == other.metadata.height && metadata.h_byte_scale == other.metadata.h_byte_scale &&
            metadata.v_pixel_scale == other.metadata.v_pixel_scale && metadata.type == other.metadata.type &&
            metadata.resource == other.metadata.resource;
    }
};
struct Interpreter {
    Shipyard::Resources::TextureHashCache<Fast::Texture> mXboxTextureHashCache;
    State state;
    void GfxDpSetTextureImage(unsigned format, unsigned size, unsigned width, const char* path,
                              unsigned flags, const RawTexMetadata& metadata, const void* pixels) {
        state.format = format; state.size = size; state.width = width; state.path = path;
        state.flags = flags; state.metadata = metadata; state.pixels = pixels;
    }
};
Ship::ResourceManager manager;
Interpreter* active;
Ship::ResourceManager* XboxRunResourceManager() { return &manager; }
Ship::ArchiveManager* XboxRunArchiveManager(Ship::ResourceManager*) { return manager.archive.get(); }
Interpreter* XboxDispatchInterpreter() { return active; }
// GENERATED

unsigned cases = 0;
void Compare(Interpreter& reference, Interpreter& cached, uint64_t hash, unsigned command) {
    F3DGfx left[4] = {{{command, 77}}, {{uintptr_t(hash >> 32), uintptr_t(uint32_t(hash))}}, {{123, 456}}, {{0, 0}}};
    F3DGfx right[4];
    std::copy(left, left + 4, right);
    auto a = left; auto b = right;
    active = &reference; errors = 0;
    bool original = ReferenceTextureHash(&a);
    unsigned oldErrors = errors;
    active = &cached; errors = 0;
    bool result = gfx_set_timg_otr_hash_handler_custom(&b);
    assert(result == original && errors == oldErrors && a - left == b - right);
    for (unsigned i = 0; i < 4; ++i) assert(left[i].words.w0 == right[i].words.w0 && left[i].words.w1 == right[i].words.w1);
    assert(reference.state == cached.state);
    ++cases;
}
int main() {
    for (unsigned id = 0; id < 900; ++id) {
        std::string path = "textures/mod/" + std::to_string(id);
        manager.archive->paths[id] = path;
        manager.resources[path] = std::make_shared<Fast::Texture>(id);
    }
    Interpreter reference, cached, otherReference, otherCached;
    ModernBeginTextureReplays(3);
    for (unsigned replay = 0; replay < 3; ++replay)
        for (unsigned draw = 0; draw < 3000; ++draw)
            Compare(reference, cached, draw % 120, (draw * 179) & 0xffffff);
    active = &cached;
    F3DGfx command[2] = {{{0x762343, 0}}, {{0, 1}}};
    unsigned generationChecks = manager.checks, epochChecks = manager.archive->checks;
    for (unsigned i = 0; i < 1000; ++i) { auto pc = command; gfx_set_timg_otr_hash_handler_custom(&pc); }
    assert(manager.checks == generationChecks && manager.archive->checks == epochChecks);
    // Owner, command fields and hash are independent of traversal order.
    for (unsigned id = 0; id < 200; ++id) Compare(otherReference, otherCached, id, id << 12);
    for (unsigned id = 0; id < 900; ++id) Compare(reference, cached, id, id * 97);
    Compare(reference, cached, UINT64_MAX, 0xabcdef); // missing path advances two words
    manager.archive->paths[901] = "missing-resource";
    Compare(reference, cached, 901, 0xaaaaaa);
    auto texture = manager.resources[manager.archive->paths[5]];
    texture->dirty = true; texture->Width = 987; texture->Flags = 1234;
    Compare(reference, cached, 5, 0x123456);
    texture->dirty = false;
    ModernClearTextureReplays(); reference.mXboxTextureHashCache.Clear(); cached.mXboxTextureHashCache.Clear();
    Compare(reference, cached, 5, 0x234567);
    texture->ImageData = nullptr;
    Compare(reference, cached, 5, 0x345678); // no texture image state write on either path
    texture->ImageData = reinterpret_cast<void*>(uintptr_t(0x9000));
    ModernEndTextureReplays();
    for (unsigned id = 0; id < 120; ++id)
        manager.resources[manager.archive->paths[id]] = std::make_shared<Fast::Texture>(id + 1000);
    ++manager.generation; ++manager.archive->epoch;
    ModernBeginTextureReplays(3);
    for (unsigned id = 0; id < 120; ++id) Compare(reference, cached, id, 0x654321);
    ModernEndTextureReplays();
    ModernBeginTextureReplays(1);
    for (unsigned id = 0; id < 120; ++id) Compare(reference, cached, id, id);
    assert(!sModernTextureReplays->active);
    ModernEndTextureReplays();
    gModernTextureReplayControl[0] = 0;
    ModernBeginTextureReplays(3);
    assert(!sModernTextureReplays->active && gModernTextureReplayControl[1] == 0);
    generationChecks = manager.checks;
    for (unsigned id = 0; id < 120; ++id) Compare(reference, cached, id, id);
    assert(manager.checks > generationChecks);
    ModernEndTextureReplays();
    gModernTextureReplayControl[0] = 1;
    ModernBeginTextureReplays(3);
    assert(sModernTextureReplays->active && gModernTextureReplayControl[1] == 1);
    Compare(reference, cached, 7, 0);
    Compare(reference, cached, 7, 0);
    assert(sModernTextureReplays->hits == 1 && sModernTextureReplays->misses == 1);
    ModernEndTextureReplays();
    // The entry owns paths and resources even after the source cache retires.
    ModernTextureReplays lifetime;
    lifetime.Begin(3);
    RawTexMetadata metadata; metadata.resource = std::make_shared<Fast::Texture>(9);
    std::weak_ptr<Fast::Texture> weak = metadata.resource;
    std::string owned = "temporary-path";
    lifetime.Store(&cached, 55, owned.c_str(), 3, metadata);
    owned.assign(8000, 'z'); metadata.resource.reset();
    assert(!weak.expired() && lifetime.Lookup(&cached, 55)->path == "temporary-path");
    lifetime.End(); assert(weak.expired());
    delete sModernTextureReplays; sModernTextureReplays = nullptr;
    printf("%u generated texture command cases; replay lookup suppression and ownership passed\n", cases);
}
