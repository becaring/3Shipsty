"""Collision geometry, icon tables and UI source-inventory differential."""

import collections, hashlib, json, re, runpy, subprocess
from prepare_application_windows import ROOT, OUT, OWN, DEBUG, GUI, UNITS, prepare, includes
from prepare_archives import stable
from prepare_randomizer_item import methods
from cpp_ast import PARSER, walk
from prepare_custom_message import literal_bytes, escape_literal
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)


def fname(n):
    return n.child_by_field_name("declarator").text.decode().split("(")[0].lstrip("*& ")


def calls(text):
    values = collections.Counter()
    for n in walk(PARSER.parse(text.encode()).root_node):
        if n.type != "call_expression":
            continue
        f = n.child_by_field_name("function").text.decode()
        if f.startswith(("ImGui::", "CVar")) or (f.startswith("UIWidgets::") and "Options" not in f):
            values[f] += 1
    return values


def main():
    prepare()
    coverage = {}
    for name in UNITS:
        a = (ROOT / name).read_text(encoding="utf-8")
        b = (OUT / "generated" / name).read_text(encoding="utf-8")
        original = collections.Counter(fname(n) for n in methods(a))
        projected = collections.Counter(fname(n) for n in methods(b))
        assert not original - projected, (name, original - projected)
        ca, cb = calls(a), calls(b)
        if name.endswith("SohStatsWindow.cpp"):
            cb["ImGui::Text"] -= 1
            ca["ImGui::GetIO"] -= 2
        if name.endswith("colViewer.cpp"):
            assert 'if (!CVarGetInteger(CVAR_DEVELOPER_TOOLS("ColViewer.Enabled"), 0)) return;' in b
            cb["CVarGetInteger"] -= 1
        assert ca == cb, (name, ca - cb, cb - ca)
        literals = [
            n.text.decode()
            for n in walk(PARSER.parse(a.encode()).root_node)
            if n.type == "string_literal" and any(c >= 128 for c in n.text)
        ]
        for literal in literals:
            escaped = escape_literal(literal)
            assert escaped in b
            assert literal_bytes(literal) == literal_bytes(escaped)
        coverage[name] = dict(
            functions=sum(original.values()), ui_cvar_calls=sum(ca.values()), utf8_literals=len(literals)
        )
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    runs = []
    for projected in (False, True):
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        base = OUT / "generated" if projected else ROOT
        col = (base / (DEBUG + "colViewer.cpp")).read_text(encoding="utf-8")
        geometry = []
        for n in methods(col):
            if fname(n) in ("CalcTriNorm", "CreateCylinderData", "CreateSphereFace", "CreateSphereData"):
                geometry.append(n.text.decode())
        assert len(geometry) == 4
        macros = col[col.index("#define G_CC_MODULATERGB_PRIM_ENVA") : col.index("void CreateCylinderData()")]
        declarations = "\n".join(re.findall(r"static std::vector<(?:Gfx|Vtx)> (?:cylinder|sphere)\w+;", col))
        assert len(declarations.splitlines()) == 4
        icons = (base / (GUI + "ImGuiUtils.cpp")).read_text(encoding="utf-8")
        tables = icons[
            icons.index("static std::map" if projected else "std::map") : icons.index("const char* GetTextureForItemId")
        ]
        getter = next(n.text.decode() for n in methods(icons) if fname(n) == "GetTextureForItemId")
        timer = (base / (DEBUG + "performanceTimer.cpp")).read_text(encoding="utf-8")
        stable(folder / "performanceTimer.h", (base / (DEBUG + "performanceTimer.h")).read_text(encoding="utf-8"))
        inv = (ROOT / "soh/src/code/z_inventory.c").read_text()
        icon_decl = re.search(r"void\* gItemIcons\[\] = \{[\s\S]*?\n\};", inv)[0]
        # Match C's existing pointer conversion while compiling this C table in a C++ fixture.
        icon_decl = re.sub(r"(?m)^(\s*)(g\w+)(,?)$", r"\1(void*)\2\3", icon_decl)
        icon_decl = icon_decl.replace('""', '(void*)""')
        source = (
            """#include <vector>
#include <tuple>
#include <cmath>
#include <cstdio>
#include <cassert>
#include <bit>
#include "performanceTimer.h"
#include "async/native.h"
#include "application-windows/support.h"
#include "resources/runtime_support.h"
#include "soh/SohGui/ImGuiUtils.h"
#include "soh_assets.h"
extern "C" {
"""
            + icon_decl
            + "\n}\n"
            + tables
            + "\n"
            + getter
            + "\n"
            + declarations
            + "\n"
            + macros
            + "\n"
            + "\n".join(geometry)
            + "\n"
            + "\n".join(n.text.decode() for n in methods(timer))
            + "\n"
            + (OWN / "geometry_contract.cpp").read_text()
        )
        stable(folder / "contract.cpp", source)
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
                str(PLATFORM_BASE / "sources/clock/chrono.cpp"),
                "/Fo:" + str(folder) + "/",
                "/Fe:" + str(folder / "contract.exe"),
            ]
        )
        r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", r.stdout + r.stderr)
        assert not r.returncode, folder / "build.log"
        r = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True, text=True)
        assert not r.returncode, (r.stdout, r.stderr)
        stable(folder / "values.txt", r.stdout)
        runs.append(
            dict(
                projected=projected,
                command=command,
                exit=r.returncode,
                stdout_sha256=hashlib.sha256(r.stdout.encode()).hexdigest(),
                lines=len(r.stdout.splitlines()),
            )
        )
    assert runs[0]["stdout_sha256"] == runs[1]["stdout_sha256"]
    native = json.loads((OUT / "xdk/build.json").read_text())
    for row in native:
        assert row["exit"] == 0
        assert row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
    stable(
        OUT / "verification.json",
        json.dumps(dict(coverage=coverage, host=runs, native=native, rendered_frames=False), indent=2) + "\n",
    )
    print(
        "All 13 full UI units preserve functions and widget/CVar calls; geometry and icon output matches ("
        + str(runs[0]["lines"])
        + " lines)"
    )


if __name__ == "__main__":
    main()
