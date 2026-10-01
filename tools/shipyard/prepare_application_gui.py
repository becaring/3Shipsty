"""Preserve the current application's complete registered window declarations."""

import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
from prepare_soh_menus import ROOT, BASE, inherited
from prepare_soh_ui import common, maps
from prepare_archives import stable
from prepare_randomizer import edits_apply
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/application-gui"
OUT = ROOT / "scratch/application-gui-xdk"


def classes(text):
    raw = text.encode()
    edits = []
    audit = {}
    statics = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "class_specifier":
            continue
        name = n.child_by_field_name("name").text.decode()
        body = n.child_by_field_name("body")
        bases = [c for c in n.named_children if c.type == "base_class_clause"]
        if not bases:
            continue
        base = bases[0].text.decode().removeprefix(": public ").strip()
        normal = []
        value = []
        members = []
        usings = [c for c in body.named_children if c.type == "using_declaration"]
        assert len(usings) == 1, name
        for f in body.named_children:
            if f.type != "field_declaration":
                continue
            d = f.child_by_field_name("declarator")
            if d is None or any(c.type == "function_declarator" for c in walk(d)):
                continue
            initializer = f.child_by_field_name("default_value")
            if b"static " in f.text:
                if b"inline " in f.text:
                    member = d.text.decode()
                    typ = f.child_by_field_name("type").text.decode()
                    # MessageViewer's single mutable static pointer keeps one definition.
                    assert (
                        name == "MessageViewer"
                        and member.replace(" ", "") == "*TABLE_ID"
                    ), f.text
                    edits.append(
                        (f.start_byte, f.end_byte, "static const char* TABLE_ID;")
                    )
                    statics.append(
                        "const char* MessageViewer::TABLE_ID="
                        + initializer.text.decode()
                        + ";"
                    )
                continue
            ids = [c for c in walk(d) if c.type == "field_identifier"]
            assert len(ids) == 1, f.text
            member = ids[0].text.decode()
            members.append(f.text.decode())
            expr = initializer.text.decode() if initializer else ""
            if initializer:
                normal.append(member + "(" + expr + ")")
                eq = next(c for c in f.children if c.type == "=")
                edits.append((eq.start_byte, initializer.end_byte, ""))
            value.append(member + "(" + expr + ")")
        extra = "".join("," + v for v in normal)
        forwards = inherited(name, extra).replace(": GuiWindow(", ": " + base + "(")
        existing = any(
            re.match(re.escape(name) + r"\s*\(", c.text.decode())
            for c in body.named_children
            if c.type in ("field_declaration", "declaration", "function_definition")
        )
        if not existing:
            forwards += name + "() : " + base + "()" + extra + " {}\n"
            forwards += (
                "explicit "
                + name
                + "(Shipyard::SohUI::ValueInit) : "
                + base
                + "()"
                + "".join("," + v for v in value)
                + " {}\n"
            )
        edits.append((usings[0].start_byte, usings[0].end_byte, forwards))
        audit[name] = dict(base=base, members=members, defaults=normal)
    return (
        edits_apply(raw, edits)
        .replace(" final :", " :")
        .replace("static constexpr", "static const"),
        audit,
        statics,
    )


def vectors(text):
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "declaration":
            continue
        typ = n.child_by_field_name("type")
        init = n.child_by_field_name("declarator")
        if (
            typ is None
            or not typ.text.startswith(b"std::vector<")
            or init is None
            or init.type != "init_declarator"
        ):
            continue
        value = init.child_by_field_name("value")
        if value is None or value.type != "initializer_list":
            continue
        name = init.child_by_field_name("declarator").text.decode()
        item = typ.text.decode()[12:-1]
        helper = "ShipyardBuild_" + name
        code = (
            "static "
            + typ.text.decode()
            + " "
            + helper
            + "(){"
            + typ.text.decode()
            + " result;\n"
        )
        if item == "FlagTable":
            for i, row in enumerate(value.named_children):
                if row.type == "comment":
                    continue
                fields = [c for c in row.named_children if c.type != "comment"]
                assert len(fields) == 4, row.text
                code += (
                    "{ FlagTable table;table.name="
                    + fields[0].text.decode()
                    + ";table.flagTableType="
                    + fields[1].text.decode()
                    + ";table.size="
                    + fields[2].text.decode()
                    + ";\n"
                )
                if b"#define RANDO_ENUM_ITEM" in fields[3].text:
                    original = """{
#define RANDO_ENUM_ITEM(rand_inf) { rand_inf, #rand_inf },
#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerInf.h"
#undef RANDO_ENUM_ITEM
      }"""
                    assert fields[3].text.decode() == original, fields[3].text
                    code += (
                        "#define RANDO_ENUM_ITEM(rand_inf) table.flagDescriptions.insert(std::make_pair(u"
                        "int16_t(rand_inf), #rand_inf));\n"
                        '#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerInf.h"\n'
                        "#undef RANDO_ENUM_ITEM\n"
                    )
                    code += "result.push_back(table);}\n"
                    continue
                for entry in fields[3].named_children:
                    if entry.type == "comment":
                        continue
                    pair = [c for c in entry.named_children if c.type != "comment"]
                    assert len(pair) == 2, entry.text
                    code += (
                        "table.flagDescriptions.insert(std::make_pair(uint16_t("
                        + pair[0].text.decode()
                        + "),"
                        + pair[1].text.decode()
                        + "));\n"
                    )
                code += "result.push_back(table);}\n"
        elif item in (
            "std::string",
            "const char*",
            "uint32_t",
            "std::pair<const char*, const char*>",
        ):
            for entry in value.named_children:
                if entry.type == "comment":
                    continue
                if item.startswith("std::pair"):
                    raise ValueError("Conditional vector rows need platform projection")
                code += "result.push_back(" + entry.text.decode() + ");\n"
        else:
            raise ValueError("Application GUI vector type " + item)
        code += "return result;}\n"
        edits.append((n.start_byte, n.start_byte, code))
        edits.append((value.start_byte, value.end_byte, helper + "()"))
    return edits_apply(raw, edits)


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    outputs = {}
    audit = {}
    statics = []
    audio = (ROOT / "soh/soh/Enhancements/audio/AudioCollection.h").read_text(
        encoding="utf-8-sig"
    )
    assert hashlib.sha256(audio.encode()).hexdigest() == lock["audio_collection_sha256"]
    # AudioCollection owns the one canonical enum declaration and full class.
    stale = OUT / "generated/soh/soh/Enhancements/audio/sequence_type.h"
    if stale.exists():
        stale.unlink()
    for path, digest in lock["sources"].items():
        text = (ROOT / path).read_text(encoding="utf-8-sig")
        assert hashlib.sha256(text.encode()).hexdigest() == digest, path
        from overlap_gui_work_projection import project as overlap_gui_work

        text = overlap_gui_work(path, text)
        text = text.replace(
            "#include <libultraship/libultraship.h>",
            '#include "soh/SohGui/UIWidgets.hpp"',
        )
        text = text.replace(
            '#include "randomizerTypes.h"',
            '#include "soh/Enhancements/randomizer/randomizerTypes.h"',
        )
        text = text.replace(
            '#include "AudioCollection.h"',
            '#include "soh/Enhancements/audio/sequence_type.h"',
        )
        if path.endswith(".h"):
            text, record, definitions = classes(text)
            audit[path] = record
            statics += definitions
            text = maps(vectors(text))
        if path.endswith("SohGui.cpp"):
            # These declarations/data are unused by any of this TU's methods.
            for unused in [
                "soh/SaveManager.h",
                "soh/Enhancements/Presets/Presets.h",
                "soh/resource/type/Skeleton.h",
                "soh/Enhancements/cosmetics/authenticGfxPatches.h",
            ]:
                text = text.replace(
                    '#include "' + unused + '"',
                    "// Unused umbrella dependency: " + unused,
                )
            a = text.index(
                "static const inline std::vector<std::pair<const char*, const char*>>"
                " audioBackends ="
            )
            b = text.index("\n};", a) + 3
            text = (
                text[:a]
                + (
                    "static std::vector<std::pair<const char*,const char*> > BuildAudioBackends(){\n"
                    'std::vector<std::pair<const char*,const char*> > r;r.push_back(std::make_pair("x'
                    'audio2","XAudio2"));r.push_back(std::make_pair("null","Null"));return r;}\n'
                    "static const std::vector<std::pair<const char*,const char*> > audioBackends=Buil"
                    "dAudioBackends();"
                )
                + text[b:]
            )
            text = '#include "ship/window/gui/IconsFontAwesome4.h"\n' + text
        if path.endswith(".h"):
            text = '#include "soh-ui/value_init.h"\n' + text
        target = OUT / "generated" / path
        stable(target, common(text))
        outputs[path] = hashlib.sha256(target.read_bytes()).hexdigest()
    stable(
        OUT / "generated/WindowStatics.cpp",
        '#include "soh/Enhancements/debugger/MessageViewer.h"\n'
        + "\n".join(statics)
        + "\n",
    )
    outputs["WindowStatics.cpp"] = hashlib.sha256(
        (OUT / "generated/WindowStatics.cpp").read_bytes()
    ).hexdigest()
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated=outputs,
                classes=audit,
                statics=statics,
                native_gui_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/soh-menus-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    flags[1:1] = ["/DENABLE_REMOTE_CONTROL"] + [
        "/I" + str(p)
        for p in [
            OUT / "generated/soh",
            ROOT / "scratch/audio-collection-xdk/generated/soh",
            ROOT / "scratch/network-xdk/generated/soh",
            ROOT / "scratch/randomizer-item-xdk/generated/soh",
            ROOT / "scratch/randomizer-options-xdk/generated/soh",
            ROOT / "scratch/randomizer-xdk/generated/soh/soh/Enhancements/randomizer",
        ]
    ]
    probe = folder / "declarations.cpp"
    headers = [
        p
        for p in json.loads((OWN / "sources.lock.json").read_text())["sources"]
        if p.endswith(".h")
    ]
    stable(
        probe,
        "\n".join('#include "' + p.removeprefix("soh/") + '"' for p in headers) + "\n",
    )
    rows = []
    for source in [
        probe,
        OUT / "generated/WindowStatics.cpp",
        OUT / "generated" / (BASE + "SohGui.cpp"),
    ]:
        obj = folder / (source.stem + ".obj")
        cmd = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        rows.append(
            dict(
                command=cmd,
                exit=r.returncode,
                source=source.relative_to(ROOT).as_posix(),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                object_sha256=(
                    hashlib.sha256(obj.read_bytes()).hexdigest()
                    if r.returncode == 0
                    else None
                ),
            )
        )
        print(source.stem, r.returncode)
        if r.returncode:
            print("\n".join(s for s in r.stdout.splitlines() if "error " in s)[:5500])
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
