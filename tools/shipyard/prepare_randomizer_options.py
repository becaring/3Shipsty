"""Option and settings declarations and the option implementation."""

import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply, inventory, lower_defaults, function_nodes
from prepare_soh_ui import common
from prepare_binary import strong_enum
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/randomizer-options"
OUT = ROOT / "scratch/randomizer-options-xdk"
BASE = "soh/soh/Enhancements/randomizer/"
NAMES = ["Option", "LocationOption", "TrickSetting", "OptionGroup"]

# The 9.2.3 Option copies raw pointers into its own strings. A Settings
# assignment from an Option::U8 temporary then destroys the strings they name.
# Keep the source hash-locked and repair ownership in the projected class only.
COPY_DECLARATIONS = """    Option(const Option& other);
    Option& operator=(const Option& other);
"""
COPY_REBIND = """void Option::RebindCopiedPointers(const Option& source) {
    optionsMap.clear();
    for (size_t i = 0; i < options.size(); ++i) {
        optionsMap.insert(std::make_pair(static_cast<int32_t>(i), options[i].c_str()));
    }
    if (source.widgetOptions) {
        switch (widgetType) {
            case WIDGET_CVAR_CHECKBOX:
                widgetOptions = std::make_shared<UIWidgets::CheckboxOptions>(
                    *static_cast<UIWidgets::CheckboxOptions*>(source.widgetOptions.get()));
                break;
            case WIDGET_CVAR_COMBOBOX: {
                std::shared_ptr<UIWidgets::ComboboxOptions> combo =
                    std::make_shared<UIWidgets::ComboboxOptions>(
                        *static_cast<UIWidgets::ComboboxOptions*>(source.widgetOptions.get()));
                combo->comboMap = optionsMap;
                widgetOptions = combo;
                break;
            }
            case WIDGET_CVAR_SLIDER_INT: {
                std::shared_ptr<UIWidgets::IntSliderOptions> slider =
                    std::make_shared<UIWidgets::IntSliderOptions>(
                        *static_cast<UIWidgets::IntSliderOptions*>(source.widgetOptions.get()));
                for (size_t i = 0; i < source.options.size() && i < options.size(); ++i) {
                    if (slider->format == source.options[i].c_str()) {
                        slider->format = options[i].c_str();
                        break;
                    }
                }
                widgetOptions = slider;
                break;
            }
            default:
                widgetOptions = source.widgetOptions;
                break;
        }
        if (widgetOptions != source.widgetOptions) {
            widgetOptions->tooltip = description.c_str();
            if (widgetOptions->disabledTooltip == source.disabledText.c_str()) {
                widgetOptions->disabledTooltip = disabledText.c_str();
            }
        }
    }
    if (source.widgetInfo.options == source.widgetOptions && source.widgetInfo.options) {
        widgetInfo.options = widgetOptions;
    }
    if (source.widgetInfo.options) widgetInfo.cVar = cvarName.c_str();
}

Option::Option(const Option& other) {
    *this = other;
}

Option& Option::operator=(const Option& other) {
    if (this == &other) return *this;
    key = other.key;
    name = other.name;
    options = other.options;
    contextSelection = other.contextSelection;
    delayedSelection = other.delayedSelection;
    hidden = other.hidden;
    category = other.category;
    cvarName = other.cvarName;
    description = other.description;
    widgetType = other.widgetType;
    defaultOption = other.defaultOption;
    defaultHidden = other.defaultHidden;
    imFlags = other.imFlags;
    disabled = other.disabled;
    disabledText = other.disabledText;
    optionsTextToVar = other.optionsTextToVar;
    widgetOptions = other.widgetOptions;
    // The upstream constructor leaves WidgetInfo's primitive fields uninitialized
    // until AddWidget runs. Do not read them when copying an unregistered option.
    if (other.widgetInfo.options) {
        widgetInfo = other.widgetInfo;
    } else {
        widgetInfo = WidgetInfo(Shipyard::SohUI::ValueInit());
    }
    callback = other.callback;
    RebindCopiedPointers(other);
    return *this;
}

"""


def enums(text):
    return re.sub(
        r"enum class (OptionCategory|OptionGroupType|WidgetContainerType|Tag) \{(.*?)\};",
        lambda m: strong_enum(m[1], m[2]),
        text,
        flags=re.S,
    )


def default_constructors(text):
    raw = text.encode()
    edits = []
    audit = {}
    for cls in walk(PARSER.parse(raw).root_node):
        if (
            cls.type != "class_specifier"
            or cls.child_by_field_name("name").text.decode() not in NAMES
        ):
            continue
        name = cls.child_by_field_name("name").text.decode()
        body = cls.child_by_field_name("body")
        normal = []
        valued = []
        members = []
        if name in ("LocationOption", "TrickSetting"):
            normal.append("Option()")
            valued.append("Option(Shipyard::SohUI::ValueInit())")
        for field in body.named_children:
            if field.type != "field_declaration":
                continue
            d = field.child_by_field_name("declarator")
            if d is None or d.type != "field_identifier":
                continue
            member = d.text.decode()
            typ = field.child_by_field_name("type").text.decode()
            value = field.child_by_field_name("default_value")
            expr = value.text.decode() if value else None
            if expr == "{}":
                expr = ""
            if value:
                normal.append(member + "(" + expr + ")")
                eq = next(c for c in field.children if c.type == "=")
                edits.append((eq.start_byte, value.end_byte, ""))
            fallback = (
                "Shipyard::SohUI::ValueInit()"
                if typ == "WidgetInfo" or typ == "struct WidgetInfo"
                else ""
            )
            valued.append(member + "(" + (expr if value else fallback) + ")")
            members.append(
                dict(name=member, type=typ, default=value.text.decode() if value else None)
            )
        old = name + "() = default;"
        where = raw.find(old.encode(), body.start_byte, body.end_byte)
        if where < 0:
            raise ValueError("Missing real default ctor " + name)
        ctor = name + "()" + (" : " + ", ".join(normal) if normal else "") + " {}\n"
        ctor += (
            "    explicit "
            + name
            + "(Shipyard::SohUI::ValueInit)"
            + (" : " + ", ".join(valued) if valued else "")
            + " {}"
        )
        edits.append((where, where + len(old), ctor))
        audit[name] = members
    if set(audit) != set(NAMES):
        raise ValueError("Option class inventory changed")
    return edits_apply(raw, edits), audit


def value_expressions(text):
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type == "init_declarator":
            value = n.child_by_field_name("value")
            parent = n.parent
            typ = parent.child_by_field_name("type") if parent.type == "declaration" else None
            if value and typ and value.text == b"{}" and typ.text.decode().split("::")[-1] in NAMES:
                eq = "" if any(c.type == "=" for c in n.children) else "= "
                edits.append(
                    (
                        value.start_byte,
                        value.end_byte,
                        eq + typ.text.decode() + "(Shipyard::SohUI::ValueInit())",
                    )
                )
        if n.type not in ("call_expression", "compound_literal_expression"):
            continue
        typ = n.child_by_field_name("function") or n.child_by_field_name("type")
        args = n.child_by_field_name("arguments") or n.child_by_field_name("value")
        if (
            typ is not None
            and args is not None
            and not args.named_children
            and typ.text.decode().split("::")[-1] in NAMES
        ):
            edits.append(
                (n.start_byte, n.end_byte, typ.text.decode() + "(Shipyard::SohUI::ValueInit())")
            )
    return edits_apply(raw, edits)


def project_option_source(text, defaults, gui_header):
    nodes = function_nodes(text, "OptionValue::")
    if len(nodes) != 4:
        raise ValueError("Expected canonical four OptionValue methods")
    text = edits_apply(
        text.encode(),
        [
            (n.start_byte, n.end_byte, "// Defined in canonical randomizer OptionValue.cpp.")
            for n in nodes
        ],
    )
    text = lower_defaults(text, defaults, [])
    text = once(
        text,
        '#include "soh/Enhancements/randomizer/settings.h"',
        "// This TU does not use Settings.",
    )
    # Full SohMenu is supplied by the menu provider. These are the only
    # two SohGui.hpp contracts used here; no implementation or class is replaced.
    declaration = re.findall(r"^UIWidgets::Colors GetMenuThemeColor\(\);$", gui_header, re.M)
    macro = re.findall(r"^#define THEME_COLOR .+$", gui_header, re.M)
    if len(declaration) != 1 or len(macro) != 1:
        raise ValueError("Exact SohGui theme contract changed")
    text = once(
        text,
        '#include "soh/SohGui/SohGui.hpp"',
        "namespace SohGui { " + declaration[0] + " }\n" + macro[0],
    )
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if (
            n.type != "return_statement"
            or not n.named_children
            or n.named_children[0].type != "initializer_list"
        ):
            continue
        parent = n.parent
        while parent and parent.type != "function_definition":
            parent = parent.parent
        if parent is None:
            raise ValueError("Return without function")
        typ = parent.child_by_field_name("type").text.decode()
        if typ not in ("Option", "TrickSetting", "OptionGroup"):
            raise ValueError("Unmapped braced return " + typ)
        value = n.named_children[0]
        edits.append(
            (value.start_byte, value.end_byte, typ + "(" + value.text.decode()[1:-1] + ")")
        )
    text = edits_apply(raw, edits)
    for a, b in [("Off", "On"), ("Disabled", "Enabled"), ("Included", "Excluded")]:
        text = text.replace(
            '{ "' + a + '", "' + b + '" }',
            'Shipyard::RandomizerOptions::StringOptions("' + a + '", "' + b + '")',
        )
    text = text.replace(
        "optionsTextToVar.contains(text)", "(optionsTextToVar.find(text) != optionsTextToVar.end())"
    )
    text = text.replace("mTags.contains(tag)", "(mTags.find(tag) != mTags.end())")
    text = once(
        text,
        "optionsMap.emplace(i, options[i].c_str());",
        "optionsMap.insert(std::make_pair(i, options[i].c_str()));",
    )
    text = once(text, "Option::Option(size_t key_,", COPY_REBIND + "Option::Option(size_t key_,")
    return "#include <cassert>\n" + common(value_expressions(text))


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    for n, h in lock["sources"].items():
        text = (ROOT / n).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != h:
            raise ValueError("Option source drift " + n)
        texts[n] = text
    for n, h in lock.get("dependencies", {}).items():
        text = (ROOT / n).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != h:
            raise ValueError("Option dependency drift " + n)
        texts[n] = text
    option = texts[BASE + "option.h"]
    defaults = inventory(option)
    cls = next(
        n
        for n in walk(PARSER.parse(option.encode()).root_node)
        if n.type == "class_specifier" and n.child_by_field_name("name").text == b"OptionValue"
    )
    option = edits_apply(
        option.encode(),
        [
            (
                cls.start_byte,
                cls.end_byte + 1,
                "// Complete class comes from the single canonical OptionValue.h.",
            )
        ],
    )
    option = once(
        option,
        '#include "randomizerTypes.h"',
        '#include "soh/Enhancements/randomizer/randomizerTypes.h"\n#include'
        ' "soh/Enhancements/randomizer/OptionValue.h"\n#include "randomizer-options/support.h"',
    )
    option = once(
        option,
        'options_ = { "Off", "On" }',
        'options_ = Shipyard::RandomizerOptions::StringOptions("Off", "On")',
    )
    option = once(option, "    Option() = default;", COPY_DECLARATIONS + "    Option() = default;")
    option = once(
        option,
        "    bool RenderCheckbox();",
        "    void RebindCopiedPointers(const Option& source);\n    bool RenderCheckbox();",
    )
    option, audit = default_constructors(option)
    option = enums(option)
    tricks = enums(texts[BASE + "tricks.h"]).replace(
        '#include "randomizerTypes.h"',
        '#include "soh/Enhancements/randomizer/randomizerTypes.h"\n#include "binary/compat.h"',
    )
    settings = texts[BASE + "settings.h"]
    settings = once(settings, '#include "SeedContext.h"', "namespace Rando { class Context; }")
    settings = once(
        settings,
        '#include "randomizerTypes.h"',
        '#include "soh/Enhancements/randomizer/randomizerTypes.h"',
    )
    settings = once(
        settings,
        '#include "3drando/spoiler_log.hpp"',
        "// Spoiler-log declarations are not used by this Settings class declaration.",
    )
    setting_defaults = inventory(settings)
    settings = lower_defaults(settings, setting_defaults, [])
    settings_source = lower_defaults(texts[BASE + "settings.cpp"], setting_defaults, [])
    nodes = function_nodes(settings_source, "Settings::Settings")
    if len(nodes) != 1:
        raise ValueError("Settings ctor inventory changed")
    node = nodes[0]
    body = node.child_by_field_name("body")
    ctor = node.text.decode()
    ctor = (
        ctor[: body.start_byte - node.start_byte + 1]
        + "\n    Shipyard::RandomizerOptions::ValueInitializeArray(mOptions);\n   "
        " Shipyard::RandomizerOptions::ValueInitializeArray(mTrickSettings);\n"
        + ctor[body.start_byte - node.start_byte + 1 :]
    )
    settings_source = edits_apply(
        settings_source.encode(),
        [(node.start_byte, node.end_byte, "// Defined in canonical SettingsConstructor.cpp.")],
    )
    projected = {
        "option.h": option,
        "tricks.h": tricks,
        "settings.h": settings,
        "option.cpp": project_option_source(
            texts[BASE + "option.cpp"], defaults, texts["soh/soh/SohGui/SohGui.hpp"]
        ),
        "settings.cpp": settings_source,
        "SettingsConstructor.cpp": '#include "settings.h"\nnamespace Rando {\n' + ctor + "\n}\n",
    }
    for n, text in projected.items():
        stable(OUT / "generated" / BASE / n, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                dependencies=lock.get("dependencies", {}),
                member_inventory=audit,
                member_defaults=defaults,
                settings_defaults=setting_defaults,
                generated={n: hashlib.sha256(t.encode()).hexdigest() for n, t in projected.items()},
                full_settings_cpp_compiled=False,
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    from prepare_soh_ui import includes as ui_includes

    return [
        OUT / "generated/soh",
        ROOT / "scratch/soh-menus-xdk/generated/soh",
        ROOT / "scratch/soh-ui-xdk/generated/soh/soh/SohGui",
        ROOT / "scratch/randomizer-xdk/generated" / BASE,
    ] + ui_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/soh-ui-xdk/xdk/build.json").read_text())[0]["command"][:-2]
    flags[1:1] = ["/I" + str(p) for p in includes()[:4]]
    source = folder / "declarations.cpp"
    stable(
        source,
        '#include "soh/Enhancements/randomizer/settings.h"\nvoid Probe(){Rando::Option'
        " a;Rando::Option b((Shipyard::SohUI::ValueInit()));Rando::Settings s;}\n",
    )
    rows = []
    for path in [source] + [
        OUT / "generated" / BASE / n for n in ("option.cpp", "SettingsConstructor.cpp")
    ]:
        obj = folder / (path.stem + ".obj")
        command = flags + [str(path), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        rows.append(
            dict(
                source=path.relative_to(ROOT).as_posix(),
                command=command,
                exit=r.returncode,
                production=path != source,
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                object_sha256=(
                    hashlib.sha256(obj.read_bytes()).hexdigest() if not r.returncode else None
                ),
            )
        )
        print(path.name, r.returncode)
        if r.returncode:
            print("\n".join(s for s in r.stdout.splitlines() if "error " in s)[:5000])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
