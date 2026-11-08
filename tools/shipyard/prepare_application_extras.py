"""Pinned application extras, with a narrow, reproducible XDK syntax rewrite."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/application-extras"
OUT = ROOT / "scratch/application-extras-xdk"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def project(name, text):
    from prepare_application_windows import project as base

    if name.endswith(".h"):
        return preproject(name, text)
    text = preproject(name, text)
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "call_expression":
            continue
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments").named_children
        if (
            not fn.text.startswith(b"UIWidgets::")
            or not fn.text.endswith(b"Options")
            or len(args) != 1
            or args[0].type != "initializer_list"
        ):
            continue
        fields = [x for x in walk(args[0]) if x.type == "initializer_pair"]
        if not fields:
            continue
        expression = "UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit())"
        for f in fields:
            field = next(c for c in walk(f) if c.type == "field_identifier").text.decode()
            value = f.child_by_field_name("value").text.decode()
            expression += "." + field[0].upper() + field[1:] + "(" + value + ")"
        edits.append((args[0].start_byte, args[0].end_byte, expression))
    text = edits_apply(raw, edits)
    text = base(name, text)
    text = postproject(name, text)
    text = text.replace(
        "#include <libultraship/classes.h>", "// Actual LUS interfaces included explicitly below."
    )
    return (
        '#include "application-extras/support.h"\n#include "ship/Context.h"\n#include'
        ' "ship/window/Window.h"\n#include "ship/window/gui/ConsoleWindow.h"\n#include'
        ' "soh/Enhancements/randomizer/SeedContext.h"\n#include'
        ' "soh/Enhancements/randomizer/randomizer.h"\n#include'
        ' "soh/Enhancements/custom-message/CustomMessageManager.h"\n#include'
        ' "soh/Enhancements/custom-message/CustomMessageTypes.h"\n'
        + text
    )


def preproject(name, text):
    if name.endswith("Mouse.h"):
        return text.replace(
            "#include <libultraship/libultraship.h>", "#include <libultraship/bridge.h>"
        )
    if name.endswith("Presets.h"):
        return text.replace("= {}", "= std::vector<PresetSection>()")
    if name.endswith("/InputViewer.cpp"):
        text = '#include "imgui_internal.h"\n' + text
        anchor = (
            '        if (pads != nullptr && ImGui::Begin("Input Viewer", nullptr, windowFlags)) {'
        )
        # The Xbox pointer exists while the menu is open. Keep the draggable
        # overlay reachable above that menu without stealing navigation focus.
        text = once(
            text,
            anchor,
            anchor
            + """
            if (Ship::Context::GetInstance()->GetWindow()->GetGui()->GetMenuOrMenubarVisible() &&
                CVarGetInteger(CVAR_INPUT_VIEWER("EnableDragging"), 1) &&
                ImGui::GetTopMostPopupModal() == nullptr) {
                ImGui::BringWindowToDisplayFront(ImGui::GetCurrentWindow());
            }
""",
        )
    if name.endswith("/mod_menu.cpp"):
        # Mods load only at startup, so Apply & Close restarts the game on the console.
        close = (
            "                                      Ship::Context::GetInstance()->GetConsoleVariables()->Save();\n"
            "                                      Ship::Context::GetInstance()->GetWindow()->Close();"
        )
        text = once(text, close, close.replace("Ship::Context::GetInstance()->GetWindow()",
                                               "Shipyard::Platform::RequestRelaunch();\n"
                                               "                                      Ship::Context::GetInstance()->GetWindow()", 1))
        text = '#include "context/platform.h"\n' + text
    text = text.replace("std::filesystem", "xbox_compat::filesystem")
    text = text.replace(
        "std::reinterpret_pointer_cast<", "Shipyard::GuiCompat::ReinterpretPointerCast<"
    )
    text = re.sub(r"\bconstexpr\b", "const", text)
    text = text.replace("[[fallthrough]]", "/* fall through */")
    text = text.replace(
        "[item](const SplitObject& split) {", "[item](const SplitObject& split) -> bool {"
    )
    text = text.replace("switch (rtn)", "switch (rtn.GetValue())")
    text = re.sub(
        r"(\b(?:ammoItems|bottleItems|inventoryItems|questItems|equipmentItems))\s*\{",
        r"\1 = {",
        text,
    )
    text = re.sub(r"(const static std::map<[^\n]+?>\s+\w+)\s*\{", r"\1 = {", text)
    text = re.sub(
        r"(?m)^(\s*)vanillaQueuedItemEntry = GET_ITEM_NONE;",
        r"\1{ const GetItemEntry empty = GET_ITEM_NONE; vanillaQueuedItemEntry = empty; }",
        text,
    )
    if name.endswith("BossRush.cpp"):
        raw = text.encode()
        outer = next(
            n
            for n in walk(PARSER.parse(raw).root_node)
            if n.type == "function_definition"
            and n.child_by_field_name("declarator").text.startswith(b"RegisterBossRush")
        )
        lam = next(n for n in walk(outer) if n.type == "lambda_expression")
        assert lam.child_by_field_name("captures").text == b"[]"
        body = lam.child_by_field_name("body").text.decode()
        text = edits_apply(
            raw,
            [
                (
                    outer.start_byte,
                    outer.start_byte,
                    "static void ShipyardBossRushOnLoad(int32_t fileNum) " + body + "\n",
                ),
                (lam.start_byte, lam.end_byte, "ShipyardBossRushOnLoad"),
            ],
        )
    # Filesystem iterators are ranges by free begin/end in standard C++, and directly iterators here.
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "for_range_loop":
            continue
        value = n.child_by_field_name("right")
        if value is None or not re.match(
            r"(?:fs|xbox_compat::filesystem)::(?:recursive_)?directory_iterator\(",
            value.text.decode(),
        ):
            continue
        kind = value.child_by_field_name("function").text.decode()
        var = n.child_by_field_name("declarator").text.decode().lstrip("&")
        body = n.child_by_field_name("body")
        assert body.type == "compound_statement"
        edits.append(
            (
                n.start_byte,
                body.start_byte,
                "for ("
                + kind
                + " shipyardDirectory = "
                + value.text.decode()
                + ";shipyardDirectory != "
                + kind
                + "();++shipyardDirectory) ",
            )
        )
        edits.append(
            (
                body.start_byte + 1,
                body.start_byte + 1,
                "const auto& " + var + " = *shipyardDirectory;",
            )
        )
    text = edits_apply(raw, edits)
    text = text.replace("return {};", "return std::vector<std::string>();")
    text = text.replace("presets[newPresetName] = {};", "presets[newPresetName] = PresetInfo();")
    text = re.sub(
        r'#include "((?:game-interactor|randomizer)/[^\"]+)"',
        r'#include "soh/Enhancements/\1"',
        text,
    )
    text = re.sub(r"WidgetPath (\w+) = \{([^{}]+)\};", r"WidgetPath \1(\2);", text)
    text = re.sub(r"\[\]\(NameTag a, NameTag b\) \{", r"[](NameTag a, NameTag b) -> bool {", text)
    text = text.replace(
        "NameTag_RegisterForActorWithOptions(actor, text, {});",
        "NameTag_RegisterForActorWithOptions(actor, text, NameTagOptions());",
    )
    # JSON items() proxies use modern iterator machinery. Preserve key/value iteration via JSON iterators.
    text = re.sub(
        r"for \(auto& (\w+) : ([^;\n]+)\.items\(\)\) \{",
        lambda m: "for (auto "
        + m[1]
        + " = "
        + m[2]
        + ".begin(); "
        + m[1]
        + " != "
        + m[2]
        + ".end(); ++"
        + m[1]
        + ") {",
        text,
    )
    if name.endswith("/Presets.cpp"):
        text = text.replace(
            "bool isBuiltIn = false;",
            "PresetInfo():isBuiltIn(false){ std::fill(apply,apply+PRESET_SECTION_MAX,false); }\n   "
            " bool isBuiltIn;",
        )
    # Convert vector-valued aggregate members using temporary backing arrays.
    targets = {
        "BossRush.cpp": ("BossRushOptions", 1, "std::array<std::string, LANGUAGE_MAX>"),
        "Presets.cpp": ("blockInfo", 0, "std::string"),
        "TimeSplits.cpp": ("popupList", 1, "uint32_t"),
    }
    leaf = Path(name).name
    if leaf in targets:
        ident, index, element = targets[leaf]
        raw = text.encode()
        edits = []
        helpers = []
        init = next(
            n
            for n in walk(PARSER.parse(raw).root_node)
            if n.type == "init_declarator"
            and n.child_by_field_name("declarator").text.decode().split("[")[0] == ident
        )
        value = init.child_by_field_name("value")
        for i, row in enumerate(c for c in value.named_children if c.type != "comment"):
            entry = [c for c in row.named_children if c.type != "comment"][index]
            assert entry.type == "initializer_list"
            helper = "Shipyard_" + ident + "_" + str(i)
            kind = "std::vector<" + element + ">"
            helpers.append(
                "static "
                + kind
                + " "
                + helper
                + "(){ "
                + (
                    "const "
                    + element
                    + " rows[]="
                    + entry.text.decode()
                    + "; return "
                    + kind
                    + "(rows,rows+sizeof(rows)/sizeof(rows[0]));"
                    if entry.named_children
                    else "return " + kind + "();"
                )
                + " }\n"
            )
            edits.append((entry.start_byte, entry.end_byte, helper + "()"))
        edits.append((init.parent.start_byte, init.parent.start_byte, "".join(helpers)))
        text = edits_apply(raw, edits)
    if leaf == "debugconsole.cpp":
        raw = text.encode()
        edits = []
        init = next(
            n
            for n in walk(PARSER.parse(raw).root_node)
            if n.type == "init_declarator"
            and n.child_by_field_name("declarator").text == b"cosmetic_groups"
        )
        for row in init.child_by_field_name("value").named_children[0].named_children:
            if row.type == "initializer_list":
                edits.append(
                    (
                        row.start_byte,
                        row.end_byte,
                        "std::pair<const char*,CosmeticGroup>(" + row.text.decode()[1:-1] + ")",
                    )
                )
        text = edits_apply(raw, edits)
    if leaf == "TimeDisplay.cpp":
        raw = text.encode()
        edits = []
        init = next(
            n
            for n in walk(PARSER.parse(raw).root_node)
            if n.type == "init_declarator"
            and n.child_by_field_name("declarator").text == b"digitList"
        )
        for row in init.child_by_field_name("value").named_children:
            if row.type == "initializer_list":
                edits.append(
                    (
                        row.start_byte,
                        row.end_byte,
                        "std::pair<std::string,const char*>(" + row.text.decode()[1:-1] + ")",
                    )
                )
        text = edits_apply(raw, edits)
    if leaf == "customequipment.cpp":
        text = text.replace(
            "std::initializer_list<const char*>", "std::vector<const char*>"
        ).replace("std::initializer_list<PatchEntry>", "std::vector<PatchEntry>")
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "call_expression":
                continue
            f = n.child_by_field_name("function").text.decode()
            if f not in ("ResolveCustomChain", "ApplyPatchEntries", "UnpatchGroup"):
                continue
            for a in n.child_by_field_name("arguments").named_children:
                if a.type != "initializer_list":
                    continue
                element = "PatchEntry" if f == "ApplyPatchEntries" else "const char*"
                kind = "std::vector<" + element + ">"
                edits.append(
                    (
                        a.start_byte,
                        a.end_byte,
                        "[&]() -> "
                        + kind
                        + " { const "
                        + element
                        + " rows[]="
                        + a.text.decode()
                        + "; return "
                        + kind
                        + "(rows,rows+sizeof(rows)/sizeof(rows[0])); }()",
                    )
                )
        text = edits_apply(raw, edits)
    raw = text.encode()
    edits = []
    arraytypes = {
        n.child_by_field_name("declarator").text.decode(): (
            n.child_by_field_name("type").text.decode()
        )
        for n in walk(PARSER.parse(raw).root_node)
        if n.type == "declaration"
        and n.child_by_field_name("type") is not None
        and n.child_by_field_name("type").text.startswith(b"std::array<")
        and n.child_by_field_name("declarator") is not None
        and n.child_by_field_name("declarator").type == "identifier"
    }
    arraytypes["brAmmo"] = "std::array<s8,16>"
    for n in walk(PARSER.parse(raw).root_node):
        if (
            n.type == "assignment_expression"
            and n.child_by_field_name("right").type == "initializer_list"
        ):
            left = n.child_by_field_name("left").text.decode()
            val = n.child_by_field_name("right").text.decode()
            if left in arraytypes:
                assert n.parent.type == "expression_statement"
                edits.append(
                    (
                        n.parent.start_byte,
                        n.parent.end_byte,
                        "{ const "
                        + arraytypes[left]
                        + " assigned="
                        + val
                        + ";"
                        + left
                        + "=assigned; }",
                    )
                )
        if (
            n.type == "compound_literal_expression"
            and n.child_by_field_name("type").text == b"nlohmann::json"
        ):
            value = n.child_by_field_name("value")
            assign = []
            for row in value.named_children:
                if row.type == "comment":
                    continue
                args = [c for c in row.named_children if c.type != "comment"]
                assert len(args) == 2
                assign.append(
                    "result[" + args[0].text.decode() + "]=" + args[1].text.decode() + ";"
                )
            edits.append(
                (
                    n.start_byte,
                    n.end_byte,
                    "[&]() -> nlohmann::json { nlohmann::json result=nlohmann::json::object();"
                    + "".join(assign)
                    + "return result; }()",
                )
            )
        if n.type == "initializer_list" and n.parent.type == "argument_list":
            fnode = n.parent.parent.child_by_field_name("function")
            if fnode is None:
                continue
            fn = fnode.text.decode()
            if fn == "CMD_REGISTER" or fn.endswith("->AddCommand"):
                fields = [x for x in n.named_children if x.type != "comment"]
                assert len(fields) in (2, 3)
                expression = (
                    "[&]() -> Ship::CommandEntry { Ship::CommandEntry entry; entry.Handler="
                    + fields[0].text.decode()
                    + ";entry.Description="
                    + fields[1].text.decode()
                    + ";"
                )
                if len(fields) == 3:
                    for a in fields[2].named_children:
                        if a.type == "comment":
                            continue
                        expression += (
                            "entry.Arguments.push_back(Ship::CommandArgument("
                            + ",".join(
                                c.text.decode() for c in a.named_children if c.type != "comment"
                            )
                            + "));"
                        )
                expression += "return entry;}()"
                edits.append((n.start_byte, n.end_byte, expression))
            elif fn.endswith("->AddRequest"):
                fields = [x for x in n.named_children if x.type != "comment"]
                assert len(fields) == 2
                edits.append(
                    (
                        n.start_byte,
                        n.end_byte,
                        "SaveStateRequest(" + ",".join(c.text.decode() for c in fields) + ")",
                    )
                )
            elif fn == "ImGui::PushStyleColor":
                edits.append((n.start_byte, n.end_byte, "ImVec4(" + n.text.decode()[1:-1] + ")"))
            elif fn == "ImGui::PushStyleVar":
                edits.append((n.start_byte, n.end_byte, "ImVec2(" + n.text.decode()[1:-1] + ")"))
            elif fn.endswith(".Padding"):
                edits.append((n.start_byte, n.end_byte, "ImVec2(" + n.text.decode()[1:-1] + ")"))
            elif fn == "UIWidgets::Checkbox":
                fields = [x for x in n.named_children if x.type == "initializer_pair"]
                expression = "UIWidgets::CheckboxOptions(Shipyard::SohUI::ValueInit())"
                for f in fields:
                    field = next(c for c in walk(f) if c.type == "field_identifier").text.decode()
                    v = f.child_by_field_name("value")
                    value = v.text.decode()
                    value = "ImVec2(" + value[1:-1] + ")" if field == "padding" else value
                    expression += "." + field[0].upper() + field[1:] + "(" + value + ")"
                edits.append((n.start_byte, n.end_byte, expression))
            elif fn.endswith("->SetMousePos"):
                edits.append(
                    (
                        n.start_byte,
                        n.end_byte,
                        "Shipyard::ApplicationExtras::Coords(" + n.text.decode()[1:-1] + ")",
                    )
                )
            elif fn.endswith("Options"):
                fields = [x for x in walk(n) if x.type == "initializer_pair"]
                if not fields:
                    continue
                expression = "UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit())"
                for f in fields:
                    field = next(c for c in walk(f) if c.type == "field_identifier").text.decode()
                    value = f.child_by_field_name("value").text.decode()
                    expression += "." + field[0].upper() + field[1:] + "(" + value + ")"
                edits.append((n.start_byte, n.end_byte, expression))
        if (
            n.type == "call_expression"
            and n.child_by_field_name("function").text.startswith(b"gs")
            and n.parent.type == "argument_list"
        ):
            edits.append(
                (
                    n.start_byte,
                    n.end_byte,
                    "[&]() -> Gfx { Gfx command=" + n.text.decode() + ";return command;}()",
                )
            )
    return edits_apply(raw, edits)


def postproject(name, text):
    if name.endswith("/Presets.cpp"):
        # Load() reloads from disk and clears all live CVars. Flush pending
        # menu/settings edits before applying only the selected preset blocks.
        text = once(
            text,
            "void applyPreset(std::string presetName, std::vector<PresetSection>"
            " includeSections) {",
            "void applyPreset(std::string presetName, std::vector<PresetSection> includeSections)"
            " {\n    CVarSave();",
        )
        begin = text.index(
            "            for (auto item = section.begin(); item != section.end(); ++item) {",
            text.index("void applyPreset("),
        )
        end = text.index("            if (i == PRESET_SECTION_RANDOMIZER) {", begin)
        original = text[begin:end]
        if (
            original.count("GetNestedJson()") != 1
            or original.count("SetBlock(") != 1
            or original.count("->Load();") != 1
        ):
            raise ValueError("Preset application boundary drift")
        # Only object blocks with simple names and an existing object CVars
        # root can be grouped. Keep the original sequence for erase, dotted
        # names, primitive merge inputs, and one-block sections.
        batch = (
            """            auto presetConfig = Ship::Context::GetInstance()->GetConfig();
            bool batchable = section.is_object() && section.size() > 1;
            if (batchable) {
                for (auto item = section.begin(); item != section.end(); ++item) {
                    if (item.key().find('.') != std::string::npos || !item.value().is_object()) {
                        batchable = false;
                        break;
                    }
                }
            }
            nlohmann::json currentJson;
            if (batchable) {
                currentJson = presetConfig->GetNestedJson();
                batchable = currentJson.contains("CVars") && currentJson["CVars"].is_object();
                if (batchable && sectionStrategy == "merge") {
                    for (auto item = section.begin(); item != section.end(); ++item) {
                        if (currentJson["CVars"].contains(item.key()) &&
                            !currentJson["CVars"][item.key()].is_object()) {
                            batchable = false;
                            break;
                        }
                    }
                }
            }
            if (batchable) {
                nlohmann::json blocks = currentJson["CVars"];
                for (auto item = section.begin(); item != section.end(); ++item) {
                    nlohmann::json block = item.value();
                    if (sectionStrategy == "merge" && blocks.contains(item.key())) {
                        block = blocks[item.key()];
                        block.update(item.value(), true);
                    }
                    blocks[item.key()] = block;
                }
                presetConfig->SetBlock("CVars", blocks);
                Ship::Context::GetInstance()->GetConsoleVariables()->Load();
            } else {
"""
            + original
            + """            }
"""
        )
        text = text[:begin] + batch + text[end:]
    text = text.replace("fileList = {};", "fileList.clear();")
    text = text.replace(", PRESET_SECTION_MAX,", ", static_cast<size_t>(PRESET_SECTION_MAX),")
    text = text.replace(
        'result["splitTimeStatus"]=SPLIT_STATUS_INACTIVE;',
        'result["splitTimeStatus"]=static_cast<int>(SPLIT_STATUS_INACTIVE);',
    )
    text = text.replace(
        '["fileType"] = FILE_TYPE_PRESET', '["fileType"] = static_cast<int>(FILE_TYPE_PRESET)'
    )
    text = re.sub(
        r'(\w+) = \{ \.name = ("[^"]+"),\s*\.type = WidgetType::(\w+) \};',
        r"\1 = Shipyard::ApplicationEditors::Widget(\2, WidgetType::\3);",
        text,
    )
    text = re.sub(
        r"AddSearchWidget\(\s*(\{[^;]*?\})\)",
        lambda m: "AddSearchWidget(SearchWidget(" + m[1][1:-1] + "))",
        text,
    )
    text = re.sub(
        r"(filePaths|tempMods).emplace\(([^,]+),([^;]+)\);",
        r"\1.insert(std::make_pair(\2,\3));",
        text,
    )
    return text


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    outputs = {}
    for name, digest in lock.get("dependencies", {}).items():
        if sha((ROOT / name).read_text(encoding="utf-8-sig")) != digest:
            raise ValueError("Application extras dependency source drift " + name)
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(text) != digest:
            raise ValueError("Application extras source drift " + name)
        text = project(name, text)
        stable(OUT / "generated" / name, text)
        outputs[name] = sha(text)
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_application_windows.py",
            "prepare_gameplay_features.py",
            "prepare_application_editors.py",
            "prepare_archives.py",
            "prepare_configuration.py",
            "prepare_enhancements.py",
            "prepare_game_interactor.py",
            "prepare_resource_manager.py",
            "prepare_custom_message.py",
            "prepare_soh_ui.py",
            "prepare_randomizer.py",
            "cpp_ast.py",
        )
    ] + [
        ROOT / "platform/shipyard/imgui/projection.py",
        ROOT / "platform/shipyard/input/lowering.py",
        OWN / "support.h",
    ]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                dependencies=lock.get("dependencies", {}),
                generated=outputs,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                projection_helpers={
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in helpers
                },
            ),
            indent=2,
        )
        + "\n",
    )
    return [n for n in outputs if n.endswith(".cpp")]


def includes():
    from prepare_gameplay_features import includes as base

    return [
        OUT / "generated/soh",
        ROOT / "scratch/application-windows-xdk/generated/soh",
        ROOT / "scratch/application-gui-xdk/generated/soh",
        ROOT / "scratch/app-services-xdk/generated/soh",
        ROOT / "scratch/randomizer-context-xdk/generated/soh",
        ROOT / "scratch/stormlib-xdk/generated/src",
    ] + base()


def build(only=None, failed=False):
    units = prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    previous = (
        json.loads((folder / "build.json").read_text())
        if (only or failed) and (folder / "build.json").exists()
        else []
    )
    if only:
        units = [n for n in units if only in n]
    if failed:
        units = [
            n
            for n in units
            if any(
                r.get("path") == n
                and (
                    r["exit"]
                    or r["source_sha256"]
                    != hashlib.sha256((OUT / "generated" / n).read_bytes()).hexdigest()
                )
                for r in previous
            )
        ]

    def compile(name):
        source = OUT / "generated" / name
        obj = folder / (source.stem + "_" + hashlib.sha256(name.encode()).hexdigest()[:8] + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        row = dict(
            path=name,
            source=source.relative_to(ROOT).as_posix(),
            object=obj.relative_to(ROOT).as_posix(),
            command=command,
            exit=r.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if not r.returncode:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(compile, n) for n in units]):
            row = f.result()
            rows.append(row)
            if row["exit"]:
                print(row["path"] + ": FAILED", flush=True)
            elif len(rows) % 10 == 0:
                print("Compiled " + str(len(rows)) + "/" + str(len(units)), flush=True)
            changed = {r["path"] for r in rows}
            stable(
                folder / "build.json",
                json.dumps(
                    sorted(
                        [r for r in previous if r["path"] not in changed] + rows,
                        key=lambda r: r["path"],
                    ),
                    indent=2,
                )
                + "\n",
            )
    changed = {r["path"] for r in rows}
    rows = [r for r in previous if r["path"] not in changed] + rows
    errors = [
        dict(
            path=r["path"],
            errors=[
                s
                for s in (ROOT / r["object"]).with_suffix(".log").read_text().splitlines()
                if "error " in s
            ],
        )
        for r in rows
        if r["exit"]
    ]
    stable(folder / "errors.json", json.dumps(errors, indent=2) + "\n")
    print("Compiled " + str(len(rows) - len(errors)) + "/" + str(len(rows)) + " units.", flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    p.add_argument("--only")
    p.add_argument("--failed", action="store_true")
    a = p.parse_args()
    build(a.only, a.failed) if a.build else prepare()
