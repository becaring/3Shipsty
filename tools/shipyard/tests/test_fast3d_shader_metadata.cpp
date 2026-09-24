#include "fast/interpreter.h"
#include "fast3d/shader_metadata_cache.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <type_traits>

namespace Fast {
struct ShaderProgram { unsigned id; uint8_t inputs; bool used[2]; };
// EXTRACTED_COMBINERS
static_assert(std::is_trivial<ProjectedCombiner>::value, "combiner remains POD");
struct Result { uint8_t inputs; bool used[2]; GfxClipParameters clip; };
struct Backend {
    ShaderProgram programs[16]; unsigned infos, clips, events; GfxClipParameters clip;
    Backend() : infos(0), clips(0), events(0) { Reset(0); }
    void Reset(unsigned seed) {
        for (unsigned i=0;i<16;++i) {
            programs[i].id=i+1; programs[i].inputs=(uint8_t)((i+seed)%8);
            programs[i].used[0]=((i+seed)&1)!=0;programs[i].used[1]=((i+seed)&2)!=0;
        }
        clip.z_is_from_0_to_1=(seed&1)!=0;clip.invertY=(seed&2)!=0;
    }
    void Init() {}
    void Event(unsigned value) { events=events*31+value; }
    void UnloadShader(ShaderProgram* p) { Event(100+(p?p->id:0)); }
    void LoadShader(ShaderProgram* p) { Event(200+p->id); }
    void SetUseAlpha(bool value) { Event(300+value); }
    void ShaderGetInfo(ShaderProgram* p,uint8_t* inputs,bool used[2]) {
        if (!p) std::abort(); ++infos;*inputs=p->inputs;used[0]=p->used[0];used[1]=p->used[1];
    }
    GfxClipParameters GetClipParameters() { ++clips;return clip; }
};
template<class Combiner> struct Harness {
    Backend* mRapi; RenderingState mRenderingState;
    std::map<ColorCombinerKey,Combiner> mColorCombinerPool; Result result;
    Harness() : mRapi(NULL), mRenderingState(), result() {}
    Combiner& At() { ColorCombinerKey key={};return mColorCombinerPool[key]; }
    void Flush() { mRapi->Event(400); }
    ShaderProgram* LookupOrCreateShaderProgram(uint64_t,uint64_t key) {
        unsigned variant=(unsigned)(key/SHADER_OPT(TEXEL0_CLAMP_S))&15;
        mRapi->Event(500+variant);return &mRapi->programs[variant];
    }
};
struct Original : Harness<OriginalCombiner> { typedef OriginalCombiner ColorCombiner;void Phase(unsigned,bool);void Init(Backend*); };
struct Projected : Harness<ProjectedCombiner> { typedef ProjectedCombiner ColorCombiner;void Phase(unsigned,bool);void Init(Backend*); };
// EXTRACTED_FUNCTIONS
}
static void require(bool ok,const char* message) { if(!ok){std::fprintf(stderr,"FAIL %s\n",message);std::exit(1);} }
int main() {
    Fast::Backend a[2],b[2];Fast::Original original;Fast::Projected projected;
    for(unsigned epoch=0;epoch<8;++epoch) {
        unsigned which=epoch%2;a[which].Reset(epoch);b[which].Reset(epoch);
        original.Init(&a[which]);projected.Init(&b[which]);
        unsigned initialInfo=b[which].infos;
        for(unsigned n=0;n<1024;++n) {
            unsigned variant=n%16;bool alpha=((n/32)&1)!=0;
            if(n==256) {original.mColorCombinerPool.clear();projected.mColorCombinerPool.clear();}
            if(n==512) {
                original.At().prg[3]=&a[which].programs[7];
                projected.At().prg[3]=&b[which].programs[7];
            }
            if(n==768) {a[which].clip.invertY=!a[which].clip.invertY;b[which].clip.invertY=!b[which].clip.invertY;}
            original.Phase(variant,alpha);projected.Phase(variant,alpha);
            require(original.result.inputs==projected.result.inputs,"inputs");
            require(original.result.used[0]==projected.result.used[0]&&original.result.used[1]==projected.result.used[1],"textures");
            require(original.result.clip.invertY==projected.result.clip.invertY&&
                    original.result.clip.z_is_from_0_to_1==projected.result.clip.z_is_from_0_to_1,"dynamic clip");
            require(a[which].events==b[which].events,"bind/flush/alpha order");
        }
        require(b[which].infos-initialInfo==33,"metadata not reused by variant");
        require(a[which].clips==b[which].clips,"modern clip read count changed");
        original.Phase(1,true);projected.Phase(1,true);
        unsigned before=b[which].infos;
        a[which].Reset(epoch+19);b[which].Reset(epoch+19);
        original.Init(&a[which]);projected.Init(&b[which]);
        original.Phase(1,true);projected.Phase(1,true);
        require(original.result.inputs==projected.result.inputs&&
                original.result.used[0]==projected.result.used[0]&&
                original.result.used[1]==projected.result.used[1],"same-address reinit");
        require(b[which].infos==before+1,"reinit did not refresh once");
        require(a[which].events==b[which].events,"reinit event order");
    }
    std::puts("PASS modern shader metadata differential: 8192 state transitions, dynamic clip, replacement, reinit");
}
