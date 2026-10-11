#define _USE_MATH_DEFINES
#include <cmath>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <vector>
#include <unordered_map>
#include <mutex>
#include "interpolation/recording_memory.h"
#include "binary/compat.h"
typedef float f32;
typedef int16_t s16;
typedef uint16_t u16;
typedef int32_t s32;
typedef uint32_t u32;
typedef uint8_t u8;
struct Mtx { int unused; };
struct MtxF { float mf[4][4]; };
struct Vec3f { float x,y,z; };
struct Vec3s { s16 x,y,z; };
enum MatrixMode { MTXMODE_NEW, MTXMODE_APPLY };
template<class T> auto PrismBegin(T& c)->decltype(c.begin()){return c.begin();}
template<class T> auto PrismEnd(T& c)->decltype(c.end()){return c.end();}
struct OTRGlobals { static OTRGlobals* Instance; unsigned GetInterpolationFPS(){return 60;} };
static OTRGlobals globals;
OTRGlobals* OTRGlobals::Instance=&globals;
static MtxF current;
static MtxF translated(float x) {
    MtxF m={}; for(int i=0;i<4;++i)m.mf[i][i]=1; m.mf[3][0]=x; return m;
}
MtxF* Matrix_GetCurrent(){return &current;}
void SkinMatrix_MtxFMtxFMult(MtxF* a,MtxF* b,MtxF* out){
    MtxF result={};for(int i=0;i<4;++i)for(int j=0;j<4;++j)for(int k=0;k<4;++k)result.mf[i][j]+=a->mf[i][k]*b->mf[k][j];*out=result;
}
void Matrix_SetTranslateRotateYXZ(float x,float y,float z,Vec3s* rot){assert(y==0&&z==0&&rot->x==0&&rot->y==0&&rot->z==0);current=translated(x);}
void Matrix_Put(MtxF* m){current=*m;}
// Unexercised operations must fail loudly rather than provide fake matrices.
static std::vector<MtxF> matrixStack;
void Matrix_Push(){matrixStack.push_back(current);}
void Matrix_Pop(){assert(!matrixStack.empty());current=matrixStack.back();matrixStack.pop_back();}
void Matrix_Mult(MtxF*,u8){std::abort();}
void Matrix_Translate(float,float,float,u8){std::abort();}
void Matrix_Scale(float,float,float,u8){std::abort();}
void Matrix_RotateX(float,u8){std::abort();}
void Matrix_RotateY(float,u8){std::abort();}
void Matrix_RotateZ(float,u8){std::abort();}
void Matrix_RotateZYX(s16,s16,s16,u8){std::abort();}
void Matrix_TranslateRotateZYX(Vec3f*,Vec3s*){std::abort();}
void Matrix_ReplaceRotation(MtxF*){std::abort();}
void Matrix_RotateAxis(float,Vec3f*,u8){std::abort();}

static unsigned reportedRecordingRequests;
extern "C" void MajoraProfileRecording(unsigned requests,unsigned,unsigned) {
    reportedRecordingRequests=requests;
}
extern "C" uint32_t Ship_GetInterpolationFPS(){return 60;}
namespace Shipyard { namespace Resources {
template<class T> auto begin(T& c)->decltype(c.begin()){return c.begin();}
template<class T> auto end(T& c)->decltype(c.end()){return c.end();}
} }
// SELECTED RECORDER
static Mtx destinations[3]; static int identity;
static void Record(float actor,float raw,int key,bool adjusted,bool extra=false) {
    FrameInterpolation_StartRecord();
    FrameInterpolation_RecordOpenChild(&identity,key);
    current=translated(actor); Vec3s rotation={};
    if(adjusted) FrameInterpolation_RecordActorPosRotMatrix();
    FrameInterpolation_RecordMatrixSetTranslateRotateYXZ(actor,0,0,&rotation);
    Matrix_Push(); FrameInterpolation_RecordMatrixPush();
    FrameInterpolation_RecordOpenChild(&identity,1);
    current=translated(raw);
    FrameInterpolation_RecordMatrixToMtx(&destinations[0],nullptr,0);
    FrameInterpolation_RecordCloseChild();
    Matrix_Pop(); FrameInterpolation_RecordMatrixPop();
    FrameInterpolation_RecordOpenChild(&identity,2);
    current=translated(raw+4);
    FrameInterpolation_RecordMatrixToMtx(&destinations[1],nullptr,0);
    if(extra) FrameInterpolation_RecordMatrixPush();
    FrameInterpolation_RecordCloseChild();
    MtxF plain=translated(raw+8);
    FrameInterpolation_RecordMatrixMtxFToMtx(&plain,&destinations[2]);
    plain=translated(raw+9);
    FrameInterpolation_RecordMatrixMtxFToMtx(&plain,&destinations[2]); // duplicate destination: last write wins
    FrameInterpolation_RecordCloseChild(); FrameInterpolation_StopRecord();
}
static void Check(float step) {
    auto result=FrameInterpolation_Interpolate(step); assert(result.size()==3);
    for(int i=0;i<3;i++) for(int r=0;r<4;r++)for(int c=0;c<4;c++)
        std::printf("%a ",double(result.at(&destinations[i]).mf[r][c]));
    for(int r=0;r<4;r++)for(int c=0;c<4;c++)std::printf("%a ",double(current.mf[r][c]));
    std::puts("");
#ifdef MODERN_RECYCLE_REPLAY
    FrameInterpolation_Recycle(result);
    assert(result.empty());
#endif
}
int main() {
    for(int old=0;old<2;old++)for(int now=0;now<2;now++) {
        Record(3,10,7,old!=0);Record(5,30,7,now!=0);
        for(float step:{0.0f,.25f,.5f,.75f,1.0f}) Check(step);
    }
    Record(3,10,7,true);Record(5,30,8,true);
    Check(.25f);Check(.5f);Check(.75f);
    Record(3,10,7,false);Record(5,30,7,false,true);Check(.5f);
    Record(3,10,7,true);Record(5,30,7,true);
    auto heldFirst=FrameInterpolation_Interpolate(.25f);
    auto heldLast=FrameInterpolation_Interpolate(.75f);
    auto expectedFirst=heldFirst; auto expectedLast=heldLast;
    Record(7,50,7,true);Record(9,70,7,true);Check(.5f);
    for(int i=0;i<3;++i) {
        assert(!memcmp(&heldFirst.at(&destinations[i]),&expectedFirst.at(&destinations[i]),sizeof(MtxF)));
        assert(!memcmp(&heldLast.at(&destinations[i]),&expectedLast.at(&destinations[i]),sizeof(MtxF)));
    }
#ifdef MODERN_RECYCLE_REPLAY
    FrameInterpolation_Recycle(heldFirst);FrameInterpolation_Recycle(heldLast);
    RecycledInterpolationMaps pool;
    Mtx keys[6145]={};
    typedef std::unordered_map<Mtx*,MtxF> Map;
    Map partial,match,output;
    std::vector<Mtx*> wanted;
    std::vector<MtxF*> slots;
    for(int i=0;i<3;++i) {
        partial[&keys[i]]=translated(11);
        wanted.push_back(&keys[i==2?3:i]);
        match[wanted.back()]=translated(22);
    }
    pool.Recycle(partial);pool.Recycle(match);
    assert(pool.Acquire(output,wanted,slots)&&slots.size()==3&&output.size()==3);
    for(int i=0;i<3;++i)assert(slots[i]==&output.at(wanted[i])&&slots[i]->mf[3][0]==22);
    output.clear();wanted[2]=&keys[4];
    assert(!pool.Acquire(output,wanted,slots)&&output.empty()&&slots.empty());
    Map oversized;
    for(int i=0;i<1025;++i)oversized[&keys[i]]=translated(33);
    pool.Recycle(oversized);assert(oversized.size()==1025);
    RecycledInterpolationMaps bounded;
    for(int bank=0;bank<8;++bank) {
        Map input;
        for(int i=0;i<768;++i)input[&keys[bank*768+i]]=translated(float(bank));
        bounded.Recycle(input);assert(input.empty());
    }
    unsigned retained=0;
    for(int bank=0;bank<8;++bank) {
        wanted.clear();slots.clear();output.clear();
        for(int i=0;i<768;++i)wanted.push_back(&keys[bank*768+i]);
        if(bounded.Acquire(output,wanted,slots)) {
            retained+=unsigned(output.size());
            for(int i=0;i<768;++i)assert(slots[i]->mf[3][0]==float(bank));
        }
    }
    assert(retained>0&&retained<=4096);
#endif
    FrameInterpolation_StartRecord();FrameInterpolation_StopRecord();
    assert(FrameInterpolation_Interpolate(.5f).empty());
}
