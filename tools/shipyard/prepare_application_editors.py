"""Complete pinned audio and cosmetics editors on canonical native providers."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_soh_ui import maps, value_expressions
from prepare_randomizer import edits_apply
from prepare_randomizer_item import methods
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/application-editors"
OUT = ROOT / "scratch/application-editors-xdk"
SOURCES = {
    "AudioEditor": "soh/soh/Enhancements/audio/AudioEditor.cpp",
    "CosmeticsEditor": "soh/soh/Enhancements/cosmetics/CosmeticsEditor.cpp",
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def project(name, text):
    from prepare_game_interactor import call_sites

    text = call_sites(text, SOURCES[name])
    section = "audio" if name == "AudioEditor" else "cosmetics"
    text = once(
        text,
        '#include "' + name + '.h"',
        '#include "soh/Enhancements/' + section + "/" + name + '.h"',
    )
    text = once(
        text,
        "#include <libultraship/libultraship.h>",
        '#include "ship/window/gui/IconsFontAwesome4.h"\n#include'
        ' "ship/controller/controldeck/ControlDeck.h"\n#include'
        ' "ship/controller/controldevice/controller/Controller.h"',
    )
    if name == "AudioEditor":
        text = once(
            text,
            '#include "../randomizer/3drando/random.hpp"',
            '#include "soh/Enhancements/randomizer/3drando/random.hpp"',
        )
        text = once(
            text,
            '#include "AudioCollection.h"',
            '#include "soh/Enhancements/audio/AudioCollection.h"',
        )
        m = re.search(r"static std::map<SeqType, bool> showType(\{[\s\S]*?\});", text)
        if not m:
            raise ValueError("Show type map drift")
        helper = maps("static std::map<SeqType, bool> showType = " + m[1] + ";").rsplit("\n", 1)[0]
        text = (
            text[: m.start()]
            + "static std::map<SeqType,bool> showType = MakeshowType();"
            + text[m.end() :]
        )
        text = text.replace(
            "// Authentic sequence counts", helper + "\n// Authentic sequence counts"
        )
        text = re.sub(r"(std::(?:vector|set)<[^;]+?> \w+) = \{\};", r"\1;", text)
        text, n = re.subn(
            r"std::vector<SeqType> allTypes = (\{[^;]+\});",
            r"static const SeqType allTypeValues[]=\1;\nstd::vector<SeqType>"
            r" allTypes(allTypeValues,allTypeValues+sizeof(allTypeValues)/sizeof(allTypeValues[0]));",
            text,
        )
        if n != 1:
            raise ValueError("All sequence type inventory drift")
    else:
        text = text.replace("MarginCvarList[]{", "MarginCvarList[] = {").replace(
            "MarginCvarNonAnchor[]{", "MarginCvarNonAnchor[] = {"
        )
        for f in ("cosmeticsTypes.h", "authenticGfxPatches.h"):
            text = once(
                text, '#include "' + f + '"', '#include "soh/Enhancements/cosmetics/' + f + '"'
            )
        text = once(
            text,
            "ResourceMgr_PatchGfxByName(path, name, index, instruction);",
            "Gfx shipyardInstruction = instruction; \\\n        ResourceMgr_PatchGfxByName(path,"
            " name, index, shipyardInstruction);",
        )
        raw = text.encode()
        edits = []
        for node in walk(PARSER.parse(raw).root_node):
            if (
                node.type != "call_expression"
                or node.child_by_field_name("function").text != b"ResourceMgr_PatchGfxByName"
            ):
                continue
            args = node.child_by_field_name("arguments").named_children
            if len(args) != 4 or not args[-1].text.startswith(b"gs"):
                continue
            statement = node.parent
            if statement.type != "expression_statement":
                raise ValueError("Gfx patch expression context drift")
            body = (
                raw[statement.start_byte : args[-1].start_byte].decode()
                + "shipyardInstruction"
                + raw[args[-1].end_byte : statement.end_byte].decode()
            )
            edits.append(
                (
                    statement.start_byte,
                    statement.end_byte,
                    "{ Gfx shipyardInstruction = " + args[-1].text.decode() + "; " + body + " }",
                )
            )
        if len(edits) != 4:
            raise ValueError("Direct graphics patch inventory drift")
        text = edits_apply(raw, edits)
        text = re.sub(r"\.currentColor = \{([^{}]+)\};", r".currentColor = ImVec4(\1);", text)
        text = re.sub(r"Color_RGBA8\{([^{}]+)\}", r"ColorRGBA8(\1)", text)
        text = re.sub(r"(CVarSetColor\([^\n]+?,)\s*\{([^{}]+)\}", r"\1 ColorRGBA8(\2)", text)
        text, n = re.subn(
            r"static RegisterShipInitFunc initFunc\(RegisterCosmeticHooks, (\{[\s\S]*?\})\);",
            r"static std::set<std::string> MakeCosmeticHookPaths(){ const std::string values[]=\1;"
            r" return std::set<std::string>(values,values+sizeof(values)/sizeof(values[0]));"
            r" }\nstatic RegisterShipInitFunc initFunc(RegisterCosmeticHooks,"
            r" MakeCosmeticHookPaths());",
            text,
        )
        if n != 1:
            raise ValueError("Cosmetic hook registration drift")
    text = maps(text)
    text, n = re.subn(
        r'(\w+) = \{ \.name = ("[^"]+"),\s*\.type = WidgetType::(\w+) \};',
        r"\1 = Shipyard::ApplicationEditors::Widget(\2, WidgetType::\3);",
        text,
    )
    if n != (10 if name == "AudioEditor" else 1):
        raise ValueError("Widget inventory drift")
    text = re.sub(
        r"AddSearchWidget\((\{[^;]*?\})\)",
        lambda m: "AddSearchWidget(SearchWidget(" + m[1][1:-1] + "))",
        text,
    )
    text = value_expressions(text)
    general = runpy.run_path(str(ROOT / "platform/shipyard/input/lowering.py"))
    return (
        '#include "resources/runtime_support.h"\n#include "input/compiler.h"\n#include'
        ' "application-editors/support.h"\n#include "soh/Enhancements/randomizer/SeedContext.h"\n'
        + general["syntax"](text, set())
    )


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    outputs = {}
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(text) != digest:
            raise ValueError("Application editor source drift " + name)
        texts[name] = text
    for name, path in SOURCES.items():
        text = project(name, texts[path])
        stable(OUT / "generated" / path, text)
        outputs[name] = sha(text)
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_archives.py",
            "prepare_configuration.py",
            "prepare_soh_ui.py",
            "prepare_randomizer.py",
            "prepare_randomizer_item.py",
            "prepare_game_interactor.py",
            "cpp_ast.py",
        )
    ] + [ROOT / "platform/shipyard/input/lowering.py", OWN / "support.h"]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                generated=outputs,
                original_functions={n: len(methods(texts[p])) for n, p in SOURCES.items()},
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


def includes():
    from prepare_randomizer_logic import includes as base

    return [
        OUT / "generated/soh",
        ROOT / "scratch/application-gui-xdk/generated/soh",
        ROOT / "scratch/audio-collection-xdk/generated/soh",
        ROOT / "scratch/enhancements-xdk/generated/soh",
        ROOT / "scratch/game-interactor-xdk/generated/soh",
        ROOT / "scratch/soh-menus-xdk/generated/soh",
        ROOT / "scratch/soh-ui-xdk/generated/soh",
        ROOT / "scratch/soh-menus-xdk/generated/soh/soh/SohGui",
        ROOT / "scratch/soh-ui-xdk/generated/soh/soh/SohGui",
    ] + base()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    rows = []
    for name, path in SOURCES.items():
        source = OUT / "generated" / path
        obj = folder / (name + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (name + ".log"), r.stdout + r.stderr)
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
            print("\n".join(s for s in (r.stdout + r.stderr).splitlines() if "error " in s)[:9500])
        rows.append(row)
        print("Full " + name + ": " + str(r.returncode), flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
