"""Source-locked randomizer Item, with its dependency declarations."""

import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import lower_defaults, default_arguments, edits_apply
from prepare_binary import strong_enum
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/randomizer-item"
OUT = ROOT / "scratch/randomizer-item-xdk"
BASE = "soh/soh/Enhancements/randomizer/"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def inventory(text):
    out = {}
    for cls in walk(PARSER.parse(text.encode()).root_node):
        if cls.type not in ("class_specifier", "struct_specifier"):
            continue
        members = []
        for node in cls.child_by_field_name("body").named_children:
            if node.type != "field_declaration":
                continue
            value = node.child_by_field_name("default_value")
            if value is None:
                continue
            decl = node.child_by_field_name("declarator")
            while decl.type == "pointer_declarator":
                decl = decl.child_by_field_name("declarator")
            if decl.type != "field_identifier":
                raise ValueError("Unsupported DMI " + node.text.decode())
            members.append(
                dict(
                    name=decl.text.decode(),
                    type=node.child_by_field_name("type").text.decode(),
                    value=value.text.decode(),
                )
            )
        if members:
            out[cls.child_by_field_name("name").text.decode()] = members
    return out


def methods(text):
    return [
        n for n in walk(PARSER.parse(text.encode()).root_node) if n.type == "function_definition"
    ]


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    generated = {}
    audit = []
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(text) != digest:
            raise ValueError("Item source drift " + name)
        texts[name] = text
    for name, digest in lock.get("dependencies", {}).items():
        if sha((ROOT / name).read_text(encoding="utf-8-sig")) != digest:
            raise ValueError("Item dependency drift " + name)

    def emit(name, text):
        stable(OUT / "generated" / name, text)
        generated[name] = sha(text)

    header = texts[BASE + "item.h"]
    defaults = inventory(header)
    header = once(header, "#include <variant>", "// Item has no variant member or signature.")
    header = once(header, '#include "3drando/hints.hpp"', "class HintText;")
    header = default_arguments(lower_defaults(header, defaults, audit))
    emit(BASE + "item.h", header)
    source = lower_defaults(texts[BASE + "item.cpp"], defaults, audit)
    source = once(source, '#include "3drando/item_pool.hpp"', '#include "static_data.h"')
    source = once(
        source,
        '#include "../../OTRGlobals.h"',
        '#include "soh/OTRGlobals.h"\n#include "randomizer.h"',
    )
    source = '#include "resources/runtime_support.h"\n' + source
    # Keep aggregate field ordering and both original metadata ownership paths.
    pattern = r"giEntry = std::make_shared<GetItemEntry>\(GetItemEntry\{([\s\S]*?)\}\);"
    source, count = re.subn(
        pattern,
        r"const GetItemEntry entry = {\1};\n        giEntry ="
        r" std::make_shared<GetItemEntry>(entry);",
        source,
    )
    if count != 2:
        raise ValueError("Expected both real GI-entry constructor branches")
    source = source.replace("[[fallthrough]]", "/* fall through */")
    emit(BASE + "item.cpp", source)
    # Source-accurate complete Logic declaration. Emit the constructor with
    # its relocated defaults, so downstream consumers cannot silently lose them.
    logic = texts[BASE + "logic.h"]
    ld = inventory(logic)
    logic = once(
        logic,
        '#include "SeedContext.h"',
        '#include <map>\n#include <memory>\n#include "z64save.h"\n#include "z64scene.h"\nnamespace'
        " Rando { class Context; class Item; }",
    )
    logic = lower_defaults(logic, ld, [])
    logic = re.sub(
        r"enum class (HasProjectileAge|GlitchType) \{(.*?)\};",
        lambda m: strong_enum(m[1], m[2]),
        logic,
        flags=re.S,
    )
    emit(BASE + "logic.h", '#include "binary/compat.h"\n' + logic)
    lsource = lower_defaults(texts[BASE + "logic.cpp"], ld, [])
    emit(BASE + "logic.cpp", lsource)
    ctor = [
        n.text.decode()
        for n in methods(lsource)
        if n.child_by_field_name("declarator").text == b"Logic::Logic()"
    ]
    if len(ctor) != 1:
        raise ValueError("Logic constructor inventory")
    emit(
        "LogicConstructor.cpp",
        '#include "soh/Enhancements/randomizer/logic.h"\nnamespace Rando {\n' + ctor[0] + "\n}\n",
    )
    # GetHint requires complete HintText layout. Other hint types are not
    # instantiated here: extract the entire class to one named header.
    hints = texts[BASE + "3drando/hints.hpp"]
    cls = next(
        n
        for n in walk(PARSER.parse(hints.encode()).root_node)
        if n.type == "class_specifier" and n.child_by_field_name("name").text == b"HintText"
    )
    hint = default_arguments(lower_defaults(cls.text.decode() + ";", inventory(hints), []))
    emit(
        BASE + "3drando/HintText.h",
        '#pragma once\n#include "soh/Enhancements/custom-message/CustomMessageManager.h"\n'
        + hint
        + "\n",
    )
    location = texts[BASE + "location.h"]
    location = lower_defaults(location, inventory(location), [])
    location = once(location, '#include "3drando/hints.hpp"', '#include "3drando/HintText.h"')
    location = once(location, '#include "../../util.h"', '#include "soh/util.h"')
    location = once(
        location, '#include "option.h"', '#include "soh/Enhancements/randomizer/option.h"'
    )
    location = location.replace("static auto ", "static SpoilerCollectionCheck ")
    emit(BASE + "location.h", location)
    spoiler = (
        texts[BASE + "3drando/spoiler_log.hpp"]
        .replace("#include <string_view>", "// No string_view declaration or use in this header.")
        .replace(
            "using RandomizerHash = std::array<std::string, 5>;",
            "typedef std::array<std::string, 5> RandomizerHash;",
        )
    )
    spoiler = once(
        spoiler,
        '#include "../randomizerTypes.h"',
        '#include "soh/Enhancements/randomizer/randomizerTypes.h"',
    )
    emit(BASE + "3drando/spoiler_log.hpp", spoiler)
    static = once(
        texts[BASE + "static_data.h"],
        '#include "location.h"',
        '#include "location.h"\nstruct StaticHintInfo;',
    )
    emit(BASE + "static_data.h", static)
    randomizer = texts[BASE + "randomizer.h"]
    unnecessary = [
        "soh/Enhancements/randomizer/randomizer_check_objects.h",
        "soh/Enhancements/randomizer/randomizer_check_tracker.h",
        "soh/Enhancements/randomizer/tricks.h",
        "soh/Enhancements/custom-message/CustomMessageManager.h",
        "../custom-message/CustomMessageTypes.h",
        "soh/Enhancements/randomizer/fishsanity.h",
    ]
    for name in unnecessary:
        randomizer, n = re.subn(
            r'#include [<"]' + re.escape(name) + r'[>"]',
            "// Unused transitive dependency: " + name,
            randomizer,
        )
        if n != 1:
            raise ValueError("Randomizer include drift " + name)
    emit(BASE + "randomizer.h", "namespace Rando { class Location; }\n" + randomizer)
    helpers = {
        n: hashlib.sha256((ROOT / "tools/shipyard" / n).read_bytes()).hexdigest()
        for n in (
            "prepare_randomizer.py",
            "prepare_binary.py",
            "prepare_configuration.py",
            "prepare_archives.py",
            "cpp_ast.py",
        )
    }
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                dependencies=lock.get("dependencies", {}),
                generated=generated,
                item_constructor_defaults=audit,
                logic_defaults=ld,
                full_item_methods=len(methods(source)),
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helpers=helpers,
                production_units=[BASE + "item.cpp", "LogicConstructor.cpp"],
                uncompiled_dependency_unit=BASE + "logic.cpp",
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    from prepare_ship_utils import includes as base

    return [
        OUT / "generated/soh",
        OUT / "generated" / BASE,
        ROOT / "scratch/randomizer-options-xdk/generated/soh",
        ROOT / "scratch/randomizer-xdk/generated" / BASE,
        ROOT / "scratch/randomizer-xdk/generated/soh",
        ROOT / "scratch/application-xdk/generated/soh",
        ROOT / "scratch/custom-message-xdk/generated/soh",
        ROOT / "scratch/soh-ui-xdk/generated/soh",
        ROOT / "scratch/soh-menus-xdk/generated/soh",
    ] + base()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/ship-utils-xdk/xdk/build.json").read_text())[0]["command"][
        :-3
    ]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    rows = []
    for name in (BASE + "item.cpp", "LogicConstructor.cpp"):
        source = OUT / "generated" / name
        obj = folder / (source.stem + ".obj")
        command = flags + ["/TP", str(source), "/Fo" + str(obj)]
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
                    :7500
                ],
                flush=True,
            )
        rows.append(row)
        print(source.stem + ": " + str(result.returncode), flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
