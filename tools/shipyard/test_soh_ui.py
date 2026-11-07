"""Execute widget value/menu methods and bounded implementation contracts."""

import hashlib
import json
import runpy
import subprocess
import struct
from prepare_soh_ui import ROOT, OUT, OWN, BASE, prepare, includes, value_expressions
from prepare_archives import stable
from cpp_ast import PARSER, walk


def main():
    prepare()
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    projected = (OUT / "generated" / BASE / "UIWidgets.cpp").read_text()
    assert '#include "math/color.h"' in projected
    assert all("Shipyard::Math::ColorByte(colorVec." + component + ")" in projected for component in "xyz")
    assert "inline double FMin" not in (OWN / "value_init.h").read_text()
    assert "ButtonOptions(Shipyard::SohUI::ValueInit())" in value_expressions("auto x=ButtonOptions{};")
    assert "WidgetInfo x= WidgetInfo(Shipyard::SohUI::ValueInit());" == value_expressions("WidgetInfo x{};")
    for projected in (False, True):
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        if not projected:
            t = (ROOT / (BASE + "UIWidgets.hpp")).read_text()
            start = t.index("namespace UIWidgets {")
            end = t.index("\nvoid PushStyleMenu(")
            generated = (OUT / "generated" / BASE / "UIWidgetTypes.h").read_text()
            prefix = generated[: generated.index("namespace UIWidgets {")]
            stable(folder / "UIWidgetTypes.h", prefix + t[start:end] + "\n}\n")
            menu = (
                (ROOT / (BASE + "MenuTypes.h"))
                .read_text()
                .replace(
                    "#include <libultraship/libultraship.h>",
                    '#include <functional>\n#include <variant>\n#include "ship/window/WindowBackend.h"\n#include "ship/audio/Audio.h"',
                )
                .replace('#include "UIWidgets.hpp"', '#include "UIWidgetTypes.h"')
            )
            stable(folder / "MenuTypes.h", menu)
        cpp = (
            (OUT / "generated" / BASE / "UIWidgets.cpp") if projected else ROOT / (BASE + "UIWidgets.cpp")
        ).read_text()
        names = lambda text: [
            n.child_by_field_name("declarator").text.decode()
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "function_definition"
        ]
        for signature in names((ROOT / (BASE + "UIWidgets.cpp")).read_text()):
            assert signature in names((OUT / "generated" / BASE / "UIWidgets.cpp").read_text()), signature
        functions = [
            n.text.decode()
            for n in walk(PARSER.parse(cpp.encode()).root_node)
            if n.type == "function_definition" and n.child_by_field_name("declarator").text.startswith(b"WrappedText(")
        ]
        assert len(functions) == 2
        imgui = (
            ROOT / "scratch/imgui-xdk" / ("generated" if projected else "original") / "imgui_widgets.cpp"
        ).read_text()
        callbacks = [
            n.text.decode()
            for n in walk(PARSER.parse(imgui.encode()).root_node)
            if n.type == "function_definition"
            and n.child_by_field_name("declarator").text.startswith(
                b"ImGuiInputTextCallbackData::ImGuiInputTextCallbackData("
            )
        ]
        assert len(callbacks) == 1
        source = folder / "contract.cpp"
        stable(
            source,
            '#include "MenuTypes.h"\n'
            + callbacks[0]
            + "\nnamespace UIWidgets {\n"
            + "\n".join(functions)
            + "\n}\n"
            + (OWN / "type_contract.cpp").read_text(),
        )
        command = [
            str(compiler),
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/GR",
            "/MD",
            "/DNOMINMAX",
            "/DSHIPYARD_AUDIO_TEST",
            "/DF3DEX_GBI_2",
            "/DCONTROLLERBUTTONS_T=uint32_t",
            "/I" + str(folder),
            "/I" + str(OUT / "generated" / BASE),
        ]
        command += ["/I" + str(p) for p in includes()]
        if projected:
            command += ["/DSHIPYARD_UI_PROJECTED"]
        command += [str(source), "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", result.stdout + result.stderr)
        assert result.returncode == 0, folder / "build.log"
        result = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        row = dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        stable(folder / "run.json", json.dumps(row, indent=2) + "\n")
        rows.append(row)
        assert result.returncode == 0, row
    assert rows[0]["stdout"] == rows[1]["stdout"]
    flags = json.loads((OUT / "xdk/probe.json").read_text())["command"][:-2]
    source = OUT / "host-projected/contract.cpp"
    obj = OUT / "xdk/type_contract.obj"
    command = flags + ["/DSHIPYARD_UI_PROJECTED", "/I" + str(OUT / "generated" / BASE), str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), result.stdout + result.stderr)
    assert result.returncode == 0, obj.with_suffix(".log")
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=rows,
                native=command,
                sha256=hashlib.sha256(rows[0]["stdout"].encode()).hexdigest(),
                native_ui_executed=False,
                scope="Complete value/menu inline methods and two real wrapping methods; rendering functions compiled but not executed",
            ),
            indent=2,
        )
        + "\n",
    )
    print(rows[0]["stdout"].splitlines()[-1])


if __name__ == "__main__":
    main()
