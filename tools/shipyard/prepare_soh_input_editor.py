"""Project the complete current SoH controller editor against native LUS APIs."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from prepare_archives import stable
from dependency_sources import ROOT
from prepare_configuration import once
from prepare_gui import inherited_window
from prepare_soh_ui import value_expressions
from prepare_randomizer import edits_apply
from prepare_custom_message import escape_literal, literal_bytes
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/soh-input-editor"
OUT = ROOT / "scratch/soh-input-editor-xdk"
BASE = "soh/soh/Enhancements/controls/SohInputEditorWindow"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def project(name, text):
    if name.endswith(".h"):
        text = once(
            text,
            "#include <libultraship/libultraship.h>",
            '#include "ship/window/gui/GuiWindow.h"\n#include'
            ' "ship/controller/controldevice/controller/Controller.h"\n#include'
            ' "ship/controller/controldevice/controller/mapping/ControllerRumbleMapping.h"',
        )
        text = inherited_window(text, "SohInputEditorWindow")
        text = once(
            text,
            "decltype(buttons)::iterator",
            "std::list<std::pair<N64ButtonMask, const char*>>::iterator",
        )
    else:
        text = (
            '#include "ship/controller/controldeck/ControlDeck.h"\n#include'
            ' "ship/window/gui/IconsFontAwesome4.h"\n#include "gui/compat.h"\n#include'
            ' "soh-input-editor/support.h"\n'
            + text
        )
        for member in (
            "mButtonsBitmasks",
            "mDpadBitmasks",
            "mModifierButtonsBitmasks",
            "mCustomOcarinaButtonsBitmasks",
        ):
            text, n = re.subn(
                r"    " + member + r" = (\{[^;]+\});",
                lambda m: "    { const N64ButtonMask values[]="
                + m[1]
                + "; "
                + member
                + "=std::set<N64ButtonMask>(values,values+sizeof(values)/sizeof(values[0])); }",
                text,
            )
            if n != 1:
                raise ValueError("Controller button set drift " + member)
        # Both source initializer ranges have exact static element types. Their
        # temporary container lifetime remains the complete enclosing loop.
        for unused in range(8):
            raw = text.encode()
            found = False
            for node in reversed(list(walk(PARSER.parse(raw).root_node))):
                if node.type != "for_range_loop":
                    continue
                right = node.child_by_field_name("right")
                if right.type != "initializer_list":
                    continue
                value = right.text.decode()
                if value == "{ Ship::LEFT, Ship::RIGHT, Ship::UP, Ship::DOWN }":
                    typ = "Ship::Direction"
                elif "std::make_pair<uint8_t, std::shared_ptr<Ship::ControllerStick>>" in value:
                    typ = "std::pair<uint8_t,std::shared_ptr<Ship::ControllerStick>>"
                else:
                    raise ValueError("Unreviewed controller editor temporary range")
                replacement = (
                    "{ const "
                    + typ
                    + " values[]="
                    + value
                    + "; "
                    + raw[node.start_byte : right.start_byte].decode()
                    + "values"
                    + raw[right.end_byte : node.end_byte].decode()
                    + " }"
                )
                text = edits_apply(raw, [(node.start_byte, node.end_byte, replacement)])
                found = True
                break
            if not found:
                break
        text = re.sub(r"ImVec4 color = \{(.*?)\};", r"ImVec4 color(\1);", text, flags=re.S)
        text = re.sub(r"ImVec4 (\w+) = \{([^{};]+)\};", r"ImVec4 \1(\2);", text)
        text = once(
            text,
            'CVarGetColor24(CVAR_SETTING("LEDPort1Color"), { 255, 255, 255 })',
            'CVarGetColor24(CVAR_SETTING("LEDPort1Color"), Shipyard::GuiCompat::Rgb(255, 255,'
            " 255))",
        )
        text, count = re.subn(
            r'CheckboxOptions\(\{ \{ \.disabled = ([\s\S]*?),\s*\.disabledTooltip = ("[^"]*") \}'
            r" \}\)",
            r"Shipyard::SohInputEditor::DisabledCheckbox(\1, \2)",
            text,
        )
        if count != 2:
            raise ValueError("Checkbox option aggregate count drift")
        text = re.sub(r"Color_RGB8\(\{(.*?)\}\)", r"Shipyard::GuiCompat::Rgb(\1)", text, flags=re.S)
        text = re.sub(
            r"static std::vector<const char\*> ledSources = (\{[\s\S]*?\});",
            r"static const char* ledSourceValues[]=\1;\n                static std::vector<const"
            r" char*>"
            r" ledSources(ledSourceValues,ledSourceValues+sizeof(ledSourceValues)/sizeof(ledSourceValues[0]));",
            text,
        )
        text = re.sub(
            r'(\w+) = \{ \.name = ("[^"]+"), \.type = WidgetType::WIDGET_CVAR_CHECKBOX \};',
            r"\1 = Shipyard::SohInputEditor::Checkbox(\2);",
            text,
        )
        text = re.sub(
            r"AddSearchWidget\((\{[^;]*?\})\)",
            lambda m: "AddSearchWidget(SearchWidget(" + m[1][1:-1] + "))",
            text,
        )
        text = value_expressions(text)
        # Stable configuration identifiers/classes remain SDLGamepad, which is
        # the existing native XInput mapping backend's compatibility identity.
        # Only the visible platform description names the actual backend.
        text = text.replace("Gamepad (SDL)", "Gamepad (XInput)").replace(
            "%s %s (SDL)", "%s %s (XInput)"
        )
    general = runpy.run_path(str(ROOT / "platform/shipyard/input/lowering.py"))
    return '#include "input/compiler.h"\n' + general["syntax"](text, set())


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    outputs = {}
    literals = []
    for name, expected in lock.get("dependencies", {}).items():
        if sha((ROOT / name).read_text(encoding="utf-8-sig")) != expected:
            raise ValueError("Editor dependency source drift " + name)
    for name, expected in lock["sources"].items():
        original = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(original) != expected:
            raise ValueError("SoH input editor drift " + name)
        text = project(name, original)
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type == "string_literal" and any(b >= 128 for b in n.text):
                value = n.text.decode()
                escaped = escape_literal(value)
                edits.append((n.start_byte, n.end_byte, escaped))
                literals.append(
                    dict(original=value, projected=escaped, bytes=literal_bytes(value).hex())
                )
        text = edits_apply(raw, edits)
        stable(OUT / "generated" / name, text)
        outputs[name] = sha(text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                dependencies=lock.get("dependencies", {}),
                generated=outputs,
                literals=literals,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helper_sha256=hashlib.sha256((OWN / "support.h").read_bytes()).hexdigest(),
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    from prepare_soh_ui import includes as base

    return [
        OUT / "generated/soh",
        ROOT / "scratch/soh-menus-xdk/generated/soh",
        ROOT / "scratch/soh-ui-xdk/generated/soh",
        ROOT / "scratch/soh-menus-xdk/generated/soh/soh/SohGui",
        ROOT / "scratch/soh-ui-xdk/generated/soh/soh/SohGui",
        ROOT / "scratch/application-xdk/generated/soh",
    ] + base()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/soh-ui-xdk/xdk/build.json").read_text())[0]["command"][:-2]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    source = OUT / "generated" / (BASE + ".cpp")
    obj = folder / "SohInputEditorWindow.obj"
    command = flags + [str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), result.stdout + result.stderr)
    row = dict(
        source=source.relative_to(ROOT).as_posix(),
        command=command,
        exit=result.returncode,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    if not result.returncode:
        assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
        row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
    else:
        print(
            "\n".join(s for s in (result.stdout + result.stderr).splitlines() if "error " in s)[
                :6500
            ],
            flush=True,
        )
    stable(folder / "build.json", json.dumps([row], indent=2) + "\n")
    print("SohInputEditorWindow: " + str(result.returncode), flush=True)
    if result.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
