"""Read-only host check of a supplied OTR using the exact pinned StormLib."""
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/stormlib-xdk'

def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: test_stormlib_mod_read.py <owned OTR path>')
    archive = Path(sys.argv[1]).resolve(strict=True)
    if not archive.is_relative_to(ROOT):
        raise ValueError('Read-only OTR test requires an owned archive')
    compiler, env = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    folder = OUT / 'host'
    executable = folder / 'storm-mod-read.exe'
    command = [str(compiler), '/nologo', '/EHsc', '/MD', '/DSTORMLIB_NO_AUTO_LINK',
               '/I' + str(OUT / 'generated/src'),
               str(Path(__file__).with_suffix('.cpp')), str(folder / 'storm.lib'),
               str(ROOT / 'scratch/libzip-xdk/host/zlib.lib'), 'user32.lib',
               '/Fe:' + str(executable), '/Fo:' + str(folder) + '/']
    subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable), str(archive)], cwd=folder, env=env,
                            capture_output=True, text=True, timeout=20)
    print(result.stdout + result.stderr, end='')
    if result.returncode:
        raise RuntimeError('Read-only MPQ listfile read failed')

if __name__ == '__main__':
    main()
