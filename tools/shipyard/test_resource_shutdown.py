"""ResourceManager/BS pool and detached-worker ownership and drain checks."""

import hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
import prepare_resource_manager as resource
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/resource-shutdown"
OUT = ROOT / "scratch/resource-shutdown-xdk"


def definitions(source):
    return [
        node.text.decode()
        for node in walk(PARSER.parse(source.encode()).root_node)
        if node.type == "function_definition"
        and node.child_by_field_name("declarator") is not None
        and re.search(
            rb"ResourceManager::(?:ResourceManager|~ResourceManager|WaitForPendingTasks)\(",
            node.child_by_field_name("declarator").text,
        )
    ]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if hasattr(resource, "prepare_lifecycle"):
        resource.prepare_lifecycle()
    header = (resource.OUT / "generated/include/ship/resource/ResourceManager.h").read_text()
    source = (resource.OUT / "generated/src/ship/resource/ResourceManager.cpp").read_text()
    assert "void WaitForPendingTasks();" in header, "Missing resource quiescence boundary"
    lifecycle = definitions(source)
    assert len(lifecycle) == 3
    folder = OUT / "host"
    folder.mkdir(parents=True, exist_ok=True)
    stable(
        folder / "ship/resource/ResourceManager.h",
        header.replace(
            "class ResourceManager {", "class ResourceManager {\n    friend struct ResourceShutdownFixture;"
        ),
    )
    stable(
        folder / "lifecycle.cpp",
        '#include "ship/resource/ResourceManager.h"\n#include <spdlog/spdlog.h>\nnamespace Ship {\n'
        + "\n".join(lifecycle)
        + "\n}\n",
    )
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    recipe = next(
        row
        for row in json.loads((resource.OUT / "xdk/report.json").read_text())
        if row["source"] == "resource/ResourceManager.cpp"
    )
    paths = [Path(arg[2:]) for arg in recipe["command"] if arg.startswith("/I") and "Microsoft Xbox 360 SDK" not in arg]
    paths = [folder, ROOT / "platform/shipyard", PLATFORM_BASE / "sources", resource.OUT / "generated/include"] + paths
    flags = [
        str(compiler),
        "/nologo",
        "/std:c++20",
        "/EHsc",
        "/GR",
        "/MD",
        "/O2",
        "/Gy",
        "/DNOMINMAX",
        "/DSPDLOG_ACTIVE_LEVEL=6",
    ] + ["/I" + str(p) for p in paths]
    records = []

    def build_run(label, units, defines=(), death=False):
        target = folder / label
        target.mkdir(exist_ok=True)
        command = (
            flags
            + list(defines)
            + [str(p) for p in units]
            + ["/Fo:" + str(target) + "/", "/Fe:" + str(target / "contract.exe"), "/link", "/OPT:REF"]
        )
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(target / "build.log", run.stdout + run.stderr)
        assert not run.returncode, target / "build.log"
        run = subprocess.run([str(target / "contract.exe")], cwd=ROOT, capture_output=True, text=True, timeout=45)
        row = dict(label=label, command=command, exit=run.returncode, stdout=run.stdout, stderr=run.stderr)
        if death:
            died = subprocess.run(
                [str(target / "contract.exe"), "--throws"], cwd=ROOT, capture_output=True, text=True, timeout=15
            )
            row["uncaught_exit"] = died.returncode
            assert died.returncode == 73, row
        stable(target / "run.json", json.dumps(row, indent=2) + "\n")
        assert not run.returncode, row
        records.append(row)
        print(run.stdout, flush=True)

    native = PLATFORM_BASE / "sources/async/native.cpp"
    detached = PLATFORM_BASE / "sources/async/detached.cpp"
    stable(
        folder / "creation_failure.h",
        """extern HANDLE WINAPI ContractCreateThread(LPSECURITY_ATTRIBUTES,SIZE_T,LPTHREAD_START_ROUTINE,LPVOID,DWORD,LPDWORD);
#define CreateThread ContractCreateThread
""",
    )
    original = detached.read_text()
    namespace = r"namespace Shipyard\s*\{\s*namespace Async\s*\{"
    assert len(re.findall(namespace, original)) == 1
    stable(
        folder / "injected_detached.cpp",
        re.sub(
            namespace,
            lambda match: '#include "creation_failure.h"\n' + match.group(),
            original,
        ),
    )
    build_run("detached-drain", [OWN / "detached_contract.cpp", folder / "injected_detached.cpp", native], death=True)
    build_run("resource-drain", [OWN / "resource_contract.cpp", folder / "lifecycle.cpp", native])
    build_run(
        "detached-regression", [ROOT / "platform/shipyard/async/detached_contract.cpp", detached, native], death=True
    )
    build_run(
        "detached-original",
        [ROOT / "platform/shipyard/async/detached_contract.cpp"],
        defines=["/DTEST_UPSTREAM"],
        death=True,
    )
    assert records[-1]["stdout"] == records[-2]["stdout"]
    target = OUT / "xdk"
    target.mkdir(exist_ok=True)
    native_rows = []
    command = recipe["command"][:-2] + ["/I" + str(PLATFORM_BASE / "sources")]
    for unit, label in [
        (resource.OUT / "generated/src/ship/resource/ResourceManager.cpp", "ResourceManager"),
        (detached, "detached"),
    ]:
        obj = target / (label + ".obj")
        call = command + [str(unit), "/Fo" + str(obj)]
        run = subprocess.run(call, cwd=ROOT, capture_output=True, text=True)
        stable(target / (label + ".log"), run.stdout + run.stderr)
        row = dict(
            source=unit.relative_to(PLATFORM_BASE if unit.is_relative_to(PLATFORM_BASE) else ROOT).as_posix(),
            command=call,
            exit=run.returncode,
            source_sha256=sha(unit),
        )
        native_rows.append(row)
        assert not run.returncode, target / (label + ".log")
        assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
        row["object_sha256"] = sha(obj)
    stable(target / "build.json", json.dumps(native_rows, indent=2) + "\n")
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=records,
                native=native_rows,
                owned={
                    str(p.relative_to(PLATFORM_BASE if p.is_relative_to(PLATFORM_BASE) else ROOT)): sha(p)
                    for p in [
                        Path(__file__),
                        detached,
                        detached.with_suffix(".h"),
                        OWN / "resource_contract.cpp",
                        OWN / "detached_contract.cpp",
                        ROOT / "tools/shipyard/prepare_resource_manager.py",
                    ]
                },
                target_runtime_executed=False,
                full_context_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print("ResourceManager full TU and tracked detached implementation compile for native PPC.")


if __name__ == "__main__":
    main()
