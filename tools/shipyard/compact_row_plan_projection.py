"""Resolve indexed rows before preparing material inputs.

Triangles whose rows are cached still append indices and obey flush limits.
Row assignment retains corner order, pointer tags, and the run generation.
"""

from prepare_configuration import once


ROW_LOOKUP = '''        if (compactReuse) {
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
        if (compactFirstPacked < 0) compactFirstPacked = i;'''


def emitter(source):
    source = once(source, '    int compactFirstPacked = -1;', '''    int compactFirstPacked = -1;
    bool compactPack[3] = { false, false, false };
    for (int i = 0; i < 3; ++i) {
''' + ROW_LOOKUP + '''
        compactPack[i] = true;
    }''')
    # The lookup was inserted above; replace only the original packing-loop copy.
    marker = '    for (int i = 0; i < 3; i++) {\n#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)\n'
    source = once(source, marker + ROW_LOOKUP,
                  marker + '        if (!compactPack[i]) continue;')
    source = once(source, '    Shipyard::Fast3D::CoordinateAxis shipyardAxisStorage[2][2];', '''#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
    // Cached rows need indices only; none of the packing inputs are consumed.
    if (compactFirstPacked >= 0) {
#endif
    Shipyard::Fast3D::CoordinateAxis shipyardAxisStorage[2][2];''')
    return once(source, '''#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
    for (unsigned corner = 0; corner < 3; ++corner) {''', '''#if defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
    }
    for (unsigned corner = 0; corner < 3; ++corner) {''')


def effective_source(source):
    for name in ('XboxEmitTriangleCompact', 'XboxEmitTriangleProfiled'):
        start = source.index('__declspec(noinline) void Interpreter::' + name + '(')
        end = source.index('\n}', start) + 2
        source = source[:start] + emitter(source[start:end]) + source[end:]
    return source
