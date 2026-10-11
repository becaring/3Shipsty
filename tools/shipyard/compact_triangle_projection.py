"""Keep ordinary triangles on a small cull/emit path with Modern's full packer.

The emitter comes from the projection before TRI2 reuse and column packing.
Detailed diagnostics use the same arithmetic in separate instrumented functions.
Texture, shader, framebuffer, material and deferred-vertex semantics stay shared.
Indexed rows may be shared only inside consecutive TRI2 commands and before a flush.
"""

import re

from prepare_configuration import once


def method(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]


# Combiner inputs resolved once per triangle avoid an indirect branch per input
# and vertex. Channels the original reads from an unset tmp keep its loop.
INPUT_PLAN = '''    unsigned char shipyardPlanKind[16];
    float shipyardPlanValue[16][3];
    unsigned shipyardPlanCount = 0;
    bool shipyardPlanReady = true;
    for (int j = 0; shipyardPlanReady && j < numInputs; j++) {
        for (int k = 0; k < 1 + (use_alpha ? 1 : 0); k++) {
            const unsigned q = shipyardPlanCount++;
            const uint8_t mapping = comb->shader_input_mapping[k][j];
            if (mapping == G_CCMUX_SHADE) {
                shipyardPlanKind[q] = k == 0 ? 0 : (use_fog ? 2 : 1);
                continue;
            }
            RGBA tmp;
            const RGBA* color = &tmp;
            switch (mapping) {
                case G_CCMUX_PRIMITIVE:
                    color = &mRdp->prim_color;
                    break;
                case G_CCMUX_ENVIRONMENT:
                    color = &mRdp->env_color;
                    break;
                case G_CCMUX_PRIMITIVE_ALPHA:
                    if (k) shipyardPlanReady = false;
                    tmp.r = tmp.g = tmp.b = mRdp->prim_color.a;
                    break;
                case G_CCMUX_ENV_ALPHA:
                    if (k) shipyardPlanReady = false;
                    tmp.r = tmp.g = tmp.b = mRdp->env_color.a;
                    break;
                case G_CCMUX_PRIM_LOD_FRAC:
                    if (k) shipyardPlanReady = false;
                    tmp.r = tmp.g = tmp.b = mRdp->prim_lod_fraction;
                    break;
                case G_CCMUX_LOD_FRACTION: {
                    if (mRdp->other_mode_l & G_TL_LOD) {
                        float distance_frac = (v1->w - 3000.0f) / 3000.0f;
                        if (distance_frac < 0.0f) {
                            distance_frac = 0.0f;
                        }
                        if (distance_frac > 1.0f) {
                            distance_frac = 1.0f;
                        }
                        tmp.r = tmp.g = tmp.b = tmp.a = distance_frac * 255.0f;
                    } else {
                        tmp.r = tmp.g = tmp.b = tmp.a = 255.0f;
                    }
                    break;
                }
                case G_ACMUX_PRIM_LOD_FRAC:
                    if (!k) shipyardPlanReady = false;
                    tmp.a = mRdp->prim_lod_fraction;
                    break;
                default:
                    memset(&tmp, 0, sizeof(tmp));
                    break;
            }
            if (k == 0) {
                shipyardPlanKind[q] = 3;
                shipyardPlanValue[q][0] = shipyardUnitColors[color->r];
                shipyardPlanValue[q][1] = shipyardUnitColors[color->g];
                shipyardPlanValue[q][2] = shipyardUnitColors[color->b];
            } else {
                shipyardPlanKind[q] = 4;
                shipyardPlanValue[q][0] = shipyardUnitColors[color->a];
            }
        }
    }
'''
INPUT_PLAN_PACK = '''        if (shipyardPlanReady) {
            const LoadedVertex* const planVertex = v_arr[i];
            for (unsigned q = 0; q < shipyardPlanCount; ++q) {
                const unsigned kind = shipyardPlanKind[q];
                if (kind == 0) {
                    shipyardVertexOutput[0] = shipyardUnitColors[planVertex->color.r];
                    shipyardVertexOutput[1] = shipyardUnitColors[planVertex->color.g];
                    shipyardVertexOutput[2] = shipyardUnitColors[planVertex->color.b];
                    shipyardVertexOutput += 3;
                } else if (kind == 3) {
                    shipyardVertexOutput[0] = shipyardPlanValue[q][0];
                    shipyardVertexOutput[1] = shipyardPlanValue[q][1];
                    shipyardVertexOutput[2] = shipyardPlanValue[q][2];
                    shipyardVertexOutput += 3;
                } else {
                    *shipyardVertexOutput++ = kind == 1 ? shipyardUnitColors[planVertex->color.a]
                                            : kind == 2 ? 1.0f : shipyardPlanValue[q][0];
                }
            }
        } else
'''

def header(source):
    declaration = '    void GfxSpTri1(uint8_t vtx1Idx, uint8_t vtx2Idx, uint8_t vtx3Idx, bool isRect);'
    return once(source, declaration, declaration + '''
    bool mXboxCompactTriangles;
    bool mXboxTriangleDiagnostics;
    bool mXboxCompactPairEnabled;
    bool mXboxCompactTriangleLod;
    const float* mXboxCompactUnitColors;
    void XboxRefreshCompactRounding();
    bool mXboxCompactPairActive, mXboxCompactPairValid;
    struct XboxCompactRowEntry { LoadedVertex* vertex; unsigned generation; uint16_t row; };
    XboxCompactRowEntry mXboxCompactRows[128];
    unsigned mXboxCompactRowGeneration;
    struct XboxCompactNdcEntry { unsigned generation; float x, y; };
    XboxCompactNdcEntry mXboxCompactNdc[128];
    unsigned mXboxCompactNdcGeneration;
    void XboxBeginCompactRun();
    __forceinline void XboxCompactNdc(uint8_t index, float& x, float& y);
    void XboxTriangleReference(uint8_t a, uint8_t b, uint8_t c, bool rectangle);
    __forceinline void XboxWorkTriangleCompact(uint8_t a, uint8_t b, uint8_t c, bool rectangle);
    void XboxEmitTriangleCompact(LoadedVertex* v1, LoadedVertex* v2, LoadedVertex* v3, bool rectangle);
    void XboxWorkTriangleProfiled(uint8_t a, uint8_t b, uint8_t c, bool rectangle);
    void XboxEmitTriangleProfiled(LoadedVertex* v1, LoadedVertex* v2, LoadedVertex* v3, bool rectangle);''')


def capture(source):
    work = method(source, 'void Interpreter::GfxSpTri1(')
    emitter = method(source, '__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    begin = work.index('    // MODERN TRIANGLE MATERIALIZATION GUARD BEGIN')
    end = work.index('    // MODERN TRIANGLE MATERIALIZATION GUARD END', begin)
    end = work.index('\n', end) + 1
    materialize = work[begin:end]
    work = work[:begin] + work[end:]
    # The cull has no callbacks: retain upstream arithmetic and invert-cull rules.
    begin = work.index('        // MODERN CULL CACHE BEGIN')
    end = work.index('        // MODERN CULL CACHE END', begin)
    end = work.index('\n', end) + 1
    work = work[:begin] + '''        float dx1, dy1, dx2, dy2;
        if (mXboxCompactPairActive) {
            float x1, y1, x2, y2, x3, y3;
            XboxCompactNdc(vtx1_idx, x1, y1);
            XboxCompactNdc(vtx2_idx, x2, y2);
            XboxCompactNdc(vtx3_idx, x3, y3);
            dx1 = x1 - x2; dy1 = y1 - y2;
            dx2 = x3 - x2; dy2 = y3 - y2;
        } else {
        dx1 = v1->x / v1->w - v2->x / v2->w;
        dy1 = v1->y / v1->w - v2->y / v2->w;
        dx2 = v3->x / v3->w - v2->x / v2->w;
        dy2 = v3->y / v3->w - v2->y / v2->w;
        }
        float cross = dx1 * dy2 - dy1 * dx2;
''' + work[end:]
    work = once(work, '    struct LoadedVertex* v_arr[3] = { v1, v2, v3 };\n', '')
    work = once(work, 'void Interpreter::GfxSpTri1(', '__forceinline void Interpreter::XboxWorkTriangleCompact(')
    work = once(work, '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);',
                '    XboxEmitTriangleCompact(v1, v2, v3, is_rect);')
    signature_end = emitter.index('{')
    emitter = '''__declspec(noinline) void Interpreter::XboxEmitTriangleCompact(
    LoadedVertex* v1, LoadedVertex* v2, LoadedVertex* v3, bool is_rect) ''' + emitter[signature_end:]
    for index, vertex in enumerate(('v1', 'v2', 'v3'), 1):
        emitter = once(emitter, '    struct LoadedVertex* ' + vertex + ' = &mRsp->loaded_vertices[vtx' + str(index) + '_idx];\n', '')
        materialize = materialize.replace('vtx' + str(index) + '_idx', 'size_t(' + vertex + ' - mRsp->loaded_vertices)')
    emitter = once(emitter, '    struct LoadedVertex* v_arr[3] = { v1, v2, v3 };',
                   materialize + '    struct LoadedVertex* v_arr[3] = { v1, v2, v3 };')
    emitter = once(emitter, 'mXboxPipelineKey.Matches(*this)', 'XboxPipelineCurrent(*this)')
    emitter = once(emitter, '''    if (ModernFrameProfile::CaptureTrianglePipeline())
        ModernFrameProfile::ObserveTrianglePipeline(xboxPipelineHit);
''', '')
    emitter = once(emitter, '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;',
                   '    const float* const shipyardUnitColors = mXboxCompactUnitColors;\n'
                   '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;')
    emitter = once(emitter, '    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();', '''    if(!xboxPipelineHit) {
        XboxPrepareTrianglePipeline();
        XboxRefreshCompactRounding();
    }''')
    emitter, count = re.subn(r'Shipyard::Fast3D::UnitColor\(([^()]+)\)', r'shipyardUnitColors[\1]', emitter)
    if count != 12:
        raise ValueError('Compact triangle color inventory changed: ' + str(count))
    emitter = once(emitter, '        Flush();',
                   '        ModernFrameProfile::SetFlushReason(ModernFrameProfile::FlushBufferFull);\n        Flush();')
    emitter = once(emitter, '    float* shipyardVertexOutput = mBufVbo + mBufVboLen;', '''#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
    const size_t compactStride = mXboxPackLayout[0];
    if (mBufVboNumTris && (mXboxIndexedStride != compactStride ||
        mBufVboLen + 3 * compactStride > MAX_TRI_BUFFER * 32 * 3)) {
        ModernFrameProfile::SetFlushReason(ModernFrameProfile::FlushBufferFull);
        Flush();
    }
    mXboxIndexedStride = compactStride;
    uint16_t compactRows[3];
    size_t compactNextRow = mXboxIndexedRows;
    const bool compactReuse = mXboxCompactPairActive && !is_rect && !mXboxCompactTriangleLod;
    if (compactReuse && !mXboxCompactPairValid && ++mXboxCompactRowGeneration == 0) {
        memset(mXboxCompactRows, 0, sizeof(mXboxCompactRows));
        mXboxCompactRowGeneration = 1;
    }
    int compactFirstPacked = -1;
#else
    const int compactFirstPacked = 0;
#endif
    float* shipyardVertexOutput = mBufVbo + mBufVboLen;''')
    emitter = once(emitter, '    for (int i = 0; i < 3; i++) {', '''    for (int i = 0; i < 3; i++) {
#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
        if (compactReuse) {
            // Pointer tags keep hash collisions harmless, including non-array rectangle vertices.
            XboxCompactRowEntry& row = mXboxCompactRows[(uintptr_t(v_arr[i]) / sizeof(LoadedVertex)) & 127];
            if (row.generation == mXboxCompactRowGeneration && row.vertex == v_arr[i]) {
                compactRows[i] = row.row;
                continue;
            }
            row.vertex = v_arr[i];
            row.generation = mXboxCompactRowGeneration;
            row.row = uint16_t(compactNextRow);
        }
        compactRows[i] = uint16_t(compactNextRow++);
        if (compactFirstPacked < 0) compactFirstPacked = i;
#endif''')
    emitter = once(emitter, 'if (i != 0 && comb->shader_input_mapping[k][j] != G_CCMUX_SHADE)',
                   'if (i != compactFirstPacked && comb->shader_input_mapping[k][j] != G_CCMUX_SHADE)')
    emitter = once(emitter, 'if (i == 0) shipyardMaterialInputs[k][j] = shipyardVertexOutput;',
                   'if (i == compactFirstPacked) shipyardMaterialInputs[k][j] = shipyardVertexOutput;')
    emitter = once(emitter, '    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);', '''#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
    for (unsigned corner = 0; corner < 3; ++corner) {
        mXboxTriangleIndices[3 * mBufVboNumTris + corner] = compactRows[corner];
    }
    // LOD fraction uses this triangle's first vertex, so those rows cannot be shared.
    mXboxCompactPairValid = mXboxCompactPairActive && !is_rect && !mXboxCompactTriangleLod;
    mXboxIndexedRows = compactNextRow;
#endif
    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);''')
    emitter = once(emitter, '    const float* shipyardMaterialInputs[2]', INPUT_PLAN + '    const float* shipyardMaterialInputs[2]')
    emitter = once(emitter, '''        for (int j = 0; j < numInputs; j++) {
            RGBA* color;
            RGBA tmp;''', INPUT_PLAN_PACK + '''        for (int j = 0; j < numInputs; j++) {
            RGBA* color;
            RGBA tmp;''')
    return work, emitter


def profiled_kernels(work, emitter):
    work = once(work, '__forceinline void Interpreter::XboxWorkTriangleCompact(',
                '__declspec(noinline) void Interpreter::XboxWorkTriangleProfiled(')
    work = once(work, '    XboxEmitTriangleCompact(v1, v2, v3, is_rect);', '''    if (sModernTri2Sample)
        ModernFrameProfile::AdvanceTri2(*sModernTri2Sample, ModernFrameProfile::Tri2Materialize);
    XboxEmitTriangleProfiled(v1, v2, v3, is_rect);
    if (sModernTri2Sample)
        ModernFrameProfile::AdvanceTri2(*sModernTri2Sample, ModernFrameProfile::Tri2Cull);''')
    emitter = once(emitter, 'void Interpreter::XboxEmitTriangleCompact(', 'void Interpreter::XboxEmitTriangleProfiled(')
    emitter = once(emitter, '    const bool xboxPipelineHit=XboxPipelineCurrent(*this);', '''    if (sModernTri2Sample)
        ModernFrameProfile::AdvanceTri2(*sModernTri2Sample, ModernFrameProfile::Tri2Pipeline);
    const bool xboxPipelineHit=XboxPipelineCurrent(*this);
    if (ModernFrameProfile::CaptureTrianglePipeline())
        ModernFrameProfile::ObserveTrianglePipeline(xboxPipelineHit);''')
    emitter = once(emitter, '    const float* const shipyardUnitColors = mXboxCompactUnitColors;', '''    if (sModernTri2Sample)
        ModernFrameProfile::AdvanceTri2(*sModernTri2Sample, ModernFrameProfile::Tri2Pack);
    const float* const shipyardUnitColors = mXboxCompactUnitColors;''')
    if emitter.count('        Flush();') != 2:
        raise ValueError('Compact triangle flush inventory changed')
    emitter = emitter.replace('        Flush();', '''        if (sModernTri2Sample)
            ModernFrameProfile::AdvanceTri2(*sModernTri2Sample, ModernFrameProfile::Tri2Flush);
        Flush();
        if (sModernTri2Sample)
            ModernFrameProfile::AdvanceTri2(*sModernTri2Sample, ModernFrameProfile::Tri2Pack);''')
    return work, emitter


def transform(source, kernels):
    work, emitter = kernels
    profiled_work, profiled_emitter = profiled_kernels(work, emitter)
    anchor = 'void Interpreter::GfxSpTri1('
    # Insert after the instrumented emitter so its source-based tests stay scoped.
    original = method(source, '__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    source = once(source, original, original + '\n\n' + emitter + '\n\n' + profiled_emitter)
    diagnostic = method(source, anchor)
    wrapper = '''void Interpreter::GfxSpTri1(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect) {
    if (mXboxCompactTriangles) {
        if (mXboxTriangleDiagnostics) XboxWorkTriangleProfiled(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);
        else XboxWorkTriangleCompact(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);
        return;
    }
    XboxTriangleReference(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);
}'''
    ndc = '''void Interpreter::XboxRefreshCompactRounding() {
    mXboxCompactUnitColors = Shipyard::Fast3D::UnitColorTable(Shipyard::Fast3D::ProjectionRoundingMode());
}

void Interpreter::XboxBeginCompactRun() {
    mXboxCompactPairActive = mXboxCompactPairEnabled;
    mXboxCompactPairValid = false;
    if (mXboxCompactPairActive && ++mXboxCompactNdcGeneration == 0) {
        memset(mXboxCompactNdc, 0, sizeof(mXboxCompactNdc));
        mXboxCompactNdcGeneration = 1;
    }
}

__forceinline void Interpreter::XboxCompactNdc(uint8_t index, float& x, float& y) {
    XboxCompactNdcEntry& entry = mXboxCompactNdc[index];
    if (entry.generation != mXboxCompactNdcGeneration) {
        const LoadedVertex& vertex = mRsp->loaded_vertices[index];
        entry.x = vertex.x / vertex.w;
        entry.y = vertex.y / vertex.w;
        entry.generation = mXboxCompactNdcGeneration;
    }
    x = entry.x; y = entry.y;
}'''
    source = once(source, diagnostic, ndc + '\n\n' + work + '\n\n' + profiled_work + '\n\n' + wrapper + '\n\n' +
                  diagnostic.replace(anchor, '__declspec(noinline) void Interpreter::XboxTriangleReference(', 1))
    source = once(source, 'Interpreter::Interpreter() :', '''// Live A/B control; sampled once per replay before interpreting commands.
extern "C" volatile unsigned gModernCompactPairControl[2] = { 1, 0 };
// Debugger switch for A/B measurement; sampled once per interpreter run.
extern "C" volatile unsigned gModernCompactTriangleControl[1] = { 1 };

Interpreter::Interpreter() :''')
    ctor = source.index('Interpreter::Interpreter() :')
    brace = source.index('{', ctor)
    source = source[:brace + 1] + '''
    mXboxCompactTriangles = false;
    mXboxTriangleDiagnostics = false;
    mXboxCompactPairEnabled = false;
    mXboxCompactTriangleLod = true;
    mXboxCompactUnitColors = NULL;
    mXboxCompactNdcGeneration = 0;
    memset(mXboxCompactNdc, 0, sizeof(mXboxCompactNdc));
    mXboxCompactRowGeneration = 0;
    memset(mXboxCompactRows, 0, sizeof(mXboxCompactRows));
    mXboxCompactPairActive = mXboxCompactPairValid = false;''' + source[brace + 1:]
    source = once(source, 'void Interpreter::Flush() {', '''void Interpreter::Flush() {
    mXboxCompactPairValid = false;''')
    prepare = method(source, '__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline()')
    source = once(source, prepare, once(prepare, '    mXboxPipelineKey.Capture(*this,p);', '''    // COMPACT TRIANGLE LOD INPUT BEGIN
    mXboxCompactTriangleLod = false;
    if (mRdp->other_mode_l & G_TL_LOD) {
        for (unsigned input = 0; input < p.numInputs; ++input) {
            if (comb->shader_input_mapping[0][input] == G_CCMUX_LOD_FRACTION ||
                (p.alpha && comb->shader_input_mapping[1][input] == G_CCMUX_LOD_FRACTION)) {
                mXboxCompactTriangleLod = true;
                break;
            }
        }
    }
    // COMPACT TRIANGLE LOD INPUT END
    mXboxPipelineKey.Capture(*this,p);'''))
    source = once(source, '    mXboxTriangleRunEnabled = !xboxDebugging;', '''    mXboxTriangleRunEnabled = !xboxDebugging;
    // COMPACT ROUNDING FRAME BEGIN
    XboxRefreshCompactRounding();
    // COMPACT ROUNDING FRAME END
    mXboxTriangleDiagnostics = ModernFrameProfile::TriangleDiagnosticsEnabled();
    mXboxCompactPairEnabled = gModernCompactPairControl[0] != 0;
    gModernCompactPairControl[1] = mXboxCompactPairEnabled ? 1 : 0;
#if !defined(USE_GBI_TRACE)
    mXboxCompactTriangles = !xboxDebugging && gModernCompactTriangleControl[0] != 0 &&
        CVarGetInteger("gSettings.XboxCompactTriangles", 1) != 0;
#else
    mXboxCompactTriangles = false;
#endif''')
    original = method(source, 'bool gfx_tri2_handler_f3dex(')
    reference = original.replace('bool gfx_tri2_handler_f3dex(',
                                 'static __declspec(noinline) bool XboxTri2ReferenceHandler(', 1)
    begin = original.index('    // MODERN TRI2 PHASE PROFILE BEGIN')
    end = original.index('    // MODERN TRI2 PHASE PROFILE END', begin)
    scope = original[begin:end]
    diagnostic = '''static __declspec(noinline) bool XboxTri2ProfiledHandler(F3DGfx** cmd0) {
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
''' + scope + '''
    const uintptr_t opcode = cmd->words.w0 >> 24;
    const bool batch = gfx->mXboxTriangleRunEnabled && !ModernFrameProfile::commandSampler.enabled;
    gfx->XboxBeginCompactRun();
    for (;;) {
        Tri2ProfileScope profile;
        gfx->XboxWorkTriangleProfiled(C0(17, 7), C0(9, 7), C0(1, 7), false);
        gfx->XboxWorkTriangleProfiled(C1(17, 7), C1(9, 7), C1(1, 7), false);
        if (!batch || ((cmd + 1)->words.w0 >> 24) != opcode) break;
        *cmd0 = ++cmd;
    }
    gfx->mXboxCompactPairActive = gfx->mXboxCompactPairValid = false;
    return false;
}'''
    handler = '''bool gfx_tri2_handler_f3dex(F3DGfx** cmd0) {
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    if (gfx->mXboxCompactTriangles) {
        if (gfx->mXboxTriangleDiagnostics) return XboxTri2ProfiledHandler(cmd0);
        const uintptr_t opcode = cmd->words.w0 >> 24;
        const bool batch = gfx->mXboxTriangleRunEnabled && !ModernFrameProfile::commandSampler.enabled;
        gfx->XboxBeginCompactRun();
        for (;;) {
            for (unsigned triangle = 0; triangle != 2; ++triangle) {
                const uintptr_t word = triangle ? cmd->words.w1 : cmd->words.w0;
                gfx->XboxWorkTriangleCompact((word >> 17) & 127, (word >> 9) & 127,
                                            (word >> 1) & 127, false);
            }
            if (!batch || ((cmd + 1)->words.w0 >> 24) != opcode) break;
            *cmd0 = ++cmd;
        }
        gfx->mXboxCompactPairActive = gfx->mXboxCompactPairValid = false;
        return false;
    }
    return XboxTri2ReferenceHandler(cmd0);
}'''
    return once(source, original, reference + '\n\n' + diagnostic + '\n\n' + handler)
