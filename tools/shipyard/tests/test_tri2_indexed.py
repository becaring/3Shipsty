"""Flatten actual indexed packing and compare every byte with the flat packer."""

from pathlib import Path
import subprocess
import sys
import unittest

from test_tri2_packed_reuse import host_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
from test_tri2_column_pack import HOST_FIXTURE
from tri2_indexed_projection import transform, header


def fixture():
    source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
    projected = transform(source)
    layout_capture = projected.split('// MODERN PACK LAYOUT CAPTURE BEGIN', 1)[1].split(
        '// MODERN PACK LAYOUT CAPTURE END', 1)[0]
    emitter = projected.split('void Interpreter::XboxEmitTriangle(', 1)[1].split('\n}', 1)[0]
    old = emitter.split('#else\n    // MODERN INDEXED EMITTER BEGIN', 1)[0]
    prelude = old[old.index('    const XboxTrianglePipelineResult& p='):
                  old.index('    // MODERN COLUMN PACK BEGIN')]
    column = old[old.index('    // MODERN COLUMN PACK BEGIN'):
                 old.index('    // MODERN COLUMN PACK END')]
    row = column[column.index('    // MODERN COLUMN PACK FALLBACK BEGIN'):column.rindex('\n    }')]
    reference = prelude + row + '\n mBufVboLen = size_t(shipyardVertexOutput - mBufVbo);\n'
    indexed = emitter.split('// MODERN INDEXED EMITTER BEGIN', 1)[1]
    indexed = indexed[indexed.index('    const XboxTrianglePipelineResult& p='):
                      indexed.index('    // MODERN INDEXED CERTIFICATE END')]
    base = HOST_FIXTURE[:HOST_FIXTURE.index('int main() {')]
    base = base.replace('#include <time.h>', '#include <time.h>\n#include <float.h>\n#include <vector>\n'
                        '#include "fast3d/tri2_packed_reuse.h"\n'
                        '#include "fast3d/coordinate_three.h"')
    base = base.replace('struct Runner {', CONTRACT_GLOBALS + '\nstruct Runner {', 1)
    runner_start = base.index('struct Runner {')
    runner_end = base.index('\n};', runner_start) + len('\n};')
    flat_runner = base[runner_start:runner_end].replace('struct Runner {', 'struct FlatRunner {')
    flat_runner = flat_runner.replace('/* PACK BODY */', reference)
    runner = base[runner_start:runner_end]
    runner = runner.replace('PairCopy mXboxPairPacked; float mBufVbo[512]; size_t mBufVboLen;', '''
    ModernTri2PackedReuse mXboxPairPacked;
    enum { MAX_TRI_BUFFER = 256 };
    float mBufVbo[MAX_TRI_BUFFER * 32 * 3]; size_t mBufVboLen;
    uint16_t mXboxTriangleIndices[MAX_TRI_BUFFER * 3];
    size_t mXboxIndexedRows, mXboxIndexedStride, mBufVboNumTris;
    size_t mXboxPackLayout[6];
    std::vector<float> flattened, expected;
    size_t emittedRows, emittedCorners, flushes;
    Runner() : mBufVboLen(0), mXboxIndexedRows(0), mXboxIndexedStride(0),
               mBufVboNumTris(0), emittedRows(0), emittedCorners(0), flushes(0) {
        memset(mXboxAxisS,0,sizeof(mXboxAxisS));memset(mXboxAxisT,0,sizeof(mXboxAxisT));
        memset(mXboxClampS,0,sizeof(mXboxClampS));memset(mXboxClampT,0,sizeof(mXboxClampT));
    }
    void Flush() {
        if (!mBufVboNumTris) return;
        for (size_t i=0;i<3*mBufVboNumTris;++i) {
            const size_t row=mXboxTriangleIndices[i];
            if(row>=mXboxIndexedRows) { puts("FAIL index bounds"); IndexedContractFail(3); }
            for(size_t j=0;j<mXboxIndexedStride;++j) {
                const float* value=mBufVbo+row*mXboxIndexedStride+j;
                if(flattened.size()>=expected.size() ||
                   memcmp(value,&expected[flattened.size()],4)) {
                    puts("FAIL an earlier indexed row changed before submission");IndexedContractFail(4);
                }
                uint32_t bits;memcpy(&bits,value,4);
                gModernIndexedContractSignature=(gModernIndexedContractSignature^bits)*16777619U;
                flattened.push_back(*value);
            }
        }
        emittedRows+=mXboxIndexedRows; emittedCorners+=3*mBufVboNumTris; ++flushes;
        mBufVboLen=mBufVboNumTris=mXboxIndexedRows=mXboxIndexedStride=0;
        mXboxPairPacked.Reset();
    }
''')
    runner = runner.replace('    void Flush() {',
                            '    void PrepareLayout() {\n'
                            '        const XboxTrianglePipelineResult& p=mXboxPipelineResult;\n' +
                            layout_capture + '\n    }\n    void Flush() {', 1)
    runner = runner.replace('void Pack(bool column,const LoadedVertex input[3],bool is_rect) {',
                            'void Pack(bool certified,const LoadedVertex input[3],bool is_rect,const uint8_t ids[3]) {')
    runner = runner.replace('''        bool xboxPairPackFirst=false,xboxPairPackReuse=false;
        size_t xboxPairStarts[3]; uint8_t xboxPairIndices[3]={0,1,2};''', '''
        const bool xboxPairPackFirst=certified;
        const bool xboxPairPackSecond=certified&&mXboxPairPacked.valid;
        const bool xboxPipelineHit=true;
        uint32_t xboxPairFirstWBits; memcpy(&xboxPairFirstWBits,&v1->w,4);
        const uint8_t xboxPairIndices[3]={ids[0],ids[1],ids[2]};''')
    runner = runner.replace('/* PACK BODY */', indexed + '\n if(++mBufVboNumTris==MAX_TRI_BUFFER) Flush();\n')
    base = base[:runner_start] + flat_runner + '\n' + runner + base[runner_end:]
    return base + MAIN.replace('flat.mXboxPipelineResult=indexed.mXboxPipelineResult=p;',
                              'flat.mXboxPipelineResult=indexed.mXboxPipelineResult=p;'
                              'indexed.PrepareLayout();')


CONTRACT_GLOBALS = r'''
extern "C" {
volatile uint32_t gModernIndexedContractStatus=0;
volatile uint32_t gModernIndexedContractChecks=0;
volatile uint32_t gModernIndexedContractRows=0;
volatile uint32_t gModernIndexedContractCorners=0;
volatile uint32_t gModernIndexedContractSignature=2166136261U;
volatile uint32_t gModernIndexedContractFailureCase=0;
volatile uint32_t gModernIndexedContractFailureTriangle=0;
volatile uint32_t gModernIndexedContractFailureCorner=0;
volatile uint32_t gModernIndexedContractFailureLane=0;
}
static void IndexedContractFail(unsigned code) { throw int(code); }
'''


MAIN = r'''
static void Setup(RDP& r,ColorCombiner& comb,XboxTrianglePipelineResult& p,unsigned flags) {
    memset(&r,0,sizeof(r));memset(&comb,0,sizeof(comb));memset(&p,0,sizeof(p));
    p.comb=&comb;p.alpha=!!(flags&1);p.fog=!!(flags&2);p.grayscale=!!(flags&4);
    p.usedTextures[0]=comb.usedTextures[0]=!!(flags&8);
    p.usedTextures[1]=comb.usedTextures[1]=!!(flags&16);
    p.numInputs=uint8_t((flags>>5)&7);p.tm=(flags>>8)&15;
    p.clip.invertY=!!(flags&4096);p.clip.z_is_from_0_to_1=!!(flags&8192);
    r.other_mode_l=(flags&16384)?G_TL_LOD:0;
    r.other_mode_h=(flags&32768)?(1U<<G_MDSFT_TEXTFILT):0;
    r.fog_color=color();r.grayscale_color=color();r.prim_color=color();r.env_color=color();
    r.prim_lod_fraction=uint8_t(next());
    for(unsigned t=0;t<2;++t) {
        p.width[t]=(next()%255)+1;p.height[t]=(next()%255)+1;
        p.boundWidth[t]=(next()%255)+1;p.boundHeight[t]=(next()%255)+1;
        r.texture_tile[t].shifts=int(next()%16);r.texture_tile[t].shiftt=int(next()%16);
        r.texture_tile[t].uls=small();r.texture_tile[t].ult=small();
        // Exercise the clamp-generated texture-coordinate fallback too.
        if(flags&65536)comb.usedTextures[t]=false;
    }
    const uint8_t rgb[]={3,4,5,10,12,14,13},alpha[]={0,1,2,3,4,5,6,7};
    for(unsigned j=0;j<7;++j) {
        comb.shader_input_mapping[0][j]=rgb[next()%7];
        comb.shader_input_mapping[1][j]=alpha[next()%8];
    }
}
static void Pool(LoadedVertex pool[256],unsigned special) {
    for(unsigned i=0;i<256;++i) {
        pool[i].x=small();pool[i].y=small();pool[i].z=small();pool[i].w=small();
        pool[i].u=small();pool[i].v=small();pool[i].color=color();
    }
    if(special) {
        const uint32_t bits[]={0,0x80000000U,0x3F800000U,0xBF800000U,
            0x7FC12345U,0xFFC23456U,0x7F800000U,0xFF800000U,
            1,0x80000001U,0x007FFFFFU,0x7F7FFFFFU};
        for(unsigned i=0;i<12;++i) {
            memcpy(&pool[i].x,&bits[i],4);
            memcpy(&pool[i].y,&bits[(i+1)%12],4);
            memcpy(&pool[i].z,&bits[(i+2)%12],4);
            // Keep LOD conversion defined while testing special xyz/uv bits.
            memcpy(&pool[i].u,&bits[(i+3)%12],4);
            memcpy(&pool[i].v,&bits[(i+4)%12],4);
        }
    }
}
static void CompareTriangle(FlatRunner& flat,Runner& indexed,const LoadedVertex pool[256],
                            const uint8_t ids[3],bool certified,bool rect,unsigned n,unsigned tri) {
    gModernIndexedContractFailureCase=n;gModernIndexedContractFailureTriangle=tri;
    LoadedVertex input[3];for(unsigned i=0;i<3;++i)input[i]=pool[ids[i]];
    flat.mBufVboLen=0;flat.Pack(false,input,rect);
    indexed.expected.insert(indexed.expected.end(),flat.mBufVbo,flat.mBufVbo+flat.mBufVboLen);
    indexed.Pack(certified,input,rect,ids);
    const size_t stride=flat.mBufVboLen/3;
    for(unsigned i=0;i<3;++i) {
        const float* actual=indexed.mBufVboNumTris ?
            indexed.mBufVbo+indexed.mXboxTriangleIndices[3*(indexed.mBufVboNumTris-1)+i]*stride :
            &indexed.flattened[indexed.flattened.size()-flat.mBufVboLen+i*stride];
        if(memcmp(flat.mBufVbo+i*stride,actual,stride*4)) {
            gModernIndexedContractFailureCorner=i;
            printf("FAIL bytes case=%u tri=%u corner=%u stride=%u rows=%u\n",n,tri,i,
                   unsigned(stride),unsigned(indexed.mXboxIndexedRows));
            for(size_t j=0;j<stride;++j)if(memcmp(flat.mBufVbo+i*stride+j,actual+j,4)) {
                uint32_t a,b;memcpy(&a,flat.mBufVbo+i*stride+j,4);memcpy(&b,actual+j,4);
                gModernIndexedContractFailureLane=uint32_t(j);
                printf("lane=%u expected=%08x actual=%08x\n",unsigned(j),a,b);break;
            }
            IndexedContractFail(1);
        }
    }
}
static int IndexedContractBody() {
    unsigned checks=0;size_t rows=0,corners=0;
    const unsigned rounds[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    for(unsigned rn=0;rn<4;++rn) {
        _controlfp(rounds[rn],_MCW_RC);
        for(unsigned n=0;n<4096;++n) {
            RDP r;ColorCombiner comb;XboxTrianglePipelineResult p;Setup(r,comb,p,n*31);
            LoadedVertex pool[256];Pool(pool,n%13==0);
            FlatRunner flat={};Runner indexed;
            flat.mRdp=indexed.mRdp=&r;flat.mXboxPipelineResult=indexed.mXboxPipelineResult=p;
            for(unsigned tri=0;tri<24;++tri) {
                uint8_t ids[3];
                switch(n%5) {
                case 0:for(unsigned i=0;i<3;++i)ids[i]=uint8_t(tri*3+i);break;
                case 1:ids[0]=0;ids[1]=uint8_t(tri+1);ids[2]=uint8_t(tri+2);break;
                case 2:ids[0]=0;ids[1]=1;ids[2]=2;break;
                case 3:ids[0]=uint8_t(tri);ids[1]=ids[0];ids[2]=uint8_t(tri+1);break;
                default:for(unsigned i=0;i<3;++i)ids[i]=uint8_t(next());break;
                }
                if(tri==7 || tri==16) {
                    indexed.mXboxPairPacked.Reset(); // A non-TRI2 command.
                    r.prim_color=color();r.env_color=color();
                    pool[ids[0]].u+=1;pool[ids[0]].color=color();
                }
                if(tri==12&&(n&1))indexed.Flush();
                if(tri==18&&(n&2)) {indexed.mXboxPairPacked.generation=0xFFFFFFFFU;indexed.mXboxPairPacked.Reset();}
                CompareTriangle(flat,indexed,pool,ids,n%11!=0,!!(n&128),n,tri);++checks;
            }
            indexed.Flush();rows+=indexed.emittedRows;corners+=indexed.emittedCorners;
        }
    }
    // Full batch rollover, all 256 keys, material/stride changes, and RN changes.
    for(unsigned rn=0;rn<4;++rn) {
        RDP r;ColorCombiner comb;XboxTrianglePipelineResult p;
        LoadedVertex pool[256];Pool(pool,0);FlatRunner flat={};Runner indexed;
        flat.mRdp=indexed.mRdp=&r;
        for(unsigned tri=0;tri<1027;++tri) {
            if(tri%257==0) {
                _controlfp(rounds[(rn+tri/257)%4],_MCW_RC);
                Setup(r,comb,p,(tri/257)*87+10);indexed.mXboxPairPacked.Reset();
                flat.mXboxPipelineResult=indexed.mXboxPipelineResult=p;
            }
            const uint8_t ids[3]={uint8_t(tri),uint8_t(tri+1),uint8_t(tri+2)};
            CompareTriangle(flat,indexed,pool,ids,true,false,4096+rn,tri);++checks;
        }
        indexed.Flush();rows+=indexed.emittedRows;corners+=indexed.emittedCorners;
    }
    _controlfp(_RC_NEAR,_MCW_RC);
    // The native representation must really omit rows, including first-use repeats.
    RDP r;ColorCombiner comb;XboxTrianglePipelineResult p;Setup(r,comb,p,8+(1<<5));
    LoadedVertex pool[256];Pool(pool,0);FlatRunner flat={};Runner indexed;
    flat.mRdp=indexed.mRdp=&r;flat.mXboxPipelineResult=indexed.mXboxPipelineResult=p;
    const uint8_t repeated[3]={7,7,7};
    CompareTriangle(flat,indexed,pool,repeated,true,false,9000,0);
    CompareTriangle(flat,indexed,pool,repeated,true,false,9000,1);
    if(indexed.mXboxIndexedRows!=1 || indexed.mBufVboNumTris!=2) {
        puts("FAIL duplicate rows were retained");return 2;
    }
    printf("PASS indexed flattened-byte checks=%u four_RN rows=%u corners=%u repeat_rows=1/6\n",
           checks,unsigned(rows),unsigned(corners));
    gModernIndexedContractChecks=checks;
    gModernIndexedContractRows=uint32_t(rows);
    gModernIndexedContractCorners=uint32_t(corners);
    return 0;
}
extern "C" int RunModernIndexedCpuContract() {
    const unsigned savedRounding=_controlfp(0,0);
    seed=0x47e12c9du;
    gModernIndexedContractStatus=1;
    gModernIndexedContractChecks=gModernIndexedContractRows=gModernIndexedContractCorners=0;
    gModernIndexedContractSignature=2166136261U;
    gModernIndexedContractFailureCase=gModernIndexedContractFailureTriangle=0;
    gModernIndexedContractFailureCorner=gModernIndexedContractFailureLane=0;
    int result;
    try { result=IndexedContractBody(); }
    catch(int failure) { result=failure; }
    catch(...) { result=255; }
    _controlfp(savedRounding,_MCW_RC);
    gModernIndexedContractStatus=result?uint32_t(0x80000000U|unsigned(result)):2;
    return result;
}
#ifndef MODERN_INDEXED_CONTRACT_NO_MAIN
int main() { return RunModernIndexedCpuContract(); }
#endif
'''


class Tri2Indexed(unittest.TestCase):
    def test_projection_and_flattened_bytes(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        projected = transform(source)
        self.assertEqual(projected, transform(projected))
        declarations = header((ROOT / 'scratch/fast3d-xdk/generated/include/fast/interpreter.h').read_text())
        self.assertEqual(declarations, header(declarations))
        self.assertIn('uint16_t mXboxTriangleIndices[256 * 3]', declarations)
        self.assertIn('#if !defined(SHIPYARD_XENOS_INDEXED_TRIANGLES)', projected)
        self.assertIn('Fast::ShipyardXenos::DrawIndexedTriangles', projected)
        out = ROOT / 'scratch/fast3d-xdk/tri2-indexed'
        out.mkdir(parents=True, exist_ok=True)
        cpp = out / 'contract.cpp'
        cpp.write_text(fixture())
        compiler, environment = host_environment()
        exe = out / 'contract.exe'
        built = subprocess.run([str(compiler), '/nologo', '/O2', '/EHsc', '/fp:strict', '/MD',
                                '/I' + str(ROOT / 'platform/shipyard'),
                                '/I' + str(resolve(ROOT) / 'sources'), str(cpp), '/Fe:' + str(exe)],
                               cwd=out, env=environment, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (out / 'result.txt').write_text(result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
