#pragma once

#include "imgui.h"

// ImGui invalidates the atlas whenever the application adds a font. Renderer
// backends must rebuild it before the next ImGui::NewFrame().
inline void Shipyard_ImGuiEnsureFontAtlas(void (*rebuild)()) {
    if (!ImGui::GetIO().Fonts->IsBuilt()) {
        rebuild();
    }
}
