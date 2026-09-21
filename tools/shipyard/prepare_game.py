"""True C compilation projection for XDK; never writes release sources.

The failed C-as-C++ experiment is removed. Preprocess and compile with /TC,
preserving C pointer conversions and identifiers. Canonicalize audited _Bool
conversions before using byte storage, and fail closed for unaudited contexts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import types
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_inventory import ROOT, inventory

OUT = ROOT / 'scratch/game-xdk'
TREE = OUT / 'source'
INCLUDE = ROOT / 'platform/shipyard/game/include'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def stable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)

def validate_inputs():
    lock = json.loads((ROOT / 'platform/shipyard/game/source-lock.json').read_text(encoding='utf-8-sig'))
    for name, expected in lock['inputs'].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError('Pinned C projection source drift: ' + name)
    return lock

def summarize_batch(directory):
    report = json.loads((directory / 'compile-report.json').read_text())
    selected = json.loads((directory / 'selected-sources.json').read_text())
    failures = []
    for row in report['results']:
        if row.get('compile_exit') == 0:
            continue
        stem = row['path'].replace('/', '__')[:-2]
        log = (directory / 'logs' / (stem + '.log')).read_text(errors='replace')
        errors = [line for line in log.splitlines() if 'error ' in line or 'Projection rejected:' in line]
        first = errors[0] if errors else 'No compiler error text; inspect full log'
        if row.get('projection_error'):
            category = 'semantic-projection-rejected'
        elif 'C1083' in log:
            category = 'missing-real-dependency-header'
        elif "member of 'MtxF'" in log:
            category = 'incorrect-GBI_FLOATS-configuration'
        elif 'bad suffix on number' in log:
            category = 'XDK-macro-parameter-substitutes-float-suffix'
        elif "'sin' : not a function" in log or "'cos' : not a function" in log or 'soh/include/fp.h' in log:
            category = 'XDK-float-math-macro-collision'
        elif 'C2275' in log:
            category = 'C99-declaration-scope'
        elif "syntax error : '.'" in log:
            category = 'designated-initializer'
        elif "syntax error : '{'" in log:
            category = 'compound-literal-or-aggregate-expression'
        else:
            category = 'other-compiler-error'
        failures.append(dict(path=row['path'], category=category, first_error=first,
                             projection_error=row.get('projection_error'), log=str(directory / 'logs' / (stem + '.log'))))
    summary = dict(selected=len(selected), attempted=len(report['results']), passed=report.get('passed_count'),
                   complete=report.get('complete', False),
                   contains_provisional_GBI_FLOATS=any('/DGBI_FLOATS' in row.get('preprocess_command', []) for row in report['results']),
                   selected_manifest_sha256=digest((directory / 'selected-sources.json').read_bytes()),
                   categories=dict(Counter(item['category'] for item in failures)), failures=failures,
                   scope='Object compiler coverage only; retain exact per-source commands and warnings; no link/runtime parity claim')
    stable(directory / 'compile-summary.json', (json.dumps(summary, indent=2) + '\n').encode())
    return summary

def lower_c(raw):
    validate_inputs()
    sys.path.insert(0, str(ROOT / 'scratch/python-tools'))
    sys.path.insert(0, str(ROOT / 'platform/shipyard/game'))
    import semantic_bool
    from tree_sitter import Language, Parser
    import tree_sitter_c
    parser = Parser(Language(tree_sitter_c.language()))
    # Source-locked native pointer packet: FB_CopyToFramebuffer -> gDPCopyFB ->
    # Interpreter::CopyFrameBuffer bool*, whose only write is true. See README.
    source, stats = semantic_bool.lower(raw, parser, {('FB_CopyToFramebuffer', 4)})
    import aggregate_c
    source, stats['typed_compound_literals'] = aggregate_c.lower(source, parser)
    tree = parser.parse(semantic_bool.parse_view(source))
    case_edits = []
    stack = [tree.root_node]
    case_scopes = 0
    while stack:
        node = stack.pop()
        if node.type == 'case_statement':
            # A declaration after a case label must start a block for C89.
            # Close at the enclosing switch block, not at the next label:
            # declarations remain visible across original fallthrough labels.
            for child in node.named_children:
                if child.type in ('declaration', 'type_definition'):
                    owner = node.parent
                    while owner and owner.type != 'compound_statement':
                        owner = owner.parent
                    if owner is None:
                        raise ValueError('Case declaration without an enclosing block')
                    case_edits.extend([(child.start_byte, b'{ '), (owner.end_byte - 1, b'} ')])
                    case_scopes += 1
        stack.extend(node.named_children)
    for offset, value in sorted(case_edits, reverse=True):
        source = source[:offset] + value + source[offset:]
    path = ROOT / 'platform/shipyard/game/donor/c89_lower.py'
    donor = path.read_bytes()
    module = types.ModuleType('shipyard_c89_lower')
    module.__file__ = str(path)
    text = donor.decode().replace("active = b'/upstream/' in name and name.endswith((b'.c', b'.inc'))",
        "active = b'microsoft xbox 360 sdk/' not in name")
    exec(compile(text, str(path), 'exec'), module.__dict__)
    source, scopes = module.lower(source)
    stats['c89_scopes'] = scopes + case_scopes
    return source, stats

def verify_semantics():
    """Run native C11/projected C on the host; also compile projected corpus /TC on XDK."""
    dest = OUT / 'semantics'
    corpus = (ROOT / 'platform/shipyard/game/bool_semantics.c').read_bytes()
    projected, stats = lower_c(corpus)
    names = re.findall(rb'^(?:_Bool|int|void) (\w+)\(', corpus, re.M)
    for suffix, body in [('native', corpus), ('projected', projected)]:
        prefix = b''.join(b'#define ' + name + b' ' + name + b'_' + suffix.encode() + b'\n' for name in names)
        stable(dest / (suffix + '.c'), prefix + body)
    harness = '''#include <stdio.h>
#include <limits.h>
'''
    integer = ['invoke', 'pointer_store', 'pointer_index', 'pointer_advance', 'field_store', 'cast_value', 'initializer', 'compound_or', 'compound_or_true', 'compound_or_effect', 'side_effect', 'shadow', 'loop_scope', 'case_scope']
    for name in integer:
        harness += 'int ' + name + '_native(int); int ' + name + '_projected(int);\n'
    harness += '_Bool return_int_native(int); unsigned char return_int_projected(int);\n'
    harness += '_Bool return_float_native(double); unsigned char return_float_projected(double);\n'
    harness += 'int main(void) { int values[]={-257,-256,-1,0,1,255,256,257}; double floats[]={-256.5,-0.5,-0.0,0.0,0.5,256.5}; unsigned i;\n'
    harness += 'for(i=0;i<sizeof(values)/sizeof(values[0]);++i) { int x=values[i];\n'
    for name in integer + ['return_int']:
        harness += 'if (' + name + '_native(x) != ' + name + '_projected(x)) { printf("FAIL ' + name + ' %d\\n",x);return 1;}\n'
    harness += '} for(i=0;i<sizeof(floats)/sizeof(floats[0]);++i) if(return_float_native(floats[i])!=return_float_projected(floats[i]))return 2;\n'
    harness += 'puts("PASS native C11/projected C boolean conversion, 256/negative/fractional inputs, direct arguments, pointer/field stores, casts, returns, single evaluation, shadowing and declaration scopes"); return 0; }\n'
    stable(dest / 'harness.c', harness.encode())
    vcvars = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
    executable = dest / 'semantics.exe'
    command = '@echo off\ncall "' + str(vcvars) + '" >nul\nif errorlevel 1 exit /b 1\n'
    command += 'cl /nologo /TC /std:c11 /O2 /W4 /Fo"' + dest.as_posix() + '/" /Fe"' + str(executable) + '" '
    command += ' '.join('"' + str(dest / name) + '"' for name in ['native.c', 'projected.c', 'harness.c'])
    command += '\nif errorlevel 1 exit /b 1\n"' + str(executable) + '"\n'
    stable(dest / 'run.cmd', command.encode())
    run = subprocess.run(['cmd.exe', '/d', '/c', str(dest / 'run.cmd')], cwd=dest, capture_output=True)
    stable(dest / 'host.log', run.stdout + run.stderr)
    xdk = Path(os.environ.get('XEDK', r'C:\Program Files (x86)\Microsoft Xbox 360 SDK'))
    xdk_command = [str(xdk / 'bin/win32/cl.exe'), '/nologo', '/TC', '/c', '/MT', '/W4', '/I' + str(xdk / 'include/xbox'), '/Fo' + str(dest / 'xdk.obj'), str(dest / 'projected.c')]
    native = subprocess.run(xdk_command, capture_output=True)
    stable(dest / 'xdk.log', native.stdout + native.stderr)
    stable(dest / 'report.json', (json.dumps(dict(host_exit=run.returncode, xdk_exit=native.returncode,
           transformations=stats, xdk_command=xdk_command, scope='Host semantics and XDK C object compilation; no Xbox runtime execution'), indent=2) + '\n').encode())
    print((run.stdout + run.stderr).decode(errors='replace'))
    print('XDK C semantic corpus: exit ' + str(native.returncode))
    if native.returncode:
        print((native.stdout + native.stderr).decode(errors='replace'))
    return run.returncode == 0 and native.returncode == 0

def project_header(name, raw):
    text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    changes = []
    if name == 'soh/soh/mixer.c':
        if text.count('static inline ') != 2: raise ValueError('Mixer static inline helper drift')
        text = text.replace('static inline ', 'static __inline ')
        changes.append('XDK inline spelling for the two unchanged internal clamp helpers')
    if name in ('soh/soh/Enhancements/randomizer/randomizer_grotto.c', 'soh/src/code/code_800E4FE0.c'):
        sys.path.insert(0, str(ROOT / 'scratch/python-tools'))
        sys.path.insert(0, str(ROOT / 'platform/shipyard/game'))
        import aggregate_c
        from tree_sitter import Language, Parser
        import tree_sitter_c
        permitted = {('f',)} if name.endswith('code_800E4FE0.c') else {('entranceIndex', 'content', 'scene'), ('entranceIndex', 'room', 'angle', 'pos'), ('x', 'y', 'z')}
        converted, patterns = aggregate_c.ordered_designators(text.encode(), Parser(Language(tree_sitter_c.language())), permitted)
        if not patterns: raise ValueError('Audited designated initializers disappeared')
        text = converted.decode()
        changes.append('Retain all values in proven identical struct/first-union-member order: ' + str(len(patterns)) + ' lists')
    if name == 'soh/src/overlays/gamestates/ovl_file_choose/z_file_choose.c':
        if text.count('const SaveFileMetaInfo* restrict meta') != 1:
            raise ValueError('File-select restrict declaration changed')
        text = text.replace('const SaveFileMetaInfo* restrict meta', 'const SaveFileMetaInfo* __restrict meta')
        changes.append('Use XDK pointer-qualifier spelling only on actual current C parameter')
    if name == 'libultraship/include/ship/utils/color.h':
        for typ, fields in [('Color_RGB8', ('r', 'g', 'b')), ('Color_RGBA8', ('r', 'g', 'b', 'a'))]:
            anchor = '} ' + typ + ';'
            if text.count(anchor) != 1: raise ValueError('Color layout anchor drift')
            args = ', '.join('uint8_t ' + field for field in fields)
            helper = '\nstatic __inline ' + typ + ' Shipyard_Make' + typ + '(' + args + ') { ' + typ + ' value = { ' + ', '.join(fields) + ' }; return value; }'
            text = text.replace(anchor, anchor + helper)
        changes.append('Typed rvalue color factories preserve byte narrowing without compound literals')
    if name == 'soh/soh/Enhancements/item-tables/ItemTableTypes.h':
        body = text[text.index('typedef struct GetItemEntry {'):text.index('} GetItemEntry;')]
        body = re.sub(r'/\*.*?\*/|//[^\n]*', '', body, flags=re.S)
        fields = re.findall(r'\b(\w+)\s+(\w+)\s*;', body)
        if len(fields) != 15: raise ValueError('GetItemEntry field layout drift')
        helper = '\nstatic __inline GetItemEntry Shipyard_MakeGetItemEntry(' + ', '.join(typ + ' ' + field for typ, field in fields) + ') { GetItemEntry value = { ' + ', '.join(field for _, field in fields) + ' }; return value; }\n'
        text = text.replace('} GetItemEntry;', '} GetItemEntry;' + helper)
        changes.append('Generate actual GetItemEntry rvalue factory from all current field types/order')
    if name == 'soh/soh/Enhancements/randomizer/randomizerEnums.h':
        if digest(raw) != '4bfb12b2cc3b9310ae49161841ac47d82410a38c217fe151590e46ec466fe794':
            raise ValueError('Randomizer macro input changed; re-audit')
        old = '#define RANDO_ENUM_ITEM(name, ...) name __VA_OPT__(=) __VA_ARGS__,'
        new = '''#define SHIPYARD_RANDO_APPLY(macro, args) macro args
#define SHIPYARD_RANDO_AUTO(name) name,
#define SHIPYARD_RANDO_VALUE(name, value) name = value,
#define SHIPYARD_RANDO_SELECT(_1, _2, NAME, ...) NAME
#define RANDO_ENUM_ITEM(...) SHIPYARD_RANDO_APPLY(SHIPYARD_RANDO_APPLY(SHIPYARD_RANDO_SELECT, (__VA_ARGS__, SHIPYARD_RANDO_VALUE, SHIPYARD_RANDO_AUTO)), (__VA_ARGS__))'''
        if text.count(old) != 1:
            raise ValueError('Expected one randomizer enum default macro')
        text = text.replace(old, new)
        text += '\n#undef SHIPYARD_RANDO_APPLY\n#undef SHIPYARD_RANDO_AUTO\n#undef SHIPYARD_RANDO_VALUE\n#undef SHIPYARD_RANDO_SELECT\n'
        changes.append('C23 optional assignment -> arity dispatch; preserves custom reflection macros')
    if name == 'soh/src/code/main.c':
        if text.count('#ifdef _WIN32') != 2:
            raise ValueError('Expected two desktop entry guards')
        text = text.replace('#ifdef _WIN32', '#if defined(_WIN32) && !defined(_XBOX)')
        changes.append('Xbox uses actual main body without desktop console/SDL entry setup')
    if name == 'libultraship/include/libultraship/libultra/message.h':
        helpers = []
        for suffix, typ, field in [('8', 'u8', 'data8'), ('16', 'u16', 'data16'), ('32', 'u32', 'data32'), ('PTR', 'void*', 'ptr')]:
            old = '#define OS_MESG_' + suffix + '(x) ((OSMesg){ .' + field + ' = (x) })'
            if text.count(old) != 1:
                raise ValueError('Unexpected OSMesg constructor: ' + suffix)
            function = 'Shipyard_Mesg' + ('Ptr' if suffix == 'PTR' else suffix)
            helpers.append('static __inline OSMesg ' + function + '(' + typ + ' value) { OSMesg result; result.' + field + ' = value; return result; }')
            text = text.replace(old, '#define OS_MESG_' + suffix + '(x) ' + function + '(x)')
        text = text.replace('} OSMesg;', '} OSMesg;\n' + '\n'.join(helpers))
        changes.append('Typed union-return factories replace message compound literals; argument evaluated once')
    if name == 'libultraship/include/ship/audio/AudioChannelsSetting.h':
        old = 'inline const char* AudioChannelsSettingName('
        if text.count(old) != 1:
            raise ValueError('Audio channel inline helper changed')
        text = text.replace(old, 'static __inline const char* AudioChannelsSettingName(')
        changes.append('Header-only inline helper uses XDK C spelling and internal linkage')
    if name == 'soh/include/z64math.h':
        old = '#define IS_ZERO(f) (fabsf(f) < 0.008f)'
        if text.count(old) != 1:
            raise ValueError('IS_ZERO macro changed')
        text = text.replace(old, '#define IS_ZERO(value) (fabsf(value) < 0.008f)')
        changes.append('Avoid XDK preprocessor substituting parameter f inside numeric suffix 0.008f')
    return text.encode(), changes

def stage(sources):
    names = set(sources)
    pending = list(sources)
    while pending:
        source_name = pending.pop()
        source_path = ROOT / source_name
        for include in re.findall(r'^\s*#include\s+"([^"\n]+\.c)"', source_path.read_text(encoding='utf-8-sig'), re.M):
            dependency = (source_path.parent / include).resolve()
            if not dependency.is_relative_to(ROOT.resolve()) or not dependency.is_file():
                raise ValueError('Unresolved textual C dependency: ' + source_name + ': ' + include)
            relative = dependency.relative_to(ROOT).as_posix()
            if relative not in names:
                names.add(relative); pending.append(relative)
    for folder in ('soh', 'libultraship/include', 'ZAPDTR/ZAPD/resource/type'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and path.suffix in ('.h', '.hpp', '.inc', '.inl'):
                names.add(path.relative_to(ROOT).as_posix())
    result = []
    for name in sorted(names):
        raw = (ROOT / name).read_bytes()
        body, edits = project_header(name, raw)
        # Actual physical guards precede line mapping for XDK pragma-once behavior.
        prefix = b''
        if re.match(rb'\s*#pragma\s+once\b', body):
            prefix = b'#pragma once\n'
        data = prefix + ('#line 1 "' + (ROOT / name).as_posix() + '"\n').encode() + body
        stable(TREE / name, data)
        result.append(dict(path=name, original_sha256=digest(raw), output_sha256=digest(data), edits=edits))
    stable(OUT / 'staged-inputs.json', (json.dumps(result, indent=2) + '\n').encode())

def main():
    global OUT, TREE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--keep-going', action='store_true')
    parser.add_argument('--preprocess-only', action='store_true')
    parser.add_argument('--verify-semantics', action='store_true')
    parser.add_argument('--output-full', action='store_true', help='Write this batch below scratch/game-xdk/full')
    parser.add_argument('--summarize', action='store_true', help='Summarize the completed/in-progress full batch without compiling')
    args = parser.parse_args()
    if args.summarize:
        result = summarize_batch(ROOT / 'scratch/game-xdk/full')
        print(json.dumps({key: value for key, value in result.items() if key != 'failures'}, indent=2))
        return 0
    if args.all or args.output_full:
        OUT = ROOT / 'scratch/game-xdk/full'
        TREE = OUT / 'source'
    validate_inputs()
    if args.verify_semantics:
        return 0 if verify_semantics() else 1
    available = {r['path']: r for r in inventory()['files'] if r['role'] == 'application' and r['path'].endswith('.c')}
    selected = sorted(available if args.all else set(args.source or ['soh/src/code/sys_math.c']))
    if set(selected) - available.keys():
        parser.error('Source outside pinned application C selection')
    stage(selected)
    stable(OUT / 'selected-sources.json', (json.dumps([available[name] for name in selected], indent=2) + '\n').encode())
    xdk = Path(os.environ.get('XEDK', r'C:\Program Files (x86)\Microsoft Xbox 360 SDK'))
    cl = xdk / 'bin/win32/cl.exe'
    includes = [INCLUDE, ROOT / 'scratch/codec-xdk/include', ROOT / 'scratch/deps/opus/include'] + [TREE / p for p in ('libultraship/include', 'soh', 'soh/include', 'soh/src', 'soh/assets', 'ZAPDTR/ZAPD/resource/type')] + [xdk / 'include/xbox']
    definitions = ['_XBOX', 'XBOX', 'NDEBUG', 'F3DEX_GBI_2', 'CONTROLLERBUTTONS_T=uint32_t', 'SAL_NO_ATTRIBUTE_DECLARATIONS']
    # Execute the narrow, pinned CVar set/cache-default pattern in release order.
    cvars = {}
    for cmake_path in ('CMake/soh-cvars.cmake', 'CMake/lus-cvars.cmake', 'libultraship/cmake/cvars.cmake'):
        cmake = (ROOT / cmake_path).read_text()
        for name, value, cache in re.findall(r'set\((CVAR_\w+) "([^"]*)"( CACHE STRING "")?\)', cmake):
            value = re.sub(r'\$\{(CVAR_\w+)\}', lambda m: cvars[m[1]], value)
            if not cache or name not in cvars:
                cvars[name] = value
    cvar_header = OUT / 'include/compile_definitions.h'
    stable(cvar_header, ('#pragma once\n' + ''.join('#define ' + name + ' "' + value + '"\n' for name, value in cvars.items())).encode())
    root_cmake = (ROOT / 'CMakeLists.txt').read_text()
    match = re.search(r'set\(SPDLOG_LEVEL_OFF (\d+)\)', root_cmake)
    if not match:
        raise ValueError('Pinned logging cutoff missing')
    definitions += ['LOG_LEVEL_GAME_PRINTS=' + match[1]]
    common = [str(cl), '/nologo', '/MT', '/fp:precise']
    flags = ['/D' + d for d in definitions] + ['/I' + str(p) for p in includes] + ['/FI' + str(cvar_header), '/FI' + str(INCLUDE / 'xdk_math_boundary.h')]
    report = dict(scope='Real C source compilation audit; no archive or runtime parity claim',
                  selected_count=len(selected), complete=False, compiler_sha256=digest(cl.read_bytes()), results=[])
    for name in selected:
        stem = name.replace('/', '__')[:-2]
        output = OUT / 'generated' / (stem + '.c')
        obj = OUT / 'objects' / (stem + '.obj')
        obj.parent.mkdir(parents=True, exist_ok=True)
        preprocess = common + ['/TC', '/E'] + flags + [str(TREE / name)]
        run = subprocess.run(preprocess, cwd=ROOT, capture_output=True)
        row = dict(available[name], preprocess_command=preprocess, preprocess_exit=run.returncode)
        log = run.stderr
        if run.returncode == 0:
            stable(OUT / 'preprocessed' / (stem + '.i'), run.stdout)
            if args.preprocess_only:
                row['preprocess_only'] = True
            else:
                try:
                    data, stats = lower_c(run.stdout)
                    stable(output, data)
                    command = common + ['/TC', '/c', '/Fo' + str(obj), str(output)]
                    compiled = subprocess.run(command, cwd=ROOT, capture_output=True)
                    log += compiled.stdout + compiled.stderr
                    row.update(compile_command=command, compile_exit=compiled.returncode, generated_sha256=digest(data), transformations=stats)
                    if compiled.returncode == 0:
                        row['object_sha256'] = digest(obj.read_bytes())
                except ValueError as error:
                    row['projection_error'] = str(error)
                    log += ('\nProjection rejected: ' + str(error) + '\n').encode()
        stable(OUT / 'logs' / (stem + '.log'), log)
        report['results'].append(row)
        report['completed_count'] = len(report['results'])
        report['passed_count'] = sum(r.get('compile_exit') == 0 for r in report['results'])
        report['complete'] = len(report['results']) == len(selected)
        stable(OUT / 'compile-report.json', (json.dumps(report, indent=2) + '\n').encode())
        okay = row.get('compile_exit') == 0 or row.get('preprocess_only', False)
        print(('PASS ' if okay else 'FAIL ') + name, flush=True)
        if not okay and not args.keep_going and not args.all:
            print(log.decode(errors='replace')[:4000])
            return 1
    return int(any(r.get('compile_exit') != 0 and not r.get('preprocess_only') for r in report['results']))

if __name__ == '__main__':
    raise SystemExit(main())
