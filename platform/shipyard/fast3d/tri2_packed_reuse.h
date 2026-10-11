#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(_MSC_VER)
#define MODERN_TRI2_INLINE __forceinline
#else
#define MODERN_TRI2_INLINE inline
#endif

// Lives only inside an uninterrupted TRI2 run. Offsets refer to mBufVbo;
// callers reset on a pipeline/LOD change, buffer flush, or end of the run.
struct ModernTri2PackedReuse {
    enum { kMaterialInputs = 7 };

    bool valid;
    uint32_t generation;
    uint32_t generations[256];
    size_t starts[256];
    uint16_t indexedRows[256];
    size_t end;
    size_t stride;
    uint32_t firstWBits;
    size_t materialOffsets[2][kMaterialInputs];

    ModernTri2PackedReuse() : valid(false), generation(1) {
        memset(generations, 0, sizeof(generations));
    }

    void Reset() {
        valid = false;
        if (++generation == 0) {
            memset(generations, 0, sizeof(generations));
            generation = 1;
        }
    }

    void Capture(const uint8_t sourceIndices[3], const size_t sourceStarts[3],
                 size_t sourceEnd, uint32_t sourceWBits) {
        if (sourceStarts[0] >= sourceStarts[1] ||
            sourceStarts[1] >= sourceStarts[2] || sourceStarts[2] >= sourceEnd) {
            Reset();
            return;
        }
        const size_t width = sourceStarts[1] - sourceStarts[0];
        if (width > 32 || sourceStarts[2] - sourceStarts[1] != width ||
            sourceEnd - sourceStarts[2] != width) {
            Reset();
            return;
        }
        if (valid && (stride != width || sourceStarts[0] != end)) Reset();
        for (unsigned i = 0; i < 3; ++i) {
            starts[sourceIndices[i]] = sourceStarts[i];
            generations[sourceIndices[i]] = generation;
        }
        end = sourceEnd;
        stride = width;
        firstWBits = sourceWBits;
        valid = true;
    }

    void CaptureMaterials(const float* inputs[2][kMaterialInputs],
                          const float* base, unsigned numInputs, bool alpha) {
        if (!valid) return;
        for (unsigned k = 0; k < 1U + unsigned(alpha); ++k)
            for (unsigned j = 0; j < numInputs; ++j)
                materialOffsets[k][j] = size_t(inputs[k][j] - base);
    }

    bool CanReuse(size_t currentLen, bool pipelineCertified, bool lodSensitive,
                  uint32_t currentWBits) const {
        return valid && pipelineCertified && currentLen == end &&
               (!lodSensitive || currentWBits == firstWBits);
    }

    MODERN_TRI2_INLINE bool ContainsAny(const uint8_t sourceIndices[3]) const {
        return valid && (generations[sourceIndices[0]] == generation ||
                         generations[sourceIndices[1]] == generation ||
                         generations[sourceIndices[2]] == generation);
    }

    bool CopyVertex(uint8_t index, float*& output, const float* base) const {
        if (!valid || generations[index] != generation) return false;
        memcpy(output, base + starts[index], stride * sizeof(float));
        output += stride;
        return true;
    }

    bool FindIndexedVertex(uint8_t index, uint16_t& row) const {
        if (!valid || generations[index] != generation) return false;
        row = indexedRows[index];
        return true;
    }

    // The indexed stream may append zero, one, two, or three rows. Preserve
    // older rows in this certificate instead of requiring three new copies.
    MODERN_TRI2_INLINE void CaptureIndexed(const uint8_t sourceIndices[3], const uint16_t rows[3],
                        size_t sourceBegin, size_t sourceEnd, size_t width,
                        uint32_t sourceWBits) {
        if (width == 0 || width > 32) {
            Reset();
            return;
        }
        if (valid && (stride != width || sourceBegin != end)) Reset();
        for (unsigned i = 0; i < 3; ++i) {
            indexedRows[sourceIndices[i]] = rows[i];
            generations[sourceIndices[i]] = generation;
        }
        end = sourceEnd;
        stride = width;
        firstWBits = sourceWBits;
        valid = true;
    }

    void RestoreMaterials(const float* inputs[2][kMaterialInputs],
                          const float* base, unsigned numInputs, bool alpha) const {
        for (unsigned k = 0; k < 1U + unsigned(alpha); ++k)
            for (unsigned j = 0; j < numInputs; ++j)
                inputs[k][j] = base + materialOffsets[k][j];
    }
};

// Records the original triangle order separately from its missing packed rows.
// Source corners may repeat even on the first triangle of a run.
struct ModernIndexedTrianglePlan {
    uint16_t rows[3];
    uint8_t sourceCorners[3];
    unsigned count;

    MODERN_TRI2_INLINE void Prepare(const ModernTri2PackedReuse& cache, bool reuse,
                 const uint8_t sourceIndices[3], size_t firstRow) {
        // Most scene triangles have three new, distinct corners. Avoid the
        // general lookup/duplicate loop and pointer compaction in that case.
        if ((!reuse || !cache.ContainsAny(sourceIndices)) &&
            sourceIndices[0] != sourceIndices[1] && sourceIndices[0] != sourceIndices[2] &&
            sourceIndices[1] != sourceIndices[2]) {
            rows[0] = uint16_t(firstRow);
            rows[1] = uint16_t(firstRow + 1);
            rows[2] = uint16_t(firstRow + 2);
            sourceCorners[0] = 0;
            sourceCorners[1] = 1;
            sourceCorners[2] = 2;
            count = 3;
            return;
        }
        count = 0;
        for (unsigned i = 0; i < 3; ++i) {
            if (reuse && cache.FindIndexedVertex(sourceIndices[i], rows[i])) continue;
            unsigned previous = 0;
            while (previous < i && sourceIndices[previous] != sourceIndices[i]) ++previous;
            if (previous < i) {
                rows[i] = rows[previous];
                continue;
            }
            rows[i] = uint16_t(firstRow + count);
            sourceCorners[count++] = uint8_t(i);
        }
    }
};

#undef MODERN_TRI2_INLINE
