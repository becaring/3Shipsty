"""Exercise the Input Viewer's real flags with ImGui dragging and ini reload."""
from pathlib import Path
import runpy
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))

def main():
    source = (ROOT / 'soh/soh/Enhancements/controls/InputViewer.cpp').read_text()
    if '--upstream' not in sys.argv:
        from prepare_application_extras import project
        source = project('soh/soh/Enhancements/controls/InputViewer.cpp', source)
        from prepare_gui import transform
        gui = transform('src/ship/window/gui/Gui.cpp',
                        (ROOT/'libultraship/src/ship/window/gui/Gui.cpp').read_text(encoding='utf-8-sig'))
        assert 'GetPathRelativeToAppDirectory("config/imgui.ini")' in gui
        assert 'mImGuiIo->IniFilename = mImGuiIniPath.c_str();' in gui
    assert 'ImGuiCond_FirstUseEver' in source
    start = source.index('        ImGuiWindowFlags windowFlags =')
    end = source.index('        if (pads != nullptr', start)
    flags = source[start:end]
    begin = source.index('        if (pads != nullptr', end)
    begin = source.index('{', begin) + 1
    behavior = source[begin:source.index('            ImGui::SetCursorPos', begin)]
    behavior = behavior.replace('Ship::Context::GetInstance()->GetWindow()->GetGui()->GetMenuOrMenubarVisible()', 'menu')
    text = r'''
#include "imgui.h"
#include "imgui_internal.h"
#include <cassert>
#include <string>
#include <cstdio>
static bool dragging=true;
#define CVAR_INPUT_VIEWER(x) x
static int CVarGetInteger(const char*, int) { return dragging; }
static void frame(bool menu=false) {
    ImGui::NewFrame();
    if(menu) {
        ImGui::SetNextWindowPos(ImVec2(50,50));
        ImGui::SetNextWindowSize(ImVec2(600,500));
        ImGui::Begin("Menu"); ImGui::End();
    }
    ImGui::SetNextWindowPos(ImVec2(100,100),ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(200,100));
''' + flags + r'''
    ImGui::Begin("Input Viewer",NULL,windowFlags);
''' + behavior + r'''
    ImGui::TextUnformatted("Controller buttons");
    ImGui::End();
    ImGui::Render();
}
int main() {
    ImGui::CreateContext(); auto& io=ImGui::GetIO();
    io.IniFilename=NULL; io.DisplaySize=ImVec2(1280,720); io.DeltaTime=1.0f/60;
    unsigned char* p; int w,h; io.Fonts->GetTexDataAsRGBA32(&p,&w,&h);
    frame(); frame(); frame(true); frame(true);
    io.AddMousePosEvent(150,170); frame(true);
    assert(ImGui::GetCurrentContext()->HoveredWindow==ImGui::FindWindowByName("Input Viewer"));
    assert(ImGui::GetCurrentContext()->NavWindow==ImGui::FindWindowByName("Menu"));
    io.AddMouseButtonEvent(0,true); frame(true);
    io.AddMousePosEvent(190,200); frame(true);
    io.AddMouseButtonEvent(0,false); frame(true);
    ImVec2 moved=ImGui::FindWindowByName("Input Viewer")->Pos;
    assert(moved.x>100 && moved.y>100);
    dragging=false;
    io.AddMousePosEvent(moved.x+50,moved.y+70); frame(true);
    io.AddMouseButtonEvent(0,true); frame(true);
    io.AddMousePosEvent(moved.x+100,moved.y+90); frame(true);
    io.AddMouseButtonEvent(0,false); frame(true);
    assert(ImGui::FindWindowByName("Input Viewer")->Pos.x==moved.x);
    ImGui::SaveIniSettingsToDisk("viewer.ini");
    ImGui::DestroyContext(); ImGui::CreateContext();
    auto& fresh=ImGui::GetIO();fresh.IniFilename=NULL;fresh.DisplaySize=ImVec2(1280,720);
    fresh.Fonts->GetTexDataAsRGBA32(&p,&w,&h);
    ImGui::LoadIniSettingsFromDisk("viewer.ini");frame();
    assert(ImGui::FindWindowByName("Input Viewer")->Pos.x==moved.x);
    assert(ImGui::FindWindowByName("Input Viewer")->Pos.y==moved.y);
    ImGui::DestroyContext();puts("Viewer drag, drag lock, and ini reload passed");
}
'''
    folder=ROOT/'scratch/input-viewer-test';folder.mkdir(exist_ok=True)
    (folder/'contract.cpp').write_text(text)
    compiler,env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    imgui=ROOT/'scratch/imgui-xdk/original'
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/I'+str(imgui),str(folder/'contract.cpp')]
    command += [str(imgui/(name+'.cpp')) for name in ('imgui','imgui_draw','imgui_widgets','imgui_tables')]
    command += ['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
    (folder/'build.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,folder/'build.log'
    result=subprocess.run([str(folder/'contract.exe')],cwd=folder,capture_output=True,text=True)
    (folder/'run.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,(result.returncode,result.stderr)
    print(result.stdout.strip())

if __name__=='__main__':main()
