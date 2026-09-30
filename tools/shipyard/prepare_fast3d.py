"""Bring the complete pinned Fast3D interpreter through the native compiler."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_graphics import feature_header,lower_api
from cpp_ast import PARSER,walk
from platform_base import resolve as resolve_platform_base
resolve_platform_base(ROOT)
from xbox360_platform import combiner_lookup, fast3d_opcode, fast3d_triangle_split, matrix_product
from xbox360_platform.resource_lookup import (texture_hash_lookup, stateless_signature,
                                               texture_command_manager, texture_hash_cache_handler,
                                               texture_hash_borrowed_handler, texture_hash_epoch_handler)
from xbox360_platform import texture_state
import deferred_lit_fog
import pipeline_phase_profile_projection
import tri2_pair_projection
import tri2_column_pack_projection
import game_fill_discard_projection
from xbox360_platform.cpp_syntax import collect_member_defaults

OUT=ROOT/'scratch/fast3d-xdk'
OWN=ROOT/'platform/shipyard/fast3d'
TRIANGLE_SPLIT_BOUNDARY='    bool depth_test = (mRsp->geometry_mode & G_ZBUFFER) == G_ZBUFFER;'


def member_defaults(text,classname):
    text,fields=collect_member_defaults(text,classname,PARSER,walk)
    initializers=[];body=[]
    for item in fields:
        if item.is_array:
            if item.value!='{}':raise ValueError('Nonempty member array needs explicit projection')
            body.append('    std::fill('+item.name+', '+item.name+' + sizeof('+item.name+')/sizeof('+item.name+'[0]), 0);')
        else:initializers.append(item.name+'('+item.value+')')
    return text,initializers,body


def header(text):
    text=matrix_product.header(text)
    text=texture_state.metadata_reference(text)
    text='#include "resources/texture_hash_cache.h"\n#include "fast3d/texture_bindings.h"\n#include "fast3d/command_stack.h"\n#include "fast3d/coordinate.h"\n'+text
    text=runpy.run_path(str(OWN/'shader_metadata_projection.py'))['header'](text)
    text=fast3d_triangle_split.header(text)
    text=combiner_lookup.header(text)
    text=once(text,'class Interpreter {',
              '#include "fast3d/triangle_traits.h"\n#include "fast3d/triangle_pipeline.h"\n\nclass Interpreter {')
    text=once(text,'    GfxTextureCache mTextureCache{};',
              '    GfxTextureCache mTextureCache{};\n'
              '    Shipyard::Resources::TextureHashCache<Fast::Texture> mXboxTextureHashCache;\n'
              '    bool mXboxTileTrialEnabled = false;\n'
              '    bool mXboxTileCaptureEnabled = false;\n'
              '    bool mXboxDiscardGameDepth = false;\n'
              '    void XboxPublishGameDepth();\n'
              '    void XboxRetireGameDepth();\n'
              '    Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES> mXboxTextureBindings;\n'
              '    GfxClipParameters mXboxClipParameters;\n'
              '    XboxTrianglePipelineKey mXboxPipelineKey;\n'
              '    XboxTrianglePipelineResult mXboxPipelineResult;\n'
              '    Shipyard::Fast3D::CoordinateAxis mXboxAxisS[2];\n'
              '    Shipyard::Fast3D::CoordinateAxis mXboxAxisT[2];\n'
              '    float mXboxClampS[2];\n'
              '    float mXboxClampT[2];\n'
              '    unsigned mXboxPipelineCertified;')
    text=runpy.run_path(str(OWN/'resource_resolution_projection.py'))['header'](text)
    text=game_fill_discard_projection.header(text)
    text=once(text,'    void XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect);',
              '    void XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect);\n'
              '    void XboxPrepareTrianglePipeline();')
    text=once(text,'std::stack<F3DGfx*> cmd_stack = {};',
              'Shipyard::Fast3D::CommandStack<F3DGfx*> cmd_stack = {};')
    # Share the real current shader constants/features with the decoder/backend.
    start=text.index('enum {\n    SHADER_0,');end=text.index('\nunion Gfx;',start)
    key_start=text.index('struct ColorCombinerKey {',start);key_end=text.index('#define SHADER_MAX_TEXTURES',key_start)
    key=text[key_start:key_end]
    text=text[:start]+'#include "fast/cc_features.h"\n'+key+text[end:]
    text=once(text,'#include <compare>','// Explicit lexicographic comparison preserves the two current fields.')
    text=once(text,'auto operator<=>(const ColorCombinerKey&) const = default;',
              'bool operator==(const ColorCombinerKey& rhs) const { return combine_mode==rhs.combine_mode && options==rhs.options; }\n'
              '    bool operator<(const ColorCombinerKey& rhs) const { return combine_mode!=rhs.combine_mode ? combine_mode<rhs.combine_mode : options<rhs.options; }')
    text=once(text,'bool operator==(const TextureCacheKey&) const noexcept = default;',
              'bool operator==(const TextureCacheKey& rhs) const throw() {\n'
              '        return texture_addr==rhs.texture_addr && palette_addrs[0]==rhs.palette_addrs[0] && palette_addrs[1]==rhs.palette_addrs[1]\n'
              '            && fmt==rhs.fmt && siz==rhs.siz && palette_index==rhs.palette_index && size_bytes==rhs.size_bytes;\n    }')
    text,defaults,arrays=member_defaults(text,'GfxExecStack')
    if len(defaults)!=3 or arrays:raise ValueError('GfxExecStack defaults changed')
    # All three defaults are empty standard containers, including disp_stack.
    text=once(text,'float h_byte_scale = 1, v_pixel_scale = 1;',
              'float h_byte_scale, v_pixel_scale;\n    RawTexMetadata() : width(0), height(0), h_byte_scale(1), v_pixel_scale(1), type(TextureType::Error) {}')
    text=once(text,'bool enabled = false;','bool enabled;\n    ShaderMod(bool enabledValue=false, int16_t idValue=0, uint8_t typeValue=0) : enabled(enabledValue), id(idValue), type(typeValue) {}')
    text,defaults,arrays=member_defaults(text,'Interpreter')
    text=deferred_lit_fog.header(text)
    text=tri2_pair_projection.header(text)
    text=text.replace('constexpr size_t','const size_t').replace(' noexcept',' throw()').replace('#include <stdbool.h>','')
    text=once(text,'#include "backends/gfx_rendering_api.h"','#include "fast/backends/gfx_rendering_api.h"')
    return text,defaults,arrays


def opcode_tables(text):
    return fast3d_opcode.lower(text,PARSER,walk,fast3d_opcode.FAST3D_TABLES)


def triangle_split(text):
    return fast3d_triangle_split.transform(text, TRIANGLE_SPLIT_BOUNDARY)


TEXEL_HELPERS = """
// Xbox: an N64 RGBA5551 texel as the four RGBA bytes the importers write,
// computed once per texel (or once per palette entry) and stored as one word.
// Each table value is exactly SCALE_5_8 of its 5-bit channel.
static const uint8_t kXboxScale5To8[32] = { 0, 8, 16, 24, 32, 41, 49, 57, 65, 74, 82, 90, 98, 106, 115, 123,
                                             131, 139, 148, 156, 164, 172, 180, 189, 197, 205, 213, 222, 230, 238, 246, 255 };
static inline uint32_t XboxRgba5551(uint16_t col16) {
    return (uint32_t(kXboxScale5To8[col16 >> 11]) << 24) | (uint32_t(kXboxScale5To8[(col16 >> 6) & 0x1f]) << 16) |
           (uint32_t(kXboxScale5To8[(col16 >> 1) & 0x1f]) << 8) | ((col16 & 1) ? 0xFFu : 0u);
}
static inline void XboxStoreRgba(uint8_t* out, uint32_t rgba) {
#if defined(_M_PPC)
    // Big-endian: the word's bytes are R, G, B, A in memory order.
    *reinterpret_cast<uint32_t*>(out) = rgba;
#else
    out[0] = (uint8_t)(rgba >> 24);
    out[1] = (uint8_t)(rgba >> 16);
    out[2] = (uint8_t)(rgba >> 8);
    out[3] = (uint8_t)rgba;
#endif
}
"""


def texel_decode(text):
    # First use of every texture decodes it on the render thread. RGBA16 and
    # the palette formats cover most of OoT: expand each texel (or each
    # palette entry, on its first use in an import) straight to its RGBA word
    # instead of a division and four byte stores per texel. Output bytes are
    # unchanged; the upload buffer is malloc-aligned and written at 4 * i.
    text=once(text,'#define SCALE_8_3(VAL_) ((VAL_) / 0x24)\n',
              '#define SCALE_8_3(VAL_) ((VAL_) / 0x24)\n'+TEXEL_HELPERS)
    text=once(text,
              '            uint16_t col16 = (addr[2 * clrIdx] << 8) | addr[2 * clrIdx + 1];\n'
              '            uint8_t a = col16 & 1;\n'
              '            uint8_t r = col16 >> 11;\n'
              '            uint8_t g = (col16 >> 6) & 0x1f;\n'
              '            uint8_t b = (col16 >> 1) & 0x1f;\n'
              '            mTexUploadBuffer[4 * i + 0] = SCALE_5_8(r);\n'
              '            mTexUploadBuffer[4 * i + 1] = SCALE_5_8(g);\n'
              '            mTexUploadBuffer[4 * i + 2] = SCALE_5_8(b);\n'
              '            mTexUploadBuffer[4 * i + 3] = a ? 255 : 0;\n',
              '            uint16_t col16 = (addr[2 * clrIdx] << 8) | addr[2 * clrIdx + 1];\n'
              '            XboxStoreRgba(&mTexUploadBuffer[4 * i], XboxRgba5551(col16));\n')
    text=once(text,
              '    SUPPORT_CHECK(fullImageLineSizeBytes == lineSizeBytes);\n\n'
              '    for (uint32_t i = 0; i < sizeBytes * 2; i++) {\n'
              '        uint8_t byte = addr[i / 2];\n'
              '        uint8_t idx = (byte >> (4 - (i % 2) * 4)) & 0xf;\n'
              '        uint16_t col16 = (palette[idx * 2] << 8) | palette[idx * 2 + 1]; // Big endian load\n'
              '        uint8_t a = col16 & 1;\n'
              '        uint8_t r = col16 >> 11;\n'
              '        uint8_t g = (col16 >> 6) & 0x1f;\n'
              '        uint8_t b = (col16 >> 1) & 0x1f;\n'
              '        mTexUploadBuffer[4 * i + 0] = SCALE_5_8(r);\n'
              '        mTexUploadBuffer[4 * i + 1] = SCALE_5_8(g);\n'
              '        mTexUploadBuffer[4 * i + 2] = SCALE_5_8(b);\n'
              '        mTexUploadBuffer[4 * i + 3] = a ? 255 : 0;\n'
              '    }\n',
              '    SUPPORT_CHECK(fullImageLineSizeBytes == lineSizeBytes);\n\n'
              '    // Each palette entry is converted on its first use, so only the\n'
              '    // entries the texture indexes are read, as before.\n'
              '    uint32_t xboxPalette[16];\n'
              '    uint8_t xboxReady[16];\n'
              '    memset(xboxReady, 0, sizeof(xboxReady));\n'
              '    for (uint32_t i = 0; i < sizeBytes * 2; i++) {\n'
              '        uint8_t byte = addr[i / 2];\n'
              '        uint8_t idx = (byte >> (4 - (i % 2) * 4)) & 0xf;\n'
              '        if (!xboxReady[idx]) {\n'
              '            xboxPalette[idx] = XboxRgba5551((uint16_t)((palette[idx * 2] << 8) | palette[idx * 2 + 1]));\n'
              '            xboxReady[idx] = 1;\n'
              '        }\n'
              '        XboxStoreRgba(&mTexUploadBuffer[4 * i], xboxPalette[idx]);\n'
              '    }\n')
    text=once(text,
              '    for (uint32_t i = 0, j = 0; i < sizeBytes; j += fullImageLineSizeBytes - lineSizeBytes) {\n'
              '        for (uint32_t k = 0; k < lineSizeBytes; i++, k++, j++) {\n'
              '            uint8_t idx = addr[j];\n'
              '            uint16_t col16 = (mRdp->palettes[idx / 128][(idx % 128) * 2] << 8) |\n'
              '                             mRdp->palettes[idx / 128][(idx % 128) * 2 + 1]; // Big endian load\n'
              '            uint8_t a = col16 & 1;\n'
              '            uint8_t r = col16 >> 11;\n'
              '            uint8_t g = (col16 >> 6) & 0x1f;\n'
              '            uint8_t b = (col16 >> 1) & 0x1f;\n'
              '            mTexUploadBuffer[4 * i + 0] = SCALE_5_8(r);\n'
              '            mTexUploadBuffer[4 * i + 1] = SCALE_5_8(g);\n'
              '            mTexUploadBuffer[4 * i + 2] = SCALE_5_8(b);\n'
              '            mTexUploadBuffer[4 * i + 3] = a ? 255 : 0;\n'
              '        }\n'
              '    }\n',
              '    // Each palette entry is converted on its first use: a texture that\n'
              '    // indexes only the first 128 entries never reads the second half.\n'
              '    uint32_t xboxPalette[256];\n'
              '    uint8_t xboxReady[256];\n'
              '    memset(xboxReady, 0, sizeof(xboxReady));\n'
              '    for (uint32_t i = 0, j = 0; i < sizeBytes; j += fullImageLineSizeBytes - lineSizeBytes) {\n'
              '        for (uint32_t k = 0; k < lineSizeBytes; i++, k++, j++) {\n'
              '            uint8_t idx = addr[j];\n'
              '            if (!xboxReady[idx]) {\n'
              '                xboxPalette[idx] = XboxRgba5551((uint16_t)((mRdp->palettes[idx / 128][(idx % 128) * 2] << 8) |\n'
              '                                                           mRdp->palettes[idx / 128][(idx % 128) * 2 + 1]));\n'
              '                xboxReady[idx] = 1;\n'
              '            }\n'
              '            XboxStoreRgba(&mTexUploadBuffer[4 * i], xboxPalette[idx]);\n'
              '        }\n'
              '    }\n')
    return text


def texture_bindings(text):
    # The selected binding is an ownership certificate for its cache node:
    # every path that can erase a node invalidates bindings first. A repeated
    # exact key can therefore recover the map iterator from that node's LRU
    # entry without hashing the key or traversing the unordered_map bucket.
    text=once(text,'    TextureCacheMap::iterator it = mTextureCache.map.find(key);\n'
              '    TextureCacheNode** n = &mRenderingState.mTextures[i];',
              '    TextureCacheNode* xboxBoundNode = mXboxTextureBindings.Bound<TextureCacheNode>(i);\n'
              '    TextureCacheMap::iterator it =\n'
              '        xboxBoundNode && xboxBoundNode->first == key\n'
              '            ? xboxBoundNode->second.lru_location->it\n'
              '            : mTextureCache.map.find(key);\n'
              '    TextureCacheNode** n = &mRenderingState.mTextures[i];')
    text=once(text,'void Interpreter::TextureCacheClear() {',
              'void Interpreter::TextureCacheClear() {\n    Flush();\n    mXboxTextureBindings.Invalidate();')
    text=once(text,'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {',
              'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {\n    Flush();\n    mXboxTextureBindings.Invalidate();')
    text=once(text,'void Interpreter::SpReset() {',
              'void Interpreter::SpReset() {\n    mXboxTextureBindings.Invalidate();')
    text=once(text,'    mRapi = rapi;',
              '    mRapi = rapi;\n    mXboxTextureBindings.Invalidate();')
    text=once(text,'GfxRenderingAPI* Interpreter::GetCurrentRenderingAPI() {',
              'GfxRenderingAPI* Interpreter::GetCurrentRenderingAPI() {\n    Flush();\n    mXboxTextureBindings.Invalidate();')
    text=once(text,'    gfx->mRapi->SelectTextureFb((uint32_t)cmd->words.w1);',
              '    gfx->mXboxTextureBindings.Invalidate();\n    gfx->mRapi->SelectTextureFb((uint32_t)cmd->words.w1);')
    text=once(text,'''    if (it != mTextureCache.map.end()) {
        mRapi->SelectTexture(i, it->second.texture_id);
        *n = &*it;''',
              '''    if (it != mTextureCache.map.end()) {
        TextureCacheNode* node=&*it;
        const Shipyard::Fast3D::TextureSamplerState sampler(it->second.linear_filter,
                                                             it->second.cms,it->second.cmt);
        if (mXboxTextureBindings.NeedsSelect(i,node,it->second.texture_id,sampler)) {
            Flush();
            mRapi->SelectTexture(i,it->second.texture_id);
            mXboxTextureBindings.Selected(i,node,it->second.texture_id,sampler);
        }
        *n = node;''')
    text=once(text,'    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {',
              '    Flush();\n    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {\n'
              '        mXboxTextureBindings.Invalidate();')
    text=once(text,'''    mRapi->SelectTexture(i, texture_id);
    mRapi->SetSamplerParameters(i, false, 0, 0);''',
              '''    mRapi->SelectTexture(i, texture_id);
    mRapi->SetSamplerParameters(i, false, 0, 0);
    mXboxTextureBindings.Selected(i,node,texture_id,Shipyard::Fast3D::TextureSamplerState());''')
    text=once(text,'''            bool linear_filter = (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
            if (linear_filter != mRenderingState.mTextures[i]->second.linear_filter ||
                cms != mRenderingState.mTextures[i]->second.cms || cmt != mRenderingState.mTextures[i]->second.cmt) {''',
              '''            bool linear_filter = (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
            const Shipyard::Fast3D::TextureSamplerState desiredSampler(linear_filter,cms,cmt);
            if (linear_filter != mRenderingState.mTextures[i]->second.linear_filter ||
                cms != mRenderingState.mTextures[i]->second.cms || cmt != mRenderingState.mTextures[i]->second.cmt ||
                mXboxTextureBindings.NeedsSampler(i,desiredSampler) ||
                (mRdp->loaded_texture[i].blended &&
                 mXboxTextureBindings.NeedsSampler(SHADER_FIRST_REPLACEMENT_TEXTURE+i,desiredSampler))) {''')
    text=once(text,'                    mRapi->SetSamplerParameters(SHADER_FIRST_REPLACEMENT_TEXTURE + i, linear_filter, cms, cmt);',
              '                    mRapi->SetSamplerParameters(SHADER_FIRST_REPLACEMENT_TEXTURE + i, linear_filter, cms, cmt);\n'
              '                    mXboxTextureBindings.SamplerChanged(SHADER_FIRST_REPLACEMENT_TEXTURE+i,desiredSampler);')
    text=once(text,'                mRapi->SetSamplerParameters(i, linear_filter, cms, cmt);',
              '                mRapi->SetSamplerParameters(i, linear_filter, cms, cmt);\n'
              '                mXboxTextureBindings.SamplerChanged(i,desiredSampler);')
    return text


def static_arrays(text):
    source=text.encode();edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='declaration' or not node.text.startswith(b'static constexpr std::array '):continue
        decl=node.child_by_field_name('declarator');name=decl.child_by_field_name('declarator').text.decode()
        values=decl.child_by_field_name('value');count=len([n for n in values.named_children if n.type!='comment'])
        if name=='tbl':typ='const char*'
        elif name=='ucode_attr_handlers':typ='UcodeAttributePointer'
        else:raise ValueError('Unreviewed deduced static array '+name)
        replacement=('typedef const uint32_t (*UcodeAttributePointer)[7];\n' if name=='ucode_attr_handlers' else '')
        replacement+='static const std::array<'+typ+', '+str(count)+'> '+name+' = { '+values.text.decode()+' };'
        edits.append((node.start_byte,node.end_byte,replacement.encode()))
    if len(edits)!=3:raise ValueError('Static array inventory drift')
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def local_array_initializers(text):
    source=text.encode();edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='init_declarator':continue
        decl=node.child_by_field_name('declarator');value=node.child_by_field_name('value')
        if decl and value and decl.type=='array_declarator' and value.type=='initializer_list':
            gap=source[decl.end_byte:value.start_byte]
            if b'=' not in gap:edits.append((decl.end_byte,value.start_byte,b' = '))
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def aggregate_assignments(text):
    source=text.encode();edits=[]
    types={'key':'TextureCacheKey','default_viewport':'XYWidthHeight',
           'gfx->mRenderingState.viewport':'XYWidthHeight','gfx->mRenderingState.scissor':'XYWidthHeight',
           'mRenderingState.viewport':'XYWidthHeight','mRenderingState.scissor':'XYWidthHeight','mFrameBuffers[fb]':'FBInfo',
           'gfx->mRsp->current_shader':'ShaderMod','gfx->mRdp->current_shader':'ShaderMod'}
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='assignment_expression':continue
        rhs=node.child_by_field_name('right')
        if not rhs or rhs.type!='initializer_list':continue
        lhs=node.child_by_field_name('left').text.decode()
        if lhs not in types or node.parent.type!='expression_statement':raise ValueError('Unreviewed aggregate assignment: '+node.text.decode())
        typ=types[lhs];initializer=rhs.text.decode()
        if typ=='ShaderMod':initializer='ShaderMod('+initializer[1:-1]+')'
        replacement='{ '+typ+' shipyardAggregate = '+initializer+'; '+lhs+' = shipyardAggregate; }'
        edits.append((node.parent.start_byte,node.parent.end_byte,replacement.encode()))
    if len(edits)!=13:raise ValueError('Current aggregate assignment inventory drift')
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def prepare():
    sources={}
    for name,expected in json.loads((OWN/'sources.lock.json').read_text())['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Fast3D input drift: '+name)
        sources[name]=text
    pending=dict(sources)
    interp='include/fast/interpreter.h'
    pending[interp],defaults,arrays=header(sources[interp])
    pending['include/fast/cc_features.h']=feature_header(sources[interp])
    for filename,classname in [('gfx_rendering_api.h','GfxRenderingAPI'),('gfx_window_manager_api.h','GfxWindowBackend')]:
        name='include/fast/backends/'+filename;pending[name]=lower_api(sources[name],classname)
    for filename in ('lus_gbi.h','f3dex.h','f3dex2.h'):
        name='include/fast/'+filename
        pending[name]=re.sub(r'\bconstexpr\b','const',sources[name])
    light='include/fast/resource/type/Light.h'
    pending[light]=once(sources[light],'using Resource::Resource;','Light(std::shared_ptr<Ship::ResourceInitData> initData) : Resource<LightEntry>(initData) {}').replace(' final :',' :')
    text=matrix_product.source(sources['src/fast/interpreter.cpp'])
    # CreateShader passes only the path to LoadFile. The upstream local
    # ResourceInitData is never observed by that call or any later branch.
    text=once(text,
              '    std::shared_ptr<Ship::ResourceInitData> initData = std::make_shared<Ship::ResourceInitData>();\n'
              '    initData->Path = path;\n'
              '    initData->IsCustom = false;\n'
              '    initData->ByteOrder = Ship::Endianness::Native;\n', '')
    text=once(text,'#include <any>','#include "fast3d/value_init.h"\n#include "fast3d/math.h"\n#include <array>')
    text=text.replace('#include <stdbool.h>','')
    text=once(text,'Interpreter::Interpreter() {','Interpreter::Interpreter() : '+', '.join(defaults)+' {\n'+'\n'.join(arrays))
    text=once(text,'mRsp = new RSP();','mRsp = Shipyard::Fast3D::NewValueInitialized<RSP>();')
    text=once(text,'mRdp = new RDP();','mRdp = Shipyard::Fast3D::NewValueInitialized<RDP>();')
    text,tables=opcode_tables(text)
    text=static_arrays(text)
    text=local_array_initializers(text)
    resolve_platform_base(ROOT)
    from xbox360_platform.cpp_syntax import lower_if_initializers
    text=lower_if_initializers(text,PARSER,walk,expected=2)
    text=aggregate_assignments(text)
    text,count=re.subn(r'RawTexMetadata (rawTexMetadata|rawTexMetdata) = \{\};',r'RawTexMetadata \1;',text)
    if count!=5:raise ValueError('Raw texture local initialization inventory drift')
    text=text.replace('[[maybe_unused]]','')
    text=once(text,'disp_stack.push_back({ file, line });','CodeDisp entry = { file, line };\n    disp_stack.push_back(entry);')
    if text.count('mGetPixelDepthPending.emplace(x, y);')!=2:raise ValueError('Depth insertion inventory drift')
    text=text.replace('mGetPixelDepthPending.emplace(x, y);','mGetPixelDepthPending.insert(std::make_pair(x, y));')
    # res is a local map destroyed immediately afterwards. Range insert retains
    # existing destination keys, just as merge does; no source nodes escape.
    text=once(text,'mGetPixelDepthCached.merge(res);','mGetPixelDepthCached.insert(res.begin(), res.end());')
    text=once(text,'mMaskedTextures[name] = MaskedTextureEntry{ mask, replacement };',
              'MaskedTextureEntry entry = { mask, replacement };\n    mMaskedTextures[name] = entry;')
    if text.count('= round(')!=2 or text.count('std::clamp(')!=2:raise ValueError('Math compatibility inventory drift')
    text=text.replace('= round(','= Shipyard::Fast3D::Round(').replace('std::clamp(','Shipyard::Fast3D::Clamp(')
    text=once(text,'node->second.lru_location = mTextureCache.lru.insert(mTextureCache.lru.end(), { it });',
              'TextureCacheMapIter location = { it };\n    node->second.lru_location = mTextureCache.lru.insert(mTextureCache.lru.end(), location);')
    text=once(text,'path.starts_with(Ship::IResource::gAltAssetPrefix)', 'Shipyard::Resources::starts_with(path, Ship::IResource::gAltAssetPrefix)')
    text=once(text,'switch (type) {','switch (type.GetValue()) {')
    text=text.replace('[[fallthrough]]','/* fall through */')
    text=once(text,'#include <spdlog/fmt/fmt.h>','#include <spdlog/spdlog.h>')
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    text=lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    text=text.replace('constexpr size_t','const size_t')
    text=re.sub(r'using (\w+) = ([^;]+?)\(\*\)(\([^;]*\));',r'typedef \2 (*\1)\3;',text)
    vertex_packing=runpy.run_path(str(OWN/'vertex_packing.py'))
    vertex_transform=runpy.run_path(str(OWN/'vertex_transform.py'))
    text=vertex_transform['transform'](text)
    text=vertex_packing['transform'](text)
    text=runpy.run_path(str(OWN/'material_cache_projection.py'))['transform'](text)
    text=runpy.run_path(str(OWN/'cull_projection.py'))['transform'](text)
    dispatch_owner=runpy.run_path(str(OWN/'dispatch_owner_projection.py'))
    text=dispatch_owner['transform'](text)
    text=triangle_split(text)
    text=texture_bindings(text)
    text=texel_decode(text)
    text=runpy.run_path(str(OWN/'shader_metadata_projection.py'))['transform'](text)
    text=once(text, '    mRapi->Init();\n    for (std::map<ColorCombinerKey, ColorCombiner>::iterator entry',
              '    mRapi->Init();\n    mXboxClipParameters = mRapi->GetClipParameters();\n'
              '    for (std::map<ColorCombinerKey, ColorCombiner>::iterator entry')
    text=once(text, '    struct GfxClipParameters clip_parameters = mRapi->GetClipParameters();',
              '    struct GfxClipParameters clip_parameters = mXboxClipParameters;')
    text=combiner_lookup.transform(text)
    text=texture_hash_lookup(text)
    text=texture_command_manager(text)
    text=texture_hash_cache_handler(text)
    for signature in ('void Interpreter::TextureCacheClear() {',
                      'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {'):
        text=once(text,signature,signature+'\n    mXboxTextureHashCache.Clear();')
    text=once(text,'void Interpreter::RunGuiOnly() {',
              'void Interpreter::RunGuiOnly() {\n    mXboxTextureHashCache.Clear();')
    text=stateless_signature(text)
    text=texture_state.exact_tile_updates(
        text, enabled_expr='mXboxTileTrialEnabled',
        capture_expr='mXboxTileCaptureEnabled',
        observe_expr='ModernFrameProfile::ObserveTileState')
    text=texture_state.empty_mask_lookup(texture_state.metadata_reference(text))
    triangle_pipeline=runpy.run_path(str(OWN/'triangle_pipeline_projection.py'))
    text=triangle_pipeline['transform'](text)
    text=triangle_pipeline['pipeline_mutation_stamps'](text)
    text=pipeline_phase_profile_projection.transform(text)
    text=deferred_lit_fog.transform(text)
    start=text.index('void Interpreter::Run(Gfx* commands,')
    end=text.index('\nvoid Interpreter::EndFrame()',start)
    body=text[start:end]
    # Profile the cost of retaining last frame's full-resolution color. The
    # ordinary path keeps Modern's depth-only clear, while this opt-in matches
    # historical 4.0.5's fresh color/depth game draw. GUI-only and explicit
    # framebuffer transfers retain their existing contents.
    body=once(body,'    (mXboxPipelineKey.valid=false, mRapi->StartFrame());',
              '    mXboxTileTrialEnabled =\n'
              '        CVarGetInteger("gSettings.XboxTileStateDedupTrialProfile", 0) != 0;\n'
              '    mXboxTileCaptureEnabled = ModernFrameProfile::CaptureResourceLookups() &&\n'
              '        CVarGetInteger("gSettings.XboxTileStateDedupCaptureProfile", 0) != 0;\n'
              '    Fast::ShipyardXenos::SetTilingGuardTrialEnabled(\n'
              '        CVarGetInteger("gSettings.XboxTilingGuardTrialProfile", 0) != 0);\n'
              '    Fast::ShipyardXenos::SetTile1PredicationTrialEnabled(\n'
              '        CVarGetInteger("gSettings.XboxTile1PredicationTrialProfile", 0) != 0);\n'
              '    (mXboxPipelineKey.valid=false, mRapi->StartFrame());')
    body=once(body,'    (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(false, true));',
              '    const bool xboxFullColorClear =\n'
              '        CVarGetInteger("gSettings.XboxFullColorClearProfile", 0) != 0;\n'
              '    (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(xboxFullColorClear, true));')
    body=once(body,'    if (mRendersToFb) {\n        (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, 1));',
              '    if (mRendersToFb) {\n'
              '        if (mXboxDiscardGameDepth) Fast::ShipyardXenos::DiscardFramebufferDepth(mGameFb);\n'
              '        mXboxDiscardGameDepth = false;\n'
              '        (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, 1));')
    # Debugger state changes only through GUI/game calls outside this walk;
    # read it once per Run instead of an out-of-line call per command.
    body=once(body,'    auto dbg = Ship::Context::GetInstance()->GetGfxDebugger();',
              '    auto dbg = Ship::Context::GetInstance()->GetGfxDebugger();\n'
              '    const bool xboxDebugging = dbg->IsDebugging();')
    body=once(body,'        if (dbg->IsDebugging()) {','        if (xboxDebugging) {')
    text=text[:start]+body+text[end:]
    text=once(text,'void Interpreter::EndFrame() {',
              'void Interpreter::EndFrame() {\n'
              '    // Direct 720p rendering needs depth only after the final replay.\n'
              '    if (mRendersToFb || mXboxDiscardGameDepth)\n'
              '        Fast::ShipyardXenos::DiscardPresentationDepthOnEnd();\n'
              '    if (mRendersToFb) {\n'
              '        Fast::ShipyardXenos::DiscardPresentationColorOnEnd();\n'
              '    }')
    # GetPixelDepth reads this same target. The application publishes it after
    # an update's final replay and retires it once the deferred read has run.
    text=once(text,'uint16_t Interpreter::GetPixelDepth(float x, float y) {',
              'void Interpreter::XboxPublishGameDepth() {\n'
              '    Fast::ShipyardXenos::PublishFramebufferDepth(mRendersToFb ? mGameFb : 0);\n'
              '}\n\n'
              'void Interpreter::XboxRetireGameDepth() {\n'
              '    Fast::ShipyardXenos::RetireFramebufferDepth();\n'
              '}\n\n'
              'uint16_t Interpreter::GetPixelDepth(float x, float y) {')
    text=once(text,'#define NOMINMAX\n',
              '#define NOMINMAX\n#include "xenos/depth_discard.h"\n'
              '#include "xenos/tiling_guard_trial.h"\n'
              '#include "xenos/tile1_predication_trial.h"\n'
              '#include "libultraship/bridge/consolevariablebridge.h"\n')
    text=game_fill_discard_projection.transform(text)
    from frame_profile_projection import interpreter as profile_interpreter
    text=profile_interpreter(text)
    text=texture_hash_borrowed_handler(text)
    text=texture_hash_epoch_handler(text)
    text=runpy.run_path(str(OWN/'resource_resolution_projection.py'))['transform'](text)
    text=tri2_pair_projection.transform(text)
    text=tri2_column_pack_projection.transform(text)
    pending['src/fast/interpreter.cpp']=text
    pending['include/stdbool.h']='#pragma once\n#ifndef __cplusplus\n#error Use the application C boolean projection for C sources\n#endif\n'
    stale_color=OUT/'generated/include/fast3d/unit_color.h'
    if stale_color.is_file():stale_color.unlink()
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps(dict(outputs={n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},
           interpreter_initializers=defaults,interpreter_array_initialization=arrays,opcode_tables=tables),indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    from prepare_window import includes
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
           '/Dnssv_CONFIG_SELECT_STRING_VIEW=1','/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h'),'/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in [OUT/'generated/include',ROOT/'scratch/gui-resources-xdk/generated/include',ROOT/'scratch/context-xdk/generated/include']+includes()+[ROOT/'scratch/async-xdk/generated']]
    source=OUT/'generated/src/fast/interpreter.cpp';obj=folder/'interpreter.obj'
    command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'interpreter.log',result.stdout+result.stderr)
    stable(folder/'build.json',json.dumps(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command),indent=2)+'\n')
    if result.returncode:
        print('\n'.join(line for line in result.stdout.splitlines() if 'error ' in line)[:4500]);raise SystemExit(result.returncode)
    if struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not a Xenon object')
    # Check the actual include composition, not a standalone forced endian flag.
    probe=folder/'endian_contract.cpp'
    stable(probe,'#include "fast/interpreter.h"\n#include "ship/utils/binarytools/endianness.h"\n'
           '#if !defined(IS_BIGENDIAN) || !SHIPYARD_BIG_ENDIAN\n#error Xenon framebuffer values already have BE byte order\n#endif\n'
           'typedef char NativeIsBig[(Ship::Endianness::Native==Ship::Endianness::Big)?1:-1];\n')
    command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(probe),'/Fo'+str(folder/'endian_contract.obj')]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'endian_contract.log',result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Actual interpreter endian composition failed; see endian_contract.log')
    print('Complete current Fast3D interpreter compiles for Xenon')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
