"""Compare original and selected Modern replay using actual recorder methods."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class InterpolationReplayTests(unittest.TestCase):
    def test_actor_relative_and_raw_replay(self):
        base = Path(
            os.environ.get(
                "XBOX360_PLATFORM_BASE", ROOT / json.loads((ROOT / "platform-base.lock.json").read_text())["base"]
            )
        ).resolve()
        fixture = Path(__file__).with_name("interpolation_pairing_fixture.cpp").read_text()
        relative = "soh/soh/frame_interpolation.cpp"
        sources = [ROOT / relative, ROOT / "scratch/interpolation-xdk/generated" / relative]
        vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
        installation = subprocess.check_output(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            text=True,
        ).strip()
        results = []
        with tempfile.TemporaryDirectory(prefix="modern-pairing-") as directory:
            out = Path(directory)
            for index, path in enumerate(sources):
                source = path.read_text()
                source = source[source.index("static bool invert_matrix") :]
                name = "replay" + str(index)
                (out / (name + ".cpp")).write_text(fixture.replace("// SELECTED RECORDER", source))
                batch = out / "build.cmd"
                define = " /DMODERN_RECYCLE_REPLAY" if index else ""
                batch.write_text(
                    '@echo off\ncall "'
                    + installation
                    + '/VC/Auxiliary/Build/vcvars64.bat" >nul\nif errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /EHsc /O2 /fp:precise /MT'
                    + define
                    + ' /I"'
                    + str(ROOT / "platform/shipyard")
                    + '" /I"'
                    + str(base / "sources")
                    + '" '
                    + name
                    + ".cpp /Fe"
                    + name
                    + ".exe\nexit /b %errorlevel%\n"
                )
                built = subprocess.run(
                    [os.environ["ComSpec"], "/d", "/c", str(batch)], cwd=out, capture_output=True, text=True
                )
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(out / (name + ".exe"))], capture_output=True, text=True, timeout=15)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                results.append(ran.stdout)
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
