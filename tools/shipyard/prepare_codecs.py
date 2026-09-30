"""Prepare exact official audio codec headers and sources for native compilation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable

OUT = ROOT / "scratch/codec-xdk"


def prepare():
    sources = {name: verified(name) for name in ("opus", "opusfile", "ogg")}
    records = []
    for name, folder, destination in [
        ("opus", "include", "opus"),
        ("opusfile", "include", ""),
        ("ogg", "include/ogg", "ogg"),
    ]:
        for source in sorted((sources[name] / folder).glob("*.h")):
            target = OUT / "include" / destination / source.name
            data = source.read_bytes()
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)
            records.append(
                dict(
                    source=source.relative_to(ROOT).as_posix(),
                    output=target.relative_to(ROOT).as_posix(),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
    (OUT / "headers.json").write_text(json.dumps(records, indent=2) + "\n")
    units = {
        "ogg": ["src/bitwise.c", "src/framing.c"],
        "opusfile": ["src/info.c", "src/internal.c", "src/opusfile.c", "src/stream.c"],
        "opus": [],
    }
    for filename, sections in [
        ("opus_sources.mk", ("OPUS_SOURCES", "OPUS_SOURCES_FLOAT")),
        ("celt_sources.mk", ("CELT_SOURCES",)),
        ("silk_sources.mk", ("SILK_SOURCES", "SILK_SOURCES_FLOAT")),
    ]:
        text = (sources["opus"] / filename).read_text().replace("\\\n", " ")
        for section in sections:
            match = re.search(r"^" + section + r"\s*=\s*([^\n]+)", text, re.M)
            if not match:
                raise ValueError("Opus source manifest section missing: " + section)
            paths = match[1].split()
            if not all(path.endswith(".c") for path in paths):
                raise ValueError("Unexpected Opus source manifest entry")
            units["opus"].extend(paths)
    for name, source in sources.items():
        receipt = json.loads((ROOT / "scratch/deps" / (name + "-receipt.json")).read_text())
        for relative in receipt["files"]:
            path = source / relative
            if path.suffix not in (".h", ".c"):
                continue
            text = path.read_text(encoding="utf-8-sig")
            if name == "opus" and relative == "celt/arch.h":
                old = "#if defined(_MSC_VER)\n   _set_abort_behavior( 0, _WRITE_ABORT_MSG);"
                if text.count(old) != 1:
                    raise ValueError("Opus fatal Windows behavior guard drift")
                text = text.replace(
                    old,
                    "#if defined(_MSC_VER) && !defined(_XBOX)\n   _set_abort_behavior( 0,"
                    " _WRITE_ABORT_MSG);",
                )
            if name == "opus" and relative == "celt/ecintrin.h":
                old = "#if defined(_MSC_VER) && (_MSC_VER >= 1400)"
                if text.count(old) != 1:
                    raise ValueError("Opus bit-scan platform guard drift")
                text = text.replace(
                    old, "#if defined(_MSC_VER) && (_MSC_VER >= 1400) && !defined(_XBOX)"
                )
            if name == "opusfile" and relative == "src/stream.c":
                text = text.replace(
                    "# include <windows.h>",
                    "#ifdef _XBOX\n# include <xtl.h>\n# include <sys/stat.h>\n#else\n# include"
                    " <windows.h>\n#endif",
                )
                old = """  intptr_t h_file;
  h_file=_get_osfhandle(_fileno(_fp));
  if(h_file!=-1
   &&(GetFileType((HANDLE)h_file)&~FILE_TYPE_REMOTE)==FILE_TYPE_DISK){"""
                if text.count(old) != 1:
                    raise ValueError("Opus native file-type boundary drift")
                text = text.replace(
                    old,
                    """#ifdef _XBOX
  struct _stat info;
  if(_fstat(_fileno(_fp), &info)==0 && (info.st_mode & _S_IFMT)==_S_IFREG){
#else
"""
                    + old
                    + "\n#endif",
                )
                if text.count("#if !defined(_WIN32)") != 2:
                    raise ValueError("Opus wide filename guards changed")
                text = text.replace(
                    "#if !defined(_WIN32)", "#if !defined(_WIN32) || defined(_XBOX)"
                )
            stable(OUT / "source" / name / relative, text)
    stable(OUT / "source/opus/config.h", '#define PACKAGE_VERSION "1.6.1"\n')
    stable(OUT / "units.json", json.dumps(units, indent=2) + "\n")
    return units


def build(host=False):
    units = prepare()
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    folder = OUT / ("host" if host else "xdk")
    folder.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if host:
        compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))[
            "host_environment"
        ]()
        librarian = compiler.parent / "lib.exe"
    else:
        compiler = sdk / "bin/win32/cl.exe"
        librarian = sdk / "bin/win32/lib.exe"
    records = []
    libraries = {}
    includes = [
        OUT / "include",
        OUT / "source/opus",
        OUT / "source/opus/include",
        OUT / "source/opus/celt",
        OUT / "source/opus/silk",
        OUT / "source/opus/silk/float",
        OUT / "source/opus/dnn",
        OUT / "source/opusfile/include",
        OUT / "source/ogg/include",
    ]
    if not host:
        includes.append(sdk / "include/xbox")
    flags = [
        "/nologo",
        "/c",
        "/TC",
        "/MD" if host else "/MT",
        "/O2",
        "/fp:precise",
        "/D_CRT_SECURE_NO_WARNINGS",
    ]
    if not host:
        flags.append("/D_XBOX")
    flags += ["/I" + str(path) for path in includes]
    for group, paths in units.items():
        objects = []
        definitions = (
            [
                "/DOPUS_BUILD",
                "/DUSE_ALLOCA",
                "/DENABLE_HARDENING",
                "/DDISABLE_DEBUG_FLOAT",
                "/DHAVE_CONFIG_H",
            ]
            if group == "opus"
            else []
        )
        for relative in paths:
            source = OUT / "source" / group / relative
            obj = folder / (group + "-" + relative.replace("/", "__")[:-2] + ".obj")
            command = [str(compiler)] + flags + definitions + [str(source), "/Fo" + str(obj)]
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            stable(folder / (obj.stem + ".log"), result.stdout + result.stderr)
            records.append(
                dict(group=group, source=relative, exit=result.returncode, command=command)
            )
            if result.returncode == 0:
                if not host and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
                    raise ValueError("Not a Xenon object")
                objects.append(obj)
        if len(objects) != len(paths):
            continue
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
        stable(folder / (group + "-library.log"), result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Codec librarian failed: " + group)
        libraries[group] = hashlib.sha256(library.read_bytes()).hexdigest()
    stable(
        folder / "build.json",
        json.dumps(
            dict(objects=records, libraries=libraries, target_runtime_executed=False), indent=2
        )
        + "\n",
    )
    failures = [record for record in records if record["exit"]]
    print(str(len(records) - len(failures)) + "/" + str(len(records)) + " codec objects compile")
    for row in failures:
        print(row["group"] + "/" + row["source"])
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--host", action="store_true")
    args = parser.parse_args()
    if args.build:
        build(args.host)
    else:
        prepare()
        print("Prepared exact codec source/header manifests")
