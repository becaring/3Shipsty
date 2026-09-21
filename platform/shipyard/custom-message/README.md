# Current CustomMessageManager XDK projection

`tools/shipyard/prepare_custom_message.py` compiles the complete pinned modern
`CustomMessageManager.cpp`: all 67 original function definitions, including the
three functions that use live game state. The source is locked to Shipwright
`cb71e22a79bc5d1f688fa881795bbd93094895fc`; the test also compares all five source
inputs with that Git commit after normalizing checkout line endings.

## Integration

Run the existing configuration, resource, logging, and randomizer providers first.
This provider consumes their outputs without modifying them. In particular, the
complete `CustomMessageManager.h`, its constructor projection, and `Text` remain
owned by `prepare_randomizer.py`.

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_custom_message.py --build
C:/Python313/python.exe -B tools/shipyard/test_custom_message.py
```

Compile `scratch/custom-message-xdk/generated/CustomMessageManager.cpp` with
`prepare_custom_message.includes()` before the other include directories and the
flags recorded in `scratch/custom-message-xdk/xdk/build.json`. The generated
`include/CustomMessageManager.h` includes the canonical randomizer provider header
and only projects its two NUL-containing string macros. There is no second class
definition, changed class layout, or replacement message manager. Downstream
consumers that expand those macros need the same macro projection.

The generator lowers five static initializer-list maps to range construction,
20 range loops while preserving value/reference iteration, two scoped if
initializers, `starts_with`, erase-remove, and bounded unsigned decimal conversion.
It explicitly constructs the seven literal arguments at old-XDK rvalue-reference
boundaries. The two dynamic debug messages use the real spdlog string view overload,
including their string length. The two map insertions retain their real result and
duplicate-key behavior. No game services or logging functions are replaced.

## Byte and behavior evidence

The manifest audits 312 string literal occurrences, including the two header
macros: 132 contain non-ASCII bytes and 14 require explicit UDL string lengths.
Every execution byte is emitted as a three-digit octal escape, independent of the
XDK compiler's active code page. Each `s` suffix becomes an explicit-length
`std::string`, preserving embedded NULs. `QM_WHITE` and `HS_HORSE_ARCHERY` each
remain a one-byte string containing zero.

The original literals are independently compiled by host MSVC with `/utf-8`.
Their bytes are compared with the projected host results and with the data of all
312 exported literal arrays in a real PowerPC COFF object. This includes the
universal character escape for soft hyphen, accented translations, Euro and other
three-byte width-table entries, escaped quote/backslash, and control bytes. Native
compilation also emits the full real message object; the test checks its source
hash, object hash, target machine and the presence of all three service-dependent
method symbols.

The host differential extracts the complete canonical classes and 64 original or
projected function bodies, using real STL and spdlog. Its bounded driver compares
all five maps, all three language outputs, every message format, translated and
TODO fallback behavior, control codes, all 256 item-icon bytes, all 256 inserted
numbers and pluralization, names/replacement, metadata, operators, message table
storage/errors, clean/encode paths, wrapping with and without icons, manual pages,
choices, unknown UTF-8 logging, and charset conversion including the C interface.
It also compares host class sizes and member offsets. The current result is 2,462
identical output lines; evidence and command logs are in
`scratch/custom-message-xdk/differential.json`, `host-original`, `host-projected`,
and `xdk/build.json`. All six focused tests pass.

## Exact limits

The host harness does not compile or execute these three service-dependent bodies:

- `CustomMessage::LoadVanillaMessageTableEntry` requires the actual English,
  German and French message tables and `gSaveContext`.
- `CustomMessage::GetForCurrentLanguage` requires `gSaveContext`.
- `CustomMessage::LoadIntoFont` requires `gPlayState`, its real font/message state,
  and `SohUtils::CopyStringToCharBuffer`.

All three remain in the full native object. This task proves full translation-unit
compilation and bounded host behavior, not application linkage, Xbox execution,
font rendering, or live vanilla-message loading. The number of compiled host
bodies is not a coverage claim for every branch.

Original behavior is deliberately retained: `GetAllMessages` formats loop copies,
`Capitalize` changes loop copies, and the width algorithm recognizes only one- or
two-byte entries even though its table includes three-byte entries. The harness
does not invoke the source's unsafe overflowing-line case with no delimiter:
`AutoFormatString` can index `str[npos]` after `find_first_of` fails. None of these
upstream quirks is silently fixed by the projection.
