"""Execute the actual interpolation scheduling block with counted vector storage."""
import json
import runpy
import subprocess
from prepare_application import ROOT, OUT, prepare, function
from prepare_archives import stable


def main():
    prepare()
    compiler, env = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))['host_environment']()
    records = []
    for label, source, allocation_limit in (
        ('original', ROOT / 'soh/soh/OTRGlobals.cpp', 3),
        ('projected', OUT / 'generated/soh/soh/OTRGlobals.cpp', 1),
    ):
        body = function(source.read_text(encoding='utf-8-sig'), 'Graph_ProcessGfxCommands').text.decode()
        start = body.index('    int next_original_frame = fps;')
        end = body.index('    time -= fps;', start) + len('    time -= fps;')
        block = body[start:end]
        fixture = (ROOT / 'platform/shipyard/application/frame_batch_contract.cpp').read_text()
        folder = ROOT / 'scratch/frame-batch' / label
        folder.mkdir(parents=True, exist_ok=True)
        stable(folder / 'contract.cpp', fixture.replace('// SCHEDULING_BLOCK', block))
        command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2',
                   '/DALLOCATION_LIMIT=' + str(allocation_limit), str(folder / 'contract.cpp'),
                   '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')]
        build = subprocess.run(command, env=env, cwd=folder, capture_output=True, text=True)
        stable(folder / 'build.log', build.stdout + build.stderr)
        assert build.returncode == 0, build.stdout + build.stderr
        result = subprocess.run([str(folder / 'contract.exe')], cwd=folder, capture_output=True, text=True)
        record = dict(label=label, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        records.append(record)
        stable(ROOT / 'scratch/frame-batch/verification.json', json.dumps(records, indent=2) + '\n')
        assert result.returncode == 0, str(record)
    print(records)


if __name__ == '__main__':
    main()
