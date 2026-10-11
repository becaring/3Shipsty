"""Check opcode 0x32 timing coverage on the selected projected interpreter."""
import sys
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtx_hash_phase_projection import transform


class VtxHashProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()

    def test_handler_routes_and_deferred_recursion(self):
        projected = transform(self.source)
        self.assertEqual(transform(projected), projected)
        handler = projected.split('bool gfx_vtx_hash_handler_custom(', 1)[1].split('\n}', 1)[0]
        deferred = projected.split('bool Interpreter::XboxTryDeferVertices(', 1)[1].split('\n}', 1)[0]
        vertex = projected.split('void Interpreter::GfxSpVertex(', 1)[1].split('\n}', 1)[0]
        eager = projected.split('void Interpreter::GfxSpVertexEager(', 1)[1].split('\n}', 1)[0]
        self.assertEqual(handler.count('BeginVtxHash(sample);'), 1)
        self.assertEqual(handler.count('EndVtxHash(sample);'), 1)
        self.assertLess(handler.index('VtxHashLookup'), handler.index('GetResourceRawPointer(hash)'))
        self.assertIn('VtxHashPointer', handler)
        self.assertIn('VtxHashResolved', handler)
        self.assertIn('VtxHashMissing', handler)
        self.assertLess(deferred.index('VtxHashTransform'), deferred.index('GfxSpVertexEager(n_vertices, dest_index, vertices);'))
        self.assertLess(deferred.index('VtxHashInsert'), deferred.index('pending.source = vertices[i];'))
        self.assertLess(vertex.index('VtxHashDeferred'), vertex.index('XboxTryDeferVertices(n_vertices'))
        self.assertLess(vertex.index('XboxTryDeferVertices(n_vertices'), vertex.index('VtxHashTransform'))
        self.assertIn('sModernVtxHashSample->vmx = shipyardVectorPositions;', eager)

    def test_handler_keeps_sampled_order_and_skips_unsampled_callbacks(self):
        sys.path.insert(0, str(ROOT / 'tools/shipyard/tests'))
        from test_binary import host_environment

        projected = transform(self.source)
        handler = 'bool gfx_vtx_hash_handler_custom(' + projected.split(
            'bool gfx_vtx_hash_handler_custom(', 1)[1].split('\n}', 1)[0] + '\n}'
        output = ROOT / 'scratch/vtx-profile-caller-guards'
        output.mkdir(parents=True, exist_ok=True)
        cpp = output / 'contract.cpp'
        cpp.write_text(HANDLER_FIXTURE.replace('/* HANDLER */', handler))
        compiler, env = host_environment()
        exe = output / 'contract.exe'
        result = subprocess.run([str(compiler), '/nologo', '/O2', '/EHsc', str(cpp),
                                 '/Fe:' + str(exe), '/Fo:' + str(output) + '/'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


HANDLER_FIXTURE = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
static char events[64];
static unsigned eventCount, beginCount, endCount, advanceCount;
static bool selectSample, failVertex, failLookup, missing;
static void Event(char c) { events[eventCount++]=c; events[eventCount]=0; }
namespace ModernFrameProfile {
enum VtxHashPhase { VtxHashLookup, VtxHashFinish };
enum VtxHashRoute { VtxHashPointer, VtxHashResolved, VtxHashMissing };
struct VtxHashSample { bool sampled; unsigned route; };
static unsigned endedRoute;
void BeginVtxHash(VtxHashSample& s) { Event('B'); ++beginCount; s.sampled=selectSample; }
void AdvanceVtxHash(VtxHashSample& s,VtxHashPhase phase) {
    Event(phase==VtxHashLookup?'L':'F'); ++advanceCount;
    if(!s.sampled) throw 99;
}
void EndVtxHash(VtxHashSample& s) {
    Event('E'); ++endCount; endedRoute=s.route;
    if(!s.sampled) Event('!');
}
}
static ModernFrameProfile::VtxHashSample outer={true,99};
static ModernFrameProfile::VtxHashSample* sModernVtxHashSample=&outer;
struct F3DVtx { unsigned char bytes[16]; };
struct F3DGfx { struct { uint32_t w0; uintptr_t w1; } words; };
static F3DVtx vertices[8];
static F3DVtx* received;
static unsigned receivedCount, receivedDest;
static bool badTls;
struct Interpreter {
    void GfxSpVertex(size_t n,size_t d,const F3DVtx* v) {
        Event('V'); received=(F3DVtx*)v; receivedCount=(unsigned)n; receivedDest=(unsigned)d;
        badTls=selectSample?(sModernVtxHashSample==&outer || !sModernVtxHashSample->sampled):
            (sModernVtxHashSample!=&outer);
        if(failVertex) throw 1;
    }
};
static Interpreter interpreter;
static Interpreter* XboxDispatchInterpreter() { return &interpreter; }
namespace Ship {
struct ResourceManager {
    void* GetResourceRawPointer(uint64_t) {
        Event('R'); if(failLookup) throw 2; return missing?NULL:vertices;
    }
};
struct Context {
    static Context* GetInstance() { static Context c; return &c; }
    ResourceManager* GetResourceManager() { static ResourceManager r; return &r; }
};
}
#define C0(shift,width) ((cmd->words.w0>>(shift))&((1u<<(width))-1u))
/* HANDLER */
int main() {
    const char* expected[2][3]={{"BV","BRV","BR"},{"BVFE","BLRVFE","BLRE"}};
    for(unsigned sampled=0;sampled<2;++sampled) for(unsigned route=0;route<3;++route) {
        for(unsigned failure=0;failure<3;++failure) {
            if((route==0 && failure==2) || (route==2 && failure==1)) continue;
            selectSample=sampled!=0; failVertex=failure==1; failLookup=failure==2; missing=route==2;
            events[0]=0; eventCount=beginCount=endCount=advanceCount=0; badTls=false; received=NULL;
            sModernVtxHashSample=&outer;
            F3DGfx command[2]={}; command[0].words.w0=(3u<<12)|(8u<<1);
            command[0].words.w1=route==0?(uintptr_t)(vertices+1):16;
            command[1].words.w1=42; F3DGfx* cursor=command;
            bool threw=false;
            try { if(gfx_vtx_hash_handler_custom(&cursor)) return 1; } catch(int) { threw=true; }
            if(beginCount!=1 || endCount!=sampled || badTls || sModernVtxHashSample!=&outer) return 2;
            if(threw!=(failure!=0)) return 3;
            if(!sampled && advanceCount) return 4;
            if(!failure) {
                if(strcmp(events,expected[sampled][route])) { puts(events); return 5; }
                if(cursor!=command+1) return 6;
                if(route!=2 && (received!=vertices+1 || receivedCount!=3 || receivedDest!=5)) return 7;
                if(route==1 && command[0].words.w1!=(uintptr_t)(vertices+1)) return 8;
                if(sampled && ModernFrameProfile::endedRoute!=route) return 9;
            } else {
                const char* want=failure==2?(sampled?"BLRE":"BR"):
                    (route==0?(sampled?"BVE":"BV"):(sampled?"BLRVE":"BRV"));
                if(strcmp(events,want)) { puts(events); return 10; }
            }
        }
    }
    return 0;
}
'''


if __name__ == '__main__':
    unittest.main()
