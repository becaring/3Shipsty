"""Keep Modern geometry arithmetic local behind Shipyard's value cache."""
import hashlib


SOURCE_SHA256 = '5bfe75e7868e5c571b8b6dde9a793f28467f726570285b608a38cd5bb2cfc84f'
START = '            uint8_t cms ='
END = '            if (mRenderingState.mTextures[i] == nullptr)'


def transform(source: str) -> str:
    tri = source.split('void Interpreter::GfxSpTri1(', 1)[1]
    body = tri[tri.index(START):tri.index(END)]
    if hashlib.sha256(body.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Re-audit Modern texture geometry arithmetic and complete cache key')
    cold = body.replace('mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index]', 'loadedState')
    cold = cold.replace('mRdp->texture_tile[tile]', 'tileState')
    for old, new in [('tex_width2[i]', 'boundWidth'), ('tex_height2[i]', 'boundHeight'),
                     ('tex_width[i]', 'width'), ('tex_height[i]', 'height'),
                     ('tm |= 1 << 2 * i + 1', 'clampMask |= 2'),
                     ('tm |= 1 << 2 * i', 'clampMask |= 1')]:
        cold = cold.replace(old, new)
    if 'mRdp' in cold or '[i]' in cold or 'tm |=' in cold:
        raise ValueError('Unmapped Modern geometry dependency')
    helper = '''// MODERN MATERIAL CACHE BEGIN
struct ModernGeometryKey {
    uint32_t tileLine,originalSize;
    unsigned rounding;
    float uls,ult,lrs,lrt;
    uint8_t siz,cms,cmt;
    bool operator==(const ModernGeometryKey& rhs) const {
        return tileLine==rhs.tileLine && originalSize==rhs.originalSize &&
            rounding==rhs.rounding &&
            uls==rhs.uls && ult==rhs.ult && lrs==rhs.lrs && lrt==rhs.lrt &&
            siz==rhs.siz && cms==rhs.cms && cmt==rhs.cmt;
    }
};
struct ModernGeometryValue {
    uint32_t width,height,boundWidth,boundHeight,clampMask;
    uint8_t cms,cmt;
};
template<class Tile,class Loaded> struct ModernGeometryBuilder {
    const Tile& tileState;
    const Loaded& loadedState;
    __declspec(noinline) void Rebuild(ModernGeometryValue& result) {
        // TEST REBUILD GEOMETRY
        uint32_t width,height,boundWidth,boundHeight,clampMask=0;
COLD_BODY
        result.width=width;result.height=height;
        result.boundWidth=boundWidth;result.boundHeight=boundHeight;
        result.clampMask=clampMask;result.cms=cms;result.cmt=cmt;
    }
};
template<class Tile,class Loaded>
const ModernGeometryValue& ModernGeometry(
    Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue>& cache,
    const Tile& tileState,const Loaded& loadedState) {
    ModernGeometryKey key={tileState.line_size_bytes,loadedState.orig_size_bytes,
        _controlfp(0,0)&_MCW_RC,
        tileState.uls,tileState.ult,tileState.lrs,tileState.lrt,
        tileState.siz,tileState.cms,tileState.cmt};
    ModernGeometryBuilder<Tile,Loaded> builder={tileState,loadedState};
    return cache.Load(key,builder);
}
static __declspec(thread) Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue> sModernGeometry0;
static __declspec(thread) Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue> sModernGeometry1;
// MODERN MATERIAL CACHE END

'''.replace('COLD_BODY', cold)
    replacement = '''            uint8_t cms = 0, cmt = 0;
            const ModernGeometryValue& geometry = ModernGeometry(
                i ? sModernGeometry1 : sModernGeometry0,mRdp->texture_tile[tile],
                mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index]);
            cms=geometry.cms;cmt=geometry.cmt;
            tex_width[i]=geometry.width;tex_height[i]=geometry.height;
            tex_width2[i]=geometry.boundWidth;tex_height2[i]=geometry.boundHeight;
            tm |= geometry.clampMask << (2 * i);

'''
    if source.count(body) != 1 or source.count('void Interpreter::GfxSpTri1(') != 1:
        raise ValueError('Modern geometry anchor inventory drift')
    source = source.replace(body, replacement, 1)
    source = source.replace('void Interpreter::GfxSpTri1(',
                            helper + 'void Interpreter::GfxSpTri1(', 1)
    return '#include <float.h>\n#include "fast3d/material_value_cache.h"\n' + source
