"""Exercise the maintained frame handoff with native waits and bounded host workers."""

from pathlib import Path
import subprocess
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard/tests"))
from test_binary import host_environment, PLATFORM_BASE, XDK


class FrameChannelTests(unittest.TestCase):
    def test_concurrent_ownership(self):
        compiler, env = host_environment()
        folder = ROOT / "scratch/frame-channel"
        folder.mkdir(parents=True, exist_ok=True)
        command = [
            str(compiler),
            "/nologo",
            "/std:c++14",
            "/EHsc",
            "/MD",
            "/W4",
            "/WX",
            "/I" + str(ROOT / "platform/shipyard"),
            "/I" + str(PLATFORM_BASE / "sources"),
            str(Path(__file__).with_suffix(".cpp")),
            str(PLATFORM_BASE / "sources/async/native.cpp"),
            "/Fo:" + str(folder) + "/",
            "/Fe:" + str(folder / "contract.exe"),
        ]
        built = subprocess.run(
            command, cwd=folder, env=env, capture_output=True, text=True, timeout=45
        )
        (folder / "build.log").write_text(built.stdout + built.stderr)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        run = subprocess.run(
            [str(folder / "contract.exe")],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=30,
        )
        (folder / "run.log").write_text(run.stdout + run.stderr)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        print(run.stdout.strip())

    def test_xdk_packet_instantiation(self):
        folder = ROOT / "scratch/frame-channel/xdk"
        folder.mkdir(parents=True, exist_ok=True)
        obj = folder / "frame_channel.obj"
        command = [
            str(XDK / "bin/win32/cl.exe"),
            "/nologo",
            "/c",
            "/EHsc",
            "/W4",
            "/WX",
            "/D_XBOX",
            "/D_XBOX_VER=200",
            "/I" + str(XDK / "include/xbox"),
            "/I" + str(ROOT / "platform/shipyard"),
            "/I" + str(PLATFORM_BASE / "sources"),
            "/Fo" + str(obj),
            str(Path(__file__).with_name("test_frame_channel_xdk.cpp")),
        ]
        built = subprocess.run(
            command, cwd=folder, capture_output=True, text=True, timeout=45
        )
        (folder / "build.log").write_text(built.stdout + built.stderr)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertEqual(struct.unpack_from("<H", obj.read_bytes())[0], 0x1F2)


if __name__ == "__main__":
    unittest.main()
