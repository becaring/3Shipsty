"""Modern-only projection: defer lit/fog attributes until a triangle survives culling."""

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
    int16_t fogMul, fogOffset;
    uint8_t references;
};
struct XboxDeferredVertex {
    F3DVtx source;
    XboxDeferredContext* context;
};
// MODERN DEFERRED LIT FOG END
'''

SOURCE_METHODS = r'''
// MODERN DEFERRED LIT FOG BEGIN
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
            context->lights[i].color[c] = (float)mRsp->current_lights[i].l.col[c];
        }
    }
    context->scaleS = mRsp->texture_scaling_factor.s;
    context->scaleT = mRsp->texture_scaling_factor.t;
    context->fogMul = mRsp->fog_mul;
    context->fogOffset = mRsp->fog_offset;

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
    d->u = U;
    d->v = V;
    int r = context->ambient[0], g = context->ambient[1], b = context->ambient[2];
    const float normal[3] = { (float)vn->n[0], (float)vn->n[1], (float)vn->n[2] };
    for (int i = 0; i < context->count; ++i) {
        float intensity = 0;
        intensity += normal[0] * context->lights[i].coeff[0];
        intensity += normal[1] * context->lights[i].coeff[1];
        intensity += normal[2] * context->lights[i].coeff[2];
        intensity /= 127.0f;
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
        return source
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
    return source


def _position_only_replay(source):
    marker = '// MODERN DEFERRED POSITION REPLAY BEGIN'
    if marker in source:
        return source
    start = source.index('void Interpreter::GfxSpVertex(')
    end = source.index('void Interpreter::GfxSpModifyVertex(', start)
    vertex = source[start:end]
    vertex = _once(vertex, '        float world_pos[3] = { 0.0 };', '''        // MODERN DEFERRED POSITION REPLAY BEGIN
        // This path is reached only after a disjoint source and a successful
        // VMX transform. Pending vertices get their UV and color from the
        // captured source/context at materialization; only position and clip
        // may be observed before then.
        if (mXboxDeferredReplay && shipyardVectorPositions) {
            if (shipyardTransformBatch && !mFbActive) {
                if (!shipyardAspectReady) {
                    shipyardAspectDenominator = (float)mCurDimensions.width / (float)mCurDimensions.height;
                    shipyardAspectReady = true;
                }
                x = x * (4.0f / 3.0f) / shipyardAspectDenominator;
            } else {
                x = AdjXForAspectRatio(x);
            }
            d->x = x;
            d->y = y;
            d->z = z;
            d->w = w;
            continue;
        }
        // MODERN DEFERRED POSITION REPLAY END
        float world_pos[3] = { 0.0 };''')
    return source[:start] + vertex + source[end:]


def transform(source):
    if '// MODERN DEFERRED LIT FOG BEGIN' in source:
        return _triangle_guard(_position_only_replay(source))
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
             '    mXboxDeferredReplay = false;\n' + \
             '    mXboxContextProbeCapture = false;\n' + \
             '    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;' + source[brace + 1:]
    run = source.index('void Interpreter::Run(Gfx* commands,')
    run_brace = source.index('{', run)
    source = source[:run_brace + 1] + '\n    mXboxContextProbeCapture = ModernFrameProfile::CaptureTrianglePipeline();\n' + \
             '    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;' + source[run_brace + 1:]
    return _triangle_guard(_position_only_replay(source))
