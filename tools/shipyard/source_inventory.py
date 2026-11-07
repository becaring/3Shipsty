"""Inventory pinned runtime/host sources; reproduce the release's C selection.

Unresolved platform selections are recorded instead of dropping sources that
fail to compile. Listing a source does not mean it compiles.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CMAKE_SHA = '19982f1321c7abc44653eb4263462b88eee598f2f8c3612ba843ce654362e7d8'
BASE = 'cb71e22a79bc5d1f688fa881795bbd93094895fc'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inventory(root=ROOT):
    cmake = (root / 'soh/CMakeLists.txt').read_bytes()
    if sha(cmake) != CMAKE_SHA:
        raise ValueError('Pinned SoH CMake changed; re-audit source selection')
    text = cmake.decode('utf-8')
    excluded = re.findall(r'list\(FILTER src__ EXCLUDE REGEX "([^"]+)"\)', text)
    removed = set(re.findall(r'list\(REMOVE_ITEM src__ "([^"]+)"\)', text))
    restored = set(re.findall(r'list\(APPEND src__ "([^"]+\.c)"\)', text))
    files = []
    for folder in ('soh/src', 'soh/soh', 'libultraship/src', 'ZAPDTR', 'OTRExporter'):
        for path in (root / folder).rglob('*'):
            if not path.is_file() or path.suffix not in ('.c', '.cpp', '.cc', '.cxx', '.mm'):
                continue
            name = path.relative_to(root).as_posix()
            role, reason = 'application', 'Pinned soh__ or src__ CMake source inventory'
            if folder in ('ZAPDTR', 'OTRExporter'):
                role, reason = 'host-tool', 'Pinned PC extraction/export pipeline; runtime dependencies audited separately'
            elif folder == 'libultraship/src':
                role, reason = 'lus-review', 'Current LUS; target and desktop backend selection requires explicit review'
            elif folder == 'soh/src':
                local = path.relative_to(root / 'soh').as_posix()
                if (local in removed or any(re.search(p, local) for p in excluded)) and local not in restored:
                    role, reason = 'upstream-excluded', 'Excluded by pinned soh/CMakeLists.txt src__ rules'
            elif name.startswith('soh/soh/Extractor/'):
                role, reason = 'host-tool', 'Extraction processes execute on the PC; preserve runtime version validation'
            elif name.startswith('soh/soh/Enhancements/speechsynthesizer/') and path.stem.startswith(('Darwin', 'SAPI', 'ESpeak')):
                role, reason = 'platform-review', 'Desktop speech transport; feature requires an explicit platform decision'
            files.append(dict(path=name, sha256=sha(path.read_bytes()), role=role, reason=reason))
    return dict(schema=1, upstream_commit=BASE, cmake_sha256=CMAKE_SHA,
                files=sorted(files, key=lambda r: r['path']))

PATTERNS = {
    'A': r'\b(constexpr|consteval|thread_local|decltype|concept|requires)\b|enum class|\[.*?\]\s*\(',
    'B': r'std::(optional|variant|filesystem|format|span|ranges|make_unique)|#include <(filesystem|optional|variant|format|span)>',
    'C': r'\b(SDL_|CreateProcess|ShellExecute|GetModuleFileName|windows\.h|unistd\.h|dlopen)',
    'D': r'std::(thread|mutex|recursive_mutex|condition_variable|future|shared_future|promise|async|atomic)|BS::thread_pool',
    'E': r'std::filesystem|\b(fopen|rename|remove|mkdir|stat)\s*\(',
    'F': r'BinaryReader|BinaryWriter|Endianness|BSWAP|BE16SWAP|LE32SWAP|ResourceFactory|ArchiveManager',
    'G': r'GfxRenderingAPI|GfxWindowBackend|Framebuffer|ShaderProgram|Prism',
    'H': r'\bva_(arg|start|copy)|\b(bit_cast|memcpy)\s*\(|:\s*\d+\s*;',
}

def candidates(root=ROOT):
    """Lexical review queue only; inactive branches/comments are not proof."""
    result = []
    compiled = {k: re.compile(v) for k, v in PATTERNS.items()}
    for folder in ('soh/soh', 'soh/include', 'libultraship/include', 'libultraship/src'):
        for path in sorted((root / folder).rglob('*')):
            if not path.is_file() or path.suffix not in ('.c', '.cpp', '.h', '.hpp'):
                continue
            for line, content in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                classes = [k for k, pattern in compiled.items() if pattern.search(content)]
                if classes:
                    result.append(dict(path=path.relative_to(root).as_posix(), line=line,
                                       classes=classes, text=content.strip()[:240]))
    return result

def pins(root=ROOT):
    result = []
    for folder in ('.', 'libultraship', 'OTRExporter', 'ZAPDTR'):
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root / folder), *args], text=True).strip()
        result.append(dict(path=folder, commit=git('rev-parse', 'HEAD'),
                           tree=git('rev-parse', 'HEAD^{tree}'), url=git('remote', 'get-url', 'origin')))
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    out = ROOT / 'scratch/audit'
    out.mkdir(parents=True, exist_ok=True)
    result = inventory()
    (out / 'source-inventory.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (out / 'revision-status.json').write_text(json.dumps(pins(), indent=2) + '\n', encoding='utf-8')
    if args.audit:
        (out / 'compatibility-candidates.json').write_text(json.dumps(candidates(), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(Counter(row['role'] for row in result['files'])), sort_keys=True))

if __name__ == '__main__':
    main()
