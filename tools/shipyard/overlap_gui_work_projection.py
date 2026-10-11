"""Keep mutable GUI work on the original per-ready-frame path.

Empty notifications allow passive composition. Hidden hotkeys, rumble and
queued message actions keep their update cadence until that work finishes.
"""

from cpp_ast import PARSER, walk
from prepare_configuration import once


def public_method(text, name, code):
    raw = text.encode()
    classes = [
        node
        for node in walk(PARSER.parse(raw).root_node)
        if node.type == "class_specifier"
        and node.child_by_field_name("name") is not None
        and node.child_by_field_name("name").text.decode() == name
    ]
    if len(classes) != 1:
        raise ValueError("Expected one GUI class: " + name)
    body = classes[0].child_by_field_name("body")
    access = [
        node
        for node in body.named_children
        if node.type == "access_specifier" and node.text.startswith(b"public")
    ]
    if not access:
        raise ValueError("GUI class has no public section: " + name)
    offset = raw.find(b":", access[0].start_byte, access[0].end_byte + 2) + 1
    if offset == 0:
        raise ValueError("GUI public section has no colon: " + name)
    return (raw[:offset] + ("\n    " + code).encode() + raw[offset:]).decode()


def project(name, text):
    name = name.replace("\\", "/")
    if name.endswith("/ship/window/gui/GuiWindow.h"):
        return public_method(
            text,
            "GuiWindow",
            """virtual bool XboxCanDrawDuringOverlap() { return false; }
    virtual bool XboxHasPendingFrameWork() {
        return !IsInitialized() || (IsVisible() && !XboxCanDrawDuringOverlap());
    }""",
        )
    if name.endswith("/ship/window/gui/StatsWindow.h"):
        return public_method(
            text, "StatsWindow", "bool XboxCanDrawDuringOverlap() override { return true; }"
        )
    if name.endswith("/Enhancements/debugger/SohStatsWindow.h"):
        return public_method(
            text, "SohStatsWindow", "bool XboxCanDrawDuringOverlap() override { return true; }"
        )
    if name.endswith("/ship/window/gui/GameOverlay.h"):
        return public_method(
            text,
            "GameOverlay",
            """bool XboxHasPendingDraw() const {
        return !mRegisteredOverlays.empty() || mNeedsCleanup;
    }""",
        )
    if name.endswith("/ship/window/gui/GameOverlay.cpp"):
        return once(
            text,
            "            overlay.duration -= .05f;",
            """            overlay.duration -= .05f;
            if (overlay.duration <= 0.0f) mNeedsCleanup = true;""",
        )
    if name.endswith("/SohGui/SohModals.h"):
        return public_method(text, "SohModalWindow", "bool XboxHasPendingFrameWork() override;")
    if name.endswith("/SohGui/SohModals.cpp"):
        return (
            text
            + """
bool SohModalWindow::XboxHasPendingFrameWork() {
    return !IsInitialized() || !modals.empty() || closePopup;
}
"""
        )
    if name.endswith("/ship/window/gui/ConsoleWindow.h"):
        return public_method(
            text,
            "ConsoleWindow",
            """bool XboxHasPendingFrameWork() override {
        return !IsInitialized() || IsVisible() || !mBindings.empty() || !mBindingToggle.empty();
    }""",
        )
    if name.endswith("/Notification/Notification.h"):
        return public_method(text, "Window", "bool XboxHasPendingFrameWork() override;")
    if name.endswith("/Notification/Notification.cpp"):
        return (
            text
            + """
namespace Notification {
bool Window::XboxHasPendingFrameWork() {
    return !IsInitialized() || !notifications.empty();
}
}
"""
        )
    if name.endswith("/Enhancements/controls/SohInputEditorWindow.h"):
        return public_method(
            text,
            "SohInputEditorWindow",
            """bool XboxHasPendingFrameWork() override {
        return !IsInitialized() || IsVisible() || mRumbleTimer != INT32_MAX ||
               mGameInputBlockTimer != INT32_MAX || mMappingInputBlockTimer != INT32_MAX;
    }""",
        )
    if name.endswith("/Enhancements/debugger/MessageViewer.h"):
        return public_method(
            text,
            "MessageViewer",
            """bool XboxHasPendingFrameWork() override {
        return !IsInitialized() || IsVisible() ||
               mDisplayExistingMessageClicked || mDisplayCustomMessageClicked;
    }""",
        )
    if name.endswith("/Enhancements/TimeDisplay/TimeDisplay.h"):
        return public_method(
            text, "TimeDisplayWindow", "bool XboxHasPendingFrameWork() override;"
        )
    if name.endswith("/Enhancements/TimeDisplay/TimeDisplay.cpp"):
        return (
            text
            + """
bool TimeDisplayWindow::XboxHasPendingFrameWork() {
    return !IsInitialized() || IsVisible() || CVarGetInteger(CVAR_WINDOW("TimeDisplayEnabled"), 0) != 0;
}
"""
        )
    return text
