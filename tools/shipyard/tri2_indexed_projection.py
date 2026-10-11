"""Submit one packed row per certified TRI2 slot and preserve corner order."""


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern indexed triangle anchor drift: ' + old[:100])
    return source.replace(old, new, 1)


def header(source):
    if 'mXboxIndexedRows' not in source:
        source = _once(source, '    ModernTri2PackedReuse mXboxPairPacked;',
                       '    ModernTri2PackedReuse mXboxPairPacked;\n'
                       '    uint16_t mXboxTriangleIndices[256 * 3];\n'
                       '    size_t mXboxIndexedRows;\n'
                       '    size_t mXboxIndexedStride;')
    # Fresh and already-projected headers must produce the same member order.
    source = source.replace('    size_t mXboxPackLayout[6];\n', '')
    return _once(source, '    size_t mXboxIndexedStride;',
                 '    size_t mXboxIndexedStride;\n'
                 '    size_t mXboxPackLayout[6];')


def indexed_body(emitter):
    """Derive arithmetic from the selected row/column kernels, not a rewrite."""
    prefix = emitter[:emitter.index('    // MODERN TRI2 PACKED REUSE BEGIN')]
    alias_start = emitter.index('    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(')
    prelude_start = emitter.index('    float* shipyardVertexOutput =')
    column_start = emitter.index('    // MODERN COLUMN PACK BEGIN')
    column_end = emitter.index('    // MODERN COLUMN PACK END')
    aliases = emitter[alias_start:prelude_start]
    prelude = emitter[prelude_start:column_start]
    column = emitter[column_start:column_end]
    kernel_start = column.index('    if (!xboxPairPackReuse && xboxColumnStride <= 32) {')
    kernel = column[kernel_start:]
    kernel = _once(kernel, '    if (!xboxPairPackReuse && xboxColumnStride <= 32) {',
                   '    if (xboxColumnStride <= 32) {')
    kernel = _once(kernel, '''        if (xboxPairPackFirst) {
            for (int i = 0; i < 3; ++i)
                xboxPairStarts[i] = size_t(xboxRows[i] - mBufVbo);
        }
''', '')
    kernel = _once(kernel, '''        if (xboxPairPackFirst) xboxPairStarts[i] = size_t(shipyardVertexOutput - mBufVbo);
        if (xboxPairPackReuse && mXboxPairPacked.CopyVertex(xboxPairIndices[i], shipyardVertexOutput, mBufVbo)) {
            if (i == 0) mXboxPairPacked.RestoreMaterials(shipyardMaterialInputs, mBufVbo, numInputs, use_alpha);
            continue;
        }
''', '')
    fixed_three = _once(kernel, '''            for (int i = 0; i < 3; ++i) {
                xboxRows[i][offset] = axisS.Apply(v_arr[i]->u, shipyardHalfTexel);
                xboxRows[i][offset + 1] = axisT.Apply(v_arr[i]->v, shipyardHalfTexel);
            }''', '''            if (axisS.generic || axisT.generic) {
                for (int i = 0; i < 3; ++i) {
                    xboxRows[i][offset] = axisS.Apply(v_arr[i]->u, shipyardHalfTexel);
                    xboxRows[i][offset + 1] = axisT.Apply(v_arr[i]->v, shipyardHalfTexel);
                }
            } else {
                Shipyard::Fast3D::ApplyCoordinate3(axisS, v_arr[0]->u, v_arr[1]->u, v_arr[2]->u,
                    shipyardHalfTexel, xboxRows[0][offset], xboxRows[1][offset], xboxRows[2][offset]);
                Shipyard::Fast3D::ApplyCoordinate3(axisT, v_arr[0]->v, v_arr[1]->v, v_arr[2]->v,
                    shipyardHalfTexel, xboxRows[0][offset + 1], xboxRows[1][offset + 1], xboxRows[2][offset + 1]);
            }''')
    dynamic = kernel.replace('i < 3;', 'i < int(xboxIndexedPlan.count);')
    dynamic = _once(dynamic, 'shipyardVertexOutput += 3 * xboxColumnStride;',
                    'shipyardVertexOutput += xboxIndexedPlan.count * xboxColumnStride;')
    kernel = '''    // MODERN INDEXED FIXED THREE BEGIN
    if (xboxIndexedPlan.count == 3) {
''' + fixed_three + '''
    } else {
''' + dynamic + '''
    }
    // MODERN INDEXED FIXED THREE END
'''
    tail = emitter[emitter.index('    if (++mBufVboNumTris == MAX_TRI_BUFFER) {'):]
    return prefix + '''    // MODERN INDEXED CERTIFICATE BEGIN
    const bool xboxPairPackFirst = mXboxTrianglePairActive && mXboxPipelineKey.valid;
    uint32_t xboxPairFirstWBits;
    memcpy(&xboxPairFirstWBits, &v1->w, sizeof(xboxPairFirstWBits));
    const uint8_t xboxPairIndices[3] = {vtx1_idx, vtx2_idx, vtx3_idx};
''' + aliases + '''    // MODERN INDEXED PACK DERIVATIONS
    const size_t xboxColumnStride = mXboxPackLayout[0];
    const size_t* const xboxTextureOffset = mXboxPackLayout + 1;
    const size_t xboxFogOffset = mXboxPackLayout[3];
    const size_t xboxGrayOffset = mXboxPackLayout[4];
    const size_t xboxInputOffset = mXboxPackLayout[5];
    // A shader normally flushes before its stride changes. Keep the stream
    // self-contained even on an unusual layout or reconciliation fallback.
    if (mBufVboNumTris && (mXboxIndexedStride != xboxColumnStride ||
        mBufVboLen + 3 * xboxColumnStride > MAX_TRI_BUFFER * 32 * 3)) Flush();
    mXboxIndexedStride = xboxColumnStride;
    const size_t xboxIndexedBegin = mBufVboLen;
    const bool xboxIndexedReuse = xboxPairPackSecond &&
        mXboxPairPacked.CanReuse(mBufVboLen, xboxPipelineHit,
            (mRdp->other_mode_l & G_TL_LOD) != 0, xboxPairFirstWBits);
    if (!xboxIndexedReuse) mXboxPairPacked.Reset();
    ModernIndexedTrianglePlan xboxIndexedPlan;
    xboxIndexedPlan.Prepare(mXboxPairPacked, xboxIndexedReuse,
                           xboxPairIndices, mXboxIndexedRows);
    if (xboxIndexedPlan.count) {
        if (xboxIndexedPlan.count != 3) {
            LoadedVertex* xboxOriginalVertices[3] = {v1, v2, v3};
            for (unsigned i = 0; i < xboxIndexedPlan.count; ++i)
                v_arr[i] = xboxOriginalVertices[xboxIndexedPlan.sourceCorners[i]];
        }
''' + prelude + kernel + '''
        mBufVboLen = size_t(shipyardVertexOutput - mBufVbo);
        mXboxIndexedRows += xboxIndexedPlan.count;
    }
    for (unsigned i = 0; i < 3; ++i)
        mXboxTriangleIndices[3 * mBufVboNumTris + i] = xboxIndexedPlan.rows[i];
    if (xboxPairPackFirst)
        mXboxPairPacked.CaptureIndexed(xboxPairIndices, xboxIndexedPlan.rows,
            xboxIndexedBegin, mBufVboLen, xboxColumnStride, xboxPairFirstWBits);
    // MODERN INDEXED CERTIFICATE END
''' + tail


def transform(source):
    # Retire the measured-slower material recipe from already-generated input.
    if '// MODERN MATERIAL INVALIDATION\n' in source:
        source = _once(source, '// MODERN MATERIAL INVALIDATION\n'
                       'static __declspec(thread) bool sModernMaterialPackInvalid = true;\n', '')
        source = source.replace('    sModernMaterialPackInvalid = true;\n', '')
    if '#include "fast3d/coordinate_three.h"' not in source:
        source = _once(source, '#include "fast/interpreter.h"',
                       '#include "fast/interpreter.h"\n#include "fast3d/coordinate_three.h"')
    if '// MODERN PACK LAYOUT CAPTURE BEGIN' not in source:
        # Integer layout depends only on the result already captured here. No
        # additional key or lifetime is needed, including uncertified fallbacks.
        emitter_start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
        layout_start = source.index('    size_t xboxColumnStride =', emitter_start)
        layout_end = source.index('    if (!xboxPairPackReuse && xboxColumnStride <= 32)', layout_start)
        layout = source[layout_start:layout_end].replace('    if (!xboxPairPackReuse) {', '    {', 1)
        capture = '''    // MODERN PACK LAYOUT CAPTURE BEGIN
    {
    const bool* usedTextures = p.usedTextures;
    const uint32_t tm = p.tm;
    const bool use_fog = p.fog, use_grayscale = p.grayscale, use_alpha = p.alpha;
    const unsigned numInputs = p.numInputs;
''' + layout + '''    mXboxPackLayout[0] = xboxColumnStride;
    mXboxPackLayout[1] = xboxTextureOffset[0];
    mXboxPackLayout[2] = xboxTextureOffset[1];
    mXboxPackLayout[3] = xboxFogOffset;
    mXboxPackLayout[4] = xboxGrayOffset;
    mXboxPackLayout[5] = xboxInputOffset;
    }
    // MODERN PACK LAYOUT CAPTURE END
'''
        source = _once(source, '    mXboxPipelineKey.Capture(*this,p);',
                       capture + '    mXboxPipelineKey.Capture(*this,p);')
    if '// MODERN INDEXED EMITTER BEGIN' in source:
        if ('// MODERN INDEXED PACK DERIVATIONS' not in source or
                '// MODERN MATERIAL PROGRAM BEGIN' in source):
            # Existing selected projections retain their exact flat reference.
            # Refresh only the native body so isolated validation uses this pass.
            start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
            body_start = source.index('{', start) + 1
            native_start = source.index('    // MODERN INDEXED EMITTER BEGIN', body_start)
            native_end = source.index('    // MODERN INDEXED EMITTER END', native_start)
            original = source[body_start:native_start].split(
                '#if !defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)\n', 1)[1].rsplit('#else', 1)[0]
            source = source[:native_start] + '    // MODERN INDEXED EMITTER BEGIN\n' + \
                indexed_body(original) + '\n' + source[native_end:]
        return source
    source = _once(source, '#include "fast/interpreter.h"',
                   '#include "fast/interpreter.h"\n#include "fast3d/indexed_submission.h"')
    source = _once(source, '    mXboxTriangleRunEnabled = false;',
                   '    mXboxTriangleRunEnabled = false;\n'
                   '    mXboxIndexedRows = 0;\n'
                   '    mXboxIndexedStride = 0;')
    start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    body_start = source.index('{', start) + 1
    end = source.index('\n}', body_start)
    original = source[body_start:end]
    indexed = indexed_body(original)
    source = source[:body_start] + '\n#if !defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)\n' + original + \
        '\n#else\n    // MODERN INDEXED EMITTER BEGIN\n' + indexed + \
        '\n    // MODERN INDEXED EMITTER END\n#endif' + source[end:]
    source = _once(source, 'void Interpreter::Flush() {', '''// Cumulative submission counts: sampled by the debugger, never logged.
#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
uint32_t gModernIndexedRows = 0;
uint32_t gModernIndexedCorners = 0;
#endif
void Interpreter::Flush() {''')
    source = _once(source, '        mRapi->DrawTriangles(mBufVbo, mBufVboLen, mBufVboNumTris);',
                   '''#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
        Fast::ShipyardXenos::DrawIndexedTriangles(mBufVbo, mBufVboLen,
            mXboxIndexedRows, mXboxTriangleIndices, mBufVboNumTris);
        gModernIndexedRows += uint32_t(mXboxIndexedRows);
        gModernIndexedCorners += uint32_t(3 * mBufVboNumTris);
        mXboxIndexedRows = 0;
        mXboxIndexedStride = 0;
        mXboxTrianglePairPrepared = false;
        mXboxPairPacked.Reset();
#else
        mRapi->DrawTriangles(mBufVbo, mBufVboLen, mBufVboNumTris);
#endif''')
    return source
