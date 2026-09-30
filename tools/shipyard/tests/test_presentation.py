"""Quantized presentation fractions and preservation of the real draw path."""

from pathlib import Path
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from prepare_presentation import prepare, OUT, OWN, PLATFORM_BASE
from prepare_archives import stable
from cpp_ast import PARSER, walk


def main():
    prepare()
    folder = OUT / "host"
    folder.mkdir(exist_ok=True)
    original = (ROOT / "libultraship/src/fast/Fast3dWindow.cpp").read_text()
    projected = (OUT / "generated/src/fast/Fast3dWindow.cpp").read_text()
    begin = "bool Fast3dWindow::DrawAndRunGraphicsCommands("

    # Compare the application path after removing only its profiler observations.
    def draw(text):
        return text[text.index(begin) : text.index("\nvoid Fast3dWindow::HandleEvents()", text.index(begin))]

    observed = draw(projected).encode()
    edits = []
    for node in walk(PARSER.parse(observed).root_node):
        if node.type == "if_statement" and b"ModernFrameProfile::CaptureTrianglePipeline()" in (
            node.child_by_field_name("condition").text
        ):
            edits.append((node.start_byte, node.end_byte))
        elif node.type == "expression_statement" and node.text.startswith(b"ModernFrameProfile::"):
            if not any(start <= node.start_byte < end for start, end in edits):
                edits.append((node.start_byte, node.end_byte))
    for start, end in sorted(edits, reverse=True):
        observed = observed[:start] + observed[end:]
    observed = observed.decode()
    assert observed.count("const bool ready = wnd->IsFrameReady();") == 1
    observed = observed.replace("const bool ready = wnd->IsFrameReady();", "")
    observed = observed.replace("if (!ready)", "if (!wnd->IsFrameReady())")
    normalize = lambda text: "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    assert normalize(draw(original)) == normalize(observed), "GUI/interpreter draw ordering changed"
    manifest = (OUT / "manifest.json").read_bytes()
    prepare()
    assert manifest == (OUT / "manifest.json").read_bytes(), "Nondeterministic generation"
    text = """#include "window_xenos.h"
#include <type_traits>
#include <cstdio>
#include <stdexcept>
#define CHECK(c) do{if(!(c))throw std::runtime_error(#c);}while(0)
static_assert(!std::is_abstract<Fast::GfxWindowBackendXenos>::value,"missing current window method");
int main(){
    const unsigned refresh[]={24,30,50,60,75,120,144};
    unsigned calls=0;
    for(unsigned h=0;h<7;++h)for(unsigned fps=1;fps<=240;++fps){
        Shipyard::PresentationPacing p;p.SetRefresh(refresh[h]);p.SetRate(fps);
        unsigned intervals=0,accepted=0;
        for(unsigned frame=0;frame<fps*10;++frame){
            p.SetRate(fps); // Application can set the same target every update.
            unsigned value=p.Next();intervals+=value;accepted+=value!=0;++calls;
            CHECK(value==refresh[h]/fps || value==refresh[h]/fps+1);
        }
        CHECK(intervals==refresh[h]*10);
        CHECK(accepted==(fps<refresh[h]?fps:refresh[h])*10);
    }
    Shipyard::PresentationPacing p;
    p.SetRate(120);CHECK(p.Next()==0);p.SetRate(60);CHECK(p.Next()==1);
    p.SetRate(120);CHECK(p.Next()==0);p.SetRefresh(120);CHECK(p.Next()==1);
    p.SetRate(0xffffffffu);p.SetRefresh(0xffffffffu);CHECK(p.Next()==1);CHECK(p.Next()==1);
    bool failed=false;try{p.SetRate(0);}catch(const std::invalid_argument&){failed=true;}CHECK(failed);
    failed=false;try{p.SetRefresh(0);}catch(const std::invalid_argument&){failed=true;}CHECK(failed);
    std::printf("%u pacing steps pass, including repeated targets, rate changes and overflow boundary; current window interface is concrete\\n",calls);
}
"""
    stable(folder / "contract.cpp", text)
    # The host checks interface completeness, so GPU pointers need declarations only.
    stable(folder / "xtl.h", "#pragma once\n#include <Windows.h>\nstruct IDirect3DDevice9;\n")
    env = runpy.run_path(str(Path(__file__).with_name("test_binary.py")))
    compiler, environment = env["host_environment"]()
    flags = ["/nologo", "/std:c++20", "/EHsc", "/MD", "/DNOMINMAX"] + [
        "/I" + str(p)
        for p in [
            folder,
            PLATFORM_BASE / "sources",
            OWN,
            OUT / "generated/include",
            ROOT / "scratch/fast3d-xdk/generated/include",
        ]
    ]
    env["invoke"](
        [compiler]
        + flags
        + [folder / "contract.cpp", "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")],
        folder,
        "build",
        environment,
    )
    result = env["invoke"]([folder / "contract.exe"], folder, "run")
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host_output=result["stdout"],
                draw_path_unchanged=True,
                deterministic=True,
                target_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(result["stdout"])


if __name__ == "__main__":
    main()
