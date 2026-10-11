"""Check passive eligibility against the GUI fields that carry deferred work."""

from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GuiWorkProjectionTests(unittest.TestCase):
    def test_expiration_and_modal_queue_release_overlap(self):
        from cpp_ast import PARSER, walk
        from overlap_gui_work_projection import project

        def projected(path):
            return project(path, (ROOT / path).read_text(encoding="utf-8-sig"))

        def method(text, name):
            return next(
                node.text.decode()
                for node in walk(PARSER.parse(text.encode()).root_node)
                if node.type == "function_definition"
                and node.child_by_field_name("declarator").text.decode().startswith(name + "(")
            )

        overlay = projected("libultraship/src/ship/window/gui/GameOverlay.cpp")
        tick = next(
            node.text.decode()
            for node in walk(PARSER.parse(overlay.encode()).root_node)
            if node.type == "if_statement"
            and node.text.startswith(b"if (overlay.Type == OverlayType::NOTIFICATION && overlay.duration > 0)")
        )
        modal = projected("soh/soh/SohGui/SohModals.cpp")
        source = r"""
#include <cassert>
#include <map>
#include <string>
#include <vector>
enum class OverlayType { TEXT, IMAGE, NOTIFICATION };
struct Overlay { OverlayType Type; std::string Value; float fadeTime, duration; };
struct ImVec4 { ImVec4(float, float, float, float) {} };
class GameOverlay {
public:
    std::map<int, Overlay> mRegisteredOverlays;
    bool mNeedsCleanup = true;
    int draws = 0;
    void CleanupNotifications();
    float GetStringWidth(const char*) { return 0; }
    float GetScreenWidth() { return 1280; }
    float GetScreenHeight() { return 720; }
    void TextDraw(float, float, bool, ImVec4, const char*) { ++draws; }
    void Tick() {
        CleanupNotifications();
        float notY = 0;
        for (auto& item : mRegisteredOverlays) {
            auto& overlay = item.second;
""" + tick + r"""
        }
    }
};
std::vector<int> modals;
bool closePopup = false;
class SohModalWindow {
public:
    bool initialized = false;
    bool visible = true;
    bool IsInitialized() { return initialized; }
    bool XboxHasPendingFrameWork();
};
""" + method(overlay, "GameOverlay::CleanupNotifications") + method(
            modal, "SohModalWindow::XboxHasPendingFrameWork"
        ) + r"""
int main() {
    GameOverlay overlay;
    overlay.mRegisteredOverlays[0] = { OverlayType::NOTIFICATION, "slot 0 set", 1, 1 };
    for (int i = 0; i < 30; ++i) overlay.Tick();
    assert(overlay.draws >= 19 && overlay.draws <= 21);
    assert(overlay.mRegisteredOverlays.empty() && !overlay.mNeedsCleanup);
    overlay.mRegisteredOverlays[1] = { OverlayType::NOTIFICATION, "short", .1f, .1f };
    overlay.mRegisteredOverlays[2] = { OverlayType::NOTIFICATION, "long", 1, 1 };
    overlay.mRegisteredOverlays[3] = { OverlayType::TEXT, "persistent", 0, 0 };
    overlay.mNeedsCleanup = true;
    for (int i = 0; i < 4; ++i) overlay.Tick();
    assert(overlay.mRegisteredOverlays.count(1) == 0);
    assert(overlay.mRegisteredOverlays.count(2) == 1);
    for (int i = 0; i < 30; ++i) overlay.Tick();
    assert(overlay.mRegisteredOverlays.size() == 1 && overlay.mRegisteredOverlays.count(3));
    SohModalWindow modal;
    assert(modal.XboxHasPendingFrameWork());
    modal.initialized = true;
    assert(!modal.XboxHasPendingFrameWork());
    modals.push_back(1);
    assert(modal.XboxHasPendingFrameWork());
    modal.visible = false;
    assert(modal.XboxHasPendingFrameWork());
    modals.clear(); closePopup = true;
    assert(modal.XboxHasPendingFrameWork());
    closePopup = false;
    assert(!modal.XboxHasPendingFrameWork());
}
"""
        folder = ROOT / "scratch/overlap-gui-contract"
        folder.mkdir(exist_ok=True)
        path = folder / "contract.cpp"
        path.write_text(source)
        env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
        compiler, environment = env["host_environment"]()
        exe = folder / "contract.exe"
        env["invoke"](
            [compiler, "/nologo", "/std:c++20", "/EHsc", path,
             "/Fo:" + str(folder) + "/", "/Fe:" + str(exe)],
            folder, "build", environment,
        )
        env["invoke"]([exe], folder, "run")

    def test_window_base_checks_initialization_and_visibility(self):
        from overlap_gui_work_projection import project

        path = "libultraship/include/ship/window/gui/GuiWindow.h"
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertIn("virtual bool XboxHasPendingFrameWork()", text)
        self.assertIn("!IsInitialized() || (IsVisible() && !XboxCanDrawDuringOverlap())", text)

    def test_hidden_rumble_and_input_release_need_updates(self):
        from overlap_gui_work_projection import project

        path = "soh/soh/Enhancements/controls/SohInputEditorWindow.h"
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        for timer in (
            "mRumbleTimer",
            "mGameInputBlockTimer",
            "mMappingInputBlockTimer",
        ):
            self.assertIn(timer + " != INT32_MAX", text)

    def test_hidden_message_actions_are_pending(self):
        from overlap_gui_work_projection import project

        path = "soh/soh/Enhancements/debugger/MessageViewer.h"
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertIn(
            "mDisplayExistingMessageClicked || mDisplayCustomMessageClicked", text
        )

    def test_notification_eligibility_uses_queue_not_visible_flag(self):
        from overlap_gui_work_projection import project

        path = "soh/soh/Notification/Notification.cpp"
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertIn("!IsInitialized() || !notifications.empty()", text)

    def test_overlay_pending_draw_is_conservative(self):
        from overlap_gui_work_projection import project

        path = (
            "scratch/gui-resources-xdk/generated/include/ship/window/gui/GameOverlay.h"
        )
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertIn("!mRegisteredOverlays.empty() || mNeedsCleanup", text)

    def test_console_bindings_require_per_ready_dispatch(self):
        from overlap_gui_work_projection import project

        path = "libultraship/include/ship/window/gui/ConsoleWindow.h"
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertIn("!mBindings.empty() || !mBindingToggle.empty()", text)


if __name__ == "__main__":
    unittest.main()
