"""Compile and run the pair-local packed-vertex byte differential."""
from pathlib import Path
import os
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent


def host_environment():
    msvc = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.43.34808')
    sdk = Path('C:/Program Files (x86)/Windows Kits/10')
    env = os.environ.copy()
    env['PATH'] = str(msvc / 'bin/Hostx64/x64') + os.pathsep + env['PATH']
    env['INCLUDE'] = ';'.join(map(str, [msvc / 'include'] +
        [sdk / 'Include/10.0.26100.0' / p for p in ('ucrt', 'shared', 'um')]))
    env['LIB'] = ';'.join(map(str, [msvc / 'lib/x64'] +
        [sdk / 'Lib/10.0.26100.0' / p / 'x64' for p in ('ucrt', 'um')]))
    return msvc / 'bin/Hostx64/x64/cl.exe', env


class Tri2PackedReuse(unittest.TestCase):
    def test_pair_bytes_and_guards(self):
        out = ROOT / 'scratch/fast3d-xdk/tri2-packed-reuse'
        out.mkdir(parents=True, exist_ok=True)
        compiler, environment = host_environment()
        source = HERE / 'test_tri2_packed_reuse.cpp'
        exe = out / 'contract.exe'
        command = [str(compiler), '/nologo', '/O2', '/fp:precise', '/EHsc', '/MD',
                   '/I' + str(ROOT / 'platform/shipyard'), str(source), '/Fe:' + str(exe)]
        built = subprocess.run(command, cwd=out, env=environment, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('quad_compute=4/6', result.stdout)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
