"""Verify owned official/extracted O2R inputs without rewriting their formats."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'scratch/assets'
OFFICIAL = ASSETS / 'official-9.2.3'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inspect_archive(path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError('CRC failure: ' + bad)
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entry names')
        for name in names:
            if name.startswith(('/', '\\')) or '..' in Path(name).parts:
                raise ValueError('Unsafe archive path: ' + name)
        version = archive.read('portVersion')
        if len(version) != 7 or version[0] not in (0, 1):
            raise ValueError('Invalid portVersion record')
        endian = '<' if version[0] == 0 else '>'
        decoded = struct.unpack(endian + 'HHH', version[1:])
        if decoded != (9, 2, 3):
            raise ValueError('Archive does not match stable 9.2.3')
        kinds = Counter()
        examples = []
        for name in names:
            if name in ('version', 'portVersion') or name.endswith('/'):
                continue
            data = archive.read(name)
            if len(data) >= 64 and data[0] in (0, 1) and data[2:4] == b'\0\0':
                order = '<' if data[0] == 0 else '>'
                resource_type, resource_version = struct.unpack_from(order + 'II', data, 4)
                key = (data[0], resource_type, resource_version)
                kinds[key] += 1
                if not any(e['key'] == list(key) for e in examples):
                    examples.append(dict(path=name, key=list(key), size=len(data), header_hex=data[:64].hex()))
            else:
                kinds[('text-or-other', 0, 0)] += 1
        result = dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), entries=len(names),
                      port_version=list(decoded), port_version_hex=version.hex(),
                      categories=[dict(byte_order=k[0], resource_type=k[1], resource_version=k[2], count=v)
                                  for k, v in sorted(kinds.items(), key=lambda x: str(x[0]))], examples=examples)
        if 'version' in names:
            game = archive.read('version')
            if len(game) != 5 or game[0] not in (0, 1):
                raise ValueError('Unexpected game version record')
            result['rom_crc'] = hex(struct.unpack(('<' if game[0] == 0 else '>') + 'I', game[1:])[0])
        return result

def main():
    package = ASSETS / 'SoH-Ackbar-Delta-Win64.zip'
    expected = 'cc7bd5ada1332be50013976fc3db3289cacde1df57e7e6cf73d4a1df81313e30'
    if sha(package) != expected:
        raise ValueError('Official package hash differs from fetched baseline')
    rom = ASSETS / 'input.z64'
    rom_sha1 = hashlib.sha1(rom.read_bytes()).hexdigest()
    if rom_sha1 != 'cee6bc3c2a634b41728f2af8da54d9bf8cc14099':
        raise ValueError('Owned ROM differs from supplied input')
    report = dict(scope='PC archive structure and version verification; Xbox factory decoding unverified',
                  source_release='https://github.com/HarbourMasters/Shipwright/releases/tag/9.2.3',
                  package_sha256=expected, extractor_sha256=sha(OFFICIAL / 'soh.exe'),
                  rom_sha1=rom_sha1, archives=[inspect_archive(OFFICIAL / n) for n in ('soh.o2r', 'oot.o2r')])
    (ASSETS / 'archive-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for row in report['archives']:
        print(f"{row['path']}: {row['entries']} entries, version {row['port_version']}, CRCs pass, sha256 {row['sha256']}")

if __name__ == '__main__':
    main()
