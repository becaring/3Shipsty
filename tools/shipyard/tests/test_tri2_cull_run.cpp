#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <float.h>
#include "fast3d/projection_cache.h"
#include "fast3d/tri2_cull_run.h"

struct Vertex { float x,y,w; };
static Shipyard::Fast3D::ProjectionValueCache sModernCullProjection[68];
static ModernTri2CullRunCache sModernTri2CullRun;
static unsigned roundingReads;
static uint32_t ReadRounding() {
    ++roundingReads;
    return Shipyard::Fast3D::ProjectionRoundingMode();
}
static __declspec(noinline) float Original(Vertex* v1, Vertex* v2, Vertex* v3) {
/* ORIGINAL */
    return cross;
}
static __declspec(noinline) float Projected(Vertex* v1, Vertex* v2, Vertex* v3,
                        uint8_t vtx1_idx,uint8_t vtx2_idx,uint8_t vtx3_idx,
                        bool mXboxTrianglePairActive) {
/* PROJECTED */
    return cross;
}
static uint32_t Next(uint32_t& state) {
    state^=state<<13; state^=state>>17; state^=state<<5; return state;
}
static float Bits(uint32_t bits) { float f; memcpy(&f,&bits,4); return f; }
static float Finite(uint32_t bits) { return Bits((bits&0x807fffffu)|0x3f000000u); }
int main() {
    uint32_t seed=0x5429ae17u;
    const uint32_t edges[]={0,0x80000000u,1,0x80000001u,0x7f800000u,
                            0xff800000u,0x7fc01234u,0x7f7fffffu};
    unsigned checks=0, totalReads=0;
    for(unsigned mode=0;mode<4;++mode) {
        for(unsigned run=0;run<4096;++run) {
            Vertex vertices[68];
            for(unsigned i=0;i<68;++i) {
                vertices[i].x=Finite(Next(seed));
                vertices[i].y=Finite(Next(seed));
                vertices[i].w=Finite(Next(seed));
            }
            if(run<8) vertices[0].w=Bits(edges[run]);
            unsigned previous;
            _controlfp_s(&previous,mode<<8,_MCW_RC);
            sModernTri2CullRun.Reset();
            const bool active=(run&3)!=0;
            roundingReads=0;
            for(unsigned tri=0;tri<32;++tri) {
                // Model a renderer callback that changes RN, then a vertex write.
                if(tri==16) {
                    sModernTri2CullRun.Reset();
                    _controlfp_s(&previous,((mode+1)%4)<<8,_MCW_RC);
                    vertices[2].x=Finite(Next(seed));
                }
                unsigned a=Next(seed)%16,b=Next(seed)%16,c=Next(seed)%16;
                if(run<8) a=0;
                const float original=Original(vertices+a,vertices+b,vertices+c);
                const float projected=Projected(vertices+a,vertices+b,vertices+c,
                    uint8_t(a),uint8_t(b),uint8_t(c),active);
                uint32_t word; memcpy(&word,&original,4);
                const bool nan=(word&0x7fffffffu)>0x7f800000u;
                if((!nan && memcmp(&original,&projected,4)) ||
                   (original<=0)!=(projected<=0) || (original>=0)!=(projected>=0)) {
                    printf("FAIL mode=%u run=%u triangle=%u\n",mode,run,tri); return 1;
                }
                ++checks;
            }
            if(roundingReads!=(active?2u:32u)) return 2;
            totalReads+=roundingReads;
        }
    }
    // Reset wraparound must not authorize stale entries stamped in generation 1.
    sModernTri2CullRun.generation=0xffffffffu;
    sModernTri2CullRun.generations[0]=1;
    sModernTri2CullRun.Reset();
    Vertex vertex={0.7f,0.3f,3.0f};
    sModernTri2CullRun.Load(0,sModernCullProjection[0],vertex,ReadRounding());
    if(sModernCullProjection[0].x!=vertex.x/vertex.w) return 3;
    // Exceptional inputs retain the underlying cache's uncached behavior.
    for(unsigned i=0;i<8;++i) {
        sModernTri2CullRun.Reset(); vertex.w=Bits(edges[i]);
        sModernTri2CullRun.Load(0,sModernCullProjection[0],vertex,ReadRounding());
        if(!sModernCullProjection[0].valid &&
           sModernTri2CullRun.generations[0]==sModernTri2CullRun.generation) return 4;
    }
    printf("PASS TRI2 cull runs cases=%u RN_reads=%u original_RN_reads=%u four_modes\n",
           checks,totalReads,checks);
    return 0;
}
