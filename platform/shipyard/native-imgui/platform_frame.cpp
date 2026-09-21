#include "imgui_xenos.h"
#include "input/physical.h"
#include <algorithm>
namespace {
double lastFrame;
#include "gamepad_bindings.inc"
}
void Shipyard_ImGuiPlatformInit(){
    ImGui::GetIO().BackendPlatformName="Shipyard_XInput";
    lastFrame=Shipyard_Time();
}
void Shipyard_ImGuiPlatformShutdown(){
    ImGuiIO& io=ImGui::GetIO();
    io.ClearInputKeys();
    io.BackendFlags&=~ImGuiBackendFlags_HasGamepad;
    io.BackendPlatformName=NULL;
}
void Shipyard_ImGuiPlatformNewFrame(unsigned width,unsigned height){
    ImGuiIO& io=ImGui::GetIO();
    const double now=Shipyard_Time();
    io.DeltaTime=static_cast<float>(std::max(.000001,now-lastFrame));lastFrame=now;
    io.DisplaySize=ImVec2(static_cast<float>(width),static_cast<float>(height));
    io.DisplayFramebufferScale=ImVec2(1,1);
    ShipyardInput_RefreshGamepadsForGui();
    ShipyardInputRawPad pad={0};
    bool connected=false;
    for(unsigned slot=0;slot<4;++slot){
        if(ShipyardInput_ReadCachedGamepad(slot,&pad)){connected=true;break;}
    }
    if(connected)io.BackendFlags|=ImGuiBackendFlags_HasGamepad;
    else io.BackendFlags&=~ImGuiBackendFlags_HasGamepad;
    // Current Gui owns enabling/blocking navigation and input editor capture.
    // Back is supplied even when navigation is disabled, for the real menu.
    BindGamepad(io,pad);
}
