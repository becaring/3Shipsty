"""Actual Modern recorder/replay with XDK aggregate-copy behavior and heap counts."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_interpolation import recording_ownership, transform
from tools.shipyard.tests.test_binary import host_environment, PLATFORM_BASE


class OwnershipTests(unittest.TestCase):
    def test_record_replay_and_ownership(self):
        original = (ROOT / 'soh/soh/frame_interpolation.cpp').read_text()
        fixture = Path(__file__).with_suffix('.cpp').read_text()
        compiler, env = host_environment()
        outputs = []
        for label, improved, text in [('control', False, original),
                                      ('ownership', True, recording_ownership(original)),
                                      ('projected', True, transform(original))]:
            # Host C++20 would synthesize the moves absent on XDK. Explicit
            # copies reproduce XDK's old aggregate behavior for the control.
            if not improved:
                text = text.replace('    vector<pair<Op, size_t>> items;', '''    vector<pair<Op, size_t>> items;
    Path() {}
    Path(const Path& other) : children(other.children), ops(other.ops), items(other.items) { ++copies; }
    Path& operator=(const Path& other) { ++copies; children=other.children; ops=other.ops; items=other.items; return *this; }''')
            else:
                text = text.replace('items(other.items) {}', 'items(other.items) { ++copies; }')
            text = text.replace('    Path root_path;', '''    Path root_path;
    Recording() {}
    Recording(const Recording& other) : root_path(other.root_path) {}
    Recording& operator=(const Recording& other) { root_path=other.root_path; return *this; }''')
            text = text.replace('#include <libultraship/bridge.h>', '')
            text = text.replace('#include "soh/OTRGlobals.h"', 'extern "C" uint32_t Ship_GetInterpolationFPS();')
            text = text.replace('OTRGlobals::Instance->GetInterpolationFPS()', 'Ship_GetInterpolationFPS()')
            # External matrix services are traps: this fixture records final
            # matrices, whose replay is entirely in the actual Modern source.
            start = text.index('extern "C" {')
            end = text.index('\n}', start)
            declarations = text[start:end]
            stubs = re.sub(r';', '{ std::abort(); }', declarations) + '\n}'
            prefix = '''#include <stdexcept>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <memory>
static size_t copies=0, allocations=0; static long failAfter=-1;
void* operator new(size_t n) { if(failAfter==0)throw std::bad_alloc(); if(failAfter>0)--failAfter; ++allocations; void* p=malloc(n?n:1); if(!p)throw std::bad_alloc(); return p; }
void operator delete(void* p) noexcept { free(p); }
void operator delete(void* p,size_t) noexcept { free(p); }
'''
            code = prefix + text + '\n' + stubs + '\n' + fixture
            with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as temp:
                folder = Path(temp); source = folder / 'contract.cpp'; exe = folder / 'contract.exe'
                source.write_text(code)
                command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2', '/fp:precise',
                           '/DF3DEX_GBI_2', '/DNOMINMAX', '/DIMPROVED=' + str(int(improved))]
                command += ['/I' + str(ROOT / p) for p in ('soh/soh', 'soh', 'soh/include', 'libultraship/include',
                            'platform/shipyard', 'scratch/resources-xdk/generated/include',
                            'scratch/binary-xdk/generated/include')]
                command += ['/I' + str(PLATFORM_BASE / 'sources')]
                built = subprocess.run(command + [str(source), '/Fe:' + str(exe)], cwd=folder,
                                       env=env, capture_output=True, text=True)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                run = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                outputs.append(run.stdout.split('counts')[0])
                print(label + ' ' + run.stdout.strip())
        self.assertEqual(outputs, [outputs[0]] * len(outputs))


if __name__ == '__main__':
    unittest.main()
