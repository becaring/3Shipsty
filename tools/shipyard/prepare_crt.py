"""Compile narrow genuine C runtime providers absent from the Xbox 360 CRT."""

import argparse, hashlib, json, struct, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from platform_base import resolve as resolve_platform_base

OWN = resolve_platform_base(ROOT) / "sources/crt"
OUT = ROOT / "scratch/crt-xdk"
SDK = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
UNITS = ("float.cpp", "format.cpp")


def stable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != value:
        path.write_text(value, encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label(path):
    return "shipyard/sources/crt/" + path.name


def prepare():
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                kind="generic Shipyard Xbox CRT compatibility",
                sources={label(p): sha(p) for p in sorted(OWN.glob("*")) if p.is_file()},
                generator_sha256=sha(Path(__file__)),
            ),
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    rows = []
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    for name in UNITS:
        source = OWN / name
        obj = folder / (source.stem + ".obj")
        command = [
            str(SDK / "bin/win32/cl.exe"),
            "/nologo",
            "/c",
            "/MT",
            "/O2",
            "/fp:strict",
            "/D_XBOX",
            "/D_XBOX_VER=200",
            "/D_CRT_SECURE_NO_WARNINGS",
            "/I" + str(SDK / "include/xbox"),
            str(source),
            "/Fo" + str(obj),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        row = dict(
            source=label(source), command=command, exit=result.returncode, source_sha256=sha(source)
        )
        if result.returncode == 0:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row.update(object_sha256=sha(obj), machine="PowerPC big-endian COFF 0x1f2")
        rows.append(row)
        print(name + ": " + str(result.returncode), flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    build() if parser.parse_args().build else prepare()
