"""Original/projected dungeon JSON, key counts, trial state, and pool contracts."""

import hashlib, json, re, runpy, subprocess
from prepare_randomizer_dungeons import ROOT, OUT, OWN, BASE, prepare, includes, methods
from prepare_archives import stable
from cpp_ast import PARSER, walk
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
EXCLUDE = {
    "DungeonInfo::PlaceVanillaMap",
    "DungeonInfo::PlaceVanillaCompass",
    "DungeonInfo::PlaceVanillaBossKey",
    "DungeonInfo::PlaceVanillaSmallKeys",
    "TrialInfo::GetName",
    "Trials::ParseJson",
}


def sig(n):
    return n.child_by_field_name("declarator").text.decode()


def name(n):
    return sig(n).split("(")[0]


def main():
    prepare()
    data = (ROOT / (BASE + "static_data.cpp")).read_text()
    trialdata = re.search(
        r"std::unordered_map<uint32_t, RandomizerHintTextKey> StaticData::trialData = \{[\s\S]*?\};", data
    )[0]
    originals = {}
    projected = {}
    counts = {}
    for kind in ("dungeon", "trial"):
        originals[kind] = (ROOT / (BASE + kind + ".cpp")).read_text()
        projected[kind] = (OUT / "generated" / (BASE + kind + ".cpp")).read_text()
        assert [sig(n) for n in methods(originals[kind])] == [sig(n) for n in methods(projected[kind])]
        counts[kind] = len(methods(originals[kind]))
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected_flag in (False, True):
        folder = OUT / ("host-projected" if projected_flag else "host-original")
        folder.mkdir(exist_ok=True)
        for kind, base in [
            ("dungeon", ROOT / "scratch/randomizer-logic-xdk/generated"),
            ("trial", ROOT / "scratch/randomizer-xdk/generated"),
        ]:
            header = ((base if projected_flag else ROOT) / (BASE + kind + ".h")).read_text()
            header = header.replace(
                '#include "../custom-message/CustomMessageManager.h"',
                '#include "soh/Enhancements/custom-message/CustomMessageManager.h"',
            )
            header = header.replace('#include "static_data.h"', "")
            header = header.replace(
                "class DungeonInfo {", "class DungeonInfo {\n    friend struct DungeonContract;"
            ).replace("class TrialInfo {", "class TrialInfo {\n    friend struct DungeonContract;")
            stable(folder / (kind + ".h"), header)
        pool = (
            (OUT / "generated/include/randomizer-dungeons/pool_filter.h").read_text()
            if projected_flag
            else (ROOT / (BASE + "3drando/pool_functions.hpp")).read_text()
        )
        stable(folder / "pool.h", pool)
        selected = []
        for kind in ("dungeon", "trial"):
            selected += [
                n.text.decode()
                for n in methods(projected[kind] if projected_flag else originals[kind])
                if name(n) not in EXCLUDE
            ]
        source = (
            """#include "dungeon.h"
#include "trial.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "z64scene.h"
#include "resources/runtime_support.h"
#include <algorithm>
#include "pool.h"
namespace Rando {
"""
            + trialdata
            + "\n"
            + "\n".join(selected)
            + "\n}\n"
            + (OWN / "state_contract.cpp").read_text()
        )
        if projected_flag:
            source = '#include "randomizer-dungeons/host_json_iterator_traits.h"\n' + source
        stable(folder / "contract.cpp", source)
        command = [
            str(compiler),
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/GR",
            "/MD",
            "/O2",
            "/Gy",
            "/DNOMINMAX",
            "/DSHIPYARD_AUDIO_TEST",
            "/DF3DEX_GBI_2",
            "/DCONTROLLERBUTTONS_T=uint32_t",
            "/I" + str(folder),
        ]
        if not projected_flag:
            command += ["/Zc:preprocessor", "/I" + str(ROOT / "platform/shipyard/json/upstream/include")]
        command += ["/I" + str(p) for p in includes()] + [str(folder / "contract.cpp")]
        if projected_flag:
            command += [str(PLATFORM_BASE / "sources/json/json.cpp")]
        command += ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe"), "/link", "/OPT:REF"]
        r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", r.stdout + r.stderr)
        assert not r.returncode, folder / "build.log"
        r = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        row = dict(projected=projected_flag, command=command, exit=r.returncode, stdout=r.stdout, stderr=r.stderr)
        rows.append(row)
        assert not r.returncode, row
    assert rows[0]["stdout"] == rows[1]["stdout"]
    native = json.loads((OUT / "xdk/build.json").read_text())
    for row in native:
        assert (
            not row["exit"] and row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
        )
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=rows,
                native=native,
                original_definitions=counts,
                host_methods=len(selected),
                not_host_executed=sorted(EXCLUDE),
                actual_trial_data=True,
                native_execution=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(rows[0]["stdout"].splitlines()[-1])
    print("Complete dungeon/trial definitions retained: " + json.dumps(counts))


if __name__ == "__main__":
    main()
