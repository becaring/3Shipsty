"""Execute the emitted TRI2 run loop against per-command reference dispatch."""

from pathlib import Path
import subprocess
import sys
import unittest

from test_tri2_packed_reuse import host_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tri2_pair_projection import _run_transform, fuse_triangle_body


HANDLER = '''void Interpreter::GfxSpTri1(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect) {
    Record r={vtx1_idx,vtx2_idx,vtx3_idx,unsigned(current-beginning)}; records[count++]=r;
}
bool gfx_tri2_handler_f3dex(F3DGfx** cmd0) {
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    Tri2ProfileScope profile;
    gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);
    gfx->GfxSpTri1(C1(17, 7), C1(9, 7), C1(1, 7), false);
    return false;
}
void Interpreter::Configure(Debugger* dbg) {
    const bool xboxDebugging = dbg->IsDebugging();
}
'''

FIXTURE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct F3DGfx { struct { uintptr_t w0, w1; } words; };
namespace ModernFrameProfile { struct Sampler { bool enabled; } commandSampler; }
static unsigned starts, ends;
struct Tri2ProfileScope {
    Tri2ProfileScope() { ++starts; }
    ~Tri2ProfileScope() { ++ends; }
};
struct Debugger { bool enabled; bool IsDebugging() { return enabled; } };
static F3DGfx* current;
static F3DGfx* beginning;
struct Record { unsigned a,b,c,command; };
struct Interpreter {
    bool mXboxTriangleRunEnabled;
    Record records[128]; unsigned count;
    void Configure(Debugger*);
    void GfxSpTri1(uint8_t,uint8_t,uint8_t,bool);
    __forceinline void XboxRunTri2Triangle(uint8_t,uint8_t,uint8_t);
} owner;
static Interpreter* XboxDispatchInterpreter() { return &owner; }
#define C0(s,n) ((cmd->words.w0>>(s))&((1u<<(n))-1))
#define C1(s,n) ((cmd->words.w1>>(s))&((1u<<(n))-1))
/* HANDLER */
int main() {
    F3DGfx commands[33]={};
    for (unsigned i=0;i<32;++i) {
        const unsigned opcode = i<13 ? 0xb1 : i<17 ? 0x06 : 0xb1;
        commands[i].words.w0=(uintptr_t(opcode)<<24)|(i<<17)|((i+1)<<9)|((i+2)<<1);
        commands[i].words.w1=((i+3)<<17)|((i+4)<<9)|((i+5)<<1);
    }
    beginning=commands;
    Record reference[64];
    for(unsigned mode=0;mode<3;++mode) {
        owner.count=0; starts=ends=0;
        Debugger debugger={mode==0}; owner.Configure(&debugger);
        ModernFrameProfile::commandSampler.enabled=mode==1;
        unsigned dispatches=0;
        current=commands;
        while(current!=commands+32) {
            if(gfx_tri2_handler_f3dex(&current)) return 1;
            ++current; ++dispatches;
        }
        if(owner.count!=64 || starts!=32 || ends!=32) return 2;
        if(mode==0) memcpy(reference,owner.records,sizeof(reference));
        else if(memcmp(reference,owner.records,sizeof(reference))) return 3;
#ifdef USE_GBI_TRACE
        if(dispatches!=32) return 4;
#else
        if(dispatches!=(mode==2?3u:32u)) return 5;
#endif
    }
    puts("PASS TRI2 run dispatch bytes/order/pointer/profile/debugger/trace");
    return 0;
}
'''


class Tri2RunDispatch(unittest.TestCase):
    def test_emitted_loop_matches_command_order(self):
        out = ROOT / 'scratch/fast3d-xdk/tri2-run-dispatch'
        out.mkdir(parents=True, exist_ok=True)
        compiler, environment = host_environment()
        source = out / 'contract.cpp'
        handler = fuse_triangle_body(_run_transform(HANDLER))
        self.assertEqual(fuse_triangle_body(handler), handler)
        source.write_text(FIXTURE.replace('/* HANDLER */', handler))
        for trace in (False, True):
            exe = out / ('trace.exe' if trace else 'run.exe')
            command = [str(compiler), '/nologo', '/O2', '/EHsc', '/MD',
                       str(source), '/Fe:' + str(exe)]
            if trace:
                command.append('/DUSE_GBI_TRACE')
            built = subprocess.run(command, cwd=out, env=environment, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
