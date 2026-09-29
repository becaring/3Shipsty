"""Preserve 9.2.3 triangle attributes while lowering Xbox vertex-stream writes.

Only the final three-vertex packing loop is touched. Material selection,
texture import, shader lifetime, culling and Flush stay upstream-owned.
"""

from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
BASE = resolve(ROOT)
from xbox360_platform.vertex_stream import lower, hoist_clamp_bounds, hoist_colors, reuse_material_inputs


START = '    for (int i = 0; i < 3; i++) {\n        float z = v_arr[i]->z, w = v_arr[i]->w;'
END = '    if (++mBufVboNumTris == MAX_TRI_BUFFER)'
COLOR = r'(mRdp->(?:fog_color|grayscale_color)\.[rgba]|v_arr\[i\]->color\.a|color->[rgba]) / 255\.0f'
UV_START = '            float u = v_arr[i]->u / 32.0f;'
UV_END = '            bool clampS = tm & (1 << 2 * t);'
UV_SHA256 = '4a481cf5cab46ba525b62b2e3ba4d17148d6a9a4404660da9b8b00c4cd3de896'
UV_REPLACEMENT = '''            *shipyardVertexOutput++ = shipyardCoordinateS[t]->Apply(v_arr[i]->u, shipyardHalfTexel);
            *shipyardVertexOutput++ = shipyardCoordinateT[t]->Apply(v_arr[i]->v, shipyardHalfTexel);

'''
# Tile shifts/starts and the texture extents are triangle invariants; the loop
# only writes mBufVbo. Each used axis is prepared once instead of converting
# the extent and shift for every vertex. The Xbox triangle pipeline projection
# replaces UV_SOURCE with the axes it prepares during reconciliation.
UV_SOURCE = '''        // SHIPYARD UV AXIS SOURCE BEGIN
        shipyardAxisStorage[t][0].Prepare(mRdp->texture_tile[mRdp->first_tile_index + t].shifts,
            mRdp->texture_tile[mRdp->first_tile_index + t].uls, tex_width[t]);
        shipyardAxisStorage[t][1].Prepare(mRdp->texture_tile[mRdp->first_tile_index + t].shiftt,
            mRdp->texture_tile[mRdp->first_tile_index + t].ult, tex_height[t]);
        shipyardCoordinateS[t] = &shipyardAxisStorage[t][0];
        shipyardCoordinateT[t] = &shipyardAxisStorage[t][1];
        // SHIPYARD UV AXIS SOURCE END
'''
UV_PRELUDE = ('''    Shipyard::Fast3D::CoordinateAxis shipyardAxisStorage[2][2];
    const Shipyard::Fast3D::CoordinateAxis* shipyardCoordinateS[2];
    const Shipyard::Fast3D::CoordinateAxis* shipyardCoordinateT[2];
    const bool shipyardHalfTexel = !is_rect &&
        (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
    for (int t = 0; t < 2; ++t) {
        if (!usedTextures[t]) continue;
''' + UV_SOURCE + '''    }
''')

def transform(source: str) -> str:
    """Project a pinned interpreter source, rejecting changed packing contracts."""
    projected = lower(source, start=START, end=END, color_pattern=COLOR,
                      namespace='Shipyard::Fast3D', cursor='shipyardVertexOutput',
                      expected_writes=21, expected_colors=12)
    if projected.count(UV_START) != 1 or projected.count(UV_END) != 1:
        raise ValueError('Modern UV packing anchors changed')
    begin = projected.index(UV_START)
    finish = projected.index(UV_END, begin)
    if hashlib.sha256(projected[begin:finish].encode()).hexdigest() != UV_SHA256:
        raise ValueError('Modern UV arithmetic changed; re-audit coordinate helper')
    projected = ('#include "fast3d/coordinate.h"\n' + projected[:begin] +
                 UV_REPLACEMENT + projected[finish:])
    loop = projected.index(START)
    projected = projected[:loop] + UV_PRELUDE + projected[loop:]
    projected = hoist_clamp_bounds(projected, start=START, end=END,
        cursor='shipyardVertexOutput', used_textures='usedTextures', axes=(
            ('shipyardClampS', 'tm & (1 << 2 * t)', '(tex_width2[t] - 0.5f) / tex_width[t]'),
            ('shipyardClampT', 'tm & (1 << 2 * t + 1)', '(tex_height2[t] - 0.5f) / tex_height[t]')))
    projected = hoist_colors(projected, start=START, end=END,
        cursor='shipyardVertexOutput', namespace='Shipyard::Fast3D', groups=(
            ('shipyardFog', 'use_fog', tuple('mRdp->fog_color.' + c for c in 'rgb')),
            ('shipyardGrayscale', 'use_grayscale', tuple('mRdp->grayscale_color.' + c for c in 'rgba'))))
    return reuse_material_inputs(projected, start=START, end=END,
        cursor='shipyardVertexOutput', mapping='comb->shader_input_mapping', shade='G_CCMUX_SHADE')
