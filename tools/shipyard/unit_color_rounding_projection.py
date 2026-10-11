"""Preserve the caller's rounding mode when normalizing packed color bytes."""

import re


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern color rounding anchor changed: ' + old[:100])
    return source.replace(old, new, 1)


def header(source):
    return _once(source,
                 'void XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect);',
                 'void XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect, uint32_t projectionRounding);')


def transform(source):
    marker = '// MODERN COLOR ROUNDING BEGIN'
    if marker in source:
        return source
    # Cull projection already samples RN once. Carry that token through the
    # materializer. Reconciliation can call the renderer, so a miss refreshes
    # RN after it returns. Unculled geometry also needs the color token.
    token = '        const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();\n'
    source = _once(source, token, '')
    source = _once(source, '    if ((mRsp->geometry_mode & cull_both) != 0) {',
                   '    const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();\n'
                   '    if ((mRsp->geometry_mode & cull_both) != 0) {')
    source = _once(source, 'XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);',
                   'XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect, projectionRounding);')
    signature = 'void Interpreter::XboxEmitTriangle(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect)'
    source = _once(source, signature, signature[:-1] + ', uint32_t projectionRounding)')
    start = source.index('void Interpreter::XboxEmitTriangle(')
    end = source.index('\n}', start)
    emitter = source[start:end]
    emitter = _once(emitter, '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;',
                    '    // MODERN COLOR ROUNDING BEGIN\n'
                    '    if (!xboxPipelineHit) projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();\n'
                    '    const float* const shipyardUnitColors = Shipyard::Fast3D::UnitColorTable(projectionRounding);\n'
                    '    // MODERN COLOR ROUNDING END\n'
                    '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;')
    emitter, count = re.subn(r'Shipyard::Fast3D::UnitColor\(([^()]+)\)',
                            r'shipyardUnitColors[\1]', emitter)
    if count != 21:
        raise ValueError('Modern packed color inventory changed: ' + str(count))
    source = source[:start] + emitter + source[end:]
    if 'Shipyard::Fast3D::UnitColor(' in source:
        raise ValueError('Modern color normalization escaped the audited emitter')
    return '#include "fast3d/unit_color_rounding.h"\n' + source
