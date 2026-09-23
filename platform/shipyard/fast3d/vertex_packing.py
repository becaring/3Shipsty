"""Preserve 9.2.3 triangle attributes while lowering Xbox vertex-stream writes.

Only the final three-vertex packing loop is touched. Material selection,
texture import, shader lifetime, culling and Flush stay upstream-owned.
"""

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[3].parent / 'LibUltraShip+Fast3D360'
if not (BASE / 'python/xbox360_platform/vertex_stream.py').is_file():
    raise RuntimeError('Shared Xbox 360 platform base missing: ' + str(BASE))
sys.path.insert(0, str(BASE / 'python'))
from xbox360_platform.vertex_stream import lower
from xbox360_platform.contract import verify
verify(BASE, Path(__file__).resolve().parents[3] / 'platform-base.lock.json')


START = '    for (int i = 0; i < 3; i++) {\n        float z = v_arr[i]->z, w = v_arr[i]->w;'
END = '    if (++mBufVboNumTris == MAX_TRI_BUFFER)'
COLOR = r'(mRdp->(?:fog_color|grayscale_color)\.[rgba]|v_arr\[i\]->color\.a|color->[rgba]) / 255\.0f'


def transform(source: str) -> str:
    """Project a pinned interpreter source, rejecting changed packing contracts."""
    return lower(source, start=START, end=END, color_pattern=COLOR,
                 namespace='Shipyard::Fast3D', cursor='shipyardVertexOutput',
                 expected_writes=21, expected_colors=12)


def color_header() -> str:
    """Xenon table of the exact 256 byte/255 float results, not 1/255 multiply."""
    rows = [', '.join('%d.0f / 255.0f' % i for i in range(base, base + 8))
            for base in range(0, 256, 8)]
    return ('#pragma once\n#include <stdint.h>\n'
            'namespace Shipyard { namespace Fast3D {\n'
            '__declspec(align(128)) static const float kUnitColor[256] = {\n    '
            + ',\n    '.join(rows) + '\n};\n'
            '__forceinline float UnitColor(uint8_t value) { return kUnitColor[value]; }\n'
            '} }\n')
