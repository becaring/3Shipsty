"""Direct Modern launch-environment adapter and XDK ownership contract."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base


class EnvironmentAdapterTests(unittest.TestCase):
    def test_host_statuses_and_immutable_lookup(self):
        base = resolve_platform_base(ROOT)
        vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
        installation = subprocess.check_output([
            str(vswhere), '-latest', '-products', '*', '-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'
        ], text=True).strip()
        source = ROOT / 'platform/shipyard/logging/environment.cpp'
        test = ROOT / 'platform/shipyard/logging/tests/environment_cases.cpp'
        with tempfile.TemporaryDirectory(prefix='modern-environment-') as folder:
            output = Path(folder)
            batch = output / 'compile.cmd'
            exe = output / 'environment.exe'
            batch.write_text(
                '@echo off\ncall "' + installation + '/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
                'if errorlevel 1 exit /b 1\n'
                'cl /nologo /EHsc /W4 /WX /MT /I"' + str(source.parent) +
                '" /I"' + str(base/'sources') + '" "' + str(source) + '" "' +
                str(test) + '" /Fo"' + str(output) + '/" /Fe"' + str(exe) +
                '"\nexit /b %errorlevel%\n'
            )
            built = subprocess.run([os.environ['ComSpec'], '/d', '/c', str(batch)],
                                   cwd=output, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            fixtures = {
                'valid': (b'# comment\r\nSSB64_MAX_FRAMES=123\r\nVALUE= a=b #literal \nEMPTY=', 0),
                'duplicate': (b'SSB64_MAX_FRAMES=123\nSSB64_MAX_FRAMES=456', 3),
                'malformed': (b'SSB64_MAX_FRAMES=123\nnot an assignment', 3),
                'nul': (b'SSB64_MAX_FRAMES=123\nBAD=x\0y', 3),
                'name': (b'BAD-NAME=value', 3),
                'oversize': (b'A=' + b'x' * (1024 * 1024 - 1), 3),
            }
            for name, (body, expected) in fixtures.items():
                path = output / (name + '.env')
                path.write_bytes(body)
                with self.subTest(name=name):
                    result = subprocess.run([str(exe), str(path), str(expected)],
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, path, expected in [('missing', output/'missing.env', 1),
                                         ('directory', output, 2)]:
                with self.subTest(name=name):
                    result = subprocess.run([str(exe), str(path), str(expected)],
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_xdk_compiles_adapter_against_shipyard_header(self):
        base = resolve_platform_base(ROOT)
        xdk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
        with tempfile.TemporaryDirectory(prefix='modern-environment-xdk-') as folder:
            output = Path(folder) / 'environment.obj'
            command = [str(xdk/'bin/win32/cl.exe'), '/nologo', '/c', '/TP', '/EHsc',
                       '/MT', '/W4', '/D_XBOX', '/I'+str(xdk/'include/xbox'),
                       '/I'+str(base/'sources'), '/Fo'+str(output),
                       str(ROOT/'platform/shipyard/logging/environment.cpp')]
            built = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual(int.from_bytes(output.read_bytes()[:2], 'little'), 0x1f2)


if __name__ == '__main__':
    unittest.main()
