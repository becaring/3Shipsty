"""Immutable fog values against the upstream signed-short consumer."""

from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from tools.shipyard.tests.test_binary import host_environment
from tools.shipyard.platform_base import resolve

ROOT = Path(__file__).resolve().parents[3]


class FogCaptureTests(unittest.TestCase):
    def test_exact_capture_and_materialization_across_rounding_changes(self):
        projection = runpy.run_path(str(ROOT / "tools/shipyard/deferred_lit_fog.py"))
        methods = projection["SOURCE_METHODS"]
        materializer = (
            methods.split("bool Interpreter::XboxTryDeferVertices(", 1)[0]
            + "void Interpreter::XboxMaterializeVertex("
            + methods.split("void Interpreter::XboxMaterializeVertex(", 1)[1]
        )
        contract = Path(__file__).with_name("test_fog_capture_contract.cpp").read_text()
        contract = contract.replace("// PROJECTED_TYPES", projection["HEADER_TYPES"]).replace(
            "// PROJECTED_METHODS", materializer
        )
        compiler, env = host_environment()
        with tempfile.TemporaryDirectory(prefix="modern-fog-capture-") as directory:
            folder = Path(directory)
            source = folder / "contract.cpp"
            source.write_text(contract)
            built = subprocess.run(
                [
                    str(compiler),
                    "/nologo",
                    "/std:c++20",
                    "/O2",
                    "/fp:precise",
                    "/EHsc",
                    "/MD",
                    "/I" + str(resolve(ROOT) / "sources"),
                    str(source),
                    "/Fe:" + str(folder / "contract.exe"),
                ],
                cwd=folder,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, built.returncode, built.stdout + built.stderr)
            ran = subprocess.run([str(folder / "contract.exe")], cwd=folder, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
            self.assertIn("65536 signed values, 4 capture modes, 4 consume modes", ran.stdout)


if __name__ == "__main__":
    unittest.main()
