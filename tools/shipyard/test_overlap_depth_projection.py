"""Compile the projected game hooks and exercise capture without live render reads."""

from pathlib import Path
import importlib.util
import re
import subprocess
import tempfile
import unittest
from platform_base import resolve

ROOT = Path(__file__).resolve().parents[2]
VCVARS = Path(
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)


def function(text, name):
    start = re.search(
        r"^[\w* ]+\b" + name + r"\([^;\n]*\)\s*\{", text, re.MULTILINE
    ).start()
    brace = text.index("{", start)
    level = 1
    end = brace + 1
    while level:
        level += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


class OverlapDepthProjectionTests(unittest.TestCase):
    def test_captured_values_reuse_epochs_and_disabled_callback(self):
        projector = ROOT / "tools/shipyard/overlap_depth_projection.py"
        # The missing capture path runs the original callback after game mutation.
        if not projector.exists():
            self.fail(
                "Known graph callback must capture values before later game mutations"
            )
        spec = importlib.util.spec_from_file_location("depth_projection", projector)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        light_name = "soh/src/code/z_lights.c"
        env_name = "soh/src/code/z_kankyo.c"
        lights = module.project(
            light_name, (ROOT / light_name).read_text(encoding="utf-8-sig")
        )
        env = module.project(
            env_name, (ROOT / env_name).read_text(encoding="utf-8-sig")
        )
        fixture = r"""
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include "overlap/depth.h"
typedef int s32; typedef unsigned int u32; typedef float f32; typedef unsigned char u8;
#define LIGHTS_BUFFER_SIZE 32
#define LIGHT_POINT_GLOW 2
#define SCREEN_WIDTH 320
#define SCREEN_HEIGHT 240
typedef struct { float x,y,z; } Vec3f;
typedef struct { int x,y,z,drawGlow; } LightPoint;
typedef struct { int type; struct { LightPoint point; } params; } LightInfo;
typedef struct LightNode { LightInfo* info; struct LightNode* next; struct LightNode* prev; } LightNode;
typedef struct { LightNode* listHead; } LightContext;
typedef struct GraphicsContext { int unused; } GraphicsContext;
typedef struct { LightContext lightCtx; } PlayState;
typedef struct { int numOccupied,searchIndex; LightNode buf[32]; } LightsBuffer;
LightsBuffer sLightsBuffer;
static int worker=1, shrink=10, callbackCalls=0;
static Vec3f projected={0.25f,-0.25f,2};
static float inverseW=0.25f;
static ShipyardOverlapDepthRequest staged;
int Shipyard_OverlapIsGameWorker(void) { return worker; }
void Shipyard_OverlapStageDepth(const ShipyardOverlapDepthRequest* value) { staged=*value; }
u32 ShrinkWindow_GetCurrentVal(void) { return shrink; }
void func_8002BE04(PlayState* p,Vec3f* a,Vec3f* b,float* w) { *b=projected; *w=inverseW; }
void LightContext_InitList(PlayState* p,LightContext* c) { c->listHead=0; }
void LightContext_SetAmbientColor(LightContext* p,u8 a,u8 b,u8 c) {}
void LightContext_SetFog(LightContext* p,u8 a,u8 b,u8 c,int d,int e) {}
void LightContext_RemoveLight(PlayState* p,LightContext* c,LightNode* n);
void Lights_GlowCheckPrepare(PlayState* p) {}
void Lights_GlowCheck(PlayState* p) {}
void OTRGetPixelDepthPrepare(float x,float y) { callbackCalls++; }
uint16_t OTRGetPixelDepth(float x,float y) { return 17; }
uint16_t Environment_GetPixelDepth(int x,int y) { return OTRGetPixelDepth((float)x,(float)y); }
int D_8015FD7E=31,D_8015FD80=47;
uint16_t D_8011FB44=99;
"""
        fixture += lights[
            lights.index("static uint64_t sShipyardLightIncarnation") : lights.index(
                "void Lights_PointSetInfo"
            )
        ]
        for name in (
            "Lights_FindBufSlot",
            "Lights_FreeNode",
            "LightContext_Init",
            "LightContext_RemoveLight",
        ):
            fixture += "\n" + function(lights, name)
        fixture += lights[lights.index("void Shipyard_OverlapCaptureLights") :]
        fixture += "\n" + function(env, "Environment_GraphCallback")
        fixture += env[env.index("int Shipyard_OverlapCaptureGraphCallback") :]
        fixture += r"""
static float sampledX[40],sampledY[40]; static int prepared=0,reads=0;
static void prepare(float x,float y,void* p) { sampledX[prepared]=x;sampledY[prepared++]=y; }
static uint16_t readDepth(float x,float y,void* p) { reads++; return 65535; }
static void unknown(GraphicsContext* c,void* p) { callbackCalls++; }
int main(void) {
    PlayState play; LightInfo info; LightNode* node; LightNode* originalSlot; ShipyardOverlapDepthResult result;
    LightContext_Init(&play,&play.lightCtx); memset(&info,0,sizeof(info));
    info.type=LIGHT_POINT_GLOW; info.params.point.drawGlow=0;
    node=Lights_FindBufSlot();node->info=&info;node->next=0;node->prev=0;play.lightCtx.listHead=node;
    assert(Shipyard_OverlapCaptureGraphCallback(0,Environment_GraphCallback,&play)==1);
    staged.generation=10;
    D_8015FD7E=200;D_8015FD80=201; projected.x=20;projected.z=-1;shrink=120;
    Shipyard_OverlapSampleDepth(&staged,&result,prepare,readDepth,0);
    assert(prepared==2 && reads==2 && sampledX[0]==31 && sampledY[0]==47);
    assert(sampledX[1]==170 && sampledY[1]==112.5f);
    assert(!Shipyard_OverlapDepthReady(&result,11) && Shipyard_OverlapDepthReady(&result,12));
    Shipyard_OverlapApplyDepthResult(&result);
    assert(D_8011FB44==65535 && info.params.point.drawGlow==1);
    originalSlot=node;Lights_FreeNode(node);node=Lights_FindBufSlot();assert(node==originalSlot);
    node->info=&info;info.params.point.drawGlow=0;
    Shipyard_OverlapApplyDepthResult(&result);assert(info.params.point.drawGlow==0);
    D_8011FB44=123;LightContext_Init(&play,&play.lightCtx);
    Shipyard_OverlapApplyDepthResult(&result);assert(D_8011FB44==123);
    node=Lights_FindBufSlot();node->info=&info;node->next=0;node->prev=0;play.lightCtx.listHead=node;
    shrink=10;projected.x=0;projected.y=-20;projected.z=2;
    assert(Shipyard_OverlapCaptureGraphCallback(0,Environment_GraphCallback,&play));
    prepared=reads=0;Shipyard_OverlapSampleDepth(&staged,&result,prepare,readDepth,0);
    assert(prepared==1 && reads==1 && result.lights[0].drawGlow==0);
    projected.y=0;projected.z=1;
    assert(Shipyard_OverlapCaptureGraphCallback(0,Environment_GraphCallback,&play));
    prepared=reads=0;Shipyard_OverlapSampleDepth(&staged,&result,prepare,readDepth,0);
    assert(prepared==1 && reads==1 && result.lights[0].drawGlow==0);
    info.type=0;
    assert(Shipyard_OverlapCaptureGraphCallback(0,Environment_GraphCallback,&play));
    prepared=reads=0;Shipyard_OverlapSampleDepth(&staged,&result,prepare,readDepth,0);
    assert(prepared==1 && reads==1 && result.lightCount==0);
    worker=0;assert(!Shipyard_OverlapCaptureGraphCallback(0,Environment_GraphCallback,&play));
    Environment_GraphCallback(0,&play);assert(D_8011FB44==17 && callbackCalls==1);
    worker=1;assert(!Shipyard_OverlapCaptureGraphCallback(0,unknown,&play));assert(callbackCalls==1);
    memset(&staged,0,sizeof(staged));staged.active=1;staged.lightCount=1;
    staged.lights[0].eligible=0;prepared=reads=0;
    Shipyard_OverlapSampleDepth(&staged,&result,prepare,readDepth,0);
    assert(prepared==1 && reads==1 && result.lights[0].drawGlow==0);
    Shipyard_OverlapSampleDepth(&staged,&result,0,0,0);assert(result.sunDepth==0);
    staged.active=0;prepared=reads=0;
    Shipyard_OverlapSampleDepth(&staged,&result,prepare,readDepth,0);
    assert(result.active==0 && prepared==0 && reads==0);
    return 0;
}
"""
        with tempfile.TemporaryDirectory(
            prefix="depth-contract-", dir=ROOT / "scratch"
        ) as temporary:
            directory = Path(temporary)
            source = directory / "fixture.c"
            source.write_text(fixture, encoding="utf-8")
            includes = f'/I"{ROOT / "platform/shipyard"}" /I"{resolve(ROOT) / "sources"}"'
            command = f'call "{VCVARS}" >nul && cl /nologo /TC /W3 {includes} "{source}" /Fe:"{directory / "fixture.exe"}"'
            compiled = subprocess.run(
                'cmd /d /s /c "' + command + '"',
                cwd=directory,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run(
                [str(directory / "fixture.exe")], capture_output=True, text=True
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
