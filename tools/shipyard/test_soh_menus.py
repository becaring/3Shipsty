"""Compare menu initializer and modal queue bodies without fake UI services."""

import json, hashlib, runpy, subprocess, struct
from pathlib import Path
from prepare_soh_menus import ROOT, OUT, OWN, BASE, prepare
from prepare_soh_ui import includes
from prepare_archives import stable
from cpp_ast import PARSER, walk


def functions(text):
    return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type == "function_definition"]


def select(text, name):
    matches = [
        n for n in functions(text) if n.child_by_field_name("declarator").text.decode().split("(")[0].strip() == name
    ]
    assert len(matches) == 1, name
    return matches[0].text.decode()


def main():
    # The original host MenuTypes.h is a test-only projection owned by the UI
    # contract. Build and verify that provider instead of relying on an older
    # scratch copy or an external test order.
    from test_soh_ui import main as verify_ui_contract

    verify_ui_contract()
    prepare()
    env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
    compiler, environment = env["host_environment"]()
    results = []
    for name in ["Menu", "SohMenu", "SohModals", "SohMenuSettings", "SohMenuEnhancements", "SohMenuDevTools"]:
        original = (ROOT / (BASE + name + ".cpp")).read_text(encoding="utf-8-sig")
        projected = (OUT / "generated" / (BASE + name + ".cpp")).read_text()
        names = lambda text: [
            n.child_by_field_name("declarator").text.decode().split("(")[0].strip() for n in functions(text)
        ]
        assert set(names(original)) <= set(names(projected)), name
    for projected in [False, True]:
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        source = '#include "MenuTypes.h"\n'
        if projected:
            menu = (OUT / "generated" / (BASE + "Menu.cpp")).read_text()
            soh = (OUT / "generated" / (BASE + "SohMenu.cpp")).read_text()
            source += (
                select(menu, "Menu::MakeSearchSidebarEntry").replace(
                    "Menu::MakeSearchSidebarEntry", "MakeSearchSidebarEntry"
                )
                + "\n"
            )
            source += select(soh, "MakeSidebarEntry") + "\n" + select(soh, "MakeWidgetInfo") + "\n"
        else:
            menu = (ROOT / (BASE + "Menu.h")).read_text()
            a = menu.index("const SidebarEntry searchSidebarEntry =")
            b = menu.index("\n\n  private:", a)
            initializer = menu[a:b].split("=", 1)[1].strip().removesuffix(";")
            source += "SidebarEntry MakeSearchSidebarEntry(){return " + initializer + ";}\n"
            source += "SidebarEntry MakeSidebarEntry(uint32_t columnCount){return SidebarEntry{ .columnCount = columnCount };}\n"
            source += "WidgetInfo MakeWidgetInfo(std::string widgetName,WidgetType widgetType){return { .name = widgetName, .type = widgetType };}\n"
        path = (OUT / "generated" if projected else ROOT) / (BASE + "SohModals.cpp")
        modal = path.read_text()
        cls = [
            n.text.decode()
            for n in walk(PARSER.parse(modal.encode()).root_node)
            if n.type == "struct_specifier" and n.child_by_field_name("name").text == b"SohModal"
        ]
        assert len(cls) == 1
        source += cls[0] + ";\nstd::vector<SohModal> modals;bool closePopup=false;\n"
        for name in ["RegisterPopup", "PopupsQueued", "IsPopupOpen", "DismissPopup"]:
            source += select(modal, "SohModalWindow::" + name).replace("SohModalWindow::" + name, name) + "\n"
        notice = (OUT / "generated" if projected else ROOT) / "soh/soh/Notification/Notification.h"
        options = [
            n.text.decode()
            for n in walk(PARSER.parse(notice.read_text().encode()).root_node)
            if n.type == "struct_specifier" and n.child_by_field_name("name").text == b"Options"
        ]
        assert len(options) == 1
        source += "namespace Notification {\n" + options[0] + ";\n}\n"
        settings = ((OUT / "generated" if projected else ROOT) / (BASE + "SohMenuSettings.cpp")).read_text()
        if projected:
            a = settings.index("Notification::Options notification;")
            b = settings.index("Notification::Emit(notification);", a)
            body = settings[a:b] + "return notification;"
        else:
            call = next(
                n
                for n in walk(PARSER.parse(settings.encode()).root_node)
                if n.type == "call_expression" and n.child_by_field_name("function").text == b"Notification::Emit"
            )
            body = "return " + call.child_by_field_name("arguments").named_children[0].text.decode() + ";"
        source += "Notification::Options MakeNotification(){" + body + "}\n"
        literals = json.loads((OUT / "manifest.json").read_text())["literals"]
        printing = "void PrintLiterals(){"
        source += "#include <cstdio>\n"
        for i, literal in enumerate(literals):
            key = "menu_literal_" + str(i)
            source += 'extern "C" const char ' + key + "[]=" + literal["projected" if projected else "original"] + ";\n"
            printing += (
                "for(size_t i=0;i<sizeof(" + key + ')-1;++i)printf("%02x",(unsigned char)' + key + '[i]);printf("\\n");'
            )
        source += printing + "}\n" + (OWN / "contract.cpp").read_text()
        stable(folder / "contract.cpp", source)
        menu_include = ROOT / "scratch/soh-ui-xdk" / ("generated" / Path(BASE) if projected else "host-original")
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
            "/I" + str(menu_include),
        ]
        command += ["/I" + str(p) for p in includes()]
        if projected:
            command += ["/DSHIPYARD_MENU_PROJECTED"]
        command += [str(folder / "contract.cpp"), "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
        r = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        stable(folder / "build.log", r.stdout + r.stderr)
        assert r.returncode == 0, folder / "build.log"
        r = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        results.append(dict(command=command, stdout=r.stdout, exit=r.returncode))
    assert results[0]["stdout"] == results[1]["stdout"]
    flags = json.loads((OUT / "xdk/build.json").read_text())[0]["command"][:-2]
    obj = OUT / "xdk/contract.obj"
    command = flags + ["/DSHIPYARD_MENU_PROJECTED", str(OUT / "host-projected/contract.cpp"), "/Fo" + str(obj)]
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), r.stdout + r.stderr)
    assert r.returncode == 0, obj.with_suffix(".log")
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    from test_custom_message import coff_symbols

    symbols = coff_symbols(obj)
    for i, literal in enumerate(literals):
        value = bytes.fromhex(literal["bytes"])
        assert symbols["menu_literal_" + str(i)][: len(value) + 1] == value + b"\0"
        assert results[0]["stdout"].splitlines()[i] == value.hex()
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=results,
                native_contract=command,
                native_ui_executed=False,
                scope="Actual initializers, map insertion, four queue methods; no rendered-frame claim",
            ),
            indent=2,
        )
        + "\n",
    )
    print(results[0]["stdout"].splitlines()[-1])


if __name__ == "__main__":
    main()
