"""Reuse material calculations across draws and interpolation replays.

Native state reconciliation still runs on every replay. Mode keys cover every decoded input;
geometry keys retain the original arithmetic and rounding mode. Texture nodes
are borrowed only until cache removal, backend initialization or owner teardown.
"""


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Material replay anchor changed: " + old[:100])
    return text.replace(old, new)


HELPERS = r'''
// Debugger switch for A/B measurement; zero bypasses the mode and texture-node memos.
extern "C" volatile unsigned gModernMaterialReplayControl[1] = { 1 };
struct ModernModeKey {
    const Interpreter* owner;
    uint64_t combine;
    uint32_t low, high;
    int16_t shader;
    unsigned flags;
    bool operator==(const ModernModeKey& rhs) const {
        return owner == rhs.owner && combine == rhs.combine && low == rhs.low &&
            high == rhs.high && shader == rhs.shader && flags == rhs.flags;
    }
};
struct ModernModeValue {
    ColorCombiner* comb;
    bool alpha, fog, grayscale;
};
static __declspec(thread) Shipyard::Fast3D::MaterialMemo<ModernModeKey, ModernModeValue, 256> sModernModes;
struct ModernTextureNodeKey {
    const Interpreter* owner;
    TextureCacheKey texture;
    bool operator==(const ModernTextureNodeKey& rhs) const {
        return owner == rhs.owner && texture == rhs.texture;
    }
};
static __declspec(thread) Shipyard::Fast3D::MaterialMemo<ModernTextureNodeKey, TextureCacheNode*, 1024> sModernTextureNodes;
static void ModernReleaseMaterialMemos();
'''

MODE_LOOKUP = r'''    const uint64_t cc_id = mRdp->combine_mode;
    const ModernModeKey xboxModeKey = { this, cc_id, mRdp->other_mode_l, mRdp->other_mode_h,
        mRdp->current_shader.id, unsigned(mRdp->grayscale) | (unsigned(mRdp->current_shader.enabled) << 1) |
        (unsigned(mRdp->loaded_texture[0].masked) << 2) | (unsigned(mRdp->loaded_texture[1].masked) << 3) |
        (unsigned(mRdp->loaded_texture[0].blended) << 4) | (unsigned(mRdp->loaded_texture[1].blended) << 5) };
    const unsigned xboxModeHash = Shipyard::Fast3D::HashMaterialKey(unsigned(cc_id) ^ unsigned(cc_id >> 32) ^
        xboxModeKey.low ^ (xboxModeKey.high * 33U) ^ (unsigned(xboxModeKey.shader) * 17U) ^ xboxModeKey.flags);
    Shipyard::Fast3D::MaterialMemo<ModernModeKey, ModernModeValue, 256>::Entry& xboxMode = sModernModes.Slot(xboxModeHash);
    if (!gModernMaterialReplayControl[0] || !xboxMode.valid || !(xboxMode.key == xboxModeKey)) {
        // MODERN MODE MISS BEGIN
MODE_BODY
        // MODERN MODE MISS END
        xboxMode.valid = false;
        xboxMode.key = xboxModeKey;
        xboxMode.value.comb = comb;
        xboxMode.value.alpha = use_alpha;
        xboxMode.value.fog = use_fog;
        xboxMode.value.grayscale = use_grayscale;
        xboxMode.valid = true;
    }
    ColorCombiner* comb = xboxMode.value.comb;
    const bool use_alpha = xboxMode.value.alpha;
    const bool use_fog = xboxMode.value.fog;
    const bool use_grayscale = xboxMode.value.grayscale;
'''

NODE_LOOKUP = r'''    TextureCacheNode* xboxBoundNode = mXboxTextureBindings.Bound<TextureCacheNode>(i);
    const ModernTextureNodeKey xboxNodeKey = { this, key };
    Shipyard::Fast3D::MaterialMemo<ModernTextureNodeKey, TextureCacheNode*, 1024>::Entry* xboxNode = NULL;
    if (!xboxBoundNode || !(xboxBoundNode->first == key)) {
        const unsigned xboxNodeHash = Shipyard::Fast3D::HashMaterialKey(unsigned(reinterpret_cast<uintptr_t>(key.texture_addr)) ^
            key.size_bytes ^ (unsigned(key.fmt) << 12) ^ (unsigned(key.siz) << 16) ^ (unsigned(key.palette_index) << 20));
        xboxNode = &sModernTextureNodes.Slot(xboxNodeHash);
        if (gModernMaterialReplayControl[0] && xboxNode->valid && xboxNode->key == xboxNodeKey) xboxBoundNode = xboxNode->value;
    }
'''


def transform(text):
    # Multi-entry geometry reuse keeps all original arithmetic on misses.
    old = 'Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue>'
    if text.count(old) != 3:
        raise ValueError('Modern geometry cache inventory changed')
    text = text.replace(old, 'Shipyard::Fast3D::MaterialMemo<ModernGeometryKey,ModernGeometryValue,256>')
    text = once(text, '    return cache.Load(key,builder);', '''    unsigned bounds[4];
    memcpy(&bounds[0], &key.uls, sizeof(float));
    memcpy(&bounds[1], &key.ult, sizeof(float));
    memcpy(&bounds[2], &key.lrs, sizeof(float));
    memcpy(&bounds[3], &key.lrt, sizeof(float));
    const unsigned hash = Shipyard::Fast3D::HashMaterialKey(key.tileLine ^ (key.originalSize * 33U) ^
        bounds[0] ^ (bounds[1] * 17U) ^ (bounds[2] * 31U) ^ (bounds[3] * 47U) ^
        (unsigned(key.siz) << 12) ^ (unsigned(key.cms) << 16) ^ (unsigned(key.cmt) << 20) ^ key.rounding);
    return cache.Load(key,hash,builder);''')
    signature = 'Interpreter::Interpreter()'
    text = once(text, signature, HELPERS + '\n' + signature)
    geometry_cache = 'static __declspec(thread) Shipyard::Fast3D::MaterialMemo<ModernGeometryKey,ModernGeometryValue,256> sModernGeometry1;'
    text = once(text, geometry_cache, geometry_cache + '''
static void ModernReleaseMaterialMemos() {
    sModernModes.Release();
    sModernTextureNodes.Release();
    sModernGeometry0.Release();
    sModernGeometry1.Release();
}
''')
    start = text.index('    uint64_t cc_id = mRdp->combine_mode;', text.index('void Interpreter::XboxPrepareTrianglePipeline()'))
    end_token = '    ColorCombiner* comb = LookupOrCreateColorCombiner(key);\n'
    end = text.index(end_token, start) + len(end_token)
    body = text[start:end].replace('    uint64_t cc_id = mRdp->combine_mode;\n', '')
    text = text[:start] + MODE_LOOKUP.replace('MODE_BODY', body) + text[end:]
    text = once(text,
                '    TextureCacheNode* xboxBoundNode = mXboxTextureBindings.Bound<TextureCacheNode>(i);\n', NODE_LOOKUP)
    store = '''        if (xboxNode) {
            xboxNode->key = xboxNodeKey;
            xboxNode->value = node;
            xboxNode->valid = true;
        }
'''
    text = once(text, '        *n = node;\n', store + '        *n = node;\n')
    text = once(text, '    *n = node;\n    ModernFrameProfile::ObserveTextureLookup(false);',
                store + '    *n = node;\n    ModernFrameProfile::ObserveTextureLookup(false);')
    # Erasure invalidates every borrowed node before map/list mutation.
    for signature in ('void Interpreter::TextureCacheClear() {',
                      'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {'):
        text = once(text, signature, signature + '\n    sModernTextureNodes.Clear();')
    text = once(text, '    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {',
                '    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {\n        sModernTextureNodes.Clear();')
    text = once(text, 'Interpreter::~Interpreter() {',
                'Interpreter::~Interpreter() {\n    ModernReleaseMaterialMemos();')
    text = once(text, '    mRapi->Init();',
                '    sModernModes.Clear();\n    sModernTextureNodes.Clear();\n    mRapi->Init();') if '    mRapi->Init();' in text else once(
                    text, '    (mXboxPipelineKey.valid=false, mRapi->Init());',
                    '    sModernModes.Clear();\n    sModernTextureNodes.Clear();\n'
                    '    (mXboxPipelineKey.valid=false, mRapi->Init());')
    return '#include "fast3d/material_memo.h"\n' + text
