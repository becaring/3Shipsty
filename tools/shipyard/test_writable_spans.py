"""Compile and run the writable-span lifetime contract against the frame channel."""

import json
from pathlib import Path
import runpy
import subprocess
from platform_base import resolve

ROOT = Path(__file__).resolve().parents[2]


def main():
    shared = resolve(ROOT)
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))[
        "host_environment"
    ]()
    folder = ROOT / "scratch/writable-spans"
    folder.mkdir(parents=True, exist_ok=True)
    command = [
        str(compiler),
        "/nologo",
        "/std:c++14",
        "/EHsc",
        "/MD",
        "/O2",
        "/W4",
        "/WX",
        "/I" + str(ROOT / "platform/shipyard"),
        "/I" + str(shared / "sources"),
        str(ROOT / "platform/shipyard/application/writable_spans_contract.cpp"),
        str(shared / "sources/async/native.cpp"),
        "/Fo:" + str(folder) + "/",
        "/Fe:" + str(folder / "contract.exe"),
    ]
    build = subprocess.run(command, env=env, cwd=folder, capture_output=True, text=True)
    (folder / "build.log").write_bytes((build.stdout + build.stderr).encode())
    assert build.returncode == 0, build.stdout + build.stderr
    result = subprocess.run(
        [str(folder / "contract.exe")],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=10,
    )
    report = dict(
        command=command,
        exit=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    (folder / "verification.json").write_bytes(
        (json.dumps(report, indent=2) + "\n").encode()
    )
    assert result.returncode == 0, report
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
