"""Pinned editor inventories, and original versus projected data and widget values."""

import hashlib, json, re, runpy, subprocess
from prepare_application_editors import ROOT, OUT, OWN, SOURCES, prepare, includes, methods
from prepare_archives import stable
from cpp_ast import PARSER, walk


def fnname(n):
    return n.child_by_field_name("declarator").text.decode().split("(")[0]


def body(text, name):
    return next(n.text.decode() for n in methods(text) if fnname(n) == name)


def calls(text, predicate):
    return [
        n.text.decode()
        for n in walk(PARSER.parse(text.encode()).root_node)
        if n.type == "call_expression" and predicate(n.child_by_field_name("function").text.decode())
    ]


def declaration(text, name):
    for n in walk(PARSER.parse(text.encode()).root_node):
        if n.type != "declaration":
            continue
        for c in n.named_children:
            if (
                c.type == "init_declarator"
                and c.child_by_field_name("declarator").text.decode().removesuffix("[]") == name
            ):
                return n.text.decode()
    raise ValueError(name)


def main():
    prepare()
    original = {n: (ROOT / p).read_text(encoding="utf-8-sig") for n, p in SOURCES.items()}
    projected = {n: (OUT / "generated" / p).read_text() for n, p in SOURCES.items()}
    inventories = {}
    for n in SOURCES:
        a, b = original[n], projected[n]
        sig = lambda t: [v.child_by_field_name("declarator").text.decode() for v in methods(t)]
        assert all(x in sig(b) for x in sig(a))
        inventory = {}
        for category, predicate in [
            ("CVars", lambda f: f.startswith("CVAR_")),
            ("graphics_macros", lambda f: f.startswith("gs")),
            ("patch_sites", lambda f: f == "PATCH_GFX"),
            ("cosmetic_rows", lambda f: f == "COSMETIC_OPTION"),
            ("hooks", lambda f: f == "COND_HOOK"),
        ]:
            old, new = calls(a, predicate), calls(b, predicate)
            # Map constructors move data above its original declaration, preserving
            # data order but moving CVar expressions inside those rows together.
            assert sorted(old) == sorted(new), (n, category)
            inventory[category] = len(old)
        inventory["functions"] = len(sig(a))
        inventory["widget_values"] = len(re.findall(r'\.name = "', a))
        inventory["search_widgets"] = a.count("->AddSearchWidget(")
        if n == "CosmeticsEditor":
            # Macro-heavy initializer syntax is not uniformly represented as
            # call_expression nodes. Audit every active row, excluding comments.
            active = lambda t: re.findall(
                r"^\s*(?:MESSAGE_)?COSMETIC_OPTION\([^\n]+\)", re.sub(r"/\*[\s\S]*?\*/", "", t), re.M
            )
            assert active(a) == active(b)
            inventory["cosmetic_rows"] = len(active(a))
            assert inventory["cosmetic_rows"] == 197
        for label, pattern in [
            ("ui_calls", r"\b(?:ImGui|UIWidgets)::\w+(?=\()"),
            ("hook_registrations", r"RegisterGameHook<[^>]+>"),
        ]:
            old, new = re.findall(pattern, a), re.findall(pattern, b)
            assert old == new, (n, label)
            inventory[label] = len(old)
        inventories[n] = inventory
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected_flag in (False, True):
        folder = OUT / ("host-projected" if projected_flag else "host-original")
        folder.mkdir(exist_ok=True)
        texts = projected if projected_flag else original
        a = texts["AudioEditor"]
        c = texts["CosmeticsEditor"]
        prefix = """#include <map>
#include <vector>
#include <string>
#include <cstdint>
#include <cassert>
#include <iostream>
#include <cstring>
#include <imgui.h>
#include "ship/utils/color.h"
#include "soh/cvar_prefixes.h"
#include "soh/Enhancements/enhancementTypes.h"
"""
        seq = (ROOT / "soh/soh/Enhancements/audio/AudioCollection.h").read_text()
        prefix += re.search(r"enum SeqType \{[\s\S]*?\};", seq)[0] + "\n"
        header = (ROOT / "soh/soh/Enhancements/cosmetics/CosmeticsEditor.h").read_text()
        prefix += re.search(r"typedef enum \{[\s\S]*?\} CosmeticGroup;", header)[0] + "\n"
        begin = c.index("static std::map<CosmeticGroup") if projected_flag else c.index("std::map<CosmeticGroup")
        data = prefix + c[begin : c.index("// clang-format on")] + "\n"
        data += "\n".join(s for s in a.splitlines() if s.startswith("#define SEQ_COUNT_")) + "\n"
        data += (
            "\n".join(
                body(a, n) for n in ("AuthenticCountBySequenceType", "GetSequenceTypeName", "GetSequenceTypeColor")
            )
            + "\n"
        )
        data += (
            (body(a, "MakeaudioRandomizerModes") + "\n" if projected_flag else "")
            + declaration(a, "audioRandomizerModes")
            + "\n"
        )
        data += (
            body(a, "MakeshowType") + "\nstd::map<SeqType,bool> ShowTypes(){ return MakeshowType(); }\n"
            if projected_flag
            else "std::map<SeqType,bool> ShowTypes(){ "
            + re.search(r"static std::map<SeqType, bool> showType\{[\s\S]*?\};", a)[0]
            + " return showType; }\n"
        )
        data += (declaration(a, "allTypeValues") + "\n" if projected_flag else "") + declaration(a, "allTypes") + "\n"
        # The full native unit also retains the default getter's pinned casts.
        # Data tests inspect its source values; they do not exercise out-of-range
        # float-to-uint8 conversions in that upstream method.
        data += "\n" + (OWN / "data_contract.cpp").read_text()
        stable(folder / "data.cpp", data)
        # Extract widget value statements without replacing/rendering SohMenu.
        # Search records are SearchWidget values held by this test alone.
        if not projected_flag:
            ui = (ROOT / "soh/soh/SohGui/UIWidgets.hpp").read_text()
            generated = (ROOT / "scratch/soh-ui-xdk/generated/soh/soh/SohGui/UIWidgetTypes.h").read_text()
            stable(
                folder / "UIWidgetTypes.h",
                generated[: generated.index("namespace UIWidgets {")]
                + ui[ui.index("namespace UIWidgets {") : ui.index("\nvoid PushStyleMenu(")]
                + "\n}\n",
            )
            menu = (
                (ROOT / "soh/soh/SohGui/MenuTypes.h")
                .read_text()
                .replace(
                    "#include <libultraship/libultraship.h>",
                    '#include <functional>\n#include <variant>\n#include "ship/window/WindowBackend.h"\n#include "ship/audio/Audio.h"',
                )
                .replace('#include "UIWidgets.hpp"', '#include "UIWidgetTypes.h"')
            )
            stable(folder / "MenuTypes.h", menu)
        widget = """#include "MenuTypes.h"
#include <cassert>
#include <iostream>
#include <cstring>
#include "soh/cvar_prefixes.h"
#include "soh/Enhancements/enhancementTypes.h"
using namespace UIWidgets;
"""
        if projected_flag:
            widget += '#include "application-editors/support.h"\n'
        widget += "\n".join(re.findall(r"static WidgetInfo \w+;", a + c)) + "\n"
        widget += (
            (body(a, "MakeaudioRandomizerModes") + "\n" if projected_flag else "")
            + declaration(a, "audioRandomizerModes")
            + "\n"
        )
        widget += "std::vector<SearchWidget> searches;\n#define THEME_COLOR theme\nvoid InitializeValues(UIWidgets::Colors theme){\n"
        for t, f in [(a, "RegisterAudioWidgets"), (c, "RegisterCosmeticWidgets")]:
            n = next(v for v in methods(t) if fnname(v) == f)
            for statement in n.child_by_field_name("body").named_children:
                s = statement.text.decode()
                if "->AddSearchWidget(" in s:
                    s = s.replace("SohGui::mSohMenu->AddSearchWidget(", "searches.push_back(")
                widget += s + "\n"
        names = re.findall(r"static WidgetInfo (\w+);", a + c)
        widget += (
            "}\nWidgetInfo* widgets[]={"
            + ",".join("&" + n for n in names)
            + "};\n"
            + (OWN / "widget_contract.cpp").read_text()
        )
        stable(folder / "widget.cpp", widget)
        for kind in ("data", "widget"):
            command = [
                str(compiler),
                "/nologo",
                "/std:c++20",
                "/utf-8",
                "/EHsc",
                "/GR",
                "/MD",
                "/O2",
                "/Gy",
                "/DNOMINMAX",
                "/DSHIPYARD_AUDIO_TEST",
                "/DF3DEX_GBI_2",
                "/DCONTROLLERBUTTONS_T=uint32_t",
                "/I" + str(folder),
            ]
            command += ["/FI" + str(ROOT / "scratch/configuration-xdk/generated/include/compile_definitions.h")]
            if projected_flag:
                command += ["/DSHIPYARD_EDITOR_PROJECTED"]
            command += ["/I" + str(p) for p in includes()] + [
                str(folder / (kind + ".cpp")),
                "/Fo:" + str(folder) + "/",
                "/Fe:" + str(folder / (kind + ".exe")),
                "/link",
                "/OPT:REF",
            ]
            r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            stable(folder / (kind + "-build.log"), r.stdout + r.stderr)
            assert not r.returncode, folder / (kind + "-build.log")
            r = subprocess.run([str(folder / (kind + ".exe"))], cwd=ROOT, capture_output=True, text=True)
            row = dict(
                kind=kind,
                projected=projected_flag,
                command=command,
                exit=r.returncode,
                stdout=r.stdout,
                stderr=r.stderr,
            )
            rows.append(row)
            assert not r.returncode, row
    for kind in ("data", "widget"):
        r = [v for v in rows if v["kind"] == kind]
        assert r[0]["stdout"] == r[1]["stdout"], kind
    native = json.loads((OUT / "xdk/build.json").read_text())
    for row in native:
        assert (
            not row["exit"] and row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
        )
    stable(
        OUT / "verification.json",
        json.dumps(dict(inventories=inventories, host=rows, native=native, native_ui_executed=False), indent=2) + "\n",
    )
    print(json.dumps(inventories))
    print("Original/projected cosmetic, sequence, map and actual widget values match.")


if __name__ == "__main__":
    main()
