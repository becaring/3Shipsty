"""Contracts for the Modern-only deferred lit/fog vertex projection."""

import sys
import inspect
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from deferred_lit_fog import HEADER_TYPES, SOURCE_METHODS, finalize, header, transform
from platform_base import resolve


def normal_cache_fixture(fixture):
    anchor = '    XboxDeferredContext mXboxDeferredContexts[MAX_VERTICES];'
    return fixture.replace(anchor, anchor + '''
    XboxDeferredNormalEntry mXboxNormalCache[64];
    uint32_t mXboxNormalCacheSerial;
    bool mXboxNormalCacheEnabled;''')


def projected_source():
    source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
    if '// MODERN DIRECT DEFERRED VERTEX BEGIN' not in source:
        source = finalize(transform(source))
    return source


def projected_method(source, name):
    first = source.index(' Interpreter::' + name + '(')
    first = source.rfind('\n', 0, first) + 1
    brace = source.index('{', first)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[first:end] + '\n'


class DeferredLitFogProjection(unittest.TestCase):
    def test_projection_keeps_cull_before_attribute_materialization(self):
        projected = projected_source()
        triangle = projected.split('void Interpreter::GfxSpTri1(', 1)[1].split('void Interpreter::XboxPrepareTrianglePipeline(', 1)[0]
        self.assertLess(triangle.index('if (v1->clip_rej & v2->clip_rej & v3->clip_rej)'),
                        triangle.index('XboxMaterializeVertex(vtx1_idx)'))
        self.assertLess(triangle.index('XboxMaterializeVertex(vtx1_idx)'),
                        triangle.index('XboxEmitTriangle('))

    def test_projected_source_captures_vertices_and_mutable_state(self):
        projected = projected_source()
        self.assertIn('pending.source = vertices[i];', projected)
        self.assertIn('context->fogMul = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_mul);', SOURCE_METHODS)
        self.assertIn('context->scaleS = mRsp->texture_scaling_factor.s;', projected)
        self.assertIn('XboxMaterializeVertex(vtx_idx);', projected)
        self.assertIn('if (mXboxDeferredReplay) return false;', projected)
        modify = projected.split('void Interpreter::GfxSpModifyVertex(', 1)[1].split('\n}', 1)[0]
        self.assertLess(modify.index('SUPPORT_CHECK(where == G_MWO_POINT_ST)'),
                        modify.index('XboxMaterializeVertex(vtx_idx)'))
        self.assertLess(modify.index('XboxMaterializeVertex(vtx_idx)'), modify.index('v->u = s;'))

    def test_header_has_interpreter_owned_storage(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/include/fast/interpreter.h').read_text()
        projected = header(source)
        self.assertIn('XboxDeferredVertex mXboxDeferredVertices[MAX_VERTICES];', projected)
        self.assertIn('XboxDeferredContext mXboxDeferredContexts[MAX_VERTICES];', projected)

    def test_context_search_probe_is_opt_in_and_noniterative(self):
        self.assertIn('void XboxTakeContextSearchCounts(unsigned* attempts, unsigned* slots, unsigned* maximum);',
                      inspect.getsource(header))
        self.assertIn('mXboxContextProbeCapture = ModernFrameProfile::CaptureTrianglePipeline();',
                      inspect.getsource(transform))
        scan = SOURCE_METHODS.split('XboxDeferredContext* context = NULL;', 1)[1].split('if (!context) return false;', 1)[0]
        self.assertIn('for (size_t i = 0; i < MAX_VERTICES; ++i)', scan)
        self.assertEqual(scan.count('mXboxContextProbeCapture'), 1)
        self.assertLess(scan.index('for (size_t i = 0; i < MAX_VERTICES; ++i)'),
                        scan.index('mXboxContextProbeCapture'))
        self.assertIn('context ? (unsigned)(context - mXboxDeferredContexts) + 1 : MAX_VERTICES', scan)

    def test_branch_and_reset_keep_pending_attributes(self):
        projected = projected_source()
        vertex = projected_method(projected, 'GfxSpVertex')
        self.assertLess(vertex.index('if (XboxTryDeferVertices('), vertex.index('GfxSpVertexEager('))
        reset = projected.split('void Interpreter::SpReset() {', 1)[1].split('\n}', 1)[0]
        self.assertNotIn('mXboxDeferredVertices', reset)
        self.assertNotIn('mXboxDeferredContexts', reset)
        # The branch and cull operations consume already computed z/w/clip.
        triangle = projected.split('void Interpreter::GfxSpTri1(', 1)[1].split('void Interpreter::XboxPrepareTrianglePipeline(', 1)[0]
        self.assertTrue(triangle.index('v1->clip_rej') < triangle.index('XboxMaterializeVertex(vtx1_idx)'))
        self.assertTrue(triangle.index('v1->w') < triangle.index('XboxMaterializeVertex(vtx1_idx)'))
        self.assertIn('for (size_t i = 0; i < n_vertices; ++i) XboxDiscardVertex(dest_index + i);',
                      projected)
        deferred = projected_method(projected, 'XboxTryDeferVertices')
        self.assertLess(deferred.index('XboxDiscardVertex(dest_index + i)'),
                        deferred.index('context->references = (uint8_t)(context->references + n_vertices);'))

    def test_materializer_matches_eager_x86_fixture(self):
        vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/vcvarsall.bat')
        compiler = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/bin/cl.exe')
        if not vcvars.is_file() or not compiler.is_file():
            self.skipTest('VS2010 host compiler unavailable')
        fixture = HOST_FIXTURE.replace('/* PROJECTED TYPES */', HEADER_TYPES).replace(
            '/* PROJECTED METHODS */',
            SOURCE_METHODS.split('bool Interpreter::XboxTryDeferVertices(', 1)[0] +
            'void Interpreter::XboxMaterializeVertex(' +
            SOURCE_METHODS.split('void Interpreter::XboxMaterializeVertex(', 1)[1])
        fixture = '#include "' + (resolve(ROOT) / 'sources/fast3d/numeric.h').as_posix() + '"\n' + fixture
        fixture = normal_cache_fixture(fixture)
        with tempfile.TemporaryDirectory(prefix='modern-deferred-') as temp:
            cpp = Path(temp) / 'fixture.cpp'
            exe = Path(temp) / 'fixture.exe'
            cpp.write_text(fixture)
            batch = Path(temp) / 'build.bat'
            batch.write_text(f'@call "{vcvars}" x86 >nul\n'
                             f'@"{compiler}" /nologo /EHsc /fp:precise "{cpp}" /Fe"{exe}"\n')
            built = subprocess.run(['cmd.exe', '/c', str(batch)], capture_output=True, text=True)
            self.assertEqual(0, built.returncode, (built.stdout + built.stderr)[-3000:])
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-3000:])

    def test_projected_vertex_matches_eager_x86_fixture(self):
        vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/vcvarsall.bat')
        compiler = Path('C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/bin/cl.exe')
        if not vcvars.is_file() or not compiler.is_file():
            self.skipTest('VS2010 host compiler unavailable')
        source = projected_source()
        methods = ''.join(projected_method(source, name) for name in (
            'XboxDiscardVertex', 'XboxTryDeferVertices', 'XboxMaterializeVertex',
            'XboxTakeContextSearchCounts', 'XboxTransformDeferredPositions',
            'GfxSpVertex', 'GfxSpVertexEager'))
        if '// MODERN EXACT VERTEX REPLAY BEGIN' in source:
            helpers = source.split('// MODERN EXACT VERTEX REPLAY BEGIN', 1)[1]
            methods = helpers.split('// MODERN EXACT VERTEX REPLAY END', 1)[0] + methods
        fixture = FULL_VERTEX_FIXTURE.replace('/* PROJECTED TYPES */', HEADER_TYPES).replace(
            '/* PROJECTED METHODS */', methods)
        fixture = '#include "' + (resolve(ROOT) / 'sources/fast3d/numeric.h').as_posix() + '"\n' + fixture
        fixture = normal_cache_fixture(fixture)
        fixture = fixture.replace('bool NearestRounding() { return false; }',
                                  'static bool nearest = true, transformAvailable = true;\n'
                                  'bool NearestRounding() { return nearest; }')
        fixture = fixture.replace(
            'bool TransformPositions(const void*,size_t,const float [4][4],void*,bool=false,size_t=16) { return false; }',
            '''bool TransformPositions(const void* input,size_t count,const float m[4][4],void* output,bool=false,size_t stride=16) {
        if(!transformAvailable) return false;
        const F3DVtx* source=(const F3DVtx*)input;
        for(size_t i=0;i<count;++i) {
            float* out=(float*)((unsigned char*)output+i*stride);
            for(int c=0;c<4;++c) {
                const short* v=source[i].v.ob;
                out[c]=v[0]*m[0][c]+v[1]*m[1][c]+v[2]*m[2][c]+m[3][c];
            }
        }
        return true;
    }''')
        fixture = fixture.replace('void ClipVertices(LoadedVertex*,size_t,bool) {}',
                                  '''void ClipVertices(LoadedVertex* v,size_t count,bool) {
        for(size_t i=0;i<count;++i) {
            unsigned flags=0;
            if(v[i].x < -v[i].w) flags|=1;
            if(v[i].x > v[i].w) flags|=2;
            if(v[i].y < -v[i].w) flags|=4;
            if(v[i].y > v[i].w) flags|=8;
            if(v[i].z > v[i].w) flags|=32;
            v[i].clip_rej=(uint8_t)flags;
        }
    }''')
        with tempfile.TemporaryDirectory(prefix='modern-vertex-') as temp:
            cpp = Path(temp) / 'fixture.cpp'
            exe = Path(temp) / 'fixture.exe'
            batch = Path(temp) / 'build.bat'
            cpp.write_text(fixture)
            batch.write_text(f'@call "{vcvars}" x86 >nul\n'
                             f'@"{compiler}" /nologo /EHsc /fp:precise "{cpp}" /Fe"{exe}"\n')
            built = subprocess.run(['cmd.exe', '/c', str(batch)], capture_output=True, text=True)
            self.assertEqual(0, built.returncode, (built.stdout + built.stderr)[-3000:])
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-3000:])


HOST_FIXTURE = r'''
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <limits>
#include <stdio.h>
#define MAX_LIGHTS 32
#define MAX_VERTICES 64
struct F3DVtx_t { short ob[3], flag, tc[2]; unsigned char cn[4]; };
struct F3DVtx_tn { short ob[3], flag, tc[2]; signed char n[3]; unsigned char a; };
union F3DVtx { F3DVtx_t v; F3DVtx_tn n; };
struct RGBA { uint8_t r,g,b,a; };
struct LoadedVertex { float x,y,z,w,u,v; RGBA color; uint8_t clip_rej; };
struct RSP { LoadedVertex loaded_vertices[MAX_VERTICES+4]; int16_t fog_mul, fog_offset; };
namespace Ship { namespace Math { template<typename T> T clamp(T v,T lo,T hi) { return v<lo?lo:(v>hi?hi:v); } } }
/* PROJECTED TYPES */
class Interpreter {
public:
    RSP* mRsp;
    XboxDeferredVertex mXboxDeferredVertices[MAX_VERTICES];
    XboxDeferredContext mXboxDeferredContexts[MAX_VERTICES];
    bool mXboxContextProbeCapture;
    unsigned mXboxContextSearchAttempts, mXboxContextSlotsScanned, mXboxContextMaxScan;
    void XboxDiscardVertex(size_t index);
    void XboxMaterializeVertex(size_t index);
    void XboxTakeContextSearchCounts(unsigned*, unsigned*, unsigned*);
};
/* PROJECTED METHODS */
static unsigned seed = 0x23ab45cd;
static unsigned next() { seed=seed*1664525u+1013904223u; return seed; }
static void eager(LoadedVertex* d, const F3DVtx& source, const XboxDeferredContext& c) {
    const F3DVtx_t* v=&source.v;
    const F3DVtx_tn* vn=&source.n;
    short U=v->tc[0]*c.scaleS >> 16;
    short V=v->tc[1]*c.scaleT >> 16;
    int r=c.ambient[0],g=c.ambient[1],b=c.ambient[2];
    float normal[3]={(float)vn->n[0],(float)vn->n[1],(float)vn->n[2]};
    for(int i=0;i<c.count;++i) {
        float intensity=0;
        intensity+=normal[0]*c.lights[i].coeff[0];
        intensity+=normal[1]*c.lights[i].coeff[1];
        intensity+=normal[2]*c.lights[i].coeff[2];
        intensity/=127.0f;
        if(intensity>0.0f) {
            r+=intensity*c.lights[i].color[0];
            g+=intensity*c.lights[i].color[1];
            b+=intensity*c.lights[i].color[2];
        }
    }
    d->color.r=r>255?255:r; d->color.g=g>255?255:g; d->color.b=b>255?255:b;
    d->u=U; d->v=V;
    float w=d->w;
    if(fabsf(w)<0.001f) w=0.001f;
    float winv=1.0f/w;
    if(winv<0.0f) winv=std::numeric_limits<int16_t>::max();
    float fog_z=d->z*winv*c.fogMul+c.fogOffset;
    fog_z=Ship::Math::clamp(fog_z,0.0f,255.0f);
    d->color.a=fog_z;
}
int main() {
    Interpreter p; RSP rsp; memset(&p,0,sizeof(p)); memset(&rsp,0,sizeof(rsp)); p.mRsp=&rsp;
    unsigned verifiedCacheHits=0;
    for(int trial=0;trial<30000;++trial) {
        int slot=trial%MAX_VERTICES;
        XboxDeferredContext* c=&p.mXboxDeferredContexts[slot];
        memset(c,0,sizeof(*c)); c->count=next()%6; c->references=1;
        c->normalCacheSerial=++p.mXboxNormalCacheSerial;
        p.mXboxNormalCacheEnabled=!!(trial&8);
        c->ambient[0]=next()%256; c->ambient[1]=next()%256; c->ambient[2]=next()%256;
        c->scaleS=next()%65536; c->scaleT=next()%65536;
        c->fogMul=(short)(next()%30000); c->fogOffset=(short)(next()%512-256);
        for(int i=0;i<c->count;++i) for(int j=0;j<3;++j) {
            c->lights[i].coeff[j]=(float)((int)(next()%300)-150)/127.0f;
            c->lights[i].color[j]=(float)(next()%256);
        }
        // Odd trials take the bounded float path; both rounding flags must
        // reproduce the eager division.
        const bool floatTrial=(trial&1)!=0;
        c->nearest=(trial&2)!=0;
        if(floatTrial) {
            c->floatLighting=true; c->normalKey=0xffffffffu;
            for(int j=0;j<3;++j) c->ambientFloat[j]=(float)c->ambient[j];
            if(c->nearest && c->count>=2 && (trial&4)) {
                for(int j=0;j<3;++j)
                    c->lights[c->count-1].coeff[j]=-c->lights[c->count-2].coeff[j];
                c->opposedLastPair=true;
            }
        }
        F3DVtx input; memset(&input,0,sizeof(input));
        input.v.tc[0]=(short)next(); input.v.tc[1]=(short)next();
        input.n.n[0]=(signed char)next(); input.n.n[1]=(signed char)next(); input.n.n[2]=(signed char)next();
        if(trial%13==0) input.n.n[0]=input.n.n[1]=input.n.n[2]=0;
        LoadedVertex original; memset(&original,0,sizeof(original));
        original.x=(float)((int)(next()%2000)-1000);
        original.y=(float)((int)(next()%2000)-1000);
        original.z=(float)((int)(next()%2000)-1000)/1000.0f;
        original.w=(trial%4==0)?0.0f:(float)((int)(next()%2000)-1000)/1000.0f;
        original.clip_rej=(uint8_t)next();
        rsp.loaded_vertices[slot]=original;
        p.mXboxDeferredVertices[slot].source=input;
        p.mXboxDeferredVertices[slot].context=c;
        LoadedVertex expected=original;
        eager(&expected,input,*c);
        const F3DVtx kept=input;
        // Later commands can mutate the original input, light/fog state and RSP.
        memset(&input,0x5a,sizeof(input)); rsp.fog_mul=1; rsp.fog_offset=-17;
        p.XboxMaterializeVertex(slot);
        if(memcmp(&expected,&rsp.loaded_vertices[slot],sizeof(expected)) ||
           p.mXboxDeferredVertices[slot].context || c->references) {
            printf("trial %d differs\n",trial); return 1;
        }
        // Materialization is idempotent, then ModifyVertex may override ST.
        p.XboxMaterializeVertex(slot);
        if(memcmp(&expected,&rsp.loaded_vertices[slot],sizeof(expected))) return 2;
        rsp.loaded_vertices[slot].u=1234; rsp.loaded_vertices[slot].v=-5678;
        expected.u=1234; expected.v=-5678;
        p.XboxMaterializeVertex(slot);
        if(memcmp(&expected,&rsp.loaded_vertices[slot],sizeof(expected))) return 4;
        if(floatTrial) {
            // The same normal reuses the snapshot's RGB; fog stays per vertex.
            const int other=(slot+1)%MAX_VERTICES;
            LoadedVertex second=original;
            second.z=(float)((int)(next()%2000)-1000)/1000.0f;
            second.w=(float)((int)(next()%2000)-1000)/1000.0f;
            rsp.loaded_vertices[other]=second;
            p.mXboxDeferredVertices[other].source=kept;
            p.mXboxDeferredVertices[other].context=c; c->references=1;
            LoadedVertex again=second;
            eager(&again,kept,*c);
            p.XboxMaterializeVertex(other);
            if(memcmp(&again,&rsp.loaded_vertices[other],sizeof(again)) || c->references) return 7;
            // Compare caching with the same materializer bypassed. The eager
            // arithmetic contract above remains independent of this cache test.
            // Revisit normals, collisions, texture coordinates and fog inputs.
            const unsigned originalSeed=seed;
            for(unsigned pass=0;pass<96;++pass) {
                F3DVtx repeated=kept;
                const unsigned normal=pass%24;
                repeated.n.n[0]=(signed char)(normal*19-127);
                repeated.n.n[1]=(signed char)(normal*7-63);
                repeated.n.n[2]=(signed char)(normal*11-31);
                repeated.v.tc[0]=(short)next(); repeated.v.tc[1]=(short)next();
                const uint32_t key=(uint32_t(uint8_t(repeated.n.n[0]))<<16) |
                    (uint32_t(uint8_t(repeated.n.n[1]))<<8) | uint8_t(repeated.n.n[2]);
                const XboxDeferredNormalEntry& entry=p.mXboxNormalCache[(key*2654435761u)>>26];
                if(p.mXboxNormalCacheEnabled && c->nearest && c->normalKey!=key &&
                   entry.context==c && entry.serial==c->normalCacheSerial && entry.normal==key)
                    ++verifiedCacheHits;
                LoadedVertex value=original;
                value.z=float(int(next()%2000)-1000)/1000.0f;
                value.w=float(int(next()%2000)-1000)/1000.0f;
                rsp.loaded_vertices[other]=value;
                const XboxDeferredContext savedContext=*c;
                const bool cacheEnabled=p.mXboxNormalCacheEnabled;
                p.mXboxNormalCacheEnabled=false;c->normalKey=0xffffffffu;
                p.mXboxDeferredVertices[other].source=repeated;
                p.mXboxDeferredVertices[other].context=c;c->references=1;
                p.XboxMaterializeVertex(other);
                const LoadedVertex uncached=rsp.loaded_vertices[other];
                *c=savedContext;p.mXboxNormalCacheEnabled=cacheEnabled;
                rsp.loaded_vertices[other]=value;
                value=uncached;
                p.mXboxDeferredVertices[other].source=repeated;
                p.mXboxDeferredVertices[other].context=c;c->references=1;
                p.XboxMaterializeVertex(other);
                if(memcmp(&value,&rsp.loaded_vertices[other],sizeof(value)) || c->references) {
                    const RGBA& actual=rsp.loaded_vertices[other].color;
                    printf("normal mismatch trial=%d pass=%u enabled=%u nearest=%u opposed=%u expected=%u,%u,%u,%u actual=%u,%u,%u,%u\n",
                           trial,pass,unsigned(p.mXboxNormalCacheEnabled),unsigned(c->nearest),unsigned(c->opposedLastPair),
                           value.color.r,value.color.g,value.color.b,value.color.a,actual.r,actual.g,actual.b,actual.a);
                    return 8;
                }
            }
            seed=originalSeed;
        }
    }
    if(verifiedCacheHits<1000) return 9;
    printf("PASS nonconsecutive normal cache: %u verified hits, eager bytes, collisions, context replacement and live toggle\n",verifiedCacheHits);
    // BranchZ and culling read eager z/w/clip without touching a pending slot.
    XboxDeferredContext* c=&p.mXboxDeferredContexts[0]; c->references=2;
    p.mXboxDeferredVertices[0].context=c;
    p.mXboxDeferredVertices[1].context=c;
    rsp.loaded_vertices[0].z=3; rsp.loaded_vertices[0].w=-4; rsp.loaded_vertices[0].clip_rej=0x11;
    bool branch=rsp.loaded_vertices[0].z<=4;
    bool culled=(rsp.loaded_vertices[0].clip_rej & 0x10)!=0;
    if(!branch || !culled || p.mXboxDeferredVertices[0].context!=c || c->references!=2) return 5;
    // A partial overwrite releases only the replaced slot. The surviving
    // snapshot remains live across reset-like mutations of the RSP.
    p.XboxDiscardVertex(0);
    if(c->references!=1 || p.mXboxDeferredVertices[0].context || p.mXboxDeferredVertices[1].context!=c) return 3;
    rsp.fog_mul=-123; rsp.fog_offset=99;
    p.XboxDiscardVertex(1);
    if(c->references || p.mXboxDeferredVertices[1].context) return 6;
    return 0;
}
'''


FULL_VERTEX_FIXTURE = r'''
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <limits>
#include <stdio.h>
#define MAX_LIGHTS 32
#define MAX_VERTICES 64
#define G_LIGHTING 0x1
#define G_FOG 0x2
#define G_TEXTURE_GEN 0x4
#define G_LIGHTING_POSITIONAL 0x8
#define G_TEXTURE_GEN_LINEAR 0x10
struct F3DVtx_t { short ob[3], flag, tc[2]; unsigned char cn[4]; };
struct F3DVtx_tn { short ob[3], flag, tc[2]; signed char n[3]; unsigned char a; };
union F3DVtx { F3DVtx_t v; F3DVtx_tn n; };
struct F3DLight_t { unsigned char col[3]; char pad1; unsigned char colc[3]; char pad2; signed char dir[3]; char pad3; };
struct F3DPointLight_t { unsigned char col[3], unk3, colc[3], unk7; short pos[3]; unsigned char unkE; };
union F3DLight { F3DLight_t l; F3DPointLight_t p; };
struct RGBA { uint8_t r,g,b,a; };
struct LoadedVertex { float x,y,z,w,u,v; RGBA color; uint8_t clip_rej; };
struct RSP {
    float modelview_matrix_stack[11][4][4];
    unsigned char modelview_matrix_stack_size;
    float MP_matrix[4][4];
    F3DLight_t lookat[2];
    F3DLight current_lights[MAX_LIGHTS+1];
    float current_lights_coeffs[MAX_LIGHTS][3];
    float current_lookat_coeffs[2][3];
    unsigned char current_num_lights;
    bool lights_changed;
    uint32_t geometry_mode;
    int16_t fog_mul, fog_offset;
    struct { uint16_t s,t; } texture_scaling_factor;
    LoadedVertex loaded_vertices[MAX_VERTICES+4];
};
namespace Ship { namespace Math { template<typename T> T clamp(T v,T lo,T hi) { return v<lo?lo:(v>hi?hi:v); } } }
namespace Shipyard { namespace Fast3D {
    const size_t ClipVertexStride=sizeof(LoadedVertex), ClipByteOffset=offsetof(LoadedVertex,clip_rej);
    bool VertexSourceDisjoint(const void* a,size_t an,const void* b,size_t bn) {
        uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
        return x<=y ? y-x>=an : x-y>=bn;
    }
    bool NearestRounding() { return false; }
    bool TransformPositions(const void*,size_t,const float [4][4],void*,bool=false,size_t=16) { return false; }
    struct TransformPhaseHook { void (*enterVertices)(void*); void* context; };
    bool TransformPositionsProfiled(const void* v,size_t n,const float m[4][4],void* out,
                                   bool aspect,size_t stride,const TransformPhaseHook* hook) {
        hook->enterVertices(hook->context);
        return TransformPositions(v,n,m,out,aspect,stride);
    }
    bool TransformPositionsUnaligned(const void* v,size_t n,const float m[4][4],void* out,
                                    bool aspect,size_t stride) {
        return TransformPositions(v,n,m,out,aspect,stride);
    }
    bool TransformPositionsUnalignedProfiled(const void* v,size_t n,const float m[4][4],void* out,
                                            bool aspect,size_t stride,const TransformPhaseHook* hook) {
        return TransformPositionsProfiled(v,n,m,out,aspect,stride,hook);
    }
    void ClipVertices(LoadedVertex*,size_t,bool) {}
    void ClipFiniteVertices(LoadedVertex* v,size_t n,bool nearPlane) { ClipVertices(v,n,nearPlane); }
    template<typename T> T Clamp(T v,T lo,T hi) { return v<lo?lo:(v>hi?hi:v); }
} }
/* PROJECTED TYPES */
namespace ModernFrameProfile {
    struct VtxHashSample { bool vmx, deferred; };
    enum VtxHashPhase { VtxHashDeferred, VtxHashTransform, VtxHashInsert };
    static void AdvanceVtxHash(VtxHashSample&,VtxHashPhase) {}
    static void BeginVtxTransform(VtxHashSample&,unsigned) {}
    static void EndVtxTransform(VtxHashSample&,bool) {}
    static void EnterVtxTransformLoop(void*) {}
}
static ModernFrameProfile::VtxHashSample* sModernVtxHashSample=NULL;
static struct { bool active; } gModernVertexReuseCensus={false};
static void ModernVertexReuseCapture(const XboxDeferredContext*,const F3DVtx*,size_t,
                                    const void*,bool,unsigned,unsigned) {}
class Interpreter {
public:
    RSP* mRsp;
    XboxDeferredVertex mXboxDeferredVertices[MAX_VERTICES];
    XboxDeferredContext mXboxDeferredContexts[MAX_VERTICES];
    XboxDeferredContext* mXboxCurrentDeferredContext;
    uint32_t mXboxCurrentDeferredFog;
    bool mXboxDeferredReplay, mFbActive;
    bool mXboxContextProbeCapture;
    unsigned mXboxContextSearchAttempts, mXboxContextSlotsScanned, mXboxContextMaxScan;
    struct { int width,height; } mCurDimensions;
    float AdjXForAspectRatio(float x) { return x; }
    void CalculateNormalDir(const F3DLight_t* light,float coeff[3]) {
        for(int c=0;c<3;++c) coeff[c]=(float)light->dir[c]/127.0f;
    }
    static void TransposedMatrixMul(float [3],const float [3],const float [4][4]) {}
    // This fixture supplies the combined matrix directly for both paths.
    void EnsureMatrixProduct() {}
    void XboxDiscardVertex(size_t);
    bool XboxTryDeferVertices(size_t,size_t,const F3DVtx*);
    void XboxMaterializeVertex(size_t);
    void XboxTakeContextSearchCounts(unsigned*, unsigned*, unsigned*);
    void GfxSpVertex(size_t,size_t,const F3DVtx*);
    void GfxSpVertexEager(size_t,size_t,const F3DVtx*);
    bool XboxTransformDeferredPositions(size_t,size_t,const F3DVtx*,bool);
};
/* PROJECTED METHODS */
static unsigned seed=0x67329eab;
static unsigned next() { seed=seed*1664525u+1013904223u; return seed; }
static void initialize(Interpreter& p,RSP& rsp) {
    memset(&p,0,sizeof(p)); memset(&rsp,0,sizeof(rsp)); p.mRsp=&rsp;
    p.mXboxNormalCacheEnabled=true;
    p.mCurDimensions.width=320; p.mCurDimensions.height=240;
    rsp.modelview_matrix_stack_size=1;
    for(int i=0;i<4;++i) rsp.MP_matrix[i][i]=1;
    rsp.current_num_lights=3;
    rsp.lights_changed=false;
    rsp.geometry_mode=G_LIGHTING|G_FOG;
    rsp.texture_scaling_factor.s=next()%65536;
    rsp.texture_scaling_factor.t=next()%65536;
    rsp.fog_mul=(short)(next()%2048); rsp.fog_offset=(short)(next()%512-256);
    for(int i=0;i<3;++i) for(int c=0;c<3;++c) {
        rsp.current_lights[i].l.col[c]=(uint8_t)next();
        rsp.current_lights[i].l.dir[c]=(signed char)next();
    }
    for(int i=0;i<2;++i) for(int c=0;c<3;++c)
        rsp.current_lights_coeffs[i][c]=(float)((int)(next()%255)-127)/127.0f;
}
int main() {
    Interpreter deferred,eager; RSP deferredRsp,eagerRsp;
    for(int trial=0;trial<4000;++trial) {
        Shipyard::Fast3D::nearest=(trial%3)!=0;
        Shipyard::Fast3D::transformAvailable=(trial%3)==2;
        initialize(deferred,deferredRsp);
        initialize(eager,eagerRsp);
        if(trial%11==0) deferred.mXboxNormalCacheSerial=0xffffffffu;
        if(trial&4) {
            deferred.mCurDimensions.width=eager.mCurDimensions.width=1280;
            deferred.mCurDimensions.height=eager.mCurDimensions.height=720;
        }
        deferred.mFbActive=eager.mFbActive=(trial%7)==0;
        // Both command streams must start with exactly the same state.
        eagerRsp=deferredRsp;
        deferredRsp.lights_changed=eagerRsp.lights_changed=(trial&1)!=0;
        F3DVtx input[4]; memset(input,0,sizeof(input));
        for(int i=0;i<4;++i) {
            input[i].v.ob[0]=(short)((int)(next()%20)-10);
            input[i].v.ob[1]=(short)((int)(next()%20)-10);
            input[i].v.ob[2]=(short)((int)(next()%20)-10);
            input[i].v.tc[0]=(short)next(); input[i].v.tc[1]=(short)next();
            for(int c=0;c<3;++c) input[i].n.n[c]=(signed char)next();
        }
        const size_t dest=trial%60;
        for(int c=0;c<MAX_VERTICES;++c) eager.mXboxDeferredContexts[c].references=1;
        eager.GfxSpVertex(4,dest,input);
        deferred.GfxSpVertex(4,dest,input);
        if(deferredRsp.geometry_mode!=eagerRsp.geometry_mode) return 1;
        for(int i=0;i<4;++i) {
            const LoadedVertex& a=eagerRsp.loaded_vertices[dest+i];
            const LoadedVertex& b=deferredRsp.loaded_vertices[dest+i];
            if(a.x!=b.x || a.y!=b.y || a.z!=b.z || a.w!=b.w || a.clip_rej!=b.clip_rej) {
                printf("position/clip trial %d vertex %d\n",trial,i); return 2;
            }
            // The deferred VMX replay must leave attributes untouched until
            // the pending snapshot is materialized below.
            if(Shipyard::Fast3D::nearest && Shipyard::Fast3D::transformAvailable &&
               (b.u!=0 || b.v!=0 || b.color.r!=0 || b.color.g!=0 ||
                b.color.b!=0 || b.color.a!=0)) return 11;
            // BranchZ and cull may read these eagerly without materializing.
            bool branch=b.z<=4, cull=(b.clip_rej&0x20)!=0;
            if(branch!=(a.z<=4) || cull!=((a.clip_rej&0x20)!=0) ||
               !deferred.mXboxDeferredVertices[dest+i].context) return 3;
        }
        memset(input,0xa5,sizeof(input));
        deferredRsp.geometry_mode=0;
        deferredRsp.fog_mul=-101; deferredRsp.fog_offset=17;
        deferredRsp.texture_scaling_factor.s=3;
        deferredRsp.MP_matrix[0][0]=999;
        for(int i=0;i<3;++i) for(int c=0;c<3;++c)
            deferredRsp.current_lights[i].l.col[c]=0;
        for(int i=0;i<4;++i) {
            deferred.XboxMaterializeVertex(dest+i);
            if(memcmp(&eagerRsp.loaded_vertices[dest+i],&deferredRsp.loaded_vertices[dest+i],sizeof(LoadedVertex))) {
                const LoadedVertex& a=eagerRsp.loaded_vertices[dest+i];
                const LoadedVertex& b=deferredRsp.loaded_vertices[dest+i];
                printf("attributes trial %d vertex %d uv %.3f/%.3f %.3f/%.3f rgba %u,%u,%u,%u/%u,%u,%u,%u pos %.3f/%.3f clip %u/%u\n",
                    trial,i,a.u,a.v,b.u,b.v,a.color.r,a.color.g,a.color.b,a.color.a,
                    b.color.r,b.color.g,b.color.b,b.color.a,a.x,b.x,a.clip_rej,b.clip_rej);
                return 4;
            }
        }
    }
    initialize(deferred,deferredRsp); initialize(eager,eagerRsp);
    eagerRsp=deferredRsp;
    F3DVtx source; memset(&source,0,sizeof(source));
    source.v.ob[0]=1; source.v.ob[1]=2; source.v.ob[2]=3;
    source.v.tc[0]=1234; source.v.tc[1]=-5678;
    source.n.n[0]=100; source.n.n[1]=-50; source.n.n[2]=20;
    for(int c=0;c<MAX_VERTICES;++c) eager.mXboxDeferredContexts[c].references=1;
    eager.GfxSpVertex(1,0,&source);
    deferred.GfxSpVertex(1,0,&source);
    if(!deferred.mXboxDeferredVertices[0].context) return 5;
    // A later command reads packed bytes inside an earlier loaded vertex.
    // The pending slot must materialize before this eager fallback consumes it.
    eager.GfxSpVertex(1,1,(const F3DVtx*)&eagerRsp.loaded_vertices[0]);
    deferred.GfxSpVertex(1,1,(const F3DVtx*)&deferredRsp.loaded_vertices[0]);
    if(deferred.mXboxDeferredVertices[0].context ||
       memcmp(&eagerRsp.loaded_vertices[0],&deferredRsp.loaded_vertices[0],sizeof(LoadedVertex)) ||
       memcmp(&eagerRsp.loaded_vertices[1],&deferredRsp.loaded_vertices[1],sizeof(LoadedVertex))) return 6;
    // The final projection retains one context across loads and partial overwrites.
    initialize(deferred,deferredRsp); initialize(eager,eagerRsp); eagerRsp=deferredRsp;
    Shipyard::Fast3D::nearest=Shipyard::Fast3D::transformAvailable=true;
    deferred.GfxSpVertex(1,0,&source);
    XboxDeferredContext* retained=deferred.mXboxDeferredVertices[0].context;
    if(!retained || retained->references!=1) return 12;
    deferred.GfxSpVertex(1,1,&source);
    if(deferred.mXboxDeferredVertices[1].context!=retained || retained->references!=2) return 13;
    deferred.GfxSpVertex(1,0,&source);
    if(deferred.mXboxDeferredVertices[0].context!=retained || retained->references!=2) return 14;
    eager.GfxSpVertexEager(1,0,&source); eager.GfxSpVertexEager(1,1,&source);
    deferred.XboxMaterializeVertex(0); deferred.XboxMaterializeVertex(1);
    if(retained->references || memcmp(eagerRsp.loaded_vertices,deferredRsp.loaded_vertices,2*sizeof(LoadedVertex))) return 15;
    // Count one successful search at slot 7, a fully occupied search, and
    // verify the accessor drains all counters. No per-iteration counter work.
    initialize(deferred,deferredRsp);
    deferred.mXboxContextProbeCapture=true;
    for(int i=0;i<6;++i) deferred.mXboxDeferredContexts[i].references=1;
    deferred.GfxSpVertex(1,0,&source);
    unsigned attempts=0,slots=0,maximum=0;
    deferred.XboxTakeContextSearchCounts(&attempts,&slots,&maximum);
    if(attempts!=1 || slots!=7 || maximum!=7) return 7;
    deferred.XboxTakeContextSearchCounts(&attempts,&slots,&maximum);
    if(attempts || slots || maximum) return 8;
    initialize(deferred,deferredRsp);
    deferred.mXboxContextProbeCapture=true;
    for(int i=0;i<MAX_VERTICES;++i) deferred.mXboxDeferredContexts[i].references=1;
    deferred.GfxSpVertex(1,0,&source);
    deferred.XboxTakeContextSearchCounts(&attempts,&slots,&maximum);
    if(attempts!=1 || slots!=MAX_VERTICES || maximum!=MAX_VERTICES) return 9;
    initialize(deferred,deferredRsp);
    deferred.GfxSpVertex(1,0,&source);
    deferred.XboxTakeContextSearchCounts(&attempts,&slots,&maximum);
    if(attempts || slots || maximum) return 10;
    return 0;
}
'''


if __name__ == '__main__':
    unittest.main()
