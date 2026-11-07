"""Full declaration audits, native object build records, and bounded value differentials.

The method harness uses the complete class definitions with private test access.
It supplies no fake services and builds no substitute Rando::Context.
"""
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
import unittest
from prepare_randomizer import ROOT, OWN, OUT, BASE, CUSTOM, PARSER, walk, prepare, build, inventory, function_nodes
from platform_base import resolve as resolve_platform_base

ENV = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))
CLASS_INPUTS = [('Text', BASE + '3drando/text.hpp', False),
                ('CustomMessage', CUSTOM + '.h', False), ('OptionValue', BASE + 'option.h', True),
                ('ItemLocation', BASE + 'item_location.h', True), ('ItemOverride', BASE + 'item_override.h', True),
                ('Hint', BASE + 'hint.h', True), ('TrialInfo', BASE + 'trial.h', True),
                ('Trials', BASE + 'trial.h', True), ('Context', BASE + 'SeedContext.h', True)]


def read(name, projected):
    return ((OUT / 'generated' if projected else ROOT) / name).read_text(encoding='utf-8-sig')


def class_node(text, name):
    return next(n for n in walk(PARSER.parse(text.encode()).root_node)
                if n.type == 'class_specifier' and n.child_by_field_name('name').text.decode() == name)


def class_members(text, name):
    body = class_node(text, name).child_by_field_name('body')
    result = []
    for n in body.named_children:
        if n.type != 'field_declaration':
            continue
        decl = n.child_by_field_name('declarator')
        if decl is not None and not any(c.type == 'function_declarator' for c in walk(decl)):
            result.append((n.child_by_field_name('type').text.decode(), decl.text.decode()))
    return result


def class_signatures(text, name):
    result = []
    for n in walk(class_node(text, name).child_by_field_name('body')):
        if n.type not in ('field_declaration', 'function_definition'):
            continue
        decl = n.child_by_field_name('declarator')
        if decl is None or not any(c.type in ('function_declarator', 'operator_cast') for c in walk(decl)):
            continue
        signature = decl.text.decode()
        # Parameter default spellings differ, but their default values
        # are audited separately. Normalize only those expression spans.
        ranges = []
        for arg in walk(decl):
            if arg.type == 'optional_parameter_declaration':
                value = arg.child_by_field_name('default_value')
                if value is not None:
                    ranges.append((value.start_byte - decl.start_byte, value.end_byte - decl.start_byte))
        raw = signature.encode()
        for a, b in sorted(ranges, reverse=True):
            raw = raw[:a] + b'DEFAULT' + raw[b:]
        typ = n.child_by_field_name('type')
        signature = (typ.text.decode() if typ else '') + ' ' + raw.decode()
        signature = signature.replace('noexcept', 'throw()')
        result.append(re.sub(r'\s+', '', signature))
    return result


def methods(name, projected):
    text = read(name, projected)
    return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type == 'function_definition']


def bounded_methods(projected):
    bodies = []; records = []
    selections = {
        'item_override.cpp': lambda d: True,
        'item_location.cpp': lambda d: not any('::' + n + '(' in d for n in (
            'GetPlacedItem', 'GetPlacedItemName', 'SetPlacedItem', 'MergeAreas', 'GetRandomArea', 'PlaceVanillaItem',
            'ApplyPlacedItemEffect', 'GetPrice', 'SetCheckStatus', 'SetIsSkipped')),
        'trial.cpp': lambda d: d.startswith('TrialInfo::') and '::GetName(' not in d,
        'hint.cpp': lambda d: (d.startswith('Hint::Hint()') or d.startswith('Hint::Hint(RandomizerHint ownKey_, std::vector<CustomMessage>') or
                              any('::' + n + '(' in d for n in ('GetHintType', 'GetHintedLocations', 'GetHintedAreas', 'SetDistribution',
                                  'GetDistribution', 'IsEnabled', 'GetHintTextKeys', 'GetHintedItems', 'GetItemNamesChosen',
                                  'GetHintTextsChosen', 'GetAreaTextsChosen', 'GetHintedTrials', 'GetNum', 'ResetVariables'))),
    }
    for name, select in selections.items():
        selected = [n for n in methods(BASE + name, projected)
                    if select(n.child_by_field_name('declarator').text.decode())]
        bodies.append('namespace Rando {\n' + '\n'.join(n.text.decode() for n in selected) + '\n}')
        records += [dict(source=BASE + name, declaration=n.child_by_field_name('declarator').text.decode(),
                         sha256=hashlib.sha256(n.text).hexdigest()) for n in selected]
    selected = [n for n in methods(CUSTOM + '.cpp', projected)
                if n.child_by_field_name('declarator').text.decode().startswith('CustomMessage::CustomMessage(')]
    bodies.append('\n'.join(n.text.decode() for n in selected))
    records += [dict(source=CUSTOM + '.cpp', declaration=n.child_by_field_name('declarator').text.decode(),
                     sha256=hashlib.sha256(n.text).hexdigest()) for n in selected]
    if projected:
        # Preserve the legacy/modern conversion selection around the exact methods.
        bodies.append(re.sub(r'^#include[^\n]*\n', '', read(BASE + 'OptionValue.cpp', True), flags=re.M))
    else:
        selected = function_nodes(read(BASE + 'option.cpp', False), 'OptionValue::')
        bodies.append('namespace Rando {\n' + '\n'.join(n.text.decode() for n in selected) + '\n}')
    return '\n'.join(bodies), records


def bundle(projected):
    prelude = '''#include <array>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>
#include <cstdint>
#include <cstdio>
#include <cctype>
#include <cassert>
#include <nlohmann/json.hpp>
#include "soh/Enhancements/randomizer/randomizerTypes.h"
#include "soh/Enhancements/item-tables/ItemTableTypes.h"
#include "message_data_textbox_types.h"
class HintText;
namespace Rando { class Item; class Fishsanity; class EntranceShuffler; class Logic;
class Dungeons; class DungeonInfo; class TrialInfo; class Trials; class Kaleido; }
typedef nlohmann::ordered_json oJson;
'''
    z64 = (ROOT / 'soh/include/z64.h').read_text()
    # Exact current enum and macro, not stand-in game definitions.
    prelude += re.search(r'typedef enum \{\s*LANGUAGE_ENG,.*?\} Language;', z64, re.S)[0] + '\n'
    prelude += re.search(r'#define TODO_TRANSLATE[^\n]*', z64)[0] + '\n'
    custom = read(CUSTOM + '.h', False)
    prelude += re.search(r'typedef enum \{\s*MF_FORMATTED,.*?\} MessageFormat;', custom, re.S)[0] + '\n'
    prelude += '\n'.join(re.findall(r'^#define (?:PLURAL|SINGULAR)[^\n]*', read(BASE + '3drando/text.hpp', False), re.M)) + '\n'
    if projected:
        prelude += '#include "randomizer/support.h"\n'
    prelude += '#define private public\n'
    for cls, source, rando in CLASS_INPUTS:
        if projected and cls == 'OptionValue':
            source = BASE + 'OptionValue.h'
        declaration = class_node(read(source, projected), cls).text.decode() + ';\n'
        prelude += ('namespace Rando {\n' + declaration + '}\n') if rando else declaration
    prelude += '#undef private\n'
    definitions, records = bounded_methods(projected)
    return prelude + definitions, records


def layout_prints():
    result = []
    for cls, name, rando in CLASS_INPUTS:
        qualified = ('Rando::' if rando else '') + cls
        result.append('printf("size ' + cls + ' %zu\\n", sizeof(' + qualified + '));')
        for typ, member in class_members(read(name, False), cls):
            if member in ('mContext',):
                continue
            result.append('printf("offset ' + cls + '.' + member + ' %zu\\n", offsetof(' + qualified + ', ' + member + '));')
    return '\n'.join(result)


def host(projected, legacy=False):
    folder = OUT / ('host-projected-legacy' if legacy else 'host-projected' if projected else 'host-original')
    folder.mkdir(parents=True, exist_ok=True)
    source, records = bundle(projected)
    source += (OWN / 'value_contract.cpp').read_text().replace('SHIPYARD_LAYOUT_PRINTS', layout_prints())
    (folder / 'contract.cpp').write_text(source, encoding='utf-8')
    (folder / 'method-inventory.json').write_text(json.dumps(records, indent=2) + '\n')
    compiler, env = ENV['host_environment']()
    includes = ([OUT / 'generated/soh'] if projected else []) + [ROOT / 'soh', ROOT / 'soh/include',
                ROOT / 'platform/shipyard/json/upstream/include', ROOT / 'platform/shipyard',
                ROOT / 'scratch/binary-xdk/generated/include', resolve_platform_base(ROOT) / 'sources']
    command = [compiler, '/nologo', '/std:c++20', '/Zc:preprocessor', '/EHsc', '/GR', '/MD', '/D_CRT_SECURE_NO_WARNINGS']
    if legacy:
        command += ['/DSHIPYARD_RANDOMIZER_LEGACY_BOOL']
    command += ['/I' + str(p) for p in includes] + ['/Fe:' + str(folder / 'contract.exe'),
                '/Fo:' + str(folder / 'contract.obj'), folder / 'contract.cpp']
    compiled = ENV['invoke'](command, folder, 'compile', env, success=False)
    if compiled['returncode']:
        raise AssertionError('\n'.join(line for line in (compiled['stdout'] + compiled['stderr']).splitlines() if 'error ' in line)[:4000])
    return ENV['invoke']([folder / 'contract.exe'], folder, 'run')['stdout']


class RandomizerFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()
        cls.manifest = json.loads((OUT / 'manifest.json').read_text())

    def test_complete_member_layout_inventory(self):
        for cls, source, _ in CLASS_INPUTS:
            other = BASE + 'OptionValue.h' if cls == 'OptionValue' else source
            self.assertEqual(class_members(read(source, False), cls), class_members(read(other, True), cls), cls)
        # The UI scope gate also retains every full Option/derived/group field.
        for cls in ('Option', 'OptionGroup', 'LocationOption', 'TrickSetting'):
            self.assertEqual(class_members(read(BASE + 'option.h', False), cls),
                             class_members(read(BASE + 'option.h', True), cls), cls)

    def test_complete_method_declarations(self):
        for cls, source, _ in CLASS_INPUTS:
            other = BASE + 'OptionValue.h' if cls == 'OptionValue' else source
            original = class_signatures(read(source, False), cls)
            projected = class_signatures(read(other, True), cls)
            if cls == 'OptionValue':
                projected = [s for s in projected if 'operatorBooleanType' not in s]
            self.assertEqual(original, projected, cls)
        for cls in ('Option', 'OptionGroup', 'LocationOption', 'TrickSetting'):
            self.assertEqual(class_signatures(read(BASE + 'option.h', False), cls),
                             class_signatures(read(BASE + 'option.h', True), cls), cls)
        for cls in ('CustomMessageManager', 'MessageNotFoundException'):
            self.assertEqual(class_members(read(CUSTOM + '.h', False), cls), class_members(read(CUSTOM + '.h', True), cls))
            self.assertEqual(class_signatures(read(CUSTOM + '.h', False), cls), class_signatures(read(CUSTOM + '.h', True), cls))

    def test_all_defaults_reach_every_constructor(self):
        defaults = self.manifest['member_defaults']
        self.assertEqual(len(defaults['Context']), 15)
        self.assertEqual(len(defaults['ItemLocation']), 18)
        self.assertEqual(len(defaults['CustomMessage']), 5)
        self.assertEqual(len(defaults['Hint']), 15)
        rows = [r for values in self.manifest['constructor_initializers'].values() for r in values]
        for row in rows:
            name = row['constructor'].split('(')[0].split('::')[-1]
            expected = [m for m in defaults.get(name, []) if m['name'] not in row['explicit']]
            self.assertEqual(row['added'], expected, row['constructor'])
        for cls, source, _ in CLASS_INPUTS:
            other = BASE + 'OptionValue.h' if cls == 'OptionValue' else source
            self.assertFalse(inventory(read(other, True)), other)
        context_source = read(BASE + 'SeedContext.cpp', True)
        self.assertIn('Context::Context() : overrides()', context_source)
        self.assertIn('mFinalSeed(0)', context_source)
        for service in ('EntranceShuffler', 'Dungeons', 'Logic', 'Trials', 'Fishsanity'):
            self.assertIn('std::make_shared<' + service + '>()', context_source)

    def test_emitted_constructor_initializer_expressions(self):
        # Independently inspect the emitted AST, not just generator metadata.
        for source, rows in self.manifest['constructor_initializers'].items():
            if not rows:
                continue
            actual_source = BASE + source if source == 'OptionValue.h' else source
            for row in rows:
                text = read(actual_source, True)
                if row['constructor'].startswith('OptionValue::') and source.endswith('option.cpp'):
                    text = read(BASE + 'OptionValue.cpp', True)
                nodes = [n for n in walk(PARSER.parse(text.encode()).root_node)
                         if n.type == 'function_definition' and n.child_by_field_name('declarator') is not None
                         and n.child_by_field_name('declarator').text.decode() == row['constructor']]
                self.assertEqual(len(nodes), 1, row['constructor'])
                init = next((c for c in nodes[0].named_children if c.type == 'field_initializer_list'), None)
                values = {c.named_children[0].text.decode(): c.named_children[1].text.decode()
                          for c in init.named_children} if init else {}
                for member in row['added']:
                    expected = member['value']
                    if expected == '{}':
                        expected = ''
                    elif expected.startswith('{'):
                        expected = 'Shipyard::Randomizer::MessageDefaults(TODO_TRANSLATE)'
                    self.assertEqual(values[member['name']], '(' + expected + ')')

    def test_option_value_is_canonical(self):
        header = read(BASE + 'option.h', True)
        self.assertIn('#include "OptionValue.h"', header)
        self.assertNotIn('class OptionValue', header)
        self.assertNotIn('OptionValue::', read(BASE + 'option.cpp', True))
        self.assertIn('class OptionValue', read(BASE + 'OptionValue.h', True))
        self.assertIn('Option() = default;', header)
        self.assertIn('TrickSetting() = default;', header)
        # These gated UI types retain their original default-vs-value-init
        # distinction for members without DMIs. They are not facade classes.
        self.assertEqual(inventory(header), {k: v for k, v in inventory(read(BASE + 'option.h', False)).items()
                                            if k != 'OptionValue'})

    def test_generated_hashes(self):
        for name, digest in self.manifest['generated'].items():
            self.assertEqual(hashlib.sha256(read(name, True).encode()).hexdigest(), digest, name)

    def test_all_full_source_functions_retained(self):
        for source in self.manifest['sources']:
            if not source.endswith('.cpp'):
                continue
            original = [n.child_by_field_name('declarator').text.decode() for n in methods(source, False)]
            projected = [n.child_by_field_name('declarator').text.decode() for n in methods(source, True)]
            if source == BASE + 'option.cpp':
                projected += [n.child_by_field_name('declarator').text.decode() for n in methods(BASE + 'OptionValue.cpp', True)
                              if 'operator BooleanType' not in n.child_by_field_name('declarator').text.decode()]
            self.assertCountEqual(original, projected, source)

    def test_original_projected_values_and_layout(self):
        original = host(False)
        self.assertEqual(original, host(True))
        self.assertEqual(original, host(True, True))
        (OUT / 'value-report.json').write_text(json.dumps(dict(equal=True, runs=3,
            option_values=256, constructors='OptionValue/Text/ItemLocation/ItemOverride/Hint/TrialInfo/CustomMessage',
            context='all fields, host offsets/size and generated initializer audit; constructor not linked',
            stdout=original), indent=2) + '\n')

    def test_native_full_header_and_objects(self):
        rows = json.loads((OUT / 'xdk/build.json').read_text())
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row['exit'], 0)
            path = OUT / 'xdk' / (Path(row['source']).stem + '.obj')
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['object_sha256'])
            self.assertEqual(struct.unpack_from('<H', path.read_bytes())[0], 0x1f2)
        # Extract target layout constants from the COFF symbol, never infer
        # Xbox sizes from the host ABI or synthesize an alternate class layout.
        raw = (OUT / 'xdk/xdk_abi.obj').read_bytes()
        _, count, _, symbols, symbol_count, optional, _ = struct.unpack_from('<HHIIIHH', raw)
        strings = symbols + symbol_count * 18
        found = None; i = 0
        while i < symbol_count:
            offset = symbols + i * 18
            if raw[offset:offset + 4] == b'\0' * 4:
                start = strings + struct.unpack_from('<I', raw, offset + 4)[0]
                name = raw[start:raw.index(b'\0', start)].decode()
            else:
                name = raw[offset:offset + 8].rstrip(b'\0').decode()
            value, section, _, _, aux = struct.unpack_from('<IhHBB', raw, offset + 8)
            if name == 'shipyard_randomizer_layout':
                header = 20 + optional + (section - 1) * 40
                pointer = struct.unpack_from('<I', raw, header + 20)[0]
                found = struct.unpack_from('>7I', raw, pointer + value)
            i += 1 + aux
        self.assertIsNotNone(found)
        names = ['Context', 'Hint', 'ItemLocation', 'CustomMessage', 'Text', 'TrialInfo', 'Trials']
        (OUT / 'xdk/layout.json').write_text(json.dumps(dict(zip(names, found)), indent=2) + '\n')

    def test_native_bounded_real_methods(self):
        definitions, records = bounded_methods(True)
        source = OUT / 'xdk/value_methods.cpp'
        source.write_text('#include "soh/Enhancements/randomizer/SeedContext.h"\n'
                          '#include "soh/Enhancements/randomizer/trial.h"\n#include <cassert>\n' + definitions, encoding='utf-8')
        command = json.loads((OUT / 'xdk/build.json').read_text())[0]['command'][:-2]
        obj = OUT / 'xdk/value_methods.obj'
        command += [str(source), '/Fo' + str(obj)]
        result = ENV['invoke'](command, OUT / 'xdk', 'value_methods', success=False)
        self.assertEqual(result['returncode'], 0, '\n'.join(line for line in (result['stdout'] + result['stderr']).splitlines() if 'error ' in line)[:4000])
        self.assertEqual(struct.unpack_from('<H', obj.read_bytes())[0], 0x1f2)
        (OUT / 'xdk/value_methods-receipt.json').write_text(json.dumps(dict(methods=records,
            option_value_methods=4, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest()), indent=2) + '\n')

    def test_native_boolean_rejects_integer_conversion(self):
        source = OUT / 'xdk/boolean_reject.cpp'
        source.write_text('#include "soh/Enhancements/randomizer/OptionValue.h"\n'
                          'int invalid(Rando::OptionValue value) { return value; }\n')
        command = json.loads((OUT / 'xdk/build.json').read_text())[0]['command'][:-2]
        result = ENV['invoke'](command + [str(source), '/Fo' + str(OUT / 'xdk/boolean_reject.obj')],
                               OUT / 'xdk', 'boolean_reject', success=False)
        self.assertNotEqual(result['returncode'], 0)
        self.assertIn('cannot convert', result['stdout'] + result['stderr'])


if __name__ == '__main__':
    unittest.main()
