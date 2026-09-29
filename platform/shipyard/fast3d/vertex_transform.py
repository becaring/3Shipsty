"""Adapt the current interpreter's vertex position loop to Shipyard's bounded VMX transform."""

from prepare_configuration import once


START = 'void Interpreter::GfxSpVertex('
END = 'void Interpreter::GfxSpModifyVertex('


def transform(source):
    matrix_begin = source.index('void Interpreter::GfxSpMatrix(')
    matrix_end = source.index('void Interpreter::GfxSpPopMatrix(', matrix_begin)
    original_matrix = source[matrix_begin:matrix_end]
    matrix = once(original_matrix, '    float matrix[4][4];',
                  '    __declspec(align(16)) float matrix[4][4];')
    first = matrix.index('        for (int i = 0; i < 4; i++) {')
    last = matrix.index('    } else {', first)
    scalar = matrix[first:last]
    matrix = once(matrix, scalar,
                  '        if (!Shipyard::Fast3D::NearestRounding() || '
                  '!Shipyard::Fast3D::QuantizeMatrix(it->second.mf, matrix)) {\n' +
                  scalar + '        }\n')
    source = once(source, original_matrix, matrix)
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError('Current Fast3D vertex boundary changed')
    begin = source.index(START)
    finish = source.index(END, begin)
    original = source[begin:finish]
    loop = '    for (size_t i = 0; i < n_vertices; i++, dest_index++) {'
    prelude = '''    static_assert(sizeof(F3DVtx) == 16, "Fast3D vertex input stride");
    static_assert(sizeof(LoadedVertex) == Shipyard::Fast3D::ClipVertexStride &&
                  offsetof(LoadedVertex, clip_rej) == Shipyard::Fast3D::ClipByteOffset &&
                  offsetof(LoadedVertex, x) == 0, "Fast3D clip layout");
    __declspec(align(16)) float shipyardTransformed[MAX_VERTICES][4];
    const size_t shipyardTransformFirst = dest_index;
    const bool shipyardTransformBatch = vertices != nullptr && n_vertices > 0 &&
        n_vertices <= MAX_VERTICES && dest_index <= MAX_VERTICES &&
        n_vertices <= MAX_VERTICES - dest_index &&
        Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx), mRsp, sizeof(*mRsp));
    const bool shipyardVectorPositions = shipyardTransformBatch &&
        Shipyard::Fast3D::NearestRounding() &&
        Shipyard::Fast3D::TransformPositions(vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed);
'''
    adapted = once(original, loop, prelude + loop)
    first = adapted.index('        float x = v->ob[0]')
    last = adapted.index('        float world_pos[3] = { 0.0 };', first)
    scalar = adapted[first:last]
    for coordinate in 'xyzw':
        scalar = once(scalar, 'float ' + coordinate + ' = ', coordinate + ' = ')
    position = '''        float x, y, z, w;
        if (shipyardVectorPositions) {
            x = shipyardTransformed[i][0];
            y = shipyardTransformed[i][1];
            z = shipyardTransformed[i][2];
            w = shipyardTransformed[i][3];
        } else {
''' + scalar + '''        }

'''
    adapted = adapted[:first] + position + adapted[last:]
    clip_first = adapted.index('        // trivial clip rejection')
    clip_last = adapted.index('        d->x = x;', clip_first)
    scalar_clip = adapted[clip_first:clip_last]
    adapted = once(adapted, scalar_clip,
                   '        if (!shipyardVectorPositions) {\n' + scalar_clip + '        }\n\n')
    if not adapted.endswith('    }\n}\n\n'):
        raise ValueError('Fast3D vertex tail changed')
    adapted = adapted[:-3] + '''    if (shipyardVectorPositions) {
        Shipyard::Fast3D::ClipVertices(&mRsp->loaded_vertices[shipyardTransformFirst],
                                      n_vertices, false);
    }
}

'''
    from xbox360_platform.vertex_invariants import aspect_denominator, normal_components, light_colors
    source = once(source, original, adapted)
    source = aspect_denominator(source, start=START, end=END, loop=loop,
        eligible='shipyardTransformBatch', framebuffer='mFbActive',
        denominator='(float)mCurDimensions.width / (float)mCurDimensions.height',
        original_statement='        x = AdjXForAspectRatio(x);',
        numerator='x * (4.0f / 3.0f)')
    source = normal_components(source, start=START, end=END,
        lighting='        if (mRsp->geometry_mode & G_LIGHTING) {',
        eligible='shipyardTransformBatch',
        needed='mRsp->current_num_lights > 1 || (mRsp->geometry_mode & G_TEXTURE_GEN)',
        components=('vn->n[0]', 'vn->n[1]', 'vn->n[2]'))
    source = light_colors(source, start=START, end=END, loop=loop,
        positive='                if (intensity > 0.0f) {',
        eligible='shipyardTransformBatch && mRsp->current_num_lights > 0 && mRsp->current_num_lights <= MAX_LIGHTS + 1',
        capacity='MAX_LIGHTS', components=tuple('mRsp->current_lights[i].l.col[%d]' % axis for axis in range(3)))
    source = exact_attribute_conversions(source, loop)
    # Every modelview change re-derives each light/look-at direction on the
    # next lit batch; its signed-byte inputs have exact table values.
    source = once(source,
                  '    float light_dir[3] = { light->dir[0] / 127.0f, light->dir[1] / 127.0f, light->dir[2] / 127.0f };',
                  '    float light_dir[3] = { Shipyard::Fast3D::NormalByteFloat(light->dir[0]) / 127.0f,\n'
                  '                           Shipyard::Fast3D::NormalByteFloat(light->dir[1]) / 127.0f,\n'
                  '                           Shipyard::Fast3D::NormalByteFloat(light->dir[2]) / 127.0f };')
    return ('#include "fast3d/clip_quantize.h"\n#include "fast3d/vertex_transform.h"\n'
            '#include "fast3d/numeric.h"\n' + source)


def exact_attribute_conversions(source, loop):
    """Replace per-vertex GPR-to-FPR conversions with exact table values.

    Xenon has no direct integer-to-float move; each conversion is a store and
    reload of the same stack slot. The 16-bit texture coordinates, the two
    signed-short fog coefficients, signed-byte normals and byte light colors
    are exactly representable, and the shared tables return those same values.
    Fog coefficients are RSP state the vertex loop never writes.
    """
    begin = source.index(START)
    finish = source.index(END, begin)
    body = source[begin:finish]
    body = once(body, '        d->u = U;\n        d->v = V;',
                '        d->u = Shipyard::Fast3D::SignedShortFloat(U);\n'
                '        d->v = Shipyard::Fast3D::SignedShortFloat(V);')
    body = once(body, '            float fog_z = z * winv * mRsp->fog_mul + mRsp->fog_offset;',
                '            float fog_z = z * winv * shipyardFogMul + shipyardFogOffset;')
    body = once(body, loop,
                '    const float shipyardFogMul = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_mul);\n'
                '    const float shipyardFogOffset = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_offset);\n'
                '    Shipyard::Fast3D::DeferredVertexBytes shipyardFogBytes[MAX_VERTICES];\n'
                '    const bool shipyardNearestNormal = Shipyard::Fast3D::NearestRounding();\n'
                + loop)
    # fdiv is not pipelined on Xenon and stalls both hardware threads. Under
    # round-to-nearest the double product is the exact float quotient (SoH360
    # 4.0.5 DivideNormal127); other modes and non-finite values still divide.
    for name in ('intensity', 'dotx', 'doty'):
        body = once(body, '                %s /= 127.0f;' % name,
                    '                %s = Shipyard::Fast3D::DivideNormal127(%s, shipyardNearestNormal);' % (name, name))
    # As SoH360 4.0.5 did: convert fog with fctiwz/stfiwx inside the loop and
    # read the bytes after clipping, not a store/reload for every vertex. Every
    # vertex of a bounded fogged batch reaches the fog store; the replay path
    # clears G_FOG.
    body = once(body, '            d->color.a = fog_z; // Use alpha variable to store fog factor',
                '            if (shipyardTransformBatch) shipyardFogBytes[i].Store(0, fog_z);\n'
                '            else d->color.a = fog_z; // Use alpha variable to store fog factor')
    body = once(body, '    if (shipyardVectorPositions) {\n        Shipyard::Fast3D::ClipVertices(',
                '    if (shipyardTransformBatch && (mRsp->geometry_mode & G_FOG)) {\n'
                '        for (size_t i = 0; i < n_vertices; ++i)\n'
                '            mRsp->loaded_vertices[shipyardTransformFirst + i].color.a = shipyardFogBytes[i].Load(0);\n'
                '    }\n'
                '    if (shipyardVectorPositions) {\n        Shipyard::Fast3D::ClipVertices(')
    for axis in range(3):
        body = once(body, '                shipyardNormal[%d] = (float)vn->n[%d];' % (axis, axis),
                    '                shipyardNormal[%d] = Shipyard::Fast3D::NormalByteFloat(vn->n[%d]);' % (axis, axis))
        body = once(body,
                    '                        shipyardLightColors[i][%d] = (float)mRsp->current_lights[i].l.col[%d];' % (axis, axis),
                    '                        shipyardLightColors[i][%d] = '
                    'Shipyard::Fast3D::LightByteFloat(mRsp->current_lights[i].l.col[%d]);' % (axis, axis))
    return source[:begin] + body + source[finish:]
