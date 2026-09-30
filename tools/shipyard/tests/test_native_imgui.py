"""Real current ImGui events with physical fixtures, plus native shader compilation."""

from pathlib import Path
import ast
import json
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from prepare_native_imgui import prepare, OUT, OWN
from platform_base import resolve as resolve_platform_base
from prepare_archives import stable


def main():
    prepare()
    folder = OUT / "host"
    folder.mkdir(exist_ok=True)
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    native = (resolve_platform_base(ROOT) / "sources/imgui/imgui_xenos.cpp").read_text()
    begin = native.index("    static const char* source =")
    end = native.index("\n    ID3DXBuffer* code =", begin)
    shader = "".join(ast.literal_eval(m[0]) for m in re.finditer(r'"(?:[^"\\]|\\.)*"', native[begin:end]))
    shaderpath = folder / "gui.hlsl"
    stable(shaderpath, shader)
    for profile, entry in [("vs_3_0", "VSMain"), ("ps_3_0", "PSMain")]:
        command = [
            str(sdk / "bin/win32/fxc.exe"),
            "/nologo",
            "/T",
            profile,
            "/E",
            entry,
            "/Fo",
            str(folder / (entry + ".bin")),
            str(shaderpath),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        stable(folder / (entry + ".log"), result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Native GUI shader compile failed " + entry)
    # Constants come from the actual XDK header. The host supplies only native
    # time and physical-device fixtures, keeping the complete platform TU body.
    defines = (sdk / "include/xbox/xinputdefs.h").read_text()
    masks = "\n".join(m[0] for m in re.finditer(r"^#define XINPUT_GAMEPAD_\w+\s+0x[0-9A-Fa-f]+", defines, re.M))
    base = resolve_platform_base(ROOT)
    platform = (base / "sources/imgui/platform_frame.cpp").read_text()
    platform = platform.replace("#ifdef _XBOX", "#if 1").replace("#include <xtl.h>", "")
    adapter = (OWN / "platform_adapter.cpp").read_text().replace('#include "imgui_xenos.h"', "")
    assert not (OWN / "platform_frame.cpp").exists()
    text = (
        """#include "imgui.h"
#include "input/physical.h"
#include "native-imgui/font_lifecycle.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
typedef uint16_t WORD;
typedef unsigned DWORD;
#define ERROR_SUCCESS 0
#define ERROR_IO_PENDING 997
#define FALSE 0
#define TRUE 1
#define VKBD_DEFAULT 0
#define VKBD_LATIN_NUMERIC 0x20
#define VKBD_LATIN_PASSWORD 0x80
struct XOVERLAPPED { unsigned status; };
static unsigned nativeStarts, nativeResult=ERROR_IO_PENDING, nativeLaunch=ERROR_IO_PENDING;
static wchar_t* nativeOutput;
unsigned XShowKeyboardUI(unsigned, unsigned, const wchar_t*, const wchar_t*, const wchar_t*, wchar_t* output, unsigned, XOVERLAPPED*) {
    ++nativeStarts;nativeOutput=output;return nativeLaunch;
}
bool XHasOverlappedIoCompleted(XOVERLAPPED*){return nativeResult!=ERROR_IO_PENDING;}
unsigned XGetOverlappedResult(XOVERLAPPED*,void*,int){return nativeResult;}
unsigned XCancelOverlapped(XOVERLAPPED*){nativeResult=1223;return 0;}

#define CHECK(c) do{if(!(c)){std::fprintf(stderr,"failed: %s line %d\\n",#c,__LINE__);throw std::runtime_error(#c);}}while(0)
static double seconds=1;
double Shipyard_Time(){return seconds;}
static unsigned physicalSlot=0,refreshes=0,presentations=0;
static ShipyardInputRawPad physicalPad={0};
void ShipyardInput_RefreshGamepadsForGui(){++refreshes;}
void ShipyardInput_BeginGamepadPresentation(){++presentations;}
bool ShipyardInput_ReadCachedGamepad(unsigned slot,ShipyardInputRawPad* out){
    if(slot==physicalSlot){*out=physicalPad;return true;}std::memset(out,0,sizeof(*out));return false;
}
"""
        + masks
        + "\n"
        + platform
        + "\n"
        + adapter
        + "\n"
        + (base / "tests/imgui_keyboard_contract.inc").read_text()
        + """
static unsigned fontRebuilds=0;
static void RebuildFonts(){
    ++fontRebuilds;unsigned char* pixels;int width,height;
    ImGui::GetIO().Fonts->GetTexDataAsRGBA32(&pixels,&width,&height);
    CHECK(pixels!=NULL && width>0 && height>0);
}
static void frame(bool visible=false){seconds+=1.0/60;Shipyard_ImGuiPlatformNewFrame(1280,720,visible);\
ImGui::NewFrame();ImGui::EndFrame();}
int main(){
    ImGui::CreateContext();ImGuiIO& io=ImGui::GetIO();io.IniFilename=NULL;
    io.ConfigFlags|=ImGuiConfigFlags_NavEnableGamepad;
    unsigned char* pixels;int w,h;io.Fonts->GetTexDataAsRGBA32(&pixels,&w,&h);
    ImFontConfig lateConfig;lateConfig.SizePixels=20.0f;
    ImFont* lateFont=io.Fonts->AddFontDefault(&lateConfig);
    CHECK(!io.Fonts->IsBuilt() && !lateFont->IsLoaded());
    Shipyard_ImGuiEnsureFontAtlas(RebuildFonts);
    CHECK(fontRebuilds==1 && io.Fonts->IsBuilt() && lateFont->IsLoaded());
    Shipyard_ImGuiEnsureFontAtlas(RebuildFonts);CHECK(fontRebuilds==1);
    Shipyard_ImGuiPlatformInit();
    struct Binding{unsigned mask;ImGuiKey key;};
    const Binding keys[]={
        {XINPUT_GAMEPAD_START,ImGuiKey_GamepadStart},{XINPUT_GAMEPAD_BACK,ImGuiKey_GamepadBack},
        {XINPUT_GAMEPAD_A,ImGuiKey_GamepadFaceDown},{XINPUT_GAMEPAD_B,ImGuiKey_GamepadFaceRight},
        {XINPUT_GAMEPAD_X,ImGuiKey_GamepadFaceLeft},{XINPUT_GAMEPAD_Y,ImGuiKey_GamepadFaceUp},
        {XINPUT_GAMEPAD_DPAD_LEFT,ImGuiKey_GamepadDpadLeft},{XINPUT_GAMEPAD_DPAD_RIGHT,ImGuiKey_GamepadDpadRight},
        {XINPUT_GAMEPAD_DPAD_UP,ImGuiKey_GamepadDpadUp},{XINPUT_GAMEPAD_DPAD_DOWN,ImGuiKey_GamepadDpadDown},
        {XINPUT_GAMEPAD_LEFT_SHOULDER,ImGuiKey_GamepadL1},{XINPUT_GAMEPAD_RIGHT_SHOULDER,ImGuiKey_GamepadR1},
        {XINPUT_GAMEPAD_LEFT_THUMB,ImGuiKey_GamepadL3},{XINPUT_GAMEPAD_RIGHT_THUMB,ImGuiKey_GamepadR3}};
    for(unsigned slot=0;slot<4;++slot){
        physicalSlot=slot;
        for(unsigned k=0;k<14;++k){
            physicalPad.buttons=keys[k].mask;frame();CHECK(ImGui::IsKeyDown(keys[k].key));
            for(unsigned j=0;j<14;++j)if(j!=k)CHECK(!ImGui::IsKeyDown(keys[j].key));
            physicalPad.buttons=0;frame();CHECK(!ImGui::IsKeyDown(keys[k].key));
        }
    }
    physicalPad.leftX=-32768;physicalPad.leftY=32767;physicalPad.leftTrigger=255;frame();
    CHECK(ImGui::IsKeyDown(ImGuiKey_GamepadLStickLeft));CHECK(ImGui::IsKeyDown(ImGuiKey_GamepadLStickUp));
    CHECK(ImGui::IsKeyDown(ImGuiKey_GamepadL2));CHECK(io.BackendFlags&ImGuiBackendFlags_HasGamepad);
    physicalSlot=4;frame();CHECK(!(io.BackendFlags&ImGuiBackendFlags_HasGamepad));
    CHECK(!ImGui::IsKeyDown(ImGuiKey_GamepadLStickLeft));CHECK(!ImGui::IsKeyDown(ImGuiKey_GamepadL2));
    physicalSlot=0;physicalPad={0};frame(true);CHECK(io.MouseDrawCursor);
    CHECK(io.MousePos.x==640 && io.MousePos.y==360);
    physicalPad.rightX=32767;frame(true);CHECK(io.MousePos.x>640);
    physicalPad.rightX=0;physicalPad.buttons=XINPUT_GAMEPAD_A;frame(true);
    CHECK(ImGui::IsMouseDown(0));CHECK(!ImGui::IsKeyDown(ImGuiKey_GamepadFaceDown));
    physicalPad.buttons=XINPUT_GAMEPAD_BACK;frame(true);
    CHECK(ImGui::IsKeyDown(ImGuiKey_GamepadBack));CHECK(!ImGui::IsMouseDown(0));
    physicalPad.buttons=XINPUT_GAMEPAD_RIGHT_THUMB;frame(true);
    CHECK(!io.MouseDrawCursor);CHECK(ImGui::IsKeyDown(ImGuiKey_GamepadR3));
    physicalPad.buttons=0;frame(true);
    physicalPad.buttons=XINPUT_GAMEPAD_RIGHT_THUMB;frame(true);CHECK(io.MouseDrawCursor);
    physicalPad.buttons=XINPUT_GAMEPAD_A;frame(false);
    CHECK(!io.MouseDrawCursor && !ImGui::IsMouseDown(0));
    frame(true);CHECK(io.MouseDrawCursor && !ImGui::IsMouseDown(0));
    physicalPad.buttons=0;frame(true);
    physicalPad.buttons=XINPUT_GAMEPAD_A;frame(true);CHECK(ImGui::IsMouseDown(0));
    physicalPad.buttons=0;frame(false);
    RunKeyboardContract();
    const int policy=io.ConfigFlags;Shipyard_ImGuiPlatformNewFrame(640,480,false);
    CHECK(io.DeltaTime==0.000001f);CHECK(io.DisplaySize.x==640 && io.DisplaySize.y==480);
    physicalPad.buttons=0;seconds+=1.0/60;
    Shipyard_ImGuiPlatformNewFrame(1280,720,true);
    ImGui::NewFrame();ImGui::Begin("Cursor draw contract");ImGui::Text("Visible UI");ImGui::End();
    Shipyard_ImGuiPlatformDrawCursor();
    CHECK(!io.MouseDrawCursor);
    ImGui::Render();
    ImDrawList* cursorList=ImGui::GetForegroundDrawList(ImGui::GetMainViewport());
    CHECK(cursorList->VtxBuffer.Size>=6);
    ImDrawData* drawData=ImGui::GetDrawData();bool cursorSubmitted=false;
    if(drawData)for(int i=0;i<drawData->CmdListsCount;\
++i)if(drawData->CmdLists[i]==cursorList)cursorSubmitted=true;
    CHECK(cursorSubmitted);
    CHECK(io.ConfigFlags==policy);Shipyard_ImGuiPlatformShutdown();CHECK(io.BackendPlatformName==NULL);
    const Shipyard::ImGuiPlatform::Services alternate={Shipyard_Time,ShipyardInput_BeginGamepadPresentation,\
"Alternate_XInput"};
    Shipyard::ImGuiPlatform::Init(alternate);
    const unsigned priorRefreshes=refreshes;
    seconds+=1.0/60;Shipyard::ImGuiPlatform::NewFrame(1280,720,false);
    CHECK(presentations==1 && refreshes==priorRefreshes);
    CHECK(std::strcmp(io.BackendPlatformName,"Alternate_XInput")==0);
    Shipyard::ImGuiPlatform::Shutdown();
    ImGui::DestroyContext();std::printf("56 real ImGui button bindings, donor cursor mode, click suppression, \
analog/disconnect and navigation ownership pass (%u refreshes)\\n",refreshes);
}
"""
    )
    stable(folder / "contract.cpp", text)
    env = runpy.run_path(str(Path(__file__).with_name("test_binary.py")))
    compiler, environment = env["host_environment"]()
    includes = [
        OUT / "generated",
        ROOT / "scratch/imgui-xdk/generated",
        ROOT / "platform/shipyard",
        resolve_platform_base(ROOT) / "sources/imgui",
        resolve_platform_base(ROOT) / "sources",
    ]
    units = [
        ROOT / "scratch/imgui-xdk/generated" / (n + ".cpp")
        for n in ("imgui", "imgui_draw", "imgui_tables", "imgui_widgets")
    ]
    command = (
        [compiler, "/nologo", "/std:c++20", "/EHsc", "/MD", "/O2"]
        + ["/I" + str(p) for p in includes]
        + [folder / "contract.cpp"]
        + units
        + ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
    )
    env["invoke"](command, folder, "build", environment)
    result = env["invoke"]([folder / "contract.exe"], folder, "run")
    stable(
        OUT / "verification.json",
        json.dumps(dict(host_output=result["stdout"], native_shader_stages=2, target_runtime_executed=False), indent=2)
        + "\n",
    )
    print(result["stdout"])


if __name__ == "__main__":
    main()
