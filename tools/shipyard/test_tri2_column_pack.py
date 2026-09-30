"""Bitwise TRI2 packing differential for the Modern columnar projection."""

import os
import unittest
import sys
import json
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tri2_column_pack_projection import transform


ROOT = Path(__file__).resolve().parents[2]


class ColumnPackProjection(unittest.TestCase):
    def test_projects_exact_selected_emitter(self):
        source = (ROOT / "scratch/fast3d-xdk/generated/src/fast/interpreter.cpp").read_text()
        projected = transform(source)
        self.assertIn("// MODERN COLUMN PACK BEGIN", projected)

    def test_actual_pack_bytes_match_row_reference(self):
        vcvars = Path("C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/vcvarsall.bat")
        compiler = Path("C:/Program Files (x86)/Microsoft Visual Studio 10.0/VC/bin/cl.exe")
        if not vcvars.is_file() or not compiler.is_file():
            self.skipTest("VS2010 host compiler unavailable")
        source = (ROOT / "scratch/fast3d-xdk/generated/src/fast/interpreter.cpp").read_text()
        start = source.index("void Interpreter::XboxEmitTriangle(")
        end = source.index("\n}", start)
        emitter = source[start:end]
        prelude = emitter[
            emitter.index("    const XboxTrianglePipelineResult& p=") : emitter.index("    // MODERN COLUMN PACK BEGIN")
        ]
        projected = emitter[
            emitter.index("    // MODERN COLUMN PACK BEGIN") : emitter.index("    // MODERN COLUMN PACK END")
        ]
        row = projected[projected.index("    // MODERN COLUMN PACK FALLBACK BEGIN") : projected.rindex("\n    }")]
        row = row.replace("    // MODERN COLUMN PACK FALLBACK BEGIN", "", 1)
        body = (
            prelude
            + "\n    if (column) {\n"
            + projected
            + "\n    } else {\n"
            + row
            + "\n    }\n    mBufVboLen = size_t(shipyardVertexOutput - mBufVbo);\n"
        )
        fixture = HOST_FIXTURE.replace("/* PACK BODY */", body)
        lock = json.loads((ROOT / "platform-base.lock.json").read_text())
        selected = Path(os.environ.get("XBOX360_PLATFORM_BASE", ROOT / lock["base"])) / "sources"
        with tempfile.TemporaryDirectory(prefix="modern-tri2-column-") as temp:
            cpp = Path(temp) / "fixture.cpp"
            exe = Path(temp) / "fixture.exe"
            batch = Path(temp) / "build.bat"
            cpp.write_text(fixture)
            batch.write_text(
                f'@call "{vcvars}" x86 >nul\n'
                f'@"{compiler}" /nologo /O2 /EHsc /fp:precise '
                f'/I"{selected}" "{cpp}" /Fe"{exe}"\n'
            )
            built = subprocess.run(["cmd.exe", "/c", str(batch)], capture_output=True, text=True)
            self.assertEqual(0, built.returncode, (built.stdout + built.stderr)[-5000:])
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-5000:])
            self.assertIn("columnar_differential=passed", result.stdout)
            print(result.stdout.strip())


HOST_FIXTURE = r"""
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include "fast3d/unit_color.h"
#include "fast3d/coordinate.h"
#define G_MDSFT_TEXTFILT 12
#define G_TF_POINT 0
#define G_TL_LOD 0x10000u
enum { G_CCMUX_PRIMITIVE=3, G_CCMUX_SHADE=4, G_CCMUX_ENVIRONMENT=5,
       G_CCMUX_PRIMITIVE_ALPHA=10, G_CCMUX_ENV_ALPHA=12,
       G_CCMUX_PRIM_LOD_FRAC=14, G_CCMUX_LOD_FRACTION=13,
       G_ACMUX_PRIM_LOD_FRAC=6 };
struct RGBA { uint8_t r,g,b,a; };
struct LoadedVertex { float x,y,z,w,u,v; RGBA color; };
struct Clip { bool z_is_from_0_to_1, invertY; };
typedef Clip GfxClipParameters;
struct Tile { int shifts,shiftt; float uls,ult; };
struct RDP {
    uint32_t other_mode_h,other_mode_l; unsigned first_tile_index;
    Tile texture_tile[2]; RGBA fog_color,grayscale_color,prim_color,env_color;
    uint8_t prim_lod_fraction;
};
struct ColorCombiner { uint8_t shader_input_mapping[2][7]; bool usedTextures[2]; };
struct XboxTrianglePipelineResult {
    ColorCombiner* comb; bool alpha,fog,grayscale,usedTextures[2];
    uint32_t tm,width[2],height[2],boundWidth[2],boundHeight[2];
    uint8_t numInputs; Clip clip;
};
struct PairCopy {
    bool CopyVertex(uint8_t,float*&,const float*) { return false; }
    void RestoreMaterials(const float* [2][7],const float*,unsigned,bool) {}
};
struct Runner {
    RDP* mRdp; XboxTrianglePipelineResult mXboxPipelineResult;
    PairCopy mXboxPairPacked; float mBufVbo[512]; size_t mBufVboLen;
    Shipyard::Fast3D::CoordinateAxis mXboxAxisS[2], mXboxAxisT[2];
    float mXboxClampS[2], mXboxClampT[2];
    void Pack(bool column,const LoadedVertex input[3],bool is_rect) {
        // Mirrors the reconciliation-time derivation for combiner-used slots.
        const XboxTrianglePipelineResult& q=mXboxPipelineResult;
        for(unsigned i=0;i<2;++i) {
            if(!q.comb->usedTextures[i]) continue;
            const Tile& tile=mRdp->texture_tile[mRdp->first_tile_index+i];
            mXboxAxisS[i].Prepare(tile.shifts,tile.uls,q.width[i]);
            mXboxAxisT[i].Prepare(tile.shiftt,tile.ult,q.height[i]);
            if(q.tm & (1u<<2*i)) mXboxClampS[i]=(q.boundWidth[i]-0.5f)/q.width[i];
            if(q.tm & (1u<<(2*i+1))) mXboxClampT[i]=(q.boundHeight[i]-0.5f)/q.height[i];
        }
        LoadedVertex* v1 = const_cast<LoadedVertex*>(&input[0]);
        LoadedVertex* v2 = const_cast<LoadedVertex*>(&input[1]);
        LoadedVertex* v3 = const_cast<LoadedVertex*>(&input[2]);
        LoadedVertex* v_arr[3] = {v1,v2,v3};
        bool xboxPairPackFirst=false,xboxPairPackReuse=false;
        size_t xboxPairStarts[3]; uint8_t xboxPairIndices[3]={0,1,2};
/* PACK BODY */
    }
};
static uint32_t seed=0x47e12c9du;
static uint32_t next() { seed=seed*1664525u+1013904223u; return seed; }
static float small() { return float(int(next()%4001)-2000) * 0.125f; }
static RGBA color() { RGBA c={uint8_t(next()),uint8_t(next()),uint8_t(next()),uint8_t(next())}; return c; }
int main() {
    for(unsigned n=0;n<30000;++n) {
        RDP r={}; ColorCombiner comb={}; LoadedVertex verts[3]={};
        XboxTrianglePipelineResult p={};
        p.comb=&comb; p.alpha=!!(n&1); p.fog=!!(n&2);
        p.grayscale=!!(n&4); p.usedTextures[0]=!!(n&8);
        // A clamp bit implies combiner use, as in reconciliation.
        comb.usedTextures[0]=p.usedTextures[0] || (n&3)!=0 || !!(n&1024);
        comb.usedTextures[1]=!!(n&2048) || (n&12)!=0;
        p.usedTextures[1]=!!(n&16); p.numInputs=uint8_t((n%3)+1);
        p.clip.invertY=!!(n&32); p.clip.z_is_from_0_to_1=!!(n&64);
        p.tm=n&15; r.other_mode_h=(n&128)?(1u<<G_MDSFT_TEXTFILT):0;
        r.other_mode_l=(n&256)?G_TL_LOD:0;
        r.fog_color=color(); r.grayscale_color=color();
        r.prim_color=color(); r.env_color=color();
        r.prim_lod_fraction=uint8_t(next());
        for(int t=0;t<2;++t) {
            p.width[t]=uint32_t((next()%255)+1); p.height[t]=uint32_t((next()%255)+1);
            p.boundWidth[t]=uint32_t((next()%255)+1); p.boundHeight[t]=uint32_t((next()%255)+1);
            r.texture_tile[t].shifts=int(next()%16); r.texture_tile[t].shiftt=int(next()%16);
            r.texture_tile[t].uls=small(); r.texture_tile[t].ult=small();
        }
        for(int i=0;i<3;++i) {
            verts[i].x=small(); verts[i].y=small(); verts[i].z=small();
            verts[i].w=small(); verts[i].u=small(); verts[i].v=small();
            verts[i].color=color();
        }
        for(int k=0;k<2;++k) for(int j=0;j<3;++j) {
            const uint8_t rgb[]={G_CCMUX_PRIMITIVE,G_CCMUX_SHADE,G_CCMUX_ENVIRONMENT,
                G_CCMUX_PRIMITIVE_ALPHA,G_CCMUX_ENV_ALPHA,G_CCMUX_PRIM_LOD_FRAC,G_CCMUX_LOD_FRACTION};
            const uint8_t alpha[]={0,1,2,G_CCMUX_PRIMITIVE,G_CCMUX_SHADE,
                G_CCMUX_ENVIRONMENT,G_ACMUX_PRIM_LOD_FRAC,7};
            comb.shader_input_mapping[k][j]= k ? alpha[next()%8] : rgb[next()%7];
        }
        Runner a={},b={}; a.mRdp=b.mRdp=&r;
        a.mXboxPipelineResult=b.mXboxPipelineResult=p;
        memset(a.mBufVbo,0xa5,sizeof(a.mBufVbo));
        memset(b.mBufVbo,0xa5,sizeof(b.mBufVbo));
        a.Pack(false,verts,!!(n&512)); b.Pack(true,verts,!!(n&512));
        if(a.mBufVboLen!=b.mBufVboLen ||
           memcmp(a.mBufVbo,b.mBufVbo,a.mBufVboLen*sizeof(float))) {
            printf("mismatch case=%u len=%u/%u\n",n,
                unsigned(a.mBufVboLen),unsigned(b.mBufVboLen));
            printf("mapping=%u/%u alpha=%u fog=%u gray=%u\n",
                unsigned(comb.shader_input_mapping[0][0]),unsigned(comb.shader_input_mapping[1][0]),
                unsigned(p.alpha),unsigned(p.fog),unsigned(p.grayscale));
            for(size_t i=0;i<a.mBufVboLen && i<b.mBufVboLen;++i)
                if(memcmp(&a.mBufVbo[i],&b.mBufVbo[i],sizeof(float))) {
                    uint32_t x,y; memcpy(&x,&a.mBufVbo[i],4); memcpy(&y,&b.mBufVbo[i],4);
                    printf("first_diff=%u bits=%08x/%08x\n",unsigned(i),x,y); break;
                }
            return 1;
        }
    }
    RDP r={}; ColorCombiner comb={}; LoadedVertex verts[3]={};
    XboxTrianglePipelineResult p={}; p.comb=&comb;
    p.alpha=true; p.fog=true; p.grayscale=false;
    p.usedTextures[0]=true; p.usedTextures[1]=false;
    p.width[0]=64; p.height[0]=64; p.boundWidth[0]=64; p.boundHeight[0]=64;
    p.numInputs=2; p.tm=3;
    comb.shader_input_mapping[0][0]=G_CCMUX_SHADE;
    comb.shader_input_mapping[1][0]=G_CCMUX_SHADE;
    comb.shader_input_mapping[0][1]=G_CCMUX_PRIMITIVE;
    comb.shader_input_mapping[1][1]=G_CCMUX_PRIMITIVE;
    for(int i=0;i<3;++i) {
        verts[i].x=float(i+1); verts[i].y=float(i+2);
        verts[i].z=float(i+3); verts[i].w=float(i+4);
        verts[i].u=float(i*17); verts[i].v=float(i*13);
        verts[i].color=color();
    }
    volatile float sink=0.0f;
    const int loops=500000;
    printf("columnar_differential=passed cases=30000\n");
    for(int mode=0;mode<3;++mode) {
        p.usedTextures[1]=(mode==1); p.grayscale=(mode==1);
        p.numInputs=uint8_t(mode==1?3:(mode==2?1:2));
        p.usedTextures[0]=(mode!=2); p.fog=(mode!=2); p.alpha=(mode!=2);
        p.tm=(mode==1?15:3);
        p.width[1]=32; p.height[1]=32; p.boundWidth[1]=32; p.boundHeight[1]=32;
        comb.shader_input_mapping[0][2]=G_CCMUX_ENVIRONMENT;
        comb.shader_input_mapping[1][2]=G_CCMUX_ENVIRONMENT;
        Runner bench={}; bench.mRdp=&r; bench.mXboxPipelineResult=p;
        clock_t start=clock();
        for(int i=0;i<loops;++i) { bench.mBufVboLen=0; bench.Pack(false,verts,false); sink+=bench.mBufVbo[0]; }
        const double row_ms=1000.0*double(clock()-start)/CLOCKS_PER_SEC;
        start=clock();
        for(int i=0;i<loops;++i) { bench.mBufVboLen=0; bench.Pack(true,verts,false); sink+=bench.mBufVbo[0]; }
        const double column_ms=1000.0*double(clock()-start)/CLOCKS_PER_SEC;
        printf("pack_benchmark mode=%d loops=%d row_ms=%.2f column_ms=%.2f speedup=%.2f sink=%.0f\n",
            mode,loops,row_ms,column_ms,row_ms/column_ms,sink);
    }
    return 0;
}
"""


if __name__ == "__main__":
    unittest.main()
