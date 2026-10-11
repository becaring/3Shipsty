#include "fast3d/numeric.h"
#include <limits>
#include <string.h>
#include <stdio.h>
#define MAX_LIGHTS 32
#define MAX_VERTICES 64
struct F3DVtx_t { short ob[3],flag,tc[2]; unsigned char cn[4]; };
struct F3DVtx_tn { short ob[3],flag,tc[2]; signed char n[3]; unsigned char a; };
union F3DVtx { F3DVtx_t v; F3DVtx_tn n; };
struct RGBA { uint8_t r,g,b,a; };
struct LoadedVertex { float x,y,z,w,u,v; RGBA color; uint8_t clip_rej; };
struct RSP { LoadedVertex loaded_vertices[MAX_VERTICES+4]; int16_t fog_mul,fog_offset; };
namespace Ship { namespace Math { template<typename T> T clamp(T v,T lo,T hi) { return v<lo?lo:(v>hi?hi:v); } } }
// PROJECTED_TYPES
class Interpreter {
public:
    RSP* mRsp;
    XboxDeferredVertex mXboxDeferredVertices[MAX_VERTICES];
    XboxDeferredContext mXboxDeferredContexts[MAX_VERTICES];
    XboxDeferredNormalEntry mXboxNormalCache[64] = {};
    uint32_t mXboxNormalCacheSerial = 0;
    bool mXboxNormalCacheEnabled = false;
    unsigned mXboxContextSearchAttempts,mXboxContextSlotsScanned,mXboxContextMaxScan;
    void XboxDiscardVertex(size_t);
    void XboxMaterializeVertex(size_t);
    void XboxTakeContextSearchCounts(unsigned*,unsigned*,unsigned*);
};
// PROJECTED_METHODS
static uint32_t bits(float v){uint32_t b;memcpy(&b,&v,4);return b;}
// Independent upstream arithmetic converts the ORIGINAL signed command words
// at consumption, without reading the projected context's float values.
static float originalFog(float z,float w,int16_t mul,int16_t offset) {
    if(fabsf(w)<0.001f)w=0.001f;
    float winv=1.0f/w;
    if(winv<0.0f)winv=std::numeric_limits<int16_t>::max();
    float fog=z*winv*mul+offset;
    return Ship::Math::clamp(fog,0.0f,255.0f);
}
int main() {
    const unsigned modes[]={_RC_NEAR,_RC_DOWN,_RC_UP,_RC_CHOP};
    const float depths[]={0.0f,0.0039961f,-0.007999f,1.0f,-1.0f,0.4999f,-0.4999f};
    const float widths[]={0.0f,1.0f,-1.0f,0.0003f,-0.0003f,2.0f,-2.0f};
    Interpreter owner={};RSP rsp={};owner.mRsp=&rsp;
    for(unsigned capture=0;capture<4;++capture) {
        _controlfp(modes[capture],_MCW_RC);
        for(unsigned word=0;word<65536;++word) {
            const int16_t mul=(int16_t)word,offset=(int16_t)(word^0xaaaaU);
            volatile int16_t rawMul=mul,rawOffset=offset;
            XboxDeferredContext snapshot={};
            snapshot.fogMul=Shipyard::Fast3D::SignedShortFloat(rawMul);
            snapshot.fogOffset=Shipyard::Fast3D::SignedShortFloat(rawOffset);
            if(bits(snapshot.fogMul)!=bits((float)rawMul) || bits(snapshot.fogOffset)!=bits((float)rawOffset))return 1;
            for(unsigned consume=0;consume<4;++consume) {
                _controlfp(modes[consume],_MCW_RC);
                for(unsigned position=0;position<7;++position) {
                    XboxDeferredContext* context=&owner.mXboxDeferredContexts[0];*context=snapshot;context->references=1;
                    owner.mXboxDeferredVertices[0].context=context;
                    LoadedVertex& vertex=rsp.loaded_vertices[0];vertex={};
                    vertex.z=depths[position];vertex.w=widths[position];
                    // Later commands overwrite mutable RSP fog state. The
                    // pending slot must retain both captured original words.
                    rsp.fog_mul=(int16_t)~mul;rsp.fog_offset=(int16_t)~offset;
                    const float expected=originalFog(vertex.z,vertex.w,rawMul,rawOffset);
                    const float actual=originalFog(vertex.z,vertex.w,(int16_t)context->fogMul,(int16_t)context->fogOffset);
                    if(bits(actual)!=bits(expected))return 2;
                    owner.XboxMaterializeVertex(0);
                    if(vertex.color.a!=(uint8_t)expected || context->references || owner.mXboxDeferredVertices[0].context)return 3;
                }
            }
            _controlfp(modes[capture],_MCW_RC);
        }
    }
    _controlfp(_RC_NEAR,_MCW_RC);
    puts("65536 signed values, 4 capture modes, 4 consume modes: exact fog snapshots");
    return 0;
}
