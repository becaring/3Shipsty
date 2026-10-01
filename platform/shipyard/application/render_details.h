#pragma once
#include <string.h>

// Details counts read no clocks and stay disabled until explicitly enabled.
// Game-owned actor counts are copied into a packet before the next recording.
namespace ModernFrameProfile {
enum FlushReason {
    FlushCombiner, FlushDepth, FlushDecal, FlushViewport, FlushScissor,
    FlushTextureImport, FlushSampler, FlushShader, FlushAlpha, FlushBufferFull,
    FlushFramebufferSet, FlushFramebufferReset, FlushFramebufferCopy, FlushFramebufferRead,
    FlushBlendedTexture, FlushFramebufferTexture, FlushFrameEnd, FlushCacheClear,
    FlushCacheDelete, FlushExternalApi, FlushTextureSelect, FlushTextureMiss, FlushReasonCount
};
struct FlushCounts { unsigned calls, empty, triangles, maximum; };
struct RenderDetailsCounts {
    bool enabled;
    FlushCounts flush[FlushReasonCount];
    unsigned draws, triangles, maximumTriangles;
    unsigned textureLookups, textureHits, textureMisses, imports, maskImports;
    RenderDetailsCounts() : enabled(false) { Reset(); }
    void Reset() {
        memset(flush, 0, sizeof(flush));
        draws = triangles = maximumTriangles = 0;
        textureLookups = textureHits = textureMisses = imports = maskImports = 0;
    }
    void Begin(bool value) { Reset(); enabled = value; }
    void Flush(FlushReason reason, unsigned count) {
        if (!enabled || reason >= FlushReasonCount) return;
        FlushCounts& bucket = flush[reason];
        ++bucket.calls;
        if (!count) { ++bucket.empty; return; }
        bucket.triangles += count;
        if (count > bucket.maximum) bucket.maximum = count;
        ++draws; triangles += count;
        if (count > maximumTriangles) maximumTriangles = count;
    }
    void TextureLookup(bool hit) {
        if (!enabled) return;
        ++textureLookups;
        if (hit) ++textureHits; else ++textureMisses;
    }
    void TextureImport(bool mask) {
        if (!enabled) return;
        if (mask) ++maskImports; else ++imports;
    }
};
struct ActorInstanceCounts {
    enum { Capacity = 512 };
    bool enabled;
    unsigned total, calls[Capacity];
    ActorInstanceCounts() : enabled(false), total(0) { memset(calls, 0, sizeof(calls)); }
    void Begin(bool value) { enabled = value; total = 0; memset(calls, 0, sizeof(calls)); }
    void Observe(int id) {
        if (!enabled || id < 0 || id >= Capacity) return;
        ++total; ++calls[id];
    }
    ActorInstanceCounts Take() {
        ActorInstanceCounts packet = *this;
        Begin(enabled);
        return packet;
    }
};
void SetFlushReason(FlushReason reason);
void ObserveFlush(unsigned triangles);
void ObserveTextureLookup(bool hit);
void ObserveTextureImport(bool mask);
void BeginActorRecording(bool detailsEnabled);
ActorInstanceCounts TakeActorInstances();
void ObserveActorInstances(const ActorInstanceCounts& packet);
}
