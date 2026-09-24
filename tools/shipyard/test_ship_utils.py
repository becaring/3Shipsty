"""Full-TU native coverage and exact original/projected utility RNG contracts."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from prepare_ship_utils import ROOT, OUT, OWN, SOURCES, build, project, sha
from cpp_ast import PARSER, walk

ENV = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))


def symbols(path):
    import struct
    raw = path.read_bytes()
    _, _, _, offset, count, _, _ = struct.unpack_from('<HHIIIHH', raw)
    strings = offset + count * 18; result = {}; i = 0
    while i < count:
        start = offset + i * 18
        if raw[start:start + 4] == b'\0' * 4:
            text = strings + struct.unpack_from('<I', raw, start + 4)[0]
            name = raw[text:raw.index(b'\0', text)].decode()
        else:
            name = raw[start:start + 8].rstrip(b'\0').decode()
        _, section, _, storage, aux = struct.unpack_from('<IhHBB', raw, start + 8)
        if storage == 2:
            result[name] = section
        i += aux + 1
    return result


def host(projected):
    folder = OUT / ('host-projected' if projected else 'host-original'); folder.mkdir(parents=True, exist_ok=True)
    base = OUT / 'generated'
    if not projected:
        base = folder / 'source'
        for name in SOURCES:
            text = (ROOT / name).read_text()
            if name.endswith('ShipUtils.h'):
                text = text.replace('#include <libultraship/libultraship.h>',
                    '#include <libultraship/libultra.h>\n#include <array>\n#include <vector>\n#include <set>\n#include <utility>\n#include <iterator>')
            elif name.endswith('ShipUtils.cpp'):
                text = text.replace('#include <libultraship/libultraship.h>',
                    '#include <libultraship/bridge/consolevariablebridge.h>\n#include <ship/utils/binarytools/endianness.h>')
            path = base / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    compiler, env = ENV['host_environment']()
    platform_base = (ROOT / json.loads((ROOT / 'platform-base.lock.json').read_text())['base']).resolve()
    inc = [base / 'soh', ROOT / 'soh', ROOT / 'soh/include', ROOT / 'soh/assets', ROOT / 'libultraship/include',
           ROOT / 'platform/shipyard/json/upstream/include', ROOT / 'platform/shipyard', platform_base / 'sources']
    command = [compiler, '/nologo', '/std:c++20', '/Zc:preprocessor', '/EHsc', '/GR', '/MD', '/Gy', '/O2', '/DNOMINMAX',
               '/DF3DEX_GBI_2', '/DCONTROLLERBUTTONS_T=uint32_t', '/FIbit', '/FIcassert', '/FIcmath']
    command += ['/I' + str(p) for p in inc]
    # Compile both full production TUs on the host as well as XDK. Runtime
    # contracts use exact self-contained methods because actor/font functions
    # genuinely require the linked game/CVar/OTR providers; no substitutes link.
    full_folder = folder / 'full'; full_folder.mkdir(exist_ok=True)
    full = command + ['/c', base / SOURCES[1], base / SOURCES[3], '/Fo:' + str(full_folder) + '/']
    record = ENV['invoke'](full, folder, 'full-objects', env, success=False)
    if record['returncode']:
        raise AssertionError('\n'.join(s for s in (record['stdout'] + record['stderr']).splitlines() if 'error ' in s)[:4500])
    (folder / 'full-object-receipt.json').write_text(json.dumps({n: dict(
        source_sha256=hashlib.sha256((base / n).read_bytes()).hexdigest(),
        object_sha256=hashlib.sha256((full_folder / (Path(n).stem + '.obj')).read_bytes()).hexdigest())
        for n in (SOURCES[1], SOURCES[3])}, indent=2) + '\n')
    source = (base / SOURCES[1]).read_text()
    functions = [n for n in walk(PARSER.parse(source.encode()).root_node)
                 if n.type == 'function_definition' and any(key in n.child_by_field_name('declarator').text.decode()
                     for key in ('Ship_IsCStringEmpty(', 'Ship_CreateQuadVertexGroup('))]
    if len(functions) != 2:
        raise AssertionError('Utility leaf method inventory changed')
    runtime = '#include "soh/ShipUtils.h"\n#include <random>\n#include <bit>\n#include <cassert>\n#include <cmath>\n'
    runtime += '\n'.join(n.text.decode() for n in functions) + '\n' + source[source.index('static bool default_init = false;'):]
    (folder / 'runtime.cpp').write_text(runtime)
    (folder / 'runtime-scope.json').write_text(json.dumps(dict(source=SOURCES[1],
        leaf_methods=[n.child_by_field_name('declarator').text.decode() for n in functions],
        rng='Complete state declarations and all four RNG methods; exact source tail',
        runtime_sha256=sha(runtime)), indent=2) + '\n')
    command += [folder / 'runtime.cpp', base / SOURCES[3], OWN / 'contract.cpp']
    if projected:
        command += [OWN / 'native_entropy.cpp', '/DSHIPYARD_UTILS_PROJECTED']
    command += ['/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe'), '/link', '/OPT:REF']
    record = ENV['invoke'](command, folder, 'build', env, success=False)
    if record['returncode']:
        raise AssertionError('\n'.join(s for s in (record['stdout'] + record['stderr']).splitlines() if 'error ' in s)[:4500])
    record = ENV['invoke']([folder / 'contract.exe'], folder, 'run')
    return record['stdout']


class ShipUtilsContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()

    def test_source_hashes_and_all_functions(self):
        manifest = json.loads((OUT / 'manifest.json').read_text())
        for name in SOURCES:
            original = (ROOT / name).read_text()
            projected = (OUT / 'generated' / name).read_text()
            self.assertEqual(sha(original), manifest['sources'][name])
            self.assertEqual(sha(projected), manifest['generated'][name])
            if name.endswith('.cpp'):
                def signatures(text):
                    return [n.child_by_field_name('declarator').text.decode() for n in walk(PARSER.parse(text.encode()).root_node)
                            if n.type == 'function_definition']
                self.assertEqual(signatures(original), signatures(projected))

    def test_native_objects(self):
        import struct
        rows = json.loads((OUT / 'xdk/build.json').read_text())
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(row['exit'], 0)
            self.assertEqual(hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest(), row['source_sha256'])
            raw = (OUT / 'xdk' / (Path(row['source']).stem + '.obj')).read_bytes()
            self.assertEqual(struct.unpack_from('<H', raw)[0], 0x1f2)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['object_sha256'])

    def test_full_host_seeded_and_container_contracts(self):
        original = host(False)
        projected = host(True)
        self.assertEqual(original, projected)
        (OUT / 'verification.json').write_text(json.dumps(dict(equal=True, stdout=original,
            full_host_objects=[SOURCES[1], SOURCES[3]], runtime_scope='Complete RNG state/functions, wrapper TU, C string and vertex methods; no fake services',
            original_adaptation='Only broad includes narrowed; real method bodies unchanged; standard bit/assert/math includes explicit',
            native_runtime_executed=False), indent=2) + '\n')

    def test_entropy_boundary(self):
        original = (ROOT / SOURCES[1]).read_text()
        projected = (OUT / 'generated' / SOURCES[1]).read_text()
        self.assertIn('static bool default_init = false;', projected)
        self.assertEqual(original.count('default_init = true;'), projected.count('default_init = true;'))
        boundary = (OWN / 'native_entropy.cpp').read_text()
        xbox = boundary[boundary.index('uint32_t Shipyard::Utils::DeviceRandom()'):].split('#else')[0]
        self.assertIn('Shipyard::Entropy::FillBytes(', xbox)
        base = (ROOT / json.loads((ROOT / 'platform-base.lock.json').read_text())['base']).resolve()
        provider = (base / 'sources/entropy/native.h').read_text()
        self.assertIn('XNetRandom(buffer, length)', provider)
        self.assertIn('throw std::runtime_error', xbox)
        self.assertNotIn('rand()', xbox)
        self.assertNotIn('time(', xbox)

    def test_native_real_interfaces_and_c_abi(self):
        utility = symbols(OUT / 'xdk/ShipUtils.obj')
        for name in ('Ship_GetExtendedAspectRatioMultiplier', 'Ship_ExtendedCullingActorAdjustProjectedZ',
                     'Ship_ExtendedCullingActorAdjustProjectedX', 'Ship_IsCStringEmpty', 'Ship_CreateQuadVertexGroup',
                     'Ship_GetCharFontWidth', 'Ship_GetCharFontTexture'):
            self.assertGreater(utility[name], 0)
        self.assertEqual(utility['CVarGetInteger'], 0)
        self.assertEqual(utility['OTRGetAspectRatio'], 0)
        self.assertEqual(symbols(OUT / 'xdk/native_entropy.obj')['XNetRandom'], 0)
        c = symbols(OUT / 'xdk/c_abi.obj')
        for name in ('Ship_GetExtendedAspectRatioMultiplier', 'Ship_CreateQuadVertexGroup', 'Ship_IsCStringEmpty'):
            self.assertEqual(c[name], 0)


if __name__ == '__main__':
    unittest.main()
