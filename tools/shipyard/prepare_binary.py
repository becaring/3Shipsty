"""Project owned pinned LUS binarytools into XDK-compatible source; never edit upstream.

The explicit transforms are adapted from the read-only Smash360 binary generator;
provenance and semantic differences are recorded in platform/shipyard/binary.
Locks hash UTF-8 text after BOM removal and CRLF-to-LF normalization, allowing
normal Git checkout newline differences without accepting source changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
COMMIT = 'fdcaf6336776d24a6408d016b0a52243f108f250'
INPUTS = {'include/ship/utils/binarytools/BinaryWriter.h': 'bf37667f3e438c1ab0e42a23c72c222ddde6800b774e1ea27bd376a110a9b66a',
 'include/ship/utils/binarytools/BinaryReader.h': '46405096528e34f312c650e83e83d215216184ffb5b98db9d31f8354d9376d03',
 'include/ship/utils/binarytools/MemoryStream.h': '806e12c9c18bd2fe14d52a87bca781da94ac377e75183a8080d8278fb2f0cc65',
 'include/ship/utils/binarytools/Stream.h': 'dfcbfc93989d71ea12306c7b576810ee1714782d1468ba3417695900f9b2afad',
 'include/ship/utils/binarytools/endianness.h': '459a76b1b81cbffdca3005e9ed0ef6712af0e893cc0587aa447adccee508a7f7',
 'src/ship/utils/binarytools/BinaryWriter.cpp': 'f2805a7f5cfd9ae691b6341ae1f88bb6d6a66a8056a43593df396f184db40975',
 'src/ship/utils/binarytools/BinaryReader.cpp': '0060874646084935b1c7de52486ea16968c3866ca6abfb0311c2804ed37f16ac',
 'src/ship/utils/binarytools/MemoryStream.cpp': 'b39db54658c4b8c923082c48846118f02f0f75a7b31eb01641578d0c53fb92f8',
 'src/ship/utils/binarytools/Stream.cpp': '6a9574c06b0fad06d48a564d221918a1a2eb8ae3b3559824482f8c14f1dfc185'}
HELPERS = {'compat.h': '9128a141d3e66943e1dd40a2788884fb0b6318aa107ee4a1b3178bce124ba51e',
 'endian.h': '4fc6b78cdd0ede693acdbddde7bc5a6ffae6d77e79835a34463f16d5e12c8784'}
HELPER_PATHS = {'compat.h': PLATFORM_BASE / 'sources/binary/compat.h',
                'endian.h': ROOT / 'platform/shipyard/binary/endian.h'}
NATIVE_CONDITION = '#if (defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)) || defined(__BIG_ENDIAN__)\n'
XDK_NATIVE_CONDITION = '#if SHIPYARD_BIG_ENDIAN\n'

class Edits:
    def __init__(self, text, path):
        self.text, self.path, self.edits = text, path, []

    def exact(self, before, after, count=1):
        if self.text.count(before) != count:
            raise ValueError(f'{self.path}: expected {count} occurrences of {before!r}')
        if not before.endswith('\n') or not after.endswith('\n'):
            raise ValueError('edits must end at line boundaries')
        pos = 0
        for _ in range(count):
            start = self.text.index(before, pos)
            if start and self.text[start - 1] != '\n':
                raise ValueError('edits must begin at line boundaries')
            end = start + len(before)
            self.edits.append((start, end, after))
            pos = end

    def render(self):
        path = self.path.as_posix().replace('"', '\\"')
        output = ['// Generated from hash-locked LUS source; do not edit.\n']
        guard = 'SHIPYARD_GENERATED_BINARYTOOLS_' + self.path.name.upper().replace('.', '_')
        if self.path.suffix == '.h':
            # XDK does not reliably deduplicate #pragma once after #line remaps
            # the header filename. A physical-file guard precedes the mapping.
            output.append(f'#ifndef {guard}\n#define {guard}\n')
        output.append(f'#line 1 "{path}"\n')
        cursor = 0
        for start, end, replacement in sorted(self.edits):
            if start < cursor:
                raise ValueError(f'{self.path}: overlapping transformations')
            output.append(self.text[cursor:start])
            output.append(replacement)
            output.append(f'#line {self.text.count(chr(10), 0, end) + 1} "{path}"\n')
            cursor = end
        output.append(self.text[cursor:])
        if self.path.suffix == '.h':
            output.append(f'\n#endif // {guard}\n')
        return ''.join(output).encode('utf-8')


def strong_enum(name, body):
    return (f'struct {name} : public Shipyard::Binary::ScopedEnum<{name}> {{\n'
            f'    enum Value {{{body}\n    }};\n'
            f'    {name}() {{}}\n'
            f'    {name}(Value value) : Shipyard::Binary::ScopedEnum<{name}>(value) {{}}\n'
            f'    explicit {name}(int value) : Shipyard::Binary::ScopedEnum<{name}>(value) {{}}\n'
            '};\n')


def transform(relative, raw, path):
    text = raw.decode('utf-8').replace('\r\n', '\n')
    edits = Edits(text, path)
    if relative.endswith('/endianness.h'):
        edits.exact('#pragma once\n', '#pragma once\n#include \"binary/endian.h\"\n')
        original = ('enum class Endianness {\n    Little = 0,\n    Big = 1,\n\n' + NATIVE_CONDITION +
                    '    Native = Big,\n#else\n    Native = Little,\n#endif\n};\n')
        body = '\n    Little = 0,\n    Big = 1,\n\n' + XDK_NATIVE_CONDITION + '    Native = Big,\n#else\n    Native = Little,\n#endif'
        edits.exact(original, strong_enum('Endianness', body))
        # This C-compatible header is also included through functions.h's
        # extern-C region. Its scoped-enum helper must retain C++ linkage.
        edits.exact('#ifdef __cplusplus\n', '#ifdef __cplusplus\nextern "C++" {\n#include "binary/compat.h"\n')
        edits.exact('} // namespace Ship\n#endif\n', '} // namespace Ship\n} // extern C++\n#endif\n')
        # The second endian condition controls BE/LE swap macros, outside the enum.
        before = NATIVE_CONDITION + '#ifndef IS_BIGENDIAN\n'
        edits.exact(before, XDK_NATIVE_CONDITION + '#ifndef IS_BIGENDIAN\n')
    elif relative.endswith('/Stream.h'):
        edits.exact('#include <vector>\n', '#include <vector>\n#include "binary/compat.h"\n')
        edits.exact('enum class SeekOffsetType { Start, Current, End };\n',
                    strong_enum('SeekOffsetType', ' Start, Current, End'))
        edits.exact('    virtual ~Stream() = default;\n', '    virtual ~Stream() {}\n')
    elif relative.endswith('/MemoryStream.h'):
        edits.exact('class MemoryStream final : public Stream {\n', 'class MemoryStream : public Stream {\n')
        lines = [line for line in text.splitlines(keepends=True) if ' override;' in line]
        if len(lines) != 10:
            raise ValueError('unexpected MemoryStream override declarations')
        for line in lines:
            edits.exact(line, line.replace(' override;', ';'))
    elif relative.endswith(('/BinaryReader.h','/BinaryWriter.h')):
        edits.exact('    Endianness mEndianness = Endianness::Native;\n', '    Endianness mEndianness;\n')
    elif relative.endswith('/BinaryWriter.cpp'):
        for signature in ('', 'Stream* nStream', 'std::shared_ptr<Stream> nStream'):
            before = f'Ship::BinaryWriter::BinaryWriter({signature}) {{\n'
            edits.exact(before, f'Ship::BinaryWriter::BinaryWriter({signature}) : mEndianness(Endianness::Native) {{\n')
        edits.exact('    for (char c : str) {\n', '    for (std::string::const_iterator i = str.begin(), end = str.end(); i != end; ++i) {\n        char c = *i;\n')
    elif relative.endswith('/BinaryReader.cpp'):
        for signature in ('char* nBuffer, size_t nBufferSize', 'Stream* nStream', 'std::shared_ptr<Stream> nStream'):
            before = f'Ship::BinaryReader::BinaryReader({signature}) {{\n'
            edits.exact(before, f'Ship::BinaryReader::BinaryReader({signature}) : mEndianness(Endianness::Native) {{\n')
        edits.exact('    float result = NAN;\n', '    float result = Shipyard::Binary::QuietNaN();\n')
        edits.exact('    double result = NAN;\n', '    double result = Shipyard::Binary::QuietNaN();\n')
        edits.exact('    if (std::isnan(result)) {\n', '    if (Shipyard::Binary::IsNaN(result)) {\n', 2)
    elif relative.endswith('/MemoryStream.cpp'):
        default_body = ('    mBuffer = std::make_shared<std::vector<char>>();\n'
                        '    // mBuffer.reserve(1024 * 16);\n'
                        '    mBufferSize = 0;\n    mBaseAddress = 0;\n')
        if f'Ship::MemoryStream::MemoryStream() {{\n{default_body}}}\n' not in text:
            raise ValueError('default MemoryStream constructor changed')
        for signature in ('char* nBuffer, size_t nBufferSize', 'std::shared_ptr<std::vector<char>> buffer'):
            before = f'Ship::MemoryStream::MemoryStream({signature}) : MemoryStream() {{\n'
            # Exact original default body executes before the original delegating
            # constructor body, including the temporary empty-buffer allocation.
            edits.exact(before, f'Ship::MemoryStream::MemoryStream({signature}) {{\n' + default_body)
        edits.exact('    std::unique_ptr<char[]> result = std::make_unique<char[]>(length);\n',
                    '    std::unique_ptr<char[]> result = Shipyard::Binary::MakeZeroedChars(length);\n')
    elif not relative.endswith('/Stream.cpp'):
        raise ValueError(f'unrecognized input {relative}')
    return edits.render(), len(edits.edits)


def normalized(raw):
    return raw.decode('utf-8-sig').replace('\r\n', '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def generate(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not destination.is_relative_to((ROOT / 'scratch/binary-xdk').resolve()):
        raise ValueError('output must remain under owned scratch/binary-xdk')
    # Validate every source/helper and prepare every transform before writing.
    prepared = []
    for name, expected in HELPERS.items():
        raw = normalized(HELPER_PATHS[name].read_bytes())
        if digest(raw) != expected:
            raise ValueError('helper SHA-256 mismatch: ' + name)
    for relative, expected in INPUTS.items():
        raw = normalized((source / relative).read_bytes())
        if digest(raw) != expected:
            raise ValueError('source SHA-256 mismatch: ' + relative)
        output, edits = transform(relative, raw, Path('libultraship') / relative)
        prepared.append((relative, output, {'normalized_input_sha256': expected,
                         'output_sha256': digest(output), 'edits': edits}))
    manifest = {'libultraship_commit': COMMIT, 'source_root': 'libultraship',
                'generator_sha256': digest(normalized(Path(__file__).read_bytes())),
                'helper_sha256': HELPERS, 'compat_header_source': 'platform_base:sources/binary/compat.h',
                'normalization': 'UTF-8, optional BOM removed, CRLF -> LF',
                'files': {relative: metadata for relative, _, metadata in prepared}}
    for relative, output, _ in prepared:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != output:
            target.write_bytes(output)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'libultraship')
    parser.add_argument('--output', type=Path, default=ROOT / 'scratch/binary-xdk/generated')
    args = parser.parse_args()
    result = generate(args.source, args.output)
    print('Generated %d pinned modern LUS binarytools files' % len(result['files']))


if __name__ == '__main__':
    main()
