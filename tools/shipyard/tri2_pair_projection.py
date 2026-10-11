"""Reuse pipeline certificates and packed rows inside uninterrupted TRI2 runs."""


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern TRI2 pair projection anchor changed: ' + old[:100])
    return source.replace(old, new, 1)


def header(source):
    declaration = '    void GfxSpTri1(uint8_t vtx1Idx, uint8_t vtx2Idx, uint8_t vtx3Idx, bool isRect);'
    if 'XboxRunTri2Triangle' not in source:
        source = _once(source, declaration, declaration + '\n'
                       '    __forceinline void XboxRunTri2Triangle(uint8_t vtx1_idx, '
                       'uint8_t vtx2_idx, uint8_t vtx3_idx);')
    if 'mXboxTrianglePairActive' in source:
        return source
    source = _once(source, '#include "fast/lus_gbi.h"',
                   '#include "fast/lus_gbi.h"\n'
                   '#include "fast3d/tri2_packed_reuse.h"')
    return _once(source, '    XboxTrianglePipelineResult mXboxPipelineResult;',
                 '    XboxTrianglePipelineResult mXboxPipelineResult;\n'
                 '    bool mXboxTrianglePairActive;\n'
                 '    bool mXboxTrianglePairPrepared;\n'
                 '    bool mXboxTriangleRunEnabled;\n'
                 '    ModernTri2PackedReuse mXboxPairPacked;')


def _pair_transform(source):
    if '// MODERN TRI2 PAIR CERTIFICATE BEGIN' in source:
        return source
    ctor = source.index('Interpreter::Interpreter() :')
    brace = source.index('{', ctor)
    source = source[:brace + 1] + '\n    mXboxTrianglePairActive = false;\n' + \
             '    mXboxTrianglePairPrepared = false;\n' + \
             '    mXboxTriangleRunEnabled = false;' + source[brace + 1:]
    handler_start = source.index('bool gfx_tri2_handler_f3dex(')
    handler_end = source.index('\n}', handler_start)
    handler = source[handler_start:handler_end]
    handler = _once(handler, '    F3DGfx* cmd = *cmd0;',
                    '''    F3DGfx* cmd = *cmd0;
    // MODERN TRI2 PAIR CERTIFICATE BEGIN
    struct PairScope {
        Interpreter* owner;
        explicit PairScope(Interpreter* p) : owner(p) {
            owner->mXboxTrianglePairActive = true;
            owner->mXboxTrianglePairPrepared = false;
            owner->mXboxPairPacked.Reset();
        }
        ~PairScope() {
            owner->mXboxTrianglePairActive = false;
            owner->mXboxTrianglePairPrepared = false;
            owner->mXboxPairPacked.Reset();
        }
    } scope(gfx);
    // MODERN TRI2 PAIR CERTIFICATE END''')
    source = source[:handler_start] + handler + source[handler_end:]
    emitter_start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    emitter_end = source.index('\n}', emitter_start)
    emitter = source[emitter_start:emitter_end]
    emitter = _once(emitter, 'const bool xboxPipelineHit=mXboxPipelineKey.Matches(*this);',
                    'const bool xboxPipelineHit=(mXboxTrianglePairActive && mXboxTrianglePairPrepared && '
                    'mXboxPipelineKey.valid) || mXboxPipelineKey.Matches(*this);')
    emitter = _once(emitter, '    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();',
                    '    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();\n'
                    '    mXboxTrianglePairPrepared = mXboxTrianglePairActive && mXboxPipelineKey.valid;')
    emitter = _once(emitter, '        Flush();\n    }',
                    '        Flush();\n        mXboxTrianglePairPrepared = false;\n    }')
    return source[:emitter_start] + emitter + source[emitter_end:]


def _packed_reuse(source):
    marker = '// MODERN TRI2 PACKED REUSE BEGIN'
    if marker in source:
        return source
    emitter_start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    emitter_end = source.index('\n}', emitter_start)
    emitter = source[emitter_start:emitter_end]
    emitter = _once(emitter,
                    '    const bool xboxPipelineHit=(mXboxTrianglePairActive',
                    '    const bool xboxPairPackSecond = mXboxTrianglePairActive && '\
                    'mXboxTrianglePairPrepared && mXboxPipelineKey.valid && '\
                    'mXboxPairPacked.valid;\n'
                    '    const bool xboxPipelineHit=(mXboxTrianglePairActive')
    emitter = _once(emitter,
                    '    mXboxTrianglePairPrepared = mXboxTrianglePairActive && mXboxPipelineKey.valid;',
                    '    mXboxTrianglePairPrepared = mXboxTrianglePairActive && mXboxPipelineKey.valid;\n'
                    '    // MODERN TRI2 PACKED REUSE BEGIN\n'
                    '    const bool xboxPairPackFirst = mXboxTrianglePairActive && '\
                    'mXboxPipelineKey.valid;\n'
                    '    uint32_t xboxPairFirstWBits;\n'
                    '    memcpy(&xboxPairFirstWBits, &v1->w, sizeof(xboxPairFirstWBits));\n'
                    '    const bool xboxPairPackEligible = xboxPairPackSecond && '\
                    'mXboxPairPacked.CanReuse(mBufVboLen, xboxPipelineHit,\n'
                    '        (mRdp->other_mode_l & G_TL_LOD) != 0, xboxPairFirstWBits);\n'
                    '    if (!xboxPairPackEligible) mXboxPairPacked.Reset();\n'
                    '    const uint8_t xboxPairIndices[3] = {vtx1_idx, vtx2_idx, vtx3_idx};\n'
                    '    const bool xboxPairPackReuse = xboxPairPackEligible && '\
                    'mXboxPairPacked.ContainsAny(xboxPairIndices);\n'
                    '    size_t xboxPairStarts[3];\n'
                    '    // MODERN TRI2 PACKED REUSE END')
    emitter = _once(emitter,
                    '    for (int i = 0; i < 3; i++) {\n        float z = v_arr[i]->z, w = v_arr[i]->w;',
                    '    for (int i = 0; i < 3; i++) {\n'
                    '        if (xboxPairPackFirst) xboxPairStarts[i] = '\
                    'size_t(shipyardVertexOutput - mBufVbo);\n'
                    '        if (xboxPairPackReuse && mXboxPairPacked.CopyVertex('\
                    'xboxPairIndices[i], shipyardVertexOutput, mBufVbo)) {\n'
                    '            if (i == 0) mXboxPairPacked.RestoreMaterials('\
                    'shipyardMaterialInputs, mBufVbo, numInputs, use_alpha);\n'
                    '            continue;\n'
                    '        }\n'
                    '        float z = v_arr[i]->z, w = v_arr[i]->w;')
    emitter = _once(emitter,
                    '    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);',
                    '    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);\n'
                    '    if (xboxPairPackFirst) {\n'
                    '        mXboxPairPacked.Capture(xboxPairIndices, xboxPairStarts, '\
                    'mBufVboLen, xboxPairFirstWBits);\n'
                    '        mXboxPairPacked.CaptureMaterials(shipyardMaterialInputs, '\
                    'mBufVbo, numInputs, use_alpha);\n'
                    '    }')
    emitter = _once(emitter, '        mXboxTrianglePairPrepared = false;',
                    '        mXboxTrianglePairPrepared = false;\n'
                    '        mXboxPairPacked.Reset();')
    return source[:emitter_start] + emitter + source[emitter_end:]


def _phase_profile(source):
    marker = '// MODERN TRI2 PHASE PROFILE BEGIN'
    if marker in source:
        return source
    source = _once(source, 'void Interpreter::GfxSpTri1(',
                   'static __declspec(thread) ModernFrameProfile::Tri2Sample* '
                   'sModernTri2Sample = NULL;\n\n'
                   'void Interpreter::GfxSpTri1(')
    handler_start = source.index('bool gfx_tri2_handler_f3dex(')
    handler_end = source.index('\n}', handler_start)
    handler = source[handler_start:handler_end]
    handler = _once(handler, '    // MODERN TRI2 PAIR CERTIFICATE END',
                    '''    // MODERN TRI2 PAIR CERTIFICATE END
    // MODERN TRI2 PHASE PROFILE BEGIN
    struct Tri2ProfileScope {
        ModernFrameProfile::Tri2Sample sample;
        ModernFrameProfile::Tri2Sample* previous;
        Tri2ProfileScope() : previous(sModernTri2Sample) {
            ModernFrameProfile::BeginTri2(sample);
            sModernTri2Sample = sample.sampled ? &sample : NULL;
        }
        ~Tri2ProfileScope() {
            if (sample.sampled) ModernFrameProfile::EndTri2(sample);
            sModernTri2Sample = previous;
        }
    };
    // MODERN TRI2 PHASE PROFILE END''')
    handler = _once(handler,
                    '    gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);',
                    '    Tri2ProfileScope profile;\n'
                    '    gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);')
    source = source[:handler_start] + handler + source[handler_end:]
    cull_start = source.index('void Interpreter::GfxSpTri1(')
    cull_end = source.index('\n}', cull_start)
    cull = source[cull_start:cull_end]
    cull = _once(cull,
                 '    if (vtx1_idx < MAX_VERTICES && mXboxDeferredVertices[vtx1_idx].context)\n'
                 '        XboxMaterializeVertex(vtx1_idx);',
                 '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                 '        *sModernTri2Sample, ModernFrameProfile::Tri2Materialize);\n'
                 '    if (vtx1_idx < MAX_VERTICES && mXboxDeferredVertices[vtx1_idx].context)\n'
                 '        XboxMaterializeVertex(vtx1_idx);')
    cull = _once(cull, '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);',
                 '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                 '        *sModernTri2Sample, ModernFrameProfile::Tri2Pipeline);\n'
                 '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);\n'
                 '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                 '        *sModernTri2Sample, ModernFrameProfile::Tri2Cull);')
    source = source[:cull_start] + cull + source[cull_end:]
    emitter_start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    emitter_end = source.index('\n}', emitter_start)
    emitter = source[emitter_start:emitter_end]
    emitter = _once(emitter, '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;',
                    '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                    '        *sModernTri2Sample, ModernFrameProfile::Tri2Pack);\n'
                    '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;')
    emitter = _once(emitter, '        Flush();\n        mXboxTrianglePairPrepared = false;',
                    '        if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                    '            *sModernTri2Sample, ModernFrameProfile::Tri2Flush);\n'
                    '        Flush();\n'
                    '        if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                    '            *sModernTri2Sample, ModernFrameProfile::Tri2Pack);\n'
                    '        mXboxTrianglePairPrepared = false;')
    return source[:emitter_start] + emitter + source[emitter_end:]


def _run_transform(source):
    marker = '// MODERN TRI2 RUN BEGIN'
    if marker in source:
        return source
    start = source.index('bool gfx_tri2_handler_f3dex(')
    end = source.index('\n}', start)
    handler = source[start:end]
    handler = _once(handler,
                    '    Tri2ProfileScope profile;\n'
                    '    gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);\n'
                    '    gfx->GfxSpTri1(C1(17, 7), C1(9, 7), C1(1, 7), false);',
                    '''    // MODERN TRI2 RUN BEGIN
    const uintptr_t xboxOpcode = cmd->words.w0 >> 24;
    // Detailed command samples and GBI traces retain one dispatch per command.
    const bool xboxBatch = gfx->mXboxTriangleRunEnabled &&
        !ModernFrameProfile::commandSampler.enabled;
    for (;;) {
        Tri2ProfileScope profile;
        gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);
        gfx->GfxSpTri1(C1(17, 7), C1(9, 7), C1(1, 7), false);
#ifdef USE_GBI_TRACE
        break;
#else
        if (!xboxBatch || ((cmd + 1)->words.w0 >> 24) != xboxOpcode) break;
        *cmd0 = ++cmd;
#endif
    }
    // MODERN TRI2 RUN END''')
    source = source[:start] + handler + source[end:]
    return _once(source, '    const bool xboxDebugging = dbg->IsDebugging();',
                 '    const bool xboxDebugging = dbg->IsDebugging();\n'
                 '    mXboxTriangleRunEnabled = !xboxDebugging;')


def transform(source):
    return _run_transform(_phase_profile(_packed_reuse(_pair_transform(source))))


def fuse_triangle_body(source):
    """Amortize the triangle call frame across the existing uninterrupted run.

    Apply last so the dedicated inline body retains every projected cull,
    materialization, rounding, and profiling change in the single-triangle path.
    """
    marker = '// MODERN TRI2 BODY FUSION BEGIN'
    if marker in source:
        return source
    start = source.index('void Interpreter::GfxSpTri1(')
    brace = source.index('{', start)
    end = source.index('\n}', brace) + 2
    body = source[brace + 1:end - 1]
    inline = (marker + '\n'
              '__forceinline void Interpreter::XboxRunTri2Triangle(\n'
              '    uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx) {\n'
              '    const bool is_rect = false;' + body + '}\n'
              '// MODERN TRI2 BODY FUSION END\n\n')
    source = source[:start] + inline + source[start:]
    start = source.index('bool gfx_tri2_handler_f3dex(')
    end = source.index('\n}', start)
    handler = source[start:end]
    calls = '''        gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);
        gfx->GfxSpTri1(C1(17, 7), C1(9, 7), C1(1, 7), false);'''
    handler = _once(handler, calls, '''#ifndef USE_GBI_TRACE
        if (xboxBatch) {
            // One common inline body: triangle 1 must finish emission before
            // triangle 2 observes callback-driven rounding/cache invalidation.
            for (unsigned xboxTriangle = 0; xboxTriangle != 2; ++xboxTriangle) {
                const uintptr_t xboxWord = xboxTriangle ? cmd->words.w1 : cmd->words.w0;
                gfx->XboxRunTri2Triangle((xboxWord >> 17) & 127,
                                        (xboxWord >> 9) & 127, (xboxWord >> 1) & 127);
            }
        } else
#endif
        {
''' + calls + '''
        }''')
    return source[:start] + handler + source[end:]
