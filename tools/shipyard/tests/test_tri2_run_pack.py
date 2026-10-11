"""Compare selected row/column packing with sparse and dense TRI2 run reuse."""

from pathlib import Path
import subprocess
import sys
import unittest

from test_tri2_packed_reuse import host_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
from test_tri2_column_pack import HOST_FIXTURE


def fixture():
    source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
    emitter = source.split('void Interpreter::XboxEmitTriangle(', 1)[1].split('\n}', 1)[0]
    prelude = emitter[emitter.index('    const XboxTrianglePipelineResult& p='):
                      emitter.index('    // MODERN COLUMN PACK BEGIN')]
    column = emitter[emitter.index('    // MODERN COLUMN PACK BEGIN'):
                     emitter.index('    // MODERN COLUMN PACK END')]
    row = column[column.index('    // MODERN COLUMN PACK FALLBACK BEGIN'):column.rindex('\n    }')]
    body = prelude + '\nif(column) {\n' + column + '\n} else {\n' + row + '\n}\n'
    body += '''mBufVboLen=size_t(shipyardVertexOutput-mBufVbo);
        if(xboxPairPackFirst) {
            mXboxPairPacked.Capture(xboxPairIndices,xboxPairStarts,mBufVboLen,wb);
            mXboxPairPacked.CaptureMaterials(shipyardMaterialInputs,mBufVbo,numInputs,use_alpha);
        }
'''
    text = HOST_FIXTURE
    start, end = text.index('struct PairCopy {'), text.index('struct Runner {')
    text = text[:start] + '''#include <float.h>
#include "fast3d/tri2_packed_reuse.h"
#include "fast3d/projection_cache.h"
#include "fast3d/unit_color_rounding.h"
''' + text[end:]
    text = text.replace('PairCopy mXboxPairPacked;', 'ModernTri2PackedReuse mXboxPairPacked;')
    text = text.replace('float mBufVbo[512]', 'float mBufVbo[8192]')
    text = text.replace('void Pack(bool column,const LoadedVertex input[3],bool is_rect) {',
                        '''__declspec(noinline) void Pack(unsigned mode,const LoadedVertex input[3],
                        bool is_rect,const uint8_t ids[3]) {
        const bool column=mode!=0;''')
    text = text.replace('''bool xboxPairPackFirst=false,xboxPairPackReuse=false;
        size_t xboxPairStarts[3]; uint8_t xboxPairIndices[3]={0,1,2};''',
                        '''uint32_t wb;memcpy(&wb,&input[0].w,4);
        const bool xboxPairPackFirst=mode>=2;
        const bool eligible=xboxPairPackFirst&&mXboxPairPacked.CanReuse(
            mBufVboLen,true,(mRdp->other_mode_l&G_TL_LOD)!=0,wb);
        if(!eligible)mXboxPairPacked.Reset();
        size_t xboxPairStarts[3]; uint8_t xboxPairIndices[3]={ids[0],ids[1],ids[2]};
        const bool xboxPairPackReuse=eligible&&(mode==2||mXboxPairPacked.ContainsAny(xboxPairIndices));''')
    text = text.replace('/* PACK BODY */', body)
    return text[:text.index('int main() {')] + MAIN


MAIN = r'''
static void Setup(RDP& r,ColorCombiner& comb,XboxTrianglePipelineResult& p,unsigned flags) {
    memset(&r,0,sizeof(r));memset(&comb,0,sizeof(comb));memset(&p,0,sizeof(p));
    p.comb=&comb;p.alpha=!!(flags&1);p.fog=!!(flags&2);p.grayscale=!!(flags&4);
    p.usedTextures[0]=comb.usedTextures[0]=!!(flags&8);
    p.usedTextures[1]=comb.usedTextures[1]=!!(flags&16);
    p.numInputs=uint8_t((flags>>5)&7);p.tm=(flags>>8)&15;
    p.clip.invertY=!!(flags&4096);p.clip.z_is_from_0_to_1=!!(flags&8192);
    r.other_mode_l=(flags&16384)?G_TL_LOD:0;
    r.fog_color=color();r.grayscale_color=color();r.prim_color=color();r.env_color=color();
    r.prim_lod_fraction=uint8_t(next());
    for(unsigned t=0;t<2;++t) {
        p.width[t]=32;p.height[t]=64;p.boundWidth[t]=16;p.boundHeight[t]=32;
        r.texture_tile[t].shifts=3;r.texture_tile[t].shiftt=1;
        r.texture_tile[t].uls=small();r.texture_tile[t].ult=small();
    }
    const uint8_t rgb[]={3,4,5,10,12,14,13},alpha[]={0,1,2,3,4,5,6,7};
    for(unsigned j=0;j<7;++j) {
        comb.shader_input_mapping[0][j]=rgb[next()%7];
        comb.shader_input_mapping[1][j]=alpha[next()%8];
    }
}
static void Pool(LoadedVertex pool[64]) {
    for(unsigned i=0;i<64;++i) {
        pool[i].x=small();pool[i].y=small();pool[i].z=small();pool[i].w=small();
        pool[i].u=small();pool[i].v=small();pool[i].color=color();
    }
}
static void Triangle(unsigned pattern,unsigned tri,uint8_t ids[3]) {
    for(unsigned i=0;i<3;++i) ids[i]=uint8_t(pattern==0?tri*3+i:
        pattern==1?(i==0?0:tri+i):i);
}
int main() {
    unsigned checks=0;
    const unsigned rounds[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    for(unsigned rn=0;rn<4;++rn) {
        _controlfp(rounds[rn],_MCW_RC);
        for(unsigned n=0;n<8192;++n) {
            RDP r;ColorCombiner comb;XboxTrianglePipelineResult p;Setup(r,comb,p,n*7);
            LoadedVertex pool[64];Pool(pool);
            Runner a={},b={};a.mRdp=b.mRdp=&r;a.mXboxPipelineResult=b.mXboxPipelineResult=p;
            for(unsigned tri=0;tri<12;++tri) {
                uint8_t ids[3];Triangle(n%3,tri,ids);
                LoadedVertex input[3];for(unsigned i=0;i<3;++i)input[i]=pool[ids[i]];
                if(tri==6&&(n&1)){a.mBufVboLen=b.mBufVboLen=0;b.mXboxPairPacked.Reset();}
                a.Pack(0,input,false,ids);b.Pack(3,input,false,ids);
                if(a.mBufVboLen!=b.mBufVboLen||memcmp(a.mBufVbo,b.mBufVbo,a.mBufVboLen*4)) {
                    printf("FAIL RN=%u flags=%u triangle=%u\n",rn,n*7,tri);return 1;
                }
                ++checks;
            }
        }
    }
    _controlfp(_RC_NEAR,_MCW_RC);
    printf("PASS run packing column selection checks=%u four_RN inputs=0..7\n",checks);
    volatile float sink=0;
    for(unsigned material=0;material<2;++material) {
        RDP r;ColorCombiner comb;XboxTrianglePipelineResult p;
        Setup(r,comb,p,material?1+2+8+(2<<5)+(3<<8):8+(1<<5));
        comb.shader_input_mapping[0][0]=G_CCMUX_SHADE;
        comb.shader_input_mapping[1][0]=G_CCMUX_SHADE;
        LoadedVertex pool[64];Pool(pool);
        for(unsigned pattern=0;pattern<3;++pattern) {
            for(unsigned mode=0;mode<4;++mode) {
                Runner a={};a.mRdp=&r;a.mXboxPipelineResult=p;
                const unsigned runs=100000;clock_t begin=clock();
                for(unsigned run=0;run<runs;++run) {
                    a.mBufVboLen=0;a.mXboxPairPacked.Reset();
                    for(unsigned tri=0;tri<12;++tri) {
                        uint8_t ids[3];Triangle(pattern,tri,ids);
                        LoadedVertex input[3];for(unsigned i=0;i<3;++i)input[i]=pool[ids[i]];
                        a.Pack(mode,input,false,ids);
                    }
                    sink+=a.mBufVbo[a.mBufVboLen-1];
                }
                printf("host_pack material=%u pattern=%u mode=%u triangles=%u ms=%.3f sink=%.3f\n",
                    material,pattern,mode,runs*12,1000.0*double(clock()-begin)/CLOCKS_PER_SEC,sink);
            }
        }
    }
    return 0;
}
'''


class Tri2RunPack(unittest.TestCase):
    def test_selected_packer_run_policy(self):
        out = ROOT / 'scratch/fast3d-xdk/tri2-run-pack'
        out.mkdir(parents=True, exist_ok=True)
        source = out / 'contract.cpp'
        source.write_text(fixture())
        compiler, environment = host_environment()
        exe = out / 'contract.exe'
        built = subprocess.run([str(compiler), '/nologo', '/O2', '/EHsc', '/fp:strict', '/MD',
                                '/I' + str(ROOT / 'platform/shipyard'),
                                '/I' + str(resolve(ROOT) / 'sources'), str(source), '/Fe:' + str(exe)],
                               cwd=out, env=environment, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (out / 'result.txt').write_text(result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
