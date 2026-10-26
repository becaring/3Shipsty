"""Compare projected game algorithms with their source implementations on the host."""
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from game_cpu_projection import project


def function(text, name):
    match = re.search(r'^(?:static )?[\w* ]+\b' + name + r'\([^;]*?\)\s*\{', text, re.M)
    assert match, name
    depth = 1
    index = match.end()
    while depth:
        depth += (text[index] == '{') - (text[index] == '}')
        index += 1
    return text[match.start():index]


def main():
    out = ROOT / 'scratch/xenon-cpu-audit/game-candidate/host-game'
    out.mkdir(parents=True, exist_ok=True)
    actor = (ROOT / 'soh/src/code/z_actor.c').read_text(encoding='utf-8')
    lights = (ROOT / 'soh/src/code/z_lights.c').read_text(encoding='utf-8')
    animation = (ROOT / 'soh/src/code/z_skelanime.c').read_text(encoding='utf-8')
    ids = sorted(set(re.findall(r'ACTOR_\w+', function(actor, 'Ship_CalcShouldDrawAndUpdate'))))
    prelude = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdio>
using s16=int16_t; using s32=int32_t; using f32=float; using u8=uint8_t;
struct Vec3s { s16 x,y,z; }; struct Vec3f { float x,y,z; };
struct PlayState {};
struct Actor { int id,params; float uncullZoneScale,uncullZoneForward,uncullZoneDownward; };
struct Light { struct { uint8_t col[3],colc[3]; int8_t dir[3]; } l; };
struct LightPoint { int16_t x,y,z; uint8_t color[3],drawGlow; int16_t radius; };
struct LightDirectional { int8_t x,y,z; uint8_t color[3]; };
union LightParams { LightPoint point; LightDirectional dir; };
struct LightInfo { uint8_t type; LightParams params; };
struct LightNode { LightInfo* info; LightNode* prev; LightNode* next; };
struct Lights { uint8_t numLights; struct { Light l[7]; } l; };
using LightsBindFunc=void(*)(Lights*,LightParams*,Vec3f*);
struct SkelAnime { void* animation; float curFrame,animLength,morphWeight,morphRate;
 int limbCount,mode; Vec3s* jointTable; Vec3s* morphTable; };
#define SQ(x) ((x)*(x))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define CVAR_ENHANCEMENT(x) x
#define R_UPDATE_RATE 3
#define ANIM_INTERP 1
'''
    prelude += 'enum { ' + ','.join(ids) + ' };\n'
    parts = [prelude]
    for projected in (False, True):
        a = project('soh/src/code/z_actor.c', actor) if projected else actor
        l = project('soh/src/code/z_lights.c', lights) if projected else lights
        s = project('soh/src/code/z_skelanime.c', animation) if projected else animation
        parts.append('namespace ' + ('changed' if projected else 'original') + ' {\n')
        parts.append(r'''
int distance=1,wide=0,exclude=0,reads=0,frameLoads=0;
float ratio=1.7777778f;
int CVarGetInteger(const char* n,int) { ++reads; return !strcmp(n,"DisableDrawDistance")?distance:
 !strcmp(n,"WidescreenActorCulling")?wide:exclude; }
float OTRGetAspectRatio() { return ratio; }
void SkelAnime_GetFrameData(void*,int frame,int count,Vec3s* out) {
 ++frameLoads;
 for(int i=0;i<count;++i) out[i]=Vec3s{(s16)(frame*31003+i*19711),
 (s16)(-frame*25001+i*22007),(s16)(frame*17011-i*31013)};
}
''')
        for name in ('Lights_FindSlot', 'Lights_BindPoint', 'Lights_BindDirectional', 'Lights_BindAll'):
            parts.append(function(l, name))
        parts.append(function(a, 'func_800314D4'))
        if projected:
            parts.append('struct ShipActorCullSettings { s32 distance,widescreen; bool hasWidescreen; };')
            parts.append(function(a, 'Ship_CalcShouldDrawAndUpdateWithSettings'))
        parts.append(function(a, 'Ship_CalcShouldDrawAndUpdate'))
        for name in ('SkelAnime_InterpFrameTable', 'SkelAnime_AnimateFrame'):
            parts.append(function(s, name))
        label_start = a.index('            if (GfxDebuggerIsDebugging()') if projected else a.index(
            '            char* actorName = ActorDB_Retrieve(actor->id)->name;')
        label_end = a.index('            HREG(66) = i;', label_start)
        parts.append(r'''
bool debugging=false,requested=false; int nameLookups=0;
bool GfxDebuggerIsDebugging() {return debugging;}
bool GfxDebuggerIsDebuggingRequested() {return requested;}
struct Entry { char* name; };
Entry* ActorDB_Retrieve(int) { static char name[]="actor";static Entry e={name};++nameLookups;return &e; }
void emit(int* destination,char* name,int index) {assert(!strcmp(name,"actor"));*destination=index+1;}
void Labels(Actor* actor,int i,int* opa,int* xlu) {
#define POLY_OPA_DISP opa
#define POLY_XLU_DISP xlu
#define gDPNoOpString(dest,name,index) emit(dest,name,index)
''')
        parts.append(a[label_start:label_end])
        parts.append('}\n#undef POLY_OPA_DISP\n#undef POLY_XLU_DISP\n#undef gDPNoOpString\n')
        parts.append('}\n')
    parts.append(r'''
static uint32_t rng=123456789;
static uint32_t next() { rng=rng*1664525u+1013904223u; return rng; }
int main() {
 // The capture-request frame must retain labels even before debugging becomes active.
 for(int mode=0;mode<4;++mode) {
  original::debugging=changed::debugging=mode&1;original::requested=changed::requested=mode&2;
  original::nameLookups=changed::nameLookups=0;
  Actor actor={}; int ao=0,ax=0,bo=0,bx=0;
  original::Labels(&actor,9,&ao,&ax);changed::Labels(&actor,9,&bo,&bx);
  assert(original::nameLookups==1);
  assert(changed::nameLookups==(mode?1:0));
  assert(mode?(ao==bo&&ax==bx):(bo==0&&bx==0));
 }
 // Compare first-seven binding, saturation, point rejection, NULL position and light order.
 for(int trial=0;trial<5000;++trial) {
  LightInfo info[32]={}; LightNode nodes[32]={};
  for(int i=0;i<32;++i) {
   info[i].type=next()%3;
   if(info[i].type==1) { info[i].params.dir.x=next();info[i].params.dir.y=next();
    info[i].params.dir.z=next(); for(int c=0;c<3;++c) info[i].params.dir.color[c]=next(); }
   else { auto& p=info[i].params.point;p.x=(next()%400)-200;p.y=(next()%400)-200;
    p.z=(next()%400)-200;p.radius=next()%400;for(int c=0;c<3;++c)p.color[c]=next(); }
   nodes[i].info=&info[i];nodes[i].next=i<31?&nodes[i+1]:nullptr;
  }
  Lights a={},b={};a.numLights=b.numLights=trial%8; Vec3f pos={12,-25,48};
  original::Lights_BindAll(&a,nodes,trial%3?&pos:nullptr);
  changed::Lights_BindAll(&b,nodes,trial%3?&pos:nullptr);
  assert(!memcmp(&a,&b,sizeof a));
 }
 // Each call sees fresh culling settings; test wrapper and the cached internal route.
 for(int trial=0;trial<100000;++trial) {
  original::distance=changed::distance=(next()%6)-1;
  original::wide=changed::wide=next()%2; original::exclude=changed::exclude=next()%2;
  Actor actor={(int)(next()%12),(int)next(),(float)(next()%500),
   (float)(next()%2000),(float)(next()%1000)};
  Vec3f p={(float)((int)(next()%4000)-2000),(float)((int)(next()%4000)-2000),
   (float)((int)(next()%6000)-1000)}; float w=(int)(next()%2000)-1000;
  bool ad=false,au=false,bd=false,bu=false,cd=false,cu=false;
  original::reads=changed::reads=0;
  int ar=original::Ship_CalcShouldDrawAndUpdate(nullptr,&actor,&p,w,&ad,&au);
  int br=changed::Ship_CalcShouldDrawAndUpdate(nullptr,&actor,&p,w,&bd,&bu);
  assert(original::reads==changed::reads);changed::reads=0;
  changed::ShipActorCullSettings settings={changed::distance,changed::wide,changed::distance<=1};
  int cr=changed::Ship_CalcShouldDrawAndUpdateWithSettings(nullptr,&actor,&p,w,&cd,&cu,&settings);
  assert(changed::reads<=original::reads);
  assert(ar==br&&ar==cr&&ad==bd&&ad==cd&&au==bu&&au==cu);
 }
 // Integer/fractional frames, mode toggles, wrap, nonzero morph and s16 wrapping.
 for(int trial=0;trial<5000;++trial) {
  Vec3s aj[100]={},bj[100]={},morph[100];
  for(auto& v:morph) v=Vec3s{(s16)next(),(s16)next(),(s16)next()};
  SkelAnime a={nullptr,float(trial%31)+((trial/4)%2?0.25f:0.0f),32.0f,
   float(trial%5)*.25f,.17f,1+trial%100,trial%4,aj,morph},b=a;b.jointTable=bj;
  original::frameLoads=changed::frameLoads=0;
  original::SkelAnime_AnimateFrame(&a);changed::SkelAnime_AnimateFrame(&b);
  assert(!memcmp(aj,bj,sizeof aj)&&a.morphWeight==b.morphWeight);
  assert(changed::frameLoads==((a.mode&1)&&a.curFrame!=(int)a.curFrame?2:1));
 }
 puts("PASS source light binding 5000, culling 100000, animation 5000 differential cases; debugger label states 4");
}
''')
    source = out / 'contract.cpp'
    source.write_text('\n'.join(parts), encoding='utf-8')
    compiler, env = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))['host_environment']()
    command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/fp:precise', str(source),
               '/Fo:' + str(out / 'contract.obj'), '/Fe:' + str(out / 'contract.exe')]
    build = subprocess.run(command, env=env, capture_output=True, text=True)
    (out / 'build.log').write_text(build.stdout + build.stderr)
    assert build.returncode == 0, out / 'build.log'
    result = subprocess.run([str(out / 'contract.exe')], capture_output=True, text=True)
    (out / 'result.json').write_text(json.dumps(dict(exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    assert result.returncode == 0, result.stderr
    print(result.stdout)


if __name__ == '__main__':
    main()
