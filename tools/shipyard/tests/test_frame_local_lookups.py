"""Actual source snippets keep per-call state and branch arguments unchanged."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment
from xbox360_platform.gui_mouse_capture import transform
from prepare_interpolation import reuse_child_lookup


class FrameLocalLookupTests(unittest.TestCase):
    def compile_run(self, code):
        compiler, env = host_environment()
        with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as temp:
            folder = Path(temp); source = folder / 'contract.cpp'; exe = folder / 'contract.exe'
            source.write_text(code)
            result = subprocess.run([str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD',
                                     str(source), '/Fe:' + str(exe)],
                                    cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_mouse_capture_pass(self):
        original = (ROOT / 'libultraship/src/ship/window/gui/Gui.cpp').read_text()
        for projected, text in [(False, original), (True, transform(original))]:
            start = text.index('void Gui::HandleMouseCapture() {')
            body = text[start:text.index('\n}', start) + 2]
            code = r'''
#include <vector>
#include <stdexcept>
using ImGuiID=unsigned;using ImGuiWindowFlags=unsigned;
const unsigned ImGuiWindowFlags_NoMouseInputs=4;
struct ImGuiWindow { unsigned Flags; };
struct Entry { unsigned key;void* val_p; };
struct State { struct { std::vector<Entry> Data; } WindowsById; } state;
namespace ImGui { State* GetCurrentContext(){return &state;} }
int mainReads=0,overlayReads=0,captureReads=0;bool capture=false;
struct Overlay { unsigned GetID(){++overlayReads;return 2;} } overlay;
struct Window { bool IsMouseCaptured(){++captureReads;return capture;} } window;
struct Context { static Context* GetInstance(){static Context c;return &c;}
Window* GetWindow(){return &window;} };
struct Gui { unsigned GetMainGameWindowID(){++mainReads;return 1;}
Overlay* GetGameOverlay(){return &overlay;}void HandleMouseCapture(); };
''' + body + r'''
void require(bool v){if(!v)throw std::runtime_error("mouse pass mismatch");}
int main(){Gui gui;ImGuiWindow windows[]={{7},{7},{3},{11}};
state.WindowsById.Data={{1,&windows[0]},{2,&windows[1]},{3,&windows[2]},{4,&windows[3]}};
capture=true;gui.HandleMouseCapture();
require(windows[0].Flags==7&&windows[1].Flags==7&&windows[2].Flags==7&&windows[3].Flags==15);
require(mainReads==EXPECTED_MAIN&&overlayReads==EXPECTED_OVERLAY&&captureReads==EXPECTED_CAPTURE);
ImGuiWindow added={15};state.WindowsById.Data.push_back({5,&added});capture=false;
gui.HandleMouseCapture();
require(windows[0].Flags==7&&windows[1].Flags==7&&windows[2].Flags==3&&windows[3].Flags==11&&added.Flags==11);
state.WindowsById.Data.clear();mainReads=overlayReads=captureReads=0;gui.HandleMouseCapture();
require(mainReads==0&&overlayReads==0&&captureReads==0);
state.WindowsById.Data={{1,&windows[0]}};gui.HandleMouseCapture();
require(mainReads==1&&overlayReads==0&&captureReads==0);return 0;}
'''
            expected = (1, 1, 1) if projected else (4, 3, 2)
            for name, value in zip(('MAIN', 'OVERLAY', 'CAPTURE'), expected):
                code = code.replace('EXPECTED_' + name, str(value))
            self.compile_run(code)

    def test_actual_interpolation_child_branch(self):
        original = (ROOT / 'soh/soh/frame_interpolation.cpp').read_text()
        for projected, text in [(False, original), (True, reuse_child_lookup(original))]:
            start = text.index('            if (item.first == Op::OpenChild) {')
            end = text.index('            if (auto it = old_path->ops.find', start)
            branch = text[start:end]
            code = r'''
#include <map>
#include <vector>
#include <stdexcept>
struct Path;
struct Children:std::map<int,std::vector<Path>> {
int finds=0;iterator find(int key){++finds;return std::map<int,std::vector<Path>>::find(key);}
};
struct Path {Children children;};
enum class Op {OpenChild};
struct Data {struct {int key;size_t idx;} open_child;};
struct Dispatch {
Path* oldArgument=nullptr;Path* newArgument=nullptr;
void interpolate_branch(Path* oldPath,Path* newPath){oldArgument=oldPath;newArgument=newPath;}
void run(Path* old_path,Path* new_path,size_t index){
std::pair<Op,int> item={Op::OpenChild,0};Data new_op={{7,index}};
for(int once=0;once<1;++once){
''' + branch + r'''
}}};
void require(bool v){if(!v)throw std::runtime_error("interpolation branch mismatch");}
int main(){Path oldPath,newPath;newPath.children[7].resize(2);Dispatch d;
d.run(&oldPath,&newPath,0);
require(d.oldArgument==&newPath.children[7][0]&&d.newArgument==d.oldArgument);
require(newPath.children.finds==UNMATCHED_LOOKUPS);
oldPath.children[7].resize(1);newPath.children.finds=0;d.run(&oldPath,&newPath,0);
require(d.oldArgument==&oldPath.children[7][0]&&d.newArgument==&newPath.children[7][0]);
require(newPath.children.finds==1);
newPath.children.finds=0;d.run(&oldPath,&newPath,1);
require(d.oldArgument==&newPath.children[7][1]&&d.newArgument==d.oldArgument);
require(newPath.children.finds==UNMATCHED_LOOKUPS);
d.run(&newPath,&newPath,0);require(d.oldArgument==d.newArgument);return 0;}
'''
            self.compile_run(code.replace('UNMATCHED_LOOKUPS', '1' if projected else '2'))
