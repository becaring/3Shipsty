"""Bounded, opt-in exact-input census for interpolated vertex-load reuse."""

CORE = r'''
// MODERN VERTEX REUSE CENSUS BEGIN
enum {
    ModernVertexReuseMaxReplays = 8,
    ModernVertexReuseBucketCount = 4096,
    ModernVertexReuseArenaSize = 1024 * 1024,
    ModernVertexReuseProbeLimit = 64
};

struct ModernVertexReuseCounts {
    uint32_t eligibleLoads, eligibleVertices;
    uint32_t fullHitLoads, fullHitVertices;
    uint32_t matrixOnlyMissLoads, matrixOnlyMissVertices;
    uint32_t matrixOneUlpMissLoads, matrixOneUlpMissVertices;
    uint32_t matrixLargerMissLoads, matrixLargerMissVertices;
    uint32_t attributeSourceMissLoads, attributeSourceMissVertices;
    // No candidate for this source address from an earlier replay, including replay zero.
    uint32_t firstSeenLoads, firstSeenVertices;
    // May also count a classified miss that could not be inserted into the arena.
    uint32_t capacityMissLoads, capacityMissVertices;
};

struct ModernVertexReuseCensus {
    uint32_t magic, version;
    volatile uint32_t request, active, complete;
    uint32_t replayCount, currentReplay, captureSerial;
    uint32_t arenaBytes, entryCount, arenaOverflow, probeOverflow, rejectedInputs;
    ModernVertexReuseCounts replay[ModernVertexReuseMaxReplays];
    uint32_t buckets[ModernVertexReuseBucketCount];
    unsigned char arena[ModernVertexReuseArenaSize];
};

struct ModernVertexReuseEntry {
    uint32_t next, sourceId, vertexCount, attributeBytes, firstReplay, recordBytes;
    // Contiguous key: matrix bits, attribute bits, then the original source bytes.
};

extern "C" {
ModernVertexReuseCensus gModernVertexReuseCensus = { 0x56545843u, 1 };

void ModernVertexReuseBeginBatch(unsigned replayCount) {
    ModernVertexReuseCensus& c = gModernVertexReuseCensus;
    c.active = 0;
    if (!c.request) return;
    c.request = 0;
    c.complete = 0;
    c.replayCount = replayCount;
    c.currentReplay = ModernVertexReuseMaxReplays;
    ++c.captureSerial;
    c.arenaBytes = c.entryCount = c.arenaOverflow = c.probeOverflow = c.rejectedInputs = 0;
    memset(c.replay, 0, sizeof(c.replay));
    memset(c.buckets, 0, sizeof(c.buckets));
    c.active = 1;
}

void ModernVertexReuseBeginReplay(unsigned replayIndex) {
    ModernVertexReuseCensus& c = gModernVertexReuseCensus;
    if (c.active) c.currentReplay = replayIndex;
}

void ModernVertexReuseEndBatch() {
    ModernVertexReuseCensus& c = gModernVertexReuseCensus;
    if (!c.active) return;
    c.active = 0;
    c.complete = 1;
}
}

static unsigned ModernVertexReuseBucket(uint32_t sourceId) {
    return (sourceId >> 4) & (ModernVertexReuseBucketCount - 1);
}

static bool ModernVertexReuseSameAttributes(const ModernVertexReuseEntry* entry,
                                           unsigned vertices, const void* source,
                                           const void* attributes, unsigned attributeBytes) {
    if (entry->vertexCount != vertices || entry->attributeBytes != attributeBytes) return false;
    const unsigned char* key = reinterpret_cast<const unsigned char*>(entry + 1);
    return memcmp(key + 64, attributes, attributeBytes) == 0 &&
           memcmp(key + 64 + attributeBytes, source, vertices * 16) == 0;
}

static bool ModernVertexReuseSameMatrix(const ModernVertexReuseEntry* entry, const void* matrix) {
    return memcmp(entry + 1, matrix, 64) == 0;
}

static bool ModernVertexReuseMatrixWithinOneUlp(const ModernVertexReuseEntry* entry, const void* matrix) {
    const unsigned char* oldBits = reinterpret_cast<const unsigned char*>(entry + 1);
    const unsigned char* newBits = static_cast<const unsigned char*>(matrix);
    for (unsigned i = 0; i < 16; ++i) {
        uint32_t a, b;
        memcpy(&a, oldBits + i * 4, 4);
        memcpy(&b, newBits + i * 4, 4);
        if (a == b) continue;
        if ((a & 0x7f800000u) == 0x7f800000u || (b & 0x7f800000u) == 0x7f800000u) return false;
        a = a & 0x80000000u ? ~a : a | 0x80000000u;
        b = b & 0x80000000u ? ~b : b | 0x80000000u;
        if ((a > b ? a - b : b - a) > 1) return false;
    }
    return true;
}

static void ModernVertexReuseRecord(uint32_t sourceId, unsigned vertices, const void* source,
                                    const void* matrix, const void* attributes, unsigned attributeBytes) {
    ModernVertexReuseCensus& c = gModernVertexReuseCensus;
    if (!c.active) return;
    if (c.currentReplay >= c.replayCount || c.currentReplay >= ModernVertexReuseMaxReplays ||
        !vertices || vertices > 64 || !source || !matrix || !attributes ||
        attributeBytes > 800 || (attributeBytes & 3)) {
        ++c.rejectedInputs;
        return;
    }
    ModernVertexReuseCounts& count = c.replay[c.currentReplay];
    ++count.eligibleLoads;
    count.eligibleVertices += vertices;
    const unsigned bucket = ModernVertexReuseBucket(sourceId);
    unsigned next = c.buckets[bucket], probes = 0;
    bool duplicate = false, priorSource = false, priorAttributes = false, nearMatrix = false;
    while (next && probes < ModernVertexReuseProbeLimit) {
        const ModernVertexReuseEntry* entry =
            reinterpret_cast<const ModernVertexReuseEntry*>(c.arena + next - 1);
        ++probes;
        next = entry->next;
        if (entry->sourceId != sourceId) continue;
        const bool previousReplay = entry->firstReplay < c.currentReplay;
        priorSource |= previousReplay;
        if (!ModernVertexReuseSameAttributes(entry, vertices, source, attributes, attributeBytes)) continue;
        priorAttributes |= previousReplay;
        if (!ModernVertexReuseSameMatrix(entry, matrix)) {
            if (previousReplay) nearMatrix |= ModernVertexReuseMatrixWithinOneUlp(entry, matrix);
            continue;
        }
        duplicate = true;
        if (previousReplay) {
            ++count.fullHitLoads;
            count.fullHitVertices += vertices;
            return;
        }
    }
    if (next) {
        // A bounded search cannot certify a miss beyond the visited candidates.
        ++c.probeOverflow;
        ++count.capacityMissLoads;
        count.capacityMissVertices += vertices;
        return;
    }
    if (priorAttributes) {
        ++count.matrixOnlyMissLoads;
        count.matrixOnlyMissVertices += vertices;
        if (nearMatrix) {
            ++count.matrixOneUlpMissLoads;
            count.matrixOneUlpMissVertices += vertices;
        } else {
            ++count.matrixLargerMissLoads;
            count.matrixLargerMissVertices += vertices;
        }
    } else if (priorSource) {
        ++count.attributeSourceMissLoads;
        count.attributeSourceMissVertices += vertices;
    } else {
        ++count.firstSeenLoads;
        count.firstSeenVertices += vertices;
    }
    if (duplicate) return;
    const unsigned bytes = sizeof(ModernVertexReuseEntry) + 64 + attributeBytes + vertices * 16;
    if (bytes > ModernVertexReuseArenaSize - c.arenaBytes) {
        ++c.arenaOverflow;
        ++count.capacityMissLoads;
        count.capacityMissVertices += vertices;
        return;
    }
    const unsigned offset = c.arenaBytes;
    ModernVertexReuseEntry* entry = reinterpret_cast<ModernVertexReuseEntry*>(c.arena + offset);
    entry->next = c.buckets[bucket];
    entry->sourceId = sourceId;
    entry->vertexCount = vertices;
    entry->attributeBytes = attributeBytes;
    entry->firstReplay = c.currentReplay;
    entry->recordBytes = bytes;
    unsigned char* key = reinterpret_cast<unsigned char*>(entry + 1);
    memcpy(key, matrix, 64);
    memcpy(key + 64, attributes, attributeBytes);
    memcpy(key + 64 + attributeBytes, source, vertices * 16);
    c.arenaBytes += bytes;
    ++c.entryCount;
    c.buckets[bucket] = offset + 1;
}
// MODERN VERTEX REUSE CENSUS END
'''


CAPTURE = r'''
static __declspec(noinline) void ModernVertexReuseCapture(const XboxDeferredContext* context,
                                                         const F3DVtx* vertices, size_t n_vertices,
                                                         const void* matrix, bool framebuffer,
                                                         unsigned width, unsigned height) {
        uint32_t attributes[8 + MAX_LIGHTS * 6];
        attributes[0] = context->count;
        attributes[1] = (uint32_t(context->scaleS) << 16) | context->scaleT;
        memcpy(&attributes[2], &context->fogMul, sizeof(float));
        memcpy(&attributes[3], &context->fogOffset, sizeof(float));
        attributes[4] = (uint32_t(context->ambient[0]) << 16) |
            (uint32_t(context->ambient[1]) << 8) | context->ambient[2];
        attributes[5] = framebuffer ? 1 : 0;
        attributes[6] = 0;
        if (!framebuffer) {
            const float aspect = (float)width / (float)height;
            memcpy(&attributes[6], &aspect, sizeof(float));
        }
        attributes[7] = context->floatLighting ? 1 : 0;
        static_assert(sizeof(XboxDeferredLight) == 6 * sizeof(uint32_t), "reuse light key layout");
        memcpy(attributes + 8, context->lights, context->count * sizeof(XboxDeferredLight));
        ModernVertexReuseRecord(uint32_t(uintptr_t(vertices)), (unsigned)n_vertices, vertices,
                               matrix, attributes, (8 + context->count * 6) * sizeof(uint32_t));
}
'''


HOOK = r'''
    // MODERN VERTEX REUSE CENSUS LOAD BEGIN
    if (gModernVertexReuseCensus.active && context->nearest &&
        Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx),
                                             mXboxDeferredVertices, sizeof(mXboxDeferredVertices)) &&
        Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx),
                                             mXboxDeferredContexts, sizeof(mXboxDeferredContexts))) {
        ModernVertexReuseCapture(context, vertices, n_vertices, mRsp->MP_matrix, mFbActive,
                                 mCurDimensions.width, mCurDimensions.height);
    }
    // MODERN VERTEX REUSE CENSUS LOAD END
'''


def _replace_block(source, begin, end, replacement):
    first = source.index(begin)
    last = source.index(end, first) + len(end)
    return source[:first] + replacement.strip('\n') + source[last:]


def transform(source):
    begin = '// MODERN VERTEX REUSE CENSUS BEGIN'
    end = '// MODERN VERTEX REUSE CENSUS END'
    core = CORE.replace(end, CAPTURE + end)
    if begin in source:
        source = _replace_block(source, begin, end, core)
    else:
        anchor = 'void Interpreter::XboxDiscardVertex(size_t index) {'
        if source.count(anchor) != 1:
            raise ValueError('vertex reuse census requires the deferred vertex projection')
        source = source.replace(anchor, core + '\n' + anchor, 1)
    begin = '    // MODERN VERTEX REUSE CENSUS LOAD BEGIN'
    end = '    // MODERN VERTEX REUSE CENSUS LOAD END'
    if begin in source:
        return _replace_block(source, begin, end, HOOK)
    anchor = '''        GfxSpVertex(n_vertices, dest_index, vertices);
    }
'''
    if source.count(anchor) != 1:
        raise ValueError('vertex reuse census deferred load anchor changed')
    return source.replace(anchor, anchor + HOOK, 1)
