"""Compile GUI replay ownership tests against the selected ImGui core."""

import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))[
        "host_environment"
    ]()
    folder = ROOT / "scratch/gui-frame-cache"
    folder.mkdir(parents=True, exist_ok=True)
    imgui = ROOT / "scratch/imgui-xdk/generated"
    command = [
        str(compiler),
        "/nologo",
        "/std:c++20",
        "/EHsc",
        "/MD",
        "/O2",
        "/I" + str(ROOT / "platform/shipyard"),
        "/I" + str(imgui),
        str(ROOT / "platform/shipyard/application/gui_frame_cache_contract.cpp"),
        *[
            str(imgui / (name + ".cpp"))
            for name in ("imgui", "imgui_draw", "imgui_tables", "imgui_widgets")
        ],
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
