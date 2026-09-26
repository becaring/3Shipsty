"""TRI2 pair certificate reuse: projection, differential, and benchmark."""
import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tri2_pair_projection import header, transform


class Tri2PairProjection(unittest.TestCase):
    def test_pair_scope_and_flush_guard(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        projected = transform(source)
        handler = projected.split('bool gfx_tri2_handler_f3dex(', 1)[1].split('\n}', 1)[0]
        self.assertIn('mXboxTrianglePairActive = true;', handler)
        self.assertIn('mXboxTrianglePairPrepared = false;', handler)
        self.assertIn('mXboxTrianglePairActive = false;', handler)
        emitter = projected.split('void Interpreter::XboxEmitTriangle(', 1)[1].split('\n}', 1)[0]
        self.assertIn('mXboxTrianglePairActive && mXboxTrianglePairPrepared', emitter)
        self.assertTrue('mXboxTrianglePairPrepared = mXboxTrianglePairActive && mXboxPipelineKey.valid;' in emitter)
        self.assertIn('mXboxTrianglePairPrepared = false;', emitter)

    def test_header_owns_pair_state(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/include/fast/interpreter.h').read_text()
        projected = header(source)
        self.assertIn('bool mXboxTrianglePairActive;', projected)
        self.assertIn('bool mXboxTrianglePairPrepared;', projected)

    def test_selected_certificate_pair_differential_and_benchmark(self):
        vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/vcvarsall.bat')
        compiler = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/bin/cl.exe')
        if not vcvars.is_file() or not compiler.is_file():
            self.skipTest('VS2010 host compiler unavailable')
        lock = json.loads((ROOT / 'platform-base.lock.json').read_text())
        header_text = (ROOT / lock['base'] / 'sources/fast3d/triangle_pipeline.h').read_text()
        fixture = HOST_FIXTURE.replace('/* SELECTED CERTIFICATE */', header_text)
        with tempfile.TemporaryDirectory(prefix='modern-tri2-') as temp:
            cpp = Path(temp) / 'fixture.cpp'
            exe = Path(temp) / 'fixture.exe'
            batch = Path(temp) / 'build.bat'
            cpp.write_text(fixture)
            batch.write_text(f'@call "{vcvars}" x86 >nul\n'
                             f'@"{compiler}" /nologo /O2 /EHsc /fp:precise "{cpp}" /Fe"{exe}"\n')
            built = subprocess.run(['cmd.exe', '/c', str(batch)], capture_output=True, text=True)
            self.assertEqual(0, built.returncode, (built.stdout + built.stderr)[-3000:])
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-3000:])
            self.assertIn('differential=passed', result.stdout)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()


HOST_FIXTURE = r'''
#include <stdint.h>
#include <stddef.h>
#include <cstring>
#include <cstdio>
#include <ctime>
#define G_ZBUFFER 1
struct GfxClipParameters { bool z_is_from_0_to_1, invertY; };
struct TextureCacheNode { struct { bool linear_filter; unsigned char cms,cmt; } second; };
struct ColorCombiner { bool usedTextures[2]; };
struct RenderingState {
    uint8_t depth_test_and_mask;
    bool decal_mode,alpha_blend;
    int viewport[4],scissor[4];
    void* shader;
    TextureCacheNode* mTextures[2];
};
struct RSP { unsigned geometry_mode; };
struct RDP {
    bool viewport_or_scissor_changed, grayscale;
    uint64_t combine_mode;
    uint32_t other_mode_l,other_mode_h;
    unsigned char first_tile_index;
    bool textures_changed[2];
    struct Loaded {
        bool masked,blended;
        unsigned size_bytes,line_size_bytes,full_image_line_size_bytes,orig_size_bytes;
    } loaded_texture[2];
    struct Tile {
        float uls,ult,lrs,lrt;
        unsigned char tmem_index,siz,cms,cmt;
        unsigned line_size_bytes;
    } texture_tile[8];
};
struct Owner {
    RDP* mRdp; RSP* mRsp; RenderingState mRenderingState;
    void* mRapi; GfxClipParameters clip;
    bool redirect,shaderPresent; int64_t shaderIdentity;
};
struct XboxTrianglePipelineTraits {
    static GfxClipParameters Clip(const Owner& x) { return x.clip; }
    static bool Redirect(const Owner& x) { return x.redirect; }
    static bool ShaderPresent(const Owner& x) { return x.shaderPresent; }
    static int64_t ShaderIdentity(const Owner& x) { return x.shaderIdentity; }
    static unsigned EffectiveTile(const Owner& x,unsigned i) { return x.mRdp->first_tile_index+i; }
};
/* SELECTED CERTIFICATE */
static unsigned seed=0x98025d31;
static unsigned next() { seed=seed*1664525u+1013904223u; return seed; }
static void setup(Owner& o,RDP& r,RSP& s,ColorCombiner& comb,XboxTrianglePipelineResult& p,
                  XboxTrianglePipelineKey& key) {
    std::memset(&o,0,sizeof(o)); std::memset(&r,0,sizeof(r));
    std::memset(&s,0,sizeof(s)); std::memset(&comb,0,sizeof(comb));
    std::memset(&p,0,sizeof(p));
    o.mRdp=&r; o.mRsp=&s; o.mRapi=&r;
    p.comb=&comb; comb.usedTextures[0]=true;
    r.loaded_texture[0].size_bytes=1024;
    r.loaded_texture[0].line_size_bytes=64;
    r.loaded_texture[0].full_image_line_size_bytes=64;
    r.loaded_texture[0].orig_size_bytes=1024;
    r.texture_tile[0].lrs=31; r.texture_tile[0].lrt=31;
    key.Capture(o,p);
}
__declspec(noinline) static bool check(const XboxTrianglePipelineKey& key,const Owner& o) {
    return key.Matches(o);
}
static int differential() {
    Owner o; RDP r; RSP s; ColorCombiner comb; XboxTrianglePipelineResult p;
    XboxTrianglePipelineKey base,pair;
    setup(o,r,s,comb,p,base); pair=base;
    unsigned emittedBase=0,emittedPair=0,checksBase=0,checksPair=0;
    for(int command=0;command<1000000;++command) {
        if(command%137==0) {
            r.other_mode_h^=2;
            r.viewport_or_scissor_changed=(command%411==0);
            r.textures_changed[0]=(command%685==0);
        }
        bool first=(next()%13)!=0, second=(next()%17)!=0;
        bool prepared=false;
        for(int tri=0;tri<2;++tri) {
            if(!(tri?second:first)) continue;
            bool b=check(base,o); ++checksBase;
            if(!b) base.Capture(o,p);
            ++emittedBase;
            bool usePrepared=tri==1 && prepared && pair.valid;
            bool q=usePrepared || check(pair,o);
            if(!usePrepared) ++checksPair;
            if(!q) pair.Capture(o,p);
            ++emittedPair;
            if(b!=q || base.valid!=pair.valid) return 1;
            // A full vertex buffer Flush between halves disables the shortcut.
            prepared=pair.valid && emittedPair%256!=0;
        }
    }
    if(emittedBase!=emittedPair || checksPair>=checksBase) return 2;
    std::printf("differential=passed commands=1000000 checks_baseline=%u checks_pair=%u skipped=%u\n",
                checksBase,checksPair,checksBase-checksPair);
    return 0;
}
static void benchmark() {
    Owner o; RDP r; RSP s; ColorCombiner comb; XboxTrianglePipelineResult p;
    XboxTrianglePipelineKey key;
    setup(o,r,s,comb,p,key);
    const int pairs=3000000;
    volatile unsigned sink=0;
    clock_t start=clock();
    for(int i=0;i<pairs;++i) {
        if(i%256==0) { r.other_mode_h^=2; key.Capture(o,p); }
        sink+=check(key,o);
        sink+=check(key,o);
    }
    double baselineMs=1000.0*(clock()-start)/CLOCKS_PER_SEC;
    start=clock();
    for(int i=0;i<pairs;++i) {
        if(i%256==0) { r.other_mode_h^=2; key.Capture(o,p); }
        bool first=check(key,o);
        sink+=first;
        sink+=first && key.valid ? true : check(key,o);
    }
    double pairMs=1000.0*(clock()-start)/CLOCKS_PER_SEC;
    std::printf("certificate_benchmark pairs=%d baseline_ms=%.2f pair_ms=%.2f speedup=%.2f sink=%u\n",
                pairs,baselineMs,pairMs,baselineMs/pairMs,(unsigned)sink);
}
int main() { if(differential()) return 1; benchmark(); return 0; }
'''
