"""Generate and build the pinned libzip/zlib runtime at its native file boundary."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from platform_base import resolve as resolve_platform_base
import sys

OUT = ROOT / "scratch/libzip-xdk"
PLATFORM_BASE = resolve_platform_base(ROOT)
sys.path.insert(0, str(PLATFORM_BASE / "python"))
from xbox360_platform.libzip import project

ZLIB_UNITS = (
    "adler32 compress crc32 deflate infback inffast inflate inftrees trees uncompr zutil".split()
)


def stable(path, text):
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def prepare():
    source = verified("libzip")
    verified("zlib")
    manifest = project(source, OUT / "generated", source.relative_to(ROOT).as_posix())
    stable(OUT / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def build(host=False):
    manifest = prepare()
    folder = OUT / ("host" if host else "xdk")
    folder.mkdir(parents=True, exist_ok=True)
    sdk = Path(os.environ.get("XEDK", "C:/Program Files (x86)/Microsoft Xbox 360 SDK"))
    env = os.environ.copy()
    if host:
        helpers = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
        compiler, env = helpers["host_environment"]()
        librarian = compiler.parent / "lib.exe"
        flags = ["/nologo", "/c", "/MD", "/W3", "/D_CRT_SECURE_NO_WARNINGS"]
    else:
        compiler = sdk / "bin/win32/cl.exe"
        librarian = sdk / "bin/win32/lib.exe"
        flags = ["/nologo", "/c", "/MT", "/W3", "/D_XBOX", "/I" + str(sdk / "include/xbox")]
    flags += [
        "/DNOMINMAX",
        "/I" + str(OUT / "generated"),
        "/I" + str(PLATFORM_BASE / "sources"),
        "/I" + str(ROOT / "platform/shipyard"),
        "/I" + str(ROOT / "scratch/deps/zlib"),
    ]
    groups = {
        "zip": (
            [OUT / "generated" / name for name in manifest["units"]]
            + [PLATFORM_BASE / "sources/libzip/native_boundary.cpp"]
        ),
        "zlib": [ROOT / "scratch/deps/zlib" / (name + ".c") for name in ZLIB_UNITS],
        "tinyxml2": [verified("tinyxml2") / "tinyxml2.cpp"],
    }
    records = []
    libraries = {}
    for group, sources in groups.items():
        objects = []
        for source in sources:
            obj = folder / (group + "-" + source.stem + ".obj")
            objects.append(obj)
            command = (
                [str(compiler)]
                + flags
                + (["/TP", "/EHsc", "/GR"] if source.suffix == ".cpp" else ["/TC"])
                + [str(source), "/Fo" + str(obj)]
            )
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            stable(folder / (obj.stem + ".log"), result.stdout + result.stderr)
            source_name = (
                "shipyard/" + source.relative_to(PLATFORM_BASE).as_posix()
                if source.is_relative_to(PLATFORM_BASE)
                else source.relative_to(ROOT).as_posix()
            )
            records.append(dict(source=source_name, command=command, exit=result.returncode))
            if result.returncode:
                raise RuntimeError(
                    "Archive source failed, see " + str(folder / (obj.stem + ".log"))
                )
            if not host and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
                raise ValueError("Expected Xenon PowerPC BE object")
        library = folder / (group + ".lib")
        response = folder / (group + ".rsp")
        stable(
            response,
            '/nologo\n/OUT:"'
            + str(library)
            + '"\n'
            + "\n".join('"' + str(p) + '"' for p in objects),
        )
        result = subprocess.run(
            [str(librarian), "@" + str(response)], cwd=ROOT, env=env, capture_output=True, text=True
        )
        stable(folder / (group + "-archive.log"), result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Librarian failed: " + group)
        libraries[group] = hashlib.sha256(library.read_bytes()).hexdigest()
    stable(
        folder / "build.json",
        json.dumps(
            dict(objects=records, libraries=libraries, target_runtime_executed=False), indent=2
        )
        + "\n",
    )
    print(
        "Built "
        + ("host" if host else "Xenon")
        + " libzip, zlib, tinyxml2 ("
        + str(len(records))
        + " objects)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--host", action="store_true")
    args = parser.parse_args()
    if args.build:
        build(args.host)
    else:
        prepare()
        print("Generated verified libzip projection")
