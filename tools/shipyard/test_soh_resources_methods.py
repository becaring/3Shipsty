"""Audit complete pure methods without inventing Context/archive/CVar services."""

import hashlib
import json
import runpy
import subprocess
from prepare_soh_resources import ROOT, OUT, OWN, prepare, includes
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from dependency_sources import verified
from cpp_ast import PARSER, walk


def functions(text):
    return [n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type == "function_definition"]


def main():
    prepare()
    environment = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
    compiler, env = environment["host_environment"]()
    outputs = []
    records = []
    for projected in (False, True):
        folder = OUT / ("methods-projected" if projected else "methods-original")
        folder.mkdir(parents=True, exist_ok=True)
        base = OUT / "generated" if projected else ROOT
        source = base / "soh/soh/resource"
        sequence = (source / "importer/AudioSequenceFactory.cpp").read_text(encoding="utf-8-sig")
        helpers = sequence[
            sequence.index("template <typename T>") : sequence.index(
                "std::shared_ptr<Ship::IResource>\nResourceFactoryXMLAudioSequenceV0"
            )
        ]
        font = (source / "importer/AudioSoundFontFactory.cpp").read_text(encoding="utf-8-sig")
        picked = [
            f
            for f in functions(font)
            if any(n in f.split("{", 1)[0] for n in ("::MediumStrToInt(", "::CachePolicyToInt(", "::ParseEnvelopes("))
        ]
        assert len(picked) == 3
        picked = [f.replace("SOH::ResourceFactoryXMLSoundFontV0::ParseEnvelopes", "ParseEnvelopes") for f in picked]
        path = [
            f
            for f in functions((source / "importer/PathFactory.cpp").read_text(encoding="utf-8-sig"))
            if "ResourceFactoryXMLPathV0::ReadResource" in f
        ][0]
        prefix = """#include "soh/resource/importer/AudioSequenceFactory.h"
#include "soh/resource/importer/AudioSoundFontFactory.h"
#include "soh/resource/importer/PathFactory.h"
#include "soh/resource/type/Path.h"
#include "ship/utils/binarytools/BinaryWriter.h"
#include "soh-resources/format.h"
#include <type_traits>
#include <stdexcept>
#include <cstring>
#include <tinyxml2.h>
#include "soh/resource/audio_enums.h"
namespace SOH {
"""
        audit = (
            prefix
            + helpers
            + "\n".join(picked)
            + "\n"
            + path
            + "\n}\n"
            + (OWN / "method_contract.cpp").read_text(encoding="utf-8-sig")
        )
        stable(folder / "audit.cpp", audit)
        resources = ROOT / "scratch/resources-xdk/generated" if projected else ROOT / "libultraship"
        binary = ROOT / "scratch/binary-xdk/generated" if projected else ROOT / "libultraship"
        sources = [folder / "audit.cpp", source / "type/Path.cpp", verified("tinyxml2") / "tinyxml2.cpp"]
        sources += [resources / "src/ship/resource" / (n + ".cpp") for n in ("Resource", "ResourceFactoryXML")]
        sources += [
            binary / "src/ship/utils/binarytools" / (n + ".cpp")
            for n in ("BinaryReader", "BinaryWriter", "MemoryStream", "Stream")
        ]
        if projected:
            sources += [
                PLATFORM_BASE / "sources/async/native.cpp",
                PLATFORM_BASE / "sources/clock/chrono.cpp",
                ROOT / "platform/shipyard/logging/environment.cpp",
            ]
        paths = includes(projected) + [OUT / "generated/soh", ROOT / "platform/shipyard", PLATFORM_BASE / "sources"]
        command = [
            str(compiler),
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/MD",
            "/DNOMINMAX",
            "/DSPDLOG_ACTIVE_LEVEL=0",
        ]
        command += ["/I" + str(p) for p in paths] + [str(p) for p in sources]
        command += ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "audit.exe")]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("See " + str(folder / "build.log"))
        result = subprocess.run([str(folder / "audit.exe")], cwd=folder, capture_output=True, text=True)
        stable(folder / "run.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Method audit failed: " + str(folder))
        outputs.append(result.stdout)
        records.append(
            dict(
                command=command,
                exit=result.returncode,
                audit_sha256=hashlib.sha256(audit.encode()).hexdigest(),
                output_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(),
            )
        )
    assert outputs[0] == outputs[1]
    stable(
        OUT / "methods.json",
        json.dumps(
            dict(
                cases=records,
                sequence_cases=4 * len(range(0, 65536, 127)),
                scope="Complete extracted pure methods only; real full production TUs separately compile with XDK",
                target_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(
        "Original/projected: 2068 sequence bytecode cases, XML path, BE envelope bytes, enum/error and formatting audits agree"
    )


if __name__ == "__main__":
    main()
