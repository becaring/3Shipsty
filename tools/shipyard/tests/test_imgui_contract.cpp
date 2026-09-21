#include "imgui.h"
#include <cstdio>
#include <stdint.h>

static uint64_t hash = 1469598103934665603ULL;
static void bytes(const void* data, size_t size) {
    const unsigned char* p = static_cast<const unsigned char*>(data);
    for (size_t i = 0; i < size; ++i) { hash ^= p[i]; hash *= 1099511628211ULL; }
}

int main() {
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = NULL; io.LogFilename = NULL;
    io.DisplaySize = ImVec2(1280, 720);
    io.DeltaTime = 1.0f / 60;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad | ImGuiConfigFlags_DockingEnable;
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    unsigned char* pixels; int width, height;
    io.Fonts->GetTexDataAsRGBA32(&pixels, &width, &height);
    io.Fonts->SetTexID(reinterpret_cast<ImTextureID>(static_cast<uintptr_t>(1)));
    bytes(pixels, static_cast<size_t>(width) * height * 4);
    bool enabled = true; float amount = 0.375f;
    for (int frame = 0; frame < 8; ++frame) {
        io.AddMousePosEvent(100.0f + frame * 9, 110.0f);
        io.AddKeyEvent(ImGuiKey_GamepadFaceDown, frame == 3);
        ImGui::NewFrame();
        ImGui::SetNextWindowPos(ImVec2(20, 20), ImGuiCond_Always);
        ImGui::SetNextWindowSize(ImVec2(460, 400), ImGuiCond_Always);
        ImGui::Begin("Dependency contract", NULL, ImGuiWindowFlags_MenuBar);
        if (ImGui::BeginMenuBar()) {
            if (ImGui::BeginMenu("Options")) { ImGui::MenuItem("Enabled", NULL, &enabled); ImGui::EndMenu(); }
            ImGui::EndMenuBar();
        }
        ImGui::Text("Current ImGui %s frame %d", IMGUI_VERSION, frame);
        ImGui::Checkbox("Enabled", &enabled);
        ImGui::SliderFloat("Value", &amount, 0, 1);
        if (ImGui::BeginTable("table", 2, ImGuiTableFlags_Borders)) {
            for (int row = 0; row < 5; ++row) {
                ImGui::TableNextRow();
                ImGui::TableNextColumn(); ImGui::Text("Row %d", row);
                ImGui::TableNextColumn(); ImGui::Text("%0.3f", row * 0.25f);
            }
            ImGui::EndTable();
        }
        ImGui::End();
        ImGui::ShowDemoWindow();
        ImGui::Render();
        ImDrawData* data = ImGui::GetDrawData();
        if (!data || data->TotalVtxCount <= 0 || data->TotalIdxCount <= 0) return 2;
        for (int i = 0; i < data->CmdListsCount; ++i) {
            const ImDrawList* list = data->CmdLists[i];
            bytes(list->VtxBuffer.Data, list->VtxBuffer.Size * sizeof(ImDrawVert));
            bytes(list->IdxBuffer.Data, list->IdxBuffer.Size * sizeof(ImDrawIdx));
            for (int j = 0; j < list->CmdBuffer.Size; ++j) {
                const ImDrawCmd& cmd = list->CmdBuffer[j];
                bytes(&cmd.ClipRect, sizeof(cmd.ClipRect));
                bytes(&cmd.ElemCount, sizeof(cmd.ElemCount));
                bytes(&cmd.VtxOffset, sizeof(cmd.VtxOffset));
                bytes(&cmd.IdxOffset, sizeof(cmd.IdxOffset));
            }
        }
        std::printf("%d %d %d %llu\n", frame, data->TotalVtxCount, data->TotalIdxCount, hash);
    }
    ImGui::DestroyContext();
    return 0;
}
