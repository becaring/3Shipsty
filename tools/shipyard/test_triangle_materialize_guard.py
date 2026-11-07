"""Guarded materializer call differential for surviving triangles."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deferred_lit_fog import TRIANGLE_MATERIALIZE_GUARD


class TriangleMaterializeGuard(unittest.TestCase):
    def test_guarded_triangle_bytes_and_calls(self):
        vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/vcvarsall.bat')
        compiler = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/bin/cl.exe')
        if not vcvars.is_file() or not compiler.is_file():
            self.skipTest('VS2010 host compiler unavailable')
        fixture = HOST_FIXTURE.replace('/* GUARDED CALLS */', TRIANGLE_MATERIALIZE_GUARD)
        with tempfile.TemporaryDirectory(prefix='modern-triangle-materialize-') as temp:
            cpp = Path(temp) / 'fixture.cpp'
            exe = Path(temp) / 'fixture.exe'
            batch = Path(temp) / 'build.bat'
            cpp.write_text(fixture)
            batch.write_text(f'@call "{vcvars}" x86 >nul\n'
                             f'@"{compiler}" /nologo /O2 /EHsc /fp:precise '
                             f'"{cpp}" /Fe"{exe}"\n')
            built = subprocess.run(['cmd.exe', '/c', str(batch)], capture_output=True, text=True)
            self.assertEqual(0, built.returncode, (built.stdout + built.stderr)[-4000:])
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-4000:])
            self.assertIn('guard_differential=passed', result.stdout)
            print(result.stdout.strip())


HOST_FIXTURE = r'''
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include <stddef.h>
enum { MAX_VERTICES=64 };
struct LoadedVertex { float x,y,z,w,u,v; uint8_t color[4],clip_rej; };
struct XboxDeferredContext { uint8_t references; uint8_t rgb[3]; };
struct XboxDeferredVertex { XboxDeferredContext* context; LoadedVertex source; };
struct Owner {
    LoadedVertex loaded[68];
    XboxDeferredVertex mXboxDeferredVertices[MAX_VERTICES];
    XboxDeferredContext contexts[MAX_VERTICES];
    unsigned calls,materialized; int throwAt;
    __declspec(noinline) void XboxMaterializeVertex(size_t index) {
        ++calls;
        if(index>=MAX_VERTICES) return;
        XboxDeferredVertex& pending=mXboxDeferredVertices[index];
        if(!pending.context) return;
        if(int(index)==throwAt) throw 17;
        loaded[index].u=pending.source.u;
        loaded[index].v=pending.source.v;
        for(int i=0;i<3;++i) loaded[index].color[i]=pending.context->rgb[i];
        loaded[index].color[3]=pending.source.color[3];
        --pending.context->references;
        pending.context=0;
        ++materialized;
    }
    void Baseline(uint8_t vtx1_idx,uint8_t vtx2_idx,uint8_t vtx3_idx) {
        XboxMaterializeVertex(vtx1_idx);
        XboxMaterializeVertex(vtx2_idx);
        XboxMaterializeVertex(vtx3_idx);
    }
    void Guarded(uint8_t vtx1_idx,uint8_t vtx2_idx,uint8_t vtx3_idx) {
/* GUARDED CALLS */
    }
};
static uint32_t seed=0x32ade413u;
static uint32_t next() {seed=seed*1664525u+1013904223u; return seed;}
static void setup(Owner& x) {
    memset(&x,0,sizeof(x));
    x.throwAt=-1;
    for(unsigned i=0;i<MAX_VERTICES;++i) {
        x.mXboxDeferredVertices[i].source.u=float(i*11);
        x.mXboxDeferredVertices[i].source.v=float(i*17);
        x.mXboxDeferredVertices[i].source.color[3]=uint8_t(i*5);
        x.contexts[i].rgb[0]=uint8_t(i*3);
        x.contexts[i].rgb[1]=uint8_t(i*7);
        x.contexts[i].rgb[2]=uint8_t(i*13);
        x.contexts[i].references=1;
        if(i%7==0) x.mXboxDeferredVertices[i].context=&x.contexts[i];
    }
}
static void rebase(Owner& x) {
    for(unsigned i=0;i<MAX_VERTICES;++i)
        if(x.mXboxDeferredVertices[i].context)
            x.mXboxDeferredVertices[i].context=&x.contexts[i];
}
int main() {
    unsigned saved=0;
    for(unsigned trial=0;trial<100000;++trial) {
        Owner a,b; setup(a); b=a; rebase(b);
        uint8_t v1=uint8_t(next()%68),v2=uint8_t(next()%68),v3=uint8_t(next()%68);
        if(trial%4==0) v2=v1;
        if(trial%11==0) v3=v1;
        a.Baseline(v1,v2,v3);
        b.Guarded(v1,v2,v3);
        if(memcmp(a.loaded,b.loaded,sizeof(a.loaded)) ||
           a.materialized!=b.materialized ||
           memcmp(a.contexts,b.contexts,sizeof(a.contexts))) return 1;
        for(unsigned i=0;i<MAX_VERTICES;++i)
            if(!!a.mXboxDeferredVertices[i].context !=
               !!b.mXboxDeferredVertices[i].context) return 2;
        saved+=a.calls-b.calls;
    }
    {
        Owner a,b; setup(a); b=a; rebase(b);
        a.throwAt=b.throwAt=0;
        bool baselineThrew=false,guardedThrew=false;
        try { a.Baseline(1,0,2); } catch(int e) { baselineThrew=e==17; }
        try { b.Guarded(1,0,2); } catch(int e) { guardedThrew=e==17; }
        if(!baselineThrew || !guardedThrew ||
           memcmp(a.loaded,b.loaded,sizeof(a.loaded)) ||
           a.materialized!=b.materialized ||
           memcmp(a.contexts,b.contexts,sizeof(a.contexts))) return 3;
    }
    Owner a,b; setup(a); b=a; rebase(b);
    const unsigned loops=10000000;
    volatile unsigned sink=0;
    clock_t t=clock();
    for(unsigned i=0;i<loops;++i) {a.Baseline(1,2,3); sink+=a.calls&1;}
    double baseline=1000.0*double(clock()-t)/CLOCKS_PER_SEC;
    t=clock();
    for(unsigned i=0;i<loops;++i) {b.Guarded(1,2,3); sink+=b.calls&1;}
    double guarded=1000.0*double(clock()-t)/CLOCKS_PER_SEC;
    printf("guard_differential=passed cases=100000 calls_saved=%u benchmark_loops=%u baseline_ms=%.2f guarded_ms=%.2f sink=%u\n",
           saved,loops,baseline,guarded,sink);
    return 0;
}
'''


if __name__ == '__main__':
    unittest.main()
