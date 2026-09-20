# Modern LUS binarytools XDK projection

Implemented and verified 2026-09-20 against Shipwright 9.2.3 LUS commit
`fdcaf6336776d24a6408d016b0a52243f108f250`. The original nine files under
`libultraship/{include,src}/ship/utils/binarytools` remain untouched.

`tools/shipyard/prepare_binary.py` generates the actual BinaryReader,
BinaryWriter, MemoryStream and Stream sources and their five headers under
`scratch/binary-xdk/generated`. This is a bounded compiler projection, not a
replacement resource manager or a test implementation of those classes.

## Owned support and transformations

`binary/endian.h` is the central C/C++ byte-order decision. It defines
`SHIPYARD_BIG_ENDIAN` using `_XBOX && _M_PPC`, GNU byte-order macros, or
`__BIG_ENDIAN__`. The generated original endian header uses that decision for
both `Endianness::Native` and `IS_BIGENDIAN`. BSWAP operations remain
unconditional; BE/LE operations retain their original conversion direction.

`binary/compat.h` provides `Shipyard::Binary` helpers for strong enum wrappers,
value-initialized array allocation and XDK-compatible NaN operations. Generated
enum class values do not implicitly convert to integers or the other enum
domain. Their named constants are nested enum values, which the native compiler
can use in constant expressions. No global preprocessor redefinition of C++
keywords or changes to the `std` namespace are used.

The projection lowers only reviewed whole-line anchors:

- `enum class` becomes a typed wrapper, `final`/`override` syntax is removed,
  and the defaulted Stream destructor becomes an empty body.
- Reader/writer default member initialization moves to every real constructor.
- The two **modern** MemoryStream delegating constructors execute the original
  default constructor body before their own body. Even the temporary empty
  buffer allocation is preserved. The Smash offset constructor is absent.
- `make_unique<char[]>` becomes the owned value-initializing helper. The writer
  string range loop becomes an iterator loop. NaN initialization/testing uses
  the narrow owned helper.
- Physical header guards precede original-source `#line` mappings so the XDK
  does not process the same mapped header twice. Mappings are stable
  `libultraship/...` paths, independent of checkout drive or output directory.

`provenance.json` records the raw SHA-256 hashes of the read-only Smash360
generator/helper used as references and all normalized modern input/helper
hashes. Seven of the nine source inputs matched that donor; both MemoryStream
files use the pinned modern source instead. The copied helper namespace and
all generated identifiers use Shipyard. Running this generator or its tests
does not require either reference checkout.

All nine input hashes and both helper hashes are checked before any output is
written. Hash normalization removes an optional UTF-8 BOM and converts CRLF
to LF; arbitrary source changes still fail closed. Every exact transformation
anchor is checked as well. Identical content is deterministic across LF and
CRLF inputs and repeated runs. Outputs are restricted to owned
`scratch/binary-xdk`; no upstream write path exists. The generated manifest
records the source commit, generator/helper hashes, each input/output hash and
edit count.

## Executed verification and exact commands

From `D:/Projects/3Shipsty9.x`, using Python 3.13:

```powershell
python -B tools/shipyard/tests/test_binary.py --baseline-only
python -B tools/shipyard/tests/test_binary.py
python -B tools/shipyard/prepare_binary.py
python -B tools/shipyard/tests/test_binary_generation.py
python -B tools/shipyard/tests/test_binary.py
```

The second command was deliberately executed before implementing the generator.
It failed with `binary projection has not been implemented`, after the original
host contract passed. The final commands passed: six generator contract tests,
host original/projected differential, four real native translation units and
two native contract objects. Each compiler command, working directory, exit
code and complete output is recorded in `scratch/binary-xdk` JSON files.

Original XDK proof is retained under `scratch/binary-xdk/xdk-original/`:

- `BinaryReader.json`, `BinaryWriter.json`, `MemoryStream.json` and
  `Stream.json` all returned 2. The first errors are C2332/C2236 at the actual
  scoped enum declarations in the original LUS headers.
- `endian-preprocess.json` ran the actual Xbox compiler with `/EP /TC`; it
  returned 2 with C1189, `Original endian detection fails on Xbox PowerPC`.
  Both `_XBOX` and `_M_PPC` were present, but original `IS_BIGENDIAN` was absent.
- `contract.json` records the original C++ header/ABI probe failure.

The native compiler is
`C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/cl.exe`, with
`/nologo /EHsc /D_XBOX /D_XBOX_VER=200`, the real `include/xbox` directory,
the projected LUS include directory and `platform/shipyard` support directory.
Every real `.cpp` is compiled separately with `/c`; there is no link or XEX.
All records under `scratch/binary-xdk/xdk-generated/` returned zero. Object
headers were checked for PowerPC big-endian COFF machine `0x1f2`. The C++
contract checks 32-bit pointers, enum widths and native big-endian selection;
the C contract checks BE identity and LE swapping through the real macros.

Host validation uses VS 2022 MSVC `14.43.34808`, Windows SDK `10.0.26100.0`,
and `/std:c++20 /EHsc /MD /W4` to compile the original and projected real
translation units against the same owned test. Independently packed Python
fixtures cover signed/unsigned 8/16/32/64-bit values, LE/BE floats/doubles,
infinities, negative zero, NaNs and strings. Writer output must equal those
fixture bytes exactly, so matching reader/writer mistakes cannot mask each
other. Both runs produced:

```text
numeric/writer=pass
numeric/writer=pass
ownership/seek/limits/exceptions=pass
```

Additional checks cover all reader/writer construction forms, original raw
input copying, shared ownership, native writer byte order, the two-int write,
start/current/end seek, full-buffer output, bulk reads within bounds, reads
beginning at EOF, exact NaN exception messages and the original no-op Close.
The projected host build also checks zero initialization and enum conversion
constraints. `test_binary_generation.py` checks repeat determinism,
LF/CRLF equivalence, stable source maps, final-input drift without partial
output, changed transformation anchors, helper drift, restricted destination
and complete manifest coverage.

`scratch/binary-xdk/verification.json` records the matched host outputs and
native object hashes, with `target_runtime_executed: false`.

## Preserved limits and next integration

This slice establishes host behavior and actual XDK compilation, not target
runtime execution, a linked application, or resource/archive integration.
Add the generated include directory before original LUS includes and compile
the generated four translation units exactly once in the application build;
retain `platform/shipyard` as an include root.

MemoryStream retains current modern semantics, including
`End = bufferSize - 1 - offset`, its existing cursor/size bookkeeping and its
no-op Flush/Close. The original bulk-read implementation validates the first
byte with `vector::at` but does not validate the entire requested span before
`memcpy_s`. Tests exercise safe in-bounds spans and reads that begin at EOF;
they do not execute a cross-allocation read or claim that bug is repaired.
Any full-span bounds correction needs a separate behavior change and tests.
Smash resource buffer-offset optimization, MIDI padding, resource manager,
game assets and game-specific save logic are not part of this projection.
