#pragma once

#include <stdint.h>
#include <string.h>

// Zero-initialized TLS. Only adjacent TRI2 commands may retain this certificate;
// pipeline reconciliation and Flush discard it before any renderer callback.
struct ModernTri2CullRunCache {
    uint32_t generation;
    uint32_t generations[256];
    uint32_t rounding;
    bool roundingValid;

    void Reset() {
        roundingValid = false;
        if (++generation == 0) {
            memset(generations, 0, sizeof(generations));
            generation = 1;
        }
    }

    bool Contains(uint8_t index) const { return generations[index] == generation; }

    template<class Cache, class Vertex>
    void Load(uint8_t index, Cache& cache, const Vertex& vertex, uint32_t mode) {
        if (generations[index] == generation) return;
        cache.Load(vertex.x, vertex.y, vertex.w, mode);
        // The underlying cache deliberately excludes exceptional divisions.
        if (cache.valid) generations[index] = generation;
    }
};
