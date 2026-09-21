"""Hash-locked projection of current LUS Directory, plus reached filesystem audit.

No generator, code or build from a reference checkout is executed. Only outputs
under the owned scratch/filesystem-xdk root are accepted.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OWN = ROOT / 'platform/shipyard/filesystem'
OUT = ROOT / 'scratch/filesystem-xdk'
DIRECTORY = 'libultraship/include/ship/utils/filesystemtools/Directory.h'
RUNTIME_APIS = frozenset(('path current_path exists is_directory is_regular_file remove rename create_directory '
                         'copy_file create_directories file_size absolute filesystem_error directory_entry '
                         'directory_iterator recursive_directory_iterator file_time_type last_write_time '
                         'directory_options').split())
HOST_APIS = frozenset('relative canonical temp_directory_path copy copy_options create_symlink remove_all'.split())


def code_mask(text):
    """Mask comments and literals, retaining offsets/newlines for precise hooks."""
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text, flags=re.S)


def projection_hooks(relative, original):
    """Return exact namespace/include edits, and reject unknown runtime APIs.

    Host extraction calls are classified, never stubbed. Mixed OTRGlobals
    needs an explicit host/platform projection before these hooks can apply.
    """
    locks = json.loads((OWN / 'sources.lock.json').read_text())
    if locks['sources'].get(relative) != digest(original):
        raise ValueError('Filesystem source hash mismatch: ' + relative)
    masked = code_mask(original)
    uses = []
    for match in re.finditer(r'\b(?:std::(?:experimental::)?filesystem|fs)::(\w+)', masked):
        api = match[1]
        uses.append({'api': api, 'line': original.count('\n', 0, match.start()) + 1,
                     'classification': 'runtime-supported' if api in RUNTIME_APIS else
                                       'host-extraction' if api in HOST_APIS else 'unreviewed'})
    edits = []
    for match in re.finditer(r'#if __has_include\(<filesystem>\).*?#endif', original, flags=re.S):
        edits.append({'start': match.start(), 'end': match.end(),
                      'replacement': '#include "filesystem/filesystem.h"\nnamespace fs = xbox_compat::filesystem;'})
    for match in re.finditer(r'\bstd::(?:experimental::)?filesystem\b', masked):
        if not any(e['start'] <= match.start() < e['end'] for e in edits):
            edits.append({'start': match.start(), 'end': match.end(), 'replacement': 'xbox_compat::filesystem'})
    for match in re.finditer(r'^[ \t]*#include[ \t]+<(?:experimental/)?filesystem>', original, flags=re.M):
        if not any(e['start'] <= match.start() < e['end'] for e in edits):
            edits.append({'start': match.start(), 'end': match.end(), 'replacement': '#include "filesystem/filesystem.h"'})
    for edit in edits:
        edit['line'] = original.count('\n', 0, edit['start']) + 1
        edit['expected'] = original[edit['start']:edit['end']]
    return {'path': relative, 'sha256': digest(original), 'uses': uses, 'edits': sorted(edits, key=lambda e: e['start']),
            'ready': all(u['classification'] == 'runtime-supported' for u in uses),
            'remaining_syntax': 'Namespace/include boundary only; callers still lower range-for, auto and other modern syntax.'}


def project_boundary(relative, original):
    """Reusable first pass for owned class projections; no application writes."""
    hooks = projection_hooks(relative, original)
    if not hooks['ready']:
        raise ValueError('Host extraction or unreviewed API requires explicit routing: ' + relative)
    text = original
    for edit in reversed(hooks['edits']):
        text = text[:edit['start']] + edit['replacement'] + text[edit['end']:]
    return text


def normalized(path):
    return path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def transform(original):
    text, count = re.subn(r'#if __has_include\(<filesystem>\).*?#endif',
                          '#include "filesystem.h"\nnamespace fs = xbox_compat::filesystem;',
                          original, count=1, flags=re.S)
    if count != 1:
        raise ValueError('Directory filesystem include shape changed')
    before = 'for (auto& p : fs::recursive_directory_iterator(dir)) {'
    after = ('for (fs::recursive_directory_iterator it(dir), finish; it != finish; ++it) {\n'
             '                const fs::directory_entry& p = *it;')
    if text.count(before) != 1:
        raise ValueError('Directory loop shape changed')
    text = text.replace(before, after)
    old_lines, new_lines = original.splitlines(True), text.splitlines(True)
    mapped = ['#ifndef SHIPYARD_GENERATED_DIRECTORY_H\n#define SHIPYARD_GENERATED_DIRECTORY_H\n']
    for _, old_start, _, new_start, new_end in difflib.SequenceMatcher(
            None, old_lines, new_lines, autojunk=False).get_opcodes():
        if new_start != new_end:
            mapped.append(f'#line {old_start + 1} "{DIRECTORY}"\n')
            mapped.extend(new_lines[new_start:new_end])
    return ''.join(mapped) + '\n#endif\n'


def generate(out=OUT / 'generated'):
    out = out.resolve()
    if not out.is_relative_to(OUT.resolve()):
        raise ValueError('output must stay inside owned scratch/filesystem-xdk')
    locks = json.loads((OWN / 'sources.lock.json').read_text())
    for name, expected in locks['helpers'].items():
        if digest(normalized(OWN / name)) != expected:
            raise ValueError('Filesystem helper hash mismatch: ' + name)
    audit = []; hooks = []
    for relative, expected in locks['sources'].items():
        original = normalized(ROOT / relative)
        if digest(original) != expected:
            raise ValueError('Filesystem source hash mismatch: ' + relative)
        matches = [{'line': n, 'source': line.strip()} for n, line in enumerate(original.splitlines(), 1)
                   if re.search(r'(?:std::filesystem|\bfs::)', line)]
        audit.append({'path': relative, 'sha256': expected, 'uses': matches})
        hooks.append(projection_hooks(relative, original))
    generated = transform(normalized(ROOT / DIRECTORY))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'Directory.h').write_text(generated, encoding='utf-8', newline='\n')
    (out / 'projection-hooks.json').write_text(json.dumps(hooks, indent=2) + '\n', encoding='utf-8')
    manifest = {'consumers': audit, 'generated_directory_sha256': digest(generated),
                'donor_provenance': json.loads((OWN / 'donor-provenance.json').read_text()),
                'helpers': {name: digest(normalized(OWN / name)) for name in ['filesystem.h', 'filesystem.cpp']},
                'changes': ['filesystem include/namespace', 'range-for to input iterator'],
                'limits': 'Actual current Directory header only; other consumers inventoried, not compiled or changed.'}
    (out / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, default=OUT / 'generated')
    arguments = parser.parse_args()
    manifest = generate(arguments.out)
    print('Generated mapped current Directory.h; audited', len(manifest['consumers']), 'locked consumers')
