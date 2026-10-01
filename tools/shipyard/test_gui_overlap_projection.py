"""Check GUI handoff hooks in the full selected source projection."""

import unittest
from dependency_sources import ROOT
from prepare_gui import transform


class GuiOverlapProjectionTests(unittest.TestCase):
    def test_full_source_has_opt_in_capture_and_unique_game_image_hook(self):
        name = "src/ship/window/gui/Gui.cpp"
        source = transform(
            name, (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        )
        self.assertIn(
            "if (!Shipyard_ImGuiCaptureDrawData(ImGui::GetDrawData())) {", source
        )
        self.assertEqual(source.count("ImGuiRenderDrawData(ImGui::GetDrawData());"), 1)
        self.assertEqual(source.count("Shipyard_ImGuiCaptureGameTexture("), 2)
        self.assertLess(
            source.index("ImGui::Render();"),
            source.index("Shipyard_ImGuiCaptureDrawData("),
        )
        self.assertIn(
            "Ship::Context::GetInstance()->GetWindow()->GetGfxFrameBuffer());", source
        )

    def test_preflight_checks_gui_intent_before_any_window_update(self):
        name = "src/ship/window/gui/Gui.cpp"
        source = transform(
            name, (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        )
        start = source.index("bool Gui::XboxBeginOverlapDraw()")
        end = source.index("void Gui::XboxCommitOverlapIntent()", start)
        preflight = source[start:end]
        self.assertIn("StartFrame();", preflight)
        self.assertIn("ImGui::IsKeyPressed(TOGGLE_BTN, false)", preflight)
        self.assertIn("ImGui::IsKeyPressed(ImGuiKey_R, false)", preflight)
        self.assertNotIn("DrawMenu();", preflight)
        self.assertNotIn("->Update()", preflight)
        self.assertNotIn("ImGuiKey_GamepadFaceDown", preflight)

    def test_passive_composition_preserves_layout_without_game_callbacks(self):
        name = "src/ship/window/gui/Gui.cpp"
        source = transform(
            name, (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        )
        start = source.index("void Gui::XboxDrawPassiveMenu()")
        end = source.index("void Gui::StartDraw()", start)
        passive = source[start:end]
        self.assertIn("ImGui::DockSpace(", passive)
        self.assertIn("CalculateGameViewport();", passive)
        self.assertIn("Shipyard_ImGuiCaptureGameTexture(", passive)
        self.assertNotIn("->Update()", passive)
        self.assertNotIn("GetGameOverlay()->Draw()", passive)
        self.assertNotIn("CheckSaveCvars()", passive)
        self.assertIn("void Gui::XboxCommitOverlapIntent()", source)


if __name__ == "__main__":
    unittest.main()
