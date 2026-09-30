"""Prebuilt shader pack: exact ports and format parity with the runtime.

  * shader_pack_keys.generate_cc against the projected interpreter's GenerateCC;
  * shader_pack_harvest.crc64 against libultraship StrHash64.cpp;
  * the display-list simulator on a synthetic OTR resource;
  * pack digests/checksums and a written pack against Shipyard shader_pack.h.
"""
import random
import runpy
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / 'tools/shipyard'
sys.path.insert(0, str(TOOLS))
import build_shader_pack as pack
import shader_pack_harvest as harvest
import shader_pack_keys as keys

INTERPRETER = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'


def build_and_run(folder, source, includes=(), extra=(), flags=(), stdin=''):
    env = runpy.run_path(str(TOOLS / 'tests/test_binary.py'))
    compiler, environment = env['host_environment']()
    path = folder / 'harness.cpp'
    path.write_text(source, encoding='utf-8')
    executable = folder / 'harness.exe'
    env['invoke']([compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2'] + list(flags) +
                  ['/I' + str(p) for p in includes] + [path] + list(extra) + ['/Fe:' + str(executable)],
                  folder, 'build', environment)
    import subprocess
    result = subprocess.run([str(executable)], input=stdin, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


class ShaderPackTests(unittest.TestCase):
    def test_generate_cc_matches_interpreter(self):
        runpy.run_path(str(TOOLS / 'prepare_fast3d.py'))['prepare']()
        runpy.run_path(str(TOOLS / 'prepare_graphics.py'))['prepare']()
        text = INTERPRETER.read_text(encoding='utf-8', errors='replace')
        start = text.index('void Interpreter::GenerateCC(ColorCombiner* comb, const ColorCombinerKey& key) {')
        end = text.index('\n}\n', start) + 3
        body = text[start:end].replace('void Interpreter::GenerateCC(', 'static void GenerateCC(', 1)
        source = ('#include <cstdint>\n#include <cstdio>\n#include <cstring>\n#include <iostream>\n'
                  '#include "libultraship/libultra/gbi.h"\n#include "fast/cc_features.h"\n'
                  'struct ColorCombinerKey { uint64_t combine_mode; uint64_t options; };\n'
                  'struct ColorCombiner { uint64_t shader_id0; uint32_t shader_id1; bool usedTextures[2];\n'
                  '    uint8_t shader_input_mapping[2][7]; };\n' + body +
                  'int main() {\n    unsigned long long mode, opts;\n'
                  '    while (std::cin >> std::hex >> mode >> opts) {\n'
                  '        ColorCombiner comb = {}; ColorCombinerKey key = {mode, opts}; GenerateCC(&comb, key);\n'
                  '        std::printf("%016llx %08x %d %d\\n", (unsigned long long)comb.shader_id0, comb.shader_id1,\n'
                  '                    comb.usedTextures[0] ? 1 : 0, comb.usedTextures[1] ? 1 : 0);\n    }\n}\n')
        rng = random.Random(9250)
        cases = [(keys.COPY_COMBINE, 0), (keys.FILL_COMBINE, keys.OPT_ALPHA)]
        for _ in range(4000):
            cases.append((rng.getrandbits(56), rng.getrandbits(8)))
        stdin = ''.join('%x %x\n' % case for case in cases)
        with tempfile.TemporaryDirectory() as folder:
            output = build_and_run(Path(folder), source,
                                   includes=[ROOT / 'libultraship/include', ROOT / 'scratch/graphics-xdk/include'],
                                   flags=['/DF3DEX_GBI_2'], stdin=stdin).split('\n')
        for (mode, opts), line in zip(cases, output):
            id0, id1, used0, used1 = keys.generate_cc(mode, opts)
            self.assertEqual(line.strip(), '%016x %08x %d %d' % (id0, id1, used0, used1), hex(mode))

    def test_crc64_matches_libultraship(self):
        names = ['objects/object_link_boy/gLinkAdultSkel', 'scenes/shared/spot04_scene/spot04_scene', '', 'a']
        source = ('#include <cstdint>\n#include <cstdio>\nextern uint64_t CRC64(const char*);\n'
                  'int main() {\n' + ''.join('    std::printf("%%016llx\\n", (unsigned long long)CRC64("%s"));\n' % n
                                             for n in names) + '}\n')
        with tempfile.TemporaryDirectory() as folder:
            output = build_and_run(Path(folder), source, includes=[ROOT / 'libultraship/include'],
                                   extra=[ROOT / 'libultraship/src/ship/utils/StrHash64.cpp']).split()
        self.assertEqual(output, ['%016x' % harvest.crc64(n) for n in names])

    def test_display_list_simulation(self):
        def command(op, w0=0, w1=0):
            return struct.pack('<II', (op << 24) | w0, w1)

        def resource(body):
            header = bytearray(64)
            struct.pack_into('<I', header, 4, harvest.DISPLAY_LIST)
            return bytes(header) + bytes([harvest.UCODE_F3DEX2]) + bytes(7) + body

        child_name = 'objects/test/child'
        child = resource(command(harvest.G_TRI1) + command(harvest.G_ENDDL))
        combine = keys.combine_mode(keys.color_comb(keys.G_CCMUX_TEXEL0, keys.G_CCMUX_0, keys.G_CCMUX_SHADE, 0),
                                    keys.alpha_comb(0, 0, 0, keys.G_ACMUX_SHADE))
        # SETCOMBINE fields per gfx_set_combine_handler_rdp's decode.
        rgb, alpha = combine & 0xFFFF, (combine >> 16) & 0xFFF
        w0 = ((rgb & 0xF) << 20) | (((rgb >> 8) & 0x1F) << 15) | ((alpha & 7) << 12) | (((alpha >> 6) & 7) << 9)
        w1 = (((rgb >> 4) & 0xF) << 28) | (((rgb >> 13) & 7) << 15) | (((alpha >> 3) & 7) << 12) | ((alpha >> 9) & 7) << 9
        self.assertEqual(harvest.decode_combine(w0, w1) & 0xFFFFFFF, combine & 0xFFFFFFF)
        crc = harvest.crc64(child_name)
        parent = resource(command(harvest.G_SETCOMBINE, w0, w1) +
                          command(harvest.G_SETTILE, 0, (2 << 8) | (1 << 18)) +
                          command(harvest.G_TEXTURE, 0, 0) +
                          command(harvest.G_DL_OTR_HASH) + struct.pack('<II', crc >> 32, crc & 0xFFFFFFFF) +
                          command(harvest.G_ENDDL))
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'test.o2r'
            with zipfile.ZipFile(archive, 'w') as out:
                out.writestr('objects/test/parent', parent)
                out.writestr(child_name, child)
            lists, records = harvest.display_list_records([archive], 2)
        self.assertEqual(lists, 2)
        tri = [r for r in records if r[0] == 'tri']
        # One draw inherits the parent's combine and clamp-only tile; the
        # child alone has unknown state.
        self.assertIn(('tri', harvest.decode_combine(w0, w1), 0, 0, 0, (2, 1), None, False), tri)
        self.assertIn(('tri', None, 0, 0, 0, None, None, False), tri)
        found = keys.shader_keys(harvest.decode_combine(w0, w1), 0, False, 0, {0: (2, 1)})
        self.assertEqual(len(found), 2)  # clamped S without mirror: both size outcomes

    def test_pack_matches_shipyard_header(self):
        rng = random.Random(3)
        programs = {}
        for i in range(64):
            key = (rng.getrandbits(64), rng.getrandbits(32), rng.randrange(0, 4))
            source = ('// shader %d\n' % i + 'x' * rng.randrange(0, 9000)).encode()
            programs[key] = (rng.randrange(4, 40), bytes(rng.getrandbits(8) for _ in range(4 * rng.randrange(1, 300))),
                             bytes(rng.getrandbits(8) for _ in range(4 * rng.randrange(1, 300))), source)
        # Shared microcode is stored once.
        first = next(iter(programs))
        shared = (first[0], first[1] ^ 1, first[2])
        programs[shared] = (5, programs[first][1], programs[first][2], b'shared')
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / 'test.shaderpack'
            count, blobs, size = pack.write_pack(programs, path)
            self.assertEqual((count, blobs), (len(programs), 2 * len(programs) - 2))
            listing = folder / 'programs.txt'
            with open(listing, 'w', encoding='ascii') as out:
                for (id0, id1, flags), (floats, vertex, pixel, _) in programs.items():
                    out.write('%016x %08x %u %u %08x %08x\n' % (id0, id1, flags, floats,
                                                             zlib.crc32(vertex) & 0xFFFFFFFF,
                                                             zlib.crc32(pixel) & 0xFFFFFFFF))
            probe = folder / 'probe.hlsl'
            probe.write_bytes(programs[min(programs)][3])
            source = r'''#include "xenos/shader_pack.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
using namespace Shipyard::Xenos;
static std::vector<unsigned char> Read(const char* path) {
    std::ifstream file(path, std::ios::binary);
    return std::vector<unsigned char>(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}
int main(int, char** argv) {
    std::vector<unsigned char> pack = Read(argv[1]), probe = Read(argv[3]);
    if (ShaderPackRead32(&pack[0]) != ShaderPackMagic || ShaderPackRead32(&pack[4]) != ShaderPackVersion) return 2;
    const uint32_t count = ShaderPackRead32(&pack[16]);
    std::vector<ShaderPackProgram> index;
    for (uint32_t i = 0; i < count; ++i) {
        index.push_back(ShaderPackParseProgram(&pack[ShaderPackHeaderBytes + i * ShaderPackEntryBytes]));
        const ShaderPackProgram& e = index.back();
        if (i && !ShaderPackBefore(index[i - 1].shaderId0, index[i - 1].shaderId1, index[i - 1].flags,
                                   e.shaderId0, e.shaderId1, e.flags)) return 3;
        // The runtime's per-entry check (shader_cache.cpp Intact).
        unsigned char head[20];
        for (int b = 0; b < 8; ++b) head[b] = (unsigned char)(e.shaderId0 >> (56 - 8 * b));
        const uint32_t fields[3] = {e.shaderId1, e.flags, e.floats};
        for (int f = 0; f < 3; ++f)
            for (int b = 0; b < 4; ++b) head[8 + f * 4 + b] = (unsigned char)(fields[f] >> (24 - 8 * b));
        uint32_t crc = ShaderPackChecksum(head, sizeof(head));
        crc = ShaderPackChecksum(&pack[e.vertexOffset], e.vertexSize, crc);
        crc = ShaderPackChecksum(&pack[e.pixelOffset], e.pixelSize, crc);
        if (crc != e.checksum || (e.vertexOffset & 3) || (e.pixelOffset & 3)) return 4;
    }
    const uint32_t probeIndex = ShaderPackRead32(&pack[20]);
    unsigned char digest[32];
    ShaderPackSha256(std::string(probe.begin(), probe.end()), digest);
    if (probeIndex >= count || memcmp(digest, &pack[32], 32)) return 5;
    unsigned found = 0;
    std::ifstream listing(argv[2]);
    unsigned long long id0;
    unsigned id1, flags, floats, vertexCrc, pixelCrc;
    while (listing >> std::hex >> id0 >> id1 >> std::dec >> flags >> floats >> std::hex >> vertexCrc >> pixelCrc) {
        size_t i = 0;
        while (i < count && !(index[i].shaderId0 == id0 && index[i].shaderId1 == id1 && index[i].flags == flags)) ++i;
        if (i == count || index[i].floats != floats ||
            ShaderPackChecksum(&pack[index[i].vertexOffset], index[i].vertexSize) != vertexCrc ||
            ShaderPackChecksum(&pack[index[i].pixelOffset], index[i].pixelSize) != pixelCrc) return 6;
        ++found;
    }
    std::printf("%u\n", found);
    return found == count ? 0 : 7;
}
'''
            env = runpy.run_path(str(TOOLS / 'tests/test_binary.py'))
            compiler, environment = env['host_environment']()
            (folder / 'reader.cpp').write_text(source, encoding='utf-8')
            platform_base = runpy.run_path(str(TOOLS / 'platform_base.py'))['resolve'](ROOT)
            env['invoke']([compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2',
                           '/I' + str(platform_base / 'sources'), folder / 'reader.cpp',
                           '/Fe:' + str(folder / 'reader.exe')], folder, 'build', environment)
            result = env['invoke']([folder / 'reader.exe', path, listing, probe], folder, 'run', environment)
            self.assertEqual(result['stdout'].strip(), str(len(programs)))


if __name__ == '__main__':
    unittest.main()
