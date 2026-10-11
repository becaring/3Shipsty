"""Count rounding reads while executing generated compact color selection."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
sys.path.insert(0, str(Path(__file__).parent))
from compact_triangle_projection import method
from test_material_replay import compile_run


class CompactRoundingTests(unittest.TestCase):
    def test_frame_snapshot_and_post_preparation_rounding(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        emitter = method(source, '__declspec(noinline) void Interpreter::XboxEmitTriangleCompact(')
        select = emitter[emitter.index('    if(!xboxPipelineHit)'):emitter.index('    const XboxTrianglePipelineResult&')]
        refresh = ''
        frame = ''
        if 'void Interpreter::XboxRefreshCompactRounding()' in source:
            refresh = method(source, 'void Interpreter::XboxRefreshCompactRounding()')
            refresh = refresh.replace('Interpreter::', 'RoundOwner::')
            frame = source.split('// COMPACT ROUNDING FRAME BEGIN\n', 1)[1].split('// COMPACT ROUNDING FRAME END', 1)[0]
        select = select.replace('Shipyard::Fast3D::ProjectionRoundingMode()', 'ReadRounding()')
        refresh = refresh.replace('Shipyard::Fast3D::ProjectionRoundingMode()', 'ReadRounding()')
        fixture = FIXTURE.replace('/* SELECT */', select).replace('/* REFRESH */', refresh).replace('/* FRAME */', frame)
        fixture = fixture.replace('/* READ */', 'return Shipyard::Fast3D::ProjectionRoundingMode();')
        compile_run(self, fixture)


FIXTURE = r'''
#include "fast3d/projection_cache.h"
#include "fast3d/unit_color_rounding.h"
#include <float.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
static unsigned reads;
static unsigned ReadRounding() { ++reads; /* READ */ }
struct RoundOwner {
    const float* mXboxCompactUnitColors;
    unsigned nextRounding;
    RoundOwner() : mXboxCompactUnitColors(NULL), nextRounding(_RC_NEAR) {}
    void XboxRefreshCompactRounding();
    void XboxPrepareTrianglePipeline() { _controlfp(nextRounding, _MCW_RC); }
    void Frame() { /* FRAME */ }
    const float* Select(bool xboxPipelineHit) {
        /* SELECT */
        return shipyardUnitColors;
    }
};
/* REFRESH */
static void require(bool okay, const char* why) {
    if (!okay) { fprintf(stderr, "FAIL %s\n", why); exit(1); }
}
int main() {
    const unsigned modes[] = {_RC_NEAR, _RC_DOWN, _RC_UP, _RC_CHOP};
    RoundOwner owner;
    for (unsigned frame = 0; frame < 4; ++frame) {
        _controlfp(modes[frame], _MCW_RC);
        reads = 0;
        owner.Frame();
        for (unsigned triangle = 0; triangle < 128; ++triangle) {
            const float* colors = owner.Select(true);
            const float* expected = Shipyard::Fast3D::UnitColorTable(Shipyard::Fast3D::ProjectionRoundingMode());
            require(memcmp(colors, expected, 256 * sizeof(float)) == 0, "frame rounding colors differ");
        }
        require(reads == 1, "stable triangles reread floating-point status");
        owner.nextRounding = modes[(frame + 1) % 4];
        const float* colors = owner.Select(false);
        const float* expected = Shipyard::Fast3D::UnitColorTable(Shipyard::Fast3D::ProjectionRoundingMode());
        require(memcmp(colors, expected, 256 * sizeof(float)) == 0, "preparation changed rounding without refreshing colors");
        require(reads == 2, "preparation refresh count differs");
    }
    _controlfp(_RC_NEAR, _MCW_RC);
    puts("PASS generated compact rounding: one read per frame, refresh after preparation, four rounding modes");
}
'''


if __name__ == '__main__':
    unittest.main()
