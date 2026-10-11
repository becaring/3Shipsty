"""Run selected generated CVar getters/setters against a frozen replay snapshot."""

import json
from pathlib import Path
import runpy
import subprocess
from platform_base import resolve
from prepare_console_variables import transform

ROOT = Path(__file__).resolve().parents[2]


def main():
    shared = resolve(ROOT)
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))[
        "host_environment"
    ]()
    folder = ROOT / "scratch/cvar-snapshot"
    folder.mkdir(parents=True, exist_ok=True)
    header = transform(
        "include/ship/config/ConsoleVariable.h",
        (ROOT / "libultraship/include/ship/config/ConsoleVariable.h").read_text(),
    )
    # Config persistence is outside this getter/ownership contract.
    header = header.replace("#include <nlohmann/json.hpp>\n", "")
    # Exercise reload/removal without bringing config persistence into this fixture.
    header = header.replace("  private:", "  public:")
    header = header.replace(
        "    void LoadFromPath(std::string path,\n"
        "                      nlohmann::detail::iteration_proxy<nlohmann::detail::iter_impl<nlohmann::json>> items);\n",
        "",
    )
    (folder / "cvar_snapshot_fixture.h").write_text(header)
    source = transform(
        "src/ship/config/ConsoleVariable.cpp",
        (ROOT / "libultraship/src/ship/config/ConsoleVariable.cpp").read_text(),
    )
    source = source[
        source.index("namespace Ship {") : source.index(
            "void ConsoleVariable::RegisterInteger"
        )
    ]
    source = source.replace("    Load();", "")
    source = source.replace('    SPDLOG_TRACE("destruct console variables");', "")
    source = (
        '#include "cvar_snapshot_fixture.h"\n#define strdup _strdup\n'
        + source
        + "\n}\n"
    )
    (folder / "cvar_snapshot_fixture.cpp").write_text(source)
    command = [
        str(compiler),
        "/nologo",
        "/std:c++20",
        "/EHsc",
        "/MD",
        "/O2",
        "/I" + str(folder),
        "/I" + str(shared / "sources"),
        "/I" + str(ROOT / "libultraship/include"),
        str(folder / "cvar_snapshot_fixture.cpp"),
        str(ROOT / "platform/shipyard/application/cvar_snapshot_contract.cpp"),
        "/Fo:" + str(folder) + "/",
        "/Fe:" + str(folder / "contract.exe"),
    ]
    build = subprocess.run(command, env=env, cwd=folder, capture_output=True, text=True)
    (folder / "build.log").write_text(build.stdout + build.stderr)
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
    (folder / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    assert result.returncode == 0, report
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
