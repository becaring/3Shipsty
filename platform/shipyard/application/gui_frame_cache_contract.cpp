// Exercise owned replay geometry against the selected ImGui implementation.
#include "application/gui_frame_cache.h"
#include "imgui_internal.h"
#include <cassert>
#include <cstdio>
#include <map>

namespace {
struct Textures {
    std::map<ImTextureID, int> refs;
    unsigned retains, retires;
    Textures() : retains(0), retires(0) {}
    static void retain(void* state, ImTextureID texture) {
        Textures& self = *static_cast<Textures*>(state);
        ++self.refs[texture];
        ++self.retains;
    }
    static void retire(void* state, ImTextureID texture) {
        Textures& self = *static_cast<Textures*>(state);
        assert(self.refs[texture] == 1);
        --self.refs[texture];
        ++self.retires;
    }
};

void unknownCallback(const ImDrawList*, const ImDrawCmd*) {}

ImDrawList* makeList(ImTextureID ordinary, ImTextureID marker) {
    ImDrawList* list = IM_NEW(ImDrawList(ImGui::GetDrawListSharedData()));
    list->VtxBuffer.resize(3);
    list->VtxBuffer[0].pos = ImVec2(14.0f, 27.0f);
    list->IdxBuffer.resize(3);
    list->IdxBuffer[0] = 2;
    ImDrawCmd cmd;
    cmd.ClipRect = ImVec4(0, 0, 1280, 720);
    cmd.ElemCount = 3;
    cmd.TextureId = ordinary;
    list->CmdBuffer.push_back(cmd);
    cmd.TextureId = marker;
    list->CmdBuffer.push_back(cmd);
    cmd.TextureId = ordinary;
    list->CmdBuffer.push_back(cmd);
    return list;
}

ImDrawData makeData(ImDrawList* list) {
    ImDrawData data;
    data.Valid = true;
    data.DisplayPos = ImVec2(3, 4);
    data.DisplaySize = ImVec2(1280, 720);
    data.FramebufferScale = ImVec2(2, 2);
    data.CmdLists.push_back(list);
    data.CmdListsCount = 1;
    data.TotalVtxCount = list->VtxBuffer.Size;
    data.TotalIdxCount = list->IdxBuffer.Size;
    return data;
}
}

int main() {
    ImGui::CreateContext();
    ImTextureID const ordinary = reinterpret_cast<ImTextureID>(0x1000);
    ImTextureID const marker = reinterpret_cast<ImTextureID>(0x2000);
    ImTextureID const nextGame = reinterpret_cast<ImTextureID>(0x3000);
    Textures textures;
    ModernOverlap::GuiTextureLifetime lifetime(&textures, Textures::retain, Textures::retire);
    ModernOverlap::GuiFrameCache cache;
    ImDrawList* source = makeList(ordinary, marker);
    ImDrawData data = makeData(source);
    assert(cache.capture(data, marker, lifetime));
    assert(textures.retains == 1 && textures.refs[ordinary] == 1);
    source->VtxBuffer[0].pos = ImVec2(999, 999);
    source->CmdBuffer[0].ElemCount = 0;
    source->IdxBuffer[0] = 0;
    IM_DELETE(source);
    data.Clear();
    const ImDrawData& owned = cache.drawData();
    assert(owned.Valid && owned.CmdListsCount == 1 && owned.TotalVtxCount == 3);
    assert(owned.DisplayPos.x == 3 && owned.FramebufferScale.x == 2);
    assert(owned.CmdLists[0]->VtxBuffer[0].pos.x == 14);
    assert(owned.CmdLists[0]->IdxBuffer[0] == 2);
    assert(owned.CmdLists[0]->CmdBuffer[0].ElemCount == 3);

    // An ordinary preview of the same texture must never become a game slot.
    cache.retargetGame(ordinary);
    assert(textures.retains == 1);
    cache.retargetGame(nextGame);
    assert(textures.retains == 2 && textures.refs[nextGame] == 1);
    assert(owned.CmdLists[0]->CmdBuffer[0].TextureId == ordinary);
    assert(owned.CmdLists[0]->CmdBuffer[1].TextureId == nextGame);
    assert(owned.CmdLists[0]->CmdBuffer[2].TextureId == ordinary);
    cache.retargetGame(NULL);
    assert(owned.CmdLists[0]->CmdBuffer[1].ElemCount == 0);
    assert(owned.CmdLists[0]->CmdBuffer[0].ElemCount == 3);
    cache.retargetGame(nextGame);
    assert(owned.CmdLists[0]->CmdBuffer[1].ElemCount == 3);
    cache.reset();
    assert(textures.retires == 2 && !cache.drawData().Valid);

    source = makeList(ordinary, marker);
    data = makeData(source);
    source->CmdBuffer[0].UserCallback = unknownCallback;
    assert(!cache.capture(data, marker, lifetime));
    assert(textures.retains == 2 && !cache.drawData().Valid);
    source->CmdBuffer[0].UserCallback = ImDrawCallback_ResetRenderState;
    assert(cache.capture(data, marker, lifetime));
    cache.reset();
    source->CmdBuffer[0].UserCallback = NULL;
    assert(!cache.capture(data, marker, lifetime, true));
    assert(!cache.capture(data, NULL, lifetime));
    data.Valid = false;
    assert(!cache.capture(data, marker, lifetime));
    IM_DELETE(source);
    assert(textures.retains == textures.retires);
    ImGui::DestroyContext();
    std::puts("GUI clone ownership, texture retirement, retargeting and callback fallback passed");
}
