"""Read-only metadata profile of the extracted Djipi MPQ archives."""
from collections import Counter, defaultdict
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[3]
MODS = ROOT / 'scratch/runtime/3Shipsty/mods/djipi_s_3ds_experience_tot_fix'


def main():
    archives = sorted(MODS.glob('*.otr'))
    if not archives:
        raise RuntimeError('Extracted MPQ folder is absent')
    compiler, environment = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    host = ROOT / 'scratch/stormlib-xdk/host'
    binary = host / 'profile-mpq-catalog.exe'
    source = Path(__file__).with_suffix('.cpp')
    command = [str(compiler), '/nologo', '/EHsc', '/MD', '/DSTORMLIB_NO_AUTO_LINK',
               '/I' + str(ROOT / 'scratch/stormlib-xdk/generated/src'), str(source),
               str(host / 'storm.lib'), str(ROOT / 'scratch/libzip-xdk/host/zlib.lib'),
               'user32.lib', '/Fe:' + str(binary), '/Fo:' + str(host) + '/']
    subprocess.run(command, cwd=host, env=environment, check=True, capture_output=True, text=True)
    output = subprocess.run([str(binary), *map(str, archives)], cwd=host, env=environment,
                            check=True, capture_output=True, text=True, timeout=120).stdout
    names = defaultdict(list)
    count = Counter()
    raw = Counter()
    compressed = Counter()
    for line in output.splitlines():
        archive, size, packed, name = line.split('\t', 3)
        index = int(archive)
        count[index] += 1
        raw[index] += int(size)
        compressed[index] += int(packed)
        names[name.lower()].append(index)
    for index, path in enumerate(archives):
        print(f'{index:2d} {count[index]:6d} {raw[index]:12d} {compressed[index]:12d} {path.name}')
    duplicate = {name: locations for name, locations in names.items() if len(locations) > 1}
    print(f'archives={len(archives)} records={sum(count.values())} unique={len(names)} '
          f'overlapping_names={len(duplicate)} raw_bytes={sum(raw.values())}')
    for name, locations in sorted(duplicate.items(), key=lambda item: len(item[1]), reverse=True)[:25]:
        print(f'overlap {locations}: {name}')


if __name__ == '__main__':
    main()
