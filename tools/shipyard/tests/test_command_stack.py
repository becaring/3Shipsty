from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent / 'LibUltraShip+Fast3D360'
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_fast3d import prepare


def stack_and_methods(header, source):
    begin = header.index('struct GfxExecStack {')
    stack = header[begin:header.index('\n};', begin) + 3]
    begin = source.index('void GfxExecStack::start(')
    methods = source[begin:source.index('\nvoid gfx_set_framebuffer(', begin)]
    return stack, methods


class CommandStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare()
        cls.output = ROOT / 'scratch/fast3d-xdk/command-stack-tests'
        cls.output.mkdir(parents=True, exist_ok=True)

    def test_actual_stack_operations(self):
        upstream = ROOT / 'libultraship'
        staged = ROOT / 'scratch/fast3d-xdk/generated'
        original = stack_and_methods(
            (upstream / 'include/fast/interpreter.h').read_text(encoding='utf-8-sig'),
            (upstream / 'src/fast/interpreter.cpp').read_text(encoding='utf-8-sig'))
        selected_header = (staged / 'include/fast/interpreter.h').read_text()
        projected = stack_and_methods(
            selected_header, (staged / 'src/fast/interpreter.cpp').read_text())
        self.assertIn('#include "fast3d/command_stack.h"', selected_header)
        self.assertIn('Shipyard::Fast3D::CommandStack<F3DGfx*> cmd_stack', projected[0])
        self.assertFalse((ROOT / 'platform/shipyard/fast3d/command_stack.h').exists())
        driver = (BASE / 'tests/command_stack_contract.cpp').read_text()
        for key, value in zip(('ORIGINAL_STACK', 'ORIGINAL_METHODS', 'PROJECTED_STACK', 'PROJECTED_METHODS'),
                              original + projected):
            driver = driver.replace('// ' + key, value)
        (self.output / 'contract.cpp').write_text(driver, encoding='utf-8')
        (self.output / 'build.cmd').write_text(
            '@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            'cl /nologo /utf-8 /std:c++17 /O2 /EHsc /MT /I"' + str(BASE / 'sources') + '" contract.cpp /Fe:contract.exe\n'
            'exit /b %errorlevel%\n')
        result = subprocess.run(['cmd', '/d', '/c', str(self.output / 'build.cmd')],
                                cwd=self.output, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(self.output / 'contract.exe')],
                                cwd=self.output, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_xdk_fetch_has_no_iterator_calls(self):
        (self.output / 'probe.cpp').write_text(
            '#include "fast3d/command_stack.h"\n'
            'extern "C" __declspec(noinline) void** Fetch(Shipyard::Fast3D::CommandStack<void*>* s) { return &s->top(); }\n')
        sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        result = subprocess.run([
            str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/O2', '/Ob2', '/EHsc', '/MT', '/D_XBOX', '/DNDEBUG', '/showIncludes',
            '/I' + str(sdk / 'include/xbox'), '/I' + str(BASE / 'sources'),
            '/Fo' + str(self.output / 'probe.obj'), str(self.output / 'probe.cpp')],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(BASE / 'sources/fast3d/command_stack.h').replace('\\', '/').casefold(),
                      (result.stdout + result.stderr).replace('\\', '/').casefold())
        result = subprocess.run([str(sdk / 'bin/win32/dumpbin.exe'), '/disasm', str(self.output / 'probe.obj')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.output / 'probe.asm').write_text(result.stdout)
        block = re.search(r'(?m)^Fetch:\s*\n(.*?)(?=^\S|\Z)', result.stdout, re.S | re.M)
        self.assertIsNotNone(block)
        ops = re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)', block[1])
        self.assertEqual(ops[:ops.index('blr') + 1] if 'blr' in ops else ops, ['lwz', 'blr'])


if __name__ == '__main__':
    unittest.main()
