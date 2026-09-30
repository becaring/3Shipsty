"""Execute full original/projected factories and matching release archive payloads."""

import hashlib
import json
import runpy
import struct
import subprocess
import zipfile
from prepare_fast_resources import ROOT, OUT, OWN, prepare
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from dependency_sources import verified


def main():
    prepare()
    first = (OUT / "manifest.json").read_bytes()
    prepare()
    assert first == (OUT / "manifest.json").read_bytes()
    environment = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_resources.py"))
    compiler, env = environment["ENV"].host_environment()
    records = []
    outputs = []
    counts = {}
    fixture = OUT / "archive-payloads.bin"
    with fixture.open("wb") as target:
        for archive in sorted((ROOT / "scratch/assets/official-9.2.3").rglob("*.o2r")):
            with zipfile.ZipFile(archive) as z:
                for name in sorted(z.namelist()):
                    data = z.read(name)
                    if len(data) < 64 or data[0] not in (0, 1):
                        continue
                    kind, version = struct.unpack_from((">" if data[0] else "<") + "II", data, 4)
                    if kind not in (0x4F444C54, 0x4F544558, 0x4F565458, 0x4F4D5458):
                        continue
                    assert version == 0 or (kind == 0x4F544558 and version == 1)
                    target.write(struct.pack("<IIII", kind, version, data[0], len(data) - 64))
                    target.write(data[64:])
                    counts[str(hex(kind))] = counts.get(str(hex(kind)), 0) + 1
    assert sum(counts.values()) > 1000, "Matching official archive fixture missing"
    for projected in (False, True):
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        base = OUT / "generated" if projected else ROOT / "libultraship"
        gui = ROOT / "scratch/gui-resources-xdk/generated" if projected else ROOT / "libultraship"
        resource = ROOT / "scratch/resources-xdk/generated" if projected else ROOT / "libultraship"
        binary = ROOT / "scratch/binary-xdk/generated" if projected else ROOT / "libultraship"
        includes = (
            [base / "include", gui / "include", verified("tinyxml2"), PLATFORM_BASE / "sources"]
            + environment["includes"](projected)
            + [ROOT / "libultraship/include"]
        )
        sources = [
            base / n for n in json.loads((OWN / "sources.lock.json").read_text())["sources"] if n.endswith(".cpp")
        ]
        sources += [
            gui / "src/fast/resource/type/Texture.cpp",
            OWN / "contract.cpp",
            verified("tinyxml2") / "tinyxml2.cpp",
        ]
        sources += [
            resource / "src/ship/resource" / (n + ".cpp")
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
            "/DF3DEX_GBI_2",
            "/DSPDLOG_ACTIVE_LEVEL=0",
        ]
        if projected:
            command += ["/DSHIPYARD_PROJECTION"]
        command += (
            ["/I" + str(p) for p in includes]
            + [str(p) for p in sources]
            + ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
        )
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("See " + str(folder / "build.log"))
        result = subprocess.run(
            [str(folder / "contract.exe"), str(fixture)], cwd=folder, capture_output=True, text=True
        )
        record = dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        stable(folder / "run.json", json.dumps(record, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(str(record))
        records.append(record)
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1], "Factory parity differs"
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                cases=records,
                archive_counts=counts,
                fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                target_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(outputs[0])


if __name__ == "__main__":
    main()
