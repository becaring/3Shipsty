# Shipyard missing C runtime functions

This is generic Shipyard platform compatibility, not 3Shipsty game behavior.
The pinned modern application calls four C functions that the XDK CRT does not
provide: `snprintf`, `roundf`, `truncf`, and `nearbyintf`. These two small source
files define their genuine unmangled C ABI symbols. There is no alternate game
path or replacement caller. Compatibility classification: **B**, missing
standard-library functions; **A**, implementation restricted to XDK-supported
C++ syntax. The sources are original implementations, not copied donor or SDK
code. SDK source was inspected read-only to establish its contracts.

## Floating-point contract

`float.cpp` operates on native IEEE binary32 representation copied with `memcpy`.
It verifies the representation at compile time. This is a runtime native value
boundary; it is not ROM, archive, GPU or serialized data and requires **no
byteswap** on Xenon.

- `roundf` chooses the nearest integer, with exact half ties away from zero,
  independently of the current rounding mode.
- `truncf` rounds toward zero independently of the current mode.
- `nearbyintf` reads the actual current mode through the SDK's `_controlfp(0,0)`
  and implements nearest-even, downward, upward and toward-zero rounding.
- All finite rounding uses integer operations. Signed zeros and infinities are
  preserved. Already integral values are unchanged. NaNs pass through native
  floating-point addition to quiet signaling NaNs and raise native invalid
  according to the caller's exception settings. No finite operation introduces
  inexact, and existing exception flags are not cleared.

Read-only evidence: the installed SDK `include/xbox/float.h` declares
`_controlfp`, `_MCW_RC` and the four `_RC_*` values. Its `Source/crt/float.c`
implements the FPSCR/abstract-mode mapping and the zero-mask query. That API
also synchronizes the kernel FPU exception-enable state with the existing
control word; the wrapper does not change the control word. The implementation
does not use `__frnd`, which could introduce an inexact exception.

**Retain `/fp:strict` for `float.cpp`.** The recipe uses it explicitly, including
under optimization. PPC disassembly confirms integer finite branches and only
NaN-branch `fadds`; the remaining FP instructions transfer exactly representable
float values. Native execution, including Xenon's handling of subnormal argument
transfer and enabled signaling-NaN traps, remains a Xenia/hardware validation
item. Host contract results do not claim that target execution occurred.

## Formatting contract

`format.cpp` uses `_vscprintf` for the required length, then a **fresh**
`va_start` with `_vsnprintf_s(...,_TRUNCATE,...)` when capacity is nonzero.
It returns the required length on truncation; writes a terminating NUL for
nonzero capacity; permits a null destination with zero capacity; and preserves
negative encoding-error results. This supplies C99 length/truncation semantics
on top of the XDK CRT's formatting dialect and locale behavior. It does not
promise support for additional format modifiers absent from that CRT.

The actual unresolved application callers in `z_std_dma.c`, `audio_load.c`,
`fault.c`, and `graph.c` use `%s`, `%d`, `%X` and widths, including the real
audio error's null/zero-capacity length query. Those are supported by the SDK.
Read-only implementation evidence is SDK `Source/crt/vsprintf.c`:
`_TRUNCATE` ensures termination and returns `-1` for truncated output, which
this wrapper translates to the separately calculated required length.

## Reproduction and evidence

Run from the project root:

```powershell
C:/Python313/python.exe -B tools/shipyard/test_crt.py
```

This compiles the **actual production source**, under alternate symbol names
only, alongside the host standard library. It checks all four rounding modes,
every exponent with representative mantissas and both signs, every half-integer
through +/-4096 and its adjacent float values, and 262144 deterministic random
bit patterns. It checks result bits, signed zero, NaN sign/quieting, invalid and
inexact behavior, retained rounding modes and sticky flags. The formatting test
compares required lengths and complete written bytes (including embedded NULs),
capacities 0 through 129, prefix/suffix canaries, a null length query, empty
output and an encoding failure.

The same command compiles both production files with the native Xbox compiler,
checks PPC big-endian COFF machine `0x1f2`, verifies all four C symbols, and
records disassembly. `scratch/crt-xdk/verification.json` contains the receipt.
`scratch/crt-xdk/xdk/build.json` is the production recipe consumed by
`generate_xdk_project.command_rows`; it contains exactly **two production TUs**.
`contract.cpp` is host validation only and is not part of that recipe.

No SDK source is copied or redistributed, and no reference tree is modified.
