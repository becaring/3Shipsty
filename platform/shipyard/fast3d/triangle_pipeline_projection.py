"""Adapt current 9.x Fast3D reconciliation to Shipyard's triangle certificate."""

import re
from xbox360_platform.fast3d_triangle_certificate import call_end, invalidate_native_calls


BEGIN = '    bool depth_test = (mRsp->geometry_mode & G_ZBUFFER) == G_ZBUFFER;'
END = '    float* shipyardVertexOutput = mBufVbo + mBufVboLen;'


def remove_invalidations(text):
    matches = list(re.finditer(r'\((?:gfx->)?mXboxPipelineKey\.valid=false, (?:gfx->)?mRapi->\w+\(', text))
    for match in reversed(matches):
        end = call_end(text, match.end() - 1)
        if text[end + 1] != ')':
            raise ValueError('Changed native invalidation expression')
        call = text[match.start():match.end()].split(', ', 1)[1]
        text = text[:end + 1] + text[end + 2:]
        text = text[:match.start()] + call + text[match.end():]
    return text


AXIS_BEGIN = '        // SHIPYARD UV AXIS SOURCE BEGIN\n'
AXIS_END = '        // SHIPYARD UV AXIS SOURCE END\n'
CLAMPS = (('        if (tm & (1 << 2 * t)) shipyardClampS[t] = (tex_width2[t] - 0.5f) / tex_width[t];',
           '        if (tm & (1 << 2 * t)) shipyardClampS[t] = mXboxClampS[t];'),
          ('        if (tm & (1 << 2 * t + 1)) shipyardClampT[t] = (tex_height2[t] - 0.5f) / tex_height[t];',
           '        if (tm & (1 << 2 * t + 1)) shipyardClampT[t] = mXboxClampT[t];'))


def prepared_packing(text):
    """Use reconciliation-time UV axes and clamp bounds in the packing prelude.

    A set clamp bit implies the combiner uses that slot. A slot the shader
    samples but the combiner does not keeps the per-triangle derivation.
    """
    if text.count(AXIS_BEGIN) != 1 or text.count(AXIS_END) != 1:
        raise ValueError('Modern UV axis source changed')
    start = text.index(AXIS_BEGIN) + len(AXIS_BEGIN)
    end = text.index(AXIS_END, start)
    fallback = ''.join('    ' + line for line in text[start:end].splitlines(True))
    text = (text[:start] + '        if (comb->usedTextures[t]) {\n'
            '            shipyardCoordinateS[t] = &mXboxAxisS[t];\n'
            '            shipyardCoordinateT[t] = &mXboxAxisT[t];\n'
            '        } else {\n' + fallback + '        }\n' + text[end:])
    for old, new in CLAMPS:
        if text.count(old) != 1:
            raise ValueError('Modern clamp bound prelude changed')
        text = text.replace(old, new)
    return text

# Every pipeline-key input (RDP modes, combiner, tiles, loads, texture dirty
# flags, grayscale/shader state, geometry Z mode, viewport/scissor flags) is
# written only by handlers outside NEUTRAL_HANDLERS or inside reconciliation,
# which recaptures. Native mutations and SpReset already clear key.valid.
NEUTRAL_HANDLERS = (
    'gfx_stubbed_command_handler', 'gfx_noop_handler_f3dex2', 'gfx_spnoop_command_handler_f3dex2',
    'gfx_cull_dl_handler_f3dex2', 'gfx_set_prim_depth_handler_rdp', 'gfx_set_interpolation_index_target',
    'gfx_set_env_color_handler_rdp', 'gfx_set_prim_color_handler_rdp', 'gfx_set_fog_color_handler_rdp',
    'gfx_set_fill_color_handler_rdp', 'gfx_set_blend_color_handler_rdp', 'gfx_moveword_handler_f3dex2',
    'gfx_marker_handler_otr', 'gfx_mtx_handler_f3dex2', 'gfx_mtx_otr_handler_custom',
    'gfx_mtx_otr_filepath_handler_custom', 'gfx_pop_mtx_handler_f3dex2', 'gfx_vtx_handler_f3dex2',
    'gfx_vtx_hash_handler_custom', 'gfx_vtx_otr_filepath_handler_custom', 'gfx_dl_handler_common',
    'gfx_end_dl_handler_common', 'gfx_dl_otr_hash_handler_custom', 'gfx_dl_otr_filepath_handler_custom',
    'gfx_dl_index_handler', 'gfx_branch_z_otr_handler_f3dex2', 'gfx_tri1_handler_f3dex2',
    'gfx_tri1_otr_handler_f3dex2', 'gfx_tri2_handler_f3dex', 'gfx_quad_handler_f3dex2')

TILE_IMPORT_CERTIFICATE = '''
// A repeated tile setter must still request imports after native invalidation,
// palette loads or changes to either TMEM image, including unused shader slots.
template<class Owner> static __declspec(noinline) bool XboxCanRetainTextureImports(const Owner& owner) {
    const XboxTrianglePipelineKey& key = owner.mXboxPipelineKey;
    const RDP& r = *owner.mRdp;
    return key.Matches(owner) &&
        key.palettes[0] == r.palettes[0] && key.palettes[1] == r.palettes[1] &&
        XboxTriangleBytesEqual(key.images[0], &r.loaded_texture[0], sizeof(key.images[0])) &&
        XboxTriangleBytesEqual(key.images[1], &r.loaded_texture[1], sizeof(key.images[1]));
}
'''

CERTIFICATE = '''
// A key recaptured or fully revalidated at the current stamp stays current
// until a non-neutral command runs, so runs of VTX/TRI/MTX/DL commands skip
// per-triangle revalidation of every RDP input.
static unsigned sXboxPipelineMutation = 1;
static __forceinline bool XboxPipelineCurrent(Interpreter& gfx) {
    if (gfx.mXboxPipelineKey.valid && gfx.mXboxPipelineCertified == sXboxPipelineMutation)
        return true;
    if (!gfx.mXboxPipelineKey.Certify(gfx))
        return false;
    gfx.mXboxPipelineCertified = sXboxPipelineMutation;
    return true;
}
'''


def pipeline_mutation_stamps(text):
    for name in NEUTRAL_HANDLERS:
        if text.count('bool ' + name + '(F3DGfx** cmd') != 1:
            raise ValueError('Neutral handler inventory changed: ' + name)
    owner = 'static __declspec(thread) XboxDispatchOwner* sXboxDispatchOwner = 0;\n'
    if text.count(owner) != 1:
        raise ValueError('Dispatch owner anchor changed')
    text = text.replace(owner, owner + CERTIFICATE + TILE_IMPORT_CERTIFICATE)
    table = ('// Built from the actual F3DEX2 dispatch, so opcode aliases follow handler identity.\n'
             'static const GfxOpcodeHandlerFunc sXboxPipelineNeutralHandlers[] = {\n    ' +
             ',\n    '.join(NEUTRAL_HANDLERS) + '\n};\n'
             'struct XboxPipelineNeutralTable {\n'
             '    unsigned char neutral[256];\n'
             '    XboxPipelineNeutralTable() {\n'
             '        for (unsigned op = 0; op < 256; ++op) {\n'
             '            const GfxOpcodeHandlerFunc handler = f3dex2Dispatch.at((int8_t)op).second;\n'
             '            neutral[op] = 0;\n'
             '            for (size_t i = 0; handler && i < sizeof(sXboxPipelineNeutralHandlers) /\n'
             '                 sizeof(sXboxPipelineNeutralHandlers[0]); ++i)\n'
             '                if (handler == sXboxPipelineNeutralHandlers[i]) neutral[op] = 1;\n'
             '        }\n'
             '    }\n'
             '};\n'
             'static const XboxPipelineNeutralTable sXboxPipelineNeutral;\n\n')
    names = 'const char* GfxGetOpcodeName(int8_t opcode) {'
    if text.count(names) != 1:
        raise ValueError('Opcode name anchor changed')
    text = text.replace(names, table + names)
    # Stamp before and after: handlers such as rectangles emit triangles and
    # then restore state.
    dispatch = '            if (handler.second(&cmd)) return;'
    if text.count(dispatch) != 1:
        raise ValueError('Opcode dispatch anchor changed')
    text = text.replace(dispatch, '''            const bool xboxNeutral = ucode_handler_index == ucode_f3dex2 &&
                sXboxPipelineNeutral.neutral[(uint8_t)opcode];
            if (!xboxNeutral) ++sXboxPipelineMutation;
            const bool xboxMoved = handler.second(&cmd);
            if (!xboxNeutral) ++sXboxPipelineMutation;
            if (xboxMoved) return;''')
    for table_name in ('otrHandlers', 'rdpHandlers'):
        old = '            if (' + table_name + '.at(opcode).second(&cmd)) return;'
        if text.count(old) != 1:
            raise ValueError('Invalid-ucode dispatch anchor changed')
        text = text.replace(old, '            ++sXboxPipelineMutation;\n'
                            '            const bool xboxMoved = ' + table_name + '.at(opcode).second(&cmd);\n'
                            '            ++sXboxPipelineMutation;\n'
                            '            if (xboxMoved) return;')
    return text


def transform(text):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError('Modern triangle reconciliation boundary changed')
    start = text.index(BEGIN)
    end = text.index(END, start)
    cold = text[start:end]
    if any(token in cold for token in ('v_arr', 'v1->', 'v2->', 'v3->', 'is_rect')):
        raise ValueError('Per-triangle geometry entered reconciliation')
    # Dirty tile state need not change the bound texture. TextureCacheLookup
    # flushes before native selection, eviction and upload; mask/replacement
    # imports use the same lookup, preserving queued triangles' texture state.
    import_flush = ('            if (mRdp->textures_changed[i]) {\n'
                    '                Flush();\n'
                    '                ImportTexture(i, tile, false);\n')
    if cold.count(import_flush) != 1:
        raise ValueError('Modern texture import flush changed')
    cold = cold.replace(import_flush, import_flush.replace('                Flush();\n', ''))
    # CreateAndLoadNewShader binds immediately; flush queued geometry before
    # changing the native program.
    creation = '    if (prg == NULL) {\n        comb->prg[tm] = prg =\n'
    if cold.count(creation) != 1:
        raise ValueError('Modern shader creation boundary changed')
    cold = cold.replace(creation, '    if (prg == NULL) {\n        Flush();\n        comb->prg[tm] = prg =\n')
    publish = '''    XboxTrianglePipelineResult& p=mXboxPipelineResult;
    p.comb=comb;p.ccId=cc_id;p.tm=tm;
    p.alpha=use_alpha;p.fog=use_fog;p.grayscale=use_grayscale;
    p.blendColor=false;p.redirect=false;p.numInputs=numInputs;p.clip=clip_parameters;
    for(unsigned i=0;i<2;++i) {
        p.usedTextures[i]=usedTextures[i];
        p.effectiveTile[i]=mRdp->first_tile_index+i;
        if(comb->usedTextures[i]) {
            p.width[i]=tex_width[i];p.height[i]=tex_height[i];
            p.boundWidth[i]=tex_width2[i];p.boundHeight[i]=tex_height2[i];
        } else {
            p.width[i]=p.height[i]=p.boundWidth[i]=p.boundHeight[i]=0;
        }
        p.widthFloat[i]=p.heightFloat[i]=p.boundWidthFloat[i]=p.boundHeightFloat[i]=0;
    }
    // Packing derivations from the tile/extent state reconciled above. The key
    // compares those tiles and extents for every used slot before a hit.
    for(unsigned i=0;i<2;++i) {
        if(!comb->usedTextures[i]) continue;
        const unsigned xboxTile=mRdp->first_tile_index+i;
        mXboxAxisS[i].Prepare(mRdp->texture_tile[xboxTile].shifts,mRdp->texture_tile[xboxTile].uls,tex_width[i]);
        mXboxAxisT[i].Prepare(mRdp->texture_tile[xboxTile].shiftt,mRdp->texture_tile[xboxTile].ult,tex_height[i]);
        if (tm & (1 << 2 * i)) mXboxClampS[i] = (tex_width2[i] - 0.5f) / tex_width[i];
        if (tm & (1 << 2 * i + 1)) mXboxClampT[i] = (tex_height2[i] - 0.5f) / tex_height[i];
    }
    mXboxPipelineKey.Capture(*this,p);
    mXboxPipelineCertified=sXboxPipelineMutation;
}

'''
    method = '''__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline() {
    mXboxPipelineKey.valid=false;
// SHIPYARD ORIGINAL RECONCILIATION BEGIN
''' + cold + '// SHIPYARD ORIGINAL RECONCILIATION END\n' + publish
    warm = '''    const bool xboxPipelineHit=mXboxPipelineKey.Matches(*this);
    if (ModernFrameProfile::CaptureTrianglePipeline())
        ModernFrameProfile::ObserveTrianglePipeline(xboxPipelineHit);
    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();
    const XboxTrianglePipelineResult& p=mXboxPipelineResult;
    ColorCombiner* comb=p.comb;
    const bool use_alpha=p.alpha;
    const uint32_t tm=p.tm;
    const uint32_t* tex_width=p.width;const uint32_t* tex_height=p.height;
    const uint32_t* tex_width2=p.boundWidth;const uint32_t* tex_height2=p.boundHeight;
    const bool use_fog=p.fog,use_grayscale=p.grayscale;
    const uint8_t numInputs=p.numInputs;
    const bool* usedTextures=p.usedTextures;
    const GfxClipParameters& clip_parameters=p.clip;

'''
    text = prepared_packing(text[:start] + warm + text[end:])
    signature = '__declspec(noinline) void Interpreter::XboxEmitTriangle('
    if text.count(signature) != 1:
        raise ValueError('Modern triangle emission boundary changed')
    text = text.replace(signature, method + signature)
    binding = re.compile(r'(?<!\w)(gfx->)?mXboxTextureBindings\.Invalidate\(\);')
    text, count = binding.subn(lambda match: '(' + (match[1] or '') +
                               'mXboxTextureBindings.Invalidate(), ' + (match[1] or '') +
                               'mXboxPipelineKey.valid=false);', text)
    if count != 7:
        raise ValueError('Modern texture-binding invalidation inventory changed')
    return invalidate_native_calls(text, 'mXboxPipelineKey.valid=false', minimum=30)
