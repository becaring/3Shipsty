"""Compare real location state, item tables, and fish helpers from both source trees."""

import hashlib, json, re, runpy, subprocess
from prepare_randomizer_context import ROOT, OUT, OWN, BASE, TABLE, KALEIDO, UNITS, prepare, includes, methods
from prepare_archives import stable
from cpp_ast import PARSER, walk

EXCLUDED = {
    "GetPlacedItem",
    "GetPlacedItemName",
    "SetPlacedItem",
    "GetRandomArea",
    "PlaceVanillaItem",
    "ApplyPlacedItemEffect",
    "GetPrice",
    "SetCheckStatus",
    "SetIsSkipped",
}


def sig(n):
    return n.child_by_field_name("declarator").text.decode()


def method(n):
    return sig(n).split("(")[0].split("::")[-1]


def main():
    prepare()
    coverage = {}
    kh = (OUT / "generated" / (KALEIDO + ".h")).read_text()
    assert len(re.findall(r"virtual void (?:Draw|Update)\([^;]+\) = 0;", kh)) == 2
    original_hash = (ROOT / (BASE + "rando_hash.h")).read_text()
    generated_context = (OUT / "generated" / (BASE + "SeedContext.cpp")).read_text()
    assert re.search(r"gSeedTextures = [\s\S]*?\n\} \};", original_hash)[0] in generated_context
    init = re.search(r"void Context::InitStaticData\(\) \{[\s\S]*?\n\}", generated_context)[0]
    landmarks = ["StaticData::HintTable_Init();", "StaticData::InitLocationTable();"]
    positions = [init.index(mark) for mark in landmarks]
    assert positions == sorted(positions)
    assert all(init.count(mark) == 1 for mark in landmarks)
    for name in UNITS:
        original = (ROOT / name).read_text(encoding="utf-8")
        projected = (OUT / "generated" / name).read_text()
        before = {sig(n): n.text.decode() for n in methods(original)}
        after = {sig(n): n.text.decode() for n in methods(projected)}
        # Generic lambda parameter is the one intentionally concretized signature.
        assert set(before) <= set(after), (name, set(before) - set(after))
        coverage[name] = dict(definitions=len(before), unchanged=sum(after[s] == v for s, v in before.items()))
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected in (False, True):
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        header = (
            (ROOT / "scratch/randomizer-xdk/generated" if projected else ROOT) / (BASE + "item_location.h")
        ).read_text()
        header = header.replace(
            '#include "static_data.h"', "namespace Rando { class Item; }\n#include <set>\n#include <vector>"
        ).replace('#include "option.h"', '#include "OptionValue.h"')
        header = header.replace("class ItemLocation {", "class ItemLocation {\n    friend struct LocationContract;")
        stable(folder / "item_location.h", header)
        fishheader = (
            ((OUT / "generated" if projected else ROOT) / (BASE + "fishsanity.h"))
            .read_text()
            .replace("class Fishsanity {", "class Fishsanity {\n    friend struct FishContract;")
        )
        stable(folder / "fishsanity.h", fishheader)
        text = ((OUT / "generated" if projected else ROOT) / (BASE + "item_location.cpp")).read_text()
        chosen = [n.text.decode() for n in methods(text) if method(n) not in EXCLUDED]
        source = (
            """#include "input/compiler.h"
#include "resources/runtime_support.h"
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include "item_location.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "fishsanity.h"
#include "soh/Enhancements/item-tables/ItemTableManager.h"
namespace Rando {
"""
            + "\n".join(chosen)
            + "\n}\n"
        )
        table = ((OUT / "generated" if projected else ROOT) / (TABLE + ".cpp")).read_text()
        source += "\n".join(n.text.decode() for n in methods(table)) + "\n"
        fish = ((OUT / "generated" if projected else ROOT) / (BASE + "fishsanity.cpp")).read_text()
        first = fish.index("static std::array" if projected else "std::array<std::pair")
        end = fish.index("ActorFunc drawFishing")
        source += fish[first:end]
        first = fish.index("const CheckIdentity Fishsanity::defaultIdentity")
        end = fish.index("Fishsanity::Fishsanity()")
        chosen = [
            n.text.decode() for n in methods(fish) if method(n) in ("Fishsanity", "~Fishsanity", "InitializeHelpers")
        ]
        source += "namespace Rando {\n" + fish[first:end] + "\n" + "\n".join(chosen) + "\n}\n"
        source += (OWN / "state_contract.cpp").read_text()
        stable(folder / "contract.cpp", source)
        option = ROOT / "scratch/randomizer-xdk/generated" / BASE / "OptionValue.cpp"
        command = (
            [
                str(compiler),
                "/nologo",
                "/std:c++20",
                "/utf-8",
                "/EHsc",
                "/GR",
                "/MD",
                "/O2",
                "/DNOMINMAX",
                "/DSHIPYARD_AUDIO_TEST",
                "/DF3DEX_GBI_2",
                "/DCONTROLLERBUTTONS_T=uint32_t",
                "/I" + str(folder),
            ]
            + ["/I" + str(p) for p in includes()]
            + [
                str(folder / "contract.cpp"),
                str(option),
                "/Fo:" + str(folder) + "/",
                "/Fe:" + str(folder / "contract.exe"),
            ]
        )
        r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", r.stdout + r.stderr)
        assert not r.returncode, folder / "build.log"
        r = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        assert not r.returncode, (r.stdout, r.stderr)
        rows.append(dict(projected=projected, command=command, stdout=r.stdout, exit=r.returncode))
    assert rows[0]["stdout"] == rows[1]["stdout"]
    native = json.loads((OUT / "xdk/build.json").read_text())
    for row in native:
        assert row["exit"] == 0
        assert row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
    stable(
        OUT / "verification.json",
        json.dumps(dict(source_coverage=coverage, host=rows, native=native, application_executed=False), indent=2)
        + "\n",
    )
    print(rows[0]["stdout"].strip())
    print("Five complete native units; actual application execution remains unvalidated")


if __name__ == "__main__":
    main()
