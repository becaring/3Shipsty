"""Exercise the actual runtime loop with the native channel and controlled I/O."""

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
    folder = ROOT / "scratch/overlap-runtime-host"
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
        "/I" + str(shared / "sources"),
        "/I" + str(imgui),
        str(ROOT / "platform/shipyard/application/overlap_runtime_contract.cpp"),
        str(shared / "sources/async/native.cpp"),
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
    cases = []
    for mode in (
        "interactive",
        "drop",
        "shutdown",
        "shutdown-drop",
        "off",
        "hotplug",
        "single",
        "sync",
        "restore",
        "remote-cc",
        "remote-anchor",
        "remote-sail",
    ):
        result = subprocess.run(
            [str(folder / "contract.exe"), mode],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=20,
        )
        cases.append(
            dict(
                mode=mode,
                exit=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
        assert result.returncode == 0, cases[-1]
    report = dict(command=command, cases=cases)
    (folder / "verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Actual runtime: 12 replay/drop/stop/hotplug/sync/restore/network cases passed; "
        + cases[0]["stdout"].strip()
    )


if __name__ == "__main__":
    main()
