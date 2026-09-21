"""Exercise the real codec libraries through the APIs used by current SoH."""
import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/codec-xdk'


def main():
    compiler, env = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    folder = OUT / 'host'
    command = [str(compiler), '/nologo', '/EHsc', '/MD', '/D_CRT_SECURE_NO_WARNINGS',
               '/I' + str(OUT / 'include'), '/I' + str(OUT / 'include/opus'),
               str(Path(__file__).with_name('test_codecs_contract.cpp')),
               *[str(folder / (name + '.lib')) for name in ('opusfile', 'opus', 'ogg')],
               '/Fe:' + str(folder / 'codec-contract.exe'), '/Fo:' + str(folder) + '/']
    result = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True)
    (folder / 'contract-build.log').write_text(result.stdout + result.stderr)
    if result.returncode: raise RuntimeError('See codec host/contract-build.log')
    result = subprocess.run([str(folder / 'codec-contract.exe'), str(folder / 'contract.opus')],
                            cwd=folder, capture_output=True, text=True)
    evidence = dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr,
                    target_runtime_executed=False)
    (OUT / 'verification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(result.stdout + result.stderr)
    if result.returncode: raise RuntimeError('Codec contract failed')


if __name__ == '__main__': main()
