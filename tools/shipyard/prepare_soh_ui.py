"""Project complete modern widget/menu declarations without replacing their UI."""

import argparse
import hashlib
import json
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_app_services import includes as current_includes
from prepare_randomizer import edits_apply, default_arguments
from prepare_resource_manager import syntax
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/soh-ui"
OUT = ROOT / "scratch/soh-ui-xdk"
BASE = "soh/soh/SohGui/"
WIDGETS = [
    "WidgetOptions",
    "TextOptions",
    "ButtonOptions",
    "ColorPickerOptions",
    "WindowButtonOptions",
    "CheckboxOptions",
    "ComboboxOptions",
    "IntSliderOptions",
    "FloatSliderOptions",
    "BtnSelectorOptions",
    "RadioButtonsOptions",
    "InputOptions",
]
MENU = [
    "WidgetInfo",
    "WidgetPath",
    "disabledInfo",
    "SidebarEntry",
    "MainMenuEntry",
    "SearchEntry",
    "SearchWidget",
]


def constructors(text, names):
    raw = text.encode()
    edits = []
    audit = {}
    for cls in walk(PARSER.parse(raw).root_node):
        if cls.type != "struct_specifier":
            continue
        ident = cls.child_by_field_name("name")
        body = cls.child_by_field_name("body")
        if not ident or not body or ident.text.decode() not in names:
            continue
        name = ident.text.decode()
        normal = []
        valued = []
        fields = []
        inherited = any(c.type == "base_class_clause" for c in cls.named_children)
        if inherited:
            normal.append("WidgetOptions()")
            valued.append("WidgetOptions(Shipyard::SohUI::ValueInit())")
        for field in body.named_children:
            if field.type != "field_declaration" or any(
                c.type == "function_declarator" for c in field.named_children
            ):
                continue
            typ = field.child_by_field_name("type")
            value = field.child_by_field_name("default_value")
            declarators = [
                field.children[i]
                for i in range(field.child_count)
                if field.field_name_for_child(i) == "declarator"
            ]
            for d in declarators:
                ids = [n for n in walk(d) if n.type == "field_identifier"]
                if len(ids) != 1:
                    raise ValueError(
                        "Widget member declaration needs audit: " + field.text.decode()
                    )
                member = ids[0].text.decode()
                expr = value.text.decode() if value else None
                if expr == "{}":
                    expr = ""
                if expr and expr.startswith("{"):
                    if typ.text == b"ImVec2":
                        expr = expr[1:-1]
                    elif typ.text == b"Color_RGBA8":
                        expr = "Shipyard::SohUI::Rgba8(" + expr[1:-1] + ")"
                    else:
                        raise ValueError("Widget list default needs audit: " + field.text.decode())
                if value:
                    normal.append(member + "(" + expr + ")")
                implicit = (
                    "Shipyard::SohUI::ValueInit()"
                    if typ.text.decode() in MENU + WIDGETS and d.type == "field_identifier"
                    else ""
                )
                valued.append(member + "(" + (expr if value else implicit) + ")")
                field_prefix = raw[field.start_byte : declarators[0].start_byte].decode().strip()
                fallback = (
                    "nullptr"
                    if d.type == "pointer_declarator"
                    else (typ.text.decode() + "(" + implicit + ")")
                )
                default = expr if value else fallback
                if value and expr == "":
                    default = typ.text.decode() + "()"
                if value and typ.text == b"ImVec2" and value.text.startswith(b"{"):
                    default = "ImVec2(" + expr + ")"
                fields.append(
                    dict(
                        name=member,
                        type=typ.text.decode(),
                        declarator=d.text.decode(),
                        parameter=field_prefix
                        + " "
                        + d.text.decode().replace(member, member + "_"),
                        reference=d.type == "reference_declarator",
                        argument_default=default,
                        default=value.text.decode() if value else None,
                    )
                )
            if value:
                eq = next(c for c in field.children if c.type == "=")
                edits.append((eq.start_byte, value.end_byte, ""))
        ctors = "\n    " + name + "()" + (" : " + ", ".join(normal) if normal else "") + " {}\n"
        ctors += (
            "    explicit "
            + name
            + "(Shipyard::SohUI::ValueInit)"
            + (" : " + ", ".join(valued) if valued else "")
            + " {}\n"
        )
        if any(f["reference"] for f in fields):
            # A reference aggregate has no valid default/value initialization.
            # Preserve its required reference through the real field sequence.
            ctors = ""
        params = ["const WidgetOptions& base_"] if inherited else []
        init = ["WidgetOptions(base_)"] if inherited else []
        for f in fields:
            parameter = f["parameter"]
            if params and not f["reference"]:
                parameter += " = " + f["argument_default"]
            params.append(parameter)
            init.append(
                f["name"]
                + "("
                + (f["name"] + "_" if f["reference"] else "std::move(" + f["name"] + "_)")
                + ")"
            )
        ctors += (
            "    explicit " + name + "(" + ", ".join(params) + ") : " + ", ".join(init) + " {}\n"
        )
        edits.append((body.start_byte + 1, body.start_byte + 1, ctors))
        audit[name] = fields
    if set(audit) != set(names):
        raise ValueError("Widget class inventory changed")
    return edits_apply(raw, edits), audit


def value_expressions(text):
    # Only expression contexts are rewritten; declarations such as T value;
    # continue to use default initialization with their original indeterminates.
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type == "init_declarator":
            a = n.child_by_field_name("value")
            declaration = n.parent
            typ = (
                declaration.child_by_field_name("type")
                if declaration.type == "declaration"
                else None
            )
            if (
                a is not None
                and a.text == b"{}"
                and typ is not None
                and typ.text.decode().split("::")[-1] in WIDGETS + MENU
            ):
                eq = "" if any(c.type == "=" for c in n.children) else "= "
                edits.append(
                    (
                        a.start_byte,
                        a.end_byte,
                        eq + typ.text.decode() + "(Shipyard::SohUI::ValueInit())",
                    )
                )
        if n.type not in ("call_expression", "compound_literal_expression"):
            continue
        f = n.child_by_field_name("function") or n.child_by_field_name("type")
        a = n.child_by_field_name("arguments") or n.child_by_field_name("value")
        if f is None or a is None or a.named_children:
            continue
        if f.text.decode().split("::")[-1] in WIDGETS + MENU:
            edits.append(
                (n.start_byte, n.end_byte, f.text.decode() + "(Shipyard::SohUI::ValueInit())")
            )
    return edits_apply(raw, edits)


def maps(text):
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "declaration":
            continue
        typ = n.child_by_field_name("type")
        if not typ or not re.match(rb"std::(?:unordered_)?map<", typ.text):
            continue
        init = next((c for c in n.named_children if c.type == "init_declarator"), None)
        value = init.child_by_field_name("value") if init else None
        if value is None or value.type != "initializer_list":
            continue
        args = typ.child_by_field_name(
            "name"
        )  # Parse the two known non-nested map key/value spellings.
        types = typ.text.decode().split("<", 1)[1][:-1].split(",")
        if len(types) != 2:
            raise ValueError("Map shape needs audit")
        name = init.child_by_field_name("declarator").text.decode()
        helper = "Make" + name
        content = value.text.decode()
        if name == "audioBackendsMap":
            content = (
                '{ { Ship::AudioBackend::XAUDIO2, "XAudio2" }, { Ship::AudioBackend::NUL,'
                ' "Null" } }'
            )
        if name == "windowBackendsMap":
            content = '{ { Ship::WindowBackend::FAST3D_XENOS, "Xenos" } }'
        prefix = (
            "static "
            + typ.text.decode()
            + " "
            + helper
            + "(){ struct Row { "
            + types[0]
            + " first; "
            + types[1]
            + " second; }; const Row values[]="
            + content
            + "; "
            + typ.text.decode()
            + " result; for(size_t i=0;i<sizeof(values)/sizeof(values[0]);++i)"
            " result.insert(std::make_pair(values[i].first,values[i].second)); return result; }\n"
        )
        edits.append((n.start_byte, n.start_byte, prefix))
        edits.append((value.start_byte, value.end_byte, helper + "()"))
    return edits_apply(raw, edits)


def common(text):
    text = re.sub(r"using (\w+) = ([^;]+);", r"typedef \2 \1;", text)
    text = text.replace("typedef void (*)() SectionFunc;", "typedef void (*SectionFunc)();")
    text = text.replace(
        "for (auto& [index, string] : comboMap) {",
        "for (auto& pair : comboMap) {\n        const auto& index=pair.first;const auto&"
        " string=pair.second;",
    )
    text = default_arguments(text)
    text = value_expressions(text)
    lower = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))["lower_ranges"]
    return syntax(
        lower(text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end").decode()
    )


def default_templates(text):
    raw = text.encode()
    edits = []
    count = 0
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "template_declaration":
            continue
        params = n.child_by_field_name("parameters")
        if params is None or b"typename T =" not in params.text:
            continue
        default = re.search(rb"typename T = (\w+)", params.text)[1].decode()
        fn = next(c for c in n.named_children if c.type == "function_definition")
        decl = fn.child_by_field_name("declarator")
        name = decl.child_by_field_name("declarator").text.decode()
        fp = decl.child_by_field_name("parameters")
        args = []
        for p in fp.named_children:
            d = p.child_by_field_name("declarator")
            ids = [i for i in walk(d) if i.type == "identifier"]
            args.append(ids[0].text.decode())
        wrapper = (
            ("template<size_t N> " if b"size_t N" in params.text else "")
            + "inline bool "
            + name
            + re.sub(r"\bT\b", default, fp.text.decode())
            + " { return "
            + name
            + "<"
            + default
            + ">("
            + ",".join(args)
            + "); }\n"
        )
        edits.append(
            (
                params.start_byte,
                params.end_byte,
                params.text.decode().replace("typename T = " + default, "typename T"),
            )
        )
        edits.append((n.end_byte, n.end_byte, "\n" + wrapper))
        count += 1
    if count != 6:
        raise ValueError("Widget template defaults changed")
    return edits_apply(raw, edits)


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    original = {}
    for name, expected in lock["sources"].items():
        t = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(t.encode()).hexdigest() != expected:
            raise ValueError("Modern menu source drift " + name)
        original[name] = t
    widgets = original[BASE + "UIWidgets.hpp"]
    start = widgets.index("namespace UIWidgets {")
    split = widgets.index("\nvoid PushStyleMenu(")
    types = widgets[start:split] + "\n}\n"
    types = maps(types)
    types = common(types)
    types, audit = constructors(types, WIDGETS)
    prefix = (
        "#pragma once\n#include <map>\n#include <unordered_map>\n#include <vector>\n#include"
        " <string>\n#include <cstring>\n#include <memory>\n#include <imgui.h>\n#include"
        ' <libultraship/libultra.h>\n#include "soh-ui/value_init.h"\n#include'
        ' "resources/runtime_support.h"\n'
    )
    stable(OUT / "generated" / BASE / "UIWidgetTypes.h", prefix + types)
    full = (
        '#ifndef UIWidgets2_hpp\n#define UIWidgets2_hpp\n#include "UIWidgetTypes.h"\n#include'
        ' "ship/window/gui/GuiWindow.h"\n#include "ship/Context.h"\n#include'
        ' "ship/window/Window.h"\n#include "ship/window/gui/Gui.h"\n#include'
        ' "libultraship/bridge.h"\n#include "soh/ShipInit.hpp"\n#include'
        ' "soh/ShipUtils.h"\nnamespace UIWidgets {\n'
        + widgets[split:]
    )
    full = common(default_templates(full))
    stable(OUT / "generated" / BASE / "UIWidgets.hpp", full)
    menu = once(
        original[BASE + "MenuTypes.h"],
        "#include <libultraship/libultraship.h>",
        '#include <functional>\n#include "ship/window/WindowBackend.h"\n#include'
        ' "ship/audio/Audio.h"\n#include <xbox_compat/variant.h>',
    )
    menu = once(menu, '#include "UIWidgets.hpp"', '#include "UIWidgetTypes.h"')
    menu = menu.replace("std::variant", "xbox_compat::variant").replace(
        "std::get<", "xbox_compat::get<"
    )
    menu = common(maps(menu))
    menu, menu_audit = constructors(menu, MENU)
    stable(OUT / "generated" / BASE / "MenuTypes.h", menu)
    source = once(
        original[BASE + "UIWidgets.cpp"],
        "#include <libultraship/libultraship.h>",
        '#include "ship/window/gui/IconsFontAwesome4.h"\n#include "input/compiler.h"\n#include'
        ' "math/color.h"',
    )
    source = once(
        source, "std::round(*value * factor)", "ShipyardInputCompiler::Round(*value * factor)"
    )
    for component in "xyz":
        source = once(
            source,
            "fmin(fmax(colorVec." + component + " * 255, 0), 255)",
            "Shipyard::Math::ColorByte(colorVec." + component + ")",
        )
    source = once(
        source,
        "{ { options.tooltip, options.disabled, options.disabledTooltip },\n                       "
        "              options.size,\n                                     options.padding,\n      "
        "                               options.color }",
        "MakeWindowButtonOptions(options)",
    )
    helper = (
        """static ButtonOptions MakeWindowButtonOptions(const WindowButtonOptions &options) {
    ButtonOptions result((Shipyard::SohUI::ValueInit()));
    result.tooltip = options.tooltip;
    result.disabled = options.disabled;
    result.disabledTooltip = options.disabledTooltip;
    result.size = options.size;
    result.padding = options.padding;
    result.color = options.color;
    return result;
}
"""
    )
    source = once(source, "namespace UIWidgets {", "namespace UIWidgets {\n" + helper)
    if source.count("ButtonOptions{ .color = options.color }") != 4:
        raise ValueError("Button color initializer inventory changed")
    source = source.replace(
        "ButtonOptions{ .color = options.color }",
        "ButtonOptions(Shipyard::SohUI::ValueInit()).Color(options.color)",
    )
    raw = source.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "initializer_list" or n.parent.type != "argument_list":
            continue
        value = n.text.decode()
        match = re.fullmatch(r'\{ \{ \.tooltip = ("(?:[^"\\]|\\.)*") \} \}', value)
        if not match:
            raise ValueError("Unmapped widget argument initializer " + value)
        callee = n.parent.parent.child_by_field_name("function").text.decode().split("::")[-1]
        typ = {
            "Button": "ButtonOptions",
            "CVarCheckbox": "CheckboxOptions",
            "ButtonOptions": "ButtonOptions",
            "CheckboxOptions": "CheckboxOptions",
        }[callee]
        edits.append(
            (
                n.start_byte,
                n.end_byte,
                typ + "(Shipyard::SohUI::ValueInit()).Tooltip(" + match[1] + ")",
            )
        )
    if len(edits) != 5:
        raise ValueError("Tooltip base initializer inventory changed")
    source = edits_apply(raw, edits)
    source = source.replace(
        "for (const auto& [buttonName, buttonMask] : buttonMap) {",
        "for (const auto& entry : buttonMap) {\n        const auto& buttonName=entry.first;const"
        " auto& buttonMask=entry.second;",
    )
    source = once(
        source,
        "ImVec4 vec = { color.r / 255.0f, color.g / 255.0f, color.b / 255.0f, color.a / 255.0f };",
        "ImVec4 vec(color.r / 255.0f, color.g / 255.0f, color.b / 255.0f, color.a / 255.0f);",
    )
    stable(OUT / "generated" / BASE / "UIWidgets.cpp", common(maps(source)))
    generated = {
        p.relative_to(OUT / "generated").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (OUT / "generated" / BASE).glob("*")
        if p.is_file()
    }
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated=generated,
                members={**audit, **menu_audit},
                native_ui_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    return [
        OUT / "generated/soh",
        ROOT / "scratch/ship-utils-xdk/generated/soh",
    ] + current_includes()


def probe():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    source = folder / "menu_declarations.cpp"
    stable(
        source,
        '#include "soh/SohGui/MenuTypes.h"\nvoid Test(WidgetInfo& w){UIWidgets::ColorPickerOptions'
        " c((Shipyard::SohUI::ValueInit())); w.Options(c);}\n",
    )
    flags = json.loads((ROOT / "scratch/game-interactor-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    obj = folder / "menu_declarations.obj"
    command = flags + [str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), result.stdout + result.stderr)
    print("Menu declarations:", result.returncode)
    if result.returncode:
        print("\n".join(s for s in result.stdout.splitlines() if "error " in s)[:4000])
        raise SystemExit(1)
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(
        folder / "probe.json",
        json.dumps(dict(command=command, exit=result.returncode), indent=2) + "\n",
    )


def build():
    probe()
    folder = OUT / "xdk"
    flags = json.loads((folder / "probe.json").read_text())["command"][:-2]
    source = OUT / "generated" / BASE / "UIWidgets.cpp"
    obj = folder / "UIWidgets.obj"
    command = flags + [str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), result.stdout + result.stderr)
    print("Complete UIWidgets:", result.returncode)
    stable(
        folder / "build.json",
        json.dumps(
            [
                dict(
                    source=source.relative_to(ROOT).as_posix(),
                    command=command,
                    exit=result.returncode,
                )
            ],
            indent=2,
        )
        + "\n",
    )
    if result.returncode:
        print("\n".join(s for s in result.stdout.splitlines() if "error " in s)[:5000])
        raise SystemExit(1)
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe", action="store_true")
    p.add_argument("--build", action="store_true")
    args = p.parse_args()
    if args.build:
        build()
    elif args.probe:
        probe()
    else:
        prepare()
