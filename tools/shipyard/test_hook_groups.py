"""Run original and projected hook headers without changing selected outputs."""
import runpy
import subprocess
import json
import re
import struct
from prepare_game_interactor import ROOT, BASE, OUT, header, call_sites, includes, syntax


def main():
    out = ROOT / 'scratch/hook-groups'
    out.mkdir(exist_ok=True)
    compiler, env = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))['host_environment']()
    original = (ROOT / BASE / 'GameInteractor.h').read_text()
    table = (ROOT / BASE / 'GameInteractor_HookTable.h').read_text()
    arguments = re.findall(r'^DEFINE_HOOK\(\w+, \((.*?)\)\);', table, re.M)
    arity = max(0 if not arg.strip() else len(arg.split(',')) for arg in arguments)
    body = (ROOT / 'platform/shipyard/game-interactor/missing_group_contract.cpp').read_text()
    for projected in (False, True):
        folder = out / ('projected' if projected else 'original')
        folder.mkdir(exist_ok=True)
        text = syntax(header(original, arity)) if projected else original.replace(
            '#include "libultraship/libultraship.h"', '#include <libultraship/bridge.h>\n#include <string>')
        (folder / 'GameInteractor.h').write_text(text)
        source = call_sites(body, 'platform/shipyard/game-interactor/missing_group_contract.cpp') if projected else body
        (folder / 'contract.cpp').write_text(source)
        command = [str(compiler), '/nologo', '/std:c++20', '/utf-8', '/EHsc', '/GR', '/MD',
                   '/DNOMINMAX', '/DF3DEX_GBI_2', '/DCONTROLLERBUTTONS_T=uint32_t',
                   '/DEXPECT_EMPTY_GROUPS=' + ('0' if projected else '1000')]
        if not projected:
            command += ['/Zc:preprocessor']
        command += ['/I' + str(p) for p in [folder, ROOT / BASE] + includes()]
        command += [str(folder / 'contract.cpp'), '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')]
        result = subprocess.run(command, cwd=out, env=env, capture_output=True, text=True)
        (folder / 'build.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        result = subprocess.run([str(folder / 'contract.exe')], cwd=out, capture_output=True, text=True)
        (folder / 'run.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        print(folder.name + ': ' + result.stdout.strip())
    recipe = json.loads((OUT / 'xdk/build.json').read_text())[0]['command'][:-2]
    command = recipe + ['/I' + str(ROOT / BASE), '/DEXPECT_EMPTY_GROUPS=0', str(folder / 'contract.cpp'), '/Fo' + str(out / 'contract.obj')]
    result = subprocess.run(command, cwd=out, capture_output=True, text=True)
    (out / 'native-build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert struct.unpack_from('<H', (out / 'contract.obj').read_bytes())[0] == 0x1f2
    print('1000 distinct absent ID/Ptr dispatches: outer group insertions 1000 -> 0 each')


if __name__ == '__main__':
    main()
