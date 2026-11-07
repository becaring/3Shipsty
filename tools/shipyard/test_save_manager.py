"""Full SaveManager ownership/schema audit and nontrivial JSON load contracts."""

import hashlib, json, re, runpy, struct, subprocess
from prepare_save_manager import ROOT, OUT, OWN, prepare, methods, load_defaults, prepared_load
from prepare_save_storage import METHODS
from prepare_application import function
from prepare_archives import stable
from cpp_ast import walk, PARSER


def main():
    prepare()
    original = (ROOT / "soh/soh/SaveManager.cpp").read_text(encoding="utf-8")
    base = (ROOT / "scratch/save-storage-xdk/generated/soh/soh/SaveManager.cpp").read_text(encoding="utf-8")
    projected = (OUT / "generated/soh/soh/SaveManager.cpp").read_text(encoding="utf-8")
    originals = methods(original)
    actual = methods(projected)
    canonical = methods(base)
    assert len(actual) == 42 and set(actual) == set(originals)
    prepared_canonical = methods(prepared_load(base))
    for name in METHODS + ["SaveRandomizer", "InitMeta"]:
        expected_method = (
            prepared_canonical[name] if name in ("LoadFile", "StartupCheckAndInitMeta") else canonical[name]
        )
        assert actual[name] == expected_method, name
    assert function(projected, "Save_LoadFile").text == function(base, "Save_LoadFile").text
    bridges = lambda text: [
        re.search(rb"\b(Save_\w+)\(", n.text)[1]
        for n in walk(PARSER.parse(text.encode()).root_node)
        if n.type == "linkage_specification"
        and n.text.startswith(b'extern "C"')
        and re.search(rb"\bSave_\w+\(", n.text)
    ]
    original_bridges = bridges(original)
    projected_bridges = bridges(projected)
    assert len(original_bridges) == 12
    assert projected_bridges.count(b"Save_PrepareLoadFile") == 1
    assert original_bridges == [b for b in projected_bridges if b != b"Save_PrepareLoadFile"]
    load = function(projected, "SaveManager::LoadFile").text.decode()
    assert load.index("ShipyardFinishPreparedSave();") < load.index("saveMtx.lock();")
    assert "input >> saveBlock" not in projected
    assert "input >> metaSaveBlock" not in projected
    assert "sShipyardPreparedSave.text == text" in projected
    assert "nlohmann::json::parse(saveText.begin(), saveText.end())" in load
    worker = function(projected, "ShipyardPrepareSave").text.decode()
    assert worker.index("ThreadPoolWait();") < worker.index("std::ifstream input(")
    assert "Shipyard::Async::ServiceProcessor" in function(projected, "Save_PrepareLoadFile").text.decode()

    def keys(text):
        result = []
        for n in walk(PARSER.parse(text.encode()).root_node):
            if n.type != "call_expression":
                continue
            fn = n.child_by_field_name("function")
            args = n.child_by_field_name("arguments")
            if re.search(rb"(SaveData|LoadData|SaveArray|LoadArray|SaveStruct|LoadStruct|LoadCharArray)$", fn.text):
                if args.named_children and args.named_children[0].type == "string_literal":
                    result.append(args.named_children[0].text)
        return result

    assert keys(original) == keys(projected)
    old_order = re.search(r"oldVerHintOrder(\{[\s\S]*?\});", original)[1]
    new_order = re.search(r"oldVerHintValues\[\]=(\{[\s\S]*?\});", projected)[1]
    assert old_order == new_order
    expected = load_defaults(base)
    expected = expected.replace(
        """randoContext->overrides.emplace(static_cast<RandomizerCheck>(i),
                                                Rando::ItemOverride(static_cast<RandomizerCheck>(i), rg));""",
        """randoContext->overrides.insert(std::make_pair(static_cast<RandomizerCheck>(i),
                                                Rando::ItemOverride(static_cast<RandomizerCheck>(i), rg)));""",
    )
    assert methods(expected)["LoadRandomizer"] == actual["LoadRandomizer"]
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    runs = []
    for projected_flag in [False, True]:
        folder = OUT / ("host-projected" if projected_flag else "host-original")
        folder.mkdir(exist_ok=True)
        header = (
            (ROOT / "scratch/save-storage-xdk/generated" if projected_flag else ROOT) / "soh/soh/SaveManager.h"
        ).read_text()
        header = header.replace(
            "class SaveManager {",
            "struct SaveSerializationFixtureTag {};\nclass SaveManager {\n    friend struct SaveSerializationAccess;",
        )
        header = header.replace(
            "    SaveManager();",
            "    SaveManager();\n    explicit SaveManager(SaveSerializationFixtureTag) : sectionIndex(SECTION_ID_MAX), currentJsonContext(nullptr) {}",
        )
        stable(folder / "soh/SaveManager.h", header)
        source = """#include <mutex>
#include "resources/runtime_support.h"
#include "soh/SaveManager.h"
#include "soh/Enhancements/randomizer/randomizerTypes.h"
#include <type_traits>
#include <cassert>
#include <iostream>
"""
        source += """static_assert(std::is_same<std::underlying_type<RandomizerGet>::type,int>::value,"enum ABI");
static_assert(std::is_same<std::underlying_type<RandomizerHintTextKey>::type,int>::value,"enum ABI");
"""
        bodies = actual if projected_flag else originals
        source += "\n".join(bodies[n] for n in ["SaveArray", "SaveStruct", "LoadArray", "LoadStruct"]) + "\n"
        contract = (OWN / "json_contract.cpp").read_text()
        if projected_flag:
            contract = contract.replace(
                'manager.LoadData("english", value);',
                '{ const std::string defaultValue; manager.LoadData("english", value, defaultValue); }',
            )
            contract = contract.replace(
                'manager.LoadData("", value);',
                '{ const nlohmann::json defaultValue; manager.LoadData("", value, defaultValue); }',
            )
        stable(folder / "contract.cpp", source + contract)
        prior = ROOT / "scratch/save-storage-xdk" / ("host-projected" if projected_flag else "host-original")
        command = json.loads((prior / "run.json").read_text())["command"]
        command = [str(compiler), "/I" + str(folder)] + [
            a
            for a in command[1:]
            if not a.startswith("/Fo") and not a.startswith("/Fe") and a != str(prior / "contract.cpp")
        ]
        insertion = command.index("/link")
        command[insertion:insertion] = [
            str(folder / "contract.cpp"),
            "/Fo:" + str(folder) + "/",
            "/Fe:" + str(folder / "contract.exe"),
        ]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", run.stdout + run.stderr)
        assert not run.returncode, folder / "build.log"
        run = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        assert not run.returncode, (run.returncode, run.stderr)
        runs.append(dict(projected=projected_flag, command=command, stdout=run.stdout))
    assert runs[0]["stdout"] == runs[1]["stdout"], runs
    native = json.loads((OUT / "xdk/build.json").read_text())[0]
    assert native["exit"] == 0
    assert native["source_sha256"] == hashlib.sha256((ROOT / native["source"]).read_bytes()).hexdigest()
    assert struct.unpack_from("<H", (OUT / "xdk/SaveManager.obj").read_bytes())[0] == 0x1F2
    stable(
        OUT / "verification.json",
        json.dumps(
            dict(
                host=runs,
                native=native,
                methods=42,
                c_bridges=12,
                serialization_keys=len(keys(original)),
                prepared_load_bridge=True,
                actual_randomizer_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )
    print(
        "42 actual SaveManager methods / 12 C bridges retained plus prepared-load bridge; all serialization keys agree."
    )
    print(runs[0]["stdout"])


if __name__ == "__main__":
    main()
