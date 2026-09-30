"""Actual utility data/string functions and resource-bridge preservation checks."""

import collections, hashlib, json, re, runpy, subprocess
from prepare_application_core import ROOT, OUT, OWN, UNITS, prepare, includes
from prepare_application_windows import sha
from prepare_archives import stable
from prepare_randomizer_item import methods
from prepare_custom_message import literal_bytes, escape_literal
from cpp_ast import PARSER, walk


def name(n):
    return n.child_by_field_name("declarator").text.decode().split("(")[0].lstrip("*& ")


def main():
    prepare()
    inventory = {}
    for p in UNITS:
        a = (ROOT / p).read_text(encoding="utf-8-sig")
        b = (OUT / "generated" / p).read_text(encoding="utf-8")
        original = collections.Counter(name(n) for n in methods(a))
        projected = collections.Counter(name(n) for n in methods(b))
        # The parser classifies the array containing a preprocessor include as
        # a function in the original direct-list declaration; it is data.
        if p.endswith("CrashHandlerExt.cpp"):
            original.pop("sSceneIdToStrArray", None)
        assert not original - projected, (p, original - projected)
        literals = [
            n.text.decode()
            for n in walk(PARSER.parse(a.encode()).root_node)
            if n.type == "string_literal" and any(c >= 128 for c in n.text)
        ]
        for s in literals:
            escaped = escape_literal(s)
            assert escaped in b
            assert literal_bytes(s) == literal_bytes(escaped)
        if p.endswith("ResourceManagerHelpers.cpp"):
            # JPEG input is decoded bytes; output explicitly emits big-endian
            # RGBA16 byte pairs, independent of native CPU order. No swap added.
            get = lambda t, f: next(n.text for n in methods(t) if name(n) == f)
            assert get(a, "ResourceMgr_LoadJPEG") == get(b, "ResourceMgr_LoadJPEG")
            assignments = [
                n
                for n in walk(PARSER.parse(a.encode()).root_node)
                if n.type == "assignment_expression" and n.child_by_field_name("left").text.startswith(b"originalGfx[")
            ]
            assert len(assignments) == 3
            for n in assignments:
                assert (
                    "const GfxPatch patch = "
                    + n.child_by_field_name("right").text.decode()
                    + "; "
                    + n.child_by_field_name("left").text.decode()
                    + " = patch;"
                ) in b
        inventory[p] = dict(functions=sum(original.values()), utf8_literals=len(literals))
    compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))["host_environment"]()
    runs = []
    for projected in (False, True):
        folder = OUT / ("host-projected" if projected else "host-original")
        folder.mkdir(exist_ok=True)
        root = OUT / "generated" if projected else ROOT
        text = (root / "soh/soh/util.cpp").read_text(encoding="utf-8-sig")
        text = re.sub(r"^\s*#include[^\n]*\n", "", text, flags=re.M)
        msg = (root / "soh/soh/z_message_OTR.cpp").read_text(encoding="utf-8-sig")
        setter = next(n.text.decode() for n in methods(msg) if name(n) == "SetMessageEntry")
        source = (
            """#include "input/compiler.h"
#include <cstdio>
#include <cassert>
#include <algorithm>
#include <vector>
#include <array>
#include <string>
#include <spdlog/spdlog.h>
#include "global.h"
#include <message_data_static.h>
#include "soh/util.h"
#include "soh/Enhancements/randomizer/randomizerTypes.h"
#include "soh/resource/type/Text.h"
#include "input/compiler.h"
"""
            + text
            + "\n"
            + setter
            + "\nSaveContext gSaveContext;\n"
            + (OWN / "contract.cpp").read_text()
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
                "/DSPDLOG_ACTIVE_LEVEL=6",
            ]
            + ["/I" + str(p) for p in includes()]
            + [str(folder / "contract.cpp"), "/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
        )
        r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / "build.log", r.stdout + r.stderr)
        assert not r.returncode, folder / "build.log"
        r = subprocess.run([str(folder / "contract.exe")], cwd=ROOT, capture_output=True)
        assert not r.returncode, (r.stdout, r.stderr)
        (folder / "values.txt").write_bytes(r.stdout)
        runs.append(
            dict(
                projected=projected,
                command=command,
                exit=r.returncode,
                stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),
                lines=len(r.stdout.splitlines()),
            )
        )
    assert runs[0]["stdout_sha256"] == runs[1]["stdout_sha256"]
    native = json.loads((OUT / "xdk/build.json").read_text())
    for row in native:
        assert (
            row["exit"] == 0 and row["source_sha256"] == hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest()
        )
    stable(
        OUT / "verification.json",
        json.dumps(dict(inventory=inventory, host=runs, native=native, runtime_executed=False), indent=2) + "\n",
    )
    print("Complete core bridge inventory preserved; actual utility/message values agree:", runs[0]["lines"], "lines")


if __name__ == "__main__":
    main()
