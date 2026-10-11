"""Differential checks for the nearest-mode deferred aspect division."""

from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'tests'))
from deferred_lit_fog import ASPECT_RECIPROCAL, transform
from test_binary import host_environment


FIXTURE = r'''
#include <math.h>
#include <stdio.h>
#include <string.h>
static float fromBits(unsigned bits) { float f; memcpy(&f,&bits,4); return f; }
static unsigned bits(float f) { unsigned b; memcpy(&b,&f,4); return b; }
__declspec(noinline) float eager(float x, float denominator) {
    return x * (4.0f / 3.0f) / denominator;
}
__declspec(noinline) float projected(float x, float shipyardAspectDenominator,
                                    double modernAspectReciprocal, bool modernAspectReciprocalReady) {
/* ASPECT */
    return x;
}
static unsigned checked=0;
static bool check(float x, float d) {
    const bool eligible=d>=0.25f && d<=4.0f;
    const double reciprocal=eligible?1.0/(double)d:0.0;
    const float a=eager(x,d), b=projected(x,d,reciprocal,eligible);
    ++checked;
    if(bits(a)==bits(b)) return true;
    printf("mismatch x=%08x d=%08x eager=%08x projected=%08x\n",bits(x),bits(d),bits(a),bits(b));
    return false;
}
int main() {
    const float denominators[]={1920.0f/1080.0f,640.0f/480.0f,3440.0f/1440.0f,
        0.25f,4.0f,1.0f,fromBits(0x3f7fffff),fromBits(0x3f800001),
        fromBits(0x3fffffff),fromBits(0x40000001)};
    for(unsigned d=0;d<sizeof(denominators)/sizeof(denominators[0]);++d)
        for(unsigned m=0;m<0x800000;++m)
            if(!check(fromBits(0x3f800000|m),denominators[d])) return 1;
    unsigned seed=0x46c01237;
    for(unsigned i=0;i<3000000;++i) {
        seed=seed*1664525u+1013904223u; unsigned xb=seed;
        seed=seed*1664525u+1013904223u;
        float d=fromBits(0x3e800000+(seed%0x2000001));
        if(!check(fromBits(xb),d)) return 2;
    }
    const unsigned edges[]={0,0x80000000,1,0x80000001,0x007fffff,0x00800000,
        0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc12345,
        bits(1.0e-30f)-1,bits(1.0e-30f),bits(1.0e-30f)+1,
        bits(1.0e30f)-1,bits(1.0e30f),bits(1.0e30f)+1};
    const unsigned ds[]={0,0x80000000,1,0x7f800000,0x7fc12345,
        0x3e7fffff,0x3e800000,0x40800000,0x40800001};
    for(unsigned i=0;i<sizeof(edges)/sizeof(edges[0]);++i)
        for(unsigned j=0;j<sizeof(ds)/sizeof(ds[0]);++j)
            if(!check(fromBits(edges[i]),fromBits(ds[j]))) return 3;
    printf("%u aspect divisions match bit-for-bit\n",checked);
    return 0;
}
'''


class DeferredAspect(unittest.TestCase):
    def test_host_differential(self):
        output = ROOT / 'scratch/deferred-aspect'
        output.mkdir(parents=True, exist_ok=True)
        cpp = output / 'aspect.cpp'
        cpp.write_text(FIXTURE.replace('/* ASPECT */', ASPECT_RECIPROCAL))
        compiler, env = host_environment()
        for mode in ('precise', 'strict'):
            exe = output / ('aspect-' + mode + '.exe')
            result = subprocess.run([str(compiler), '/nologo', '/O2', '/fp:' + mode,
                                     str(cpp), '/Fe:' + str(exe), '/Fo:' + str(output) + '/'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(mode + ': ' + result.stdout.strip())

    def test_projection_is_idempotent_and_nearest_only(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        projected = transform(source)
        self.assertEqual(projected, transform(projected))
        vertex = projected.split('void Interpreter::GfxSpVertex(', 1)[1].split(
            'void Interpreter::GfxSpModifyVertex(', 1)[0]
        fast = vertex.split('if (mXboxDeferredReplay && shipyardVectorPositions)', 1)[1]
        self.assertIn(ASPECT_RECIPROCAL, fast)
        self.assertIn('Shipyard::Fast3D::NearestRounding()', vertex.split('bool shipyardAspectReady', 1)[0])
        compact, eager = fast.split('// MODERN DEFERRED POSITION REPLAY BATCH END', 1)
        self.assertIn('ClipFiniteVertices(modernDestination, n_vertices, false);', compact)
        self.assertIn('modernAspectReciprocalReady && shipyardAspectDenominator >= 0.5f', compact)
        self.assertIn('ClipVertices(modernDestination, n_vertices, false);\n        return;', compact)
        self.assertNotIn('SignedShortFloat', compact)
        self.assertIn('shipyardLightColorReady[MAX_LIGHTS] = {};', eager)


if __name__ == '__main__':
    unittest.main()
