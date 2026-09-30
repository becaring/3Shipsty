"""Current sample factory binary and codec-worker methods, no fake archive service."""

import hashlib
import json
import math
import runpy
import struct
import subprocess
import wave
from prepare_soh_resources import ROOT, OWN, OUT, prepare, includes
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from cpp_ast import PARSER, walk


def main():
    prepare()
    folder = OUT / "audio-contract"
    folder.mkdir(exist_ok=True)
    wav = folder / "sample.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(32000)
        f.writeframes(b"".join(struct.pack("<h", round(12000 * math.sin(i * 0.13))) for i in range(8192)))
    fixtures = [wav]
    encoders = {"mp3": "libmp3lame", "flac": "flac", "ogg": "libvorbis"}
    encodes = []
    for suffix, encoder in encoders.items():
        output = folder / ("sample." + suffix)
        command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(wav), "-c:a", encoder, str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        fixtures.append(output)
        encodes.append(command)
    environment = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
    compiler, env = environment["host_environment"]()
    outputs = []
    records = []
    for projected in (False, True):
        dest = folder / ("projected" if projected else "original")
        dest.mkdir(exist_ok=True)
        base = OUT / "generated" if projected else ROOT
        text = (base / "soh/soh/resource/importer/AudioSampleFactory.cpp").read_text()
        # Exactly one XML method acquires real Context/archive files. All actual
        # codec workers, binary parser and codec-name method remain in this audit.
        nodes = [
            n
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "function_definition"
            and b"ResourceFactoryXMLAudioSampleV0::ReadResource" in n.child_by_field_name("declarator").text
        ]
        assert len(nodes) == 1
        node = nodes[0]
        raw = text.encode()
        text = (raw[: node.start_byte] + raw[node.end_byte :]).decode()
        for unused in ("<ship/Context.h>", "<ship/resource/archive/Archive.h>", "<ship/resource/ResourceManager.h>"):
            text = text.replace("#include " + unused, "// Unused service header omitted in this bounded host audit.")
        if not projected:
            text = text.replace('#include "z64.h"', "").replace(
                '#include "z64audio.h"', '#include "soh/resource/audio_enums.h"'
            )
        stable(dest / "factory_contract.cpp", text + "\n" + (OWN / "audio_sample_contract.cpp").read_text())
        inc = includes(projected) + [PLATFORM_BASE / "sources"]
        if not projected:
            inc += [OUT / "generated/soh"]
        resources = ROOT / "scratch/resources-xdk/generated" if projected else ROOT / "libultraship"
        binary = ROOT / "scratch/binary-xdk/generated" if projected else ROOT / "libultraship"
        sources = [dest / "factory_contract.cpp", base / "soh/soh/resource/type/AudioSample.cpp"]
        sources += [
            resources / "src/ship/resource" / (n + ".cpp")
            for n in ("Resource", "ResourceFactoryBinary", "ResourceFactoryXML")
        ]
        sources += [
            binary / "src/ship/utils/binarytools" / (n + ".cpp") for n in ("BinaryReader", "MemoryStream", "Stream")
        ]
        if projected:
            sources += [
                PLATFORM_BASE / "sources/async/native.cpp",
                PLATFORM_BASE / "sources/clock/chrono.cpp",
                ROOT / "platform/shipyard/logging/environment.cpp",
            ]
        command = [
            str(compiler),
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/GR",
            "/MD",
            "/DNOMINMAX",
            "/DSPDLOG_ACTIVE_LEVEL=0",
        ]
        command += (
            ["/I" + str(p) for p in inc]
            + [str(p) for p in sources]
            + [
                str(ROOT / "scratch/vorbis-xdk/host/vorbis.lib"),
                str(ROOT / "scratch/codec-xdk/host/ogg.lib"),
                "/Fo:" + str(dest) + "/",
                "/Fe:" + str(dest / "contract.exe"),
            ]
        )
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(dest / "build.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("See " + str(dest / "build.log"))
        result = subprocess.run(
            [str(dest / "contract.exe")] + [str(p) for p in fixtures], cwd=dest, capture_output=True, text=True
        )
        record = dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        stable(dest / "run.json", json.dumps(record, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(result.stderr)
        records.append(record)
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    stable(
        OUT / "audio-verification.json",
        json.dumps(
            dict(
                cases=records,
                fixture_generation=encodes,
                fixtures={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures},
                target_runtime_executed=False,
                real_xml_acquisition_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(outputs[0])


if __name__ == "__main__":
    main()
