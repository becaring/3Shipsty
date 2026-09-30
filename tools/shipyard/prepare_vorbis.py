"""Build upstream libvorbis 1.3.7 for the current application's sample decoder."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import runpy
from dependency_sources import ROOT, verified
from prepare_archives import stable
from prepare_game import lower_c

OUT = ROOT / "scratch/vorbis-xdk"


def prepare():
    src = verified("vorbis")
    units = []
    cmake = (src / "lib/CMakeLists.txt").read_text()
    for name in ("VORBIS_SOURCES", "VORBISFILE_SOURCES", "VORBISENC_SOURCES"):
        units += re.search(r"set\(" + name + r"\s+(.*?)\)", cmake, re.S)[1].split()
    if len(units) != 22 or len(set(units)) != 22:
        raise ValueError("Vorbis source inventory changed")
    for folder in ("include", "lib"):
        for path in sorted((src / folder).rglob("*")):
            if path.suffix not in (".h", ".c"):
                continue
            text = path.read_text(encoding="utf-8-sig")
            stable(OUT / "source" / path.relative_to(src), text)
    stable(OUT / "sources.json", json.dumps(units, indent=2) + "\n")
    return units


def build():
    units = prepare()
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    flags = [
        "/nologo",
        "/MT",
        "/TC",
        "/fp:precise",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/D_WIN32",
        "/DNOMINMAX",
        "/I" + str(OUT / "source/include"),
        "/I" + str(ROOT / "scratch/codec-xdk/include"),
        "/I" + str(sdk / "include/xbox"),
    ]
    for name in units:
        source = OUT / "source/lib" / name
        pre = folder / (source.stem + ".i")
        obj = folder / (source.stem + ".obj")
        precommand = [str(sdk / "bin/win32/cl.exe")] + flags + ["/P", "/Fi" + str(pre), str(source)]
        result = subprocess.run(precommand, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + ".pre.log"), result.stdout + result.stderr)
        if result.returncode:
            print(result.stdout[-2000:])
            raise SystemExit(1)
        data, stats = lower_c(pre.read_bytes())
        generated = OUT / "generated" / name
        generated.parent.mkdir(exist_ok=True)
        generated.write_bytes(data)
        command = [
            str(sdk / "bin/win32/cl.exe"),
            "/nologo",
            "/MT",
            "/TC",
            "/fp:precise",
            "/c",
            str(generated),
            "/Fo" + str(obj),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + ".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source=generated.relative_to(ROOT).as_posix(),
                preprocess_command=precommand,
                command=command,
                exit=result.returncode,
                statistics=stats,
                generated_sha256=hashlib.sha256(data).hexdigest(),
            )
        )
        print(name + ": " + str(result.returncode), flush=True)
        if result.returncode:
            print("\n".join(l for l in result.stdout.splitlines() if "error " in l)[:1800])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


def host():
    units = prepare()
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))[
        "host_environment"
    ]()
    folder = OUT / "host"
    folder.mkdir(exist_ok=True)
    command = [
        str(compiler),
        "/nologo",
        "/TC",
        "/std:c11",
        "/MD",
        "/O2",
        "/fp:precise",
        "/DNOMINMAX",
        "/D_CRT_SECURE_NO_WARNINGS",
        "/I" + str(OUT / "source/include"),
        "/I" + str(ROOT / "scratch/codec-xdk/include"),
        "/c",
    ]
    command += [str(OUT / "source/lib" / n) for n in units] + ["/Fo" + str(folder) + "/"]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    stable(folder / "build.log", result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Host Vorbis build failed: " + str(folder / "build.log"))
    libcommand = [
        str(compiler.parent / "lib.exe"),
        "/nologo",
        "/OUT:" + str(folder / "vorbis.lib"),
    ] + [str(folder / (Path(n).stem + ".obj")) for n in units]
    result = subprocess.run(libcommand, cwd=ROOT, env=env, capture_output=True, text=True)
    stable(folder / "library.log", result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Host Vorbis library failed")
    stable(
        folder / "build.json",
        json.dumps(
            dict(command=command, library_command=libcommand, exit=result.returncode), indent=2
        )
        + "\n",
    )
    print("22 full upstream Vorbis TUs built for host contracts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--host", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    elif args.host:
        host()
    else:
        prepare()
