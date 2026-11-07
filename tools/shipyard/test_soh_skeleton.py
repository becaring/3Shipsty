"""Bounded skeleton methods; player and Context patching stays a runtime gate."""

import json
import runpy
import subprocess
from prepare_soh_resources import ROOT, OUT, OWN, prepare, includes
from prepare_archives import stable
from cpp_ast import PARSER, walk


def main():
    prepare()
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected in (False, True):
        folder = OUT / ("skeleton-projected" if projected else "skeleton-original")
        folder.mkdir(exist_ok=True)
        base = OUT / "generated" if projected else ROOT
        text = (base / "soh/soh/resource/type/Skeleton.cpp").read_text()
        methods = [
            n.text.decode()
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "function_definition"
            and any(
                s in n.child_by_field_name("declarator").text.decode()
                for s in (
                    "Skeleton::GetPointer",
                    "SkeletonPatcher::UnregisterSkeleton",
                    "SkeletonPatcher::ClearSkeletons",
                )
            )
        ]
        assert len(methods) == 4
        audit = (
            '#include "soh/resource/type/Skeleton.h"\nnamespace SOH {\nstd::vector<SkeletonPatchInfo> SkeletonPatcher::skeletons;\n'
            + "\n".join(methods)
            + "\n}\n"
            + (OWN / "skeleton_contract.cpp").read_text()
        )
        stable(folder / "audit.cpp", audit)
        resources = ROOT / "scratch/resources-xdk/generated" if projected else ROOT / "libultraship"
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
        ] + ["/I" + str(p) for p in includes(projected)]
        command += [
            str(folder / "audit.cpp"),
            str(resources / "src/ship/resource/Resource.cpp"),
            "/Fo:" + str(folder) + "/",
            "/Fe:" + str(folder / "audit.exe"),
        ]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(folder / "build.log")
        result = subprocess.run([str(folder / "audit.exe")], cwd=ROOT, capture_output=True, text=True)
        row = dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        rows.append(row)
        stable(folder / "run.json", json.dumps(row, indent=2) + "\n")
        assert result.returncode == 0, row
    assert rows[0]["stdout"] == rows[1]["stdout"]
    stable(
        OUT / "skeleton-verification.json",
        json.dumps(dict(cases=rows, actual_service_patching_executed=False, target_runtime_executed=False), indent=2)
        + "\n",
    )
    print(rows[0]["stdout"])


if __name__ == "__main__":
    main()
