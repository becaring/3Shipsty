"""Run the native game-worker integration contract on the host."""

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
    folder = ROOT / "scratch/frame-worker"
    folder.mkdir(parents=True, exist_ok=True)
    command = [
        str(compiler),
        "/nologo",
        "/std:c++20",
        "/EHsc",
        "/MD",
        "/O2",
        "/I" + str(ROOT / "platform/shipyard"),
        "/I" + str(shared / "sources"),
        str(ROOT / "platform/shipyard/application/frame_worker_contract.cpp"),
        str(shared / "sources/async/native.cpp"),
        "/Fo:" + str(folder) + "/",
        "/Fe:" + str(folder / "contract.exe"),
    ]
    build = subprocess.run(command, env=env, cwd=folder, capture_output=True, text=True)
    (folder / "build.log").write_text(build.stdout + build.stderr, encoding="utf-8")
    assert build.returncode == 0, build.stdout + build.stderr
    result = subprocess.run(
        [str(folder / "contract.exe")],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=20,
    )
    report = dict(
        command=command,
        exit=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    (folder / "verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    assert result.returncode == 0, report
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
