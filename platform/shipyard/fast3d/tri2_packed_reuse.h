#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

// Lives only for the two GfxSpTri1 calls inside one TRI2 command. Offsets refer
// to mBufVbo, and callers discard the certificate whenever that buffer flushes.
struct ModernTri2PackedReuse {
    enum { kMaterialInputs = 7 };

    bool valid;
    uint8_t indices[3];
    size_t starts[3];
    size_t end;
    size_t stride;
    uint32_t firstWBits;
    size_t materialOffsets[2][kMaterialInputs];

    void Reset() { valid = false; }

    void Capture(const uint8_t sourceIndices[3], const size_t sourceStarts[3],
                 size_t sourceEnd, uint32_t sourceWBits) {
        valid = false;
        if (sourceStarts[0] >= sourceStarts[1] ||
            sourceStarts[1] >= sourceStarts[2] || sourceStarts[2] >= sourceEnd)
            return;
        const size_t width = sourceStarts[1] - sourceStarts[0];
        if (width > 32 || sourceStarts[2] - sourceStarts[1] != width ||
            sourceEnd - sourceStarts[2] != width)
            return;
        memcpy(indices, sourceIndices, sizeof(indices));
        memcpy(starts, sourceStarts, sizeof(starts));
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

    bool CopyVertex(uint8_t index, float*& output, const float* base) const {
        for (unsigned i = 0; i < 3; ++i) {
            if (indices[i] != index) continue;
            memcpy(output, base + starts[i], stride * sizeof(float));
            output += stride;
            return true;
        }
        return false;
    }

    void RestoreMaterials(const float* inputs[2][kMaterialInputs],
                          const float* base, unsigned numInputs, bool alpha) const {
        for (unsigned k = 0; k < 1U + unsigned(alpha); ++k)
            for (unsigned j = 0; j < numInputs; ++j)
                inputs[k][j] = base + materialOffsets[k][j];
    }
};
