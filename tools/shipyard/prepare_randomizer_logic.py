"""Pinned randomizer Logic translation unit for the native XDK compiler."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import lower_defaults, edits_apply
from prepare_randomizer_item import inventory, methods, includes as item_includes
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/randomizer-logic"
OUT = ROOT / "scratch/randomizer-logic-xdk"
BASE = "soh/soh/Enhancements/randomizer/"


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def maps(text):
    raw = text.encode()
    edits = []
    audit = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "declaration":
            continue
        typ = n.child_by_field_name("type")
        if typ is None or not typ.text.startswith(b"std::map<"):
            continue
        init = next((c for c in n.named_children if c.type == "init_declarator"), None)
        value = init.child_by_field_name("value") if init else None
        if value is None or value.type != "initializer_list":
            continue
        types = typ.text.decode().split("<", 1)[1][:-1].split(",")
        assert len(types) == 2
        name = init.child_by_field_name("declarator").text.decode()
        helper = "ShipyardMake" + name.replace("::", "_")
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
            + value.text.decode()
            + "; "
            + typ.text.decode()
            + " result; for(size_t i=0;i<sizeof(values)/sizeof(values[0]);++i)"
            " result.insert(std::make_pair(values[i].first,values[i].second)); return result; }\n"
        )
        edits.append((n.start_byte, n.start_byte, prefix))
        edits.append((value.start_byte, value.end_byte, helper + "()"))
        audit.append(dict(name=name, entries=len(value.named_children), source=value.text.decode()))
    if len(audit) != 5:
        raise ValueError("Logic map initializer count drift")
    return edits_apply(raw, edits), audit


def project(text):
    text = lower_defaults(text, inventory((ROOT / (BASE + "logic.h")).read_text()), [])
    text = once(
        text,
        '#include "../debugger/performanceTimer.h"',
        '#include "randomizer-logic/performance_calls.h"',
    )
    text = (
        '#include "resources/runtime_support.h"\n#include'
        ' "soh/Enhancements/randomizer/item.h"\n#include'
        ' "soh/Enhancements/randomizer/option.h"\n#include "ship/resource/ResourceManager.h"\n'
        + text
    )
    text = text.replace("[[fallthrough]]", "/* fall through */")
    text = once(text, "switch (glitch) {", "switch (glitch.GetValue()) {")
    text = once(
        text,
        "BottleRandomizerGetToItemID.contains(randoGet)",
        "(BottleRandomizerGetToItemID.find(randoGet) != BottleRandomizerGetToItemID.end())",
    )
    text = once(
        text,
        "static const std::vector<uint8_t> normalSmallKeyDoors{ 1, 2, 3, 4 };",
        "static const uint8_t normalDoorValues[]={ 1, 2, 3, 4 };\n    static const"
        " std::vector<uint8_t> normalSmallKeyDoors(normalDoorValues,normalDoorValues+4);",
    )
    text = once(
        text,
        "static const std::vector<uint8_t> fastSmallKeyDoors{ 1 };",
        "static const uint8_t fastDoorValues[]={ 1 };\n    static const std::vector<uint8_t>"
        " fastSmallKeyDoors(fastDoorValues,fastDoorValues+1);",
    )
    text = once(
        text,
        "static const std::vector<uint8_t> freeSmallKeyDoors{};",
        "static const std::vector<uint8_t> freeSmallKeyDoors;",
    )
    text = once(
        text,
        "dungeonSmallKeyDoors[key] = {};",
        "dungeonSmallKeyDoors[key] = std::vector<uint8_t>();",
    )
    text, audit = maps(text)
    ranges = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))["lower_ranges"]
    text = ranges(text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end").decode()
    return text, audit


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    outputs = {}
    for name, digest in lock["sources"].items():
        t = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(t) != digest:
            raise ValueError("Logic source drift " + name)
        texts[name] = t
    for name, digest in lock.get("dependencies", {}).items():
        if sha((ROOT / name).read_text(encoding="utf-8-sig")) != digest:
            raise ValueError("Logic dependency drift " + name)

    def emit(name, t):
        stable(OUT / "generated" / name, t)
        outputs[name] = sha(t)

    text, audit = project(texts[BASE + "logic.cpp"])
    emit(BASE + "logic.cpp", text)
    dungeon = (
        texts[BASE + "dungeon.h"]
        .replace("uint8_t vanillaKeyCount{};", "uint8_t vanillaKeyCount = 0;")
        .replace("uint8_t mqKeyCount{};", "uint8_t mqKeyCount = 0;")
    )
    defaults = inventory(dungeon)
    emit(BASE + "dungeon.h", lower_defaults(dungeon, defaults, []))
    emit(BASE + "dungeon.cpp", lower_defaults(texts[BASE + "dungeon.cpp"], defaults, []))
    perf = texts["soh/soh/Enhancements/debugger/performanceTimer.h"]
    enum = re.search(r"typedef enum \{[\s\S]*?\} TimerID;", perf)[0]
    calls = "\n".join(
        re.findall(r"^void (?:Start|Stop)PerformanceTimer\(TimerID timer\);$", perf, re.M)
    )
    if len(calls.splitlines()) != 2:
        raise ValueError("Performance timer API drift")
    emit(
        "include/randomizer-logic/performance_calls.h",
        "#pragma once\n" + enum + "\n" + calls + "\n",
    )
    helpers = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            ROOT / "tools/shipyard" / n
            for n in (
                "prepare_randomizer.py",
                "prepare_randomizer_item.py",
                "prepare_configuration.py",
                "prepare_archives.py",
                "cpp_ast.py",
            )
        ]
        + [ROOT / "platform/shipyard/imgui/projection.py"]
    }
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                dependencies=lock.get("dependencies", {}),
                generated=outputs,
                map_initializers=audit,
                full_original_definitions=len(methods(texts[BASE + "logic.cpp"])),
                constructor_defaults=inventory(texts[BASE + "logic.h"]),
                dungeon_defaults=defaults,
                uncompiled_dependency=BASE + "dungeon.cpp",
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helpers=helpers,
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    return [
        OUT / "generated/soh",
        OUT / "generated" / BASE,
        OUT / "generated/include",
        ROOT / "scratch/soh-resources-xdk/generated/soh",
    ] + item_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    source = OUT / "generated" / (BASE + "logic.cpp")
    obj = folder / "logic.obj"
    command = flags + [str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(folder / "logic.log", result.stdout + result.stderr)
    row = dict(
        source=source.relative_to(ROOT).as_posix(),
        command=command,
        exit=result.returncode,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    if result.returncode == 0:
        assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
        row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
    else:
        print(
            "\n".join(s for s in (result.stdout + result.stderr).splitlines() if "error " in s)[
                :8500
            ]
        )
    stable(folder / "build.json", json.dumps([row], indent=2) + "\n")
    print("Full randomizer Logic: " + str(result.returncode))
    if result.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
