"""Emit XDK enum traits and exact modern enum declaration/consumer probes.

The generated traits are included after the real enum declarations by a consumer
projection. This does not replace or include any application header in json.hpp.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def generate(output, source_root=ROOT):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / 'scratch/json-xdk').resolve()):
        raise ValueError('output must remain in owned scratch/json-xdk')
    evidence = json.loads((HERE / 'container-consumer-source.json').read_text())
    sources = {}
    for path, digest in evidence['sources'].items():
        raw = (Path(source_root) / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('container consumer SHA-256 mismatch: ' + path)
        sources[path] = raw.decode('utf-8-sig')
    declarations, traits, assertions = [], [], []
    for name, record in evidence['enums'].items():
        source = sources[record['source']]
        block = re.search(r'RANDO_ENUM_BEGIN\(' + name + r'\)(.*?)RANDO_ENUM_END\(' + name + r'\)', source, re.S)
        if block is None:
            raise ValueError('missing actual enum: ' + name)
        # These two actual enums use only consecutive identifiers, with no
        # explicit values. Fail closed if a future source changes that grammar.
        items = re.findall(r'^RANDO_ENUM_ITEM\(([A-Za-z_]\w*)\)\s*$', block[1], re.M)
        residue = re.sub(r'RANDO_ENUM_ITEM\([A-Za-z_]\w*\)', '', block[1])
        residue = re.sub(r'//[^\n]*', '', residue)
        if not items or residue.strip() or len(items) > 0x7fffffff:
            raise ValueError('unsupported enum grammar: ' + name)
        declarations.append('typedef enum ' + name + ' {\n    ' + ',\n    '.join(items) + '\n} ' + name + ';')
        traits.append('template <> struct enum_underlying<' + name + '> { typedef int type; };')
        assertions.append('static_assert(std::is_same<std::underlying_type<' + name + '>::type, int>::value, "modern enum underlying type changed");')
    statements = []
    for statement in evidence['consumer_statements']:
        if statement not in sources[evidence['consumer']]:
            raise ValueError('missing actual enum consumer: ' + statement)
        statements.append(statement)
    trait_text = ('#pragma once\n// Generated for declared modern types; include after the actual declarations.\n'
                  '#if defined(_XBOX)\nnamespace nlohmann { namespace detail {\n' + '\n'.join(traits) + '\n} }\n#endif\n')
    probe = ('#include <nlohmann/json.hpp>\n#include <iostream>\n' + '\n'.join(declarations) +
             '\n#include "modern_enum_traits.hpp"\n#if !defined(_XBOX)\n' + '\n'.join(assertions) + '\n#endif\n'
             'int main() {\n    nlohmann::json payload = nlohmann::json::parse("{\\"rc\\":1,\\"status\\":4}");\n' +
             '\n'.join(statements) + '\n    payload["rc"] = rc;\n    payload["status"] = status;\n'
             '    std::cout << payload.dump() << "\\n";\n}\n')
    output.mkdir(parents=True, exist_ok=True)
    files = {'modern_enum_traits.hpp': trait_text, 'modern_enum_contract.cpp': probe}
    for name, text in files.items():
        (output / name).write_text(text, encoding='utf-8', newline='\n')
    return {'source_sha256': evidence['sources'], 'generated_sha256': {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files},
        'actual_application_integrated': False}
