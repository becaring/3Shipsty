"""Adapt Modern's cull arithmetic to Shipyard's raw-value projection cache."""
import hashlib

SOURCE_SHA256 = '0c012aa86cadca8a1d9f0eb0b41a28845ebdf122df697b645958103ac111f795'
START = '        float dx1 = '
END = '        if ((v1->w < 0)'


def transform(source: str) -> str:
    tri = source.split('void Interpreter::GfxSpTri1(', 1)[1]
    original = tri[tri.index(START):tri.index(END)]
    if hashlib.sha256(original.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Modern cull arithmetic changed; re-audit its cache adapter')
    replacement = '''        // MODERN CULL CACHE BEGIN
        Shipyard::Fast3D::ProjectionValueCache& p1 = sModernCullProjection[vtx1_idx];
        Shipyard::Fast3D::ProjectionValueCache& p2 = sModernCullProjection[vtx2_idx];
        Shipyard::Fast3D::ProjectionValueCache& p3 = sModernCullProjection[vtx3_idx];
        p1.Load(v1->x, v1->y, v1->w);
        p2.Load(v2->x, v2->y, v2->w);
        p3.Load(v3->x, v3->y, v3->w);
        float dx1 = p1.x - p2.x;
        float dy1 = p1.y - p2.y;
        float dx2 = p3.x - p2.x;
        float dy2 = p3.y - p2.y;
        float cross = dx1 * dy2 - dy1 * dx2;
        // MODERN CULL CACHE END
'''
    if source.count(original) != 1:
        raise ValueError('Modern cull anchor inventory drift')
    source = source.replace(original, replacement, 1)
    source = source.replace('void Interpreter::GfxSpTri1(',
                            'static __declspec(thread) Shipyard::Fast3D::ProjectionValueCache '
                            'sModernCullProjection[MAX_VERTICES + 4];\n\n'
                            'void Interpreter::GfxSpTri1(', 1)
    return '#include "fast3d/projection_cache.h"\n' + source
