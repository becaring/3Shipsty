"""Network.cpp loopback, native transport and declaration verification."""

import hashlib, json, runpy, subprocess, unittest
from prepare_network import ROOT, OUT, OWN, BASE, prepare, build, value_expressions
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from cpp_ast import PARSER, walk

ENV = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))


class NetworkContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare()

    def test_native_complete_transport_and_headers(self):
        build()

    def test_real_loopback(self):
        folder = OUT / "host"
        folder.mkdir(exist_ok=True)
        compiler, env = ENV["host_environment"]()
        command = [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/GR",
            "/MD",
            "/utf-8",
            "/DNOMINMAX",
            "/DENABLE_REMOTE_CONTROL",
            "/I" + str(OUT / "generated/soh"),
            "/I" + str(ROOT / "platform/shipyard"),
            "/I" + str(PLATFORM_BASE / "sources"),
            "/I" + str(PLATFORM_BASE / "sources/json/include"),
            "/I" + str(ROOT / "scratch/json-xdk/backend-generated"),
            "/I" + str(ROOT / "scratch/deps/spdlog/include"),
            "/I" + str(ROOT / "libultraship/include"),
            OWN / "loopback.cpp",
            PLATFORM_BASE / "sources/network/transport.cpp",
            OUT / "generated" / BASE / "Network.cpp",
            PLATFORM_BASE / "sources/async/native.cpp",
            PLATFORM_BASE / "sources/json/json.cpp",
            "/Fo:" + str(folder) + "/",
            "/Fe:" + str(folder / "loopback.exe"),
            "/link",
            "ws2_32.lib",
        ]
        record = ENV["invoke"](command, folder, "compile", env, success=False)
        self.assertEqual(
            record["returncode"],
            0,
            "\n".join(l for l in (record["stdout"] + record["stderr"]).splitlines() if "error " in l)[:4500],
        )
        r = subprocess.run(
            [str(folder / "loopback.exe")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20
        )
        stable(
            folder / "run.json",
            json.dumps(
                dict(command=[str(folder / "loopback.exe")], exit=r.returncode, stdout=r.stdout, stderr=r.stderr),
                indent=2,
            )
            + "\n",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_original_framing_and_method_inventory(self):
        def names(text):
            return [
                n.child_by_field_name("declarator").text.decode()
                for n in walk(PARSER.parse(text.encode()).root_node)
                if n.type == "function_definition"
            ]

        original = (ROOT / BASE / "Network.cpp").read_text()
        projected = (OUT / "generated" / BASE / "Network.cpp").read_text()
        self.assertEqual(names(original), names(projected))
        start = original.index("            HandleRemoteData(remoteDataReceived);")
        end = original.index("\n        if (socketSet)")
        self.assertIn(original[start:end], projected)
        self.assertIn("#ifdef ENABLE_REMOTE_CONTROL", projected)
        self.assertNotIn("#define ENABLE_REMOTE_CONTROL 0", projected)
        self.assertIn("BUILD_REMOTE_CONTROL=1", (ROOT / "archive/upstream-ci/generate-builds.yml").read_text())

    def test_repeatable_generation(self):
        first = json.loads((OUT / "manifest.json").read_text())["generated"]
        prepare()
        self.assertEqual(first, json.loads((OUT / "manifest.json").read_text())["generated"])
        self.assertEqual(value_expressions("auto a=new Anchor();"), "auto a=new Anchor(Shipyard::SohUI::ValueInit());")
        self.assertEqual(value_expressions("Anchor a;"), "Anchor a;")


if __name__ == "__main__":
    unittest.main()
