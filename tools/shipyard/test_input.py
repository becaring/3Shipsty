"""Host differential for the retained input math and defaults, plus physical contract fixtures.
The host fixture supplies the physical bytes, so native controller I/O is not tested.
"""

import json, runpy, subprocess
from pathlib import Path
from prepare_input import ROOT, OUT, OWN, prepare
from platform_base import resolve as resolve_platform_base
from cpp_ast import PARSER, walk


def host(projected):
    environment = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_resources.py"))
    compiler, env = environment["ENV"].host_environment()
    folder = OUT / ("host-projected" if projected else "host-original")
    folder.mkdir(parents=True, exist_ok=True)
    source = OUT / "generated" if projected else ROOT / "libultraship"
    if not projected:
        # Only replace the physical API include; original declarations and
        # method bodies remain modern C++ for differential syntax validation.
        for name in json.loads((OWN / "sources.lock.json").read_text())["sources"]:
            if name.startswith("include/"):
                text = (
                    (source / name)
                    .read_text(encoding="utf-8-sig")
                    .replace("#include <SDL2/SDL.h>", '#include "input/sdl_bridge.h"')
                )
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
    selected = {
        "ControllerStick::" + name
        for name in [
            "ControllerStick",
            "~ControllerStick",
            "GetClosestNotch",
            "GetAxisDirectionValue",
            "Process",
            "UpdatePad",
            "AddAxisDirectionMapping",
            "HasMappingsForPhysicalDeviceType",
        ]
    }
    text = (source / "src/ship/controller/controldevice/controller/ControllerStick.cpp").read_bytes()
    funcs = [
        n
        for n in walk(PARSER.parse(text).root_node)
        if n.type == "function_definition"
        and n.child_by_field_name("declarator").text.decode().split("(")[0].strip() in selected
    ]
    if len(funcs) != len(selected):
        raise ValueError("Stick audit method selector drift")
    audit = folder / "stick-method-audit.cpp"
    audit.write_text(
        """#include "input/compiler.h"
#include <algorithm>
#include "ship/controller/controldevice/controller/ControllerStick.h"
#define M_PI 3.14159265358979323846
#define M_TAU 2 * M_PI
#define MINIMUM_RADIUS_TO_MAP_NOTCH 0.9
namespace Ship {
"""
        + "\n".join(n.text.decode() for n in funcs)
        + "\n}"
    )
    paths = [
        "src/ship/controller/controldevice/controller/mapping/" + name + ".cpp"
        for name in [
            "ControllerAxisDirectionMapping",
            "ControllerInputMapping",
            "ControllerMapping",
            "ControllerDefaultMappings",
        ]
    ]
    paths += ["src/libultraship/controller/controldevice/controller/mapping/ControllerDefaultMappings.cpp"]
    platform_base = resolve_platform_base(ROOT)
    inc = [
        source / "include" if projected else folder / "include",
        ROOT / "platform/shipyard",
        ROOT / "libultraship/include",
        platform_base / "sources",
    ]
    command = [str(compiler), "/nologo", "/std:c++20", "/utf-8", "/EHsc", "/MD", "/DCONTROLLERBUTTONS_T=uint32_t"] + [
        "/I" + str(p) for p in inc
    ]
    # Distinct object names avoid Ship/LUS ControllerDefaultMappings collision.
    objects = []
    for i, p in enumerate(
        [source / n for n in paths] + [audit, platform_base / "sources/input/physical.cpp", OWN / "contract.cpp"]
    ):
        obj = folder / (str(i) + ".obj")
        cmd = command + ["/c", str(p), "/Fo" + str(obj)]
        result = subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True)
        (folder / (str(i) + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Host compile failed: " + str(folder / (str(i) + ".log")))
        objects.append(obj)
    result = subprocess.run(
        [str(compiler), "/nologo"] + [str(p) for p in objects] + ["/Fe" + str(folder / "contract.exe")],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (folder / "link.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Host link failed: " + str(folder / "link.log"))
    result = subprocess.run([str(folder / "contract.exe")], cwd=folder, capture_output=True, text=True)
    (folder / "verification.json").write_text(
        json.dumps(
            dict(
                exit=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=command,
                scope="Actual defaults, eight stick methods, physical byte fixture; no Context/runtime integration",
                target_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n"
    )
    if result.returncode:
        raise RuntimeError("Host fixture failed: " + str(folder / "verification.json"))
    return result.stdout


if __name__ == "__main__":
    prepare()
    a = host(False)
    b = host(True)
    if a != b:
        raise RuntimeError("Original/projected differential mismatch")
    print(a)
    print("Original and projected defaults + 40,401 stick vectors agree; physical fixture passes.")
