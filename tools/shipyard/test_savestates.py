"""Savestate methods against typed memory fixtures; no game or service stubs."""

import hashlib, json, re, runpy, struct, unittest
from prepare_savestates import ROOT, OUT, OWN, BASE, prepare, build
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from prepare_configuration import once
from cpp_ast import PARSER, walk
from prepare_randomizer import edits_apply

ENV = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))
METHODS = [
    "SaveStateMgr::SaveStateMgr",
    "SaveStateMgr::~SaveStateMgr",
    "SaveStateMgr::SetCurrentSlot",
    "SaveStateMgr::GetCurrentSlot",
    "SaveStateMgr::AddRequest",
    "SaveState::SaveState",
    "SaveState::BackupSeqScriptState",
    "SaveState::LoadSeqScriptState",
]


def functions(text):
    return [
        n
        for n in walk(PARSER.parse(text.encode()).root_node)
        if n.type == "function_definition"
    ]


def name(n):
    return n.child_by_field_name("declarator").text.decode().split("(")[0].strip()


def host(projected):
    folder = OUT / ("host-projected" if projected else "host-original")
    folder.mkdir(parents=True, exist_ok=True)
    text = (
        (OUT / "generated" if projected else ROOT) / BASE / "savestates.cpp"
    ).read_text()
    source = text[: text.index("SaveStateMgr::SaveStateMgr()")]
    source = re.sub(
        r"^#include .*?(?:OTRGlobals|OTRAudio|libultraship/libultraship|ship/(?:Context|window/)).*\n",
        "",
        source,
        flags=re.M,
    )
    source = source.replace(
        '#include "soh/Enhancements/savestates.h"', '#include "savestates.h"'
    )
    source = source.replace('#include "../../src/overlays/', '#include "src/overlays/')
    source = source.replace("  private:", "  public:")
    header = (
        (
            (ROOT / "scratch/application-xdk/generated" if projected else ROOT)
            / BASE
            / "savestates.h"
        )
        .read_text()
        .replace("  private:", "  public:")
    )
    stable(folder / "savestates.h", header)
    count = 0
    for n in functions(text):
        if name(n) not in METHODS:
            continue
        body = n.text.decode()
        edits = []
        for call in walk(PARSER.parse(body.encode()).root_node):
            if call.type == "expression_statement" and call.text.startswith(
                b"Ship::Context::GetInstance()"
            ):
                edits.append(
                    (
                        call.start_byte,
                        call.end_byte,
                        "// Live notification excluded only from host method audit.",
                    )
                )
        count += len(edits)
        source += edits_apply(body.encode(), edits) + "\n"
    assert count == 3, count
    source = (
        '#include <cstdio>\n#include <cstring>\n#include <vector>\n#include "resources/runtime_support.h"\n'
        + source
        + "\n"
        + (OWN / "contract.cpp").read_text()
    )
    stable(folder / "contract.cpp", source)
    compiler, env = ENV["host_environment"]()
    native = json.loads((OUT / "xdk/build.json").read_text())[0]["command"]
    roots = [
        p for p in native if p.startswith("/I") and "Microsoft Xbox 360 SDK" not in p
    ] + ["/I" + str(PLATFORM_BASE / "sources")]
    command = (
        [
            compiler,
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/GR",
            "/MD",
            "/DNOMINMAX",
            "/DF3DEX_GBI_2",
            "/DCONTROLLERBUTTONS_T=uint32_t",
            "/DSHIPYARD_AUDIO_TEST",
            "/I" + str(OUT / "generated/soh/soh/Enhancements"),
        ]
        + roots
        + [folder / "contract.cpp"]
    )
    command += [
        PLATFORM_BASE / "sources/async/native.cpp",
        PLATFORM_BASE / "sources/clock/chrono.cpp",
    ]
    command += ["/Fo:" + str(folder) + "/", "/Fe:" + str(folder / "contract.exe")]
    result = ENV["invoke"](command, folder, "compile", env, success=False)
    assert result["returncode"] == 0, "\n".join(
        l for l in (result["stdout"] + result["stderr"]).splitlines() if "error " in l
    )[:4500]
    return ENV["invoke"]([folder / "contract.exe"], folder, "run", env)["stdout"]


class SavestateContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare()
        build()

    def test_native_full_tu(self):
        row = json.loads((OUT / "xdk/build.json").read_text())[0]
        self.assertEqual(row["exit"], 0)
        self.assertEqual(
            hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest(),
            row["source_sha256"],
        )

    def test_original_projected_contracts(self):
        original = host(False)
        projected = host(True)
        self.assertEqual(original, projected)
        stable(
            OUT / "verification.json",
            json.dumps(
                dict(
                    methods=METHODS,
                    result=original,
                    scope="""Actual slot/request methods minus live notification dispatch; actual constructor and audio script relocation \
over real game data types in test memory; no production game or service stubs""",
                    native_runtime_executed=False,
                ),
                indent=2,
            )
            + "\n",
        )

    def test_complete_serialization_and_inventory(self):
        original = (ROOT / BASE / "savestates.cpp").read_text()
        projected = (OUT / "generated" / BASE / "savestates.cpp").read_text()
        self.assertEqual(
            [name(n) for n in functions(original)],
            [name(n) for n in functions(projected)],
        )
        for before, after in zip(functions(original), functions(projected)):
            if name(before).startswith("SaveState::"):
                actual = after.text.decode()
                boundaries = {"SaveState::Save": 0, "SaveState::Load": 1}
                if name(before) in boundaries:
                    statement = (
                        "\n    Shipyard_OverlapSaveStateBoundary(%d);"
                        % boundaries[name(before)]
                    )
                    self.assertEqual(actual.count(statement), 1)
                    actual = actual.replace(statement, "")
                self.assertEqual(
                    before.text.decode().replace(
                        "std::unique_lock<std::mutex>",
                        "Shipyard::Async::unique_lock<Shipyard::Async::mutex>",
                    ),
                    actual,
                )
        shape = lambda s: next(
            n.text.decode()
            for n in walk(PARSER.parse(s.encode()).root_node)
            if n.type == "struct_specifier"
            and n.child_by_field_name("name")
            and n.child_by_field_name("name").text == b"SaveStateInfo"
        )
        self.assertEqual(shape(original), shape(projected))
        self.assertEqual(projected.count("TextDrawNotification("), 5)
        self.assertIn("OTRGlobals::Instance->gSaveStateMgr", projected)

    def test_repeatable(self):
        first = (OUT / "manifest.json").read_bytes()
        prepare()
        self.assertEqual(first, (OUT / "manifest.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
