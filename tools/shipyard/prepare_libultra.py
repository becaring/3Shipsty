"""Project complete pinned LUS libultra and remaining C bridges; no upstream edits."""

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path
from prepare_archives import stable
from prepare_configuration import once
from platform_base import resolve as resolve_platform_base

ROOT = Path(__file__).resolve().parents[2]
OWN = ROOT / "platform/shipyard/libultra"
OUT = ROOT / "scratch/libultra-xdk"
PLATFORM_BASE = resolve_platform_base(ROOT)


def transform(name, text):
    if "/libultra/" in name and text:
        text = once(
            text,
            '#include "libultraship/libultraship.h"',
            '#include "libultraship/libultra.h"\n#include <cstring>',
        )
    if name.endswith("/os_eeprom.cpp"):
        text = '#include "ship/Context.h"\n#include <cstdio>\n' + text
    if name.endswith("/os.cpp"):
        text = once(
            text,
            "#include <SDL2/SDL.h>",
            '#include "ship/Context.h"\n#include'
            ' "ship/controller/controldeck/ControlDeck.h"\n#include "libultra/platform.h"',
        )
        begin = text.index("#include <ratio>")
        end = text.index('extern "C" {', begin)
        text = text[:begin] + text[end:]
        begin = text.index("    std::string controllerDb")
        end = text.index("    Ship::Context::GetInstance()->GetControlDeck()->Init", begin)
        text = (
            text[:begin]
            + "    // Xbox physical discovery is owned by the real XInput-backed ControlDeck.\n"
            + text[end:]
        )
        text = once(
            text,
            "std::chrono::duration_cast<n64CycleRateDuration>(std::chrono::steady_clock::now().time_since_epoch()).count()",
            "Shipyard::Libultra::NowCycles()",
        )
        text = once(
            text,
            "std::chrono::duration_cast<n64CycleRateDuration>(std::chrono::steady_clock::now().time_since_epoch())\n"
            "               .count()",
            "Shipyard::Libultra::NowCycles()",
        )
        text = once(
            text,
            "std::chrono::duration_cast<n64CycleRateDuration>(std::chrono::steady_clock::now().time_since_epoch())\n"
            "        .count()",
            "Shipyard::Libultra::NowCycles()",
        )
    if name.endswith("/os_vi.cpp"):
        text = '#include "libultra/platform.h"\n' + text
        text = text.replace("Uint32", "uint32_t")
        text = once(
            text,
            "SDL_AddTimer(16, &__lusViCallback, NULL);",
            "Shipyard::Libultra::AddTimer(16, &__lusViCallback, NULL);",
        )
    if name.endswith("/resourcebridge.cpp"):
        from lookup_cost_projection import resource_bridge

        text = resource_bridge('#include "ship/resource/ResourceManager.h"\n' + text)
    if name.endswith("/gfxbridge.cpp"):
        # XDK does not find this explicit-template call through ADL.
        text = once(
            text,
            "gfx = static_pointer_cast<Fast::Fast3dWindow>",
            "gfx = std::static_pointer_cast<Fast::Fast3dWindow>",
        )
    return text


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    pending = {}
    for name, expected in lock["sources"].items():
        text = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("LUS input drift " + name)
        if name.endswith(".cpp"):
            pending[name] = transform(name, text)
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            {n: hashlib.sha256(t.encode()).hexdigest() for n, t in pending.items()}, indent=2
        )
        + "\n",
    )


def includes():
    from prepare_gui import includes as gui_includes

    return [ROOT / "platform/shipyard", PLATFORM_BASE / "sources"] + gui_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
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
        "/DF3DEX_GBI_2",
        "/DINCLUDE_MPQ_SUPPORT",
        "/DCONTROLLERBUTTONS_T=uint32_t",
        "/Dnssv_CONFIG_SELECT_STRING_VIEW=1",
        "/I" + str(sdk / "include/xbox"),
    ]
    flags += [
        "/FI" + str(ROOT / "scratch/configuration-xdk/generated/include/compile_definitions.h")
    ] + ["/I" + str(p) for p in includes()]
    rows = []
    for name in json.loads((OUT / "manifest.json").read_text()):
        source = OUT / "generated" / name
        obj = folder / (source.stem + ".obj")
        command = [str(sdk / "bin/win32/cl.exe")] + flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source=source.relative_to(ROOT).as_posix(), exit=result.returncode, command=command
            )
        )
        print(source.name + ": " + str(result.returncode), flush=True)
        if result.returncode:
            print("\n".join(l for l in result.stdout.splitlines() if "error " in l)[:2000])
        elif struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
            raise ValueError("Not Xenon")
    for name in ("clock.cpp", "timer.cpp"):
        source = PLATFORM_BASE / "sources/libultra" / name
        obj = folder / name.replace(".cpp", ".obj")
        command = [str(sdk / "bin/win32/cl.exe")] + flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source="shipyard/sources/libultra/" + name,
                exit=result.returncode,
                command=command,
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        )
        print(name + ": " + str(result.returncode), flush=True)
        if not result.returncode and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
            raise ValueError("Not Xenon")
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)
    # Upstream supplies these as a static library. Preserve archive extraction:
    # SoH stubs.c already owns the cache entry points and osCreatePiManager.
    command = [
        str(sdk / "bin/win32/lib.exe"),
        "/nologo",
        "/out:" + str(folder / "shipyard_libultra.lib"),
    ] + [str(folder / (Path(row["source"]).stem + ".obj")) for row in rows]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(folder / "archive.log", result.stdout + result.stderr)
    stable(
        folder / "archive.json",
        json.dumps(dict(command=command, exit=result.returncode), indent=2) + "\n",
    )
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
