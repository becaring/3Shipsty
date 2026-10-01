"""Check passive eligibility against the GUI fields that carry deferred work."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GuiWorkProjectionTests(unittest.TestCase):
    def test_window_base_checks_initialization_and_visibility(self):
        from overlap_gui_work_projection import project

        path = "libultraship/include/ship/window/gui/GuiWindow.h"
        text = project(path, (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertIn("virtual bool XboxHasPendingFrameWork()", text)
        self.assertIn("!IsInitialized() || IsVisible()", text)

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
