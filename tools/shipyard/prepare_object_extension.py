"""Compile the application object-extension registry and actor fields."""

import argparse
import hashlib
import json
import re
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_enhancements import transform as enhancement_transform, includes

OWN = ROOT / "platform/shipyard/object-extension"
OUT = ROOT / "scratch/object-extension-xdk"
BASE = "soh/soh/ObjectExtension/"


def transform(name, text):
    if name.endswith("/ObjectExtension.h"):
        text = once(text, "#include <libultraship/libultraship.h>", "#include <cassert>")
        text = once(text, "#include <any>", '#include "object-extension/any.h"')
        text = text.replace("std::any", "Shipyard::any").replace(
            "using Id = uint32_t;", "typedef uint32_t Id;"
        )
        text = once(
            text,
            "static constexpr Id InvalidId = std::numeric_limits<Id>::max();",
            "static const Id InvalidId = UINT32_MAX;",
        )
        text = once(text, "ObjectExtension() = default;", "ObjectExtension() : NextId(0) {}")
        text = once(text, "ObjectExtension::Id NextId = 0;", "ObjectExtension::Id NextId;")
        text = once(
            text,
            "Data.contains(std::make_pair(object, ObjectExtension::Register<T>::Id))",
            "(Data.find(std::make_pair(object, ObjectExtension::Register<T>::Id)) != Data.end())",
        )
        text = text.replace("std::hash<const void*>{}", "std::hash<const void*>()").replace(
            "std::hash<ObjectExtension::Id>{}", "std::hash<ObjectExtension::Id>()"
        )
    if name.endswith("/ObjectExtension.cpp"):
        text = once(
            text,
            "    std::erase_if(Data, [&object](const auto& iter) {\n        auto const& [key,"
            " value] = iter;\n        return key.first == object;\n    });",
            "    for (auto it=Data.begin();it!=Data.end();) {\n        if (it->first.first =="
            " object) it=Data.erase(it); else ++it;\n    }",
        )
    for cls, field, typ, default in [
        ("ActorListIndex", "index", "s16", "-1"),
        ("ActorMaximumHealth", "maximumHealth", "u8", "0"),
    ]:
        if name.endswith("/" + cls + ".cpp"):
            text = once(
                text,
                typ + " " + field + " = " + default + ";",
                typ
                + " "
                + field
                + ";\n    "
                + cls
                + "("
                + typ
                + " value="
                + default
                + ") : "
                + field
                + "(value) {}",
            )
            text = text.replace(cls + "{}", cls + "()").replace(
                cls + "{ " + field + " }", cls + "(" + field + ")"
            )
    if name.endswith(".cpp"):
        text = enhancement_transform(name, text)
    return text


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    for name, expected in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("ObjectExtension source drift " + name)
        stable(OUT / "generated" / name, transform(name, text))


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    rows = []
    flags = json.loads((ROOT / "scratch/game-interactor-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    flags[1:1] = [
        "/I" + str(OUT / "generated/soh"),
        "/I" + str(ROOT / "scratch/enhancements-xdk/generated/soh"),
    ]
    for name in ("ObjectExtension", "ActorListIndex", "ActorMaximumHealth"):
        source = OUT / "generated" / BASE / (name + ".cpp")
        obj = folder / (name + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source=source.relative_to(ROOT).as_posix(), command=command, exit=result.returncode
            )
        )
        print(name + ": " + str(result.returncode))
        if result.returncode:
            print("\n".join(line for line in result.stdout.splitlines() if "error " in line)[:2200])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    args = p.parse_args()
    if args.build:
        build()
    else:
        prepare()
