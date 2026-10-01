#include "imgui_xenos.h"
#include "platform_frame.h"
#include "input/physical.h"
#include "gui_capture.h"
#include "application/gui_frame_cache.h"

namespace Fast { namespace ShipyardXenos {
void RetireExternalTexture(IDirect3DTexture9* texture);
} }

namespace {
ModernOverlap::GuiFrameCache* captureCache;
bool captureSucceeded;
bool suppressCapturedDraw;
uintptr_t capturedGameTexture;
char gameTextureMarker;

void retainGuiTexture(void*, ImTextureID texture) {
    static_cast<IDirect3DTexture9*>(texture)->AddRef();
}
void retireGuiTexture(void*, ImTextureID texture) {
    Fast::ShipyardXenos::RetireExternalTexture(static_cast<IDirect3DTexture9*>(texture));
}
}

void Shipyard_ImGuiBeginCapture(ModernOverlap::GuiFrameCache* cache, bool suppressDraw) {
    captureCache = cache;
    captureSucceeded = false;
    suppressCapturedDraw = suppressDraw;
    capturedGameTexture = 0;
}

bool Shipyard_ImGuiEndCapture() {
    captureCache = NULL;
    return captureSucceeded;
}

bool Shipyard_ImGuiCaptureDrawData(ImDrawData* data) {
    if (!captureCache) return false;
    const ModernOverlap::GuiTextureLifetime textures(NULL, retainGuiTexture, retireGuiTexture);
    captureSucceeded = captureCache->capture(*data, &gameTextureMarker, textures,
        (ImGui::GetIO().ConfigFlags & ImGuiConfigFlags_ViewportsEnable) != 0);
    if (!suppressCapturedDraw) {
        for (int i = 0; i != data->CmdListsCount; ++i) {
            ImDrawList* list = data->CmdLists[i];
            for (int j = 0; j != list->CmdBuffer.Size; ++j) {
                ImDrawCmd& cmd = list->CmdBuffer[j];
                if (cmd.TextureId == &gameTextureMarker && !cmd.UserCallback) {
                    cmd.TextureId = reinterpret_cast<ImTextureID>(capturedGameTexture);
                    if (!capturedGameTexture) cmd.ElemCount = 0;
                }
            }
        }
    }
    return suppressCapturedDraw;
}

uintptr_t Shipyard_ImGuiCaptureGameTexture(uintptr_t texture) {
    capturedGameTexture = texture;
    return captureCache ? reinterpret_cast<uintptr_t>(&gameTextureMarker) : texture;
}

void Shipyard_ImGuiDrawCache(ModernOverlap::GuiFrameCache& cache, uintptr_t texture) {
    cache.retargetGame(reinterpret_cast<ImTextureID>(texture));
    Shipyard_ImGuiRender(&cache.drawData());
}

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
