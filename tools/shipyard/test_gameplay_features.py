"""Feature inventory and original versus projected data and lifetime contracts."""

import collections, hashlib, json, re, runpy, subprocess
from prepare_gameplay_features import ROOT, OUT, OWN, prepare, includes
from prepare_archives import stable
from prepare_randomizer_item import methods
from prepare_custom_message import literal_bytes
from cpp_ast import PARSER, walk
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
BASE = "soh/soh/Enhancements/"


def read(path):
    return path.read_text(encoding="utf-8-sig")


def method(text, name):
    return next(
        n.text.decode()
        for n in methods(text)
        if n.child_by_field_name("declarator").text.decode().split("(")[0] == name
    )


def declaration(text, name):
    for n in walk(PARSER.parse(text.encode()).root_node):
        if n.type != "declaration":
            continue
        for c in n.named_children:
            if (
                c.type == "init_declarator"
                and c.child_by_field_name("declarator").text.decode().removesuffix("[]") == name
            ):
                return n.text.decode()
    raise ValueError(name)


def structure(text, name):
    n = next(
        n
        for n in walk(PARSER.parse(text.encode()).root_node)
        if n.type == "struct_specifier"
        and n.child_by_field_name("name") is not None
        and n.child_by_field_name("name").text.decode() == name
    )
    return n.parent.text.decode() if n.parent.type == "type_definition" else n.text.decode() + ";"


def inventory(original, projected):
    result = {}
    a = list(walk(PARSER.parse(original.encode()).root_node))
    b = list(walk(PARSER.parse(projected.encode()).root_node))
    names = lambda nodes: [
        n.child_by_field_name("declarator").text.decode().split("(")[0]
        for n in nodes
        if n.type == "function_definition"
    ]
    assert not (collections.Counter(names(a)) - collections.Counter(names(b)))
    result["functions"] = len(names(a))
    for category, predicate in [
        ("cvars", lambda f: f.startswith("CVAR_")),
        ("gfx", lambda f: f.startswith("gs")),
        ("hooks", lambda f: f in ("COND_HOOK", "COND_ID_HOOK", "COND_VB_SHOULD", "REGISTER_VB_SHOULD")),
    ]:
        extract = lambda nodes: [
            n.child_by_field_name("function").text.decode()
            for n in nodes
            if n.type == "call_expression" and predicate(n.child_by_field_name("function").text.decode())
        ]
        assert collections.Counter(extract(a)) == collections.Counter(extract(b)), category
        result[category] = len(extract(a))
        if category == "gfx":
            expressions = lambda nodes: collections.Counter(
                n.text.decode()
                for n in nodes
                if n.type == "call_expression" and n.child_by_field_name("function").text.startswith(b"gs")
            )
            assert expressions(a) == expressions(b), "graphics command arguments"

    def strings(text):
        text = re.sub(r"^\s*#\s*include[^\n]*", "", text, flags=re.M)
        return collections.Counter(
            literal_bytes(s)
            for s in re.findall(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"', text)
            if s.startswith('"')
        )

    # Additional diagnostic source paths are permitted, original user-visible,
    # asset and configuration strings must remain in the complete projection.
    assert not (strings(original) - strings(projected))
    result["literal_occurrences"] = sum(strings(original).values())
    for fn in ("RAND_GET_OPTION", "GameInteractor::RegisterGameHook", "Notification::Emit"):
        assert original.count(fn) == projected.count(fn), fn
    return result


def main():
    units = prepare()
    original = {n: read(ROOT / n) for n in units}
    projected = {n: read(OUT / "generated" / n) for n in units}
    inventories = {n: inventory(original[n], projected[n]) for n in units}
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    rows = []
    for projected_flag in (False, True):
        folder = OUT / ("host-projected" if projected_flag else "host-original")
        folder.mkdir(exist_ok=True)
        sources = projected if projected_flag else original

        def source(n):
            return sources[BASE + n + ".cpp"]

        prefix = """#include "resources/runtime_support.h"
#include "z64.h"
#include "soh/Enhancements/enhancementTypes.h"
#include "soh/cvar_prefixes.h"
#include <map>
#include <set>
#include <array>
#include <vector>
#include <string>
#include <cassert>
#include <iostream>
#include <cstring>
"""
        data = prefix
        for name, fields in [
            ("Graphics/Disable2DBackgrounds", ["fogControlList", "skyboxSceneControlList", "skyboxIdControlList"]),
            ("Graphics/DisableFixedCamera", ["fixedCameraSceneList"]),
        ]:
            t = source(name)
            if projected_flag:
                data += (
                    "\n".join(
                        n.text.decode()
                        for n in walk(PARSER.parse(t.encode()).root_node)
                        if n.type == "declaration" and b"ShipyardSetValues" in n.text and b"[]" in n.text
                    )
                    + "\n"
                )
            data += "\n".join(declaration(t, f) for f in fields) + "\n"
        data += method(source("Graphics/DisableFixedCamera"), "IsFixedCameraType") + "\n"
        enemy = source("ExtraModes/EnemyRandomizer")
        data += (
            structure(enemy, "EnemyEntry")
            + "\n"
            + declaration(enemy, "randomizedEnemySpawnTable")
            + "\n"
            + declaration(enemy, "enemiesToRandomize")
            + "\n"
        )
        data += (
            "#define CUSTOM_SURFACE_TYPE 32\n"
            + declaration(source("Restorations/GraveHoleJumps"), "graveyardGeometryPatches")
            + "\n"
        )
        day = source("QoL/DaytimeGS")
        data += (
            structure(day, "DayTimeGoldSkulltulas")
            + "\ntypedef std::vector<DayTimeGoldSkulltulas> DayTimeGoldSkulltulasList;\n"
        )
        data += (
            method(day, "MakedayTimeGoldSkulltulas") + "\n"
            if projected_flag
            else "static DayTimeGoldSkulltulasList MakedayTimeGoldSkulltulas(){"
            + declaration(day, "dayTimeGoldSkulltulas")
            + "return dayTimeGoldSkulltulas;}\n"
        )
        data += (OWN / "data_contract.cpp").read_text()
        stable(folder / "data.cpp", data)
        # Full WeirdAnimation declaration and its neighbor table.
        header = read(
            (OUT / "generated" if projected_flag else ROOT) / (BASE + "Restorations/N64WeirdFrames/WeirdAnimation.h")
        )
        header = header.replace("class WeirdAnimation {", "class WeirdAnimation { friend struct AnimationContract;")
        stable(folder / "WeirdAnimation.h", header)
        anim = prefix + '#include "WeirdAnimation.h"\n#include "objects/gameplay_keep/gameplay_keep.h"\n'
        anim += (
            method(source("Restorations/N64WeirdFrames/N64WeirdFrames"), "MakeweirdAnimations") + "\n"
            if projected_flag
            else ""
        )
        anim += (
            declaration(source("Restorations/N64WeirdFrames/N64WeirdFrames"), "weirdAnimations")
            + "\n"
            + (OWN / "animation_contract.cpp").read_text()
        )
        stable(folder / "animation.cpp", anim)
        warp = prefix + "#include <nlohmann/json.hpp>\n" + structure(source("Warping"), "WarpPoint") + "\n"
        if projected_flag:
            warp += (
                "\n".join(
                    method(source("Warping"), n)
                    for n in (
                        "EncodeVec3f",
                        "DecodeVec3f",
                        "EncodeWarpPoint",
                        "DecodeWarpPoint",
                        "EncodeWarpPoints",
                        "DecodeWarpPoints",
                    )
                )
                + "\n"
            )
        else:
            warp += "\n".join(re.findall(r"^NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE[^\n]+", source("Warping"), re.M)) + "\n"
            warp += """static nlohmann::json EncodeWarpPoints(const std::map<std::string,WarpPoint>& v){return v;}
static std::map<std::string,WarpPoint> DecodeWarpPoints(const nlohmann::json& j){return \
j.get<std::map<std::string,WarpPoint>>();}
"""
        warp += (OWN / "warp_contract.cpp").read_text()
        stable(folder / "warp.cpp", warp)
        for kind in ("data", "animation", "warp"):
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
                "/FI" + str(ROOT / "scratch/configuration-xdk/generated/include/compile_definitions.h"),
            ]
            if projected_flag:
                command += ["/DSHIPYARD_FEATURE_PROJECTED"]
            elif kind == "warp":
                command += ["/Zc:preprocessor", "/I" + str(ROOT / "platform/shipyard/json/upstream/include")]
            command += ["/I" + str(p) for p in includes()] + [str(folder / (kind + ".cpp"))]
            if kind == "warp" and projected_flag:
                command += [str(PLATFORM_BASE / "sources/json/json.cpp")]
            command += ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / (kind + ".exe")), "/link", "/OPT:REF"]
            r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            stable(folder / (kind + "-build.log"), r.stdout + r.stderr)
            assert not r.returncode, folder / (kind + "-build.log")
            r = subprocess.run([str(folder / (kind + ".exe"))], cwd=ROOT, capture_output=True, text=True)
            row = dict(
                kind=kind,
                projected=projected_flag,
                command=command,
                exit=r.returncode,
                stdout=r.stdout,
                stderr=r.stderr,
            )
            rows.append(row)
            assert not r.returncode, row
    for kind in ("data", "animation", "warp"):
        pair = [r for r in rows if r["kind"] == kind]
        assert pair[0]["stdout"] == pair[1]["stdout"], kind
    native = json.loads((OUT / "xdk/build.json").read_text())
    assert len(native) == 89
    for row in native:
        assert not row["exit"], row["path"]
        assert row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest(), row["path"]
        assert row["object_sha256"] == hashlib.sha256((ROOT / row["object"]).read_bytes()).hexdigest()
    # The XDK lambda used to turn redundant block-scope declarations in the
    # display macros into C++ imports. Verify the complete object imports
    # the real C implementations, rather than supplying duplicate wrappers.
    file_select = next(row for row in native if row["path"].endswith("/FileSelectMoreInfo.cpp"))
    symbols = subprocess.check_output(
        [
            "C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/dumpbin.exe",
            "/symbols",
            str(ROOT / file_select["object"]),
        ],
        text=True,
    )
    for name in ("FrameInterpolation_RecordOpenChild", "FrameInterpolation_RecordCloseChild"):
        references = [
            line.split("|", 1)[1].strip() for line in symbols.splitlines() if "UNDEF" in line and name in line
        ]
        assert references == [name], references
    stable(
        OUT / "verification.json",
        json.dumps(dict(inventories=inventories, host=rows, native=native, native_gameplay_executed=False), indent=2)
        + "\n",
    )
    print("All 89 source inventories and six original/projected contracts pass.")


if __name__ == "__main__":
    main()
