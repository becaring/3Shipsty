from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent / 'LibUltraShip+Fast3D360'
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_fast3d import prepare


class DispatchOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare()
        cls.output = ROOT / 'scratch/fast3d-xdk/dispatch-owner-tests'
        cls.output.mkdir(parents=True, exist_ok=True)

    def test_selected_interpreter_and_lifetime(self):
        original = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        selected = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        self.assertEqual(original.count('Interpreter* gfx = mInstance.lock().get();'), 84)
        self.assertEqual(selected.count('Interpreter* gfx = XboxDispatchInterpreter();'), 84)
        self.assertEqual(selected.count('mInstance.lock().get()'), 2)
        self.assertIn('typedef Shipyard::Fast3D::DispatchOwner<Interpreter> XboxDispatchOwner;', selected)
        self.assertIn('    mInstance = gfx;\n    XboxDispatchOwner::Invalidate(sXboxDispatchOwner);', selected)
        run = selected[selected.index('void Interpreter::Run('):]
        self.assertIn('    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);\n    g_exec_stack.start(', run)
        self.assertIn('        gfx_step();\n    }\n    }\n\n    Flush();', run)
        self.assertFalse((ROOT / 'platform/shipyard/fast3d/dispatch_owner.h').exists())
        source = BASE / 'tests/dispatch_owner_contract.cpp'
        batch = self.output / 'build.cmd'
        batch.write_text(
            '@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            'cl /nologo /std:c++17 /O2 /EHsc /MT /I"' + str(BASE / 'sources') + '" "' + str(source) + '" /Fe:owner.exe\n'
            'exit /b %errorlevel%\n')
        result = subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=self.output, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(self.output / 'owner.exe')], cwd=self.output, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_xdk_cached_borrow(self):
        probe = self.output / 'probe.cpp'
        probe.write_text('#include "fast3d/dispatch_owner.h"\nstruct Object {int value;};\n'
                         'extern "C" __declspec(noinline) Object* Borrow(Shipyard::Fast3D::DispatchOwner<Object>* scope,'
                         'const std::weak_ptr<Object>& selected) {return scope->Get(selected);}\n')
        sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        result = subprocess.run([
            str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/O2', '/Ob2', '/MT', '/EHsc', '/D_XBOX', '/DNDEBUG',
            '/showIncludes', '/I' + str(sdk / 'include/xbox'), '/I' + str(BASE / 'sources'),
            '/Fo' + str(self.output / 'probe.obj'), str(probe)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(BASE / 'sources/fast3d/dispatch_owner.h').replace('\\', '/').casefold(),
                      (result.stdout + result.stderr).replace('\\', '/').casefold())
        result = subprocess.run([str(sdk / 'bin/win32/dumpbin.exe'), '/disasm', str(self.output / 'probe.obj')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.output / 'probe.asm').write_text(result.stdout)
        block = re.search(r'(?m)^Borrow:\s*\n(.*?)(?=^[^\s$]|\Z)', result.stdout, re.S | re.M)
        self.assertIsNotNone(block)
        ops = re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)', block[1])
        self.assertIn('blr', ops)
        hot = ops[:ops.index('blr') + 1]
        self.assertIn('lbz', hot)
        self.assertIn('lwz', hot)
        for forbidden in ('bl', 'b', 'mflr', 'mtlr', 'stwu', 'stw', 'std', 'lwarx', 'ldarx'):
            self.assertNotIn(forbidden, hot)


if __name__ == '__main__':
    unittest.main()
