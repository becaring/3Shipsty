# Release-enabled graphics disassembler

Root CMake enables GFX_DEBUG_DISASSEMBLER. Its exact LUS dependency is libgfxd
008f73dca8ebc9151b205959b17773a19c5bd0da from glankk/libgfxd, recorded in
dependencies.lock.json. It was fetched into owned scratch/dependency-git and
snapshotted with a per-file receipt. No reference tree or pinned source changed.

`python -B tools/shipyard/prepare_gfxd.py --build` builds all seven upstream C
TUs as C, retaining all five ucode targets, public APIs, file and callback I/O,
formatting and macro/argument tables. Native XDK COFF is verified as 0x1f2.
No F3DEX_GBI_2 global define is used for this library: each ucode source owns its
variant, as in upstream. The current GUI does use F3DEX_GBI_2 and the debugger
definition, and all six complete GUI TUs rebuild with the real gfxd header.

Generic Shipyard compatibility (A/B/H/I): 12 C11 alignment declarations map to
the same eight-byte XDK alignment; static inline spelling; binary integer tokens
retain values/suffixes; reached inttypes formats preserve actual int32 ABI; C99
vsnprintf uses independent XDK va_list copies and preserves required length and
bounded termination. XDK's nested comma macro expansion corrupts the 57 combiner
preset rows; these are mechanically expanded from the actual header's aliases
and eight operands before invoking the original token-pasting macro.

After preprocessing each native ucode variant, designated array and structure
initializers are emitted in the actual enum-index/declared-field order, retaining
zero-filled holes and last duplicate values. Named-field assignment order differs
from declaration order in the original macro table; simply removing designators
would corrupt n_arg/n_gfx. The generator derives both layouts and indexes from
the exact sources and rejects unrecognized remaining initializers. The tested
generic C89 scope pass completes native C adaptation.

Endian behavior remains verbatim. gfxd_endian_host decodes native uint32 words
by value and reconstructs canonical words; it is valid on big-endian Xenon.
The GUI's current packed uint32-word input and explicit host/4 setting remain.
No desktop-only blanket byte swap was imported.

`python -B tools/shipyard/test_gfxd.py` executes all complete original and projected
library TUs. 15,360 disassemblies match across five ucodes, every opcode, four
argument patterns and BE/LE/host input. Bounded formatting also matches, including
the real XDK-style CRT branch executed on the Windows host. Host C11 headers use
their native boolean machinery; the generic C89 pass is tested separately and
applied to all seven native TUs. Receipt: scratch/gfxd-xdk/verification.json.
This is host disassembly parity and native compilation, not Xbox GUI execution.
