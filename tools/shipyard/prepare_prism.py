"""Pinned Prism and the DX shader builder, keeping resources."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable
from prepare_configuration import once
from platform_base import resolve as resolve_platform_base
from cpp_ast import PARSER

OUT = ROOT / "scratch/prism-xdk"
PLATFORM_BASE = resolve_platform_base(ROOT)
from xbox360_platform.prism import PrismProjector

PROJECTOR = PrismProjector(PARSER, "bbcbc7e3f890a5806b579361e7aa0336acd547e7")


def source_builder(text, compat):
    start = text.index("#define RAND_NOISE")
    end = text.rindex("} // namespace Fast")
    text = text[start:end]
    if compat:
        start = text.index("    prism::ContextItems mContext = {")
        end = text.index("\n    };", start) + 7
        entries = text[start:end].splitlines()[1:-1]
        lines = ["    prism::ContextItems mContext;"]
        for entry in entries:
            match = re.fullmatch(r'\s*\{ "([^"]+)", (.*) \},', entry)
            if not match:
                raise ValueError("Current shader context shape drift " + entry)
            expression = match[2]
            if re.fullmatch(r"SHADER_[A-Z0-9_]+", expression):
                expression = "static_cast<int>(" + expression + ")"
            lines.append(
                '    mContext["' + match[1] + '"] = prism::ContextTypes(' + expression + ");"
            )
        if len(entries) != 38:
            raise ValueError("Shader context inventory drift " + str(len(entries)))
        text = text[:start] + "\n".join(lines) + text[end:]
        text = PROJECTOR.lower(text, "shader_builder.cpp")
        # Keep all includes outside the Fast namespace.
        text = once(text, "#include <prism/compat.h>\n", "")
        text = text.replace(
            "static_pointer_cast<Ship::Shader>", "std::static_pointer_cast<Ship::Shader>"
        )
    return (
        '#include "prism/processor.h"\n#include "fast/interpreter.h"\n'
        '#include "ship/Context.h"\n#include "ship/resource/ResourceManager.h"\n'
        '#include "ship/resource/type/Shader.h"\n#include "ship/resource/ResourceType.h"\n'
        "#include <spdlog/spdlog.h>\nnamespace Fast {\n"
        + text
        + "\n}\n"
    )


def prepare():
    dependency = verified("prism")
    pending = {}
    for name in (
        "compat.h",
        "xbox_compat/common.h",
        "xbox_compat/optional.h",
        "xbox_compat/variant.h",
    ):
        stale = OUT / "generated" / name
        if stale.is_file():
            stale.unlink()
    for path in sorted((dependency / "src/prism").rglob("*")):
        if path.suffix not in (".h", ".cpp", ".c"):
            continue
        name = path.relative_to(dependency / "src").as_posix()
        text = path.read_text(encoding="utf-8-sig")
        pending[name] = PROJECTOR.lower(text, path.name) if path.suffix != ".c" else text
    dx = ROOT / "libultraship/src/fast/backends/gfx_direct3d11.cpp"
    text = dx.read_text(encoding="utf-8-sig")
    locks = json.loads((ROOT / "platform/shipyard/graphics/source-lock.json").read_text())
    # This release builder was already pinned by the graphics differential audit.
    expected = locks["inputs"]["libultraship/src/fast/backends/gfx_direct3d11.cpp"]
    if hashlib.sha256(dx.read_bytes()).hexdigest() != expected:
        raise ValueError("Pinned DX builder drift")
    pending["shader_builder.cpp"] = source_builder(text, True)
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "reference/shader_builder.cpp",
        source_builder(dx.read_text(encoding="utf-8-sig"), False),
    )
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                prism_commit="bbcbc7e3f890a5806b579361e7aa0336acd547e7",
                outputs={n: hashlib.sha256(t.encode()).hexdigest() for n, t in pending.items()},
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
        "/EHsc",
        "/GR",
        "/MT",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNOMINMAX",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/Dnssv_CONFIG_SELECT_STRING_VIEW=1",
        "/I" + str(sdk / "include/xbox"),
    ]
    flags += [
        "/I" + str(p)
        for p in [
            PLATFORM_BASE / "sources",
            PLATFORM_BASE / "sources/value_types",
            OUT / "generated",
            ROOT / "scratch/fast3d-xdk/generated/include",
            ROOT / "scratch/gui-resources-xdk/generated/include",
            ROOT / "scratch/context-xdk/generated/include",
        ]
        + includes()
        + [ROOT / "scratch/async-xdk/generated"]
    ]
    sources = [
        OUT / "generated" / n
        for n in (
            "prism/lexer.cpp",
            "prism/ast.cpp",
            "prism/processor.cpp",
            "prism/utils/gv.cpp",
            "prism/utils/invoke.c",
            "shader_builder.cpp",
        )
    ]
    records = []
    for source in sources:
        obj = folder / (source.stem + ".obj")
        command = (
            [str(sdk / "bin/win32/cl.exe")]
            + flags
            + ["/TC" if source.suffix == ".c" else "/TP", str(source), "/Fo" + str(obj)]
        )
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        records.append(
            dict(
                source=source.relative_to(ROOT).as_posix(), exit=result.returncode, command=command
            )
        )
        if not result.returncode and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
            raise ValueError("Not Xenon")
        print(source.name + ": " + str(result.returncode))
        if result.returncode:
            print("\n".join(l for l in result.stdout.splitlines() if "error " in l)[:2200])
    stable(folder / "build.json", json.dumps(records, indent=2) + "\n")
    if any(r["exit"] for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
