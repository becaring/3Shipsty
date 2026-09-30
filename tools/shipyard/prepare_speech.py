"""Pinned eSpeak NG and modern SoH speech platform projection."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from platform_base import resolve as resolve_platform_base

OWN = ROOT / "platform/shipyard/speech"
OUT = ROOT / "scratch/speech-xdk"
DEP = OUT / "espeak-ng"
GEN = OUT / "generated/espeak-ng"
PLATFORM_BASE = resolve_platform_base(ROOT)
PIN = "4870adfa25b1a32b4361592f1be8a40337c58d6c"
SDK = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")


def prepare_engine():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=DEP, text=True).strip() == PIN
    subprocess.run(["git", "diff", "--exit-code", "--quiet", "HEAD", "--"], cwd=DEP, check=True)
    inputs = {}
    outputs = {}
    for p in sorted((DEP / "src").rglob("*")):
        if p.suffix not in (".h", ".c", ".inc"):
            continue
        rel = p.relative_to(DEP).as_posix()
        raw = p.read_bytes()
        inputs[rel] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
        if rel.startswith("src/include/compat/"):
            text = re.sub(
                r"<\.\./include/([^>]+)>",
                lambda m: '"' + (SDK / "include/xbox" / m[1]).as_posix() + '"',
                text,
            )
        if rel in ["src/include/espeak-ng/espeak_ng.h", "src/include/espeak-ng/speak_lib.h"]:
            text = text.replace(
                "#if defined(_WIN32) || defined(_WIN64)",
                "#if (defined(_WIN32) || defined(_WIN64)) && !defined(SHIPYARD_ESPEAK_STATIC)",
            )
        if rel == "src/libespeak-ng/speech.c":
            text = text.replace(
                "#include <windows.h>",
                "#ifdef _XBOX\n#include <xtl.h>\n#else\n#include <windows.h>\n#include"
                " <winreg.h>\n#endif",
            ).replace(
                "\n#include <winreg.h>\n#endif\n#include <winreg.h>",
                "\n#include <winreg.h>\n#endif",
            )
            text = text.replace(
                "#if PLATFORM_WINDOWS\n\tHKEY RegKey;",
                "#if PLATFORM_WINDOWS && !defined(_XBOX)\n\tHKEY RegKey;",
            )
            text = text.replace(
                "#elif !defined(PLATFORM_DOS)", "#elif !defined(PLATFORM_DOS) && !defined(_XBOX)"
            )
        if rel == "src/libespeak-ng/voices.c":
            text = text.replace(
                "#include <windows.h>",
                "#ifdef _XBOX\n#include <xtl.h>\n#else\n#include <windows.h>\n#endif",
            )
        if rel == "src/libespeak-ng/readclause.c":
            text = once(
                text,
                "static const char *LookupCharName",
                "typedef const char* ShipyardSpeechCharName;\nstatic ShipyardSpeechCharName"
                " LookupCharName",
            )
        if rel == "src/libespeak-ng/synthdata.c":
            text = '#include "speech/data_boundary.h"\n' + text
            text = once(
                text,
                "\tfclose(f_in);\n\tif (size != NULL)",
                "\tfclose(f_in);\n#ifdef ARCH_BIG\n\tif (!ShipyardSpeechFixupData(*ptr, length,"
                " fname, path_home)) { free(*ptr); *ptr = NULL; return EINVAL; }\n#endif\n\tif"
                " (size != NULL)",
            )
        from cpp_ast import PARSER, walk
        from prepare_custom_message import escape_literal
        from prepare_randomizer import edits_apply

        literal_edits = [
            (n.start_byte, n.end_byte, escape_literal(n.text.decode()))
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "string_literal" and any(c > 127 for c in n.text)
        ]
        text = edits_apply(text.encode(), literal_edits)
        stable(GEN / rel, text)
        outputs[rel] = hashlib.sha256(text.encode()).hexdigest()
    units = re.search(
        r"add_library\(espeak-ng\s+(.*?)\n\)",
        (DEP / "src/libespeak-ng/CMakeLists.txt").read_text(),
        re.S,
    )[1].split()
    units = (
        ["src/libespeak-ng/" + u for u in units]
        + ["src/libespeak-ng/klatt.c"]
        + [p.relative_to(DEP).as_posix() for p in sorted((DEP / "src/ucd-tools/src").glob("*.c"))]
    )
    stable(
        OUT / "engine-manifest.json",
        json.dumps(
            dict(
                repository="https://github.com/espeak-ng/espeak-ng",
                tag="1.52.0",
                commit=PIN,
                inputs=inputs,
                generated=outputs,
                units=units,
            ),
            indent=2,
        )
        + "\n",
    )
    return units


def engine_flags():
    roots = [
        OWN / "include",
        PLATFORM_BASE / "sources",
        ROOT / "platform/shipyard",
        ROOT / "platform/shipyard/game/include",
        GEN / "src/include",
        GEN / "src/include/compat",
        GEN / "src/ucd-tools/src/include",
        SDK / "include/xbox",
    ]
    return [
        str(SDK / "bin/win32/cl.exe"),
        "/nologo",
        "/TC",
        "/MT",
        "/O2",
        "/Gy",
        "/W3",
        "/D_XBOX",
        "/D_XENON",
        "/DSHIPYARD_ESPEAK_STATIC",
        "/Dinline=__inline",
    ] + ["/I" + str(p) for p in roots]


def build_engine():
    units = prepare_engine()
    folder = OUT / "xdk-engine"
    folder.mkdir(parents=True, exist_ok=True)
    flags = engine_flags()
    rows = []
    from prepare_game import lower_c

    for rel in units:
        source = GEN / rel
        stem = rel.replace("/", "__")[:-2]
        obj = folder / (stem + ".obj")
        pre = flags + ["/E", str(source)]
        r = subprocess.run(pre, cwd=ROOT, capture_output=True)
        row = dict(source=rel, preprocess_command=pre, preprocess_exit=r.returncode)
        stable(folder / (stem + ".pre.log"), r.stderr.decode(errors="replace"))
        if not r.returncode:
            stable(folder / (stem + ".i"), r.stdout.decode("utf-8"))
            try:
                lowered, stats = lower_c(r.stdout)
                target = folder / (stem + ".c")
                stable(target, lowered.decode())
                command = flags + ["/c", str(target), "/Fo" + str(obj)]
                c = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                stable(folder / (stem + ".log"), c.stdout + c.stderr)
                row.update(command=command, exit=c.returncode, lowering=stats)
                if not c.returncode:
                    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
                    row.update(
                        object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest(),
                        lowered_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                        machine="PowerPC big-endian COFF 0x1f2",
                    )
                else:
                    print(
                        "\n".join(s for s in c.stdout.splitlines() if "error " in s)[:1800],
                        flush=True,
                    )
            except Exception as e:
                row["projection_error"] = str(e)
                print(str(e)[:1800], flush=True)
        else:
            print(r.stderr.decode(errors="replace")[:1600], flush=True)
        rows.append(row)
        print(rel, row.get("exit", row.get("projection_error", r.returncode)), flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    return all(r.get("exit") == 0 for r in rows)


def prepare_application():
    from prepare_enhancements import transform
    from prepare_custom_message import lower_literals

    sources = [
        "soh/soh/Enhancements/speechsynthesizer/" + name
        for name in [
            "SpeechSynthesizer.h",
            "SpeechSynthesizer.cpp",
            "SpeechLogger.h",
            "SpeechLogger.cpp",
        ]
    ] + ["soh/soh/Enhancements/tts/tts.cpp", "soh/soh/Enhancements/randomizer/ShuffleSpeak.cpp"]
    rows = {}
    outputs = {}
    lock = json.loads((OWN / "sources.lock.json").read_text())["files"]
    for name in sources:
        raw = (ROOT / name).read_bytes()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
        rows[name] = hashlib.sha256(raw).hexdigest()
        assert rows[name] == lock[name], "Pinned speech source changed: " + name
        if name.endswith("SpeechSynthesizer.h"):
            text = once(
                text,
                "#ifdef _WIN32",
                '#if defined(_XBOX)\n#include "speech/XboxSpeechSynthesizer.h"\n#elif'
                " defined(_WIN32)",
            )
        if name.endswith("SpeechLogger.cpp"):
            text = text.replace(
                "#include <libultraship/libultraship.h>", "#include <libultraship/log/luslog.h>"
            )
        if name.endswith("ShuffleSpeak.cpp"):
            text = (
                '#include "z64.h"\n#include "soh/Enhancements/randomizer/SeedContext.h"\n#include'
                ' "soh/Enhancements/game-interactor/GameInteractor.h"\n#include'
                ' "soh/ShipInit.hpp"\n'
                + text
            )
        if name.endswith("tts.cpp"):
            text = '#include "soh-resources/format.h"\n' + text
            text = text.replace("snprintf(", "Shipyard::SohResources::snprintf(")
            text = text.replace(
                "#include <libultraship/classes.h>",
                "#include <libultraship/bridge.h>\n#include <ship/Context.h>\n#include"
                " <ship/resource/ResourceManager.h>",
            )
            text, count = re.subn(
                r"std::to_string\(([^()]*)\)", r"std::to_string(static_cast<long long>(\1))", text
            )
            assert count == 7
        if name.endswith(("tts.cpp", "ShuffleSpeak.cpp")):
            text = transform(name, text)
        if name.endswith(".cpp"):
            text, literals = lower_literals(text)
        stable(OUT / "generated" / name, text)
        outputs[name] = hashlib.sha256(text.encode()).hexdigest()
    stable(
        OUT / "application-manifest.json",
        json.dumps(dict(inputs=rows, generated=outputs), indent=2) + "\n",
    )


def build_application():
    prepare_application()
    folder = OUT / "xdk-application"
    folder.mkdir(parents=True, exist_ok=True)
    flags = json.loads((ROOT / "scratch/randomizer-content-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    flags[1:1] = [
        "/DSHIPYARD_ESPEAK_STATIC",
        "/I" + str(PLATFORM_BASE / "sources"),
        "/I" + str(PLATFORM_BASE / "sources/json/include"),
        "/I" + str(PLATFORM_BASE / "sources/value_types"),
        "/I" + str(OUT / "generated/soh"),
        "/I" + str(GEN / "src/include"),
    ]
    sources = sorted((OUT / "generated/soh").rglob("*.cpp")) + [
        OWN / "XboxSpeechSynthesizer.cpp",
        PLATFORM_BASE / "sources/speech/data_boundary.c",
    ]
    rows = []
    for source in sources:
        command = (
            [p for p in flags if p != "/TP"]
            + (["/TC"] if source.suffix == ".c" else [])
            + [str(source), "/Fo" + str(folder / (source.stem + ".obj"))]
        )
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + ".log"), r.stdout + r.stderr)
        row = dict(
            source=(
                ("platform_base:" + source.relative_to(PLATFORM_BASE).as_posix())
                if PLATFORM_BASE in source.parents
                else source.relative_to(ROOT).as_posix()
            ),
            command=command,
            exit=r.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if not r.returncode:
            obj = folder / (source.stem + ".obj")
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row.update(
                object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest(),
                machine="PowerPC big-endian COFF 0x1f2",
            )
        rows.append(row)
        print(source.name, r.returncode, flush=True)
        if r.returncode:
            print("\n".join(s for s in r.stdout.splitlines() if "error " in s)[:4000], flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    return all(r["exit"] == 0 for r in rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", action="store_true")
    p.add_argument("--application", action="store_true")
    p.add_argument("--prepare-application", action="store_true")
    a = p.parse_args()
    if a.engine:
        raise SystemExit(0 if build_engine() else 1)
    if a.application:
        raise SystemExit(0 if build_application() else 1)
    if a.prepare_application:
        prepare_application()
        raise SystemExit(0)
    prepare_engine()
