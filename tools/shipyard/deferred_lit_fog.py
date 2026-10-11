"""Modern-only projection: defer lit/fog attributes until a triangle survives culling."""

from vertex_reuse_census import transform as vertex_reuse_census

HEADER_TYPES = r'''
// MODERN DEFERRED LIT FOG BEGIN
struct XboxDeferredLight {
    float coeff[3];
    float color[3];
};
struct XboxDeferredContext {
    XboxDeferredLight lights[MAX_LIGHTS];
    uint8_t ambient[3];
    uint8_t count;
    uint16_t scaleS, scaleT;
    // Exact signed-short values in the form every materialized vertex consumes.
    float fogMul, fogOffset;
    uint8_t references;
    // SoH360 4.0.5 lighting form: exact float ambient, bounded coefficients,
    // and one exact RGB result for the most recent normal of this snapshot.
    float ambientFloat[3];
    bool floatLighting;
    // Rounding mode when the snapshot was taken, where upstream divides.
    bool nearest;
    uint32_t normalKey;
    uint32_t normalCacheSerial;
    uint8_t normalRgb[3];
    bool opposedLastPair;
};
struct XboxDeferredNormalEntry {
    XboxDeferredContext* context;
    uint32_t serial, normal;
    uint8_t rgb[3];
};
struct XboxDeferredVertex {
    F3DVtx source;
    XboxDeferredContext* context;
};
// MODERN DEFERRED LIT FOG END
'''

SOURCE_METHODS = r'''
// MODERN DEFERRED LIT FOG BEGIN
extern "C" volatile unsigned gModernNormalCacheControl[2] = { 1, 0 };

void Interpreter::XboxDiscardVertex(size_t index) {
    if (index >= MAX_VERTICES) return;
    XboxDeferredVertex& pending = mXboxDeferredVertices[index];
    if (pending.context) {
        --pending.context->references;
        pending.context = NULL;
    }
}

bool Interpreter::XboxTryDeferVertices(size_t n_vertices, size_t dest_index, const F3DVtx* vertices) {
    if (mXboxDeferredReplay) return false;
    if (!vertices || !n_vertices || n_vertices > MAX_VERTICES ||
        dest_index > MAX_VERTICES || n_vertices > MAX_VERTICES - dest_index) {
        return false;
    }
    if (!Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx), mRsp, sizeof(*mRsp))) {
        // A command may reinterpret earlier loaded-vertex bytes as its
        // source. Restore every pending slot before the eager fallback reads
        // any of the RSP. This branch is outside the normal disjoint path.
        for (size_t i = 0; i < MAX_VERTICES; ++i) XboxMaterializeVertex(i);
        for (size_t i = 0; i < n_vertices; ++i) XboxDiscardVertex(dest_index + i);
        return false;
    }
    for (size_t i = 0; i < n_vertices; ++i) XboxDiscardVertex(dest_index + i);
    if ((mRsp->geometry_mode & (G_LIGHTING | G_FOG | G_TEXTURE_GEN)) != (G_LIGHTING | G_FOG) ||
        (mRsp->geometry_mode & G_LIGHTING_POSITIONAL) ||
        mRsp->current_num_lights == 0 || mRsp->current_num_lights > MAX_LIGHTS + 1) {
        return false;
    }
    XboxDeferredContext* context = NULL;
    for (size_t i = 0; i < MAX_VERTICES; ++i) {
        if (!mXboxDeferredContexts[i].references) {
            context = &mXboxDeferredContexts[i];
            break;
        }
    }
    if (mXboxContextProbeCapture) {
        // Include exhausted searches; no counter work occurs inside the scan.
        const unsigned scanned = context ? (unsigned)(context - mXboxDeferredContexts) + 1 : MAX_VERTICES;
        ++mXboxContextSearchAttempts;
        mXboxContextSlotsScanned += scanned;
        if (scanned > mXboxContextMaxScan) mXboxContextMaxScan = scanned;
    }
    if (!context) return false;

    // The eager path refreshes these on its first lit vertex.
    if (mRsp->lights_changed) {
        for (int i = 0; i < mRsp->current_num_lights - 1; ++i)
            CalculateNormalDir(&mRsp->current_lights[i].l, mRsp->current_lights_coeffs[i]);
        CalculateNormalDir(&mRsp->lookat[0], mRsp->current_lookat_coeffs[0]);
        CalculateNormalDir(&mRsp->lookat[1], mRsp->current_lookat_coeffs[1]);
        mRsp->lights_changed = false;
    }
    context->count = mRsp->current_num_lights - 1;
    for (int c = 0; c < 3; ++c) context->ambient[c] = mRsp->current_lights[context->count].l.col[c];
    for (int i = 0; i < context->count; ++i) {
        for (int c = 0; c < 3; ++c) {
            context->lights[i].coeff[c] = mRsp->current_lights_coeffs[i][c];
            context->lights[i].color[c] = Shipyard::Fast3D::LightByteFloat(mRsp->current_lights[i].l.col[c]);
        }
    }
    context->scaleS = mRsp->texture_scaling_factor.s;
    context->scaleT = mRsp->texture_scaling_factor.t;
    context->fogMul = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_mul);
    context->fogOffset = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_offset);
    // |normal| <= 128 and |coeff| <= 16 bound each intensity below 49, so every
    // channel stays a finite nonnegative integer below 2^24. There, a float sum
    // truncated after each light equals the int compound assignment. NaN and
    // larger coefficients keep the int path.
    context->floatLighting = true;
    for (int i = 0; i < context->count; ++i)
        for (int c = 0; c < 3; ++c)
            if (!(context->lights[i].coeff[c] >= -16.0f && context->lights[i].coeff[c] <= 16.0f))
                context->floatLighting = false;
    for (int c = 0; c < 3; ++c) context->ambientFloat[c] = Shipyard::Fast3D::LightByteFloat(context->ambient[c]);
    context->normalKey = 0xffffffffu;
    context->normalCacheSerial = ++mXboxNormalCacheSerial;
    if (!context->normalCacheSerial) {
        memset(mXboxNormalCache, 0, sizeof(mXboxNormalCache));
        context->normalCacheSerial = ++mXboxNormalCacheSerial;
    }
    // Upstream divides each intensity by 127 here, while loading. Under
    // round-to-nearest the double product is that exact quotient (SoH360
    // 4.0.5 DivideNormal127) without a non-pipelined fdiv per light and vertex.
    context->nearest = Shipyard::Fast3D::NearestRounding();

    // Reuse the authoritative VMX/aspect/clip transform with attributes off.
    struct ReplayGuard {
        Interpreter* self;
        uint32_t mode;
        ReplayGuard(Interpreter* s) : self(s), mode(s->mRsp->geometry_mode) {
            self->mXboxDeferredReplay = true;
            self->mRsp->geometry_mode &= ~(G_LIGHTING | G_FOG);
        }
        ~ReplayGuard() {
            self->mRsp->geometry_mode = mode;
            self->mXboxDeferredReplay = false;
        }
    };
    {
        ReplayGuard guard(this);
        GfxSpVertex(n_vertices, dest_index, vertices);
    }
    for (size_t i = 0; i < n_vertices; ++i) {
        XboxDeferredVertex& pending = mXboxDeferredVertices[dest_index + i];
        pending.source = vertices[i];
        pending.context = context;
    }
    context->references = (uint8_t)n_vertices;
    return true;
}

void Interpreter::XboxMaterializeVertex(size_t index) {
    if (index >= MAX_VERTICES) return;
    XboxDeferredVertex& pending = mXboxDeferredVertices[index];
    XboxDeferredContext* context = pending.context;
    if (!context) return;
    LoadedVertex* d = &mRsp->loaded_vertices[index];
    const F3DVtx_t* v = &pending.source.v;
    const F3DVtx_tn* vn = &pending.source.n;
    short U = v->tc[0] * context->scaleS >> 16;
    short V = v->tc[1] * context->scaleT >> 16;
    // Exact table values avoid Xenon's store/reload integer-to-float moves.
    d->u = Shipyard::Fast3D::SignedShortFloat(U);
    d->v = Shipyard::Fast3D::SignedShortFloat(V);
    if (context->floatLighting) {
        // Channels stay in FPRs (fctidz/fcfid truncation) and bytes leave via
        // stfiwx words read after the fog math, instead of an int<->float
        // store/reload per light and channel. Lit RGB depends only on the
        // normal within one snapshot, so a repeated normal reuses its bytes.
        Shipyard::Fast3D::DeferredVertexBytes bytes;
        const uint32_t normalKey = (uint32_t(uint8_t(vn->n[0])) << 16) |
            (uint32_t(uint8_t(vn->n[1])) << 8) | uint8_t(vn->n[2]);
        bool reuse = normalKey == context->normalKey;
        XboxDeferredNormalEntry* normalEntry = NULL;
        if (!reuse && mXboxNormalCacheEnabled && context->nearest) {
            normalEntry = &mXboxNormalCache[(normalKey * 2654435761u) >> 26];
            if (normalEntry->context == context && normalEntry->serial == context->normalCacheSerial &&
                normalEntry->normal == normalKey) {
                for (unsigned channel = 0; channel < 3; ++channel)
                    context->normalRgb[channel] = normalEntry->rgb[channel];
                context->normalKey = normalKey;
                reuse = true;
            }
        }
        if (!reuse) {
            float r = context->ambientFloat[0], g = context->ambientFloat[1], b = context->ambientFloat[2];
            const float normal[3] = { Shipyard::Fast3D::NormalByteFloat(vn->n[0]),
                                      Shipyard::Fast3D::NormalByteFloat(vn->n[1]),
                                      Shipyard::Fast3D::NormalByteFloat(vn->n[2]) };
            for (int i = 0; i < context->count; ++i) {
                float intensity = 0;
                intensity += normal[0] * context->lights[i].coeff[0];
                intensity += normal[1] * context->lights[i].coeff[1];
                intensity += normal[2] * context->lights[i].coeff[2];
                intensity = Shipyard::Fast3D::DivideNormal127(intensity, context->nearest);
                if (intensity > 0.0f) {
                    r = Shipyard::Fast3D::TruncateLightChannel(r + intensity * context->lights[i].color[0]);
                    g = Shipyard::Fast3D::TruncateLightChannel(g + intensity * context->lights[i].color[1]);
                    b = Shipyard::Fast3D::TruncateLightChannel(b + intensity * context->lights[i].color[2]);
                }
            }
            bytes.Store(0, Shipyard::Fast3D::VertexColorLimit(r));
            bytes.Store(1, Shipyard::Fast3D::VertexColorLimit(g));
            bytes.Store(2, Shipyard::Fast3D::VertexColorLimit(b));
        }
        float w = d->w;
        if (fabsf(w) < 0.001f) w = 0.001f;
        float winv = 1.0f / w;
        if (winv < 0.0f) winv = std::numeric_limits<int16_t>::max();
        float fog_z = d->z * winv * context->fogMul + context->fogOffset;
        fog_z = Ship::Math::clamp(fog_z, 0.0f, 255.0f);
        bytes.Store(3, fog_z);
        if (!reuse) {
            context->normalRgb[0] = bytes.Load(0);
            context->normalRgb[1] = bytes.Load(1);
            context->normalRgb[2] = bytes.Load(2);
            context->normalKey = normalKey;
            if (normalEntry) {
                normalEntry->context = context;
                normalEntry->serial = context->normalCacheSerial;
                normalEntry->normal = normalKey;
                for (unsigned channel = 0; channel < 3; ++channel)
                    normalEntry->rgb[channel] = context->normalRgb[channel];
            }
        }
        d->color.r = context->normalRgb[0];
        d->color.g = context->normalRgb[1];
        d->color.b = context->normalRgb[2];
        d->color.a = bytes.Load(3);
        XboxDiscardVertex(index);
        return;
    }
    int r = context->ambient[0], g = context->ambient[1], b = context->ambient[2];
    const float normal[3] = { Shipyard::Fast3D::NormalByteFloat(vn->n[0]),
                              Shipyard::Fast3D::NormalByteFloat(vn->n[1]),
                              Shipyard::Fast3D::NormalByteFloat(vn->n[2]) };
    for (int i = 0; i < context->count; ++i) {
        float intensity = 0;
        intensity += normal[0] * context->lights[i].coeff[0];
        intensity += normal[1] * context->lights[i].coeff[1];
        intensity += normal[2] * context->lights[i].coeff[2];
        intensity = Shipyard::Fast3D::DivideNormal127(intensity, context->nearest);
        if (intensity > 0.0f) {
            r += intensity * context->lights[i].color[0];
            g += intensity * context->lights[i].color[1];
            b += intensity * context->lights[i].color[2];
        }
    }
    d->color.r = r > 255 ? 255 : r;
    d->color.g = g > 255 ? 255 : g;
    d->color.b = b > 255 ? 255 : b;
    float w = d->w;
    if (fabsf(w) < 0.001f) w = 0.001f;
    float winv = 1.0f / w;
    if (winv < 0.0f) winv = std::numeric_limits<int16_t>::max();
    float fog_z = d->z * winv * context->fogMul + context->fogOffset;
    fog_z = Ship::Math::clamp(fog_z, 0.0f, 255.0f);
    d->color.a = fog_z;
    XboxDiscardVertex(index);
}

void Interpreter::XboxTakeContextSearchCounts(unsigned* attempts, unsigned* slots, unsigned* maximum) {
    *attempts = mXboxContextSearchAttempts;
    *slots = mXboxContextSlotsScanned;
    *maximum = mXboxContextMaxScan;
    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;
}
// MODERN DEFERRED LIT FOG END
'''


def _once(source, old, new):
    if old not in source:
        raise ValueError('deferred lit/fog projection anchor changed: ' + old[:90])
    return source.replace(old, new, 1)


def _opposed_lighting(source):
    if 'context->opposedLastPair =' in source:
        return source
    nearest = '    context->nearest = Shipyard::Fast3D::NearestRounding();'
    if nearest not in source:
        nearest = '        context->nearest = nearest;'
    setup = '''
    // Nearest rounding makes a nonzero dot with exact negated coefficients
    // the exact negative. Only one of the final two lights can contribute.
    context->opposedLastPair = context->nearest && context->floatLighting && context->count >= 2;
    if (context->opposedLastPair) {
        const int last = context->count - 1;
        for (int c = 0; c < 3; ++c) {
            uint32_t a, b;
            memcpy(&a, &context->lights[last - 1].coeff[c], sizeof(a));
            memcpy(&b, &context->lights[last].coeff[c], sizeof(b));
            if ((a ^ b) != 0x80000000u) context->opposedLastPair = false;
        }
    }
'''
    source = _once(source, nearest, nearest + setup)
    old = '''                intensity = Shipyard::Fast3D::DivideNormal127(intensity, context->nearest);
                if (intensity > 0.0f) {
                    r = Shipyard::Fast3D::TruncateLightChannel(r + intensity * context->lights[i].color[0]);
                    g = Shipyard::Fast3D::TruncateLightChannel(g + intensity * context->lights[i].color[1]);
                    b = Shipyard::Fast3D::TruncateLightChannel(b + intensity * context->lights[i].color[2]);
                }'''
    new = '''                intensity = Shipyard::Fast3D::DivideNormal127(intensity, context->nearest);
                int colorLight = i;
                // Bounded finite coefficients put the quotient inside (-49,49).
                // Zero and exceptional results keep the original second dot.
                if (context->opposedLastPair && i + 2 == context->count &&
                    intensity != 0.0f && intensity > -49.0f && intensity < 49.0f) {
                    if (intensity < 0.0f) { intensity = -intensity; colorLight = i + 1; }
                    ++i;
                }
                if (intensity > 0.0f) {
                    r = Shipyard::Fast3D::TruncateLightChannel(r + intensity * context->lights[colorLight].color[0]);
                    g = Shipyard::Fast3D::TruncateLightChannel(g + intensity * context->lights[colorLight].color[1]);
                    b = Shipyard::Fast3D::TruncateLightChannel(b + intensity * context->lights[colorLight].color[2]);
                }'''
    return _once(source, old, new)


SOURCE_METHODS = _opposed_lighting(SOURCE_METHODS)


TRIANGLE_MATERIALIZE_GUARD = '''    // MODERN TRIANGLE MATERIALIZATION GUARD BEGIN
    // Most surviving triangles reuse already materialized vertex slots. Keep
    // the authoritative materializer for pending slots and for every other
    // consumer; avoid its call/early-return cost for clean triangle inputs.
    if (vtx1_idx < MAX_VERTICES && mXboxDeferredVertices[vtx1_idx].context)
        XboxMaterializeVertex(vtx1_idx);
    if (vtx2_idx < MAX_VERTICES && mXboxDeferredVertices[vtx2_idx].context)
        XboxMaterializeVertex(vtx2_idx);
    if (vtx3_idx < MAX_VERTICES && mXboxDeferredVertices[vtx3_idx].context)
        XboxMaterializeVertex(vtx3_idx);
    // MODERN TRIANGLE MATERIALIZATION GUARD END'''


def _triangle_guard(source):
    if '// MODERN TRIANGLE MATERIALIZATION GUARD BEGIN' in source:
        return source
    return _once(source,
                 '    XboxMaterializeVertex(vtx1_idx);\n'
                 '    XboxMaterializeVertex(vtx2_idx);\n'
                 '    XboxMaterializeVertex(vtx3_idx);',
                 TRIANGLE_MATERIALIZE_GUARD)


def header(source):
    if '// MODERN DEFERRED LIT FOG BEGIN' in source:
        return _direct_header(source)
    source = _once(source, 'class Interpreter {', HEADER_TYPES + '\nclass Interpreter {')
    source = _once(source, '    void GfxSpVertex(size_t numVertices, size_t destIndex, const F3DVtx* vertices);',
                   '    bool XboxTryDeferVertices(size_t n_vertices, size_t dest_index, const F3DVtx* vertices);\n'
                   '    void XboxDiscardVertex(size_t index);\n'
                   '    void XboxMaterializeVertex(size_t index);\n'
                   '    void XboxTakeContextSearchCounts(unsigned* attempts, unsigned* slots, unsigned* maximum);\n'
                   '    void GfxSpVertex(size_t numVertices, size_t destIndex, const F3DVtx* vertices);')
    source = _once(source, '    GfxTextureCache mTextureCache;',
                   '    GfxTextureCache mTextureCache;\n'
                   '    XboxDeferredVertex mXboxDeferredVertices[MAX_VERTICES];\n'
                   '    XboxDeferredContext mXboxDeferredContexts[MAX_VERTICES];\n'
                   '    bool mXboxDeferredReplay;\n'
                   '    bool mXboxContextProbeCapture;\n'
                   '    unsigned mXboxContextSearchAttempts, mXboxContextSlotsScanned, mXboxContextMaxScan;')
    return _direct_header(source)


def _direct_header(source):
    if 'uint32_t normalCacheSerial;' not in source:
        source = _once(source, '    uint32_t normalKey;', '    uint32_t normalKey;\n    uint32_t normalCacheSerial;')
    if 'struct XboxDeferredNormalEntry' not in source:
        entry = HEADER_TYPES[HEADER_TYPES.index('struct XboxDeferredNormalEntry'):HEADER_TYPES.index('struct XboxDeferredVertex')]
        source = _once(source, 'struct XboxDeferredVertex', entry + 'struct XboxDeferredVertex')
    if 'mXboxNormalCache[64]' not in source:
        source = _once(source, '    bool mXboxDeferredReplay;',
                       '    XboxDeferredNormalEntry mXboxNormalCache[64];\n'
                       '    uint32_t mXboxNormalCacheSerial;\n'
                       '    bool mXboxNormalCacheEnabled;\n    bool mXboxDeferredReplay;')
    if 'bool opposedLastPair;' not in source:
        source = _once(source, '    uint8_t normalRgb[3];',
                       '    uint8_t normalRgb[3];\n    bool opposedLastPair;')
    if 'XboxTransformDeferredPositions(' not in source:
        source = _once(source, '    void GfxSpVertex(size_t numVertices, size_t destIndex, const F3DVtx* vertices);',
                       '    bool XboxTransformDeferredPositions(size_t n_vertices, size_t dest_index, const F3DVtx* vertices, bool nearest);\n'
                       '    void GfxSpVertexEager(size_t n_vertices, size_t dest_index, const F3DVtx* vertices);\n'
                       '    void GfxSpVertex(size_t numVertices, size_t destIndex, const F3DVtx* vertices);')
    if 'mXboxCurrentDeferredContext' not in source:
        source = _once(source, '    bool mXboxDeferredReplay;',
                       '    XboxDeferredContext* mXboxCurrentDeferredContext;\n'
                       '    uint32_t mXboxCurrentDeferredFog;\n'
                       '    bool mXboxDeferredReplay;')
    return source


ASPECT_RECIPROCAL = r'''                const float numerator = x * (4.0f / 3.0f);
                const float magnitude = fabsf(numerator);
                // Binary64 reciprocal/product error is below the distance of
                // a binary32 quotient from a rounding midpoint. Keep extreme
                // values on division so denormals and exceptions stay eager.
                if (modernAspectReciprocalReady && magnitude >= 1.0e-30f && magnitude <= 1.0e30f)
                    x = (float)((double)numerator * modernAspectReciprocal);
                else
                    x = numerator / shipyardAspectDenominator;'''


POSITION_REPLAY = r'''
    // MODERN DEFERRED POSITION REPLAY BATCH BEGIN
    // Only position and clip are observable before deferred materialization.
    // Keep the compact loop ahead of all eager lighting/fog setup.
    if (mXboxDeferredReplay && shipyardVectorPositions) {
        const bool modernAspect = !mFbActive;
        bool modernAspectReciprocalReady = false;
        double modernAspectReciprocal = 0.0;
        LoadedVertex* const modernDestination = &mRsp->loaded_vertices[dest_index];
        if (modernAspect) {
            shipyardAspectDenominator = (float)mCurDimensions.width / (float)mCurDimensions.height;
            modernAspectReciprocalReady = shipyardAspectDenominator >= 0.25f && shipyardAspectDenominator <= 4.0f;
            if (modernAspectReciprocalReady)
                modernAspectReciprocal = 1.0 / (double)shipyardAspectDenominator;
        }
        for (size_t i = 0; i < n_vertices; ++i) {
            LoadedVertex* d = &modernDestination[i];
            float x = shipyardTransformed[i][0];
            if (modernAspect) {
/* ASPECT RECIPROCAL */
            }
            d->x = x;
            d->y = shipyardTransformed[i][1];
            d->z = shipyardTransformed[i][2];
            d->w = shipyardTransformed[i][3];
        }
        // Accepted VMX matrices bound unscaled coordinates below 2^126 and
        // keep w zero or normal. This aspect range also keeps scaled x finite.
        if (!modernAspect || (modernAspectReciprocalReady && shipyardAspectDenominator >= 0.5f))
            Shipyard::Fast3D::ClipFiniteVertices(modernDestination, n_vertices, false);
        else
            Shipyard::Fast3D::ClipVertices(modernDestination, n_vertices, false);
        return;
    }
    // MODERN DEFERRED POSITION REPLAY BATCH END
'''.replace('/* ASPECT RECIPROCAL */', ASPECT_RECIPROCAL)


def _position_only_replay(source):
    if '// MODERN DEFERRED POSITION REPLAY BATCH BEGIN' in source:
        first = source.index('    // MODERN DEFERRED POSITION REPLAY BATCH BEGIN')
        last = source.index('    // MODERN DEFERRED POSITION REPLAY BATCH END', first)
        last = source.index('\n', last) + 1
        return source[:first] + POSITION_REPLAY.lstrip('\n') + source[last:]
    start = source.index('void Interpreter::GfxSpVertex(')
    end = source.index('void Interpreter::GfxSpModifyVertex(', start)
    vertex = source[start:end]
    marker = '        // MODERN DEFERRED POSITION REPLAY BEGIN'
    if marker in vertex:
        first = vertex.index(marker)
        last = vertex.index('        // MODERN DEFERRED POSITION REPLAY END', first)
        last = vertex.index('\n', last) + 1
        vertex = vertex[:first] + vertex[last:]
    vertex = _once(vertex, '    float shipyardAspectDenominator;\n',
                   '    float shipyardAspectDenominator;\n' + POSITION_REPLAY)
    return source[:start] + vertex + source[end:]


def transform(source):
    if '// MODERN DEFERRED LIT FOG BEGIN' in source:
        return vertex_reuse_census(_opposed_lighting(_triangle_guard(_position_only_replay(source))))
    source = _once(source, 'void Interpreter::GfxSpVertex(size_t n_vertices, size_t dest_index, const F3DVtx* vertices) {',
                   SOURCE_METHODS + '\nvoid Interpreter::GfxSpVertex(size_t n_vertices, size_t dest_index, const F3DVtx* vertices) {\n'
                   '    if (XboxTryDeferVertices(n_vertices, dest_index, vertices)) return;')
    source = _once(source, '    SUPPORT_CHECK(where == G_MWO_POINT_ST);',
                   '    SUPPORT_CHECK(where == G_MWO_POINT_ST);\n'
                   '    XboxMaterializeVertex(vtx_idx);')
    source = _once(source, '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);',
                   '    XboxMaterializeVertex(vtx1_idx);\n'
                   '    XboxMaterializeVertex(vtx2_idx);\n'
                   '    XboxMaterializeVertex(vtx3_idx);\n'
                   '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);')
    constructor = source.index('Interpreter::Interpreter() :')
    brace = source.index('{', constructor)
    source = source[:brace + 1] + '\n    memset(mXboxDeferredVertices, 0, sizeof(mXboxDeferredVertices));\n' + \
             '    memset(mXboxDeferredContexts, 0, sizeof(mXboxDeferredContexts));\n' + \
             '    memset(mXboxNormalCache, 0, sizeof(mXboxNormalCache));\n' + \
             '    mXboxNormalCacheSerial = 0;\n    mXboxNormalCacheEnabled = false;\n' + \
             '    mXboxDeferredReplay = false;\n' + \
             '    mXboxContextProbeCapture = false;\n' + \
             '    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;' + source[brace + 1:]
    run = source.index('void Interpreter::Run(Gfx* commands,')
    run_brace = source.index('{', run)
    source = source[:run_brace + 1] + '\n    mXboxContextProbeCapture = ModernFrameProfile::CaptureTrianglePipeline();\n' + \
             '    mXboxNormalCacheEnabled = gModernNormalCacheControl[0] != 0;\n' + \
             '    gModernNormalCacheControl[1] = mXboxNormalCacheEnabled ? 1 : 0;\n' + \
             '    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;' + source[run_brace + 1:]
    return vertex_reuse_census(_triangle_guard(_position_only_replay(source)))


DIRECT_POSITION_PREFIX = r'''
// MODERN DIRECT DEFERRED VERTEX BEGIN
__declspec(noinline) bool Interpreter::XboxTransformDeferredPositions(
    size_t n_vertices, size_t dest_index, const F3DVtx* vertices, bool nearest) {
    EnsureMatrixProduct();
    if (!nearest) return false;
    __declspec(align(16)) float shipyardTransformed[MAX_VERTICES][4];
    Shipyard::Fast3D::TransformPhaseHook shipyardPhaseHook;
    if (sModernVtxHashSample) {
        shipyardPhaseHook.enterVertices = ModernFrameProfile::EnterVtxTransformLoop;
        shipyardPhaseHook.context = sModernVtxHashSample;
        ModernFrameProfile::BeginVtxTransform(*sModernVtxHashSample, (unsigned)n_vertices);
    }
    const bool shipyardVectorPositions = sModernVtxHashSample
        ? Shipyard::Fast3D::TransformPositionsProfiled(
              vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed, false, 16, &shipyardPhaseHook)
        : Shipyard::Fast3D::TransformPositions(vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed);
    if (sModernVtxHashSample) {
        ModernFrameProfile::EndVtxTransform(*sModernVtxHashSample, shipyardVectorPositions);
        sModernVtxHashSample->vmx = shipyardVectorPositions;
    }
    if (!shipyardVectorPositions) return false;
    float shipyardAspectDenominator;
'''


def finalize(source):
    """Run after the VTX phase projection so its existing timing anchors stay intact."""
    source = _opposed_lighting(source)
    if '// MODERN DIRECT DEFERRED VERTEX BEGIN' in source:
        return _direct_position_output(source)
    if '// MODERN VTX HASH PHASE PROFILE BEGIN' not in source:
        raise ValueError('direct deferred vertices require the VTX phase projection first')

    first = source.index('bool Interpreter::XboxTryDeferVertices(')
    last = source.index('void Interpreter::XboxMaterializeVertex(', first)
    deferred = source[first:last]
    deferred = deferred.replace('        return false;',
                                '        mXboxCurrentDeferredContext = NULL;\n        return false;')
    begin = deferred.index('    XboxDeferredContext* context = NULL;')
    end = deferred.index('    // Reuse the authoritative VMX/aspect/clip transform', begin)
    capture = deferred[begin:end]
    capture = capture.replace('    XboxDeferredContext* context = NULL;', '    context = NULL;', 1)
    capture = capture.replace('    if (!context) return false;',
                              '    if (!context) { mXboxCurrentDeferredContext = NULL; return false; }')
    capture = capture.replace('context->nearest = Shipyard::Fast3D::NearestRounding();',
                              'context->nearest = nearest;')
    cached = '''    const bool nearest = Shipyard::Fast3D::NearestRounding();
    const uint32_t fogKey = (uint32_t(uint16_t(mRsp->fog_mul)) << 16) | uint16_t(mRsp->fog_offset);
    XboxDeferredContext* context = mXboxCurrentDeferredContext;
    if (!context || !nearest || !context->nearest || mRsp->lights_changed ||
        context->count + 1 != mRsp->current_num_lights ||
        context->scaleS != mRsp->texture_scaling_factor.s ||
        context->scaleT != mRsp->texture_scaling_factor.t || mXboxCurrentDeferredFog != fogKey ||
        !Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx),
                                              mXboxDeferredVertices, sizeof(mXboxDeferredVertices)) ||
        !Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx),
                                              mXboxDeferredContexts, sizeof(mXboxDeferredContexts))) {
'''
    cached += ''.join('    ' + line if line.strip() else line for line in capture.splitlines(True))
    cached += '''        mXboxCurrentDeferredContext = context;
        mXboxCurrentDeferredFog = fogKey;
    }

'''
    deferred = deferred[:begin] + cached + deferred[end:]
    deferred = _once(deferred,
                     '''    {
        ReplayGuard guard(this);
        if (sModernVtxHashSample) ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashTransform);
        GfxSpVertex(n_vertices, dest_index, vertices);
    }''',
                     '''    if (sModernVtxHashSample)
        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashTransform);
    if (!XboxTransformDeferredPositions(n_vertices, dest_index, vertices, nearest)) {
        ReplayGuard guard(this);
        GfxSpVertexEager(n_vertices, dest_index, vertices);
    }''')
    deferred = _once(deferred, '    context->references = (uint8_t)n_vertices;',
                     '    context->references = (uint8_t)(context->references + n_vertices);')
    source = source[:first] + deferred + source[last:]

    first = source.index('void Interpreter::GfxSpVertex(size_t n_vertices,')
    body = source.index('{', first) + 1
    split = source.index('    EnsureMatrixProduct();', body)
    last = source.index('void Interpreter::GfxSpModifyVertex(', split)
    eager = source[split:last]
    begin = eager.index('    // MODERN DEFERRED POSITION REPLAY BATCH BEGIN')
    end = eager.index('    // MODERN DEFERRED POSITION REPLAY BATCH END', begin)
    end = eager.index('\n', end) + 1
    eager = eager[:begin] + eager[end:]
    eager = _once(eager, '    const bool shipyardVectorEligible = shipyardTransformBatch &&',
                   '    const bool shipyardVectorEligible = shipyardTransformBatch && !mXboxDeferredReplay &&')
    wrapper = source[first:split] + '    GfxSpVertexEager(n_vertices, dest_index, vertices);\n}\n\n'
    wrapper += '__declspec(noinline) void Interpreter::GfxSpVertexEager(\n'
    wrapper += '    size_t n_vertices, size_t dest_index, const F3DVtx* vertices) {\n' + eager
    position = POSITION_REPLAY.replace('MODERN DEFERRED POSITION REPLAY BATCH', 'MODERN DIRECT POSITION BODY')
    position = position.replace('    if (mXboxDeferredReplay && shipyardVectorPositions) {', '    {')
    position = position.replace('        return;', '        return true;')
    helper = DIRECT_POSITION_PREFIX + position + '}\n// MODERN DIRECT DEFERRED VERTEX END\n\n'
    source = source[:first] + helper + wrapper + source[last:]

    constructor = source.index('Interpreter::Interpreter() :')
    initialize = source.index('    mXboxDeferredReplay = false;\n', constructor)
    source = source[:initialize] + '    mXboxCurrentDeferredContext = NULL;\n' + \
             '    mXboxCurrentDeferredFog = 0;\n' + source[initialize:]
    source = _once(source, '    mXboxContextProbeCapture = ModernFrameProfile::CaptureTrianglePipeline();',
                   '    mXboxCurrentDeferredContext = NULL;\n'
                   '    mXboxContextProbeCapture = ModernFrameProfile::CaptureTrianglePipeline();')
    # These copies change colors without setting the upstream lights_changed flag.
    for copy in ('memcpy(mRsp->current_lights + lightidx, data, sizeof(F3DLight));',
                 'memcpy(mRsp->current_lights + (index - F3DEX_G_MV_L0) / 2, data, sizeof(F3DLight_t));'):
        source = _once(source, copy, copy + '\n                mXboxCurrentDeferredContext = NULL;')
    return _direct_position_output(source)


def _direct_position_output(source):
    if '// MODERN DIRECT POSITION OUTPUT' in source:
        return source
    first = source.index('__declspec(noinline) bool Interpreter::XboxTransformDeferredPositions(')
    last = source.index('// MODERN DIRECT DEFERRED VERTEX END', first)
    helper = source[first:last]
    destination = 'LoadedVertex* const modernDestination = &mRsp->loaded_vertices[dest_index];'
    helper = _once(helper, '        ' + destination + '\n', '')
    helper = _once(helper, '    __declspec(align(16)) float shipyardTransformed[MAX_VERTICES][4];',
                   '    // MODERN DIRECT POSITION OUTPUT\n    ' + destination)
    helper = helper.replace('Shipyard::Fast3D::TransformPositionsProfiled(',
                            'Shipyard::Fast3D::TransformPositionsUnalignedProfiled(')
    helper = helper.replace('Shipyard::Fast3D::TransformPositions(',
                            'Shipyard::Fast3D::TransformPositionsUnaligned(')
    helper = _once(helper, 'mRsp->MP_matrix, shipyardTransformed, false, 16, &shipyardPhaseHook)',
                   'mRsp->MP_matrix, modernDestination, false, sizeof(LoadedVertex), &shipyardPhaseHook)')
    helper = _once(helper, 'mRsp->MP_matrix, shipyardTransformed);',
                   'mRsp->MP_matrix, modernDestination, false, sizeof(LoadedVertex));')
    helper = _once(helper, '        for (size_t i = 0; i < n_vertices; ++i) {',
                   '        if (modernAspect) for (size_t i = 0; i < n_vertices; ++i) {')
    helper = _once(helper, '            float x = shipyardTransformed[i][0];',
                   '            float x = d->x;')
    helper = _once(helper, '''            d->y = shipyardTransformed[i][1];
            d->z = shipyardTransformed[i][2];
            d->w = shipyardTransformed[i][3];
''', '')
    return source[:first] + helper + source[last:]
