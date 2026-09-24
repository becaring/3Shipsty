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
    return '#include "fast3d/clip_quantize.h"\n#include "fast3d/vertex_transform.h"\n' + once(source, original, adapted)
