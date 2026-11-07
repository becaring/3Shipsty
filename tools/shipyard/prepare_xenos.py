"""SoH Xenos API adapter and the build record for the compiled Shipyard core."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from dependency_sources import ROOT
from platform_base import resolve as resolve_platform_base
from prepare_archives import stable

OWN = ROOT / "platform/shipyard/xenos"
OUT = ROOT / "scratch/xenos-xdk"
PLATFORM_BASE = resolve_platform_base(ROOT)
CORE = PLATFORM_BASE / "sources/xenos/core.cpp"
SHADER_PROVIDER = PLATFORM_BASE / "sources/graphics/shader_provider.cpp"
SHADER_CACHE = PLATFORM_BASE / "sources/xenos/shader_cache.cpp"
SHADER_WORKER = PLATFORM_BASE / "sources/io/shader_worker.cpp"


def prepare():
    from prepare_fast3d import prepare as prepare_current_interfaces

    prepare_current_interfaces()
    api = (
        ROOT / "scratch/fast3d-xdk/generated/include/fast/backends/gfx_rendering_api.h"
    ).read_text()
    begin = api.index("  public:")
    end = api.index("  protected:", begin)
    declarations = (
        api[begin:end]
        .replace("virtual ~GfxRenderingAPI() {}", "virtual ~GfxRenderingAPIXenos();")
        .replace(" = 0", "")
    )
    declarations, count = re.subn(r"    GfxRenderingAPI\(\) :[^\n]+\n", "", declarations)
    if count != 1:
        raise ValueError("Current API base constructor drift")
    declarations = declarations.replace("~GfxRenderingAPIXenos();;", "~GfxRenderingAPIXenos();")
    header = (
        '#pragma once\n#include "fast/backends/gfx_rendering_api.h"\nnamespace Fast {\nclass'
        " GfxRenderingAPIXenos : public GfxRenderingAPI {\n"
        + declarations
        + "};\n}\n"
    )
    stable(OUT / "generated/xenos_backend.h", header)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                outputs={"xenos_backend.h": hashlib.sha256(header.encode()).hexdigest()},
                core_source=CORE.as_posix(),
                core_sha256=hashlib.sha256(CORE.read_bytes()).hexdigest(),
                shader_cache_sources={
                    p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (SHADER_CACHE, SHADER_WORKER)
                },
            ),
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    from prepare_window import includes

    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    flags = [
        "/nologo",
        "/c",
        "/TP",
        "/EHsc",
        "/GR",
        "/MT",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNOMINMAX",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/I" + str(sdk / "include/xbox"),
    ]
    flags += [
        "/I" + str(p)
        for p in [
            PLATFORM_BASE / "sources",
            PLATFORM_BASE / "sources/xenos",
            OUT / "generated",
            OWN,
            ROOT / "platform/shipyard",
            ROOT / "scratch/fast3d-xdk/generated/include",
            ROOT / "scratch/imgui-xdk/generated",
            PLATFORM_BASE / "sources/graphics",
        ]
        + includes()
    ]
    rows = []
    for source in [
        CORE,
        SHADER_PROVIDER,
        SHADER_CACHE,
        SHADER_WORKER,
        OWN / "api.cpp",
        OWN / "shader_provider.cpp",
        OWN / "services.cpp",
    ]:
        obj = folder / (
            "shipyard_shader_provider.obj" if source == SHADER_PROVIDER else source.stem + ".obj"
        )
        from xenos_capabilities import compiler_options

        options = flags + (compiler_options() if source == CORE else [])
        command = [str(sdk / "bin/win32/cl.exe")] + options + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        label = (
            "shipyard/" + source.relative_to(PLATFORM_BASE).as_posix()
            if source.is_relative_to(PLATFORM_BASE)
            else source.relative_to(ROOT).as_posix()
        )
        rows.append(dict(source=label, exit=result.returncode, command=command))
        print(source.name + ": " + str(result.returncode))
        if result.returncode:
            print("\n".join(l for l in result.stdout.splitlines() if "error " in l)[:3500])
        elif struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
            raise ValueError("Not Xenon")
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
