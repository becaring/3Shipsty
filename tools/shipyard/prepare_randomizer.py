"""Hash-locked current randomizer value/header foundation for the XDK frontend.

Full feature sources are retained with constructor defaults lowered, but only
the explicitly listed production units are native build inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from cpp_ast import PARSER, walk

OWN = ROOT / 'platform/shipyard/randomizer'
OUT = ROOT / 'scratch/randomizer-xdk'
BASE = 'soh/soh/Enhancements/randomizer/'
CUSTOM = 'soh/soh/Enhancements/custom-message/CustomMessageManager'
COMMIT = 'cb71e22a79bc5d1f688fa881795bbd93094895fc'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def edits_apply(raw, edits):
    for start, end, value in sorted(edits, reverse=True):
        raw = raw[:start] + value.encode() + raw[end:]
    return raw.decode()


def inventory(text):
    result = {}
    for cls in walk(PARSER.parse(text.encode()).root_node):
        if cls.type not in ('class_specifier', 'struct_specifier'):
            continue
        name = cls.child_by_field_name('name')
        body = cls.child_by_field_name('body')
        if name is None or body is None:
            continue
        members = []
        for node in body.named_children:
            if node.type != 'field_declaration':
                continue
            value = node.child_by_field_name('default_value')
            if value is None:
                continue
            declarator = node.child_by_field_name('declarator')
            if declarator.type != 'field_identifier':
                raise ValueError('Unsupported member default: ' + node.text.decode())
            members.append(dict(name=declarator.text.decode(), type=node.child_by_field_name('type').text.decode(),
                                value=value.text.decode()))
        if members:
            result[name.text.decode()] = members
    return result


def initializer(member):
    value = member['value']
    if value == '{}':
        value = ''
    elif value.startswith('{'):
        # The only nonempty DMI list on the foundation path is CustomMessage's
        # three language slots. This owns storage and copies the original list.
        if member['type'] != 'std::vector<std::string>' or value != '{ "", TODO_TRANSLATE, TODO_TRANSLATE }':
            raise ValueError('Unmapped nonempty member initializer: ' + value)
        value = 'Shipyard::Randomizer::MessageDefaults(TODO_TRANSLATE)'
    return member['name'] + '(' + value + ')'


def lower_defaults(text, defaults, audit):
    raw = text.encode(); edits = []
    for node in walk(PARSER.parse(raw).root_node):
        if node.type == 'field_declaration':
            value = node.child_by_field_name('default_value')
            if value is not None:
                eq = next(c for c in node.children if c.type == '=')
                edits.append((eq.start_byte, value.end_byte, ''))
        if node.type != 'function_definition':
            continue
        decl = node.child_by_field_name('declarator')
        if decl is None or decl.type != 'function_declarator':
            continue
        ident = decl.child_by_field_name('declarator')
        if ident is None:
            continue
        qualified = ident.text.decode()
        cls = qualified.split('::')[-1]
        parent = node.parent
        if '::' in qualified:
            if qualified.split('::')[-2] != cls:
                continue
        elif parent.type == 'field_declaration_list' and parent.parent.child_by_field_name('name') is not None:
            if parent.parent.child_by_field_name('name').text.decode() != cls:
                continue
        else:
            continue
        init = next((c for c in node.named_children if c.type == 'field_initializer_list'), None)
        existing = {c.named_children[0].text.decode() for c in init.named_children} if init else set()
        added = [m for m in defaults.get(cls, []) if m['name'] not in existing]
        audit.append(dict(constructor=decl.text.decode(), added=added, explicit=sorted(existing)))
        body = node.child_by_field_name('body')
        default = next((c for c in node.named_children if c.type == 'default_method_clause'), None)
        values = ', '.join(initializer(m) for m in added)
        if body is not None and values:
            edits.append((body.start_byte, body.start_byte, (', ' if init else ': ') + values + ' '))
        elif default is not None:
            edits.append((default.start_byte, default.end_byte, (': ' + values + ' ' if values else '') + '{}'))
    return edits_apply(raw, edits)


def default_arguments(text):
    edits = []
    for node in walk(PARSER.parse(text.encode()).root_node):
        if node.type != 'optional_parameter_declaration':
            continue
        value = node.child_by_field_name('default_value') or node.child_by_field_name('value')
        if value is not None and value.text.strip() == b'{}':
            typ = node.child_by_field_name('type').text.decode()
            edits.append((value.start_byte, value.end_byte, typ + '()'))
    return edits_apply(text.encode(), edits)


def text_header(text):
    # Preserve the original four-language constructor behavior, including its
    # unused Spanish argument. Each braced pointer list is an ordered array.
    pattern = r'for \(std::string\* str : \{ (.*?) \}\) \{'
    index = [0]
    def loop(match):
        n = str(index[0]); index[0] += 1
        return ('std::string* shipyardStrings' + n + '[] = { ' + match[1] + ' };\n'
                '        for (size_t shipyardIndex' + n + ' = 0; shipyardIndex' + n + ' < 4; ++shipyardIndex' + n + ') {\n'
                '            std::string* str = shipyardStrings' + n + '[shipyardIndex' + n + '];')
    text = re.sub(pattern, loop, text)
    if index[0] != 3:
        raise ValueError('Text language loop inventory changed')
    text, count = re.subn(r'return Text\{(.*?)\s*,\s*\};', r'return Text(\1);', text, flags=re.S)
    if count != 2:
        raise ValueError('Text constructor expression inventory changed')
    return '#include <cctype>\n' + text.replace('std::move("")', '""')


def function_nodes(text, prefix):
    return [n for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == 'function_definition' and n.child_by_field_name('declarator') is not None
            and n.child_by_field_name('declarator').text.decode().startswith(prefix)]


def prepare():
    lock = json.loads((OWN / 'sources.lock.json').read_text())
    texts = {}
    for name, digest in lock['sources'].items():
        text = (ROOT / name).read_text(encoding='utf-8-sig')
        if sha(text) != digest:
            raise ValueError('Randomizer source drift: ' + name)
        texts[name] = text
    for name, digest in lock.get('dependencies', {}).items():
        if sha((ROOT / name).read_text(encoding='utf-8-sig')) != digest:
            raise ValueError('Randomizer dependency drift: ' + name)
    defaults = {}
    for name, text in texts.items():
        if name.endswith(('.h', '.hpp')):
            for cls, members in inventory(text).items():
                if cls in defaults:
                    raise ValueError('Ambiguous class DMI inventory: ' + cls)
                defaults[cls] = members
    audit = {}; generated = {}
    def emit(name, text):
        stable(OUT / 'generated' / name, text)
        generated[name] = sha(text)
    option = texts[BASE + 'option.h']
    cls = next(n for n in walk(PARSER.parse(option.encode()).root_node)
               if n.type == 'class_specifier' and n.child_by_field_name('name').text == b'OptionValue')
    option_class = cls.text.decode() + ';'
    option = option[:cls.start_byte] + '// Definition shared with every value/header consumer.\n' + option[cls.end_byte + 1:]
    option = '#include "OptionValue.h"\n' + option
    texts[BASE + 'option.h'] = option
    records = []
    value_header = lower_defaults(option_class, defaults, records)
    value_header = once(value_header, 'explicit operator bool() const;', '''#if !defined(SHIPYARD_RANDOMIZER_LEGACY_BOOL)
    explicit operator bool() const;
#else
    typedef bool (OptionValue::*BooleanType)(uint32_t) const;
    operator BooleanType() const;
#endif''')
    emit(BASE + 'OptionValue.h', '#pragma once\n#include <stdint.h>\n#if defined(_MSC_VER) && _MSC_VER < 1700\n#define SHIPYARD_RANDOMIZER_LEGACY_BOOL\n#endif\nnamespace Rando {\n' + value_header + '\n}\n')
    audit['OptionValue.h'] = records
    for name, text in texts.items():
        records = []
        # Full UI Option types are a declared scope gate. Keep their DMIs and
        # defaulted constructors intact: replacing Option()/TrickSetting() with
        # user-provided constructors would suppress value-initialization of
        # their OTHER scalar members. The canonical OptionValue is fully lowered.
        if name != BASE + 'option.h':
            text = lower_defaults(text, defaults, records)
        audit[name] = records
        if name.endswith('SeedContext.h'):
            text = '#include <ship/utils/binarytools/endianness.h>\n' + text
            text = once(text, '#include "fishsanity.h"', 'namespace Rando { class Fishsanity; }')
            text = once(text, '#include "trial.h"', '#include <unordered_map>')
        elif name.endswith('item_location.h'):
            text = once(text, '#include "static_data.h"', 'namespace Rando { class Item; }\n#include <set>\n#include <vector>')
            text = once(text, '#include "option.h"', '#include "OptionValue.h"')
        elif name.endswith('hint.h'):
            text = once(text, '#include "3drando/hints.hpp"', 'class HintText;')
            text = once(text, 'using oJson = nlohmann::ordered_json;', 'typedef nlohmann::ordered_json oJson;')
        elif name.endswith('trial.h'):
            text = once(text, '#include "static_data.h"', '#include <array>')
        elif name.endswith('3drando/text.hpp'):
            text = text_header(text)
        elif name.endswith('randomizerEnums.h'):
            text = once(text, '#define RANDO_ENUM_ITEM(name, ...) name __VA_OPT__(=) __VA_ARGS__,', '''#define SHIPYARD_RANDOMIZER_AUTO(name) name,
#define SHIPYARD_RANDOMIZER_VALUE(name, value) name = value,
#define SHIPYARD_RANDOMIZER_SELECT(_1, _2, NAME, ...) NAME
#define SHIPYARD_RANDOMIZER_APPLY(macro, args) macro args
#define RANDO_ENUM_ITEM(...) SHIPYARD_RANDOMIZER_APPLY(SHIPYARD_RANDOMIZER_APPLY(SHIPYARD_RANDOMIZER_SELECT, (__VA_ARGS__, SHIPYARD_RANDOMIZER_VALUE, SHIPYARD_RANDOMIZER_AUTO)), (__VA_ARGS__))''')
            text += '\n#undef SHIPYARD_RANDOMIZER_AUTO\n#undef SHIPYARD_RANDOMIZER_VALUE\n#undef SHIPYARD_RANDOMIZER_SELECT\n#undef SHIPYARD_RANDOMIZER_APPLY\n'
        elif name == CUSTOM + '.h':
            text = text.replace('"../../../include/z64item.h"', '<z64item.h>').replace('"../../../include/z64.h"', '<z64.h>')
            text = text.replace('"../../../include/message_data_textbox_types.h"', '<message_data_textbox_types.h>')
            text = '#include "randomizer/support.h"\n' + text
            text = text.replace(' noexcept', ' throw()')
            text = once(text, 'snprintf(message, 500,', 'Shipyard::SohResources::snprintf(message, 500,')
        elif name.endswith('SeedContext.cpp'):
            text = '#include "trial.h"\n' + text
        elif name.endswith('item_location.cpp'):
            text = '#include "static_data.h"\n' + text
            for member in ('hintedBy', 'areas'):
                text = once(text, member + ' = {};', member + '.clear();')
        elif name.endswith('hint.cpp'):
            text = '#include "3drando/hints.hpp"\n' + text
            for member in defaults['Hint']:
                if member['value'] == '{}':
                    text = once(text, member['name'] + ' = {};', member['name'] + '.clear();')
        elif name.endswith('trial.cpp'):
            text = text.replace('TrialInfo::~TrialInfo() = default;', 'TrialInfo::~TrialInfo() {}')
            text = text.replace('Trials::~Trials() = default;', 'Trials::~Trials() {}')
        if name.endswith(('.h', '.hpp')):
            text = default_arguments(text)
        emit(name, text)
    # Extract complete, real value methods from option.cpp. The full projected
    # option.cpp delegates these symbols to this canonical production unit.
    original = (OUT / 'generated' / (BASE + 'option.cpp')).read_text()
    methods = function_nodes(original, 'OptionValue::')
    if len(methods) != 4:
        raise ValueError('OptionValue method inventory changed')
    value_methods = '\n'.join(n.text.decode() for n in methods)
    value_methods = once(value_methods, 'OptionValue::operator bool() const {\n    return mVal != 0;\n}', '''#if !defined(SHIPYARD_RANDOMIZER_LEGACY_BOOL)
OptionValue::operator bool() const {
    return mVal != 0;
}
#else
OptionValue::operator BooleanType() const {
    return (mVal != 0) ? &OptionValue::Is : 0;
}
#endif''')
    emit(BASE + 'OptionValue.cpp', '#include "OptionValue.h"\nnamespace Rando {\n' + value_methods + '\n}\n')
    emit(BASE + 'option.cpp', edits_apply(original.encode(), [(n.start_byte, n.end_byte, '// Defined in canonical OptionValue.cpp.') for n in methods]))
    stable(OUT / 'manifest.json', json.dumps(dict(upstream_commit=lock['source_commit'], sources=lock['sources'],
           dependencies=lock.get('dependencies', {}), generated=generated, member_defaults=defaults, constructor_initializers=audit,
           generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           helpers={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OWN.glob('*.h')},
           retained_modern_member_defaults={'option.h': ['Option', 'OptionGroup']},
           full_native_units=['item_override.cpp', 'OptionValue.cpp'],
           scope_gates=['SeedContext.cpp', 'item_location.cpp', 'hint.cpp', 'trial.cpp', 'option.h UI dependencies', 'option.cpp', 'CustomMessageManager.cpp']), indent=2) + '\n')


def includes():
    from prepare_game_interactor import includes as current_includes
    return [OUT / 'generated/soh', ROOT / 'platform/shipyard'] + current_includes()


def build():
    prepare()
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    folder = OUT / 'xdk'; folder.mkdir(parents=True, exist_ok=True)
    flags = ['/nologo', '/c', '/TP', '/EHsc', '/GR', '/MT', '/D_XBOX', '/D_XBOX_VER=200', '/DF3DEX_GBI_2', '/DNOMINMAX',
             '/DSPDLOG_ACTIVE_LEVEL=0', '/DINCLUDE_MPQ_SUPPORT', '/DCONTROLLERBUTTONS_T=uint32_t',
             '/FI' + str(ROOT / 'scratch/configuration-xdk/generated/include/compile_definitions.h'),
             '/FI' + str(ROOT / 'platform/shipyard/game/include/xdk_math_boundary.h'), '/I' + str(sdk / 'include/xbox')]
    flags += ['/I' + str(p) for p in includes()]
    sources = [OWN / 'xdk_abi.cpp'] + [OUT / 'generated' / BASE / (n + '.cpp') for n in ('item_override', 'OptionValue')]
    rows = []
    for source in sources:
        obj = folder / (source.stem + '.obj')
        command = [str(sdk / 'bin/win32/cl.exe')] + flags + [str(source), '/Fo' + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + '.log'), result.stdout + result.stderr)
        row = dict(source=source.relative_to(ROOT).as_posix(), command=command, exit=result.returncode,
                   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not result.returncode:
            assert struct.unpack_from('<H', obj.read_bytes())[0] == 0x1f2
            row['object_sha256'] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print('\n'.join(line for line in (result.stdout + result.stderr).splitlines() if 'error ' in line)[:5000])
        print(source.stem + ': ' + str(result.returncode)); rows.append(row)
    stable(folder / 'build.json', json.dumps(rows, indent=2) + '\n')
    if any(r['exit'] for r in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    build() if args.build else prepare()
