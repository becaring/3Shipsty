"""Execute projected GUI eligibility and capture with visible and closing Stats."""

from pathlib import Path
import runpy
import unittest

from cpp_ast import PARSER, walk
from overlap_gui_work_projection import project
from prepare_gui import transform

ROOT = Path(__file__).resolve().parents[2]


def method(text, name):
    return next(
        node.text.decode()
        for node in walk(PARSER.parse(text.encode()).root_node)
        if node.type == "function_definition"
        and node.child_by_field_name("declarator").text.decode().startswith(name + "(")
    )


class StatsOverlapTests(unittest.TestCase):
    def test_stats_draws_at_idle_handoff_without_admitting_mutable_windows(self):
        base_path = "libultraship/include/ship/window/gui/GuiWindow.h"
        stats_path = "libultraship/include/ship/window/gui/StatsWindow.h"
        soh_stats_path = "soh/soh/Enhancements/debugger/SohStatsWindow.h"
        gui_path = "src/ship/window/gui/Gui.cpp"
        base = project(base_path, (ROOT / base_path).read_text())
        stats = project(stats_path, (ROOT / stats_path).read_text())
        soh_stats = project(soh_stats_path, (ROOT / soh_stats_path).read_text())
        registration = (ROOT / "soh/soh/SohGui/SohGui.cpp").read_text()
        self.assertIn('std::make_shared<SohStatsWindow>(CVAR_WINDOW("SohStats"), "Stats##Soh"', registration)
        gui = transform(gui_path, (ROOT / "libultraship" / gui_path).read_text())
        source = r'''
#include <cassert>
#include <map>
#include <memory>
#include <string>
bool workerRunning = false;
struct GuiWindow {
    bool initialized = true, visible = false, close = false;
    unsigned draws = 0, saves = 0;
    bool IsInitialized() { return initialized; }
    bool IsVisible() { return visible; }
    void Draw() {
        assert(!workerRunning);
        if (!visible) return;
        ++draws;
        if (close) { visible = false; ++saves; }
    }
''' + method(base, "XboxCanDrawDuringOverlap") + method(base, "XboxHasPendingFrameWork") + r'''
};
struct StatsWindow : GuiWindow {
''' + method(stats, "XboxCanDrawDuringOverlap") + r'''
};
struct SohStatsWindow final : GuiWindow {
''' + method(soh_stats, "XboxCanDrawDuringOverlap") + r'''
};
const int ImGuiConfigFlags_ViewportsEnable = 1;
namespace ImGui {
    struct IO { int ConfigFlags = 0; } io;
    bool modal = false;
    void* GetTopMostPopupModal() { return modal ? &io : nullptr; }
    IO& GetIO() { return io; }
}
struct Overlay { bool pending = false; bool XboxHasPendingDraw() { return pending; } };
struct Interpreter { struct { unsigned width = 1280, height = 720; float aspect_ratio; } mCurDimensions; };
struct Gui {
    std::map<std::string, std::shared_ptr<GuiWindow>> mGuiWindows;
    std::weak_ptr<Interpreter> mInterpreter;
    bool mNeedsConsoleVariableSave = false, menu = false;
    Overlay overlay;
    unsigned captures = 0;
    Overlay* GetGameOverlay() { return &overlay; }
    bool GetMenuOrMenubarVisible() { return menu; }
    void XboxDrawPassiveMenu() {}
    void CalculateGameViewport() {}
    void XboxDrawPassiveGame() {}
    void EndFrame() { ++captures; }
    bool XboxHasInteractiveGui();
    void XboxFinishPassiveDraw();
};
''' + method(gui, "Gui::XboxHasInteractiveGui") + method(gui, "Gui::XboxFinishPassiveDraw") + r'''
int main() {
    Gui gui;
    auto interpreter = std::make_shared<Interpreter>();
    gui.mInterpreter = interpreter;
    auto stats = std::make_shared<SohStatsWindow>();
    StatsWindow libraryStats;
    libraryStats.visible = true;
    assert(!libraryStats.XboxHasPendingFrameWork());
    auto editor = std::make_shared<GuiWindow>();
    gui.mGuiWindows["Stats"] = stats;
    gui.mGuiWindows["Editor"] = editor;
    stats->visible = true;
    assert(!gui.XboxHasInteractiveGui());
    for (unsigned i = 0; i < 20; ++i) gui.XboxFinishPassiveDraw();
    assert(stats->draws == 20 && editor->draws == 0 && gui.captures == 20);
    stats->initialized = false;
    assert(gui.XboxHasInteractiveGui());
    gui.XboxFinishPassiveDraw();
    assert(stats->draws == 20);
    stats->initialized = true;
    editor->visible = true;
    assert(gui.XboxHasInteractiveGui());
    gui.XboxFinishPassiveDraw();
    assert(editor->draws == 0);
    editor->visible = false;
    gui.menu = true; assert(gui.XboxHasInteractiveGui()); gui.menu = false;
    ImGui::modal = true; assert(gui.XboxHasInteractiveGui()); ImGui::modal = false;
    gui.overlay.pending = true; assert(gui.XboxHasInteractiveGui()); gui.overlay.pending = false;
    gui.mNeedsConsoleVariableSave = true; assert(gui.XboxHasInteractiveGui());
    gui.mNeedsConsoleVariableSave = false;
    stats->close = true;
    gui.XboxFinishPassiveDraw();
    assert(!stats->visible && stats->saves == 1 && !gui.XboxHasInteractiveGui());
    unsigned prior = stats->draws;
    gui.XboxFinishPassiveDraw();
    assert(stats->draws == prior && stats->saves == 1);
}
'''
        folder = ROOT / "scratch/stats-overlap-contract"
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

    def test_stats_reports_presentations_instead_of_gui_capture_rate(self):
        name = "src/ship/window/gui/StatsWindow.cpp"
        text = transform(name, (ROOT / "libultraship" / name).read_text())
        self.assertIn("ModernFrameProfile::PresentationFps()", text)
        self.assertNotIn("ImGui::GetIO().Framerate", text)
        self.assertNotIn("ImGui::GetIO().DeltaTime", text)
        from prepare_application_windows import project as project_application

        name = "soh/soh/Enhancements/debugger/SohStatsWindow.cpp"
        text = project_application(name, (ROOT / name).read_text())
        self.assertIn("ModernFrameProfile::PresentationFps()", text)
        self.assertNotIn("ImGui::GetIO().Framerate", text)
        self.assertNotIn("ImGui::GetIO().DeltaTime", text)

    def test_selected_game_stats_header_is_projected(self):
        from prepare_application_gui import prepare

        prepare()
        header = ROOT / "scratch/application-gui-xdk/generated/soh/soh/Enhancements/debugger/SohStatsWindow.h"
        self.assertIn("XboxCanDrawDuringOverlap()", header.read_text())


if __name__ == "__main__":
    unittest.main()
