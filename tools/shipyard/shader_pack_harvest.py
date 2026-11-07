"""Static shader-key harvest for the prebuilt shader pack.

No game code runs. Two sources feed the key set:
  * every F3DEX2 display list in the O2R archives, simulated with the RDP state
    the interpreter reads (combine, other modes, tile clamp modes, grayscale),
    following OTR display-list calls; state a list inherits from its caller is
    left unknown and filled from the C-side seeds;
  * the game's C sources: the setup display lists in z_rcp.c and every
    constant gDPSetCombine*/RenderMode/OtherMode/CycleType/AlphaCompare call,
    compiled with the gbi.h macros by a host dump program.
The result is a superset of the runtime keys. Misses still compile at runtime
and persist in the appendable cache.
"""
import os
import re
import struct
import zipfile
from multiprocessing import Pool
from pathlib import Path

import shader_pack_keys as keys

DISPLAY_LIST = 0x4F444C54  # 'ODLT'
UCODE_F3DEX2 = 4
OTR_HEADER = 64
EXPANDED = {0x20, 0x31, 0x32, 0x35, 0x33, 0x36, 0x42}
G_TRI1, G_TRI2, G_QUAD, G_TRI1_OTR = 0x05, 0x06, 0x07, 0x26
G_DL, G_ENDDL, G_TEXTURE = 0xDE, 0xDF, 0xD7
G_SETOTHERMODE_H, G_SETOTHERMODE_L, G_RDPSETOTHERMODE = 0xE3, 0xE2, 0xEF
G_SETCOMBINE, G_SETTILE, G_FILLRECT = 0xFC, 0xF5, 0xF6
G_TEXRECT, G_TEXRECTFLIP, G_TEXRECT_WIDE, G_IMAGERECT = 0xE4, 0xE5, 0x37, 0x3C
G_DL_OTR_HASH, G_BRANCH_Z_OTR, G_SETGRAYSCALE = 0x31, 0x35, 0x39
MAX_DEPTH = 32
FULL = (1 << 64) - 1

# StrHash64.cpp: ECMA-182 polynomial, MSB-first table, all-ones start, no final xor.
_POLY = 0x42F0E1EBA9EA3693
_TABLE = []
for _i in range(256):
    _crc = _i << 56
    for _ in range(8):
        _crc = ((_crc << 1) ^ _POLY) & FULL if _crc & (1 << 63) else (_crc << 1) & FULL
    _TABLE.append(_crc)


def crc64(text):
    crc = FULL
    for byte in text.encode('utf-8'):
        crc = _TABLE[((crc >> 56) ^ byte) & 0xFF] ^ ((crc << 8) & FULL)
    return crc


def field(word, shift, width):
    return (word >> shift) & ((1 << width) - 1)


def decode_combine(w0, w1):
    """gfx_set_combine_handler_rdp."""
    rgb = keys.color_comb(field(w0, 20, 4), field(w1, 28, 4), field(w0, 15, 5), field(w1, 15, 3))
    alpha = keys.alpha_comb(field(w0, 12, 3), field(w1, 12, 3), field(w0, 9, 3), field(w1, 9, 3))
    rgb2 = keys.color_comb(field(w0, 5, 4), field(w1, 24, 4), field(w0, 0, 5), field(w1, 6, 3))
    alpha2 = keys.alpha_comb(field(w1, 21, 3), field(w1, 3, 3), field(w1, 18, 3), field(w1, 0, 3))
    return keys.combine_mode(rgb, alpha, rgb2, alpha2)


def parse_display_list(data):
    """ResourceFactoryBinaryDisplayListV0: commands as (op, w0, w1, x0, x1)."""
    if len(data) < OTR_HEADER + 16:
        return None
    order = '<' if data[0] == 0 else '>'
    if struct.unpack_from(order + 'I', data, 4)[0] != DISPLAY_LIST:
        return None
    payload = data[OTR_HEADER:]
    if payload[0] != UCODE_F3DEX2:
        return None
    position = 8  # the ucode byte, then padding to an 8-byte boundary
    commands = []
    while position + 8 <= len(payload):
        w0, w1 = struct.unpack_from(order + 'II', payload, position)
        position += 8
        op = w0 >> 24
        x0 = x1 = 0
        if op in EXPANDED:
            if position + 8 > len(payload):
                break
            x0, x1 = struct.unpack_from(order + 'II', payload, position)
            position += 8
        commands.append((op, w0, w1, x0, x1))
        if op == G_ENDDL:
            break
    return commands


class State:
    __slots__ = ('combine', 'other_mode', 'known', 'tiles', 'first_tile', 'grayscale')

    def __init__(self, combine=None, other_mode=0, known=0):
        self.combine = combine
        self.other_mode = other_mode  # only known bits are meaningful
        self.known = known
        self.tiles = {}
        self.first_tile = None
        self.grayscale = False

    def copy(self):
        other = State(self.combine, self.other_mode, self.known)
        other.tiles = dict(self.tiles)
        other.first_tile = self.first_tile
        other.grayscale = self.grayscale
        return other

    def set_other_mode(self, shift, bits, value):
        """GfxSpSetOtherMode: the value is ORed unmasked, so its set bits are known too."""
        if shift < 0 or bits <= 0 or shift + bits > 64:
            return
        mask = ((1 << bits) - 1) << shift
        value &= FULL
        self.other_mode = (self.other_mode & ~mask) | value
        self.known |= mask | value

    def apply(self, op, w0, w1):
        if op == G_SETCOMBINE:
            self.combine = decode_combine(w0, w1)
        elif op == G_SETOTHERMODE_L:
            self.set_other_mode(31 - field(w0, 8, 8) - field(w0, 0, 8), field(w0, 0, 8) + 1, w1)
        elif op == G_SETOTHERMODE_H:
            self.set_other_mode(63 - field(w0, 8, 8) - field(w0, 0, 8), field(w0, 0, 8) + 1, w1 << 32)
        elif op == G_RDPSETOTHERMODE:
            self.other_mode = (field(w0, 0, 24) << 32) | w1
            self.known = FULL
        elif op == G_SETTILE:
            self.tiles[field(w1, 24, 3)] = (field(w1, 8, 2), field(w1, 18, 2))
        elif op == G_TEXTURE:
            self.first_tile = field(w0, 8, 3)
        elif op == G_SETGRAYSCALE:
            self.grayscale = w1 != 0

    def record(self, kind, tile=None):
        first = tile if tile is not None else (self.first_tile or 0)
        return (kind, self.combine, self.other_mode, self.known, first,
                self.tiles.get(first & 7), self.tiles.get((first + 1) & 7), self.grayscale)


# Worker globals: archive handles and a hash -> (archive, name) map.
_ARCHIVES = []
_NAMES = {}
_PARSED = {}


def _open(paths):
    global _ARCHIVES, _NAMES
    _ARCHIVES = [zipfile.ZipFile(p) for p in paths]
    _NAMES = {}
    for index, archive in enumerate(_ARCHIVES):
        for name in archive.namelist():
            if not name.endswith('/'):
                _NAMES.setdefault(crc64(name), (index, name))


def _commands(key):
    if key not in _PARSED:
        index, name = key
        try:
            _PARSED[key] = parse_display_list(_ARCHIVES[index].read(name))
        except (KeyError, zipfile.BadZipFile, struct.error):
            _PARSED[key] = None
    return _PARSED[key]


def _run(key, state, records, stack):
    commands = _commands(key)
    if not commands or key in stack or len(stack) >= MAX_DEPTH:
        return
    stack = stack + (key,)
    for op, w0, w1, x0, x1 in commands:
        if op in (G_TRI1, G_TRI2, G_QUAD, G_TRI1_OTR):
            records.add(state.record('tri'))
        elif op in (G_TEXRECT, G_TEXRECTFLIP):
            records.add(state.record('texrect', field(w1, 24, 3)))
        elif op in (G_TEXRECT_WIDE, G_IMAGERECT):
            records.add(state.record('texrect'))
        elif op == G_FILLRECT:
            records.add(state.record('fillrect'))
        elif op == G_DL_OTR_HASH:
            target = _NAMES.get(((x0 << 32) | x1) & FULL)
            if target:
                _run(target, state, records, stack)
            if field(w0, 16, 1):
                return
        elif op == G_BRANCH_Z_OTR:
            # Either outcome may occur: take the branch on a copy, then fall through.
            target = _NAMES.get(((x0 << 32) | x1) & FULL)
            if target:
                _run(target, state.copy(), records, stack)
        elif op == G_DL:
            # Segmented calls depend on game state; a branch ends this list.
            if field(w0, 16, 1):
                return
        elif op == G_ENDDL:
            return
        else:
            state.apply(op, w0, w1)


def _is_display_list(key):
    index, name = key
    with _ARCHIVES[index].open(name) as stream:
        header = stream.read(8)
    if len(header) < 8:
        return False
    return struct.unpack_from('<I' if header[0] == 0 else '>I', header, 4)[0] == DISPLAY_LIST


def _simulate(entries):
    records = set()
    lists = 0
    for key in entries:
        if not _is_display_list(key):
            continue
        lists += 1
        _run(key, State(), records, ())
    return lists, records


def display_list_records(archives, jobs):
    """Draw records of every display list, from unknown entry state. Each
    worker opens the archives itself and filters entries by resource type."""
    entries = []
    for index, path in enumerate(archives):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir() and not info.filename.startswith('alt/') and                         info.file_size >= OTR_HEADER + 16:
                    entries.append((index, info.filename))
    chunks = [entries[i::jobs * 8] for i in range(jobs * 8)]
    records = set()
    lists = 0
    with Pool(jobs, initializer=_open, initargs=(list(archives),)) as pool:
        for count, part in pool.imap_unordered(_simulate, chunks):
            lists += count
            records |= part
    return lists, records


# ---- C sources -----------------------------------------------------------

MACROS = ('SetCombineMode', 'SetCombineLERP', 'SetRenderMode', 'SetOtherMode', 'SetCycleType', 'SetAlphaCompare')
CALL = re.compile(r'\bg(s?)DP(' + '|'.join(MACROS) + r')\s*\(')
LERP_TOKENS = {'COMBINED', 'TEXEL0', 'TEXEL1', 'PRIMITIVE', 'SHADE', 'ENVIRONMENT', 'CENTER', 'SCALE',
               'COMBINED_ALPHA', 'TEXEL0_ALPHA', 'TEXEL1_ALPHA', 'PRIMITIVE_ALPHA', 'SHADE_ALPHA', 'ENV_ALPHA',
               'LOD_FRACTION', 'PRIM_LOD_FRAC', 'NOISE', 'K4', 'K5', '0', '1'}
IDENTIFIER = re.compile(r'[A-Za-z_]\w*|0[xX][0-9A-Fa-f]+|\d+')


def _arguments(text, start):
    """Top-level comma-separated arguments of the call whose '(' is at start-1."""
    depth, current, args, i = 1, [], [], start
    while i < len(text) and depth:
        ch = text[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if not depth:
                break
        if ch == ',' and depth == 1:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    args.append(''.join(current).strip())
    return args


def _constant(arg, defined):
    tokens = IDENTIFIER.findall(arg)
    if not tokens or re.sub(r'[\w\s|()<>]', '', arg):
        return False
    return all(t[0].isdigit() or t in defined for t in tokens)


def c_calls(source_roots, defined):
    """Constant state calls as (file, gs-macro expression)."""
    found = []
    for root in source_roots:
        for path in sorted(Path(root).rglob('*')):
            if path.suffix not in ('.c', '.cpp', '.h', '.inc'):
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
            for match in CALL.finditer(text):
                args = _arguments(text, match.end())
                if not match.group(1):
                    args = args[1:]  # display-list pointer
                macro = match.group(2)
                if macro == 'SetCombineLERP':
                    ok = len(args) == 16 and all(a in LERP_TOKENS for a in args)
                else:
                    ok = args and all(_constant(a, defined) for a in args)
                if ok:
                    found.append((path.as_posix(), 'gsDP' + macro + '(' + ', '.join(args) + ')'))
    return found


def setup_table(z_rcp):
    text = Path(z_rcp).read_text(encoding='utf-8')
    start = text.index('Gfx sSetupDL[')
    body = text.index('{', text.index('=', start))
    depth, i = 0, body
    while True:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if not depth:
                break
        i += 1
    return text[body:i + 1]


def setup_functions(z_rcp):
    """Gfx_SetupDL_* function name -> SETUPDL indices it applies."""
    text = Path(z_rcp).read_text(encoding='utf-8')
    names = {}
    for match in re.finditer(r'\b(Gfx_SetupDL_\w+)\s*\([^;{]*\)\s*\{', text):
        end = text.find('\n}', match.end())
        indices = {int(n) for n in re.findall(r'SETUPDL_(\d+)', text[match.end():end])}
        if indices:
            names[match.group(1)] = indices
    return names


def dump_program(table, calls):
    lines = ['#include <stdint.h>', '#include <stdio.h>', '#include "libultraship/libultra/gbi.h"',
             'static Gfx setup[][6] = ' + table + ';',
             'struct Call { const char* file; Gfx g; };',
             'static Call calls[] = {']
    for file, expression in calls:
        lines.append('    { "' + file.replace('\\', '/') + '", ' + expression + ' },')
    lines += ['    { "", gsSPEndDisplayList() }', '};',
              'int main() {',
              '    for (size_t i = 0; i < sizeof(setup) / sizeof(setup[0]); ++i)',
              '        for (int j = 0; j < 6; ++j)',
              '            printf("S %u %08x %08x\\n", (unsigned)i, (unsigned)setup[i][j].words.w0, (unsigned)setup[i][j].words.w1);',
              '    for (size_t i = 0; i + 1 < sizeof(calls) / sizeof(calls[0]); ++i)',
              '        printf("C %s %08x %08x\\n", calls[i].file, (unsigned)calls[i].g.words.w0, (unsigned)calls[i].g.words.w1);',
              '    return 0;', '}']
    return '\n'.join(lines) + '\n'


def c_seeds(dump_output, z_rcp, source_roots):
    """Per-file seed states and C draw records from the dump program's output."""
    setups = {}
    per_file = {}
    for line in dump_output.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        w0, w1 = int(parts[2], 16), int(parts[3], 16)
        if parts[0] == 'S':
            setups.setdefault(int(parts[1]), []).append((w0 >> 24, w0, w1))
        elif parts[0] == 'C':
            per_file.setdefault(parts[1], []).append((w0 >> 24, w0, w1))
    setup_states = {}
    for index, commands in setups.items():
        state = State(combine=0, other_mode=0, known=FULL)
        for op, w0, w1 in commands:
            state.apply(op, w0, w1)
        setup_states[index] = (state.combine, state.other_mode)
    functions = setup_functions(z_rcp)
    call = re.compile(r'\b(' + '|'.join(sorted(functions, key=len, reverse=True)) + r')\s*\(') if functions else None
    modes_seen = {m for _, m in setup_states.values()}
    c_records = set()
    files = set(per_file)
    for root in source_roots:
        for path in Path(root).rglob('*'):
            if path.suffix in ('.c', '.cpp') and call:
                text = path.read_text(encoding='utf-8', errors='replace')
                if call.search(text) or 'FillRectangle' in text or 'TextureRectangle' in text:
                    files.add(path.as_posix())
    for file in files:
        text = Path(file).read_text(encoding='utf-8', errors='replace')
        indices = set()
        if call:
            for match in call.finditer(text):
                indices |= functions[match.group(1)]
        bases = [setup_states[i] for i in sorted(indices) if i in setup_states] or list(setup_states.values())
        modifiers = per_file.get(file, [])
        combines = {b[0] for b in bases} | {decode_combine(w0, w1) for op, w0, w1 in modifiers if op == G_SETCOMBINE}
        modes = {b[1] for b in bases}
        for base in list(modes):
            cumulative = State(other_mode=base, known=FULL)
            for op, w0, w1 in modifiers:
                if op == G_SETCOMBINE:
                    continue
                single = State(other_mode=base, known=FULL)
                single.apply(op, w0, w1)
                cumulative.apply(op, w0, w1)
                modes.add(single.other_mode)
                modes.add(cumulative.other_mode)
        kinds = ['tri'] + (['fillrect'] if 'FillRectangle' in text else []) + \
                (['texrect'] if 'TextureRectangle' in text else [])
        modes_seen |= modes
        for combine in combines:
            for mode in modes:
                for kind in kinds:
                    c_records.add((kind, combine, mode, FULL, 0, None, None, False))
    return set(setup_states.values()), modes_seen, c_records


# ---- expansion ------------------------------------------------------------

_SEEDS = []
_SEED_MODES = []


def _seed(setups, modes):
    """Unknown other-mode bits take every seen C-side mode; an unknown combine
    takes the setup display lists' combines with every such mode."""
    global _SEEDS, _SEED_MODES
    _SEED_MODES = sorted({m & keys.RELEVANT_OTHER_MODE for m in modes})
    combines = sorted({c for c, _ in setups})
    _SEEDS = sorted({(c, m) for c in combines for m in _SEED_MODES} |
                    {(c, m & keys.RELEVANT_OTHER_MODE) for c, m in setups})


def _expand(records):
    found = set()
    for kind, combine, mode, known, first, t0, t1, gray in records:
        tiles = {}
        if t0 is not None:
            tiles[first & 7] = t0
        if t1 is not None:
            tiles[(first + 1) & 7] = t1
        complete = (known & keys.RELEVANT_OTHER_MODE) == keys.RELEVANT_OTHER_MODE
        if combine is not None and complete:
            found |= keys.shader_keys(combine, mode, gray, first, tiles, kind)
        elif combine is not None:
            for seed_mode in _SEED_MODES:
                found |= keys.shader_keys(combine, (seed_mode & ~known) | mode, gray, first, tiles, kind)
        else:
            for seed_combine, seed_mode in _SEEDS:
                found |= keys.shader_keys(seed_combine, (seed_mode & ~known) | mode, gray, first, tiles, kind)
    return found


def expand(records, setups, modes, jobs):
    # Only the option-relevant mode bits can change a key.
    relevant = keys.RELEVANT_OTHER_MODE
    records = sorted({(kind, combine, mode & known & relevant, known & relevant, first, t0, t1, gray)
                      for kind, combine, mode, known, first, t0, t1, gray in records}, key=repr)
    chunks = [records[i::jobs * 8] for i in range(jobs * 8)]
    found = set()
    with Pool(jobs, initializer=_seed, initargs=(list(setups), list(modes))) as pool:
        for part in pool.imap_unordered(_expand, chunks):
            found |= part
    return found


def default_jobs():
    return os.cpu_count() or 1
