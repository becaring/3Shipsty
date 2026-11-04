"""Project ZAPD and OTRExporter through Shipyard so the console builds its ROM archives.

The application extracts oot.o2r and oot-mq.o2r from a ROM beside the XEX, so a
release needs no PC extraction step. Shipyard owns the projection; this script
supplies SoH's resource headers and the XDK recipes. libgfxd and tinyxml2 come
from the gfxd and archives subsystems, so the build holds one copy of each.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from tree_sitter import Language, Parser
import tree_sitter_cpp

from dependency_sources import ROOT, verified
from platform_base import resolve

OUT = ROOT / "scratch/extractor-xdk"
SDK = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
SHIPYARD_UNITS = ("zapd/extract.cpp", "archive/stored_zip_writer.cpp", "rom/rom.cpp")


def prepare():
    base = resolve(ROOT)
    from xbox360_platform import zapd

    parser = Parser(Language(tree_sitter_cpp.language()))
    result = zapd.project(
        ROOT / "ZAPDTR",
        ROOT / "OTRExporter",
        ROOT / "libultraship",
        ROOT / "soh/soh/resource/type/SohResourceType.h",
        ROOT / "soh/soh/resource/type/Animation.h",
        OUT / "generated",
        parser,
    )
    return base, result["units"]


def build(jobs):
    base, units = prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    includes = [
        OUT / "generated/ZAPD",
        OUT / "generated/OTRExporter",
        OUT / "generated",
        verified("tinyxml2"),
        ROOT / "scratch/gfxd-xdk/source",
        ROOT / "libultraship/include",
        base / "sources",
        base / "sources/crt",
        base / "sources/value_types",
        SDK / "include/xbox",
    ]
    flags = [
        "/nologo",
        "/c",
        "/EHsc",
        "/GR",
        "/MT",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNDEBUG",
        "/DNOMINMAX",
        "/DGAME_OOT",
        "/FIzapd/compat.h",
    ] + ["/I" + str(path) for path in includes]
    sources = [OUT / "generated" / unit for unit in units] + [base / "sources" / unit for unit in SHIPYARD_UNITS]

    def compile_unit(source):
        name = source.relative_to(OUT / "generated" if source.is_relative_to(OUT) else base / "sources")
        obj = folder / (name.as_posix().replace("/", "__").rsplit(".", 1)[0] + ".obj")
        command = [str(SDK / "bin/win32/cl.exe")] + flags + ["/TP", str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        row = dict(source=str(source), command=command, exit=result.returncode,
                   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if result.returncode:
            print(name.as_posix() + ":\n" + "\n".join(l for l in result.stdout.splitlines() if " error " in l)[:1500])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        return row

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(compile_unit, sources))
    (folder / "build.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    failed = sum(1 for row in rows if row["exit"])
    print("extractor units: %d, failed: %d" % (len(rows), failed))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.build:
        build(args.jobs)
    else:
        prepare()
