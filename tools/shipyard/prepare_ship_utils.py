"""Generate the ShipUtils and 3drando RNG units for XDK."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once

OWN = ROOT / "platform/shipyard/ship-utils"
OUT = ROOT / "scratch/ship-utils-xdk"
SOURCES = [
    "soh/soh/ShipUtils.h",
    "soh/soh/ShipUtils.cpp",
    "soh/soh/Enhancements/randomizer/3drando/random.hpp",
    "soh/soh/Enhancements/randomizer/3drando/random.cpp",
]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def project(name, text):
    if name.endswith("ShipUtils.h"):
        text = once(
            text,
            "#include <libultraship/libultraship.h>",
            """#include <libultraship/libultra.h>
#ifdef __cplusplus
#include <array>
#include <vector>
#include <set>
#include <utility>
#include "ship-utils/support.h"
#endif""",
        )
        # Tag spellings expose the same game types to C consumers without
        # requiring a prior typedef from a different game header.
        text = text.replace("(Actor* actor)", "(struct Actor* actor)")
        text = text.replace(
            "(PlayState* play, Actor* actor)", "(struct PlayState* play, struct Actor* actor)"
        )
        text = text.replace("std::size(container)", "Shipyard::Utils::size(container)")
    if name.endswith(("ShipUtils.h", "random.hpp")):
        text = once(
            text,
            "template <typename Container> auto& RandomElement(",
            "template <typename Container> typename Shipyard::Utils::IndexedValue<Container>::type&"
            " RandomElement(",
        )
        text = once(
            text,
            "template <typename Container> const auto& RandomElement(",
            "template <typename Container> const typename Shipyard::Utils::IndexedValue<const"
            " Container>::type& RandomElement(",
        )
    if name.endswith("ShipUtils.cpp"):
        text = once(
            text,
            "#include <libultraship/libultraship.h>",
            "#include <libultraship/bridge/consolevariablebridge.h>\n#include"
            " <ship/utils/binarytools/endianness.h>",
        )
        text = once(text, "#include <random>", "#include <cassert>\n#include <cmath>")
        text = once(text, "constexpr f32 fourByThree", "const f32 fourByThree")
        text = once(text, "std::random_device{}()", "Shipyard::Utils::DeviceRandom()")
        text = once(
            text, "std::rotr(xorshifted, rot)", "Shipyard::Utils::RotateRight(xorshifted, rot)"
        )
        text = once(
            text, "ldexp(next32(state), -32)", "ldexp(static_cast<double>(next32(state)), -32)"
        )
    return text


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    generated = {}
    for name, digest in lock["sources"].items():
        original = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(original) != digest:
            raise ValueError("ShipUtils source drift: " + name)
        result = project(name, original)
        stable(OUT / "generated" / name, result)
        generated[name] = sha(result)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                generated=generated,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helpers={
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in OWN.glob("*")
                    if p.suffix in (".h", ".cpp")
                },
                full_units=[SOURCES[1], SOURCES[3]],
                entropy="XNetRandom; throw runtime_error on failure; caller owns XNet startup",
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    from prepare_game_interactor import includes as current_includes

    return [
        OUT / "generated/soh",
        ROOT / "platform/shipyard",
        ROOT / "platform/shipyard/game/include",
    ] + current_includes()


def build():
    prepare()
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    flags = [
        "/nologo",
        "/c",
        "/EHsc",
        "/GR",
        "/MT",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DF3DEX_GBI_2",
        "/DNOMINMAX",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/DINCLUDE_MPQ_SUPPORT",
        "/DCONTROLLERBUTTONS_T=uint32_t",
        "/FI" + str(ROOT / "scratch/configuration-xdk/generated/include/compile_definitions.h"),
        "/FI" + str(ROOT / "platform/shipyard/game/include/xdk_math_boundary.h"),
        "/I" + str(sdk / "include/xbox"),
    ]
    flags += ["/I" + str(p) for p in includes()]
    units = [OUT / "generated" / n for n in (SOURCES[1], SOURCES[3])] + [
        OWN / "native_entropy.cpp",
        OWN / "xdk_contract.cpp",
        OWN / "c_abi.c",
    ]
    rows = []
    for source in units:
        obj = folder / (source.stem + ".obj")
        command = (
            [str(sdk / "bin/win32/cl.exe")]
            + flags
            + [("/TC" if source.suffix == ".c" else "/TP"), str(source), "/Fo" + str(obj)]
        )
        preprocessing = None
        if source.suffix == ".c":
            from prepare_game import lower_c

            precommand = [str(sdk / "bin/win32/cl.exe")] + flags + ["/TC", "/E", str(source)]
            preprocessed = subprocess.run(precommand, cwd=ROOT, capture_output=True)
            if preprocessed.returncode:
                raise ValueError(
                    "C ABI preprocessing failed: " + preprocessed.stderr.decode(errors="replace")
                )
            lowered, stats = lower_c(preprocessed.stdout)
            staged = folder / "c_abi.i"
            staged.write_bytes(lowered)
            preprocessing = dict(
                command=precommand,
                exit=preprocessed.returncode,
                transformations=stats,
                lowered_sha256=hashlib.sha256(lowered).hexdigest(),
            )
            command = [
                str(sdk / "bin/win32/cl.exe"),
                "/nologo",
                "/c",
                "/TC",
                "/MT",
                str(staged),
                "/Fo" + str(obj),
            ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + ".log"), result.stdout + result.stderr)
        row = dict(
            source=source.relative_to(ROOT).as_posix(),
            command=command,
            exit=result.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if preprocessing:
            row["preprocessing"] = preprocessing
        if not result.returncode:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print(
                "\n".join(
                    line
                    for line in (result.stdout + result.stderr).splitlines()
                    if "error " in line
                )[:4500]
            )
        print(source.stem + ": " + str(result.returncode))
        rows.append(row)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    build() if args.build else prepare()
