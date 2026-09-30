"""Actual original/projected Logic state methods and table parity, without fake services."""

import hashlib, json, re, runpy, subprocess
from prepare_randomizer_logic import ROOT, OUT, OWN, BASE, prepare, includes, methods
from prepare_archives import stable
from cpp_ast import PARSER, walk

SELECT = [
    "Logic",
    "InventorySlot",
    "CurrentUpgrade",
    "CurrentInventory",
    "SetUpgrade",
    "CheckInventory",
    "SetInventory",
    "CheckEquipment",
    "CheckQuestItem",
    "SetQuestItem",
    "SetSmallKeyCount",
    "CheckDungeonItem",
    "SetDungeonItem",
    "CheckRandoInf",
    "SetRandoInf",
    "CheckEventChkInf",
    "SetEventChkInf",
    "GetGSCount",
    "GetAmmo",
    "SetAmmo",
    "SetSaveContext",
    "Get",
    "Set",
    "DungeonCount",
    "CanBreakCrates",
    "CanBonkTrees",
]
TABLES = ["gBitFlags", "gUpgradeMasks", "gUpgradeNegMasks", "gUpgradeShifts", "gItemSlots"]


def sig(n):
    return n.child_by_field_name("declarator").text.decode()


def method_name(n):
    return sig(n).split("(")[0].split("::")[-1]


def main():
    prepare()
    original = (ROOT / (BASE + "logic.cpp")).read_text()
    projected = (OUT / "generated" / (BASE + "logic.cpp")).read_text()
    originals = {sig(n): n.text.decode() for n in methods(original)}
    projections = {sig(n): n.text.decode() for n in methods(projected)}
    assert set(originals) <= set(projections)
    changed = []
    for name, body in originals.items():
        if body.replace("[[fallthrough]]", "/* fall through */") != projections[name]:
            changed.append(name)
    expected = {
        "Logic::Logic()",
        "Logic::CanDoGlitch(GlitchType glitch)",
        "Logic::ApplyItemEffect(Item& item, bool state)",
        "& GetThievesHideoutSmallKeyDoors()",
        "& GetDungeonSmallKeyDoors(SceneID sceneId)",
        "Logic::GetUsedSmallKeyCount(SceneID sceneId)",
    }
    assert set(changed) == expected, changed
    game = (ROOT / "soh/src/code/z_inventory.c").read_text()
    arrays = []
    for name in TABLES:
        arrays.append(re.search(r"\bu(?:8|32) " + name + r"\[\] = \{[\s\S]*?\};", game)[0])
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected_flag in (False, True):
        folder = OUT / ("host-projected" if projected_flag else "host-original")
        folder.mkdir(exist_ok=True)
        if not projected_flag:
            header = (
                (ROOT / (BASE + "logic.h"))
                .read_text()
                .replace(
                    '#include "SeedContext.h"',
                    '#include <map>\n#include <memory>\n#include "z64save.h"\n#include "z64scene.h"\nnamespace Rando { class Context; class Item; }',
                )
            )
            stable(folder / "logic.h", header)
        source = projected if projected_flag else original
        chosen = [n.text.decode() for n in methods(source) if method_name(n) in SELECT]
        assert len(chosen) == len(SELECT)
        # Preserve real static map constructors and declarations without replacing
        # any table. Upstream and projected table definitions are compiled as-is.
        start = source.index(
            "static std::map" if projected_flag else "std::map<RandomizerGet, uint32_t> Logic::RandoGetToEquipFlag"
        )
        end = source.index("void Logic::ApplyItemEffect")
        maps = source[start:end]
        code = '#include "logic.h"\n#include <cassert>\n#include <cstdio>\n#include <cstring>\n'
        code += 'extern "C" {\n' + "\n".join(arrays) + "\n}\n"
        code += (
            "namespace Rando {\n" + maps + "\n" + "\n".join(chosen) + "\n}\n" + (OWN / "state_contract.cpp").read_text()
        )
        stable(folder / "contract.cpp", code)
        command = (
            [
                str(compiler),
                "/nologo",
                "/std:c++20",
                "/EHsc",
                "/GR",
                "/MD",
                "/Od",
                "/DNOMINMAX",
                "/DF3DEX_GBI_2",
                "/DCONTROLLERBUTTONS_T=uint32_t",
                "/I" + str(folder),
            ]
            + ["/I" + str(p) for p in includes()]
            + [str(folder / "contract.cpp"), "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
        )
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", result.stdout + result.stderr)
        assert not result.returncode, folder / "build.log"
        result = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        row = dict(
            projected=projected_flag,
            command=command,
            exit=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        rows.append(row)
        assert not result.returncode, row
    assert rows[0]["stdout"] == rows[1]["stdout"]
    native = json.loads((OUT / "xdk/build.json").read_text())[0]
    assert not native["exit"]
    assert native["source_sha256"] == hashlib.sha256((ROOT / native["source"]).read_bytes()).hexdigest()
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=rows,
                native=native,
                full_original_functions=len(originals),
                preserved_nonannotation_functions=len(originals) - len(changed),
                changed_functions=changed,
                host_actual_methods=SELECT,
                actual_game_arrays=TABLES,
                external_services_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(rows[0]["stdout"].splitlines()[-1])
    print(str(len(originals)) + " complete original definitions retained; full native Logic TU compiled")


if __name__ == "__main__":
    main()
