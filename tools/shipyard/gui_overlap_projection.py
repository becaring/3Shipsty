"""Separate render-owned GUI construction from native replay at an idle handoff.

The capture hook is inactive on the sequential path. A unique image marker
allows each replay to select its current framebuffer without retargeting previews.
"""

from prepare_configuration import once

PREFLIGHT = r"""
static bool overlapF1, overlapEscape, overlapBack, overlapReset;

bool Gui::XboxHasInteractiveGui() {
    if (mNeedsConsoleVariableSave) return true;
    if (GetGameOverlay()->XboxHasPendingDraw()) return true;
    if (GetMenuOrMenubarVisible() || ImGui::GetTopMostPopupModal() != nullptr) return true;
    if (ImGui::GetIO().ConfigFlags & ImGuiConfigFlags_ViewportsEnable) return true;
    for (std::map<std::string, std::shared_ptr<GuiWindow>>::const_iterator window = mGuiWindows.begin();
         window != mGuiWindows.end(); ++window) {
        if (window->second->XboxHasPendingFrameWork()) return true;
    }
    return false;
}

bool Gui::XboxBeginOverlapDraw() {
    ModernFrameProfile::Begin(ModernFrameProfile::GuiStartFrame);
    StartFrame();
    ModernFrameProfile::End(ModernFrameProfile::GuiStartFrame);
    overlapF1 = ImGui::IsKeyPressed(TOGGLE_BTN, false);
    overlapEscape = ImGui::IsKeyPressed(ImGuiKey_Escape, false);
    overlapBack = ImGui::IsKeyPressed(TOGGLE_PAD_BTN, false);
    const bool toggle = overlapF1 || overlapEscape ||
        (overlapBack &&
         Context::GetInstance()->GetConsoleVariables()->GetInteger(CVAR_IMGUI_CONTROLLER_NAV, 0));
    overlapReset = (ImGui::IsKeyDown(ImGuiKey_LeftCtrl) || ImGui::IsKeyDown(ImGuiKey_RightCtrl)) &&
        ImGui::IsKeyPressed(ImGuiKey_R, false);
    return !XboxHasInteractiveGui() && !toggle && !overlapReset;
}

"""


def passive_methods(text):
    menu_start = text.index("void Gui::DrawMenu() {")
    menu_end = text.index("\n}\n", menu_start) + 2
    menu = text[menu_start:menu_end]
    intent_start = menu.index("    if (ImGui::IsKeyPressed(TOGGLE_BTN, false)")
    intent_end = menu.index("    if (GetMenuBar()) {", intent_start)
    intent = menu[intent_start:intent_end]
    for key, saved in (
        ("TOGGLE_BTN", "overlapF1"),
        ("ImGuiKey_Escape", "overlapEscape"),
        ("TOGGLE_PAD_BTN", "overlapBack"),
    ):
        intent = intent.replace("ImGui::IsKeyPressed(" + key + ", false)", saved)
    intent = once(
        intent,
        "(ImGui::IsKeyDown(ImGuiKey_LeftCtrl) || ImGui::IsKeyDown(ImGuiKey_RightCtrl)) &&\n"
        "        ImGui::IsKeyPressed(ImGuiKey_R, false)",
        "overlapReset",
    )
    commit = "void Gui::XboxCommitOverlapIntent() {\n" + intent + "\n}\n"
    menu = (
        menu[:intent_start].replace("Gui::DrawMenu", "Gui::XboxDrawPassiveMenu")
        + "    ImGui::End();\n}\n"
    )
    game_start = text.index("void Gui::DrawGame() {")
    game_end = text.index("\n}\n", game_start) + 2
    game = text[game_start:game_end].replace(
        "Gui::DrawGame", "Gui::XboxDrawPassiveGame"
    )
    game = once(game, "    GetGameOverlay()->Draw();\n", "")
    finish = r"""
void Gui::XboxFinishPassiveDraw() {
    XboxDrawPassiveMenu();
    CalculateGameViewport();
    auto interpreter = mInterpreter.lock();
    if (interpreter->mCurDimensions.height == 0) interpreter->mCurDimensions.height = 1;
    interpreter->mCurDimensions.aspect_ratio =
        (float)interpreter->mCurDimensions.width / (float)interpreter->mCurDimensions.height;
    XboxDrawPassiveGame();
    EndFrame();
}
"""
    return commit + menu + game + finish


def project(name, text):
    if name == "include/ship/window/gui/Gui.h":
        return once(
            text,
            "    void StartDraw();",
            "    void StartDraw();\n"
            "    bool XboxHasInteractiveGui();\n"
            "    bool XboxBeginOverlapDraw();\n"
            "    void XboxFinishPassiveDraw();\n"
            "    void XboxCommitOverlapIntent();\n"
            "    void XboxDrawPassiveMenu();\n"
            "    void XboxDrawPassiveGame();",
        )
    if name != "src/ship/window/gui/Gui.cpp":
        return text
    text = (
        '#include "application/overlap.h"\n#include "native-imgui/gui_capture.h"\n'
        + text
    )
    text = once(
        text,
        "    ImGuiRenderDrawData(ImGui::GetDrawData());",
        """    if (!Shipyard_ImGuiCaptureDrawData(ImGui::GetDrawData())) {
        ImGuiRenderDrawData(ImGui::GetDrawData());
    }""",
    )
    text = once(
        text,
        "    uintptr_t fb = Ship::Context::GetInstance()->GetWindow()->GetGfxFrameBuffer();",
        """    uintptr_t fb = Shipyard_ImGuiCaptureGameTexture(
        Ship::Context::GetInstance()->GetWindow()->GetGfxFrameBuffer());""",
    )
    text = once(
        text,
        "void Gui::EndDraw() {",
        "void Gui::EndDraw() {\n    if (Shipyard_OverlapDrawGui(0)) return;",
    )
    return once(
        text,
        "void Gui::StartDraw() {",
        PREFLIGHT + passive_methods(text) + "\nvoid Gui::StartDraw() {\n"
        "    if (Shipyard_OverlapDrawGui(1)) return;",
    )
