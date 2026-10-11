"""Complete actual debugger, resolution and icon application UI implementations."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from prepare_randomizer_context import includes as runtime_includes
from prepare_game_interactor import call_sites
from prepare_soh_ui import common, value_expressions
from prepare_enhancements import transform as enhancement_syntax
from prepare_custom_message import escape_literal
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/application-windows"
OUT = ROOT / "scratch/application-windows-xdk"
DEBUG = "soh/soh/Enhancements/debugger/"
GUI = "soh/soh/SohGui/"
SYNTAX = runpy.run_path(str(ROOT / "platform/shipyard/input/lowering.py"))["syntax"]
PAIR_BINDINGS = runpy.run_path(str(ROOT / "platform/shipyard/input/lowering.py"))["pair_bindings"]
UNITS = [
    DEBUG + n + ".cpp"
    for n in (
        "actorViewer",
        "colViewer",
        "debugSaveEditor",
        "dlViewer",
        "hookDebugger",
        "MessageViewer",
        "performanceTimer",
        "SohConsoleWindow",
        "SohGfxDebuggerWindow",
        "SohStatsWindow",
        "valueViewer",
    )
] + [GUI + "ImGuiUtils.cpp", GUI + "ResolutionEditor.cpp"]


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def containers(text):
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "declaration":
            continue
        typ = n.child_by_field_name("type")
        init = n.child_by_field_name("declarator")
        if typ is None or init is None or init.type != "init_declarator":
            continue
        value = init.child_by_field_name("value")
        if value is None or value.type != "initializer_list":
            continue
        kind = typ.text.decode()
        name = init.child_by_field_name("declarator").text.decode()
        if not kind.startswith(("std::vector<", "std::map<", "std::unordered_map<")):
            continue
        if not value.named_children:
            edits.append((init.start_byte, init.end_byte, name))
            continue
        static = "static " if any(c.text == b"static" for c in n.named_children) else ""
        row_name = "_rows_" + name
        row_type = "_Row_" + name
        args = next(c for c in walk(typ) if c.type == "template_argument_list").named_children
        if kind.startswith("std::vector<"):
            assert len(args) == 1
            prefix = (
                static
                + "const "
                + args[0].text.decode()
                + " "
                + row_name
                + "[] = "
                + value.text.decode()
                + ";\n"
            )
            replacement = (
                "("
                + row_name
                + ","
                + row_name
                + "+sizeof("
                + row_name
                + ")/sizeof("
                + row_name
                + "[0]))"
            )
            eq = next((c for c in init.children if c.type == "="), None)
            start = eq.start_byte if eq else value.start_byte
        else:
            assert len(args) == 2, (kind, n.text.decode()[:90])
            prefix = (
                "struct "
                + row_type
                + " { "
                + args[0].text.decode()
                + " first; "
                + args[1].text.decode()
                + " second; };\n"
                + static
                + "const "
                + row_type
                + " "
                + row_name
                + "[] = "
                + value.text.decode()
                + ";\n"
            )
            replacement = (
                "Shipyard::ApplicationWindows::MapFromRows<" + kind + ">(" + row_name + ")"
            )
            start = value.start_byte
        # Match the initializer-list backing array's temporary lifetime: rows
        # must not become extra permanent strings/callback objects in the app.
        result = kind + replacement if kind.startswith("std::vector<") else replacement
        body = prefix.removeprefix("static ") + "return " + result + ";"
        if n.parent.type in ("translation_unit", "declaration_list"):
            helper = "_Build_" + name
            edits.append(
                (n.start_byte, n.start_byte, "static " + kind + " " + helper + "(){" + body + "}\n")
            )
            expression = helper + "()"
        else:
            expression = "[&]() -> " + kind + " { " + body + " }()"
        edits.append((value.start_byte, value.end_byte, expression))
    return edits_apply(raw, edits)


def project(name, text):
    text = call_sites(text, name)
    text = PAIR_BINDINGS(text.encode()).decode()
    text = enhancement_syntax(name, text)
    # Resolve complete canonical declarations rather than adjacent pristine headers.
    dirname = Path(name).parent.as_posix().removeprefix("soh/")
    text = re.sub(
        r'#include "([^/\"]+\.h)"',
        lambda m: (
            '#include "' + dirname + "/" + m[1] + '"'
            if (ROOT / Path(name).parent / m[1]).exists()
            else m[0]
        ),
        text,
    )
    text = text.replace(
        '#include "../custom-message/CustomMessageManager.h"',
        '#include "soh/Enhancements/custom-message/CustomMessageManager.h"',
    )
    text = text.replace('#include "../../util.h"', '#include "soh/util.h"')
    text = text.replace(
        "#include <libultraship/libultraship.h>", "#include <libultraship/bridge.h>"
    )
    text = text.replace(
        "#include <bit>", "// Only popcount is used; supplied by the bounded native helper."
    ).replace("std::popcount(", "Shipyard::ApplicationWindows::Popcount(")
    text = text.replace(
        "#include <version>",
        "// Source-location availability is declared by the canonical hook header.",
    )
    text = text.replace("constexpr int", "const int")
    if name.endswith("MessageViewer.cpp"):
        text = once(
            text,
            "std::erase(mCustomMessageString, '\\n');",
            (
                'mCustomMessageString.erase(std::remove(mCustomMessageString.begin(),mCustomMessa'
                "geString.end(),'\\n'),mCustomMessageString.end());"
            ),
        )
    if name.endswith("dlViewer.cpp"):
        text = once(
            text,
            'val.ends_with("DL")',
            '(val.size() >= 2 && val.compare(val.size()-2,2,"DL") == 0)',
        )
    if name.endswith("hookDebugger.cpp"):
        text = once(
            text,
            "hookData.insert({ #name,"
            " GameInteractor::Instance->GetHookData<GameInteractor::name>() });",
            "hookData.insert(std::make_pair(#name,"
            " GameInteractor::Instance->GetHookData<GameInteractor::name>()));",
        )
    if name.endswith("actorViewer.cpp"):
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "lambda_expression" or n.child_by_field_name("captures").text != b"[this]":
                continue
            for ident in walk(n.child_by_field_name("body")):
                if ident.type == "identifier" and ident.text in (b"category", b"list", b"display"):
                    edits.append((ident.start_byte, ident.end_byte, "this->" + ident.text.decode()))
        text = edits_apply(raw, edits)
        text = once(
            text,
            "\n                newActor = { 0, 0, { 0, 0, 0 }, { 0, 0, 0 } };",
            "\n                { const ActorInfo reset = { 0, 0, { 0, 0, 0 }, { 0, 0, 0 } };"
            " newActor = reset; }",
        )
        text = once(
            text,
            "{ .tag = DEBUG_ACTOR_NAMETAG_TAG, .noZBuffer = !withZBuffer }",
            "Shipyard::ApplicationWindows::NameOptions(DEBUG_ACTOR_NAMETAG_TAG,!withZBuffer)",
        )
        text = re.sub(
            r'\{ \{ \.tooltip = ("(?:[^"\\]|\\.)*") \} \}',
            lambda m: "UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit()).Tooltip("
            + m[1]
            + ")",
            text,
        )
        # Derived widget aggregates initialize their base plus all defaulted members.
        text = text.replace(
            'UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit()).Tooltip("Click to add display'
            ' items on the name tags")',
            'UIWidgets::ButtonOptions(UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit()).Tooltip("Click'
            ' to add display items on the name tags"))',
        )
        for tooltip in (
            'Adds \\"name tags\\" above actors for identification',
            "Allow name tags to be obstructed when behind geometry and actors",
        ):
            old = (
                'UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit()).Tooltip("' + tooltip + '")'
            )
            text = text.replace(old, "UIWidgets::CheckboxOptions(" + old + ")")
    if name.endswith("debugSaveEditor.cpp"):
        text = text.replace("std::snprintf(", "Shipyard::SohResources::snprintf(")
        text = (
            '#include "soh-resources/format.h"\n#include'
            ' "soh/Enhancements/randomizer/randomizer.h"\n'
            + text
        )
    if name.endswith("ResolutionEditor.cpp"):
        text = once(
            text,
            "auto fastWnd = dynamic_pointer_cast<",
            "auto fastWnd = std::dynamic_pointer_cast<",
        )
        text = re.sub(r"WidgetPath path = \{([^{}]*)\};", r"WidgetPath path(\1);", text)
        m = re.search(r"const ImVec4 messageColor\[\](\{[\s\S]*?\n\});", text)
        assert m
        body = re.sub(r"\{([^{}]+)\}", lambda x: "ImVec4(" + x[1] + ")", m[1][1:-1])
        text = text[: m.start()] + "const ImVec4 messageColor[] = {" + body + "};" + text[m.end() :]
    if name.endswith("colViewer.cpp"):
        raw = text.encode()
        macro = next(
            n
            for n in walk(PARSER.parse(raw).root_node)
            if n.type == "preproc_function_def"
            and n.child_by_field_name("name").text == b"gdSPDefVtxN"
        )
        text = edits_apply(
            raw,
            [
                (
                    macro.start_byte,
                    macro.end_byte,
                    (
                        "#define gdSPDefVtxN(x,y,z,s,t,nx,ny,nz,ca)"
                        " Shipyard::ApplicationWindows::NormalVertex(x,y,z,qs105(s),qs105(t),nx,ny,nz,ca)\n"
                    ),
                )
            ],
        )
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if (
            n.type == "assignment_expression"
            and n.child_by_field_name("left").text == b"*gfx"
            and n.child_by_field_name("right").text.startswith(b"gs")
        ):
            assert n.parent.type == "expression_statement"
            edits.append(
                (
                    n.parent.start_byte,
                    n.parent.end_byte,
                    "{ const Gfx _command = "
                    + n.child_by_field_name("right").text.decode()
                    + "; *gfx = _command; }",
                )
            )
        if n.type == "initializer_list" and n.parent.type == "argument_list":
            call = n.parent.parent
            fn = call.child_by_field_name("function")
            if fn is None:
                continue
            func = fn.text.decode()
            values = n.text.decode()[1:-1]
            if func in ("CVarColorPicker", "CVarGetColor"):
                replacement = "ShipyardRGBA(" + values + ")"
            elif func.endswith(".Size") or func == "ImGui::Dummy":
                replacement = "ImVec2(" + values + ")"
            elif func == "Vec3f":
                edits.append(
                    (
                        call.start_byte,
                        call.end_byte,
                        "Shipyard::ApplicationWindows::Vector3(" + values + ")",
                    )
                )
                continue
            elif func in (
                "UIWidgets::CheckboxOptions",
                "UIWidgets::IntSliderOptions",
                "UIWidgets::FloatSliderOptions",
            ):
                if not values.strip():
                    replacement = "Shipyard::SohUI::ValueInit()"
                else:
                    match = re.fullmatch(r"\s*\{\s*\.disabled\s*=\s*([\s\S]*?)\s*\}\s*", values)
                    assert match, values
                    replacement = (
                        "UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit()).Disabled("
                        + match[1]
                        + ")"
                    )
            else:
                continue
            edits.append((n.start_byte, n.end_byte, replacement))
        if (
            n.type == "compound_literal_expression"
            and n.child_by_field_name("type").text == b"Vec3f"
        ):
            edits.append(
                (
                    n.start_byte,
                    n.end_byte,
                    "Shipyard::ApplicationWindows::Vector3("
                    + n.child_by_field_name("value").text.decode()[1:-1]
                    + ")",
                )
            )
        if n.type != "call_expression":
            continue
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments").named_children
        if (
            fn.text.endswith(b"push_back")
            and len(args) == 1
            and args[0].text.startswith((b"gs", b"gdSP"))
        ):
            assert n.parent.type == "expression_statement"
            typ = "Vtx" if args[0].text.startswith(b"gdSP") else "Gfx"
            edits.append(
                (
                    n.parent.start_byte,
                    n.parent.end_byte,
                    "{ const "
                    + typ
                    + " _command = "
                    + args[0].text.decode()
                    + "; "
                    + fn.text.decode()
                    + "(_command); }",
                )
            )
        if fn.text == b"faces.emplace_back":
            edits.append(
                (
                    n.start_byte,
                    n.end_byte,
                    "faces.push_back(std::make_tuple("
                    + ",".join("size_t(" + a.text.decode() + ")" for a in args)
                    + "))",
                )
            )
    text = edits_apply(raw, edits)
    text = text.replace("base.emplace_back(", "base.push_back(")
    if name.endswith("valueViewer.cpp"):
        raw = text.encode()
        edits = []
        helpers = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "lambda_expression" or n.parent.type != "initializer_list":
                continue
            assert n.text.decode().startswith("[]() -> void*")
            helper = "ShipyardValueGetter" + str(len(helpers))
            helpers.append(
                "static void* " + helper + "() " + n.child_by_field_name("body").text.decode()
            )
            edits.append((n.start_byte, n.end_byte, helper))
        text = edits_apply(raw, edits)
        text = once(text, "// clang-format off", "\n".join(helpers) + "\n// clang-format off")
    if name.endswith("SohStatsWindow.cpp"):
        text = '#include "application/frame_profile.h"\n' + text
        text = once(
            text, "const float framerate = ImGui::GetIO().Framerate;",
            "const float framerate = ModernFrameProfile::PresentationFps();",
        )
        text = once(
            text, "const float deltatime = ImGui::GetIO().DeltaTime;",
            "const float deltatime = framerate > 0.0f ? 1.0f / framerate : 0.0f;",
        )
        text = once(
            text,
            "#if defined(_WIN32)",
            '#if defined(_XBOX)\n    ImGui::Text("Platform: Xbox 360");\n#elif defined(_WIN32)',
        )
    if name.endswith("performanceTimer.cpp"):
        text = (
            text.replace("std::chrono::", "Shipyard::Logging::chrono::")
            .replace("std::milli", "Shipyard::Logging::chrono::ratio<1,1000>")
            .replace("high_resolution_clock", "steady_clock")
        )
        text = once(
            text,
            "totalTimes[timer] = {};",
            "totalTimes[timer] ="
            " Shipyard::Logging::chrono::duration<double,Shipyard::Logging::chrono::ratio<1,1000>"
            " >();",
        )
        text = once(
            text,
            "totalTimes = {};",
            "totalTimes ="
            " std::array<Shipyard::Logging::chrono::duration<double,Shipyard::Logging::chrono::ratio<1,1000>"
            " >, PT_MAX>();",
        )
    text = containers(text)
    text = re.sub(r"(ImVec[24]) (\w+) = \{([^;{}]*)\};", r"\1 \2(\3);", text)
    text = common(SYNTAX(text, set()))
    if name.endswith("colViewer.cpp"):
        text = re.sub(r"xbox_compat::get<([012])>", r"std::get<\1>", text)
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type == "string_literal" and any(b >= 128 for b in n.text):
            edits.append((n.start_byte, n.end_byte, escape_literal(n.text.decode())))
    text = edits_apply(raw, edits)
    text = text.replace(
        '#include "../game-interactor/GameInteractor_HookTable.h"',
        '#include "soh/Enhancements/game-interactor/GameInteractor_HookTable.h"',
    )
    return (
        '#include "application-windows/support.h"\n#include "resources/runtime_support.h"\n#include'
        ' "input/compiler.h"\n#include "game-interactor/varargs.h"\n#include'
        ' "soh/Enhancements/game-interactor/GameInteractor.h"\n#include'
        ' "ship/window/gui/IconsFontAwesome4.h"\n#include "ship/window/gui/Gui.h"\n#include'
        ' "soh/cvar_prefixes.h"\n#include <libultraship/bridge/consolevariablebridge.h>\n#include'
        " <locale>\n"
        + text
    )


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    generated = {}
    for name, digest in lock["sources"].items():
        t = (ROOT / name).read_text(encoding="utf-8-sig")
        assert sha(t) == digest, name
        texts[name] = t

    def emit(n, t):
        stable(OUT / "generated" / n, t)
        generated[n] = sha(t)

    header = (
        texts[DEBUG + "performanceTimer.h"]
        .replace("#include <chrono>", '#include "logging/chrono/chrono.h"')
        .replace("std::chrono::", "Shipyard::Logging::chrono::")
        .replace("std::milli", "Shipyard::Logging::chrono::ratio<1,1000>")
        .replace("high_resolution_clock", "steady_clock")
    )
    header = header.replace(" = {};", ";")
    emit(DEBUG + "performanceTimer.h", header)
    emit(
        GUI + "ResolutionEditor.h",
        texts[GUI + "ResolutionEditor.h"].replace(
            "#include <libultraship/libultraship.h>",
            "// This header declares three functions and needs no desktop umbrella.",
        ),
    )
    for n in UNITS:
        emit(n, project(n, texts[n]))
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_archives.py",
            "prepare_configuration.py",
            "prepare_randomizer.py",
            "prepare_randomizer_context.py",
            "prepare_game_interactor.py",
            "prepare_soh_ui.py",
            "prepare_enhancements.py",
            "prepare_custom_message.py",
            "prepare_resource_manager.py",
            "cpp_ast.py",
        )
    ] + [
        ROOT / "platform/shipyard/input/lowering.py",
        ROOT / "platform/shipyard/imgui/projection.py",
        OWN / "support.h",
    ]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated=generated,
                full_units=UNITS,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helpers={
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in helpers
                },
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    return [
        OUT / "generated/soh",
        ROOT / "scratch/application-gui-xdk/generated/soh",
        ROOT / "scratch/presentation-xdk/generated/include",
        ROOT / "scratch/stormlib-xdk/generated/src",
        ROOT / "platform/shipyard",
    ] + runtime_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    roots = list(dict.fromkeys(includes() + [Path(f[2:]) for f in flags if f.startswith("/I")]))
    roots.sort(
        key=lambda p: (
            2
            if p.is_relative_to(ROOT / "soh")
            else 1 if p.is_relative_to(ROOT / "scratch/game-xdk") else 0
        )
    )
    flags = [f for f in flags if not f.startswith("/I")]
    flags[1:1] = ["/I" + str(p) for p in roots]
    rows = []
    for n in UNITS:
        source = OUT / "generated" / n
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        row = dict(
            source=source.relative_to(ROOT).as_posix(),
            command=command,
            exit=r.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if not r.returncode:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print("\n".join(s for s in (r.stdout + r.stderr).splitlines() if "error " in s)[:1800])
        rows.append(row)
        print(source.stem + ": " + str(r.returncode), flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
