"""Seed-generation source inventories and bounded algorithm contracts."""

import collections, hashlib, json, re, runpy, struct, subprocess
from prepare_randomizer_generation import *
from test_randomizer_regions import tokens
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)


def methods(text):
    return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type == "function_definition"]


def sig(n):
    return next(d.text.decode() for d in walk(n.child_by_field_name("declarator")) if d.type == "function_declarator")


def fname(n):
    return sig(n).split("(")[0].split("::")[-1]


SELECT = {
    "fill": {"GetShopItemBaseName"},
    "hints": {
        "HintDistributionSetting",
        "StaticHintInfo",
        "NoFilter",
        "getRandomWeight",
        "DistributeHints",
        "GetRandomJunkHint",
        "GetRandomGanonJoke",
    },
    "shops": {"PriceSettingsStruct", "GetMinVanillaShopItems", "GetCheapBalancedPrice"},
    "item_pool": {"ReplaceMaxItem"},
    "spoiler_log": {"RemoveLineBreaks"},
    "starting_inventory": {"AddItemToInventory"},
}
RNG = {"Random", "RandomDouble", "RandomElement", "Random_Init", "next32", "rand", "srand", "Shuffle", "SohUtils::Hash"}


def inventory_check(manifest):
    rows = {}
    total = 0
    for name in NAMES:
        orig = (ROOT / (DIR + name + ".cpp")).read_text()
        proj = (OUT / "generated" / (DIR + name + ".cpp")).read_text()

        def inventory(t):
            result = collections.defaultdict(list)
            for n in methods(t):
                result[fname(n)].append(n)
            return result

        a = inventory(orig)
        b = inventory(proj)
        for key, defs in a.items():
            assert key in b and len(defs) == len(b[key]), (name, key)

        def calls(n):
            return [
                c.text.decode().replace("std::to_string(", "Shipyard::Generation::Decimal(")
                for c in walk(n)
                if c.type == "call_expression" and c.child_by_field_name("function").text.decode() in RNG
            ]

        for key, defs in a.items():
            for first, second in zip(defs, b[key]):
                assert calls(first) == calls(second), (name, key, "RNG order")
        rows[name] = dict(
            original_functions=sum(len(v) for v in a.values()), rng_calls=sum(len(calls(n)) for n in methods(orig))
        )
        total += rows[name]["original_functions"]
    assert total == 157, total
    original = (ROOT / (DIR + "hints.hpp")).read_text()
    projected = (OUT / "generated" / (DIR + "hints.hpp")).read_text()
    for name in ("HintDistributionSetting", "HintSetting"):

        def get(t):
            return next(
                n.text.decode()
                for n in walk(PARSER.parse(t.encode()).root_node)
                if n.type == "struct_specifier" and n.child_by_field_name("name").text.decode() == name
            )

        assert tokens(get(original)) == tokens(get(projected))
    for name in ("CheapPriceProbability", "ShopPriceProbability"):
        values = []
        for root in (ROOT, OUT / "generated"):
            t = (root / (DIR + "shops.cpp")).read_text()
            n = next(
                n
                for n in walk(PARSER.parse(t.encode()).root_node)
                if n.type == "init_declarator" and n.child_by_field_name("declarator").text.decode() == name
            )
            values.append(tokens(n.child_by_field_name("value").text.decode()))
        assert values[0] == values[1]
    original = (ROOT / (DIR + "hints.cpp")).read_text()
    projected = (OUT / "generated" / (DIR + "hints.cpp")).read_text()

    def table(text):
        return next(
            n
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "init_declarator" and n.child_by_field_name("declarator").text == b"hintSettingTable"
        ).child_by_field_name("value")

    origrows = kids(kids(table(original))[0])
    projrows = kids(kids(table(projected))[0])
    assert len(origrows) == len(projrows) == 4
    helpers = {fname(n): n for n in methods(projected)}

    # Keep all twelve predicates, including their ordering and check IDs.
    # The old XDK silently omitted most nontrivial aggregate initializers; the
    # generated callback table must instead use explicitly constructed elements.
    def conditional(text):
        return next(
            n
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "init_declarator" and n.child_by_field_name("declarator").text == b"conditionalAlwaysHints"
        ).child_by_field_name("value")

    source_callbacks = kids(conditional(original))
    callback_helper = helpers[conditional(projected).child_by_field_name("function").text.decode()]
    actual_callbacks = [
        n
        for n in walk(callback_helper)
        if n.type == "call_expression" and n.child_by_field_name("function").text == b"std::make_pair"
    ]
    assert len(source_callbacks) == len(actual_callbacks) == 12
    assert callback_helper.text.count(b"result.push_back(") == 12
    for a, b in zip(source_callbacks, actual_callbacks):
        # Only the XDK-required explicit lambda return type differs.
        assert tokens(a.text.decode()) == tokens(b.text.decode().replace(" -> bool ", ""))
    for old, new in zip(origrows, projrows):
        fields = [n.child_by_field_name("value") for n in kids(old)]
        values = kids(new)
        assert [tokens(n.text.decode()) for n in fields[:3]] == [tokens(n.text.decode()) for n in values[:3]]
        olddist = kids(fields[3])
        call = values[3]
        if not olddist:
            assert call.text == b"std::vector<HintDistributionSetting>()"
            continue
        helper = helpers[call.child_by_field_name("function").text.decode()]
        array = next(
            n.child_by_field_name("value")
            for n in walk(helper)
            if n.type == "init_declarator" and n.child_by_field_name("declarator").text == b"values[]"
        )
        newdist = kids(array)
        assert len(olddist) == len(newdist)
        for a, b in zip(olddist, newdist):
            actual = kids(b.child_by_field_name("arguments"))
            assert len(kids(a)) == len(actual)
            for x, y in zip(kids(a), actual):
                assert tokens(lower_literals(x.text.decode())[0]) == tokens(lower_literals(y.text.decode())[0])
    return dict(units=rows, original_functions=total)


def source_for_host(projected, folder):
    if not projected:
        h = (ROOT / (DIR + "hints.hpp")).read_text()
        cls = next(
            n.text.decode()
            for n in walk(PARSER.parse(h.encode()).root_node)
            if n.type == "struct_specifier" and n.child_by_field_name("name").text == b"StaticHintInfo"
        )
        stable(
            folder / "soh/Enhancements/randomizer/3drando/StaticHintInfo.h",
            '#pragma once\n#include <variant>\n#include <vector>\n#include "soh/Enhancements/randomizer/randomizerTypes.h"\n'
            + cls
            + ";\n",
        )
        stable(
            folder / "soh/Enhancements/randomizer/3drando/fill.hpp",
            normalize_includes((ROOT / (DIR + "fill.hpp")).read_text()),
        )
    code = (
        PREFIX
        + """
#include <cassert>
#include <cstdio>
#include <cstring>
#include <nlohmann/json.hpp>
#include "soh/Enhancements/randomizer/3drando/hints.hpp"
#include "soh/Enhancements/randomizer/3drando/fill.hpp"
#include "soh/Enhancements/randomizer/3drando/shops.hpp"
#include "soh/Enhancements/randomizer/3drando/pool_functions.hpp"
"""
    )
    code += "uint32_t next32();\nstd::vector<RandomizerGet> itemPool;\nstd::vector<RandomizerGet> StartingInventory;\n"
    for name, selected in SELECT.items():
        t = ((OUT / "generated" if projected else ROOT) / (DIR + name + ".cpp")).read_text()
        chosen = [n.text.decode() for n in methods(t) if fname(n) in selected]
        assert len(chosen) == len(selected), (name, len(chosen))
        if name == "shops":
            decl = next(
                n
                for n in walk(PARSER.parse(t.encode()).root_node)
                if n.type == "declaration" and b"CheapPriceProbability =" in n.text[:100]
            )
            code += decl.text.decode() + "\n"
        code += "\n".join(chosen) + "\n"
    custom = ((OUT / "generated" if projected else ROOT) / (DIR + "custom_messages.cpp")).read_text()
    code += (
        "namespace CustomMessages {\nusing namespace std::literals::string_literals;\n"
        + "\n".join(n.text.decode() for n in methods(custom))
        + "\n}\n"
    )
    entrance = (ROOT / ("scratch/save-manager-xdk/generated/" + BASE + "entrance.cpp")).read_text()
    code += (
        "namespace Rando {\n"
        + "\n".join(
            n.text.decode()
            for n in methods(entrance)
            if fname(n) in ("Entrance", "GetType", "SetType", "GetReverse", "BindTwoWay")
        )
        + "\n}\n"
    )
    spoiler = ((OUT / "generated" if projected else ROOT) / (DIR + "spoiler_log.cpp")).read_text()
    statements = [
        n.text.decode()
        for n in walk(PARSER.parse(spoiler.encode()).root_node)
        if n.type == "declaration"
        and (n.text.startswith(b"json entranceJson =") or n.text.startswith(b"json reverseEntranceJson ="))
    ]
    assert len(statements) == 2
    if not projected:
        statements = [
            s.replace("entrance->GetType()", "entrance->GetType().GetValue()").replace(
                "entrance->GetReverse()->GetType()", "entrance->GetReverse()->GetType().GetValue()"
            )
            for s in statements
        ]
    code += (
        """typedef nlohmann::ordered_json json;
json EntranceJSON(Rando::Entrance* entrance,int16_t originalIndex,int16_t destinationIndex,int16_t \
replacementIndex,int16_t replacementDestinationIndex) {
"""
        + "\n".join(statements)
        + "\njson result=json::array();result.push_back(entranceJson);result.push_back(reverseEntranceJson);return result;}\n"
    )
    code += "#define HINT_GET " + ("xbox_compat::get" if projected else "std::get") + "\n"
    return code + (OWN / "contract.cpp").read_text()


def host(projected):
    folder = OUT / ("host-projected" if projected else "host-original")
    folder.mkdir(exist_ok=True)
    stable(folder / "contract.cpp", source_for_host(projected, folder))
    rng = (ROOT / "scratch/ship-utils-xdk/generated/soh/soh/ShipUtils.cpp").read_text()
    rng = rng[rng.index("static bool default_init = false;") :]
    stable(folder / "rng.cpp", '#include "soh/ShipUtils.h"\n#include <cassert>\n#include <cmath>\n' + rng)
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    jsonroots = (
        [PLATFORM_BASE / "sources/json/include", ROOT / "scratch/json-xdk/backend-generated"]
        if projected
        else [ROOT / "platform/shipyard/json/upstream/include"]
    )
    roots = [folder] + jsonroots + includes()
    command = [
        str(compiler),
        "/nologo",
        "/std:c++20",
        "/Zc:preprocessor",
        "/utf-8",
        "/EHsc",
        "/GR",
        "/MD",
        "/O2",
        "/DNOMINMAX",
        "/DSHIPYARD_AUDIO_TEST",
        "/DF3DEX_GBI_2",
        "/DCONTROLLERBUTTONS_T=uint32_t",
    ] + ["/I" + str(p) for p in roots]
    command += [
        str(folder / "contract.cpp"),
        str(folder / "rng.cpp"),
        str(ROOT / ("scratch/ship-utils-xdk/generated/" + DIR + "random.cpp")),
        str(ROOT / "platform/shipyard/ship-utils/native_entropy.cpp"),
    ]
    if projected:
        command.append(str(PLATFORM_BASE / "sources/json/json.cpp"))
    command += ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
    r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    stable(folder / "build.log", r.stdout + r.stderr)
    assert not r.returncode, folder / "build.log"
    r = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
    assert not r.returncode, (r.returncode, r.stdout, r.stderr)
    return dict(projected=projected, command=command, exit=r.returncode, stdout=r.stdout)


def native_symbols(path):
    raw = path.read_bytes()
    _, _, _, offset, count, _, _ = struct.unpack_from("<HHIIIHH", raw)
    strings = offset + count * 18
    index = 0
    result = {}
    while index < count:
        start = offset + index * 18
        if raw[start : start + 4] == b"\0" * 4:
            first = strings + struct.unpack_from("<I", raw, start + 4)[0]
            name = raw[first : raw.index(b"\0", first)].decode()
        else:
            name = raw[start : start + 8].rstrip(b"\0").decode()
        value, section, _, storage, aux = struct.unpack_from("<IhHBB", raw, start + 8)
        if storage == 2 and section > 0:
            data = struct.unpack_from("<I", raw, 20 + (section - 1) * 40 + 20)[0]
            result[name] = (raw, data + value)
        index += aux + 1
    return result


def main():
    prepare()
    manifest = json.loads((OUT / "manifest.json").read_text())
    report = inventory_check(manifest)
    rows = [host(False), host(True)]
    assert rows[0]["stdout"] == rows[1]["stdout"], rows
    native = json.loads((OUT / "xdk/build.json").read_text())
    assert len(native) == 11 and sum(row["production"] for row in native) == 10
    for row in native:
        assert row["exit"] == 0, row["source"]
        assert row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
        obj = Path(next(s[3:] for s in row["command"] if s.startswith("/Fo")))
        assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
        assert row["object_sha256"] == hashlib.sha256(obj.read_bytes()).hexdigest()
        assert "/GR" in row["command"]
    raw, position = native_symbols(OUT / "xdk/declarations.obj")["GenerationABI"]
    abi = struct.unpack_from(">4I", raw, position)
    assert abi == (116, 72, 20, 88), abi
    names = native_symbols(OUT / "xdk/hints.obj")
    assert any(n.startswith("??0StaticHintInfo@@") for n in names)
    assert any(n.startswith("??0HintText@@") for n in names)
    report.update(
        host=rows,
        native=native,
        native_abi=dict(
            zip(("GetAccessibleLocationsStruct", "HintDistributionSetting", "HintSetting", "StaticHintInfo"), abi)
        ),
        external_services_executed=False,
    )
    stable(OUT / "verification.json", json.dumps(report, indent=2) + "\n")
    print(rows[0]["stdout"])
    print("All 157 definitions and original RNG call order retained; 10 full native units verified")


if __name__ == "__main__":
    main()
