"""Compare sampled events and selection before/after the TRI2 caller guard."""

from pathlib import Path
import subprocess
import sys
import unittest

from test_tri2_packed_reuse import host_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tri2_pair_projection import _phase_profile


SOURCE = '''void Interpreter::GfxSpTri1() {
    if (vtx1_idx < MAX_VERTICES && mXboxDeferredVertices[vtx1_idx].context)
        XboxMaterializeVertex(vtx1_idx);
    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);
}
__declspec(noinline) void Interpreter::XboxEmitTriangle() {
    const XboxTrianglePipelineResult& p=mXboxPipelineResult;
        Flush();
        mXboxTrianglePairPrepared = false;
}
bool gfx_tri2_handler_f3dex() {
    // MODERN TRI2 PAIR CERTIFICATE END
    gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);
}
'''

FIXTURE = r'''
#include "application/frame_profile.h"
#include <stdio.h>
namespace ModernFrameProfile {
static bool inInterpreter,tri2ProfileEnabled;
static uint32_t tri2RandomState;
struct Stats { uint64_t ticks[Tri2PhaseCount],maximum[Tri2PhaseCount]; unsigned calls,samples; };
static Stats tri2;
static unsigned beginCalls,endCalls;
static uint64_t clockTick,eventHash;
static uint64_t Clock() { return ++clockTick; }
static void RecordTri2Phase(Tri2Sample& sample) {
    const uint64_t now=Clock();
    sample.ticks[sample.currentPhase]+=now-sample.lastTick;sample.lastTick=now;
    eventHash=eventHash*1664525u+sample.currentPhase+1;
}
/* FUNCTIONS */
}
static ModernFrameProfile::Tri2Sample* sModernTri2Sample;
/* SCOPES */
using namespace ModernFrameProfile;
struct Result { Stats stats; uint32_t random; uint64_t events; unsigned begins,ends; };
static void Advance() {
    if(sModernTri2Sample) AdvanceTri2(*sModernTri2Sample,Tri2Pipeline);
    if(sModernTri2Sample) AdvanceTri2(*sModernTri2Sample,Tri2Pack);
}
template<class Scope> static Result Run(bool enabled,bool interpreter) {
    memset(&tri2,0,sizeof(tri2));inInterpreter=interpreter;tri2ProfileEnabled=enabled;
    tri2RandomState=0x579321edu;beginCalls=endCalls=0;clockTick=eventHash=0;sModernTri2Sample=0;
    for(unsigned i=0;i<65536;++i) {
        Scope outer;Advance();
        if(i%17==0) { Scope inner;Advance(); }
        if(sModernTri2Sample) AdvanceTri2(*sModernTri2Sample,Tri2Cull);
    }
    Result result={tri2,tri2RandomState,eventHash,beginCalls,endCalls};return result;
}
int main() {
    for(unsigned mode=0;mode<4;++mode) {
        Result original=Run<OriginalScope>((mode&1)!=0,(mode&2)!=0);
        Result guarded=Run<Tri2ProfileScope>((mode&1)!=0,(mode&2)!=0);
        if(memcmp(&original.stats,&guarded.stats,sizeof(Stats)) ||
           original.random!=guarded.random || original.events!=guarded.events ||
           original.begins!=guarded.begins || guarded.ends!=guarded.stats.samples ||
           guarded.ends>=original.ends || sModernTri2Sample) return 1;
        printf("PASS TRI2 scope mode=%u begins=%u old_ends=%u guarded_ends=%u events=%llu\n",
               mode,guarded.begins,original.ends,guarded.ends,guarded.events);
    }
    return 0;
}
'''


class Tri2ProfileScope(unittest.TestCase):
    def test_actual_scope_preserves_selection_events_and_nested_pointer(self):
        projected = _phase_profile(SOURCE)
        scope = 'struct Tri2ProfileScope' + projected.split('struct Tri2ProfileScope', 1)[1].split('\n    };', 1)[0] + '\n};'
        baseline = scope.replace('Tri2ProfileScope', 'OriginalScope').replace('if (sample.sampled) ', '')
        services = (ROOT / 'platform/shipyard/xenos/services.cpp').read_text()
        functions = []
        for name in ('BeginTri2', 'AdvanceTri2', 'EndTri2'):
            start = services.index('void ' + name + '(')
            body = services[start:services.index('\n}', start) + 2]
            if name != 'AdvanceTri2':
                counter = 'beginCalls' if name == 'BeginTri2' else 'endCalls'
                body = body.replace('{', '{\n    ++' + counter + ';', 1)
            functions.append(body)
        fixture = FIXTURE.replace('/* FUNCTIONS */', '\n'.join(functions)).replace('/* SCOPES */', baseline + '\n' + scope)
        out = ROOT / 'scratch/fast3d-xdk/tri2-profile-scope'
        out.mkdir(parents=True, exist_ok=True)
        source = out / 'contract.cpp'
        source.write_text(fixture)
        compiler, environment = host_environment()
        exe = out / 'contract.exe'
        built = subprocess.run([str(compiler), '/nologo', '/O2', '/EHsc', '/MD',
                                '/I' + str(ROOT / 'platform/shipyard'), str(source), '/Fe:' + str(exe)],
                               cwd=out, env=environment, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
