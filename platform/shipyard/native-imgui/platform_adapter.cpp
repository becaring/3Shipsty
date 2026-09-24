#include "imgui_xenos.h"
#include "platform_frame.h"
#include "input/physical.h"

#ifdef _XBOX
IDirect3DDevice9* Shipyard_ImGuiDevice(){return Fast::xenos_device;}
void Shipyard_ImGuiBeginNativeDraw(){Fast::BeginNativeGuiDraw();}
void Shipyard_ImGuiInvalidateNativeState(){Fast::InvalidateNativeGuiState();}
void Shipyard_ImGuiLogShader(const char* message){Shipyard_Log("ImGui shader: %s",message);}
__declspec(noreturn) void Shipyard_ImGuiFatal(const char* operation,HRESULT result){Shipyard_Fatal(operation,result);}
#endif

void Shipyard_ImGuiPlatformInit(){
    const Shipyard::ImGuiPlatform::Services services={Shipyard_Time,ShipyardInput_RefreshGamepadsForGui,"Shipyard_XInput"};
    Shipyard::ImGuiPlatform::Init(services);
}
void Shipyard_ImGuiPlatformShutdown(){Shipyard::ImGuiPlatform::Shutdown();}
void Shipyard_ImGuiPlatformNewFrame(unsigned width,unsigned height,bool menuVisible){
    Shipyard::ImGuiPlatform::NewFrame(width,height,menuVisible);
}
void Shipyard_ImGuiPlatformDrawCursor(){Shipyard::ImGuiPlatform::DrawCursor();}
