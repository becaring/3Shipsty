"""Compare actual pinned and projected ImGui draw data, not a replacement GUI."""
import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/imgui-xdk'
UNITS = ('imgui', 'imgui_draw', 'imgui_widgets', 'imgui_tables', 'imgui_demo')


def main():
    compiler, env = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    results = {}
    for label in ('original', 'generated'):
        folder = OUT / ('host-' + label); folder.mkdir(parents=True, exist_ok=True)
        command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2',
                   '/I' + str(OUT / label), '/Fe:' + str(folder / 'contract.exe'), '/Fo:' + str(folder) + '/',
                   str(Path(__file__).with_name('test_imgui_contract.cpp'))]
        command += [str(OUT / label / (unit + '.cpp')) for unit in UNITS]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        (folder / 'compile.log').write_text(result.stdout + result.stderr)
        if result.returncode: raise RuntimeError('Host ImGui build failed: ' + label)
        result = subprocess.run([str(folder / 'contract.exe')], cwd=folder, env=env, capture_output=True, text=True)
        results[label] = dict(exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode: raise RuntimeError('Host ImGui contract failed: ' + label)
    (OUT / 'verification.json').write_text(json.dumps(dict(host=results, target_runtime_executed=False), indent=2) + '\n')
    if results['original'] != results['generated']: raise AssertionError('ImGui draw data differs')
    print('Original/projected fonts, draw vertices, indices, clipping and command offsets match over eight frames')


if __name__ == '__main__': main()
