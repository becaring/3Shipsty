#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <float.h>
#include "fast3d/material_value_cache.h"
#include "fast3d/projection_cache.h"

#define G_IM_SIZ_4b 0
#define G_IM_SIZ_8b 1
#define G_IM_SIZ_16b 2
#define G_IM_SIZ_32b 3
#define G_IM_SIZ_16b_LINE_BYTES 2
#define G_IM_SIZ_32b_LINE_BYTES 2
#define G_TX_MIRROR 1
#define G_TX_CLAMP 2

struct Tile {
    uint8_t siz, cms, cmt, tmem_index;
    uint32_t line_size_bytes;
    float uls, ult, lrs, lrt;
};
struct Loaded { uint32_t orig_size_bytes; };
struct RDP { Tile texture_tile[8]; Loaded loaded_texture[2]; };
static unsigned rebuilds;
// GENERATED_HELPERS
struct Harness {
    RDP* mRdp;
    unsigned i, tile, tm;
    uint32_t tex_width[2], tex_height[2], tex_width2[2], tex_height2[2];
    uint8_t cms_out,cmt_out;
    void Original(); void Projected();
};
void Harness::Original() {
// ORIGINAL_BODY
    cms_out=cms; cmt_out=cmt;
}
void Harness::Projected() {
// PROJECTED_BODY
    cms_out=cms; cmt_out=cmt;
}
static void require(bool okay,const char* what) {
    if(!okay) { fprintf(stderr,"FAIL %s\n",what); exit(1); }
}
static uint32_t randomState=0x6be3129f;
static uint32_t Next() { randomState^=randomState<<13; randomState^=randomState>>17; return randomState^=randomState<<5; }
static void Compare(RDP& rdp,unsigned slot,unsigned tile) {
    Harness a={};a.mRdp=&rdp;a.i=slot;a.tile=tile;a.tm=0x5a5a0000;
    Harness b=a;a.Original();b.Projected();
    require(a.tm==b.tm,"clamp mask");
    require(!memcmp(a.tex_width,b.tex_width,sizeof(a.tex_width)),"width and inactive slot");
    require(!memcmp(a.tex_height,b.tex_height,sizeof(a.tex_height)),"height and inactive slot");
    require(!memcmp(a.tex_width2,b.tex_width2,sizeof(a.tex_width2)),"bound width and inactive slot");
    require(!memcmp(a.tex_height2,b.tex_height2,sizeof(a.tex_height2)),"bound height and inactive slot");
    require(a.cms_out==b.cms_out && a.cmt_out==b.cmt_out,"sampler modes");
}
int main() {
    RDP rdp={};unsigned cases=0;
    for(unsigned n=0;n<65536;++n) {
        unsigned tile=n%8,slot=(n>>3)%2;
        Tile& t=rdp.texture_tile[tile]; t.tmem_index=(n>>4)%2;
        Loaded& l=rdp.loaded_texture[t.tmem_index];
        t.siz=n%4;t.cms=(n>>2)%4;t.cmt=(n>>4)%4;
        t.uls=(int(Next()%8192)-4096)*0.25f;t.ult=(int(Next()%8192)-4096)*0.25f;
        t.lrs=(int(Next()%8192)-4096)*0.25f;t.lrt=(int(Next()%8192)-4096)*0.25f;
        t.line_size_bytes=Next()%4097;l.orig_size_bytes=Next()%65537;
        Compare(rdp,slot,tile);++cases;
        unsigned before=rebuilds;Compare(rdp,slot,tile);++cases;
        require(before==rebuilds,"same complete geometry reuses value");
#define MUTATE(field) { auto saved=field; unsigned beforeMutation=rebuilds; field=decltype(field)(field+1); Compare(rdp,slot,tile); ++cases; require(rebuilds==beforeMutation+1,"each key dependency rebuilds"); field=saved; }
        MUTATE(t.siz);MUTATE(t.cms);MUTATE(t.cmt);MUTATE(t.uls);MUTATE(t.ult);
        MUTATE(t.lrs);MUTATE(t.lrt);MUTATE(t.line_size_bytes);MUTATE(l.orig_size_bytes);
#undef MUTATE
        RDP other=rdp;Compare(other,slot,tile);++cases;
    }
    unsigned savedRound=_controlfp(0,0)&_MCW_RC;
    _controlfp(_RC_DOWN,_MCW_RC);Compare(rdp,0,0);Compare(rdp,0,0);
    unsigned beforeRoundChange=rebuilds;
    _controlfp(_RC_UP,_MCW_RC);Compare(rdp,0,0);
    require(rebuilds==beforeRoundChange+1,"FPSCR rounding-mode change rebuilds");
    _controlfp(savedRound,_MCW_RC);
    printf("PASS %u original/projected Modern geometry cases and key mutations\n",cases);
}
