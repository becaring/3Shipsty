"""Certify the first opaque full-game fill before discarding retained color."""

from prepare_configuration import once


def header(text):
    return once(text, '    bool mXboxDiscardGameDepth = false;',
                '    bool mXboxDiscardGameDepth = false;\n'
                '    bool mXboxCanDiscardGameColor = false;')


def transform(text):
    text = once(text, '#define NOMINMAX\n',
                '#define NOMINMAX\n'
                '#include "fast3d/game_fill_discard_certificate.h"\n')
    text = once(text,
                '    (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(xboxFullColorClear, true));',
                '    mXboxCanDiscardGameColor =\n'
                '        mRendersToFb && mMsaaLevel == 1 && !xboxFullColorClear;\n'
                '    mXboxPipelineKey.valid = false;\n'
                '    if (mXboxCanDiscardGameColor)\n'
                '        Fast::ShipyardXenos::BeginGameFramebufferDepthClear();\n'
                '    else\n'
                '        mRapi->ClearFramebuffer(xboxFullColorClear, true);')
    text = once(text,
                '__declspec(noinline) void Interpreter::XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect) {',
                '__declspec(noinline) void Interpreter::XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect) {\n'
                '    mXboxCanDiscardGameColor = false;')
    text = once(text, 'void Interpreter::SetFrameBuffer(int fb, float noiseScale) {',
                'void Interpreter::SetFrameBuffer(int fb, float noiseScale) {\n'
                '    mXboxCanDiscardGameColor = false;')
    text = once(text,
                'void Interpreter::CopyFrameBuffer(int fb_dst_id, int fb_src_id, bool copyOnce, bool* hasCopiedPtr) {',
                'void Interpreter::CopyFrameBuffer(int fb_dst_id, int fb_src_id, bool copyOnce, bool* hasCopiedPtr) {\n'
                '    mXboxCanDiscardGameColor = false;')

    start = text.index('void Interpreter::GfxDpFillRectangle(')
    end = text.index('\nvoid Interpreter::GfxDpSetZImage(', start)
    body = text[start:end]
    anchor = '    for (int i = MAX_VERTICES; i < MAX_VERTICES + 4; i++) {'
    guard = '''    // The backend also requires a pending, idle, single-sample game target.
    // This consumer proves its first color operation overwrites every pixel.
    if (mXboxCanDiscardGameColor) {
        const LoadedVertex* corners = &mRsp->loaded_vertices[MAX_VERTICES];
        const bool fullOpaqueFill = !mFbActive && mRendersToFb &&
            mMsaaLevel == 1 && mBufVboLen == 0 && mBufVboNumTris == 0 &&
            mode == G_CYC_FILL && mRdp->other_mode_l ==
                (G_AC_NONE | G_ZS_PIXEL | G_RM_NOOP | G_RM_NOOP2) &&
            mRdp->fill_color.a == 255 && !mRdp->grayscale &&
            !mRdp->current_shader.enabled &&
            ModernFast3D::FullGameFillCovers(
                mNativeDimensions.width, mNativeDimensions.height,
                mCurDimensions.width, mCurDimensions.height,
                ulx, uly, lrx, lry,
                mRdp->scissor.x, mRdp->scissor.y,
                mRdp->scissor.width, mRdp->scissor.height,
                corners[0].clip_rej, corners[1].clip_rej,
                corners[2].clip_rej, corners[3].clip_rej);
        if (fullOpaqueFill)
            Fast::ShipyardXenos::TryDiscardGameFramebufferColor();
        // A partial first fill or backend rejection cannot be retried.
        mXboxCanDiscardGameColor = false;
    }

'''
    body = once(body, anchor, guard + anchor)
    return text[:start] + body + text[end:]
