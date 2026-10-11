"""Compare the emitted compact triangle path with Modern's rendering semantics."""

from pathlib import Path
import subprocess
import sys
import unittest

from test_tri2_packed_reuse import host_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from compact_triangle_projection import method
from platform_base import resolve
from test_tri2_column_pack import HOST_FIXTURE


class CompactTriangles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        cls.out = ROOT / 'scratch/fast3d-xdk/compact-contract'
        cls.out.mkdir(parents=True, exist_ok=True)
        cls.compiler, cls.environment = host_environment()

    def run_fixture(self, name, fixture, defines=()):
        source = self.out / (name + '.cpp')
        exe = self.out / (name + '.exe')
        source.write_text(fixture)
        command = [str(self.compiler), '/nologo', '/O2', '/EHsc', '/MD', '/fp:strict',
                   '/I' + str(ROOT / 'platform/shipyard'), '/I' + str(resolve(ROOT) / 'sources'),
                   str(source), '/Fe:' + str(exe)]
        command += ['/D' + name for name in defines]
        built = subprocess.run(command, cwd=self.out, env=self.environment, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(exe)], cwd=self.out, capture_output=True, text=True)
        (self.out / (name + '.log')).write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_packed_bytes_all_material_inputs_and_rounding_modes(self):
        reference = method(self.source, '__declspec(noinline) void Interpreter::XboxEmitTriangle(')
        reference = reference[reference.index('    const XboxTrianglePipelineResult& p='):
                              reference.index('    // MODERN COLUMN PACK END')]
        compact = method(self.source, '__declspec(noinline) void Interpreter::XboxEmitTriangleCompact(')
        compact = compact[compact.index('    const XboxTrianglePipelineResult& p='):
                          compact.index('    if (++mBufVboNumTris == MAX_TRI_BUFFER)')]
        body = 'if (column) {\n' + reference + '\n    mBufVboLen = size_t(shipyardVertexOutput - mBufVbo);\n}\n'
        body += 'else {\n' + compact + '\n}\n'
        fixture = HOST_FIXTURE.replace('/* PACK BODY */', body)
        # The fixture's second half is a timing loop, outside this byte contract.
        stop = fixture.index('    RDP r={}; ColorCombiner comb={}; LoadedVertex verts[3]={};', fixture.index('    RDP r={};') + 1)
        fixture = fixture[:stop] + '''    }
    _controlfp(_RC_NEAR, _MCW_RC);
    puts("PASS compact pack bytes: 131072 cases, 0..7 inputs, four rounding modes");
    return 0;
}
'''
        fixture = '#include <float.h>\n' + fixture
        fixture = fixture.replace('    for(unsigned n=0;n<30000;++n) {', '''    const unsigned rounds[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    for(unsigned rn=0;rn<4;++rn) {
    _controlfp(rounds[rn],_MCW_RC);
    for(unsigned n=0;n<32768;++n) {''')
        fixture = fixture.replace('p.numInputs=uint8_t((n%3)+1);', 'p.numInputs=uint8_t((n>>12)&7);')
        fixture = fixture.replace('for(int j=0;j<3;++j)', 'for(int j=0;j<7;++j)')
        self.run_fixture('pack', fixture)

    def test_upstream_cull_inversion_and_exceptional_vertices(self):
        original = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        original = method(original, 'void Interpreter::GfxSpTri1(')
        original = original[:original.index('    bool depth_test =')] + '    emitted = true;\n}'
        original = original.replace('Interpreter::GfxSpTri1', 'Interpreter::Original')
        compact = method(self.source, '__forceinline void Interpreter::XboxWorkTriangleCompact(')
        cache = method(self.source, 'void Interpreter::XboxBeginCompactRun(') + '\n'
        cache += method(self.source, '__forceinline void Interpreter::XboxCompactNdc(')
        fixture = CULL_FIXTURE.replace('/* METHODS */', original + '\n' + cache + '\n' + compact)
        self.run_fixture('cull', fixture)

    def test_indexed_submission_flattens_to_the_reference_stream(self):
        self.run_fixture('indexed', self.indexed_fixture(INDEXED_MAIN))

    def test_pair_reuse_preserves_materials_and_flush_boundaries(self):
        self.run_reuse_fixture('compact-pair', PAIR_MAIN)

    def test_nonadjacent_triangles_pack_each_vertex_once(self):
        self.run_reuse_fixture('compact-nonadjacent', NONADJACENT_MAIN)

    def test_adjacent_commands_reuse_preserves_the_reference_stream(self):
        run = PAIR_MAIN.replace('unsigned indices[2][3]', 'unsigned indices[16][3]')
        run = run.replace('for(unsigned t=0;t<2;++t) for(unsigned v=0;v<3;++v)',
                          'for(unsigned t=0;t<16;++t) for(unsigned v=0;v<3;++v)')
        run = run.replace('                for(unsigned t=0;t<2;++t) {',
                          '                for(unsigned t=0;t<16;++t) {')
        run = run.replace('compact paired stream', 'compact consecutive-command stream')
        self.run_reuse_fixture('compact-run', run)

    def run_reuse_fixture(self, name, main):
        fixture = self.indexed_fixture(main)
        fixture = fixture.replace('const LoadedVertex input[3],bool is_rect)',
                                  'const LoadedVertex input[3],bool is_rect,const unsigned* indices=NULL)')
        for i in range(3):
            fixture = fixture.replace('&input[' + str(i) + ']', '&input[indices ? indices[' + str(i) + '] : ' + str(i) + ']')
        self.run_fixture(name, fixture)

    def indexed_fixture(self, main):
        prepare = method(self.source, '__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline()')
        lod = prepare[prepare.index('    // COMPACT TRIANGLE LOD INPUT BEGIN'):
                      prepare.index('    // COMPACT TRIANGLE LOD INPUT END')]
        lod = '{ const XboxTrianglePipelineResult& p=mXboxPipelineResult; ColorCombiner* comb=p.comb;\n' + lod + '\n}\n'
        reference = method(self.source, '__declspec(noinline) void Interpreter::XboxEmitTriangle(')
        reference = reference[reference.index('    const XboxTrianglePipelineResult& p='):
                              reference.index('    // MODERN COLUMN PACK END')]
        compact = method(self.source, '__declspec(noinline) void Interpreter::XboxEmitTriangleCompact(')
        compact = compact[compact.index('    const XboxTrianglePipelineResult& p='):compact.rindex('\n}')]
        body = 'if (column) {\n' + compact + '\n} else {\n' + reference
        body += '\n    mBufVboLen = size_t(shipyardVertexOutput - mBufVbo);\n}\n'
        fixture = HOST_FIXTURE[:HOST_FIXTURE.index('int main() {')]
        fixture = fixture.replace('/* PACK BODY */', body)
        fixture = fixture.replace('        const XboxTrianglePipelineResult& q=mXboxPipelineResult;',
                                  lod + '        const XboxTrianglePipelineResult& q=mXboxPipelineResult;')
        fixture = fixture.replace('float mBufVbo[512]', 'float mBufVbo[256 * 32 * 3]')
        fixture = fixture.replace('struct Runner {', INDEXED_MEMBERS)
        fixture = fixture.replace('''        const XboxTrianglePipelineResult& q=mXboxPipelineResult;''',
                                  '''        const XboxTrianglePipelineResult& q=mXboxPipelineResult;
        mXboxPackLayout[0] = 4;
        for(unsigned t=0;t<2;++t) if(q.usedTextures[t])
            mXboxPackLayout[0] += 2 + unsigned((q.tm&(1u<<2*t))!=0) + unsigned((q.tm&(1u<<(2*t+1)))!=0);
        mXboxPackLayout[0] += (q.fog?4:0) + (q.grayscale?4:0) + q.numInputs*(q.alpha?4:3);''')
        fixture = '''#define SHIPYARD_XENOS_INDEXED_TRIANGLES 1
#include <vector>
#include <cassert>
#include <float.h>
static const unsigned MAX_TRI_BUFFER=256;
namespace ModernFrameProfile {
enum { FlushBufferFull };
static void SetFlushReason(unsigned) {}
}
''' + fixture + main
        return fixture

    def test_hot_handler_has_no_diagnostic_stack(self):
        handler = method(self.source, 'bool gfx_tri2_handler_f3dex(')
        self.assertNotIn('Tri2ProfileScope', handler)
        self.assertNotIn('PairScope', handler)
        self.assertNotIn('mXboxPairPacked', handler)
        work = method(self.source, '__forceinline void Interpreter::XboxWorkTriangleCompact(')
        self.assertNotIn('ModernFrameProfile', work)
        self.assertNotIn('XboxMaterializeVertex', work)
        self.assertNotIn('ProjectionValueCache', work)
        emitter = method(self.source, '__declspec(noinline) void Interpreter::XboxEmitTriangleCompact(')
        self.assertNotIn('mXboxPairPacked', emitter)
        self.assertNotIn('sModernTri2Sample', emitter)
        self.assertIn('XboxPipelineCurrent(*this)', emitter)
        self.assertIn('XboxMaterializeVertex', emitter)

    def test_compact_dispatch_preserves_command_order_and_pointer(self):
        handler = method(self.source, 'bool gfx_tri2_handler_f3dex(')
        handler = method(self.source, 'static __declspec(noinline) bool XboxTri2ProfiledHandler(') + '\n' + handler
        self.run_fixture('dispatch', DISPATCH_FIXTURE.replace('/* HANDLER */', handler))

    def test_selected_indexed_backend_enables_compact_by_default(self):
        begin = self.source.index('    mXboxTriangleRunEnabled = !xboxDebugging;')
        end = self.source.index('#endif', begin) + len('#endif')
        fixture = SELECTION_FIXTURE.replace('/* SELECTION */', self.source[begin:end])
        self.run_fixture('selection', fixture)
        self.run_fixture('selection-trace', fixture, ('USE_GBI_TRACE',))


SELECTION_FIXTURE = r'''
#define _XBOX 1
#include "fast3d/indexed_submission.h"
#include <cassert>
#include <stdio.h>
namespace ModernFrameProfile {
static bool details;
static bool TriangleDiagnosticsEnabled() { return details; }
}
static int requested=-1;
static volatile unsigned gModernCompactPairControl[2]={1,0};
static volatile unsigned gModernCompactTriangleControl[1]={1};
static int CVarGetInteger(const char*,int fallback) { return requested<0?fallback:requested; }
struct Interpreter {
    bool mXboxTriangleRunEnabled,mXboxTriangleDiagnostics,mXboxCompactTriangles;
    bool mXboxCompactPairEnabled;
    void XboxRefreshCompactRounding() {}
    void Configure(bool xboxDebugging) {
/* SELECTION */
    }
};
int main() {
#if !defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)
#error The selected Xbox backend must exercise indexed submission.
#endif
    Interpreter owner;
    owner.Configure(false);
    assert(owner.mXboxCompactPairEnabled && gModernCompactPairControl[1]);
#ifdef USE_GBI_TRACE
    assert(!owner.mXboxCompactTriangles);
#else
    assert(owner.mXboxCompactTriangles);
    ModernFrameProfile::details=true;
    owner.Configure(false);
    assert(owner.mXboxCompactTriangles && owner.mXboxTriangleDiagnostics);
#endif
    requested=0;
    gModernCompactPairControl[0]=0;
    owner.Configure(false);
    assert(!owner.mXboxCompactPairEnabled && !gModernCompactPairControl[1]);
    assert(!owner.mXboxCompactTriangles);
    requested=1;
    owner.Configure(true);
    assert(!owner.mXboxCompactTriangles && !owner.mXboxTriangleRunEnabled);
    puts("PASS selected Xbox indexed backend: compact default, diagnostics, reference and debug/trace gates");
    return 0;
}
'''


INDEXED_MEMBERS = r'''struct Runner {
    size_t mXboxPackLayout[6],mXboxIndexedRows,mXboxIndexedStride,mBufVboNumTris;
    bool mXboxCompactPairActive,mXboxCompactPairValid;
    bool mXboxCompactTriangleLod;
    struct XboxCompactRowEntry { LoadedVertex* vertex; unsigned generation; uint16_t row; };
    XboxCompactRowEntry mXboxCompactRows[128];
    unsigned mXboxCompactRowGeneration;
    uint16_t mXboxTriangleIndices[256 * 3];
    std::vector<float> submitted;
    unsigned flushes,totalRows,totalCorners;
    void Flush() {
        mXboxCompactPairValid=false;
        if(!mBufVboLen) return;
        assert(mBufVboLen==mXboxIndexedRows*mXboxIndexedStride);
        assert(mBufVboLen<=256*32*3 && mBufVboNumTris<=256);
        totalRows+=unsigned(mXboxIndexedRows); totalCorners+=unsigned(3*mBufVboNumTris);
        for(unsigned i=0;i<3*mBufVboNumTris;++i) {
            assert(mXboxTriangleIndices[i]<mXboxIndexedRows);
            const float* row=mBufVbo + mXboxTriangleIndices[i]*mXboxIndexedStride;
            submitted.insert(submitted.end(),row,row+mXboxIndexedStride);
        }
        mXboxIndexedRows=mXboxIndexedStride=mBufVboNumTris=mBufVboLen=0;
        ++flushes;
    }
'''


INDEXED_MAIN = r'''
int main() {
    const unsigned rounds[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    unsigned checks=0;
    for(unsigned rn=0;rn<4;++rn) {
        _controlfp(rounds[rn],_MCW_RC);
        RDP r={}; ColorCombiner comb={}; XboxTrianglePipelineResult p={}; LoadedVertex vertices[3]={};
        p.comb=&comb;
        for(unsigned t=0;t<2;++t) {
            p.width[t]=32; p.height[t]=64; p.boundWidth[t]=16; p.boundHeight[t]=32;
        }
        for(unsigned i=0;i<7;++i) {
            comb.shader_input_mapping[0][i]=i%2?G_CCMUX_PRIMITIVE:G_CCMUX_SHADE;
            comb.shader_input_mapping[1][i]=i%2?G_CCMUX_ENVIRONMENT:G_CCMUX_SHADE;
        }
        r.prim_color=color();r.env_color=color();r.fog_color=color();r.grayscale_color=color();
        Runner a={},b={}; a.mRdp=b.mRdp=&r;
        std::vector<float> expected;
        for(unsigned mode=0;mode<8;++mode) {
            p.alpha=!!(mode&1); p.fog=mode>=4; p.grayscale=mode>=4;
            p.usedTextures[0]=comb.usedTextures[0]=mode>=2;
            p.usedTextures[1]=comb.usedTextures[1]=mode>=4;
            p.tm=mode>=4?15:0; p.numInputs=uint8_t(mode);
            a.mXboxPipelineResult=b.mXboxPipelineResult=p;
            // More than a full buffer per layout also tests partial-buffer stride changes.
            for(unsigned tri=0;tri<600;++tri) {
                for(unsigned v=0;v<3;++v) {
                    vertices[v].x=small();vertices[v].y=small();vertices[v].z=small();vertices[v].w=1+v;
                    vertices[v].u=small();vertices[v].v=small();vertices[v].color=color();
                }
                a.mBufVboLen=0;
                a.Pack(false,vertices,!!(tri&1));
                expected.insert(expected.end(),a.mBufVbo,a.mBufVbo+a.mBufVboLen);
                b.Pack(true,vertices,!!(tri&1));
                ++checks;
            }
        }
        b.Flush();
        assert(b.flushes>8);
        assert(expected.size()==b.submitted.size());
        assert(!memcmp(&expected[0],&b.submitted[0],expected.size()*sizeof(float)));
    }
    _controlfp(_RC_NEAR,_MCW_RC);
    printf("PASS compact indexed stream: %u triangles, stride changes and capacity flushes\n",checks);
    return 0;
}
'''


NONADJACENT_MAIN = r'''
int main() {
    RDP r={}; ColorCombiner comb={}; XboxTrianglePipelineResult p={}; LoadedVertex vertices[6]={};
    p.comb=&comb; p.numInputs=1; comb.shader_input_mapping[0][0]=G_CCMUX_SHADE;
    Runner a={},b={}; a.mRdp=b.mRdp=&r; a.mXboxPipelineResult=b.mXboxPipelineResult=p;
    std::vector<float> expected;
    for(unsigned v=0;v<6;++v) {
        vertices[v].x=float(v); vertices[v].w=1; vertices[v].color=color();
    }
    unsigned indices[3][3]={{0,1,2},{3,4,5},{2,1,0}};
    b.mXboxCompactPairActive=true;
    for(unsigned run=0;run<3;++run) {
        if(run==1) b.mXboxCompactRowGeneration=~0u;
        for(unsigned v=0;v<6;++v) { vertices[v].x+=1; vertices[v].color=color(); }
        for(unsigned t=0;t<3;++t) {
            a.mBufVboLen=0; a.Pack(false,vertices,false,indices[t]);
            expected.insert(expected.end(),a.mBufVbo,a.mBufVbo+a.mBufVboLen);
            b.Pack(true,vertices,false,indices[t]);
        }
        b.Flush();
    }
    assert(expected.size()==b.submitted.size());
    assert(!memcmp(&expected[0],&b.submitted[0],expected.size()*sizeof(float)));
    if(b.totalRows!=18) { printf("FAIL nonadjacent rows: %u, expected 18\n",b.totalRows); return 1; }
    puts("PASS nonadjacent compact rows: six packed rows per run, changed vertices, flushes and generation wrap");
    return 0;
}
'''


PAIR_MAIN = r'''
int main() {
    const unsigned rounds[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    unsigned triangles=0,saved=0;
    for(unsigned rn=0;rn<4;++rn) {
        _controlfp(rounds[rn],_MCW_RC);
        RDP r={}; ColorCombiner comb={}; XboxTrianglePipelineResult p={}; LoadedVertex vertices[8]={};
        p.comb=&comb;
        Runner a={},b={}; a.mRdp=b.mRdp=&r;
        std::vector<float> expected;
        const uint8_t rgb[]={G_CCMUX_PRIMITIVE,G_CCMUX_SHADE,G_CCMUX_ENVIRONMENT,
            G_CCMUX_PRIMITIVE_ALPHA,G_CCMUX_ENV_ALPHA,G_CCMUX_PRIM_LOD_FRAC,G_CCMUX_LOD_FRACTION};
        const uint8_t alpha[]={0,1,2,G_CCMUX_PRIMITIVE,G_CCMUX_SHADE,
            G_CCMUX_ENVIRONMENT,G_ACMUX_PRIM_LOD_FRAC,7,G_CCMUX_LOD_FRACTION};
        for(unsigned mode=0;mode<32;++mode) {
            b.Flush();
            p.alpha=!!(mode&1); p.fog=!!(mode&2); p.grayscale=!!(mode&4);
            p.clip.invertY=!!(mode&8); p.clip.z_is_from_0_to_1=!!(mode&16);
            p.usedTextures[0]=comb.usedTextures[0]=!!(mode&8);
            p.usedTextures[1]=comb.usedTextures[1]=!!(mode&16);
            p.tm=mode&15; p.numInputs=uint8_t(mode&7);
            for(unsigned t=0;t<2;++t) {
                p.width[t]=32; p.height[t]=64; p.boundWidth[t]=16; p.boundHeight[t]=32;
            }
            a.mXboxPipelineResult=b.mXboxPipelineResult=p;
            for(unsigned command=0;command<1200;++command) {
                r.other_mode_l=command%5==0 ? G_TL_LOD : 0;
                r.other_mode_h=command&1 ? 1u<<G_MDSFT_TEXTFILT : 0;
                for(unsigned t=0;t<2;++t) {
                    r.texture_tile[t].shifts=int(next()%16);r.texture_tile[t].shiftt=int(next()%16);
                    r.texture_tile[t].uls=small();r.texture_tile[t].ult=small();
                }
                r.prim_color=color();r.env_color=color();r.fog_color=color();r.grayscale_color=color();
                r.prim_lod_fraction=uint8_t(next());
                for(unsigned j=0;j<7;++j) {
                    comb.shader_input_mapping[0][j]=rgb[next()%7];
                    comb.shader_input_mapping[1][j]=alpha[next()%9];
                }
                for(unsigned v=0;v<8;++v) {
                    vertices[v].x=small();vertices[v].y=small();vertices[v].z=small();
                    vertices[v].w=float(next()%10000);vertices[v].u=small();vertices[v].v=small();vertices[v].color=color();
                }
                unsigned indices[2][3];
                for(unsigned t=0;t<2;++t) for(unsigned v=0;v<3;++v) indices[t][v]=next()%8;
                // Cover every reused corner, including three reused rows and duplicate indices.
                if(command%4==0) for(unsigned v=0;v<3;++v) indices[1][v]=indices[0][2-v];
                b.mXboxCompactPairActive=true;b.mXboxCompactPairValid=false;
                for(unsigned t=0;t<2;++t) {
                    if(command%11==t) continue; // A culled first/second triangle emits nothing.
                    if(t && command%19==0) b.Flush();
                    const bool rectangle=command%17==0;
                    a.mBufVboLen=0;
                    a.Pack(false,vertices,rectangle,indices[t]);
                    expected.insert(expected.end(),a.mBufVbo,a.mBufVbo+a.mBufVboLen);
                    b.Pack(true,vertices,rectangle,indices[t]);
                    ++triangles;
                }
                b.mXboxCompactPairActive=b.mXboxCompactPairValid=false;
            }
        }
        b.Flush();
        assert(b.totalRows<b.totalCorners);
        saved+=b.totalCorners-b.totalRows;
        assert(expected.size()==b.submitted.size());
        if(memcmp(&expected[0],&b.submitted[0],expected.size()*sizeof(float))) return 1;
    }
    _controlfp(_RC_NEAR,_MCW_RC);
    printf("PASS compact paired stream: %u triangles, %u rows reused; materials, LOD, rectangles, culls and flushes\n",triangles,saved);
    return 0;
}
'''


DISPATCH_FIXTURE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct F3DGfx { struct { uintptr_t w0,w1; } words; };
namespace ModernFrameProfile {
    struct Sampler { bool enabled; } commandSampler;
    struct Tri2Sample { bool sampled; };
    static unsigned begins,ends;
    static void BeginTri2(Tri2Sample& sample) { ++begins; sample.sampled=true; }
    static void EndTri2(Tri2Sample&) { ++ends; }
}
static ModernFrameProfile::Tri2Sample* sModernTri2Sample;
static F3DGfx* current;
static F3DGfx* beginning;
struct Record { unsigned a,b,c,command; };
struct Interpreter {
    bool mXboxCompactTriangles,mXboxTriangleRunEnabled,mXboxTriangleDiagnostics;
    bool mXboxCompactPairEnabled;
    bool mXboxCompactPairActive,mXboxCompactPairValid;
    unsigned runStarts;
    void XboxBeginCompactRun() {
        ++runStarts;
        mXboxCompactPairActive=mXboxCompactPairEnabled;
        mXboxCompactPairValid=false;
    }
    Record records[64]; unsigned count;
    void XboxWorkTriangleCompact(uint8_t a,uint8_t b,uint8_t c,bool) {
        Record r={a,b,c,unsigned(current-beginning)}; records[count++]=r;
    }
    void XboxWorkTriangleProfiled(uint8_t a,uint8_t b,uint8_t c,bool rectangle) {
        XboxWorkTriangleCompact(a,b,c,rectangle);
    }
} owner;
static Interpreter* XboxDispatchInterpreter() { return &owner; }
static unsigned diagnosticCalls;
static bool XboxTri2ReferenceHandler(F3DGfx** command) {
    ++diagnosticCalls;
    for(unsigned triangle=0;triangle<2;++triangle) {
        const uintptr_t word=triangle?(*command)->words.w1:(*command)->words.w0;
        owner.XboxWorkTriangleCompact(uint8_t((word>>17)&127),uint8_t((word>>9)&127),uint8_t((word>>1)&127),false);
    }
    return false;
}
#define C0(s,n) ((cmd->words.w0>>(s))&((1u<<(n))-1))
#define C1(s,n) ((cmd->words.w1>>(s))&((1u<<(n))-1))
/* HANDLER */
int main() {
    F3DGfx commands[33]={};
    for(unsigned i=0;i<32;++i) {
        const unsigned opcode=i<13?0xb1:i<17?0x06:0xb1;
        commands[i].words.w0=(uintptr_t(opcode)<<24)|(i<<17)|((i+1)<<9)|((i+2)<<1);
        commands[i].words.w1=((i+3)<<17)|((i+4)<<9)|((i+5)<<1);
    }
    beginning=commands;
    Record reference[64];
    for(unsigned mode=0;mode<5;++mode) {
        owner.count=diagnosticCalls=0;
        owner.runStarts=0;
        owner.mXboxCompactPairEnabled=true;
        ModernFrameProfile::begins=ModernFrameProfile::ends=0;
        owner.mXboxCompactTriangles=mode!=0;
        owner.mXboxTriangleDiagnostics=mode==4;
        owner.mXboxTriangleRunEnabled=mode!=3;
        ModernFrameProfile::commandSampler.enabled=mode==1;
        unsigned dispatches=0;
        current=commands;
        while(current!=commands+32) {
            if(gfx_tri2_handler_f3dex(&current)) return 1;
            if(owner.mXboxCompactPairActive || owner.mXboxCompactPairValid) return 7;
            ++current; ++dispatches;
        }
        if(owner.count!=64) return 2;
        if(mode==0) memcpy(reference,owner.records,sizeof(reference));
        else if(memcmp(reference,owner.records,sizeof(reference))) return 3;
        if(dispatches!=((mode==2||mode==4)?3u:32u)) return 4;
        if(diagnosticCalls!=(mode==0?32u:0u)) return 5;
        if(owner.runStarts!=(mode==0?0:dispatches)) return 8;
        if(ModernFrameProfile::begins!=(mode==4?32u:0u) ||
           ModernFrameProfile::ends!=ModernFrameProfile::begins || sModernTri2Sample) return 6;
    }
    puts("PASS compact TRI2 dispatch: indices, order, pointer, sampler and run boundaries");
    return 0;
}
'''


CULL_FIXTURE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <float.h>
enum { CULL_FRONT, CULL_BACK, CULL_BOTH };
struct UcodeHandlers { enum { ucode_f3dex2=4 }; };
static unsigned ucode_handler_index;
static const unsigned G_EX_INVERT_CULLING=1;
static uint32_t get_attr(unsigned attr) {
    return (attr+1) << (ucode_handler_index<4?12:9);
}
struct LoadedVertex { float x,y,z,w; unsigned clip_rej; };
struct RSP { LoadedVertex loaded_vertices[8]; unsigned geometry_mode,extra_geometry_mode; };
struct Interpreter {
    RSP* mRsp; bool emitted;
    bool mXboxCompactPairEnabled,mXboxCompactPairActive,mXboxCompactPairValid;
    struct XboxCompactNdcEntry { unsigned generation; float x,y; };
    XboxCompactNdcEntry mXboxCompactNdc[128];
    unsigned mXboxCompactNdcGeneration;
    void XboxBeginCompactRun();
    __forceinline void XboxCompactNdc(uint8_t,float&,float&);
    void Original(uint8_t,uint8_t,uint8_t,bool);
    __forceinline void XboxWorkTriangleCompact(uint8_t,uint8_t,uint8_t,bool);
    void XboxEmitTriangleCompact(LoadedVertex*,LoadedVertex*,LoadedVertex*,bool) { emitted=true; }
};
/* METHODS */
static uint32_t seed=17;
static uint32_t next() { seed=1664525u*seed+1013904223u; return seed; }
int main() {
    const unsigned rounds[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    const uint32_t special[]={0,0x80000000u,0x7f800000u,0xff800000u,0x7fc00000u,
        1,0x80000001u,0x3f800000u,0xbf800000u,0x7f7fffffu};
    unsigned checks=0;
    for(unsigned rn=0;rn<4;++rn) {
        _controlfp(rounds[rn],_MCW_RC);
        for(ucode_handler_index=0;ucode_handler_index<6;++ucode_handler_index) {
            for(unsigned n=0;n<16000;++n) {
                RSP rsp={};
                rsp.geometry_mode=(n&3) << (ucode_handler_index<4?12:9);
                rsp.extra_geometry_mode=(n>>2)&1;
                for(unsigned i=0;i<8;++i) {
                    float* p=&rsp.loaded_vertices[i].x;
                    for(unsigned k=0;k<4;++k) {
                        if(n&8) { uint32_t bits=special[next()%10]; memcpy(p+k,&bits,4); }
                        else p[k]=float(int(next()%10001)-5000)*0.03125f;
                    }
                    rsp.loaded_vertices[i].clip_rej=(n&16)?next()%64:0;
                }
                Interpreter a={&rsp,false},b={&rsp,false};
                b.mXboxCompactPairEnabled=!!(n&1);
                // Force generation rollover with poisoned entries as well as normal run changes.
                if(n%7==0) {
                    b.mXboxCompactNdcGeneration=0xffffffffu;
                    for(unsigned slot=0;slot<128;++slot) {
                        b.mXboxCompactNdc[slot].generation=1;
                        b.mXboxCompactNdc[slot].x=13;b.mXboxCompactNdc[slot].y=-17;
                    }
                }
                for(unsigned run=0;run<2;++run) {
                    b.XboxBeginCompactRun();
                    for(unsigned tri=0;tri<16;++tri) {
                        a.emitted=b.emitted=false;
                        const uint8_t i=uint8_t(next()%8),j=uint8_t(next()%8),k=uint8_t(next()%8);
                        a.Original(i,j,k,false); b.XboxWorkTriangleCompact(i,j,k,false);
                        if(a.emitted!=b.emitted) { printf("FAIL cull %u/%u/%u/%u\n",rn,ucode_handler_index,n,tri);return 1; }
                        ++checks;
                    }
                    b.mXboxCompactPairActive=b.mXboxCompactPairValid=false;
                    // A vertex command between runs replaces positions in the same slots.
                    for(unsigned slot=0;slot<8;++slot) {
                        rsp.loaded_vertices[slot].x=-rsp.loaded_vertices[slot].x;
                        rsp.loaded_vertices[slot].y+=0.5f;
                    }
                }
            }
        }
    }
    _controlfp(_RC_NEAR,_MCW_RC);
    printf("PASS compact cull: %u cases, six ucodes, four rounding modes\n",checks);
    return 0;
}
'''


if __name__ == '__main__':
    unittest.main()
